"""Tests de saldo a favor y adelantos de clientes."""

import os

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite:///:memory:')

import json
from decimal import Decimal

import pytest

from app import create_app
from app.extensions import db as _db
from app.models import (
    Caja,
    Cliente,
    Empresa,
    MovimientoCaja,
    MovimientoCuentaCorriente,
    Producto,
    Usuario,
    Venta,
)

# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def app():
    """App con LOGIN_DISABLED=False para tests de rutas."""
    app = create_app('testing')
    app.config.update(
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_ENGINE_OPTIONS={},
        WTF_CSRF_ENABLED=False,
        TESTING=True,
        LOGIN_DISABLED=False,
    )
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def empresa(app):
    """Crea empresa de prueba."""
    emp = Empresa(nombre='Ferretería Test', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.flush()
    return emp


@pytest.fixture
def admin(empresa):
    """Crea usuario administrador."""
    usuario = Usuario(
        email='admin@test.com',
        nombre='Admin Test',
        rol='administrador',
        activo=True,
        empresa_id=empresa.id,
    )
    usuario.set_password('clave123')
    _db.session.add(usuario)
    _db.session.commit()
    return usuario


@pytest.fixture
def client(app):
    """Cliente HTTP de prueba."""
    return app.test_client()


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _login(client, email='admin@test.com', password='clave123'):
    """Helper: inicia sesión."""
    client.post('/auth/login', data={'email': email, 'password': password})


def _crear_cliente(
    empresa_id,
    saldo=Decimal('0'),
    saldo_a_favor=Decimal('0'),
    limite_credito=Decimal('1000.00'),
):
    """Crea un cliente de prueba con campos separados de deuda y saldo a favor."""
    cliente = Cliente(
        nombre='Cliente Prueba',
        limite_credito=limite_credito,
        saldo_cuenta_corriente=saldo,
        saldo_a_favor_monto=saldo_a_favor,
        activo=True,
        empresa_id=empresa_id,
    )
    _db.session.add(cliente)
    _db.session.flush()
    return cliente


def _crear_caja_abierta(empresa_id, usuario_id):
    """Crea una caja abierta."""
    caja = Caja(
        usuario_apertura_id=usuario_id,
        monto_inicial=Decimal('1000.00'),
        estado='abierta',
        empresa_id=empresa_id,
    )
    _db.session.add(caja)
    _db.session.flush()
    return caja


def _crear_producto(empresa_id):
    """Crea un producto de prueba con stock."""
    producto = Producto(
        codigo='PRD-001',
        nombre='Producto Test',
        unidad_medida='unidad',
        precio_costo=Decimal('50.00'),
        precio_venta=Decimal('100.00'),
        stock_actual=Decimal('100.000'),
        stock_minimo=Decimal('1.000'),
        activo=True,
        empresa_id=empresa_id,
    )
    _db.session.add(producto)
    _db.session.flush()
    return producto


# --------------------------------------------------------------------------
# Tests del modelo: propiedades de saldo a favor
# --------------------------------------------------------------------------


def test_tiene_saldo_a_favor_con_monto_positivo(app):
    """Cliente con saldo_a_favor_monto > 0 tiene saldo a favor."""
    emp = Empresa(nombre='Empresa Test', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.flush()
    cliente = _crear_cliente(emp.id, saldo_a_favor=Decimal('50.00'))
    _db.session.commit()

    assert cliente.tiene_saldo_a_favor is True


def test_tiene_saldo_a_favor_con_monto_cero(app):
    """Cliente con saldo_a_favor_monto = 0 NO tiene saldo a favor."""
    emp = Empresa(nombre='Empresa Test', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.flush()
    cliente = _crear_cliente(emp.id, saldo_a_favor=Decimal('0'))
    _db.session.commit()

    assert cliente.tiene_saldo_a_favor is False


def test_saldo_a_favor_retorna_monto(app):
    """Propiedad saldo_a_favor retorna el valor de saldo_a_favor_monto."""
    emp = Empresa(nombre='Empresa Test', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.flush()
    cliente = _crear_cliente(emp.id, saldo_a_favor=Decimal('150.75'))
    _db.session.commit()

    assert cliente.saldo_a_favor == Decimal('150.75')


def test_saldo_a_favor_retorna_cero_si_no_tiene(app):
    """Propiedad saldo_a_favor retorna 0 si no tiene saldo a favor."""
    emp = Empresa(nombre='Empresa Test', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.flush()
    cliente = _crear_cliente(emp.id, saldo=Decimal('200.00'))
    _db.session.commit()

    assert cliente.saldo_a_favor == Decimal('0')


def test_cliente_puede_tener_deuda_y_saldo_a_favor(app):
    """Un cliente puede tener deuda y saldo a favor simultaneamente."""
    emp = Empresa(nombre='Empresa Test', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.flush()
    cliente = _crear_cliente(emp.id, saldo=Decimal('300.00'), saldo_a_favor=Decimal('100.00'))
    _db.session.commit()

    assert cliente.tiene_deuda is True
    assert cliente.tiene_saldo_a_favor is True
    assert cliente.saldo_cuenta_corriente == Decimal('300.00')
    assert cliente.saldo_a_favor == Decimal('100.00')


# --------------------------------------------------------------------------
# Tests del modelo: actualizar_saldo_favor
# --------------------------------------------------------------------------


def test_actualizar_saldo_favor_adelanto(app):
    """Adelanto aumenta saldo a favor."""
    emp = Empresa(nombre='Empresa Test', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.flush()
    cliente = _crear_cliente(emp.id)
    _db.session.commit()

    anterior, posterior = cliente.actualizar_saldo_favor(Decimal('500'), 'adelanto')
    assert anterior == Decimal('0')
    assert posterior == Decimal('500')
    assert cliente.saldo_a_favor_monto == Decimal('500')


def test_actualizar_saldo_favor_cargo(app):
    """Cargo consume saldo a favor."""
    emp = Empresa(nombre='Empresa Test', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.flush()
    cliente = _crear_cliente(emp.id, saldo_a_favor=Decimal('500'))
    _db.session.commit()

    anterior, posterior = cliente.actualizar_saldo_favor(Decimal('200'), 'cargo')
    assert anterior == Decimal('500')
    assert posterior == Decimal('300')
    assert cliente.saldo_a_favor_monto == Decimal('300')


def test_actualizar_saldo_favor_no_baja_de_cero(app):
    """Saldo a favor no puede bajar de cero."""
    emp = Empresa(nombre='Empresa Test', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.flush()
    cliente = _crear_cliente(emp.id, saldo_a_favor=Decimal('100'))
    _db.session.commit()

    anterior, posterior = cliente.actualizar_saldo_favor(Decimal('200'), 'cargo')
    assert posterior == Decimal('0')
    assert cliente.saldo_a_favor_monto == Decimal('0')


# --------------------------------------------------------------------------
# Tests de registrar adelanto
# --------------------------------------------------------------------------


def test_registrar_adelanto_exitoso(app, empresa, admin, client):
    """Registrar adelanto aumenta saldo a favor y crea movimientos."""
    cliente = _crear_cliente(empresa.id, saldo=Decimal('0'))
    _crear_caja_abierta(empresa.id, admin.id)
    _db.session.commit()
    cliente_id = cliente.id

    _login(client)

    resp = client.post(
        f'/clientes/{cliente_id}/registrar-adelanto',
        data={
            'monto': '500.00',
            'forma_pago': 'efectivo',
            'motivo': 'Adelanto de prueba',
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200

    cliente_db = _db.session.get(Cliente, cliente_id)
    # Deuda se mantiene en 0, saldo a favor sube a 500
    assert cliente_db.saldo_cuenta_corriente == Decimal('0')
    assert cliente_db.saldo_a_favor_monto == Decimal('500.00')
    assert cliente_db.tiene_saldo_a_favor is True
    assert cliente_db.saldo_a_favor == Decimal('500.00')

    # Verificar movimiento de cuenta corriente
    mov_cc = MovimientoCuentaCorriente.query.filter_by(
        cliente_id=cliente_id, referencia_tipo='adelanto'
    ).first()
    assert mov_cc is not None
    assert mov_cc.tipo == 'pago'
    assert mov_cc.monto == Decimal('500.00')
    assert mov_cc.saldo_anterior == Decimal('0')
    assert mov_cc.saldo_posterior == Decimal('500.00')

    # Verificar movimiento de caja
    mov_caja = MovimientoCaja.query.filter_by(concepto='adelanto_cliente').first()
    assert mov_caja is not None
    assert mov_caja.tipo == 'ingreso'
    assert mov_caja.monto == Decimal('500.00')
    assert mov_caja.forma_pago == 'efectivo'


def test_registrar_adelanto_con_deuda_no_reduce_deuda(app, empresa, admin, client):
    """Adelanto NO reduce deuda, solo aumenta saldo a favor."""
    cliente = _crear_cliente(empresa.id, saldo=Decimal('200.00'))
    _crear_caja_abierta(empresa.id, admin.id)
    _db.session.commit()
    cliente_id = cliente.id

    _login(client)

    client.post(
        f'/clientes/{cliente_id}/registrar-adelanto',
        data={
            'monto': '350.00',
            'forma_pago': 'efectivo',
            'motivo': '',
        },
        follow_redirects=True,
    )

    cliente_db = _db.session.get(Cliente, cliente_id)
    # Deuda se mantiene, saldo a favor se crea
    assert cliente_db.saldo_cuenta_corriente == Decimal('200.00')
    assert cliente_db.saldo_a_favor_monto == Decimal('350.00')


def test_registrar_adelanto_sin_caja_abierta(app, empresa, admin, client):
    """Sin caja abierta, redirige a caja."""
    cliente = _crear_cliente(empresa.id, saldo=Decimal('0'))
    _db.session.commit()
    cliente_id = cliente.id

    _login(client)

    resp = client.post(
        f'/clientes/{cliente_id}/registrar-adelanto',
        data={
            'monto': '100.00',
            'forma_pago': 'efectivo',
            'motivo': '',
        },
    )

    # Debe redirigir a la página de caja
    assert resp.status_code == 302
    assert '/caja' in resp.headers.get('Location', '')

    # Saldo no debe cambiar
    cliente_db = _db.session.get(Cliente, cliente_id)
    assert cliente_db.saldo_cuenta_corriente == Decimal('0')
    assert cliente_db.saldo_a_favor_monto == Decimal('0')


# --------------------------------------------------------------------------
# Tests de anular adelanto
# --------------------------------------------------------------------------


def test_anular_adelanto_exitoso(app, empresa, admin, client):
    """Anular adelanto revierte el saldo a favor y crea movimientos."""
    cliente = _crear_cliente(empresa.id, saldo=Decimal('0'))
    _crear_caja_abierta(empresa.id, admin.id)
    _db.session.commit()
    cliente_id = cliente.id

    _login(client)

    # Registrar adelanto
    client.post(
        f'/clientes/{cliente_id}/registrar-adelanto',
        data={
            'monto': '300.00',
            'forma_pago': 'efectivo',
            'motivo': 'Adelanto para anular',
        },
        follow_redirects=True,
    )

    # Verificar que se creó el adelanto
    mov_adelanto = MovimientoCuentaCorriente.query.filter_by(
        cliente_id=cliente_id, referencia_tipo='adelanto'
    ).first()
    assert mov_adelanto is not None
    movimiento_id = mov_adelanto.id

    # Verificar saldo a favor antes de anular
    cliente_db = _db.session.get(Cliente, cliente_id)
    assert cliente_db.saldo_a_favor_monto == Decimal('300.00')

    # Anular adelanto
    resp = client.post(
        f'/clientes/{cliente_id}/anular-adelanto/{movimiento_id}',
        follow_redirects=True,
    )

    assert resp.status_code == 200

    cliente_db = _db.session.get(Cliente, cliente_id)
    # Saldo a favor vuelve a 0
    assert cliente_db.saldo_a_favor_monto == Decimal('0')
    # Deuda se mantiene en 0
    assert cliente_db.saldo_cuenta_corriente == Decimal('0')

    # Verificar movimiento de anulación
    mov_anulacion = MovimientoCuentaCorriente.query.filter_by(
        referencia_tipo='anulacion_adelanto',
        referencia_id=movimiento_id,
    ).first()
    assert mov_anulacion is not None
    assert mov_anulacion.tipo == 'cargo'
    assert mov_anulacion.monto == Decimal('300.00')

    # Verificar egreso en caja
    mov_caja_egreso = MovimientoCaja.query.filter_by(
        tipo='egreso', concepto='adelanto_cliente'
    ).first()
    assert mov_caja_egreso is not None
    assert mov_caja_egreso.monto == Decimal('300.00')


def test_anular_adelanto_doble_bloqueado(app, empresa, admin, client):
    """No se puede anular un adelanto dos veces."""
    cliente = _crear_cliente(empresa.id, saldo=Decimal('0'))
    _crear_caja_abierta(empresa.id, admin.id)
    _db.session.commit()
    cliente_id = cliente.id

    _login(client)

    # Registrar adelanto
    client.post(
        f'/clientes/{cliente_id}/registrar-adelanto',
        data={
            'monto': '200.00',
            'forma_pago': 'efectivo',
            'motivo': '',
        },
        follow_redirects=True,
    )

    mov_adelanto = MovimientoCuentaCorriente.query.filter_by(
        cliente_id=cliente_id, referencia_tipo='adelanto'
    ).first()
    movimiento_id = mov_adelanto.id

    # Primera anulación: exitosa
    client.post(
        f'/clientes/{cliente_id}/anular-adelanto/{movimiento_id}',
        follow_redirects=True,
    )

    # Segunda anulación: bloqueada
    resp = client.post(
        f'/clientes/{cliente_id}/anular-adelanto/{movimiento_id}',
        follow_redirects=True,
    )

    assert resp.status_code == 200

    # Solo debe haber UNA anulación
    anulaciones = MovimientoCuentaCorriente.query.filter_by(
        referencia_tipo='anulacion_adelanto',
        referencia_id=movimiento_id,
    ).all()
    assert len(anulaciones) == 1

    # Saldo a favor debe quedar en 0 (no negativo)
    cliente_db = _db.session.get(Cliente, cliente_id)
    assert cliente_db.saldo_a_favor_monto == Decimal('0')
    assert cliente_db.saldo_cuenta_corriente == Decimal('0')


# --------------------------------------------------------------------------
# Tests de consumo de saldo a favor en ventas
# --------------------------------------------------------------------------


def _crear_venta_cc_con_saldo_favor(client, cliente_id, producto_id, monto_saldo_favor, cantidad=1):
    """Helper: crea una venta a cuenta corriente consumiendo saldo a favor."""
    items = [
        {
            'producto_id': producto_id,
            'cantidad': str(cantidad),
            'precio_unitario': '100.00',
            'descuento_porcentaje': '0',
        }
    ]
    return client.post(
        '/ventas/punto-de-venta',
        data={
            'cliente_id': str(cliente_id),
            'forma_pago': 'cuenta_corriente',
            'descuento_porcentaje': '0',
            'items_json': json.dumps(items),
            'monto_saldo_favor': str(monto_saldo_favor),
        },
        follow_redirects=True,
    )


def test_consumo_saldo_favor_en_venta_cc(app, empresa, admin, client):
    """Venta CC consume saldo a favor del campo saldo_a_favor_monto."""
    cliente = _crear_cliente(empresa.id, saldo=Decimal('0'), saldo_a_favor=Decimal('500.00'))
    _crear_caja_abierta(empresa.id, admin.id)
    producto = _crear_producto(empresa.id)
    _db.session.commit()

    cliente_id = cliente.id
    producto_id = producto.id

    _login(client)

    # Venta de $100 consumiendo $100 del saldo a favor
    _crear_venta_cc_con_saldo_favor(
        client,
        cliente_id,
        producto_id,
        monto_saldo_favor='100.00',
    )

    cliente_db = _db.session.get(Cliente, cliente_id)
    # Saldo a favor: 500 - 100 = 400
    assert cliente_db.saldo_a_favor_monto == Decimal('400.00')
    # Deuda: 0 (todo cubierto por saldo a favor)
    assert cliente_db.saldo_cuenta_corriente == Decimal('0')

    # Verificar movimiento de consumo de saldo a favor
    mov_consumo = MovimientoCuentaCorriente.query.filter_by(
        cliente_id=cliente_id,
        referencia_tipo='consumo_saldo_favor',
    ).first()
    assert mov_consumo is not None
    assert mov_consumo.tipo == 'cargo'
    assert mov_consumo.monto == Decimal('100.00')

    # No debe haber cargo adicional a CC (porque el total fue cubierto
    # por el saldo a favor)
    mov_venta_cc = MovimientoCuentaCorriente.query.filter_by(
        cliente_id=cliente_id,
        referencia_tipo='venta',
    ).first()
    assert mov_venta_cc is None


def test_consumo_parcial_saldo_favor(app, empresa, admin, client):
    """Consumo parcial: parte con saldo a favor, parte carga a CC."""
    cliente = _crear_cliente(empresa.id, saldo=Decimal('0'), saldo_a_favor=Decimal('30.00'))
    _crear_caja_abierta(empresa.id, admin.id)
    producto = _crear_producto(empresa.id)
    _db.session.commit()

    cliente_id = cliente.id
    producto_id = producto.id

    _login(client)

    # Venta de $100, consumir $30 del saldo a favor, $70 a CC
    _crear_venta_cc_con_saldo_favor(
        client,
        cliente_id,
        producto_id,
        monto_saldo_favor='30.00',
    )

    cliente_db = _db.session.get(Cliente, cliente_id)
    # Saldo a favor: 30 - 30 = 0
    assert cliente_db.saldo_a_favor_monto == Decimal('0')
    # Deuda: 0 + 70 = 70
    assert cliente_db.saldo_cuenta_corriente == Decimal('70.00')

    # Verificar movimiento de consumo
    mov_consumo = MovimientoCuentaCorriente.query.filter_by(
        cliente_id=cliente_id,
        referencia_tipo='consumo_saldo_favor',
    ).first()
    assert mov_consumo is not None
    assert mov_consumo.monto == Decimal('30.00')

    # Verificar cargo remanente a CC
    mov_venta = MovimientoCuentaCorriente.query.filter_by(
        cliente_id=cliente_id,
        referencia_tipo='venta',
    ).first()
    assert mov_venta is not None
    assert mov_venta.monto == Decimal('70.00')


# --------------------------------------------------------------------------
# Test CRITICO: cargo CC NO consume saldo a favor
# --------------------------------------------------------------------------


def test_cargo_cc_no_consume_saldo_a_favor(app, empresa, admin, client):
    """Una venta a CC sin consumir saldo NO toca el saldo a favor."""
    cliente = _crear_cliente(empresa.id, saldo=Decimal('0'), saldo_a_favor=Decimal('5000.00'))
    _crear_caja_abierta(empresa.id, admin.id)
    producto = _crear_producto(empresa.id)
    _db.session.commit()

    cliente_id = cliente.id
    producto_id = producto.id

    _login(client)

    # Venta de $100 a CC, SIN consumir saldo a favor (monto_saldo_favor=0)
    items = [
        {
            'producto_id': producto_id,
            'cantidad': '3',
            'precio_unitario': '100.00',
            'descuento_porcentaje': '0',
        }
    ]
    client.post(
        '/ventas/punto-de-venta',
        data={
            'cliente_id': str(cliente_id),
            'forma_pago': 'cuenta_corriente',
            'descuento_porcentaje': '0',
            'items_json': json.dumps(items),
            'monto_saldo_favor': '0',
        },
        follow_redirects=True,
    )

    cliente_db = _db.session.get(Cliente, cliente_id)
    # Deuda: 0 + 300 = 300
    assert cliente_db.saldo_cuenta_corriente == Decimal('300.00')
    # Saldo a favor: 5000, NO cambió
    assert cliente_db.saldo_a_favor_monto == Decimal('5000.00')


# --------------------------------------------------------------------------
# Test de anulación de venta que consumió saldo a favor
# --------------------------------------------------------------------------


def test_anular_venta_restaura_saldo_favor(app, empresa, admin, client):
    """Anular venta con consumo de saldo a favor restaura el saldo."""
    cliente = _crear_cliente(empresa.id, saldo=Decimal('0'), saldo_a_favor=Decimal('200.00'))
    _crear_caja_abierta(empresa.id, admin.id)
    producto = _crear_producto(empresa.id)
    _db.session.commit()

    cliente_id = cliente.id
    producto_id = producto.id

    _login(client)

    # Venta de $100, consumir $100 del saldo a favor
    _crear_venta_cc_con_saldo_favor(
        client,
        cliente_id,
        producto_id,
        monto_saldo_favor='100.00',
    )

    cliente_db = _db.session.get(Cliente, cliente_id)
    # Saldo a favor: 200 - 100 = 100
    assert cliente_db.saldo_a_favor_monto == Decimal('100.00')
    # Deuda: 0 (todo cubierto por saldo a favor)
    assert cliente_db.saldo_cuenta_corriente == Decimal('0')

    # Obtener la venta creada
    venta = Venta.query.filter_by(empresa_id=empresa.id).first()
    assert venta is not None
    venta_id = venta.id

    # Anular la venta
    resp = client.post(
        f'/ventas/{venta_id}/anular',
        data={'motivo': 'Test de anulación'},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # El saldo a favor debe restaurarse a 200 (original)
    cliente_db = _db.session.get(Cliente, cliente_id)
    assert cliente_db.saldo_a_favor_monto == Decimal('200.00')
    # Deuda: 0
    assert cliente_db.saldo_cuenta_corriente == Decimal('0')

    # Verificar movimiento de reversión del consumo
    mov_reversion = MovimientoCuentaCorriente.query.filter_by(
        referencia_tipo='anul_consumo_saldo',
        referencia_id=venta_id,
    ).first()
    assert mov_reversion is not None
    assert mov_reversion.tipo == 'pago'
    assert mov_reversion.monto == Decimal('100.00')

    # Verificar que la venta quedó anulada
    venta_db = _db.session.get(Venta, venta_id)
    assert venta_db.estado == 'anulada'


# --------------------------------------------------------------------------
# Test de vista de clientes con saldo a favor
# --------------------------------------------------------------------------


def test_vista_con_saldo_a_favor(app, empresa, admin, client):
    """La vista con-saldo-a-favor muestra clientes con saldo_a_favor_monto > 0."""
    # Cliente con saldo a favor
    cliente_favor = Cliente(
        nombre='Con Saldo',
        saldo_cuenta_corriente=Decimal('0'),
        saldo_a_favor_monto=Decimal('500.00'),
        activo=True,
        empresa_id=empresa.id,
    )
    # Cliente con deuda (no debería aparecer)
    cliente_deuda = Cliente(
        nombre='Con Deuda',
        saldo_cuenta_corriente=Decimal('300.00'),
        saldo_a_favor_monto=Decimal('0'),
        activo=True,
        empresa_id=empresa.id,
    )
    # Cliente con saldo cero (no debería aparecer)
    cliente_cero = Cliente(
        nombre='Sin Saldo',
        saldo_cuenta_corriente=Decimal('0'),
        saldo_a_favor_monto=Decimal('0'),
        activo=True,
        empresa_id=empresa.id,
    )
    _db.session.add_all([cliente_favor, cliente_deuda, cliente_cero])
    _db.session.commit()

    _login(client)

    resp = client.get('/clientes/con-saldo-a-favor')
    assert resp.status_code == 200

    html = resp.data.decode('utf-8')
    assert 'Con Saldo' in html
    assert 'Con Deuda' not in html
    assert 'Sin Saldo' not in html
