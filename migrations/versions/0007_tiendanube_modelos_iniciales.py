"""Agregar modelos iniciales de Tienda Nube.

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-12
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tiendanube_credenciales',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tn_app_id', sa.String(length=100), nullable=False),
        sa.Column('tn_app_secret', sa.String(length=255), nullable=False),
        sa.Column('tienda_id_externo', sa.String(length=50), nullable=True),
        sa.Column('usuario_id_externo', sa.String(length=50), nullable=True),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('token_type', sa.String(length=30), nullable=False, server_default='bearer'),
        sa.Column('scope', sa.String(length=255), nullable=True),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['empresa_id'], ['empresas.id'], name='fk_tiendanube_credenciales_empresa_id'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('empresa_id', name='uq_tiendanube_credenciales_empresa'),
        sa.UniqueConstraint(
            'tienda_id_externo', name='uq_tiendanube_credenciales_tienda_id_externo'
        ),
    )
    op.create_index(
        'ix_tiendanube_credenciales_empresa_id',
        'tiendanube_credenciales',
        ['empresa_id'],
        unique=False,
    )
    op.create_index(
        'ix_tiendanube_credenciales_tienda_id_externo',
        'tiendanube_credenciales',
        ['tienda_id_externo'],
        unique=False,
    )

    op.create_table(
        'tiendanube_sync_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recurso', sa.String(length=50), nullable=False),
        sa.Column(
            'direccion',
            sa.Enum('importacion', 'exportacion', name='direccion_sync'),
            nullable=False,
        ),
        sa.Column(
            'estado',
            sa.Enum('pendiente', 'exitoso', 'error', name='estado_sync'),
            nullable=False,
            server_default='pendiente',
        ),
        sa.Column('referencia_id_externo', sa.String(length=100), nullable=True),
        sa.Column('mensaje', sa.Text(), nullable=True),
        sa.Column('payload', sa.Text(), nullable=True),
        sa.Column('respuesta', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['empresa_id'], ['empresas.id'], name='fk_tiendanube_sync_logs_empresa_id'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_tiendanube_sync_logs_created_at',
        'tiendanube_sync_logs',
        ['created_at'],
        unique=False,
    )
    op.create_index(
        'ix_tiendanube_sync_logs_empresa_id',
        'tiendanube_sync_logs',
        ['empresa_id'],
        unique=False,
    )
    op.create_index(
        'ix_tiendanube_sync_logs_estado',
        'tiendanube_sync_logs',
        ['estado'],
        unique=False,
    )
    op.create_index(
        'ix_tiendanube_sync_logs_recurso',
        'tiendanube_sync_logs',
        ['recurso'],
        unique=False,
    )
    op.create_index(
        'ix_tiendanube_sync_logs_referencia_id_externo',
        'tiendanube_sync_logs',
        ['referencia_id_externo'],
        unique=False,
    )


def downgrade():
    op.drop_index(
        'ix_tiendanube_sync_logs_referencia_id_externo', table_name='tiendanube_sync_logs'
    )
    op.drop_index('ix_tiendanube_sync_logs_recurso', table_name='tiendanube_sync_logs')
    op.drop_index('ix_tiendanube_sync_logs_estado', table_name='tiendanube_sync_logs')
    op.drop_index('ix_tiendanube_sync_logs_empresa_id', table_name='tiendanube_sync_logs')
    op.drop_index('ix_tiendanube_sync_logs_created_at', table_name='tiendanube_sync_logs')
    op.drop_table('tiendanube_sync_logs')

    op.drop_index(
        'ix_tiendanube_credenciales_tienda_id_externo',
        table_name='tiendanube_credenciales',
    )
    op.drop_index('ix_tiendanube_credenciales_empresa_id', table_name='tiendanube_credenciales')
    op.drop_table('tiendanube_credenciales')

    sa.Enum(name='estado_sync').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='direccion_sync').drop(op.get_bind(), checkfirst=True)
