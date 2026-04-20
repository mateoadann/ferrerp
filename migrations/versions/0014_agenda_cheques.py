"""Agenda de cheques: agregar tipo, destinatario, evolucionar estado.

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-18
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar columna tipo con default 'recibido' (backfill automático)
    with op.batch_alter_table('cheques') as batch_op:
        batch_op.add_column(
            sa.Column(
                'tipo',
                sa.String(20),
                nullable=False,
                server_default='recibido',
            )
        )
        batch_op.add_column(sa.Column('destinatario', sa.String(200), nullable=True))
        # Hacer referencia_tipo y referencia_id nullable
        batch_op.alter_column(
            'referencia_tipo',
            existing_type=sa.String(30),
            nullable=True,
        )
        batch_op.alter_column(
            'referencia_id',
            existing_type=sa.Integer,
            nullable=True,
        )

    # Convertir estado 'recibido' a 'pendiente'
    op.execute("UPDATE cheques SET estado = 'pendiente' WHERE estado = 'recibido'")

    # Índice en tipo para filtrado de agenda
    op.create_index('ix_cheques_tipo', 'cheques', ['tipo'])


def downgrade():
    op.drop_index('ix_cheques_tipo', 'cheques')

    # Revertir estado 'pendiente' a 'recibido'
    op.execute("UPDATE cheques SET estado = 'recibido' WHERE estado = 'pendiente'")

    with op.batch_alter_table('cheques') as batch_op:
        batch_op.alter_column(
            'referencia_id',
            existing_type=sa.Integer,
            nullable=False,
        )
        batch_op.alter_column(
            'referencia_tipo',
            existing_type=sa.String(30),
            nullable=False,
        )
        batch_op.drop_column('destinatario')
        batch_op.drop_column('tipo')
