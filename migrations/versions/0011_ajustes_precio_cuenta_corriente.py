"""Crear tabla ajustes_precio_cuenta_corriente para auditoría de ajustes CC.

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-14
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ajustes_precio_cuenta_corriente',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column(
            'empresa_id',
            sa.Integer,
            sa.ForeignKey('empresas.id'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'cliente_id',
            sa.Integer,
            sa.ForeignKey('clientes.id'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'venta_id',
            sa.Integer,
            sa.ForeignKey('ventas.id'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'movimiento_cc_id',
            sa.Integer,
            sa.ForeignKey('movimientos_cuenta_corriente.id'),
            nullable=True,
        ),
        sa.Column('actualizacion_fecha', sa.DateTime, nullable=False),
        sa.Column('porcentaje_aplicado', sa.Numeric(8, 4), nullable=False),
        sa.Column('total_original', sa.Numeric(12, 2), nullable=False),
        sa.Column('total_recalculado', sa.Numeric(12, 2), nullable=False),
        sa.Column('monto_ajuste', sa.Numeric(12, 2), nullable=False),
        sa.Column(
            'usuario_id',
            sa.Integer,
            sa.ForeignKey('usuarios.id'),
            nullable=False,
        ),
        sa.Column(
            'created_at',
            sa.DateTime,
            nullable=True,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            'venta_id', 'actualizacion_fecha', 'empresa_id',
            name='uq_ajuste_cc_venta_fecha_empresa',
        ),
    )

    op.create_index(
        'ix_ajustes_precio_cc_actualizacion_fecha',
        'ajustes_precio_cuenta_corriente',
        ['actualizacion_fecha'],
    )


def downgrade():
    op.drop_index(
        'ix_ajustes_precio_cc_actualizacion_fecha',
        'ajustes_precio_cuenta_corriente',
    )
    op.drop_table('ajustes_precio_cuenta_corriente')
