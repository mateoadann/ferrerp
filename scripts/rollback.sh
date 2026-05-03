#!/usr/bin/env bash
# scripts/rollback.sh
# Rollback al ultimo "estado bueno conocido" - el backup pre-deploy mas reciente.
#
# Uso:
#   ./scripts/rollback.sh           # rollback al ultimo backup pre-deploy
#   ./scripts/rollback.sh --commit  # rollback solo de codigo (sin DB)
#
# Diferencia con restore.sh:
#   - restore.sh es interactivo y elegis cualquier backup
#   - rollback.sh es automatico al "estado anterior al ultimo deploy"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

trap 'on_error $LINENO' ERR

# --- Args ---
ONLY_COMMIT=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --commit) ONLY_COMMIT=true; shift ;;
        -h|--help) grep '^#' "$0" | head -12; exit 0 ;;
        *) log_error "Argumento desconocido: $1"; exit 1 ;;
    esac
done

cd "$PROJECT_DIR"
load_env
require_cmd docker
require_cmd git

log_step "Rollback FerrERP"

# --- 1. Codigo: volver al penultimo commit ---
log_info "Commit actual: $(git rev-parse --short HEAD) ($(git log -1 --pretty=%s))"
PREV_COMMIT="$(git rev-parse HEAD~1 2>/dev/null || echo '')"
if [[ -z "$PREV_COMMIT" ]]; then
    log_error "No hay commit anterior al cual hacer rollback"
    exit 1
fi
log_warn "Rollback de codigo a: ${PREV_COMMIT:0:7} ($(git log -1 --pretty=%s "$PREV_COMMIT"))"

if ! confirm "Confirmar rollback?" n; then
    log_info "Cancelado"
    exit 0
fi

git checkout "$PREV_COMMIT"
log_ok "Codigo revertido"

# --- 2. Rebuild + up ---
log_step "Rebuild y restart"
docker compose build web
docker compose up -d

# --- 3. DB: restore del ultimo backup pre-deploy (si corresponde) ---
if [[ "$ONLY_COMMIT" == "true" ]]; then
    log_warn "Solo rollback de codigo (--commit). DB queda como esta."
else
    PRE_DEPLOY_BACKUP="$(ls -1t "${BACKUP_DIR}"/ferrerp-*-pre-deploy.tar.gz 2>/dev/null | head -1 || true)"
    if [[ -z "$PRE_DEPLOY_BACKUP" ]]; then
        log_warn "No hay backup pre-deploy local. DB queda como esta."
    else
        log_info "Backup encontrado: $(basename "$PRE_DEPLOY_BACKUP")"
        if confirm "Restaurar tambien la DB desde este backup?" y; then
            "${SCRIPT_DIR}/restore.sh" --file "$PRE_DEPLOY_BACKUP" --skip-pre-backup <<< "y"
        fi
    fi
fi

# --- 4. Healthcheck ---
log_step "Healthcheck"
sleep 5
HTTP_CODE="$(curl -s -o /dev/null -w '%{http_code}' \
    --max-time 5 \
    -H "Host: ${HEALTHCHECK_HOST}" \
    "$HEALTHCHECK_URL" || true)"
if [[ "$HTTP_CODE" =~ ^(200|302)$ ]]; then
    log_ok "App responde ($HTTP_CODE)"
else
    log_error "App no responde correctamente ($HTTP_CODE). Revisa logs: docker logs ferrerp_web"
    exit 1
fi

log_ok "ROLLBACK COMPLETADO"
