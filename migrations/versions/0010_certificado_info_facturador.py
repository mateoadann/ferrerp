"""Agregar campos de información de certificado a facturadores.

Agrega certificado_emisor y certificado_sujeto, y cambia
certificado_vencimiento de Date a DateTime para almacenar
hora de expiración exacta del certificado X.509.

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-14
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade():
    """Agrega columnas de info de certificado a la tabla facturadores."""
    conn = op.get_bind()
    dialect = conn.dialect.name

    # certificado_emisor y certificado_sujeto: columnas nuevas
    op.add_column(
        'facturadores',
        sa.Column('certificado_emisor', sa.String(255), nullable=True),
    )
    op.add_column(
        'facturadores',
        sa.Column('certificado_sujeto', sa.String(255), nullable=True),
    )

    # certificado_vencimiento: cambiar de Date a DateTime
    # SQLite no soporta ALTER COLUMN, pero Date y DateTime son compatibles
    # en SQLite (ambos se almacenan como texto). Para PostgreSQL usamos
    # ALTER COLUMN con USING.
    if dialect == 'postgresql':
        op.execute(
            'ALTER TABLE facturadores '
            'ALTER COLUMN certificado_vencimiento '
            'TYPE TIMESTAMP USING certificado_vencimiento::timestamp'
        )


def downgrade():
    """Revierte los cambios: elimina columnas y restaura tipo Date."""
    conn = op.get_bind()
    dialect = conn.dialect.name

    op.drop_column('facturadores', 'certificado_sujeto')
    op.drop_column('facturadores', 'certificado_emisor')

    if dialect == 'postgresql':
        op.execute(
            'ALTER TABLE facturadores '
            'ALTER COLUMN certificado_vencimiento '
            'TYPE DATE USING certificado_vencimiento::date'
        )
