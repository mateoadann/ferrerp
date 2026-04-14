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
def client(app):
    """Cliente HTTP de prueba."""
    return app.test_client()


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _crear_empresa():
    """Crea una empresa de prueba activa y aprobada."""
    empresa = Empresa(nombre='Ferretería Test', activa=True, aprobada=True)
    _db.session.add(empresa)
    _db.session.flush()
    return empresa


def _crear_usuario(empresa_id, rol='administrador'):
    """Crea un usuario de prueba."""
    usuario = Usuario(
        email='admin@ferrerp.test',
        nombre='Admin Test',
        rol=rol,
        activo=True,
        empresa_id=empresa_id,
    )
    usuario.set_password('clave123')
    _db.session.add(usuario)
    _db.session.flush()
    return usuario


def _crear_cliente(empresa_id, saldo=Decimal('0'), limite_credito=Decimal('1000.00')):
    """Crea un cliente de prueba."""
    cliente = Cliente(
        nombre='Cliente Prueba',
        limite_credito=limite_credito,
        saldo_cuenta_corriente=saldo,
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


def _login(client, email='admin@ferrerp.test', password='clave123'):
    """Helper: inicia sesión."""
    client.post('/auth/login', data={'email': email, 'password': password})


def _setup_completo(con_caja=True, saldo_cliente=Decimal('0')):
    """Crea empresa + usuario + cliente + caja (opcional). Retorna tupla."""
    empresa = _crear_empresa()
    usuario = _crear_usuario(empresa.id)
    cliente = _crear_cliente(empresa.id, saldo=saldo_cliente)
    caja = _crear_caja_abierta(empresa.id, usuario.id) if con_caja else None
    _db.session.commit()
    return empresa, usuario, cliente, caja


# --------------------------------------------------------------------------
# Tests del modelo: propiedades de saldo a favor
# --------------------------------------------------------------------------


def test_tiene_saldo_a_favor_con_saldo_negativo(app):
    """Cliente con saldo negativo tiene saldo a favor."""
    empresa = _crear_empresa()
    cliente = _crear_cliente(empresa.id, saldo=Decimal('-50.00'))
    _db.session.commit()

    assert cliente.tiene_saldo_a_favor is True


def test_tiene_saldo_a_favor_con_saldo_cero(app):
    """Cliente con saldo cero NO tiene saldo a favor."""
    empresa = _crear_empresa()
    cliente = _crear_cliente(empresa.id, saldo=Decimal('0'))
    _db.session.commit()

    assert cliente.tiene_saldo_a_favor is False


def test_saldo_a_favor_retorna_valor_absoluto(app):
    """Propiedad saldo_a_favor retorna el valor absoluto del saldo negativo."""
    empresa = _crear_empresa()
    cliente = _crear_cliente(empresa.id, saldo=Decimal('-150.75'))
    _db.session.commit()

    assert cliente.saldo_a_favor == Decimal('150.75')


def test_saldo_a_favor_retorna_cero_si_positivo(app):
    """Propiedad saldo_a_favor retorna 0 si el cliente tiene deuda."""
    empresa = _crear_empresa()
    cliente = _crear_cliente(empresa.id, saldo=Decimal('200.00'))
    _db.session.commit()

    assert cliente.saldo_a_favor == Decimal('0')


# --------------------------------------------------------------------------
# Tests de registrar adelanto
# --------------------------------------------------------------------------


def test_registrar_adelanto_exitoso(client, app):
    """Registrar adelanto reduce saldo y crea movimientos."""
    with app.app_context():
        empresa, usuario, cliente, caja = _setup_completo(saldo_cliente=Decimal('0'))
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
        assert cliente_db.saldo_cuenta_corriente == Decimal('-500.00')
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
        assert mov_cc.saldo_posterior == Decimal('-500.00')

        # Verificar movimiento de caja
        mov_caja = MovimientoCaja.query.filter_by(concepto='adelanto_cliente').first()
        assert mov_caja is not None
        assert mov_caja.tipo == 'ingreso'
        assert mov_caja.monto == Decimal('500.00')
        assert mov_caja.forma_pago == 'efectivo'


def test_registrar_adelanto_reduce_deuda_y_genera_saldo(client, app):
    """Adelanto mayor a la deuda genera saldo a favor."""
    with app.app_context():
        empresa, usuario, cliente, caja = _setup_completo(saldo_cliente=Decimal('200.00'))
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
        # 200 - 350 = -150 (saldo a favor)
        assert cliente_db.saldo_cuenta_corriente == Decimal('-150.00')
        assert cliente_db.tiene_saldo_a_favor is True
        assert cliente_db.saldo_a_favor == Decimal('150.00')


def test_registrar_adelanto_sin_caja_abierta(client, app):
    """Sin caja abierta, redirige a caja."""
    with app.app_context():
        empresa, usuario, cliente, _ = _setup_completo(con_caja=False)
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


# --------------------------------------------------------------------------
# Tests de anular adelanto
# --------------------------------------------------------------------------


def test_anular_adelanto_exitoso(client, app):
    """Anular adelanto revierte el saldo y crea movimientos."""
    with app.app_context():
        empresa, usuario, cliente, caja = _setup_completo(saldo_cliente=Decimal('0'))
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

        # Anular adelanto
        resp = client.post(
            f'/clientes/{cliente_id}/anular-adelanto/{movimiento_id}',
            follow_redirects=True,
        )

        assert resp.status_code == 200

        cliente_db = _db.session.get(Cliente, cliente_id)
        # Saldo vuelve a 0: -300 + 300 = 0
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


def test_anular_adelanto_doble_bloqueado(client, app):
    """No se puede anular un adelanto dos veces."""
    with app.app_context():
        empresa, usuario, cliente, caja = _setup_completo(saldo_cliente=Decimal('0'))
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

        # Saldo debe quedar en 0 (no en +200)
        cliente_db = _db.session.get(Cliente, cliente_id)
        assert cliente_db.saldo_cuenta_corriente == Decimal('0')


# --------------------------------------------------------------------------
# Tests de consumo de saldo a favor en ventas
# --------------------------------------------------------------------------


def _crear_venta_cc_con_saldo_favor(
    client, app, cliente_id, producto_id, monto_saldo_favor, cantidad=1
):
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


def test_consumo_saldo_favor_en_venta_cc(client, app):
    """Venta CC consume saldo a favor completo del cliente."""
    with app.app_context():
        empresa, usuario, cliente, caja = _setup_completo(
            saldo_cliente=Decimal('-500.00')  # Saldo a favor de 500
        )
        producto = _crear_producto(empresa.id)
        _db.session.commit()

        cliente_id = cliente.id
        producto_id = producto.id
        _login(client)

        # Venta de $100 consumiendo $100 del saldo a favor
        _crear_venta_cc_con_saldo_favor(
            client,
            app,
            cliente_id,
            producto_id,
            monto_saldo_favor='100.00',
        )

        cliente_db = _db.session.get(Cliente, cliente_id)
        # -500 + 100 (consumo) = -400 (no se carga nada extra a CC)
        assert cliente_db.saldo_cuenta_corriente == Decimal('-400.00')

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


def test_consumo_parcial_saldo_favor(client, app):
    """Consumo parcial: parte con saldo a favor, parte carga a CC."""
    with app.app_context():
        empresa, usuario, cliente, caja = _setup_completo(
            saldo_cliente=Decimal('-30.00')  # Saldo a favor de 30
        )
        producto = _crear_producto(empresa.id)
        _db.session.commit()

        cliente_id = cliente.id
        producto_id = producto.id
        _login(client)

        # Venta de $100, consumir $30 del saldo a favor, $70 a CC
        _crear_venta_cc_con_saldo_favor(
            client,
            app,
            cliente_id,
            producto_id,
            monto_saldo_favor='30.00',
        )

        cliente_db = _db.session.get(Cliente, cliente_id)
        # -30 + 30 (consumo) + 70 (cargo CC) = 70
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
# Test de anulación de venta que consumió saldo a favor
# --------------------------------------------------------------------------


def test_anular_venta_restaura_saldo_favor(client, app):
    """Anular venta con consumo de saldo a favor restaura el saldo."""
    with app.app_context():
        empresa, usuario, cliente, caja = _setup_completo(
            saldo_cliente=Decimal('-200.00')  # Saldo a favor de 200
        )
        producto = _crear_producto(empresa.id)
        _db.session.commit()

        cliente_id = cliente.id
        producto_id = producto.id
        _login(client)

        # Venta de $100, consumir $100 del saldo a favor
        _crear_venta_cc_con_saldo_favor(
            client,
            app,
            cliente_id,
            producto_id,
            monto_saldo_favor='100.00',
        )

        cliente_db = _db.session.get(Cliente, cliente_id)
        # -200 + 100 (consumo) = -100
        assert cliente_db.saldo_cuenta_corriente == Decimal('-100.00')

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

        # El saldo debe restaurarse a -200 (saldo a favor original)
        cliente_db = _db.session.get(Cliente, cliente_id)
        assert cliente_db.saldo_cuenta_corriente == Decimal('-200.00')

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


def test_vista_con_saldo_a_favor(client, app):
    """La vista con-saldo-a-favor muestra clientes con saldo negativo."""
    with app.app_context():
        empresa = _crear_empresa()
        _crear_usuario(empresa.id)

        # Cliente con saldo a favor
        cliente_favor = Cliente(
            nombre='Con Saldo',
            saldo_cuenta_corriente=Decimal('-500.00'),
            activo=True,
            empresa_id=empresa.id,
        )
        # Cliente con deuda (no debería aparecer)
        cliente_deuda = Cliente(
            nombre='Con Deuda',
            saldo_cuenta_corriente=Decimal('300.00'),
            activo=True,
            empresa_id=empresa.id,
        )
        # Cliente con saldo cero (no debería aparecer)
        cliente_cero = Cliente(
            nombre='Sin Saldo',
            saldo_cuenta_corriente=Decimal('0'),
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
