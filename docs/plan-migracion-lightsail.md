# Plan de Migracion: FerrERP de Hostinger a AWS Lightsail

## Contexto

FerrERP corre en un VPS de Hostinger (1 vCPU, 4GB RAM, 50GB NVMe) con uso minimo (2% CPU, 720MB RAM, 8GB disco). Se migra a AWS Lightsail **$12/mo** (2 vCPUs, 2GB RAM, 60GB SSD) para mejor infraestructura AWS, 90 dias gratis, y aprovechar para agregar backups automaticos. Hay 1 usuario en produccion con datos reales. DNS en Cloudflare facilita el cutover.

## Decision: Lightsail $12/mo

La de $7 (1GB RAM) es muy justa para Flask + PostgreSQL + Nginx + WeasyPrint. La de $12 (2GB RAM) da margen suficiente + swap como safety net.

## Tiempo estimado: ~2-3 horas total, ~55 min de downtime

---

## Phase 0 — Pre-Migracion (30 min, dias antes)

1. **SSH a Hostinger**, confirmar servicios healthy: `docker-compose ps`
2. **Copiar `.env`** completo a lugar seguro (password manager). Especialmente `SECRET_KEY` y `DB_PASSWORD`
3. **Backup de prueba**: `docker exec ferrerp_db pg_dump -U ferrerp -Fc ferrerp > ferrerp_backup_pre.dump` y descargar via `scp`
4. **Cloudflare**: anotar IPs actuales de los 3 registros A (`ferrerp.app`, `www.ferrerp.app`, `panel.ferrerp.app`). Bajar TTL a 1 min
5. **Verificar** Cloudflare SSL mode = "Full (strict)"
6. **Preparar SSH key** para Lightsail (o usar la default de AWS)

## Phase 1 — Setup Lightsail (20 min, sin downtime)

1. **Crear instancia**: Ubuntu 22.04 LTS, $12/mo, region `sa-east-1` (Sao Paulo)
2. **Static IP**: crear y asociar a la instancia (gratis mientras este attached)
3. **Firewall Lightsail**: abrir puertos 22, 80, 443
4. **Setup del servidor**:
   ```bash
   sudo apt-get update && sudo apt-get upgrade -y
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker ubuntu
   sudo apt-get install -y git htop

   # Swap de 2GB (safety net para WeasyPrint)
   sudo fallocate -l 2G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
   sudo sysctl -p
   ```

## Phase 2 — Deploy App en Lightsail (15 min, sin downtime)

1. **Clonar repo**: `git clone <repo-url> /home/ubuntu/ferrerp`
2. **Crear `.env`** con los MISMOS valores de Hostinger (especialmente `SECRET_KEY`)
3. **Copiar `ferrerp-init.conf`** como config nginx activa (HTTP-only para certbot)
   ```bash
   cp nginx/conf.d/ferrerp-init.conf nginx/conf.d/active.conf
   ```
4. No arrancar el stack todavia

## Phase 3 — Migracion de Datos (20 min, DOWNTIME EMPIEZA)

1. **Parar web y nginx en Hostinger** (dejar DB corriendo):
   ```bash
   docker-compose stop web nginx
   ```
2. **Dump final**:
   ```bash
   docker exec ferrerp_db pg_dump -U ferrerp -Fc --no-owner ferrerp > /tmp/ferrerp_final.dump
   ```
3. **Transferir a Lightsail**: `scp ferrerp_final.dump ubuntu@<LIGHTSAIL_IP>:/home/ubuntu/ferrerp/`
4. **Levantar solo DB en Lightsail**: `docker compose up -d db`
5. **Restaurar**:
   ```bash
   docker cp ferrerp_final.dump ferrerp_db:/tmp/
   docker exec ferrerp_db pg_restore -U ferrerp -d ferrerp --no-owner --clean --if-exists /tmp/ferrerp_final.dump
   ```
6. **Verificar**: contar tablas y spot check datos clave

## Phase 4 — Certificados SSL (10 min)

1. **Cloudflare**: cambiar los 3 registros A a la IP de Lightsail. **Proxy OFF (grey cloud)** temporalmente
2. **Arrancar nginx**: `docker compose up -d nginx`
3. **Emitir certificado**:
   ```bash
   docker compose run --rm certbot certbot certonly \
     --webroot --webroot-path /var/www/certbot \
     --email admin@ferrerp.app --agree-tos --no-eff-email \
     -d ferrerp.app -d www.ferrerp.app -d panel.ferrerp.app
   ```
4. **Activar config produccion**:
   ```bash
   cp nginx/conf.d/ferrerp.conf nginx/conf.d/active.conf
   docker compose restart nginx
   ```

## Phase 5 — Stack Completo (10 min, DOWNTIME TERMINA)

