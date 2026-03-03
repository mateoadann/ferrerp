#!/bin/bash
set -e

echo "Esperando a que PostgreSQL este listo..."
while ! pg_isready -h db -p 5432 -U ferrerp > /dev/null 2>&1; do
    sleep 1
done
echo "PostgreSQL listo!"

# Aplicar migraciones pendientes
echo "Aplicando migraciones..."
flask db upgrade

# Cargar datos de prueba si la base esta vacia (opcional)
if [ "$LOAD_SEED_DATA" = "true" ]; then
    echo "Cargando datos de prueba..."
    flask seed
fi

echo "Iniciando aplicacion..."
exec "$@"
