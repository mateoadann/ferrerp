#!/usr/bin/env bash
# scripts/restore.sh
# Restaurar FerrERP desde un backup local o de S3.
#
# Uso:
#   ./scripts/restore.sh                          # interactivo (lista backups locales)
#   ./scripts/restore.sh --from-s3                # interactivo (lista backups en S3)
#   ./scripts/restore.sh --file path/to/backup    # archivo especifico (.tar.gz)
#   ./scripts/restore.sh --s3-key backups/xxx.tar.gz  # key especifica de S3
#
# IMPORTANTE: hace un backup automatico antes de restaurar (--tag pre-restore).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

trap 'on_error $LINENO' ERR

# --- Args ---
SOURCE="local"
FILE=""
S3_KEY=""
SKIP_PRE_BACKUP=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --from-s3) SOURCE="s3"; shift ;;
        --file) FILE="$2"; SOURCE="file"; shift 2 ;;
        --s3-key) S3_KEY="$2"; SOURCE="s3-key"; shift 2 ;;
        --skip-pre-backup) SKIP_PRE_BACKUP=true; shift ;;
        -h|--help)
            grep '^#' "$0" | head -15
            exit 0
            ;;
        *) log_error "Argumento desconocido: $1"; exit 1 ;;
    esac
done

load_env
require_cmd docker
init_dirs

# --- Resolver el archivo a restaurar ---
RESTORE_ARCHIVE=""

