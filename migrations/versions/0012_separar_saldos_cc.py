"""Separar saldo_cuenta_corriente en deuda y saldo a favor.

Agrega columna saldo_a_favor_monto para almacenar el credito del cliente
de forma independiente a la deuda.

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
    # Agregar nueva columna para saldo a favor
    op.add_column(
        'clientes',
        sa.Column(
            'saldo_a_favor_monto',
            sa.Numeric(12, 2),
            server_default='0',
            nullable=False,
        ),
    )

    # Migrar datos: saldo negativo = saldo a favor
    op.execute(
        'UPDATE clientes SET saldo_a_favor_monto = ABS(saldo_cuenta_corriente) '
        'WHERE saldo_cuenta_corriente < 0'
    )
    op.execute('UPDATE clientes SET saldo_cuenta_corriente = 0 ' 'WHERE saldo_cuenta_corriente < 0')


def downgrade():
    # Revertir: fusionar saldo a favor de vuelta en saldo_cuenta_corriente
    op.execute(
        'UPDATE clientes SET saldo_cuenta_corriente = '
        'saldo_cuenta_corriente - saldo_a_favor_monto '
        'WHERE saldo_a_favor_monto > 0'
    )
    op.drop_column('clientes', 'saldo_a_favor_monto')
