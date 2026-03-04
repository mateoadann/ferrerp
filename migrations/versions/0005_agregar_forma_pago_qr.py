"""Agregar forma de pago QR a los enums.

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-04
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar 'qr' al enum forma_pago (ventas)
    op.execute("ALTER TYPE forma_pago ADD VALUE IF NOT EXISTS 'qr'")
    # Agregar 'qr' al enum forma_pago_movimiento (movimientos de caja)
    op.execute("ALTER TYPE forma_pago_movimiento ADD VALUE IF NOT EXISTS 'qr'")


def downgrade():
    # PostgreSQL no permite eliminar valores de un enum existente.
    # Para revertir se necesitaría recrear el tipo, lo cual es destructivo.
    pass
