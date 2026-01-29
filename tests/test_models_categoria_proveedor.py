from decimal import Decimal

from app.extensions import db
from app.models import Categoria, Producto, Proveedor


def test_categoria_cantidad_productos(app):
    categoria = Categoria(nombre='Herramientas', activa=True)
    db.session.add(categoria)
    db.session.commit()

    producto_activo = Producto(
        codigo='PRD-CAT-1',
        nombre='Producto Activo',
        unidad_medida='unidad',
        precio_costo=Decimal('1.00'),
        precio_venta=Decimal('2.00'),
        stock_actual=Decimal('1.000'),
        stock_minimo=Decimal('0.000'),
        categoria_id=categoria.id,
        activo=True,
    )
    producto_inactivo = Producto(
        codigo='PRD-CAT-2',
        nombre='Producto Inactivo',
        unidad_medida='unidad',
        precio_costo=Decimal('1.00'),
        precio_venta=Decimal('2.00'),
        stock_actual=Decimal('1.000'),
        stock_minimo=Decimal('0.000'),
        categoria_id=categoria.id,
        activo=False,
    )
    db.session.add_all([producto_activo, producto_inactivo])
    db.session.commit()

    assert categoria.cantidad_productos == 1


def test_proveedor_condicion_pago_display(app):
    proveedor = Proveedor(nombre='Proveedor Uno', condicion_pago='30_dias', activo=True)
    db.session.add(proveedor)
    db.session.commit()

    assert proveedor.condicion_pago_display == '30 días'
