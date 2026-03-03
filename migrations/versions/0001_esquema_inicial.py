"""Esquema inicial consolidado

Crea todas las tablas del sistema FerrERP con multi-tenancy (empresa_id),
categorias jerarquicas, presupuestos e IVA por producto.

Revision ID: 0001
Revises:
Create Date: 2026-03-03 23:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # --- Tabla empresas ---
    op.create_table(
        'empresas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=150), nullable=False),
        sa.Column('cuit', sa.String(length=13), nullable=True),
        sa.Column('direccion', sa.String(length=200), nullable=True),
        sa.Column('telefono', sa.String(length=20), nullable=True),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column(
            'activa', sa.Boolean(), nullable=False, server_default='true'
        ),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # --- Tabla usuarios ---
    op.create_table(
        'usuarios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('password_hash', sa.String(length=256), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column(
            'rol',
            sa.Enum(
                'owner', 'administrador', 'vendedor',
                name='rol_usuario',
            ),
            nullable=False,
            server_default='vendedor',
        ),
        sa.Column(
            'activo', sa.Boolean(), nullable=False, server_default='true'
        ),
        sa.Column('empresa_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['empresa_id'], ['empresas.id'], name='fk_usuarios_empresa_id'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.create_index('ix_usuarios_email', ['email'], unique=True)
        batch_op.create_index('ix_usuarios_empresa_id', ['empresa_id'])

    # --- Tabla categorias ---
    op.create_table(
        'categorias',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=50), nullable=False),
        sa.Column('descripcion', sa.String(length=200), nullable=True),
        sa.Column('padre_id', sa.Integer(), nullable=True),
        sa.Column(
            'activa', sa.Boolean(), nullable=False, server_default='true'
        ),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['empresa_id'], ['empresas.id'], name='fk_categorias_empresa_id'
        ),
        sa.ForeignKeyConstraint(
            ['padre_id'], ['categorias.id'],
            name='fk_categorias_padre_id_categorias',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'empresa_id', 'nombre', 'padre_id',
            name='uq_categorias_empresa_nombre_padre_id',
        ),
    )
    with op.batch_alter_table('categorias', schema=None) as batch_op:
        batch_op.create_index('ix_categorias_empresa_id', ['empresa_id'])
        batch_op.create_index('ix_categorias_padre_id', ['padre_id'])

    # --- Tabla proveedores ---
    op.create_table(
        'proveedores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('razon_social', sa.String(length=150), nullable=True),
        sa.Column('cuit', sa.String(length=13), nullable=True),
        sa.Column('telefono', sa.String(length=20), nullable=True),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('direccion', sa.String(length=200), nullable=True),
        sa.Column(
            'condicion_pago',
            sa.Enum(
                'contado', '30_dias', '60_dias',
                name='condicion_pago',
            ),
            server_default='contado',
        ),
        sa.Column('notas', sa.Text(), nullable=True),
        sa.Column(
            'activo', sa.Boolean(), nullable=False, server_default='true'
        ),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['empresa_id'], ['empresas.id'],
            name='fk_proveedores_empresa_id',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('proveedores', schema=None) as batch_op:
        batch_op.create_index('ix_proveedores_empresa_id', ['empresa_id'])

    # --- Tabla clientes ---
    op.create_table(
        'clientes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('dni_cuit', sa.String(length=13), nullable=True),
        sa.Column('telefono', sa.String(length=20), nullable=True),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('direccion', sa.String(length=200), nullable=True),
        sa.Column(
            'limite_credito',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default='0',
        ),
        sa.Column(
            'saldo_cuenta_corriente',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default='0',
        ),
        sa.Column('notas', sa.Text(), nullable=True),
        sa.Column(
            'activo', sa.Boolean(), nullable=False, server_default='true'
        ),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['empresa_id'], ['empresas.id'],
            name='fk_clientes_empresa_id',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('clientes', schema=None) as batch_op:
        batch_op.create_index('ix_clientes_empresa_id', ['empresa_id'])
        batch_op.create_index('ix_clientes_dni_cuit', ['dni_cuit'])

    # --- Tabla productos ---
    op.create_table(
        'productos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('codigo', sa.String(length=20), nullable=False),
        sa.Column('codigo_barras', sa.String(length=50), nullable=True),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('categoria_id', sa.Integer(), nullable=True),
        sa.Column(
            'unidad_medida',
            sa.Enum(
                'unidad', 'metro', 'kilo', 'litro', 'par',
                name='unidad_medida',
            ),
            nullable=False,
            server_default='unidad',
        ),
        sa.Column(
            'precio_costo',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default='0',
        ),
        sa.Column(
            'precio_venta',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default='0',
        ),
        sa.Column(
            'iva_porcentaje',
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default='21',
        ),
        sa.Column(
            'stock_actual',
            sa.Numeric(precision=12, scale=3),
            nullable=False,
            server_default='0',
        ),
        sa.Column(
            'stock_minimo',
            sa.Numeric(precision=12, scale=3),
            nullable=False,
            server_default='0',
        ),
        sa.Column('proveedor_id', sa.Integer(), nullable=True),
        sa.Column('ubicacion', sa.String(length=50), nullable=True),
        sa.Column(
            'activo', sa.Boolean(), nullable=False, server_default='true'
        ),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['empresa_id'], ['empresas.id'],
            name='fk_productos_empresa_id',
        ),
        sa.ForeignKeyConstraint(
            ['categoria_id'], ['categorias.id'],
        ),
        sa.ForeignKeyConstraint(
            ['proveedor_id'], ['proveedores.id'],
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'empresa_id', 'codigo', name='uq_productos_empresa_codigo'
        ),
    )
    with op.batch_alter_table('productos', schema=None) as batch_op:
        batch_op.create_index('ix_productos_empresa_id', ['empresa_id'])
        batch_op.create_index('ix_productos_codigo', ['codigo'])
        batch_op.create_index(
            'ix_productos_codigo_barras', ['codigo_barras']
        )
        batch_op.create_index(
            'ix_productos_categoria_id', ['categoria_id']
        )
        batch_op.create_index(
            'ix_productos_proveedor_id', ['proveedor_id']
        )

    # --- Tabla configuraciones ---
    op.create_table(
        'configuraciones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('clave', sa.String(length=50), nullable=False),
        sa.Column('valor', sa.Text(), nullable=True),
        sa.Column(
            'tipo',
            sa.Enum(
                'string', 'integer', 'decimal', 'boolean', 'json',
                name='tipo_configuracion',
            ),
            nullable=False,
            server_default='string',
        ),
        sa.ForeignKeyConstraint(
            ['empresa_id'], ['empresas.id'],
            name='fk_configuraciones_empresa_id',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'empresa_id', 'clave', name='uq_configuraciones_empresa_clave'
        ),
    )
    with op.batch_alter_table('configuraciones', schema=None) as batch_op:
        batch_op.create_index(
            'ix_configuraciones_empresa_id', ['empresa_id']
        )
        batch_op.create_index('ix_configuraciones_clave', ['clave'])

    # --- Tabla cajas ---
    op.create_table(
        'cajas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('fecha_apertura', sa.DateTime(), nullable=False),
        sa.Column('fecha_cierre', sa.DateTime(), nullable=True),
        sa.Column(
            'usuario_apertura_id', sa.Integer(), nullable=False
        ),
        sa.Column('usuario_cierre_id', sa.Integer(), nullable=True),
        sa.Column(
            'monto_inicial',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column(
            'monto_esperado',
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
        sa.Column(
            'monto_real',
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
        sa.Column(
            'diferencia',
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
        sa.Column(
            'estado',
            sa.Enum('abierta', 'cerrada', name='estado_caja'),
            nullable=False,
            server_default='abierta',
        ),
        sa.Column('observaciones', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ['empresa_id'], ['empresas.id'],
            name='fk_cajas_empresa_id',
        ),
        sa.ForeignKeyConstraint(
            ['usuario_apertura_id'], ['usuarios.id'],
        ),
        sa.ForeignKeyConstraint(
            ['usuario_cierre_id'], ['usuarios.id'],
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('cajas', schema=None) as batch_op:
        batch_op.create_index('ix_cajas_empresa_id', ['empresa_id'])

    # --- Tabla presupuestos ---
    op.create_table(
        'presupuestos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('numero', sa.Integer(), nullable=False),
        sa.Column('fecha', sa.DateTime(), nullable=False),
        sa.Column('fecha_vencimiento', sa.DateTime(), nullable=False),
        sa.Column('cliente_id', sa.Integer(), nullable=True),
        sa.Column('cliente_nombre', sa.String(length=100), nullable=True),
        sa.Column('cliente_telefono', sa.String(length=20), nullable=True),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column(
            'subtotal',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default='0',
        ),
        sa.Column(
            'descuento_porcentaje',
            sa.Numeric(precision=5, scale=2),
            nullable=True,
        ),
        sa.Column(
            'descuento_monto',
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
        sa.Column(
            'total',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default='0',
        ),
        sa.Column(
            'estado',
            sa.Enum(
                'pendiente', 'aceptado', 'rechazado', 'vencido',
                'convertido',
                name='estado_presupuesto',
            ),
            nullable=False,
            server_default='pendiente',
        ),
        sa.Column('notas', sa.Text(), nullable=True),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['empresa_id'], ['empresas.id'],
            name='fk_presupuestos_empresa_id',
        ),
        sa.ForeignKeyConstraint(['cliente_id'], ['clientes.id']),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('presupuestos', schema=None) as batch_op:
        batch_op.create_index('ix_presupuestos_empresa_id', ['empresa_id'])
        batch_op.create_index('ix_presupuestos_numero', ['numero'])
        batch_op.create_index(
            'ix_presupuestos_cliente_id', ['cliente_id']
        )
        batch_op.create_index(
            'ix_presupuestos_token', ['token'], unique=True
        )

    # --- Tabla ventas ---
    op.create_table(
        'ventas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('numero', sa.Integer(), nullable=False),
        sa.Column('fecha', sa.DateTime(), nullable=False),
        sa.Column('cliente_id', sa.Integer(), nullable=True),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column(
            'subtotal',
            sa.Numeric(precision=12, scale=2),
            server_default='0',
        ),
        sa.Column(
            'descuento_porcentaje',
            sa.Numeric(precision=5, scale=2),
            server_default='0',
        ),
        sa.Column(
            'descuento_monto',
            sa.Numeric(precision=12, scale=2),
            server_default='0',
        ),
        sa.Column(
            'total',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column(
            'forma_pago',
            sa.Enum(
                'efectivo', 'tarjeta_debito', 'tarjeta_credito',
                'transferencia', 'cuenta_corriente',
                name='forma_pago',
            ),
            nullable=False,
            server_default='efectivo',
        ),
        sa.Column(
            'estado',
            sa.Enum(
                'completada', 'anulada', name='estado_venta'
            ),
            nullable=False,
            server_default='completada',
        ),
        sa.Column('motivo_anulacion', sa.Text(), nullable=True),
        sa.Column('caja_id', sa.Integer(), nullable=True),
        sa.Column('presupuesto_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['empresa_id'], ['empresas.id'],
            name='fk_ventas_empresa_id',
        ),
        sa.ForeignKeyConstraint(['cliente_id'], ['clientes.id']),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id']),
        sa.ForeignKeyConstraint(['caja_id'], ['cajas.id']),
        sa.ForeignKeyConstraint(
            ['presupuesto_id'], ['presupuestos.id']
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('ventas', schema=None) as batch_op:
        batch_op.create_index('ix_ventas_empresa_id', ['empresa_id'])
        batch_op.create_index('ix_ventas_numero', ['numero'])
        batch_op.create_index('ix_ventas_cliente_id', ['cliente_id'])
        batch_op.create_index('ix_ventas_caja_id', ['caja_id'])
        batch_op.create_index(
            'ix_ventas_presupuesto_id', ['presupuesto_id']
        )

    # --- Tabla venta_detalles ---
    op.create_table(
        'venta_detalles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('venta_id', sa.Integer(), nullable=False),
        sa.Column('producto_id', sa.Integer(), nullable=False),
        sa.Column(
            'cantidad',
            sa.Numeric(precision=12, scale=3),
            nullable=False,
        ),
        sa.Column(
            'precio_unitario',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column(
            'iva_porcentaje',
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default='21',
        ),
        sa.Column(
            'subtotal',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['venta_id'], ['ventas.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(['producto_id'], ['productos.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('venta_detalles', schema=None) as batch_op:
        batch_op.create_index(
            'ix_venta_detalles_venta_id', ['venta_id']
        )
        batch_op.create_index(
            'ix_venta_detalles_producto_id', ['producto_id']
        )

    # --- Tabla presupuesto_detalles ---
    op.create_table(
        'presupuesto_detalles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('presupuesto_id', sa.Integer(), nullable=False),
        sa.Column('producto_id', sa.Integer(), nullable=False),
        sa.Column(
            'cantidad',
            sa.Numeric(precision=12, scale=3),
            nullable=False,
        ),
        sa.Column(
            'precio_unitario',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column(
            'iva_porcentaje',
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default='21',
        ),
        sa.Column(
            'subtotal',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['presupuesto_id'], ['presupuestos.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(['producto_id'], ['productos.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table(
        'presupuesto_detalles', schema=None
    ) as batch_op:
        batch_op.create_index(
            'ix_presupuesto_detalles_presupuesto_id', ['presupuesto_id']
        )
        batch_op.create_index(
            'ix_presupuesto_detalles_producto_id', ['producto_id']
        )

    # --- Tabla devoluciones ---
    op.create_table(
        'devoluciones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('venta_id', sa.Integer(), nullable=False),
        sa.Column('fecha', sa.DateTime(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('motivo', sa.Text(), nullable=False),
        sa.Column(
            'accion',
            sa.Enum(
                'reintegro_efectivo', 'nota_credito',
                'credito_cuenta_corriente',
                name='accion_devolucion',
            ),
            nullable=False,
        ),
        sa.Column(
            'monto_total',
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['empresa_id'], ['empresas.id'],
            name='fk_devoluciones_empresa_id',
        ),
        sa.ForeignKeyConstraint(['venta_id'], ['ventas.id']),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('devoluciones', schema=None) as batch_op:
        batch_op.create_index(
            'ix_devoluciones_empresa_id', ['empresa_id']
        )
        batch_op.create_index(
            'ix_devoluciones_venta_id', ['venta_id']
        )

    # --- Tabla devolucion_detalles ---
    op.create_table(
        'devolucion_detalles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('devolucion_id', sa.Integer(), nullable=False),
        sa.Column('producto_id', sa.Integer(), nullable=False),
        sa.Column(
            'cantidad',
            sa.Numeric(precision=12, scale=3),
            nullable=False,
        ),
        sa.Column(
            'precio_unitario',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column(
            'subtotal',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['devolucion_id'], ['devoluciones.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(['producto_id'], ['productos.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table(
        'devolucion_detalles', schema=None
    ) as batch_op:
        batch_op.create_index(
            'ix_devolucion_detalles_devolucion_id', ['devolucion_id']
        )

    # --- Tabla ordenes_compra ---
    op.create_table(
        'ordenes_compra',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('numero', sa.Integer(), nullable=False),
        sa.Column('fecha', sa.DateTime(), nullable=False),
        sa.Column('proveedor_id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column(
            'estado',
            sa.Enum(
                'pendiente', 'recibida_parcial', 'recibida_completa',
                'cancelada',
                name='estado_orden_compra',
            ),
            nullable=False,
            server_default='pendiente',
        ),
        sa.Column(
            'total',
            sa.Numeric(precision=12, scale=2),
            server_default='0',
        ),
        sa.Column('notas', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['empresa_id'], ['empresas.id'],
            name='fk_ordenes_compra_empresa_id',
        ),
        sa.ForeignKeyConstraint(
            ['proveedor_id'], ['proveedores.id']
        ),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'empresa_id', 'numero',
            name='uq_ordenes_compra_empresa_numero',
        ),
    )
    with op.batch_alter_table('ordenes_compra', schema=None) as batch_op:
        batch_op.create_index(
            'ix_ordenes_compra_empresa_id', ['empresa_id']
        )
        batch_op.create_index('ix_ordenes_compra_numero', ['numero'])
        batch_op.create_index(
            'ix_ordenes_compra_proveedor_id', ['proveedor_id']
        )

    # --- Tabla orden_compra_detalles ---
    op.create_table(
        'orden_compra_detalles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('orden_compra_id', sa.Integer(), nullable=False),
        sa.Column('producto_id', sa.Integer(), nullable=False),
        sa.Column(
            'cantidad_pedida',
            sa.Numeric(precision=12, scale=3),
            nullable=False,
        ),
        sa.Column(
            'cantidad_recibida',
            sa.Numeric(precision=12, scale=3),
            server_default='0',
        ),
        sa.Column(
            'precio_unitario',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column(
            'subtotal',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['orden_compra_id'], ['ordenes_compra.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(['producto_id'], ['productos.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table(
        'orden_compra_detalles', schema=None
    ) as batch_op:
        batch_op.create_index(
            'ix_orden_compra_detalles_orden_compra_id', ['orden_compra_id']
        )

    # --- Tabla movimientos_stock ---
    op.create_table(
        'movimientos_stock',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('producto_id', sa.Integer(), nullable=False),
        sa.Column(
            'tipo',
            sa.Enum(
                'venta', 'compra', 'ajuste_positivo',
                'ajuste_negativo', 'devolucion',
                name='tipo_movimiento_stock',
            ),
            nullable=False,
        ),
        sa.Column(
            'cantidad',
            sa.Numeric(precision=12, scale=3),
            nullable=False,
        ),
        sa.Column(
            'stock_anterior',
            sa.Numeric(precision=12, scale=3),
            nullable=False,
        ),
        sa.Column(
            'stock_posterior',
            sa.Numeric(precision=12, scale=3),
            nullable=False,
        ),
        sa.Column(
            'referencia_tipo', sa.String(length=20), nullable=True
        ),
        sa.Column('referencia_id', sa.Integer(), nullable=True),
        sa.Column('motivo', sa.Text(), nullable=True),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['empresa_id'], ['empresas.id'],
            name='fk_movimientos_stock_empresa_id',
        ),
        sa.ForeignKeyConstraint(
            ['producto_id'], ['productos.id']
        ),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('movimientos_stock', schema=None) as batch_op:
        batch_op.create_index(
            'ix_movimientos_stock_empresa_id', ['empresa_id']
        )
        batch_op.create_index(
            'ix_movimientos_stock_producto_id', ['producto_id']
        )
        batch_op.create_index(
            'ix_movimientos_stock_created_at', ['created_at']
        )

    # --- Tabla movimientos_caja ---
    op.create_table(
        'movimientos_caja',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('caja_id', sa.Integer(), nullable=False),
        sa.Column(
            'tipo',
            sa.Enum(
                'ingreso', 'egreso', name='tipo_movimiento_caja'
            ),
            nullable=False,
        ),
        sa.Column(
            'concepto',
            sa.Enum(
                'venta', 'cobro_cuenta_corriente', 'pago_proveedor',
                'gasto', 'retiro', 'devolucion', 'otro',
                name='concepto_movimiento_caja',
            ),
            nullable=False,
        ),
        sa.Column(
            'descripcion', sa.String(length=200), nullable=True
        ),
        sa.Column(
            'monto',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column(
            'forma_pago',
            sa.Enum(
                'efectivo', 'tarjeta_debito', 'tarjeta_credito',
                'transferencia',
                name='forma_pago_movimiento',
            ),
            nullable=False,
            server_default='efectivo',
        ),
        sa.Column(
            'referencia_tipo', sa.String(length=20), nullable=True
        ),
        sa.Column('referencia_id', sa.Integer(), nullable=True),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['caja_id'], ['cajas.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('movimientos_caja', schema=None) as batch_op:
        batch_op.create_index(
            'ix_movimientos_caja_caja_id', ['caja_id']
        )
        batch_op.create_index(
            'ix_movimientos_caja_created_at', ['created_at']
        )

    # --- Tabla movimientos_cuenta_corriente ---
    op.create_table(
        'movimientos_cuenta_corriente',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('cliente_id', sa.Integer(), nullable=False),
        sa.Column(
            'tipo',
            sa.Enum(
                'cargo', 'pago', name='tipo_movimiento_cc'
            ),
            nullable=False,
        ),
        sa.Column(
            'monto',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column(
            'saldo_anterior',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column(
            'saldo_posterior',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column(
            'referencia_tipo', sa.String(length=20), nullable=True
        ),
        sa.Column('referencia_id', sa.Integer(), nullable=True),
        sa.Column(
            'descripcion', sa.String(length=200), nullable=True
        ),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['empresa_id'], ['empresas.id'],
            name='fk_movimientos_cuenta_corriente_empresa_id',
        ),
        sa.ForeignKeyConstraint(['cliente_id'], ['clientes.id']),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table(
        'movimientos_cuenta_corriente', schema=None
    ) as batch_op:
        batch_op.create_index(
            'ix_movimientos_cuenta_corriente_empresa_id', ['empresa_id']
        )
        batch_op.create_index(
            'ix_movimientos_cuenta_corriente_cliente_id', ['cliente_id']
        )
        batch_op.create_index(
            'ix_movimientos_cuenta_corriente_created_at', ['created_at']
        )


def downgrade():
    op.drop_table('movimientos_cuenta_corriente')
    op.drop_table('movimientos_caja')
    op.drop_table('movimientos_stock')
    op.drop_table('orden_compra_detalles')
    op.drop_table('ordenes_compra')
    op.drop_table('devolucion_detalles')
    op.drop_table('devoluciones')
    op.drop_table('presupuesto_detalles')
    op.drop_table('venta_detalles')
    op.drop_table('ventas')
    op.drop_table('presupuestos')
    op.drop_table('cajas')
    op.drop_table('configuraciones')
    op.drop_table('productos')
    op.drop_table('clientes')
    op.drop_table('proveedores')
    op.drop_table('categorias')
    op.drop_table('usuarios')
    op.drop_table('empresas')

    # Eliminar tipos enum de PostgreSQL
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        for enum_name in [
            'tipo_movimiento_cc', 'forma_pago_movimiento',
            'concepto_movimiento_caja', 'tipo_movimiento_caja',
            'tipo_movimiento_stock', 'estado_orden_compra',
            'accion_devolucion', 'estado_venta', 'forma_pago',
            'estado_presupuesto', 'estado_caja', 'tipo_configuracion',
            'unidad_medida', 'condicion_pago', 'rol_usuario',
        ]:
            op.execute(f'DROP TYPE IF EXISTS {enum_name}')
