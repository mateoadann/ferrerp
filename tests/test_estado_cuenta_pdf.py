"""Tests para el endpoint de Estado de Cuenta PDF.

Verifica generacion de PDF, manejo de clientes sin movimientos,
aislamiento multi-tenant y requerimiento de login.
"""

import os

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite:///:memory:')

from decimal import Decimal
from unittest.mock import patch

import pytest
from flask import Blueprint
from flask_login import login_user

from app import create_app
from app.extensions import db as _db
from app.models import (
    Cliente,
    Empresa,
    MovimientoCuentaCorriente,
    Producto,
    Usuario,
    Venta,
    VentaDetalle,
)

# ─── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def app():
    """Crea la app con LOGIN_DISABLED=False para probar autenticacion."""
    app = create_app('testing')
    app.config.update(
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_ENGINE_OPTIONS={},
        WTF_CSRF_ENABLED=False,
        TESTING=True,
        LOGIN_DISABLED=False,
    )

    test_bp = Blueprint('test_pdf_login', __name__)

    @test_bp.route('/test-login/<int:user_id>')
    def test_login(user_id):
        usuario = _db.session.get(Usuario, user_id)
        login_user(usuario)
        return 'logged-in'

    with app.app_context():
        app.register_blueprint(test_bp)
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
def logged_client(app, usuario):
    client = app.test_client()
    client.get(f'/test-login/{usuario.id}')
    return client


# ─── Helpers ─────────────────────────────────────────────────────────


def _crear_cliente(empresa, nombre='Cliente CC'):
    cliente = Cliente(
        nombre=nombre,
        limite_credito=Decimal('10000.00'),
        saldo_cuenta_corriente=Decimal('500.00'),
        activo=True,
        empresa_id=empresa.id,
    )
    _db.session.add(cliente)
    _db.session.flush()
    return cliente


def _crear_producto(empresa, codigo='PRD-001', nombre='Martillo'):
    prod = Producto(
        codigo=codigo,
        nombre=nombre,
        unidad_medida='unidad',
        precio_costo=Decimal('100.00'),
        precio_venta=Decimal('150.00'),
        stock_actual=Decimal('10.000'),
        stock_minimo=Decimal('5.000'),
        activo=True,
        empresa_id=empresa.id,
    )
    _db.session.add(prod)
    _db.session.flush()
    return prod


def _crear_venta_cc(empresa, usuario, cliente, producto, total=Decimal('500.00')):
    """Crea una venta CC con un detalle y un movimiento de cargo."""
    venta = Venta(
        numero=1,
        total=total,
        forma_pago='cuenta_corriente',
        estado='completada',
        usuario_id=usuario.id,
        cliente_id=cliente.id,
        empresa_id=empresa.id,
    )
    _db.session.add(venta)
    _db.session.flush()

    detalle = VentaDetalle(
        venta_id=venta.id,
        producto_id=producto.id,
        cantidad=Decimal('2.000'),
        precio_unitario=Decimal('250.00'),
        subtotal=total,
    )
    _db.session.add(detalle)

    movimiento = MovimientoCuentaCorriente(
        cliente_id=cliente.id,
        tipo='cargo',
        monto=total,
        saldo_anterior=Decimal('0.00'),
        saldo_posterior=total,
        referencia_tipo='venta',
        referencia_id=venta.id,
        descripcion='Venta a cuenta corriente',
        usuario_id=usuario.id,
        empresa_id=empresa.id,
    )
    _db.session.add(movimiento)
    _db.session.flush()
    return venta


# ─── Tests ───────────────────────────────────────────────────────────


def test_estado_cuenta_pdf_genera_pdf(logged_client, empresa, usuario):
    """PDF generado correctamente para cliente con movimientos CC."""
    cliente = _crear_cliente(empresa)
    producto = _crear_producto(empresa)
    _crear_venta_cc(empresa, usuario, cliente, producto)
    _db.session.commit()

    # Mock WeasyPrint para evitar dependencia de sistema en tests
    fake_pdf = b'%PDF-1.4 fake pdf content'
    with patch('app.services.cuenta_corriente_service.HTML') as mock_html_cls:
        mock_html_cls.return_value.write_pdf.return_value = fake_pdf
        resp = logged_client.get(f'/clientes/{cliente.id}/estado-cuenta-pdf')

    assert resp.status_code == 200
    assert resp.content_type == 'application/pdf'
    assert resp.data == fake_pdf


def test_estado_cuenta_pdf_sin_movimientos(logged_client, empresa, usuario):
    """PDF valido incluso para cliente sin movimientos ni ventas CC."""
    cliente = _crear_cliente(empresa)
    cliente.saldo_cuenta_corriente = Decimal('0.00')
    _db.session.commit()

    fake_pdf = b'%PDF-1.4 empty'
    with patch('app.services.cuenta_corriente_service.HTML') as mock_html_cls:
        mock_html_cls.return_value.write_pdf.return_value = fake_pdf
        resp = logged_client.get(f'/clientes/{cliente.id}/estado-cuenta-pdf')

    assert resp.status_code == 200
    assert resp.content_type == 'application/pdf'


def test_estado_cuenta_pdf_cliente_otra_empresa(logged_client, empresa, usuario):
    """Debe retornar 404 para cliente de otra empresa."""
    otra_empresa = Empresa(nombre='Otra Ferreteria', activa=True, aprobada=True)
    _db.session.add(otra_empresa)
    _db.session.flush()

    cliente_ajeno = Cliente(
        nombre='Cliente Ajeno',
        limite_credito=Decimal('5000.00'),
        saldo_cuenta_corriente=Decimal('0.00'),
        activo=True,
        empresa_id=otra_empresa.id,
    )
    _db.session.add(cliente_ajeno)
    _db.session.commit()

    resp = logged_client.get(f'/clientes/{cliente_ajeno.id}/estado-cuenta-pdf')
    assert resp.status_code == 404


def test_estado_cuenta_pdf_requiere_login(app, empresa):
    """Sin login, debe redirigir (302) al login."""
    cliente = _crear_cliente(empresa)
    _db.session.commit()

    client = app.test_client()
    resp = client.get(f'/clientes/{cliente.id}/estado-cuenta-pdf')
    # Flask-Login redirige a login cuando no hay sesion
    assert resp.status_code in (302, 401)
