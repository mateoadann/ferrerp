"""Agregar concepto adelanto_cliente a movimientos de caja.

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-13
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar 'adelanto_cliente' al enum concepto_movimiento_caja
    op.execute("ALTER TYPE concepto_movimiento_caja ADD VALUE IF NOT EXISTS 'adelanto_cliente'")


def downgrade():
    # PostgreSQL no permite eliminar valores de un enum existente.
    # Para revertir se necesitaria recrear el tipo, lo cual es destructivo.
    pass
