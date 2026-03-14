"""Facturacion electronica ARCA fase 1.

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
    with op.batch_alter_table('empresas', schema=None) as batch_op:
        batch_op.add_column(sa.Column('condicion_iva_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('condicion_iva', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('inicio_actividades', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('punto_venta_arca', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('certificado_arca', sa.LargeBinary(), nullable=True))
        batch_op.add_column(sa.Column('clave_privada_arca', sa.LargeBinary(), nullable=True))
        batch_op.add_column(
            sa.Column(
                'ambiente_arca',
                sa.String(length=20),
                nullable=True,
                server_default='testing',
            )
        )
        batch_op.add_column(
            sa.Column(
                'arca_habilitado',
                sa.Boolean(),
                nullable=True,
                server_default='false',
            )
        )

    with op.batch_alter_table('clientes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('razon_social', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('condicion_iva_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('condicion_iva', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('doc_tipo', sa.Integer(), nullable=True))

    op.execute('UPDATE clientes SET condicion_iva_id = 5 WHERE condicion_iva_id IS NULL')
    op.execute('UPDATE clientes SET doc_tipo = 99 WHERE doc_tipo IS NULL')

    op.create_table(
        'facturas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('venta_id', sa.Integer(), nullable=True),
        sa.Column('tipo_comprobante', sa.Integer(), nullable=False),
        sa.Column('punto_venta', sa.Integer(), nullable=False),
        sa.Column('numero_comprobante', sa.Integer(), nullable=False),
        sa.Column('concepto', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('fecha_emision', sa.Date(), nullable=False),
        sa.Column('doc_tipo_receptor', sa.Integer(), nullable=True),
        sa.Column('doc_nro_receptor', sa.String(length=20), nullable=True),
        sa.Column('condicion_iva_receptor_id', sa.Integer(), nullable=False),
        sa.Column('imp_total', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('imp_neto', sa.Numeric(precision=14, scale=2), nullable=True, server_default='0'),
        sa.Column('imp_iva', sa.Numeric(precision=14, scale=2), nullable=True, server_default='0'),
        sa.Column(
            'imp_tot_conc',
            sa.Numeric(precision=14, scale=2),
            nullable=True,
            server_default='0',
        ),
        sa.Column(
            'imp_op_ex', sa.Numeric(precision=14, scale=2), nullable=True, server_default='0'
        ),
        sa.Column('imp_trib', sa.Numeric(precision=14, scale=2), nullable=True, server_default='0'),
        sa.Column('mon_id', sa.String(length=5), nullable=True, server_default='PES'),
        sa.Column(
            'mon_cotiz', sa.Numeric(precision=14, scale=6), nullable=True, server_default='1'
        ),
        sa.Column('cae', sa.String(length=20), nullable=True),
        sa.Column('cae_vencimiento', sa.Date(), nullable=True),
        sa.Column('estado', sa.String(length=20), nullable=True, server_default='pendiente'),
        sa.Column('error_codigo', sa.String(length=20), nullable=True),
        sa.Column('error_mensaje', sa.Text(), nullable=True),
        sa.Column('arca_request', sa.JSON(), nullable=True),
        sa.Column('arca_response', sa.JSON(), nullable=True),
        sa.Column('fch_serv_desde', sa.Date(), nullable=True),
        sa.Column('fch_serv_hasta', sa.Date(), nullable=True),
        sa.Column('fch_vto_pago', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id'], name='fk_facturas_empresa_id'),
        sa.ForeignKeyConstraint(['venta_id'], ['ventas.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'empresa_id',
            'tipo_comprobante',
            'punto_venta',
            'numero_comprobante',
            name='uq_factura_comprobante',
        ),
    )
    with op.batch_alter_table('facturas', schema=None) as batch_op:
        batch_op.create_index('ix_facturas_empresa_id', ['empresa_id'])
        batch_op.create_index('ix_facturas_venta_id', ['venta_id'])

    op.create_table(
        'factura_detalles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('factura_id', sa.Integer(), nullable=False),
        sa.Column('producto_id', sa.Integer(), nullable=True),
        sa.Column('descripcion', sa.String(length=200), nullable=False),
        sa.Column('cantidad', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('precio_unitario', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('subtotal', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            'iva_porcentaje', sa.Numeric(precision=5, scale=2), nullable=False, server_default='21'
        ),
        sa.Column('iva_id', sa.Integer(), nullable=True),
        sa.Column(
            'iva_monto', sa.Numeric(precision=14, scale=2), nullable=True, server_default='0'
        ),
        sa.ForeignKeyConstraint(['factura_id'], ['facturas.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['producto_id'], ['productos.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('factura_detalles', schema=None) as batch_op:
        batch_op.create_index('ix_factura_detalles_factura_id', ['factura_id'])
        batch_op.create_index('ix_factura_detalles_producto_id', ['producto_id'])

    op.create_table(
        'comprobantes_asociados',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('factura_id', sa.Integer(), nullable=False),
        sa.Column('tipo_comprobante', sa.Integer(), nullable=False),
        sa.Column('punto_venta', sa.Integer(), nullable=False),
        sa.Column('numero_comprobante', sa.Integer(), nullable=False),
        sa.Column('cuit_emisor', sa.String(length=13), nullable=True),
        sa.Column('fecha_comprobante', sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(['factura_id'], ['facturas.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('comprobantes_asociados', schema=None) as batch_op:
        batch_op.create_index('ix_comprobantes_asociados_factura_id', ['factura_id'])


def downgrade():
    op.drop_table('comprobantes_asociados')
    op.drop_table('factura_detalles')
    op.drop_table('facturas')

    with op.batch_alter_table('clientes', schema=None) as batch_op:
        batch_op.drop_column('doc_tipo')
        batch_op.drop_column('condicion_iva')
        batch_op.drop_column('condicion_iva_id')
        batch_op.drop_column('razon_social')

    with op.batch_alter_table('empresas', schema=None) as batch_op:
        batch_op.drop_column('arca_habilitado')
        batch_op.drop_column('ambiente_arca')
        batch_op.drop_column('clave_privada_arca')
        batch_op.drop_column('certificado_arca')
        batch_op.drop_column('punto_venta_arca')
        batch_op.drop_column('inicio_actividades')
        batch_op.drop_column('condicion_iva')
        batch_op.drop_column('condicion_iva_id')
