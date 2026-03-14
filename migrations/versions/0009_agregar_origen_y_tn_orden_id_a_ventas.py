"""Agregar origen y tn_orden_id a ventas.

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-14
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade():
    # Columna origen: distingue ventas POS de órdenes Tienda Nube
    op.add_column(
        'ventas',
        sa.Column(
            'origen',
            sa.String(length=20),
            nullable=False,
            server_default='pos',
        ),
    )
    op.create_index('ix_ventas_origen', 'ventas', ['origen'], unique=False)

    # Columna tn_orden_id: ID de la orden en Tienda Nube (solo para origen='tiendanube')
    op.add_column(
        'ventas',
        sa.Column('tn_orden_id', sa.BigInteger(), nullable=True),
    )
    op.create_index('ix_ventas_tn_orden_id', 'ventas', ['tn_orden_id'], unique=False)

    # Constraint único por empresa + tn_orden_id para evitar importaciones duplicadas
    op.create_unique_constraint(
        'uq_ventas_empresa_tn_orden',
        'ventas',
        ['empresa_id', 'tn_orden_id'],
    )


def downgrade():
    op.drop_constraint('uq_ventas_empresa_tn_orden', 'ventas', type_='unique')
    op.drop_index('ix_ventas_tn_orden_id', table_name='ventas')
    op.drop_column('ventas', 'tn_orden_id')
    op.drop_index('ix_ventas_origen', table_name='ventas')
    op.drop_column('ventas', 'origen')
