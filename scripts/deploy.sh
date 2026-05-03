#!/usr/bin/env bash
# scripts/deploy.sh
# Deploy seguro: backup pre-deploy + git pull + build + up + healthcheck + rollback automatico.
#
# Uso:
#   ./scripts/deploy.sh                 # deploy del HEAD de la rama actual
#   ./scripts/deploy.sh --branch main   # checkout a una rama especifica
#   ./scripts/deploy.sh --no-backup     # saltear backup pre-deploy (NO recomendado)
#   ./scripts/deploy.sh --skip-build    # saltear rebuild de la imagen
#
# Ejecutar EN EL VPS, dentro de /opt/apps/ferrerp.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

trap 'on_error $LINENO' ERR

# --- Args ---
TARGET_BRANCH=""
DO_BACKUP=true
DO_BUILD=true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --branch) TARGET_BRANCH="$2"; shift 2 ;;
        --no-backup) DO_BACKUP=false; shift ;;
        --skip-build) DO_BUILD=false; shift ;;
        -h|--help)
            grep '^#' "$0" | head -15
            exit 0
            ;;
        *) log_error "Argumento desconocido: $1"; exit 1 ;;
    esac
done

cd "$PROJECT_DIR"
load_env
require_cmd docker
require_cmd git

LOG_FILE="${LOG_DIR}/deploy-$(date -u '+%Y%m%d-%H%M%S').log"
init_dirs
exec > >(tee -a "$LOG_FILE") 2>&1

log_step "Deploy FerrERP"
log_info "Log: $LOG_FILE"

# --- 1. Estado inicial - guardar para rollback ---
PREV_COMMIT="$(git rev-parse HEAD)"
PREV_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
log_info "Estado actual: ${PREV_BRANCH} @ ${PREV_COMMIT:0:7}"

if ! git diff --quiet || ! git diff --cached --quiet; then
    log_error "Hay cambios sin commitear en $PROJECT_DIR. Limpia el working tree antes."
    git status --short
    exit 1
fi

# --- 2. Backup pre-deploy ---
if [[ "$DO_BACKUP" == "true" ]]; then
    log_step "Backup pre-deploy"
    "${SCRIPT_DIR}/backup.sh" --tag "pre-deploy" --no-s3
    PRE_DEPLOY_BACKUP="$(ls -1t "${BACKUP_DIR}"/ferrerp-*-pre-deploy.tar.gz | head -1)"
    log_ok "Backup: $(basename "$PRE_DEPLOY_BACKUP")"
else
    log_warn "Backup pre-deploy omitido (--no-backup)"
    PRE_DEPLOY_BACKUP=""
fi

# --- 3. Fetch y checkout ---
log_step "git fetch"
git fetch --all --prune

if [[ -n "$TARGET_BRANCH" ]]; then
    log_info "Checkout a $TARGET_BRANCH"
    git checkout "$TARGET_BRANCH"
fi

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
log_info "Pull origin/${CURRENT_BRANCH}"
git pull --ff-only origin "$CURRENT_BRANCH"
NEW_COMMIT="$(git rev-parse HEAD)"

if [[ "$NEW_COMMIT" == "$PREV_COMMIT" ]]; then
    log_warn "No hay cambios nuevos para deployar (commit: ${NEW_COMMIT:0:7})"
    if ! confirm "Continuar igual con build/up?" n; then
        log_info "Cancelado"
        exit 0
    fi
fi

log_info "Nuevo commit: ${NEW_COMMIT:0:7}"

# --- 4. Build ---
if [[ "$DO_BUILD" == "true" ]]; then
    log_step "Build imagen"
    docker compose build --pull web
fi

# --- 5. Up ---
log_step "docker compose up -d"
docker compose up -d --remove-orphans

# --- 6. Esperar a que el web este listo ---
log_step "Esperando container web (max 60s)"
for i in {1..30}; do
    if docker ps --filter "name=${WEB_CONTAINER}" --filter "status=running" --format '{{.Names}}' | grep -q "$WEB_CONTAINER"; then
        log_info "Container corriendo"
        break
    fi
    sleep 2
done

sleep 5  # gunicorn arranca

# --- 7. Healthcheck ---
log_step "Healthcheck"
HEALTH_OK=false
for i in {1..15}; do
    HTTP_CODE="$(curl -s -o /dev/null -w '%{http_code}' \
        --max-time 5 \
        -H "Host: ${HEALTHCHECK_HOST}" \
        "$HEALTHCHECK_URL" || true)"
    if [[ "$HTTP_CODE" =~ ^(200|302)$ ]]; then
        log_ok "Healthcheck OK ($HTTP_CODE)"
        HEALTH_OK=true
        break
    fi
    log_info "Intento $i/15: HTTP $HTTP_CODE - reintentando..."
    sleep 2
done

# --- 8. Rollback si falla healthcheck ---
if [[ "$HEALTH_OK" != "true" ]]; then
    log_error "Healthcheck FALLO. Iniciando rollback automatico."
    log_warn "Revertir codigo a ${PREV_COMMIT:0:7}..."
    git checkout "$PREV_COMMIT"

    if [[ "$DO_BUILD" == "true" ]]; then
        docker compose build web
    fi
    docker compose up -d

    if [[ -n "$PRE_DEPLOY_BACKUP" ]]; then
        log_warn "Restaurando DB del backup pre-deploy..."
        "${SCRIPT_DIR}/restore.sh" --file "$PRE_DEPLOY_BACKUP" --skip-pre-backup <<< "y"
    fi

    log_error "ROLLBACK COMPLETADO. Revisa los logs: $LOG_FILE"
    exit 1
fi

# --- 9. Limpiar imagenes viejas ---
log_step "Limpieza imagenes dangling"
docker image prune -f >/dev/null 2>&1 || true

log_ok "DEPLOY EXITOSO: ${PREV_COMMIT:0:7} -> ${NEW_COMMIT:0:7}"
