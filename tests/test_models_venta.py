from datetime import datetime
from decimal import Decimal

from app.extensions import db
from app.models import Producto, Usuario, Venta, VentaDetalle


def _crear_usuario():
    usuario = Usuario(
        email='venta@ferrerp.test',
        nombre='Usuario Venta',
        rol='vendedor',
        activo=True,
    )
    usuario.set_password('clave')
    return usuario


def _crear_producto():
    return Producto(
        codigo='PRD-VENTA',
        nombre='Producto Venta',
        unidad_medida='unidad',
        precio_costo=Decimal('10.00'),
        precio_venta=Decimal('15.00'),
        stock_actual=Decimal('10.000'),
        stock_minimo=Decimal('1.000'),
        activo=True,
    )


def test_venta_calcular_totales_y_props(app):
    usuario = _crear_usuario()
    producto = _crear_producto()
    db.session.add_all([usuario, producto])
    db.session.commit()

    venta = Venta(
        numero=1,
        fecha=datetime(2024, 1, 1),
        usuario_id=usuario.id,
        total=Decimal('0.00'),
        forma_pago='efectivo',
        estado='completada',
        descuento_porcentaje=Decimal('10.00'),
    )

    detalle = VentaDetalle(
        producto_id=producto.id,
        cantidad=Decimal('2.000'),
        precio_unitario=Decimal('10.00'),
        subtotal=Decimal('0.00'),
    )
    detalle.calcular_subtotal()
    venta.detalles.append(detalle)

    db.session.add(venta)
    db.session.commit()

    total = venta.calcular_totales()
    assert total == Decimal('18.00')
    assert venta.cantidad_items == Decimal('2.000')
    assert venta.numero_completo == '2024-000001'
    assert venta.forma_pago_display == 'Efectivo'
    assert venta.estado_display == 'Completada'
