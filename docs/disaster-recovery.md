# Disaster Recovery — FerrERP

Plan de recuperación ante distintos escenarios de falla. Mantener actualizado.

## Recursos críticos

| Recurso | Valor / Ubicación |
|---------|-------------------|
| VPS producción | Lightsail Ubuntu 24.04 LTS, IP `3.226.35.24` (`us-east-1a`) |
| SSH alias | `aws-ferrerp-vps` |
| Bucket de backups | `s3://ferrerp-backups-prod` (us-east-1) |
| IAM user del VPS | `ferrerp-lightsail-backup` (mínimo privilegio) |
| DNS | Cloudflare → A record `panel.ferrerp.app` y `ferrerp.app` |
| Repo | `git@github.com:mateoadann/ferrerp.git` (Deploy Key SSH en VPS) |
| `.env` (secretos) | **Solo en el VPS** y en password manager personal |

## Backups

- **Cron diario**: `/etc/cron.d/ferrerp-backup` corre `scripts/backup.sh` a las 5am UTC (2am ART)
- **Retención**: rolling window de 7 backups, igual en local y en S3 (configurable via `KEEP_BACKUPS`)
- **Local**: en `/opt/backups/ferrerp/` con rotación al ejecutar `backup.sh`
- **S3**: rotación activa por el script (cuando entra el #8, se borra el #1)
- **Encriptación**: SSE-S3 (AES-256) automática del bucket
- **Versioning**: bucket con versioning ON. Las versiones no-current se eliminan a los 30 días

## Verificar backups antes de necesitarlos

**Backups no probados son backups que no existen.** Mensualmente, ejecutar `scripts/restore.sh --from-s3` apuntando a un Postgres temporal y verificar que los conteos coinciden.

---

## Escenario 1 — App rota, VPS vivo (caso más común)

Síntomas: deploy malo, migración Alembic rota, datos borrados por error, app responde 500.

### Opción A: rollback al estado pre-deploy (más rápido)

```bash
ssh aws-ferrerp-vps
cd /opt/apps/ferrerp
./scripts/rollback.sh
```

Esto revierte código al penúltimo commit y opcionalmente restaura la DB del backup pre-deploy. Tiempo: 2-3 min.

### Opción B: restore desde un backup específico

```bash
ssh aws-ferrerp-vps
cd /opt/apps/ferrerp

./scripts/restore.sh                # interactivo, lista backups locales
./scripts/restore.sh --from-s3      # interactivo, lista backups en S3
./scripts/restore.sh --file path    # archivo específico ya descargado
```

El script hace un backup defensivo del estado roto antes de restaurar. Tiempo: 5-10 min.

---

## Escenario 2 — VPS muerto, hay que crear uno nuevo

Síntomas: AWS suspendió la instancia, disco corrupto, la VM no responde.

### Pasos

1. **Crear nueva instancia Lightsail** (Ubuntu 24.04, mismo plan, `us-east-1a`).
2. **Asignar la IP estática** vieja a la nueva instancia (Cloudflare no se entera del cambio).
3. **Instalar Docker en el host nuevo**:

   ```bash
   ssh ubuntu@<IP>
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker ubuntu
   exit && ssh ubuntu@<IP>   # reconectar para que tome el grupo
   ```

4. **Instalar AWS CLI v2**:

   ```bash
   sudo apt-get install -y unzip
   cd /tmp
   curl -sSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
   unzip -q awscliv2.zip
   sudo ./aws/install
   ```

5. **Hardening básico** (ver `scripts/setup-host.sh` si existe, o aplicar manualmente UFW + fail2ban + sysctl).

6. **Generar Deploy Key SSH y agregarla al repo** (`Settings → Deploy keys` en GitHub):

   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -N "" -C "ferrerp-lightsail-deploy@$(hostname)"
   cat ~/.ssh/github_deploy.pub   # pegar como Deploy Key (read-only)

   cat > ~/.ssh/config <<EOF
   Host github.com
       HostName github.com
       User git
       IdentityFile ~/.ssh/github_deploy
       IdentitiesOnly yes
       StrictHostKeyChecking accept-new
   EOF
   chmod 600 ~/.ssh/config
   ```

7. **Clonar el repo**:

   ```bash
   sudo mkdir -p /opt/apps && sudo chown ubuntu:ubuntu /opt/apps
   git clone git@github.com:mateoadann/ferrerp.git /opt/apps/ferrerp
   cd /opt/apps/ferrerp
   ```

8. **Recrear `.env`** desde el password manager personal:

   ```bash
   cat > .env <<'EOF'
   FLASK_APP=run.py
   FLASK_ENV=production
   FLASK_DEBUG=0
   SECRET_KEY=<desde-password-manager>
   DATABASE_URL=postgresql://ferrerp:<DB_PASSWORD>@db:5432/ferrerp
   DB_PASSWORD=<desde-password-manager>
   APP_NAME=FerrERP
   ITEMS_PER_PAGE=20
   AWS_ACCESS_KEY_ID=<desde-password-manager>
   AWS_SECRET_ACCESS_KEY=<desde-password-manager>
   AWS_DEFAULT_REGION=us-east-1
   S3_BUCKET=ferrerp-backups-prod
   EOF
   chmod 600 .env
   ```

9. **Crear directorios de operaciones**:

   ```bash
   sudo mkdir -p /opt/backups/ferrerp /var/log/ferrerp
   sudo chown -R ubuntu:ubuntu /opt/backups/ferrerp /var/log/ferrerp
   ```

10. **Levantar SOLO la DB** (sin app aún, para restore previo):

    ```bash
    docker compose up -d db
    sleep 10
    docker compose ps   # verificar healthy
    ```

11. **Restaurar backup más reciente desde S3**:

    ```bash
    ./scripts/restore.sh --from-s3
    # Elegir el backup más reciente del listado
    ```

12. **Levantar el resto del stack**:

    ```bash
    docker compose up -d
    ```

13. **Verificar SSL y healthcheck**:

    ```bash
    curl -I -H "Host: panel.ferrerp.app" https://localhost/auth/login -k
    # debería responder 200 o 302
    ```

14. **Si el cert SSL del backup ya venció**, regenerarlo desde el VPS:

    ```bash
    docker compose exec certbot certbot renew --force-renewal
    docker compose exec nginx nginx -s reload
    ```

15. **Reinstalar cron de backup**:

    ```bash
    sudo tee /etc/cron.d/ferrerp-backup > /dev/null <<EOF
    SHELL=/bin/bash
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
    0 5 * * * ubuntu /opt/apps/ferrerp/scripts/backup.sh >> /var/log/ferrerp/cron.log 2>&1
    EOF
    sudo systemctl reload cron
    ```

**Tiempo total estimado**: 30-45 min (la mayor parte es esperar provisioning de Lightsail).

---

## Escenario 3 — Recuperar un dato específico de un backup viejo

Síntomas: "el cliente borró todas sus ventas del lunes pasado, recuperalas".

```bash
ssh aws-ferrerp-vps

# 1. Listar backups en S3 con fechas
aws s3 ls s3://ferrerp-backups-prod/backups/ --human-readable

# 2. Bajar el backup específico
aws s3 cp s3://ferrerp-backups-prod/backups/ferrerp-AAAAMMDD-HHMMSS.tar.gz /tmp/

# 3. Extraer
mkdir -p /tmp/cherry-pick && cd /tmp/cherry-pick
tar xzf /tmp/ferrerp-AAAAMMDD-HHMMSS.tar.gz

# 4. Postgres temporal aislado en puerto 15432 (no choca con prod)
docker run -d --name pg_temp \
    -e POSTGRES_USER=ferrerp -e POSTGRES_PASSWORD=tmp -e POSTGRES_DB=ferrerp_temp \
    -p 15432:5432 postgres:15-alpine
sleep 5

# 5. Restaurar el dump al Postgres temporal
DUMP_DIR=$(ls -d ferrerp-*)
docker cp "${DUMP_DIR}/db.dump" pg_temp:/tmp/dump
docker exec pg_temp pg_restore -U ferrerp -d ferrerp_temp --no-owner --no-acl /tmp/dump

# 6. Sacar lo que necesitás (ejemplo: ventas de una fecha)
docker exec pg_temp psql -U ferrerp -d ferrerp_temp \
    -c "COPY (SELECT * FROM ventas WHERE fecha::date = '2026-04-27') TO STDOUT WITH CSV HEADER" \
    > /tmp/ventas-recuperadas.csv

# 7. Insertar en la DB real (cuidado con conflictos de PK!)
#    Revisar el CSV antes de insertar. Posiblemente necesites editar IDs.
docker exec -i ferrerp_db psql -U ferrerp -d ferrerp \
    -c "\COPY ventas FROM STDIN WITH CSV HEADER" < /tmp/ventas-recuperadas.csv

# 8. Limpieza
docker rm -f pg_temp
rm -rf /tmp/cherry-pick /tmp/ferrerp-*.tar.gz /tmp/ventas-recuperadas.csv
```

**Tiempo estimado**: 10-20 min según la complejidad de la query.

---

## Escenario 4 — Bucket S3 comprometido

Síntomas: leak de keys AWS, acceso no autorizado al bucket.

### Acción inmediata

1. **Deshabilitar las keys del IAM user** desde la consola AWS (IAM → Users → Security credentials → Deactivate).
2. **Verificar `s3:ListBucket` activity** en CloudTrail por accesos sospechosos.
3. **Crear nuevas keys** y actualizar `.env` del VPS.
4. **Revisar versioning del bucket**: si el atacante borró backups, recuperar desde versions:

   ```bash
   aws s3api list-object-versions --bucket ferrerp-backups-prod --prefix backups/
   aws s3api get-object --bucket ferrerp-backups-prod \
       --key backups/ferrerp-XXX.tar.gz \
       --version-id <ID> recovered.tar.gz
   ```

5. **Si los backups en S3 están corruptos o eliminados sin posibilidad de recovery**: usar el último backup local en `/opt/backups/ferrerp/` del VPS.

---

## Mantenimiento mensual

- [ ] Verificar que `scripts/backup.sh` corrió todos los días (revisar `/var/log/ferrerp/cron.log`)
- [ ] Verificar que los backups llegan a S3 (`aws s3 ls s3://ferrerp-backups-prod/backups/`)
- [ ] **Hacer un restore de prueba en sandbox** (Postgres temporal local, comparar conteos)
- [ ] Verificar que las keys AWS no están cerca del rotation (rotar cada 90 días)
- [ ] Verificar que el cert SSL no está cerca de vencer (`docker exec ferrerp_nginx openssl x509 -in /etc/letsencrypt/live/ferrerp.app/fullchain.pem -noout -dates`)
