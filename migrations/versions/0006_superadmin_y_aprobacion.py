"""Agregar superadmin y aprobacion de empresas.

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-06
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar valor al enum rol_usuario (PostgreSQL)
    op.execute("ALTER TYPE rol_usuario ADD VALUE IF NOT EXISTS 'superadmin'")

    # Agregar columna debe_cambiar_password a usuarios
    op.add_column(
        'usuarios',
        sa.Column(
            'debe_cambiar_password',
            sa.Boolean(),
            nullable=False,
            server_default='false',
        ),
    )

    # Agregar columna aprobada a empresas
    op.add_column(
        'empresas',
        sa.Column(
            'aprobada',
            sa.Boolean(),
            nullable=False,
            server_default='false',
        ),
    )

    # Empresas existentes quedan aprobadas
    op.execute('UPDATE empresas SET aprobada = true')


def downgrade():
    op.drop_column('empresas', 'aprobada')
    op.drop_column('usuarios', 'debe_cambiar_password')
    # Nota: No se puede eliminar un valor de enum en PostgreSQL facilmente
