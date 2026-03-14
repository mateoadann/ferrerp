"""Agregar tabla de mapeo ProductoTiendaNube.

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-14
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tiendanube_productos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('producto_id', sa.Integer(), nullable=False),
        sa.Column('tn_producto_id', sa.BigInteger(), nullable=False),
        sa.Column('tn_variante_id', sa.BigInteger(), nullable=False),
        sa.Column('sincronizado_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'estado_sync',
            sa.String(length=20),
            nullable=False,
            server_default='pendiente',
        ),
        sa.Column('ultimo_error', sa.Text(), nullable=True),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column(
            'creado_en',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column('actualizado_en', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['empresa_id'],
            ['empresas.id'],
            name='fk_tiendanube_productos_empresa_id',
        ),
        sa.ForeignKeyConstraint(
            ['producto_id'],
            ['productos.id'],
            name='fk_tiendanube_productos_producto_id',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'empresa_id',
            'producto_id',
            name='uq_tiendanube_productos_empresa_producto',
        ),
        sa.UniqueConstraint(
            'empresa_id',
            'tn_producto_id',
            name='uq_tiendanube_productos_empresa_tn_producto',
        ),
    )
    op.create_index(
        'ix_tiendanube_productos_empresa_id',
        'tiendanube_productos',
        ['empresa_id'],
        unique=False,
    )
    op.create_index(
        'ix_tiendanube_productos_producto_id',
        'tiendanube_productos',
        ['producto_id'],
        unique=False,
    )
    op.create_index(
        'ix_tiendanube_productos_empresa_activo',
        'tiendanube_productos',
        ['empresa_id', 'activo'],
        unique=False,
    )


def downgrade():
    op.drop_index(
        'ix_tiendanube_productos_empresa_activo',
        table_name='tiendanube_productos',
    )
    op.drop_index(
        'ix_tiendanube_productos_producto_id',
        table_name='tiendanube_productos',
    )
    op.drop_index(
        'ix_tiendanube_productos_empresa_id',
        table_name='tiendanube_productos',
    )
    op.drop_table('tiendanube_productos')
