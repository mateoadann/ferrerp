"""Crear tabla actualizaciones_precio para historial de precios.

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-06
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'actualizaciones_precio',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column(
            'producto_id',
            sa.Integer,
            sa.ForeignKey('productos.id'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'usuario_id',
            sa.Integer,
            sa.ForeignKey('usuarios.id'),
            nullable=False,
        ),
        sa.Column(
            'fecha', sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
        sa.Column('tipo', sa.String(10), nullable=False, server_default='masiva'),
        sa.Column('porcentaje', sa.Numeric(8, 4), nullable=True),
        sa.Column('precio_costo_anterior', sa.Numeric(12, 2), nullable=False),
        sa.Column('precio_costo_nuevo', sa.Numeric(12, 2), nullable=False),
        sa.Column('precio_venta_anterior', sa.Numeric(12, 2), nullable=False),
        sa.Column('precio_venta_nuevo', sa.Numeric(12, 2), nullable=False),
        sa.Column(
            'actualizo_costo',
            sa.Boolean,
            nullable=False,
            server_default=sa.text('true'),
        ),
        sa.Column(
            'categoria_id',
            sa.Integer,
            sa.ForeignKey('categorias.id'),
            nullable=True,
        ),
        sa.Column('notas', sa.Text, nullable=True),
        sa.Column(
            'empresa_id',
            sa.Integer,
            sa.ForeignKey('empresas.id'),
            nullable=False,
            index=True,
        ),
    )

    op.create_index(
        'ix_actualizaciones_precio_fecha',
        'actualizaciones_precio',
        ['fecha'],
    )


def downgrade():
    op.drop_index('ix_actualizaciones_precio_fecha', 'actualizaciones_precio')
    op.drop_table('actualizaciones_precio')
