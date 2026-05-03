#!/usr/bin/env bash
# scripts/lib/common.sh
# Funciones comunes para los scripts de operaciones (deploy, backup, restore, rollback).
# Source este archivo desde los demas scripts:  source "$(dirname "$0")/lib/common.sh"

# --- Colores para logs en TTY ---
if [[ -t 1 ]]; then
    readonly C_RESET='\033[0m'
    readonly C_RED='\033[0;31m'
    readonly C_GREEN='\033[0;32m'
    readonly C_YELLOW='\033[0;33m'
    readonly C_BLUE='\033[0;34m'
    readonly C_BOLD='\033[1m'
else
    readonly C_RESET='' C_RED='' C_GREEN='' C_YELLOW='' C_BLUE='' C_BOLD=''
fi

log_info()  { echo -e "${C_BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${C_RESET} $*"; }
log_ok()    { echo -e "${C_GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] OK${C_RESET} $*"; }
log_warn()  { echo -e "${C_YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARN${C_RESET} $*" >&2; }
log_error() { echo -e "${C_RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR${C_RESET} $*" >&2; }
log_step()  { echo -e "\n${C_BOLD}${C_BLUE}==> $*${C_RESET}"; }

# --- Configuracion del proyecto ---
readonly PROJECT_DIR="${PROJECT_DIR:-/opt/apps/ferrerp}"
readonly BACKUP_DIR="${BACKUP_DIR:-/opt/backups/ferrerp}"
readonly LOG_DIR="${LOG_DIR:-/var/log/ferrerp}"
readonly DB_CONTAINER="${DB_CONTAINER:-ferrerp_db}"
readonly WEB_CONTAINER="${WEB_CONTAINER:-ferrerp_web}"
readonly DB_USER="${DB_USER:-ferrerp}"
readonly DB_NAME="${DB_NAME:-ferrerp}"
readonly UPLOADS_VOLUME="${UPLOADS_VOLUME:-ferrerp_uploads_data}"
readonly STATIC_VOLUME="${STATIC_VOLUME:-ferrerp_app_static}"
readonly HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://localhost/auth/login}"
readonly HEALTHCHECK_HOST="${HEALTHCHECK_HOST:-panel.ferrerp.app}"

# --- Variables esperadas en .env ---
require_env() {
    local var_name="$1"
    if [[ -z "${!var_name:-}" ]]; then
        log_error "Variable $var_name no definida. Cargala en /opt/apps/ferrerp/.env"
        exit 1
    fi
}

# Carga el .env del proyecto y exporta las variables
load_env() {
    local env_file="${PROJECT_DIR}/.env"
    if [[ ! -f "$env_file" ]]; then
        log_error ".env no encontrado en $env_file"
        exit 1
    fi
    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a
}

# Verifica que un comando existe
require_cmd() {
    if ! command -v "$1" &>/dev/null; then
        log_error "Comando '$1' no encontrado. Instalalo antes de continuar."
        exit 1
    fi
}

# Verifica que un container Docker existe y esta corriendo
require_container_running() {
    local name="$1"
    if ! docker ps --format '{{.Names}}' | grep -q "^${name}$"; then
        log_error "Container '$name' no esta corriendo"
        exit 1
    fi
}

# Inicializa directorios de trabajo (idempotente)
init_dirs() {
    sudo mkdir -p "$BACKUP_DIR" "$LOG_DIR"
    sudo chown -R "$(whoami):$(whoami)" "$BACKUP_DIR" "$LOG_DIR"
}

# Confirmacion interactiva con default
confirm() {
    local prompt="${1:-Continuar?}"
    local default="${2:-n}"
    local yn_hint
    if [[ "$default" == "y" ]]; then yn_hint="[Y/n]"; else yn_hint="[y/N]"; fi
    local reply
    read -r -p "$prompt $yn_hint " reply
    reply="${reply:-$default}"
    [[ "$reply" =~ ^[Yy]$ ]]
}

# Cleanup en caso de error - usar con trap
on_error() {
    local exit_code=$?
    log_error "Script fallo en linea $1 (exit $exit_code)"
    exit "$exit_code"
}

# Setear traps estandar al inicio de cada script:
#   trap 'on_error $LINENO' ERR
