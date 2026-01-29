from decimal import Decimal

from app.extensions import db
from app.models import Producto


def test_create_producto(app):
    producto = Producto(
        codigo='PRD-001',
        nombre='Martillo',
        unidad_medida='unidad',
        precio_costo=Decimal('100.00'),
        precio_venta=Decimal('150.00'),
        stock_actual=Decimal('10.000'),
        stock_minimo=Decimal('5.000'),
        activo=True,
    )

    db.session.add(producto)
    db.session.commit()

    assert producto.id is not None
    assert producto.stock_bajo is False
    assert producto.to_dict()['codigo'] == 'PRD-001'
