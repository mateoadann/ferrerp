"""Crear tabla importaciones_producto para auditoría de importaciones masivas.

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
        'importaciones_producto',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column(
            'empresa_id',
            sa.Integer,
            sa.ForeignKey('empresas.id'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'usuario_id',
            sa.Integer,
            sa.ForeignKey('usuarios.id'),
            nullable=False,
        ),
        sa.Column('nombre_archivo', sa.String(255), nullable=False),
        sa.Column('total_filas', sa.Integer, nullable=False, server_default='0'),
        sa.Column('filas_importadas', sa.Integer, nullable=False, server_default='0'),
        sa.Column('filas_actualizadas', sa.Integer, nullable=False, server_default='0'),
        sa.Column('filas_omitidas', sa.Integer, nullable=False, server_default='0'),
        sa.Column('errores_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('categorias_creadas', sa.Integer, nullable=False, server_default='0'),
        sa.Column(
            'modo_duplicados',
            sa.String(20),
            nullable=False,
            server_default='saltar',
        ),
        sa.Column(
            'created_at',
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        'ix_importaciones_producto_created_at',
        'importaciones_producto',
        ['created_at'],
    )


def downgrade():
    op.drop_index('ix_importaciones_producto_created_at', 'importaciones_producto')
    op.drop_table('importaciones_producto')
