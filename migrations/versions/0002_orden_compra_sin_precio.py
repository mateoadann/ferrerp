"""Orden de compra sin precio — precio_unitario y subtotal nullable.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('orden_compra_detalles') as batch_op:
        batch_op.alter_column(
            'precio_unitario',
            existing_type=sa.Numeric(12, 2),
            nullable=True,
            server_default='0',
        )
        batch_op.alter_column(
            'subtotal',
            existing_type=sa.Numeric(12, 2),
            nullable=True,
            server_default='0',
        )


def downgrade():
    with op.batch_alter_table('orden_compra_detalles') as batch_op:
        batch_op.alter_column(
            'precio_unitario',
            existing_type=sa.Numeric(12, 2),
            nullable=False,
            server_default=None,
        )
        batch_op.alter_column(
            'subtotal',
            existing_type=sa.Numeric(12, 2),
            nullable=False,
            server_default=None,
        )
