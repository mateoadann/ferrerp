"""
Seeds para datos iniciales de FerrERP.
Ejecutar con: flask seed
"""

import random
from datetime import timedelta
from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models import (
    Caja,
    Categoria,
    Cliente,
    Configuracion,
    Empresa,
    MovimientoCaja,
    MovimientoStock,
    Presupuesto,
    PresupuestoDetalle,
    Producto,
    Proveedor,
    Usuario,
    Venta,
    VentaDetalle,
)
from app.utils.helpers import ahora_argentina


def run_seeds():
    """Ejecuta todos los seeds."""
    print('Iniciando carga de datos de prueba...')

    # Limpiar datos existentes (en orden inverso por las FK)
    print('Limpiando datos existentes...')
    PresupuestoDetalle.query.delete()
    Presupuesto.query.delete()
    MovimientoCaja.query.delete()
    MovimientoStock.query.delete()
    VentaDetalle.query.delete()
    Venta.query.delete()
    Caja.query.delete()
    Producto.query.delete()
    Categoria.query.delete()
    Proveedor.query.delete()
    Cliente.query.delete()
    Configuracion.query.delete()
    Usuario.query.delete()
    Empresa.query.delete()
    db.session.commit()

    # Crear empresa demo
    empresa = seed_empresa()

    # Crear configuracion
    seed_configuracion(empresa.id)

    # Crear usuarios
    seed_usuarios(empresa.id)

    # Crear categorias
    seed_categorias(empresa.id)

    # Crear proveedores
    seed_proveedores(empresa.id)

    # Crear productos
    seed_productos(empresa.id)

    # Crear clientes
    seed_clientes(empresa.id)

    # Crear ventas de ejemplo
    seed_ventas(empresa.id)

    db.session.commit()
    print('Datos de prueba cargados correctamente!')


def seed_empresa():
    """Crea empresa demo."""
    print('  - Empresa demo...')

    empresa = Empresa(
        nombre='Ferretería El Tornillo',
        cuit='30-12345678-9',
        direccion='Av. San Martín 1234, CABA',
        telefono='011-4555-1234',
        email='contacto@eltornillo.com',
        activa=True,
    )
    db.session.add(empresa)
    db.session.flush()
    return empresa


def seed_configuracion(empresa_id):
    """Crea la configuracion inicial del negocio."""
    print('  - Configuracion del negocio...')

    configs = [
        ('nombre_negocio', 'Ferreteria El Tornillo', 'string'),
        ('cuit', '30-12345678-9', 'string'),
        ('direccion', 'Av. San Martin 1234, CABA', 'string'),
        ('telefono', '011-4555-1234', 'string'),
        ('email', 'contacto@eltornillo.com', 'string'),
        ('condicion_iva', 'responsable_inscripto', 'string'),
        ('moneda', 'ARS', 'string'),
        ('presupuesto_validez_dias', '15', 'integer'),
        (
            'presupuesto_texto_pie',
            'Los precios pueden variar sin previo aviso. Este presupuesto no incluye IVA salvo indicación expresa.',
            'string',
        ),
    ]

    for clave, valor, tipo in configs:
        config = Configuracion(
            clave=clave, valor=valor, tipo=tipo, empresa_id=empresa_id
        )
        db.session.add(config)


def seed_usuarios(empresa_id):
    """Crea usuarios de prueba."""
    print('  - Usuarios...')

    # Owner
    owner = Usuario(
        email='admin@ferreteria.com',
        nombre='Administrador',
        rol='owner',
        activo=True,
        empresa_id=empresa_id,
    )
    owner.set_password('admin123')
    db.session.add(owner)

    # Vendedor 1
    vendedor1 = Usuario(
        email='juan@ferreteria.com',
        nombre='Juan Perez',
        rol='vendedor',
        activo=True,
        empresa_id=empresa_id,
    )
    vendedor1.set_password('vendedor123')
    db.session.add(vendedor1)

    # Vendedor 2
    vendedor2 = Usuario(
        email='maria@ferreteria.com',
        nombre='Maria Garcia',
        rol='vendedor',
        activo=True,
        empresa_id=empresa_id,
    )
    vendedor2.set_password('vendedor123')
    db.session.add(vendedor2)


