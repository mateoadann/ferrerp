"""Tabla facturadores y FK en facturas.

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-14
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'facturadores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=150), nullable=False),
        sa.Column('razon_social', sa.String(length=200), nullable=False),
        sa.Column('cuit', sa.String(length=13), nullable=False),
        sa.Column('condicion_iva_id', sa.Integer(), nullable=False),
        sa.Column('condicion_iva', sa.String(length=100), nullable=True),
        sa.Column('domicilio_fiscal', sa.String(length=300), nullable=True),
        sa.Column('numero_iibb', sa.String(length=50), nullable=True),
        sa.Column('email_fiscal', sa.String(length=120), nullable=True),
        sa.Column('inicio_actividades', sa.Date(), nullable=True),
        sa.Column('punto_venta', sa.Integer(), nullable=False),
        sa.Column('certificado', sa.LargeBinary(), nullable=True),
        sa.Column('clave_privada', sa.LargeBinary(), nullable=True),
        sa.Column('certificado_vencimiento', sa.Date(), nullable=True),
        sa.Column(
            'ambiente',
            sa.String(length=20),
            nullable=True,
            server_default='testing',
        ),
        sa.Column(
            'habilitado',
            sa.Boolean(),
            nullable=True,
            server_default='false',
        ),
        sa.Column(
            'activo',
            sa.Boolean(),
            nullable=True,
            server_default='true',
        ),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['empresa_id'],
            ['empresas.id'],
            name='fk_facturadores_empresa_id',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'empresa_id',
            'cuit',
            'punto_venta',
            name='uq_facturador_empresa_cuit_pv',
        ),
    )
    with op.batch_alter_table('facturadores', schema=None) as batch_op:
        batch_op.create_index('ix_facturadores_empresa_id', ['empresa_id'])

    with op.batch_alter_table('facturas', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('facturador_id', sa.Integer(), nullable=True),
        )
        batch_op.create_foreign_key(
            'fk_facturas_facturador_id',
            'facturadores',
            ['facturador_id'],
            ['id'],
        )
        batch_op.create_index('ix_facturas_facturador_id', ['facturador_id'])


def downgrade():
    with op.batch_alter_table('facturas', schema=None) as batch_op:
        batch_op.drop_index('ix_facturas_facturador_id')
        batch_op.drop_constraint('fk_facturas_facturador_id', type_='foreignkey')
        batch_op.drop_column('facturador_id')

    op.drop_table('facturadores')
