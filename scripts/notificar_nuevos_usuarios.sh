#!/bin/bash
# Notificar por email cuando hay nuevos usuarios registrados.
# Corre cada 1 hora via cron en el VPS de produccion.
#
# Uso: ./notificar_nuevos_usuarios.sh
# Cron: 0 * * * * /opt/ferrerp/scripts/notificar_nuevos_usuarios.sh >> /var/log/ferrerp_notif.log 2>&1

set -euo pipefail

# --- Configuracion ---
DB_CONTAINER="ferrerp_db"
DB_USER="ferrerp"
DB_NAME="ferrerp"

SMTP_SERVER="smtp.gmail.com"
SMTP_PORT="587"
SMTP_USER="agente.mat30@gmail.com"
SMTP_PASS="fklx tvhs kkzl nuye"

DESTINATARIOS="mateoadan02@gmail.com,agente.mat30@gmail.com,luciano.javier.adan@gmail.com"
REMITENTE="agente.mat30@gmail.com"

ESTADO_FILE="/tmp/ferrerp_ultimo_check_usuarios.txt"

# --- Obtener timestamp del ultimo check ---
if [ -f "$ESTADO_FILE" ]; then
    ULTIMO_CHECK=$(cat "$ESTADO_FILE")
else
    # Primera ejecucion: solo verificar la ultima hora
    ULTIMO_CHECK=$(date -u -d '1 hour ago' '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date -u -v-1H '+%Y-%m-%d %H:%M:%S')
fi

# Guardar timestamp actual para el proximo check
date -u '+%Y-%m-%d %H:%M:%S' > "$ESTADO_FILE"

# --- Consultar nuevos usuarios ---
QUERY="SELECT id, nombre, email, rol, created_at::text FROM usuarios WHERE created_at > '$ULTIMO_CHECK' ORDER BY created_at DESC;"

RESULTADO=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -A -F '|' -c "$QUERY" 2>/dev/null || echo "")

# Si no hay resultados, salir silenciosamente
if [ -z "$RESULTADO" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sin nuevos usuarios."
    exit 0
fi

# --- Armar el mensaje ---
CANTIDAD=$(echo "$RESULTADO" | wc -l | tr -d ' ')
echo "[$(date '+%Y-%m-%d %H:%M:%S')] $CANTIDAD nuevo(s) usuario(s) detectado(s)."

DETALLE=""
while IFS='|' read -r id nombre email rol created_at; do
    DETALLE="${DETALLE}
- ${nombre} (${email}) — Rol: ${rol} — Fecha: ${created_at}"
done <<< "$RESULTADO"

ASUNTO="[FerrERP] ${CANTIDAD} nuevo(s) usuario(s) registrado(s)"

CUERPO="Hola,

Se registraron ${CANTIDAD} nuevo(s) usuario(s) en panel.ferrerp.app:
${DETALLE}

Revisalo en el panel de superadmin:
https://panel.ferrerp.app/superadmin/empresas

---
FerrERP — Notificacion automatica"

# --- Enviar email via Python (disponible en el VPS) ---
python3 - <<PYEOF
import smtplib
from email.mime.text import MIMEText

msg = MIMEText("""$CUERPO""")
msg['Subject'] = "$ASUNTO"
msg['From'] = "$REMITENTE"
msg['To'] = "$DESTINATARIOS"

with smtplib.SMTP("$SMTP_SERVER", $SMTP_PORT) as server:
    server.starttls()
    server.login("$SMTP_USER", "$SMTP_PASS")
    server.sendmail("$REMITENTE", "$DESTINATARIOS".split(","), msg.as_string())

print("Email enviado correctamente.")
PYEOF

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Email enviado a $DESTINATARIOS"
