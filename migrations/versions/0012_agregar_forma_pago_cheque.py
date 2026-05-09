"""Agregar forma de pago cheque a los enums y crear tabla cheques.

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-14
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar 'cheque' al enum forma_pago (ventas)
    op.execute("ALTER TYPE forma_pago ADD VALUE IF NOT EXISTS 'cheque'")
    # Agregar 'cheque' al enum forma_pago_movimiento (movimientos de caja)
    op.execute("ALTER TYPE forma_pago_movimiento ADD VALUE IF NOT EXISTS 'cheque'")

    # Crear tabla de cheques
    op.create_table(
        'cheques',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('numero_cheque', sa.String(50), nullable=False),
        sa.Column('banco', sa.String(100), nullable=False),
        sa.Column('fecha_emision', sa.Date, nullable=True),
        sa.Column('fecha_vencimiento', sa.Date, nullable=False),
        sa.Column('importe', sa.Numeric(12, 2), nullable=False),
        sa.Column('referencia_tipo', sa.String(30), nullable=False),
        sa.Column('referencia_id', sa.Integer, nullable=False),
        sa.Column(
            'estado',
            sa.String(20),
            nullable=False,
            server_default='recibido',
        ),
        sa.Column('observaciones', sa.Text, nullable=True),
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
        sa.Column(
            'empresa_id',
            sa.Integer,
            sa.ForeignKey('empresas.id'),
            nullable=False,
            index=True,
        ),
    )

    # Índices para consultas frecuentes
    op.create_index(
        'ix_cheques_referencia',
        'cheques',
        ['referencia_tipo', 'referencia_id'],
    )
    op.create_index(
        'ix_cheques_estado',
        'cheques',
        ['estado'],
    )
    op.create_index(
        'ix_cheques_fecha_vencimiento',
        'cheques',
        ['fecha_vencimiento'],
    )


def downgrade():
    # PostgreSQL no permite eliminar valores de un enum existente.
    # Solo se elimina la tabla.
    op.drop_index('ix_cheques_fecha_vencimiento', 'cheques')
    op.drop_index('ix_cheques_estado', 'cheques')
    op.drop_index('ix_cheques_referencia', 'cheques')
    op.drop_table('cheques')
