from decimal import Decimal

from app.extensions import db
from app.models import MovimientoStock, Producto, Usuario


def test_movimiento_stock_props(app):
    usuario = Usuario(
        email='stock@ferrerp.test',
        nombre='Usuario Stock',
        rol='administrador',
        activo=True,
    )
    usuario.set_password('clave')
    producto = Producto(
        codigo='PRD-STK',
        nombre='Producto Stock',
        unidad_medida='unidad',
        precio_costo=Decimal('1.00'),
        precio_venta=Decimal('2.00'),
        stock_actual=Decimal('5.000'),
        stock_minimo=Decimal('1.000'),
        activo=True,
    )
    db.session.add_all([usuario, producto])
    db.session.commit()

    movimiento = MovimientoStock(
        producto_id=producto.id,
        tipo='compra',
        cantidad=Decimal('3.000'),
        stock_anterior=Decimal('5.000'),
        stock_posterior=Decimal('8.000'),
        usuario_id=usuario.id,
    )
    db.session.add(movimiento)
    db.session.commit()

    assert movimiento.tipo_display == 'Compra'
    assert movimiento.es_entrada is True
    assert movimiento.es_salida is False
