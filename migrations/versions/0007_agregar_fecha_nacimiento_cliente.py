"""Agregar fecha de nacimiento a clientes.

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-25
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'clientes',
        sa.Column('fecha_nacimiento', sa.Date(), nullable=True),
    )


def downgrade():
    op.drop_column('clientes', 'fecha_nacimiento')
