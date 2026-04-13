"""Agregar descuento porcentual por linea de detalle en ventas y presupuestos.

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-06
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'venta_detalles',
        sa.Column(
            'descuento_porcentaje',
            sa.Numeric(5, 2),
            nullable=False,
            server_default='0',
        ),
    )
    op.add_column(
        'presupuesto_detalles',
        sa.Column(
            'descuento_porcentaje',
            sa.Numeric(5, 2),
            nullable=False,
            server_default='0',
        ),
    )


def downgrade():
    op.drop_column('presupuesto_detalles', 'descuento_porcentaje')
    op.drop_column('venta_detalles', 'descuento_porcentaje')