def seed_categorias(empresa_id):
    """Crea categorias de productos."""
    print('  - Categorias...')

    categorias = {
        'Herramientas': {
            'descripcion': 'Herramientas para trabajo general.',
            'hijas': [
                ('Manuales', 'Martillos, destornilladores, llaves, pinzas.'),
                ('Electricas', 'Taladros, amoladoras, sierras electricas.'),
            ],
        },
        'Tornilleria': {
            'descripcion': 'Elementos de fijacion y sujecion.',
            'hijas': [
                ('Tornillos', 'Tornillos para madera, chapa y autoperforantes.'),
                ('Buloneria', 'Bulones, arandelas, tuercas y tarugos.'),
            ],
        },
        'Plomeria': {
            'descripcion': 'Productos para instalaciones sanitarias.',
            'hijas': [
                ('Griferia', 'Canillas y llaves de paso.'),
                ('Conexiones', 'Uniones, flexibles y accesorios de conexion.'),
            ],
        },
        'Electricidad': {
            'descripcion': 'Materiales para instalaciones electricas.',
            'hijas': [
                ('Cables', 'Cableado y conductores electricos.'),
                ('Tomas e Interruptores', 'Tomacorrientes, llaves y fichas.'),
            ],
        },
        'Pintureria': {
            'descripcion': 'Productos para pintura y terminaciones.',
            'hijas': [
                ('Pinturas', 'Latex, esmaltes y solventes.'),
                ('Accesorios de Pintura', 'Rodillos, pinceles y lijas.'),
            ],
        },
        'Construccion': {
            'descripcion': 'Materiales para obra y mamposteria.',
            'hijas': [],
        },
        'Jardineria': {
            'descripcion': 'Herramientas y accesorios para jardin.',
            'hijas': [],
        },
        'Adhesivos': {
            'descripcion': 'Pegamentos, siliconas y adhesivos tecnicos.',
            'hijas': [
                ('Siliconas', 'Selladores y siliconas para obra.'),
                ('Pegamentos', 'Pegamentos de contacto y colas vinilicas.'),
            ],
        },
    }

    for nombre_padre, datos in categorias.items():
        categoria_padre = Categoria(
            nombre=nombre_padre,
            descripcion=datos['descripcion'],
            activa=True,
            empresa_id=empresa_id,
        )
        db.session.add(categoria_padre)
        db.session.flush()

        for nombre_hija, descripcion_hija in datos['hijas']:
            subcategoria = Categoria(
                nombre=nombre_hija,
                descripcion=descripcion_hija,
                activa=True,
                padre_id=categoria_padre.id,
                empresa_id=empresa_id,
            )
            db.session.add(subcategoria)

    db.session.flush()


def seed_proveedores(empresa_id):
    """Crea proveedores de prueba."""
    print('  - Proveedores...')

    proveedores = [
        (
            'Stanley Tools',
            '30-11111111-1',
            'ventas@stanley.com',
            '011-4000-1111',
            'Av. Industrial 1000',
        ),
        (
            'Black & Decker',
            '30-22222222-2',
            'ventas@blackdecker.com',
            '011-4000-2222',
            'Parque Industrial Km 5',
        ),
        (
            'Tornillos SRL',
            '30-33333333-3',
            'info@tornillos.com',
            '011-4000-3333',
            'Calle Fierro 555',
        ),
        (
            'Sanitarios Norte',
            '30-44444444-4',
            'pedidos@sanitariosnorte.com',
            '011-4000-4444',
            'Ruta 8 Km 22',
        ),
        (
            'Cables del Sur',
            '30-55555555-5',
            'ventas@cablesdelsur.com',
            '011-4000-5555',
            'Av. Electricidad 789',
        ),
        (
            'Pinturas Color',
            '30-66666666-6',
            'info@pinturascolor.com',
            '011-4000-6666',
            'Zona Industrial Lote 15',
        ),
    ]

    for nombre, cuit, email, telefono, direccion in proveedores:
        proveedor = Proveedor(
            nombre=nombre,
            cuit=cuit,
            email=email,
            telefono=telefono,
            direccion=direccion,
            activo=True,
            empresa_id=empresa_id,
        )
        db.session.add(proveedor)

    db.session.flush()