1. `docker compose up -d`
2. Verificar logs: `docker compose logs -f web`
3. Confirmar 4 servicios healthy: `docker compose ps`
4. **Cloudflare**: re-activar proxy (orange cloud) en los 3 registros

## Phase 6 — Verificacion (15 min)

- [ ] `https://ferrerp.app` — landing carga con assets
- [ ] `https://www.ferrerp.app` — landing carga
- [ ] `https://panel.ferrerp.app` — login funciona
- [ ] Login con usuario de produccion
- [ ] Navegar paginas clave (dashboard, productos, facturas)
- [ ] Generar un PDF (test WeasyPrint en server nuevo)
- [ ] `http://ferrerp.app` redirige a HTTPS
- [ ] `free -h` — swap activo, RAM razonable
- [ ] `docker stats --no-stream` — containers sin exceso de memoria

## Phase 7 — Backups Automaticos (10 min)

Crear `/home/ubuntu/ferrerp/backup.sh`:

```bash
#!/bin/bash
# FerrERP - Backup automatico de PostgreSQL
# Retencion: 7 dailies + 4 weeklies
set -euo pipefail

BACKUP_DIR="/home/ubuntu/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DAY_OF_WEEK=$(date +%u)

mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly"

DUMP_FILE="$BACKUP_DIR/daily/ferrerp_${TIMESTAMP}.dump"
docker exec ferrerp_db pg_dump -U ferrerp -Fc ferrerp > "$DUMP_FILE"

if [ ! -s "$DUMP_FILE" ]; then
    echo "ERROR: Backup file is empty!" >&2
    exit 1
fi

echo "Backup created: $DUMP_FILE ($(du -h "$DUMP_FILE" | cut -f1))"

# Copia semanal los domingos
if [ "$DAY_OF_WEEK" -eq 7 ]; then
    cp "$DUMP_FILE" "$BACKUP_DIR/weekly/"
fi

# Retencion: 7 dailies, 4 weeklies
find "$BACKUP_DIR/daily" -name "ferrerp_*.dump" -mtime +7 -delete
find "$BACKUP_DIR/weekly" -name "ferrerp_*.dump" -mtime +30 -delete

echo "Backup complete. Daily: $(ls "$BACKUP_DIR/daily" | wc -l), Weekly: $(ls "$BACKUP_DIR/weekly" | wc -l)"
```

Cron: `0 3 * * * /home/ubuntu/ferrerp/backup.sh >> /home/ubuntu/backups/backup.log 2>&1`

Para restaurar desde backup:
```bash
docker cp /home/ubuntu/backups/daily/ferrerp_YYYYMMDD_HHMMSS.dump ferrerp_db:/tmp/restore.dump
docker exec ferrerp_db pg_restore -U ferrerp -d ferrerp --no-owner --clean --if-exists /tmp/restore.dump
```

## Phase 8 — Post-Migracion (dia siguiente)

1. Monitorear 24-48h: logs, RAM, certbot renewal, backup nocturno
2. Hardening SSH:
   ```bash
   sudo sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
   sudo systemctl restart sshd
   sudo apt-get install -y unattended-upgrades
   sudo dpkg-reconfigure -plow unattended-upgrades
   ```
3. Crear `deploy.sh`:
   ```bash
   #!/bin/bash
   set -euo pipefail
   cd /home/ubuntu/ferrerp
   git pull origin main
   docker compose build web
   docker compose up -d
   docker compose logs -f web --tail=20
   ```
4. **NO cancelar Hostinger** hasta que pase la prueba de 1-2 semanas

## Rollback

- **Antes del DNS cutover**: simplemente `docker-compose up -d` en Hostinger, nada cambio
- **Despues del DNS cutover**: cambiar IPs en Cloudflare de vuelta a Hostinger, arrancar stack alla. Propagacion instantanea con Cloudflare proxy

## Archivos clave (no requieren cambios)

- `docker-compose.yml` — stack de produccion
- `nginx/conf.d/ferrerp-init.conf` — config HTTP-only para setup inicial de SSL
- `nginx/conf.d/ferrerp.conf` — config produccion con los 3 server blocks
- `docker-entrypoint.sh` — corre migraciones automaticamente al arrancar
- `Dockerfile` — deps de WeasyPrint, usuario non-root

## Riesgos y mitigaciones

| Riesgo | Mitigacion |
|--------|-----------|
| WeasyPrint OOM en 2GB | Swap de 2GB configurado en Phase 1 |
| Certbot challenge falla | Cloudflare en DNS-only mode; `ferrerp-init.conf` existe para esto |
| Restore de DB falla | Backup de prueba en Phase 0; flag `--if-exists` |
| Se pierden valores de `.env` | Copiarlos en Phase 0 a password manager |
| Lightsail falla en primeros dias | Hostinger vivo como fallback |
