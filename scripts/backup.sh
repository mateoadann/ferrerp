#!/usr/bin/env bash
# scripts/backup.sh
# Backup completo de FerrERP: DB + uploads + config, con upload a S3 y rotacion.
#
# Uso:
#   ./scripts/backup.sh              # backup completo a disco + S3
#   ./scripts/backup.sh --no-s3      # solo a disco (sin subir a S3)
#   ./scripts/backup.sh --tag manual # tag custom para identificar
#
# Requiere en .env:
#   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION, S3_BUCKET

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

trap 'on_error $LINENO' ERR

# --- Args ---
UPLOAD_S3=true
TAG=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-s3) UPLOAD_S3=false; shift ;;
        --tag)   TAG="-$2"; shift 2 ;;
        -h|--help)
            grep '^#' "$0" | head -15
            exit 0
            ;;
        *) log_error "Argumento desconocido: $1"; exit 1 ;;
    esac
done

# --- Setup ---
load_env
require_cmd docker
require_container_running "$DB_CONTAINER"
init_dirs

if [[ "$UPLOAD_S3" == "true" ]]; then
    require_cmd aws
    require_env "S3_BUCKET"
fi

TIMESTAMP="$(date -u '+%Y%m%d-%H%M%S')"
BACKUP_NAME="ferrerp-${TIMESTAMP}${TAG}"
WORK_DIR="${BACKUP_DIR}/${BACKUP_NAME}"
ARCHIVE="${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
LOG_FILE="${LOG_DIR}/backup-${TIMESTAMP}.log"

# Redirigir todo a log y a stdout
exec > >(tee -a "$LOG_FILE") 2>&1

log_step "Backup FerrERP - $BACKUP_NAME"
log_info "Destino: $ARCHIVE"
log_info "Log: $LOG_FILE"

mkdir -p "$WORK_DIR"

# --- 1. Dump de la base de datos ---
log_step "1/5 pg_dump (custom format, comprimido)"
docker exec "$DB_CONTAINER" pg_dump \
    -U "$DB_USER" -d "$DB_NAME" \
    --format=custom --compress=9 \
    --file="/tmp/${BACKUP_NAME}.dump"
docker cp "${DB_CONTAINER}:/tmp/${BACKUP_NAME}.dump" "${WORK_DIR}/db.dump"
docker exec "$DB_CONTAINER" rm "/tmp/${BACKUP_NAME}.dump"
log_ok "DB: $(du -h "${WORK_DIR}/db.dump" | cut -f1)"

# --- 2. Volumen de uploads ---
log_step "2/5 Volumen uploads"
docker run --rm \
    -v "${UPLOADS_VOLUME}:/src:ro" \
    -v "${WORK_DIR}:/dst" \
    alpine tar czf /dst/uploads.tar.gz -C /src .
log_ok "Uploads: $(du -h "${WORK_DIR}/uploads.tar.gz" | cut -f1)"

# --- 3. Config (sin .env por seguridad - vive en el VPS) ---
log_step "3/5 Configuracion (nginx + docker-compose)"
tar czf "${WORK_DIR}/config.tar.gz" \
    -C "$PROJECT_DIR" \
    nginx \
    docker-compose.yml
log_ok "Config: $(du -h "${WORK_DIR}/config.tar.gz" | cut -f1)"

# --- 4. Manifest con metadata ---
log_step "4/5 Manifest"
GIT_COMMIT="$(cd "$PROJECT_DIR" && git rev-parse HEAD 2>/dev/null || echo 'unknown')"
GIT_BRANCH="$(cd "$PROJECT_DIR" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')"
ALEMBIC_REV="$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    'SELECT version_num FROM alembic_version' 2>/dev/null || echo 'unknown')"
ROW_COUNTS="$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tAc "
    SELECT json_object_agg(table_name, n)
    FROM (
        SELECT 'usuarios' AS table_name, COUNT(*) AS n FROM usuarios UNION ALL
        SELECT 'empresas',  COUNT(*) FROM empresas UNION ALL
        SELECT 'productos', COUNT(*) FROM productos UNION ALL
        SELECT 'clientes',  COUNT(*) FROM clientes UNION ALL
        SELECT 'ventas',    COUNT(*) FROM ventas
    ) t" 2>/dev/null || echo '{}')"

cat > "${WORK_DIR}/manifest.json" <<EOF
{
  "backup_name": "${BACKUP_NAME}",
  "timestamp_utc": "${TIMESTAMP}",
  "hostname": "$(hostname)",
  "git_commit": "${GIT_COMMIT}",
  "git_branch": "${GIT_BRANCH}",
  "alembic_revision": "${ALEMBIC_REV}",
  "row_counts": ${ROW_COUNTS},
  "files": {
    "db.dump": "$(sha256sum "${WORK_DIR}/db.dump" | awk '{print $1}')",
    "uploads.tar.gz": "$(sha256sum "${WORK_DIR}/uploads.tar.gz" | awk '{print $1}')",
    "config.tar.gz": "$(sha256sum "${WORK_DIR}/config.tar.gz" | awk '{print $1}')"
  }
}
EOF
log_ok "Commit ${GIT_COMMIT:0:7} | Alembic ${ALEMBIC_REV} | $(echo "$ROW_COUNTS" | head -c 80)..."

# --- 5. Empaquetar y limpiar ---
log_step "5/5 Empaquetar archivo final"
tar czf "$ARCHIVE" -C "$BACKUP_DIR" "$BACKUP_NAME"
rm -rf "$WORK_DIR"
SIZE="$(du -h "$ARCHIVE" | cut -f1)"
SHA="$(sha256sum "$ARCHIVE" | awk '{print $1}')"
log_ok "Archivo: $ARCHIVE ($SIZE, sha256:${SHA:0:16}...)"

# --- 6. Upload a S3 ---
if [[ "$UPLOAD_S3" == "true" ]]; then
    log_step "Upload a s3://${S3_BUCKET}/backups/"
    aws s3 cp "$ARCHIVE" "s3://${S3_BUCKET}/backups/${BACKUP_NAME}.tar.gz" \
        --no-progress \
        --metadata "git-commit=${GIT_COMMIT},alembic=${ALEMBIC_REV},sha256=${SHA}"
    log_ok "Subido a S3"
else
    log_warn "Upload a S3 deshabilitado (--no-s3)"
fi

# --- 7. Rotacion local: mantener ultimos 7 backups en disco ---
log_step "Rotacion local (mantener 7 backups en disco)"
KEEP_LOCAL=7
mapfile -t old_backups < <(ls -1t "${BACKUP_DIR}"/ferrerp-*.tar.gz 2>/dev/null | tail -n +$((KEEP_LOCAL + 1)) || true)
if [[ ${#old_backups[@]} -gt 0 ]]; then
    for old in "${old_backups[@]}"; do
        rm -f "$old"
        log_info "Eliminado local: $(basename "$old")"
    done
else
    log_info "Sin backups viejos para rotar"
fi

log_ok "BACKUP COMPLETO: $ARCHIVE ($SIZE)"