def seed_productos(empresa_id):
    """Crea productos de prueba."""
    print('  - Productos...')

    # Obtener categorias y proveedores
    categorias = {c.nombre: c.id for c in Categoria.query.all()}
    proveedores = {p.nombre: p.id for p in Proveedor.query.all()}

    productos = [
        # Herramientas > Manuales
        (
            'HM001',
            'Martillo Carpintero 500g',
            'Manuales',
            'Stanley Tools',
            1500,
            2500,
            25,
            10,
            'unidad',
        ),
        (
            'HM002',
            'Destornillador Phillips #2',
            'Manuales',
            'Stanley Tools',
            400,
            750,
            50,
            15,
            'unidad',
        ),
        (
            'HM003',
            'Destornillador Plano 6mm',
            'Manuales',
            'Stanley Tools',
            380,
            700,
            45,
            15,
            'unidad',
        ),
        ('HM004', 'Llave Francesa 8"', 'Manuales', 'Stanley Tools', 2000, 3500, 15, 5, 'unidad'),
        ('HM005', 'Pinza Universal 8"', 'Manuales', 'Stanley Tools', 1200, 2000, 20, 8, 'unidad'),
        ('HM006', 'Cinta Metrica 5m', 'Manuales', 'Stanley Tools', 600, 1200, 30, 10, 'unidad'),
        (
            'HM007',
            'Nivel de Aluminio 60cm',
            'Manuales',
            'Stanley Tools',
            1800,
            3200,
            12,
            5,
            'unidad',
        ),
        # Herramientas > Electricas
        (
            'HE001',
            'Taladro Percutor 750W',
            'Electricas',
            'Black & Decker',
            25000,
            42000,
            8,
            3,
            'unidad',
        ),
        (
            'HE002',
            'Amoladora Angular 4 1/2"',
            'Electricas',
            'Black & Decker',
            18000,
            32000,
            10,
            4,
            'unidad',
        ),
        (
            'HE003',
            'Sierra Caladora 600W',
            'Electricas',
            'Black & Decker',
            22000,
            38000,
            6,
            2,
            'unidad',
        ),
        (
            'HE004',
            'Atornillador Inalambrico 12V',
            'Electricas',
            'Black & Decker',
            28000,
            48000,
            5,
            2,
            'unidad',
        ),
        # Tornilleria
        (
            'TO001',
            'Tornillo Madera 4x40 (x100)',
            'Tornillos',
            'Tornillos SRL',
            200,
            450,
            100,
            30,
            'unidad',
        ),
        (
            'TO002',
            'Tornillo Madera 5x50 (x100)',
            'Tornillos',
            'Tornillos SRL',
            280,
            550,
            80,
            25,
            'unidad',
        ),
        (
            'TO003',
            'Tornillo Autoperf. 10 (x100)',
            'Tornillos',
            'Tornillos SRL',
            350,
            700,
            60,
            20,
            'unidad',
        ),
        (
            'TO004',
            'Bulon Hex. 8x50 c/tuerca (x20)',
            'Buloneria',
            'Tornillos SRL',
            400,
            800,
            40,
            15,
            'unidad',
        ),
        ('TO005', 'Tarugo 8mm (x100)', 'Buloneria', 'Tornillos SRL', 180, 400, 120, 40, 'unidad'),
        (
            'TO006',
            'Arandela Plana 8mm (x100)',
            'Buloneria',
            'Tornillos SRL',
            80,
            180,
            80,
            30,
            'unidad',
        ),
        # Plomeria
        (
            'PL001',
            'Canilla Esferica 1/2"',
            'Griferia',
            'Sanitarios Norte',
            1500,
            2800,
            25,
            10,
            'unidad',
        ),
        (
            'PL002',
            'Flexibles Acero 40cm',
            'Conexiones',
            'Sanitarios Norte',
            800,
            1500,
            40,
            15,
            'unidad',
        ),
        ('PL003', 'Cinta Teflon 12m', 'Conexiones', 'Sanitarios Norte', 80, 200, 150, 50, 'unidad'),
        ('PL004', 'Union Doble 1/2"', 'Conexiones', 'Sanitarios Norte', 120, 280, 60, 20, 'unidad'),
        (
            'PL005',
            'Llave de Paso 3/4"',
            'Griferia',
            'Sanitarios Norte',
            2200,
            4000,
            15,
            5,
            'unidad',
        ),
        # Electricidad
        (
            'EL001',
            'Cable Unipolar 2.5mm (x100m)',
            'Cables',
            'Cables del Sur',
            8500,
            15000,
            20,
            5,
            'metro',
        ),
        (
            'EL002',
            'Cable Unipolar 1.5mm (x100m)',
            'Cables',
            'Cables del Sur',
            5500,
            9800,
            25,
            8,
            'metro',
        ),
        (
            'EL003',
            'Interruptor Simple',
            'Tomas e Interruptores',
            'Cables del Sur',
            280,
            600,
            80,
            25,
            'unidad',
        ),
        (
            'EL004',
            'Tomacorriente Doble',
            'Tomas e Interruptores',
            'Cables del Sur',
            350,
            750,
            70,
            20,
            'unidad',
        ),
        ('EL005', 'Cinta Aisladora 10m', 'Cables', 'Cables del Sur', 180, 400, 100, 30, 'unidad'),
        (
            'EL006',
            'Ficha Macho 10A',
            'Tomas e Interruptores',
            'Cables del Sur',
            150,
            350,
            60,
            20,
            'unidad',
        ),
        # Pintureria
        (
            'PI001',
            'Latex Interior 4L Blanco',
            'Pinturas',
            'Pinturas Color',
            3500,
            6500,
            30,
            10,
            'litro',
        ),
        (
            'PI002',
            'Latex Interior 20L Blanco',
            'Pinturas',
            'Pinturas Color',
            15000,
            28000,
            15,
            5,
            'litro',
        ),
        (
            'PI003',
            'Rodillo Lana 22cm',
            'Accesorios de Pintura',
            'Pinturas Color',
            800,
            1500,
            25,
            8,
            'unidad',
        ),
        (
            'PI004',
            'Pincel 2"',
            'Accesorios de Pintura',
            'Pinturas Color',
            250,
            500,
            40,
            15,
            'unidad',
        ),
        ('PI005', 'Aguarras 1L', 'Pinturas', 'Pinturas Color', 600, 1200, 35, 12, 'litro'),
        (
            'PI006',
            'Lija al Agua #120',
            'Accesorios de Pintura',
            'Pinturas Color',
            80,
            180,
            100,
            30,
            'unidad',
        ),
        # Adhesivos
        (
            'AD001',
            'Silicona Acetica 280ml',
            'Siliconas',
            'Pinturas Color',
            600,
            1200,
            40,
            15,
            'unidad',
        ),
        (
            'AD002',
            'Adhesivo Contacto 250ml',
            'Pegamentos',
            'Pinturas Color',
            900,
            1800,
            30,
            10,
            'unidad',
        ),
        ('AD003', 'Cola Vinilica 1kg', 'Pegamentos', 'Pinturas Color', 500, 1000, 35, 12, 'kilo'),
        (
            'AD004',
            'Cinta Doble Faz 19mm',
            'Adhesivos',
            'Pinturas Color',
            350,
            700,
            50,
            18,
            'unidad',
        ),
    ]

    for codigo, nombre, cat_nombre, prov_nombre, costo, venta, stock, minimo, unidad in productos:
        producto = Producto(
            codigo=codigo,
            nombre=nombre,
            categoria_id=categorias.get(cat_nombre),
            proveedor_id=proveedores.get(prov_nombre),
            precio_costo=Decimal(str(costo)),
            precio_venta=Decimal(str(venta)),
            stock_actual=Decimal(str(stock)),
            stock_minimo=Decimal(str(minimo)),
            unidad_medida=unidad,
            activo=True,
            empresa_id=empresa_id,
        )
        db.session.add(producto)

    db.session.flush()


