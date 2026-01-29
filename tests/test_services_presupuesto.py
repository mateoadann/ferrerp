from decimal import Decimal

import pytest

from app.extensions import db
from app.models import Caja, Cliente, MovimientoCaja, MovimientoStock, Producto, Usuario
from app.services.presupuesto_service import crear_presupuesto, convertir_a_venta


def _crear_usuario(email='usuario@ferrerp.test', rol='vendedor'):
    usuario = Usuario(
        email=email,
        nombre='Usuario Test',
        rol=rol,
        activo=True,
    )
    usuario.set_password('clave')
    return usuario


def _crear_producto(codigo, stock_actual='10.000', precio='10.00'):
    return Producto(
        codigo=codigo,
        nombre=f'Producto {codigo}',
        unidad_medida='unidad',
        precio_costo=Decimal('5.00'),
        precio_venta=Decimal(str(precio)),
        stock_actual=Decimal(str(stock_actual)),
        stock_minimo=Decimal('1.000'),
        activo=True,
    )


def _crear_caja(usuario_id):
    return Caja(
        usuario_apertura_id=usuario_id,
        monto_inicial=Decimal('100.00'),
    )


def _crear_cliente(limite_credito='100.00', saldo='0.00'):
    return Cliente(
        nombre='Cliente Test',
        limite_credito=Decimal(str(limite_credito)),
        saldo_cuenta_corriente=Decimal(str(saldo)),
        activo=True,
    )


def test_crear_presupuesto_calcula_totales(app):
    usuario = _crear_usuario()
    producto_a = _crear_producto('PRD-A', precio='10.00')
    producto_b = _crear_producto('PRD-B', precio='20.00')
    db.session.add_all([usuario, producto_a, producto_b])
    db.session.commit()

    items = [
        {'producto_id': producto_a.id, 'cantidad': Decimal('2.000'), 'precio_unitario': Decimal('10.00')},
        {'producto_id': producto_b.id, 'cantidad': Decimal('1.000'), 'precio_unitario': Decimal('20.00')},
    ]

    presupuesto = crear_presupuesto(
        items,
        usuario_id=usuario.id,
        descuento_porcentaje=Decimal('10.00'),
        cliente_nombre='Cliente Presupuesto',
    )

    assert presupuesto.subtotal == Decimal('40.00')
    assert presupuesto.descuento_monto == Decimal('4.00')
    assert presupuesto.total == Decimal('36.00')
    assert presupuesto.estado == 'pendiente'
    assert presupuesto.detalles.count() == 2


def test_crear_presupuesto_producto_inexistente(app):
    usuario = _crear_usuario()
    db.session.add(usuario)
    db.session.commit()

    items = [
        {'producto_id': 9999, 'cantidad': Decimal('1.000'), 'precio_unitario': Decimal('10.00')},
    ]

    with pytest.raises(ValueError, match='Producto no encontrado: 9999'):
        crear_presupuesto(items, usuario_id=usuario.id)


def test_convertir_a_venta_crea_movimientos(app):
    usuario = _crear_usuario()
    producto = _crear_producto('PRD-VENTA', stock_actual='5.000', precio='10.00')
    db.session.add_all([usuario, producto])
    db.session.commit()

    caja = _crear_caja(usuario.id)
    db.session.add(caja)
    db.session.commit()

    items = [
        {'producto_id': producto.id, 'cantidad': Decimal('2.000'), 'precio_unitario': Decimal('10.00')},
    ]
    presupuesto = crear_presupuesto(items, usuario_id=usuario.id)
    presupuesto.estado = 'aceptado'
    db.session.commit()

    venta = convertir_a_venta(
        presupuesto,
        usuario_id=usuario.id,
        forma_pago='efectivo',
        caja_id=caja.id,
    )

    db.session.refresh(producto)
    assert venta.total == presupuesto.total
    assert venta.estado == 'completada'
    assert producto.stock_actual == Decimal('3.000')

    movimiento_stock = MovimientoStock.query.filter_by(
        referencia_tipo='venta',
        referencia_id=venta.id,
    ).first()
    assert movimiento_stock is not None
    assert movimiento_stock.tipo == 'venta'
    assert movimiento_stock.cantidad == Decimal('-2.000')

    movimiento_caja = MovimientoCaja.query.filter_by(
        referencia_tipo='venta',
        referencia_id=venta.id,
    ).first()
    assert movimiento_caja is not None
    assert movimiento_caja.tipo == 'ingreso'
    assert movimiento_caja.concepto == 'venta'
    assert movimiento_caja.forma_pago == 'efectivo'


