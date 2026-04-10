"""Agregar soporte para pagos divididos.

Crea tabla venta_pagos y agrega valor 'dividido' al enum forma_pago.
Backfill de ventas existentes a venta_pagos.

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-06
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Agregar 'dividido' al enum forma_pago (fuera de transaccion)
    op.execute('COMMIT')
    op.execute("ALTER TYPE forma_pago ADD VALUE IF NOT EXISTS 'dividido'")

    # 2. Crear tabla venta_pagos
    op.create_table(
        'venta_pagos',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column(
            'venta_id',
            sa.Integer,
            sa.ForeignKey('ventas.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'forma_pago',
            postgresql.ENUM(
                'efectivo', 'tarjeta_debito', 'tarjeta_credito',
                'transferencia', 'qr', 'cuenta_corriente', 'dividido',
                name='forma_pago',
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column('monto', sa.Numeric(12, 2), nullable=False),
    )

    # 3. Backfill: crear VentaPago para cada venta completada existente
    op.execute("""
        INSERT INTO venta_pagos (venta_id, forma_pago, monto)
        SELECT id, forma_pago, total
        FROM ventas
        WHERE estado = 'completada'
    """)


def downgrade():
    op.drop_table('venta_pagos')
    # No se puede quitar un valor de un enum en PostgreSQL