def seed_clientes(empresa_id):
    """Crea clientes de prueba."""
    print('  - Clientes...')

    clientes = [
        (
            'Carlos Rodriguez',
            '20-12345678-9',
            '011-4555-1001',
            'carlos@email.com',
            'Calle Falsa 123',
            50000,
        ),
        (
            'Muebleria San Jose',
            '30-98765432-1',
            '011-4555-1002',
            'muebleria@email.com',
            'Av. Libertador 456',
            100000,
        ),
        (
            'Constructora Norte',
            '30-11223344-5',
            '011-4555-1003',
            'constructora@email.com',
            'Ruta 9 Km 12',
            200000,
        ),
        (
            'Pedro Martinez',
            '20-55667788-0',
            '011-4555-1004',
            'pedro@email.com',
            'San Martin 789',
            30000,
        ),
        (
            'Electricidad Total',
            '30-99887766-3',
            '011-4555-1005',
            'electotal@email.com',
            'Av. Edison 321',
            80000,
        ),
        ('Ana Gomez', '27-44556677-8', '011-4555-1006', 'ana@email.com', 'Belgrano 654', 25000),
        (
            'Pinturerias Sur',
            '30-77889900-2',
            '011-4555-1007',
            'pintsur@email.com',
            'Rivadavia 987',
            150000,
        ),
        (
            'Roberto Sanchez',
            '20-33221100-4',
            '011-4555-1008',
            'roberto@email.com',
            'Mitre 147',
            20000,
        ),
    ]

    for nombre, dni_cuit, telefono, email, direccion, limite_credito in clientes:
        cliente = Cliente(
            nombre=nombre,
            dni_cuit=dni_cuit,
            telefono=telefono,
            email=email,
            direccion=direccion,
            limite_credito=Decimal(str(limite_credito)),
            saldo_cuenta_corriente=Decimal('0'),
            activo=True,
            empresa_id=empresa_id,
        )
        db.session.add(cliente)

    db.session.flush()