def test_convertir_a_venta_sin_caja_abierta(app):
    usuario = _crear_usuario()
    producto = _crear_producto('PRD-SIN-CAJA')
    db.session.add_all([usuario, producto])
    db.session.commit()

    items = [
        {'producto_id': producto.id, 'cantidad': Decimal('1.000'), 'precio_unitario': Decimal('10.00')},
    ]
    presupuesto = crear_presupuesto(items, usuario_id=usuario.id)
    presupuesto.estado = 'aceptado'
    db.session.commit()

    with pytest.raises(ValueError, match='No hay caja abierta'):
        convertir_a_venta(
            presupuesto,
            usuario_id=usuario.id,
            forma_pago='efectivo',
            caja_id=9999,
        )


def test_convertir_a_venta_stock_insuficiente(app):
    usuario = _crear_usuario()
    producto = _crear_producto('PRD-LOW', stock_actual='1.000')
    db.session.add_all([usuario, producto])
    db.session.commit()

    caja = _crear_caja(usuario.id)
    db.session.add(caja)
    db.session.commit()

    items = [
        {'producto_id': producto.id, 'cantidad': Decimal('2.000'), 'precio_unitario': Decimal('10.00')},
    ]
    presupuesto = crear_presupuesto(items, usuario_id=usuario.id)
    presupuesto.estado = 'aceptado'
    db.session.commit()

    with pytest.raises(ValueError, match='Stock insuficiente'):
        convertir_a_venta(
            presupuesto,
            usuario_id=usuario.id,
            forma_pago='efectivo',
            caja_id=caja.id,
        )


def test_convertir_a_venta_cuenta_corriente_sin_cliente(app):
    usuario = _crear_usuario()
    producto = _crear_producto('PRD-CC')
    db.session.add_all([usuario, producto])
    db.session.commit()

    caja = _crear_caja(usuario.id)
    db.session.add(caja)
    db.session.commit()

    items = [
        {'producto_id': producto.id, 'cantidad': Decimal('1.000'), 'precio_unitario': Decimal('10.00')},
    ]
    presupuesto = crear_presupuesto(items, usuario_id=usuario.id)
    presupuesto.estado = 'aceptado'
    db.session.commit()

    with pytest.raises(ValueError, match='Se requiere un cliente registrado'):
        convertir_a_venta(
            presupuesto,
            usuario_id=usuario.id,
            forma_pago='cuenta_corriente',
            caja_id=caja.id,
        )


def test_convertir_a_venta_credito_insuficiente(app):
    usuario = _crear_usuario()
    cliente = _crear_cliente(limite_credito='50.00', saldo='0.00')
    producto = _crear_producto('PRD-CC2', precio='40.00')
    db.session.add_all([usuario, cliente, producto])
    db.session.commit()

    caja = _crear_caja(usuario.id)
    db.session.add(caja)
    db.session.commit()

    items = [
        {'producto_id': producto.id, 'cantidad': Decimal('2.000'), 'precio_unitario': Decimal('40.00')},
    ]
    presupuesto = crear_presupuesto(
        items,
        usuario_id=usuario.id,
        cliente_id=cliente.id,
    )
    presupuesto.estado = 'aceptado'
    db.session.commit()

    with pytest.raises(ValueError, match='excedería su límite de crédito'):
        convertir_a_venta(
            presupuesto,
            usuario_id=usuario.id,
            forma_pago='cuenta_corriente',
            caja_id=caja.id,
        )