select_local_backup() {
    log_step "Backups locales disponibles en $BACKUP_DIR"
    mapfile -t backups < <(ls -1t "${BACKUP_DIR}"/ferrerp-*.tar.gz 2>/dev/null || true)
    if [[ ${#backups[@]} -eq 0 ]]; then
        log_error "No hay backups locales en $BACKUP_DIR"
        log_info "Probar: $0 --from-s3"
        exit 1
    fi
    local i=1
    for b in "${backups[@]}"; do
        printf "  [%d] %s (%s)\n" "$i" "$(basename "$b")" "$(du -h "$b" | cut -f1)"
        ((i++))
    done
    local choice
    read -r -p "Numero a restaurar (1-${#backups[@]}): " choice
    if [[ ! "$choice" =~ ^[0-9]+$ ]] || (( choice < 1 || choice > ${#backups[@]} )); then
        log_error "Eleccion invalida"
        exit 1
    fi
    RESTORE_ARCHIVE="${backups[$((choice - 1))]}"
}

select_s3_backup() {
    require_cmd aws
    require_env "S3_BUCKET"
    log_step "Backups en s3://${S3_BUCKET}/backups/"
    mapfile -t s3_keys < <(aws s3 ls "s3://${S3_BUCKET}/backups/" \
        | awk '{print $4}' | grep '^ferrerp-.*\.tar\.gz$' | sort -r || true)
    if [[ ${#s3_keys[@]} -eq 0 ]]; then
        log_error "No hay backups en S3"
        exit 1
    fi
    local i=1
    for k in "${s3_keys[@]}"; do
        printf "  [%d] %s\n" "$i" "$k"
        ((i++))
        [[ $i -gt 20 ]] && break
    done
    local choice
    read -r -p "Numero a restaurar: " choice
    if [[ ! "$choice" =~ ^[0-9]+$ ]] || (( choice < 1 || choice > ${#s3_keys[@]} )); then
        log_error "Eleccion invalida"
        exit 1
    fi
    local s3_path="s3://${S3_BUCKET}/backups/${s3_keys[$((choice - 1))]}"
    RESTORE_ARCHIVE="${BACKUP_DIR}/_from_s3_${s3_keys[$((choice - 1))]}"
    log_info "Descargando $s3_path ..."
    aws s3 cp "$s3_path" "$RESTORE_ARCHIVE" --no-progress
}

case "$SOURCE" in
    local) select_local_backup ;;
    s3)    select_s3_backup ;;
    file)
        [[ -f "$FILE" ]] || { log_error "Archivo no existe: $FILE"; exit 1; }
        RESTORE_ARCHIVE="$FILE"
        ;;
    s3-key)
        require_cmd aws
        require_env "S3_BUCKET"
        RESTORE_ARCHIVE="${BACKUP_DIR}/_from_s3_$(basename "$S3_KEY")"
        log_info "Descargando s3://${S3_BUCKET}/${S3_KEY}"
        aws s3 cp "s3://${S3_BUCKET}/${S3_KEY}" "$RESTORE_ARCHIVE" --no-progress
        ;;
esac

[[ -f "$RESTORE_ARCHIVE" ]] || { log_error "Archivo no encontrado: $RESTORE_ARCHIVE"; exit 1; }

# --- Confirmacion explicita ---
log_step "Vas a RESTAURAR desde: $(basename "$RESTORE_ARCHIVE")"
log_warn "Esto va a SOBRESCRIBIR la base de datos y los uploads actuales."
if ! confirm "Estas seguro?" n; then
    log_info "Cancelado por el usuario"
    exit 0
fi

# --- Backup defensivo antes de restaurar ---
if [[ "$SKIP_PRE_BACKUP" != "true" ]]; then
    log_step "Backup defensivo pre-restore"
    "${SCRIPT_DIR}/backup.sh" --tag "pre-restore" --no-s3
else
    log_warn "Backup pre-restore omitido (--skip-pre-backup)"
fi

# --- Extraer ---
log_step "Extrayendo backup..."
EXTRACT_DIR="${BACKUP_DIR}/_restore_$(date +%s)"
mkdir -p "$EXTRACT_DIR"
tar xzf "$RESTORE_ARCHIVE" -C "$EXTRACT_DIR"
INNER_DIR="$(find "$EXTRACT_DIR" -maxdepth 1 -mindepth 1 -type d | head -1)"
[[ -d "$INNER_DIR" ]] || { log_error "Estructura de backup invalida"; exit 1; }

# --- Verificar manifest ---
if [[ -f "${INNER_DIR}/manifest.json" ]]; then
    log_info "Manifest encontrado:"
    cat "${INNER_DIR}/manifest.json" | head -20
fi

# --- Restaurar DB ---
log_step "Restaurando base de datos"
require_container_running "$DB_CONTAINER"
docker cp "${INNER_DIR}/db.dump" "${DB_CONTAINER}:/tmp/restore.dump"
docker exec "$DB_CONTAINER" pg_restore \
    -U "$DB_USER" -d "$DB_NAME" \
    --clean --if-exists --no-owner --no-acl \
    /tmp/restore.dump
docker exec "$DB_CONTAINER" rm /tmp/restore.dump
log_ok "DB restaurada"

# --- Restaurar uploads ---
if [[ -f "${INNER_DIR}/uploads.tar.gz" ]]; then
    log_step "Restaurando uploads"
    docker run --rm \
        -v "${UPLOADS_VOLUME}:/dst" \
        -v "${INNER_DIR}:/src:ro" \
        alpine sh -c "rm -rf /dst/* /dst/.[!.]* 2>/dev/null; tar xzf /src/uploads.tar.gz -C /dst"
    log_ok "Uploads restaurados"
fi

# --- Reiniciar app para que tome los cambios ---
log_step "Reiniciando container web"
docker restart "$WEB_CONTAINER" >/dev/null
sleep 3
log_ok "Web reiniciado"

# --- Verificacion post-restore ---
log_step "Verificacion"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
    SELECT 'usuarios'  AS tabla, COUNT(*) FROM usuarios UNION ALL
    SELECT 'productos', COUNT(*) FROM productos UNION ALL
    SELECT 'ventas',    COUNT(*) FROM ventas;"

# --- Limpiar ---
rm -rf "$EXTRACT_DIR"
[[ "$RESTORE_ARCHIVE" == *"_from_s3_"* ]] && rm -f "$RESTORE_ARCHIVE"

log_ok "RESTORE COMPLETO"
