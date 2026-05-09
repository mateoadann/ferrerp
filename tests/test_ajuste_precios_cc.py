"""Tests para el algoritmo de ajuste de precios de cuenta corriente.

Verifica la regla de negocio critica: primer pago congela precio por venta,
el calculo de ajustes con descuentos globales, pagos divididos, y prevencion
de duplicados.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app import create_app
from app.extensions import db as _db
from app.models import (
    AjustePrecioCuentaCorriente,
    Categoria,
    Cliente,
    Empresa,
    MovimientoCuentaCorriente,
    Producto,
    Usuario,
    Venta,
    VentaDetalle,
    VentaPago,
)
from app.services.cuenta_corriente_service import (
    aplicar_ajustes_cc,
    calcular_ajustes_cc,
    venta_esta_congelada,
)

# ─── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def app():
    app = create_app('testing')
    app.config.update(
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_ENGINE_OPTIONS={},
        WTF_CSRF_ENABLED=False,
        TESTING=True,
        LOGIN_DISABLED=True,
    )

    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def empresa(app):
    emp = Empresa(nombre='Ferreteria Test', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.commit()
    return emp


@pytest.fixture
def usuario(empresa):
    u = Usuario(
        email='admin@test.com',
        nombre='Admin Test',
        rol='administrador',
        activo=True,
        empresa_id=empresa.id,
    )
    u.set_password('clave123')
    _db.session.add(u)
    _db.session.commit()
    return u


@pytest.fixture
def categoria(empresa):
    cat = Categoria(
        nombre='Herramientas',
        activa=True,
        empresa_id=empresa.id,
    )
    _db.session.add(cat)
    _db.session.commit()
    return cat


@pytest.fixture
def cliente(empresa):
    c = Cliente(
        nombre='Cliente CC',
        limite_credito=Decimal('50000.00'),
        saldo_cuenta_corriente=Decimal('0.00'),
        activo=True,
        empresa_id=empresa.id,
    )
    _db.session.add(c)
    _db.session.commit()
    return c


# ─── Helpers ─────────────────────────────────────────────────────────

FECHA_BASE = datetime(2026, 1, 1, 10, 0, 0)


def _crear_producto(empresa, categoria, codigo='PRD-001', precio=Decimal('100.00')):
    prod = Producto(
        codigo=codigo,
        nombre=f'Producto {codigo}',
        unidad_medida='unidad',
        precio_costo=Decimal('50.00'),
        precio_venta=precio,
        stock_actual=Decimal('10.000'),
        stock_minimo=Decimal('1.000'),
        activo=True,
        empresa_id=empresa.id,
        categoria_id=categoria.id,
    )
    _db.session.add(prod)
    _db.session.flush()
    return prod


def _crear_venta_cc(
    empresa,
    usuario,
    cliente,
    productos_cantidades,
    fecha=None,
    forma_pago='cuenta_corriente',
    descuento_porcentaje=Decimal('0'),
    pagos_dividido=None,
):
    """Crea una venta CC con detalles.

    Args:
        productos_cantidades: lista de (producto, cantidad, precio_unitario)
        pagos_dividido: si forma_pago='dividido', lista de (forma_pago, monto)
    """
    fecha = fecha or FECHA_BASE

    # Calcular total
    subtotal = Decimal('0')
    for _prod, cant, precio in productos_cantidades:
        subtotal += Decimal(str(cant)) * Decimal(str(precio))

    desc_monto = subtotal * descuento_porcentaje / Decimal('100')
    total = subtotal - desc_monto

    venta = Venta(
        numero=Venta.query.count() + 1,
        fecha=fecha,
        total=total,
        subtotal=subtotal,
        descuento_porcentaje=descuento_porcentaje,
        descuento_monto=desc_monto,
        forma_pago=forma_pago,
        estado='completada',
        usuario_id=usuario.id,
        cliente_id=cliente.id,
        empresa_id=empresa.id,
    )
    _db.session.add(venta)
    _db.session.flush()

    for prod, cant, precio in productos_cantidades:
        detalle = VentaDetalle(
            venta_id=venta.id,
            producto_id=prod.id,
            cantidad=Decimal(str(cant)),
            precio_unitario=Decimal(str(precio)),
            subtotal=Decimal(str(cant)) * Decimal(str(precio)),
        )
        _db.session.add(detalle)

    if forma_pago == 'dividido' and pagos_dividido:
        for fp, monto in pagos_dividido:
            pago = VentaPago(
                venta_id=venta.id,
                forma_pago=fp,
                monto=Decimal(str(monto)),
            )
            _db.session.add(pago)

    _db.session.flush()
    return venta


def _crear_pago_cc(empresa, usuario, cliente, fecha=None, monto=Decimal('100.00')):
    """Crea un movimiento de pago de cuenta corriente."""
    fecha = fecha or FECHA_BASE + timedelta(days=15)
    movimiento = MovimientoCuentaCorriente(
        cliente_id=cliente.id,
        tipo='pago',
        monto=monto,
        saldo_anterior=cliente.saldo_cuenta_corriente,
        saldo_posterior=cliente.saldo_cuenta_corriente - monto,
        referencia_tipo='pago',
        descripcion='Pago de cuenta corriente',
        usuario_id=usuario.id,
        empresa_id=empresa.id,
        created_at=fecha,
    )
    _db.session.add(movimiento)
    _db.session.flush()
    return movimiento


# ─── Tests de clasificacion congelada/viva ───────────────────────────


def test_venta_sin_pagos_esta_viva(app, empresa, usuario, cliente, categoria):
    """Venta CC sin pagos posteriores debe clasificarse como viva."""
    prod = _crear_producto(empresa, categoria)
    venta = _crear_venta_cc(
        empresa,
        usuario,
        cliente,
        [(prod, 2, Decimal('100.00'))],
        fecha=FECHA_BASE,
    )
    _db.session.commit()

    assert venta_esta_congelada(venta) is False


def test_venta_con_pago_posterior_esta_congelada(app, empresa, usuario, cliente, categoria):
    """Venta CC con pago posterior debe clasificarse como congelada."""
    prod = _crear_producto(empresa, categoria)
    venta = _crear_venta_cc(
        empresa,
        usuario,
        cliente,
        [(prod, 2, Decimal('100.00'))],
        fecha=FECHA_BASE,
    )
    # Pago 15 dias despues de la venta
    _crear_pago_cc(empresa, usuario, cliente, fecha=FECHA_BASE + timedelta(days=15))
    _db.session.commit()

    assert venta_esta_congelada(venta) is True


def test_venta_posterior_al_pago_esta_viva(app, empresa, usuario, cliente, categoria):
    """Venta CC creada DESPUES del ultimo pago debe clasificarse como viva."""
    prod = _crear_producto(empresa, categoria)

    # Primero un pago
    _crear_pago_cc(empresa, usuario, cliente, fecha=FECHA_BASE)

    # Luego una venta posterior al pago
    venta = _crear_venta_cc(
        empresa,
        usuario,
        cliente,
        [(prod, 2, Decimal('100.00'))],
        fecha=FECHA_BASE + timedelta(days=30),
    )
    _db.session.commit()

    assert venta_esta_congelada(venta) is False


# ─── Tests de calculo de ajustes ─────────────────────────────────────


def test_calcular_ajustes_venta_viva(app, empresa, usuario, cliente, categoria):
    """Venta viva con productos en categoria actualizada genera ajuste."""
    prod = _crear_producto(empresa, categoria, precio=Decimal('100.00'))
    _crear_venta_cc(
        empresa,
        usuario,
        cliente,
        [(prod, Decimal('2'), Decimal('100.00'))],
        fecha=FECHA_BASE,
    )
    _db.session.commit()

    ajustes = calcular_ajustes_cc([categoria.id], Decimal('10'), empresa.id)

    assert len(ajustes) == 1
    assert ajustes[0]['monto_ajuste'] == Decimal('20.00')


def test_calcular_ajustes_venta_congelada(app, empresa, usuario, cliente, categoria):
    """Venta congelada (con pago posterior) no genera ajuste."""
    prod = _crear_producto(empresa, categoria, precio=Decimal('100.00'))
    _crear_venta_cc(
        empresa,
        usuario,
        cliente,
        [(prod, Decimal('2'), Decimal('100.00'))],
        fecha=FECHA_BASE,
    )
    _crear_pago_cc(empresa, usuario, cliente, fecha=FECHA_BASE + timedelta(days=15))
    _db.session.commit()

    ajustes = calcular_ajustes_cc([categoria.id], Decimal('10'), empresa.id)

    assert len(ajustes) == 0


def test_calcular_ajustes_mixto(app, empresa, usuario, cliente, categoria):
    """Dos ventas: una congelada y una viva. Solo la viva genera ajuste."""
    prod = _crear_producto(empresa, categoria, precio=Decimal('100.00'))

    # Venta 1 en enero
    _crear_venta_cc(
        empresa,
        usuario,
        cliente,
        [(prod, Decimal('1'), Decimal('100.00'))],
        fecha=FECHA_BASE,
    )
    # Pago en enero 15 (congela venta 1)
    _crear_pago_cc(empresa, usuario, cliente, fecha=FECHA_BASE + timedelta(days=15))

    # Venta 2 en febrero (posterior al pago, esta viva)
    _crear_venta_cc(
        empresa,
        usuario,
        cliente,
        [(prod, Decimal('3'), Decimal('100.00'))],
        fecha=FECHA_BASE + timedelta(days=45),
    )
    _db.session.commit()

    ajustes = calcular_ajustes_cc([categoria.id], Decimal('10'), empresa.id)

    assert len(ajustes) == 1
    # Solo la venta 2: 3 * 100 * 10% = 30
    assert ajustes[0]['monto_ajuste'] == Decimal('30.00')


def test_calcular_ajustes_descuento_global(app, empresa, usuario, cliente, categoria):
    """Venta con descuento_porcentaje global: el ajuste se calcula post-descuento."""
    prod = _crear_producto(empresa, categoria, precio=Decimal('100.00'))
    _crear_venta_cc(
        empresa,
        usuario,
        cliente,
        [(prod, Decimal('2'), Decimal('100.00'))],
        fecha=FECHA_BASE,
        descuento_porcentaje=Decimal('10'),
    )
    _db.session.commit()

    # 2 * 100 = 200 bruto. Con 10% aumento: 2 * 110 = 220. Diff = 20.
    # Descuento global 10%: 20 * 0.9 = 18
    ajustes = calcular_ajustes_cc([categoria.id], Decimal('10'), empresa.id)

    assert len(ajustes) == 1
    assert ajustes[0]['monto_ajuste'] == Decimal('18.00')


def test_calcular_ajustes_pago_dividido(app, empresa, usuario, cliente, categoria):
    """Venta dividida: solo la porcion CC se ajusta."""
    prod = _crear_producto(empresa, categoria, precio=Decimal('100.00'))
    # Venta total 1000, CC 600, efectivo 400
    _crear_venta_cc(
        empresa,
        usuario,
        cliente,
        [(prod, Decimal('10'), Decimal('100.00'))],
        fecha=FECHA_BASE,
        forma_pago='dividido',
        pagos_dividido=[
            ('cuenta_corriente', Decimal('600.00')),
            ('efectivo', Decimal('400.00')),
        ],
    )
    _db.session.commit()

    # 10 * 100 = 1000, aumento 10%: 10 * 110 = 1100, diff = 100
    # ratio_cc = 600/1000 = 0.6 => ajuste = 100 * 0.6 = 60
    ajustes = calcular_ajustes_cc([categoria.id], Decimal('10'), empresa.id)

    assert len(ajustes) == 1
    assert ajustes[0]['monto_ajuste'] == Decimal('60.00')


def test_calcular_ajustes_sin_productos_afectados(app, empresa, usuario, cliente, categoria):
    """Productos no pertenecientes a las categorias actualizadas no generan ajuste."""
    otra_cat = Categoria(
        nombre='Pintura',
        activa=True,
        empresa_id=empresa.id,
    )
    _db.session.add(otra_cat)
    _db.session.flush()

    # Producto en otra categoria
    prod = _crear_producto(empresa, otra_cat, codigo='PRD-PINTURA', precio=Decimal('100.00'))
    _crear_venta_cc(
        empresa,
        usuario,
        cliente,
        [(prod, Decimal('5'), Decimal('100.00'))],
        fecha=FECHA_BASE,
    )
    _db.session.commit()

    # Buscar ajustes en la categoria 'Herramientas' (no contiene el producto)
    ajustes = calcular_ajustes_cc([categoria.id], Decimal('10'), empresa.id)

    assert len(ajustes) == 0


# ─── Tests de aplicacion de ajustes ──────────────────────────────────


def test_aplicar_ajustes_crea_movimiento_y_auditoria(app, empresa, usuario, cliente, categoria):
    """Aplicar ajustes crea MovimientoCuentaCorriente y AjustePrecioCuentaCorriente."""
    prod = _crear_producto(empresa, categoria, precio=Decimal('100.00'))
    _crear_venta_cc(
        empresa,
        usuario,
        cliente,
        [(prod, Decimal('2'), Decimal('100.00'))],
        fecha=FECHA_BASE,
    )
    _db.session.commit()

    ajustes = calcular_ajustes_cc([categoria.id], Decimal('10'), empresa.id)
    assert len(ajustes) == 1

    fecha_act = datetime(2026, 4, 14, 12, 0, 0)
    cantidad = aplicar_ajustes_cc(ajustes, usuario.id, fecha_act, Decimal('10'))
    _db.session.commit()

    assert cantidad == 1

    # Verificar movimiento CC creado
    movimientos = MovimientoCuentaCorriente.query.filter_by(
        cliente_id=cliente.id,
        referencia_tipo='ajuste_precio',
    ).all()
    assert len(movimientos) == 1
    assert movimientos[0].tipo == 'cargo'
    assert movimientos[0].monto == Decimal('20.00')

    # Verificar registro de auditoria
    auditorias = AjustePrecioCuentaCorriente.query.filter_by(
        cliente_id=cliente.id,
    ).all()
    assert len(auditorias) == 1
    assert auditorias[0].monto_ajuste == Decimal('20.00')
    assert auditorias[0].porcentaje_aplicado == Decimal('10')

    # Verificar que el saldo del cliente se actualizo
    _db.session.refresh(cliente)
    assert cliente.saldo_cuenta_corriente == Decimal('20.00')


def test_aplicar_ajustes_duplicado(app, empresa, usuario, cliente, categoria):
    """Ejecutar aplicar_ajustes_cc dos veces con misma fecha no duplica."""
    prod = _crear_producto(empresa, categoria, precio=Decimal('100.00'))
    _crear_venta_cc(
        empresa,
        usuario,
        cliente,
        [(prod, Decimal('2'), Decimal('100.00'))],
        fecha=FECHA_BASE,
    )
    _db.session.commit()

    fecha_act = datetime(2026, 4, 14, 12, 0, 0)

    # Primera aplicacion
    ajustes = calcular_ajustes_cc([categoria.id], Decimal('10'), empresa.id)
    cantidad_1 = aplicar_ajustes_cc(ajustes, usuario.id, fecha_act, Decimal('10'))
    _db.session.commit()

    assert cantidad_1 == 1

    # Segunda aplicacion con misma fecha — debe saltear
    ajustes_2 = calcular_ajustes_cc([categoria.id], Decimal('10'), empresa.id)
    # La venta sigue viva, pero ya fue ajustada para esta fecha
    if ajustes_2:
        cantidad_2 = aplicar_ajustes_cc(ajustes_2, usuario.id, fecha_act, Decimal('10'))
    else:
        cantidad_2 = 0
    _db.session.commit()

    assert cantidad_2 == 0

    # Solo 1 registro de auditoria
    total_auditorias = AjustePrecioCuentaCorriente.query.filter_by(
        cliente_id=cliente.id,
    ).count()
    assert total_auditorias == 1