def seed_ventas(empresa_id):
    """Crea ventas de ejemplo para los ultimos 7 dias."""
    print('  - Ventas de ejemplo...')

    usuario = Usuario.query.filter_by(rol='vendedor').first()
    productos = Producto.query.filter_by(empresa_id=empresa_id).all()
    clientes = Cliente.query.filter_by(empresa_id=empresa_id).all()

    if not usuario or not productos:
        print('    (Saltando - no hay usuarios o productos)')
        return

    # Crear una caja abierta
    caja = Caja(
        fecha_apertura=ahora_argentina().replace(hour=8, minute=0, second=0),
        monto_inicial=Decimal('10000'),
        estado='abierta',
        usuario_apertura_id=usuario.id,
        empresa_id=empresa_id,
    )
    db.session.add(caja)
    db.session.flush()

    formas_pago = ['efectivo', 'tarjeta_debito', 'tarjeta_credito', 'transferencia']

    # Generar ventas para los ultimos 7 dias
    numero_base = 1
    for dias_atras in range(7, -1, -1):
        fecha_base = ahora_argentina() - timedelta(days=dias_atras)

        # Entre 3 y 8 ventas por dia
        num_ventas = random.randint(3, 8)

        for _ in range(num_ventas):
            # Hora aleatoria entre 8am y 8pm
            hora = random.randint(8, 20)
            minuto = random.randint(0, 59)
            fecha_venta = fecha_base.replace(hour=hora, minute=minuto, second=0)

            # Cliente aleatorio o consumidor final
            cliente = random.choice(clientes) if random.random() > 0.4 else None
            forma_pago = random.choice(formas_pago)

            venta = Venta(
                numero=numero_base,
                fecha=fecha_venta,
                cliente_id=cliente.id if cliente else None,
                usuario_id=usuario.id,
                forma_pago=forma_pago,
                estado='completada',
                caja_id=caja.id,
                descuento_porcentaje=Decimal('0'),
                empresa_id=empresa_id,
            )

            # Entre 1 y 5 productos por venta
            num_items = random.randint(1, 5)
            productos_venta = random.sample(productos, min(num_items, len(productos)))

            subtotal = Decimal('0')
            for producto in productos_venta:
                cantidad = Decimal(str(random.randint(1, 3)))
                item_subtotal = cantidad * producto.precio_venta
                subtotal += item_subtotal

                detalle = VentaDetalle(
                    producto_id=producto.id,
                    cantidad=cantidad,
                    precio_unitario=producto.precio_venta,
                    subtotal=item_subtotal,
                )
                venta.detalles.append(detalle)

            venta.subtotal = subtotal
            venta.descuento_monto = Decimal('0')
            venta.total = subtotal

            db.session.add(venta)
            numero_base += 1

    db.session.flush()


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        run_seeds()
