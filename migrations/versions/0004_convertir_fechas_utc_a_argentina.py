"""Convertir fechas UTC a hora Argentina (UTC-3).

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-04
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

# Tablas y columnas DateTime a convertir
TABLAS_COLUMNAS = [
    ('usuarios', ['created_at', 'updated_at']),
    ('empresas', ['created_at', 'updated_at']),
    ('productos', ['created_at', 'updated_at']),
    ('proveedores', ['created_at']),
    ('categorias', ['created_at']),
    ('clientes', ['created_at']),
    ('presupuestos', ['fecha', 'fecha_vencimiento', 'created_at', 'updated_at']),
    ('ventas', ['fecha', 'created_at']),
    ('cajas', ['fecha_apertura', 'fecha_cierre']),
    ('movimientos_caja', ['created_at']),
    ('ordenes_compra', ['fecha', 'created_at']),
    ('devoluciones', ['fecha', 'created_at']),
    ('movimientos_stock', ['created_at']),
    ('movimientos_cuenta_corriente', ['created_at']),
]


def upgrade():
    """Convierte fechas de UTC a Argentina (restar 3 horas)."""
    bind = op.get_bind()
    es_postgres = bind.dialect.name == 'postgresql'

    for tabla, columnas in TABLAS_COLUMNAS:
        for columna in columnas:
            if es_postgres:
                op.execute(
                    f"UPDATE {tabla} SET {columna} = {columna} - INTERVAL '3 hours' "
                    f'WHERE {columna} IS NOT NULL'
                )
            else:
                # SQLite
                op.execute(
                    f"UPDATE {tabla} SET {columna} = datetime({columna}, '-3 hours') "
                    f'WHERE {columna} IS NOT NULL'
                )


def downgrade():
    """Revierte: convierte fechas de Argentina a UTC (sumar 3 horas)."""
    bind = op.get_bind()
    es_postgres = bind.dialect.name == 'postgresql'

    for tabla, columnas in TABLAS_COLUMNAS:
        for columna in columnas:
            if es_postgres:
                op.execute(
                    f"UPDATE {tabla} SET {columna} = {columna} + INTERVAL '3 hours' "
                    f'WHERE {columna} IS NOT NULL'
                )
            else:
                # SQLite
                op.execute(
                    f"UPDATE {tabla} SET {columna} = datetime({columna}, '+3 hours') "
                    f'WHERE {columna} IS NOT NULL'
                )
