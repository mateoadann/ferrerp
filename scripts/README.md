# scripts/

Scripts de operaciones para FerrERP en producción (Lightsail).

## Setup inicial en el VPS

```bash
sudo mkdir -p /opt/backups/ferrerp /var/log/ferrerp
sudo chown -R ubuntu:ubuntu /opt/backups/ferrerp /var/log/ferrerp
chmod +x /opt/apps/ferrerp/scripts/*.sh
```

Variables requeridas en `/opt/apps/ferrerp/.env`:

```
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET=ferrerp-backups-prod
```

## Scripts

| Script | Qué hace |
|--------|----------|
| `backup.sh` | Backup completo (DB + uploads + config) → disco + S3, con rotación local de 7 |
| `restore.sh` | Restaurar desde backup local o S3, interactivo. Backup defensivo previo. |
| `deploy.sh` | `git pull` + build + up con backup pre-deploy y rollback automático si falla healthcheck |
| `rollback.sh` | Volver al commit anterior + restore del backup pre-deploy |
| `lib/common.sh` | Funciones compartidas (logging, validación, etc.) |

## Uso

```bash
cd /opt/apps/ferrerp

./scripts/backup.sh                    # backup completo + S3
./scripts/backup.sh --no-s3            # solo a disco
./scripts/backup.sh --tag manual       # tag custom

./scripts/restore.sh                   # interactivo, backups locales
./scripts/restore.sh --from-s3         # interactivo, backups en S3
./scripts/restore.sh --file path/x.tar.gz

./scripts/deploy.sh                    # deploy de la rama actual
./scripts/deploy.sh --branch main      # checkout y deploy de main

./scripts/rollback.sh                  # rollback completo (código + DB)
./scripts/rollback.sh --commit         # solo código, DB queda
```

## Cron de backup diario

Configurado en `/etc/cron.d/ferrerp-backup`. Corre todos los días a las 5:00 UTC (2:00 ART).

## Logs

- Backups y deploys: `/var/log/ferrerp/`
- Cron: `journalctl -u cron -f`
