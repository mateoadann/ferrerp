"""Tests de regresión para rutas HTMX con partials y links en movimientos de stock.

Estos tests verifican que las rutas que responden a peticiones HTMX (parciales)
devuelvan 200 y no 500 por templates faltantes o variables no pasadas.
También verifican que los movimientos de stock muestren links a ventas.
"""

import os

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite:///:memory:')

from decimal import Decimal

import pytest
from flask import Blueprint
from flask_login import login_user

from app import create_app
from app.extensions import db as _db
from app.models import (
    Cliente,
    Empresa,
    MovimientoStock,
    Producto,
    Usuario,
    Venta,
)


# ─── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def app():
    """Crea la app de prueba con LOGIN_DISABLED=False para simular sesión real."""
    app = create_app('testing')
    app.config.update(
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_ENGINE_OPTIONS={},
        WTF_CSRF_ENABLED=False,
        TESTING=True,
        LOGIN_DISABLED=False,
    )

    # Ruta auxiliar para login en tests
    test_bp = Blueprint('test_htmx_login', __name__)

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
    """Crea una empresa aprobada de prueba."""
    emp = Empresa(nombre='Ferretería Test', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.commit()
    return emp


@pytest.fixture
def usuario(empresa):
    """Crea un usuario administrador de prueba."""
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
    """Cliente HTTP con sesión autenticada."""
    client = app.test_client()
    client.get(f'/test-login/{usuario.id}')
    return client


# ─── Helpers ─────────────────────────────────────────────────────────


def _crear_producto(empresa, codigo='PRD-001', nombre='Martillo'):
    """Crea un producto de prueba."""
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


def _crear_venta(empresa, usuario):
    """Crea una venta mínima de prueba."""
    venta = Venta(
        numero=1,
        total=Decimal('150.00'),
        forma_pago='efectivo',
        estado='completada',
        usuario_id=usuario.id,
        empresa_id=empresa.id,
    )
    _db.session.add(venta)
    _db.session.flush()
    return venta


def _crear_movimiento(empresa, producto, usuario, referencia_tipo=None, referencia_id=None,
                       motivo=None):
    """Crea un movimiento de stock de prueba."""
    mov = MovimientoStock(
        producto_id=producto.id,
        tipo='venta',
        cantidad=Decimal('-1.000'),
        stock_anterior=Decimal('10.000'),
        stock_posterior=Decimal('9.000'),
        referencia_tipo=referencia_tipo,
        referencia_id=referencia_id,
        motivo=motivo,
        usuario_id=usuario.id,
        empresa_id=empresa.id,
    )
    _db.session.add(mov)
    _db.session.flush()
    return mov


# ─── Tests de búsqueda HTMX en listados ──────────────────────────────


HTMX_HEADERS = {'HX-Request': 'true'}


def test_htmx_busqueda_clientes_retorna_200(logged_client):
    """GET /clientes/?q=test con header HTMX debe devolver 200, no 500."""
    resp = logged_client.get('/clientes/?q=test', headers=HTMX_HEADERS)
    assert resp.status_code == 200


def test_htmx_busqueda_productos_retorna_200(logged_client):
    """GET /productos/?q=test con header HTMX debe devolver 200, no 500."""
    resp = logged_client.get('/productos/?q=test', headers=HTMX_HEADERS)
    assert resp.status_code == 200


def test_htmx_busqueda_presupuestos_retorna_200(logged_client):
    """GET /presupuestos/?q=test con header HTMX debe devolver 200, no 500."""
    resp = logged_client.get('/presupuestos/?q=test', headers=HTMX_HEADERS)
    assert resp.status_code == 200


def test_htmx_busqueda_proveedores_retorna_200(logged_client):
    """GET /proveedores/?q=test con header HTMX debe devolver 200.

    Esta ruta devolvía TemplateNotFound antes del fix porque faltaba
    el partial proveedores/_tabla.html.
    """
    resp = logged_client.get('/proveedores/?q=test', headers=HTMX_HEADERS)
    assert resp.status_code == 200


def test_htmx_busqueda_inventario_retorna_200(logged_client):
    """GET /inventario/?q=test con header HTMX debe devolver 200, no 500."""
    resp = logged_client.get('/inventario/?q=test', headers=HTMX_HEADERS)
    assert resp.status_code == 200


# ─── Tests de contenido en respuestas HTMX ────────────────────────────


def test_htmx_clientes_contiene_tabla(logged_client, empresa):
    """La respuesta HTMX de clientes debe contener estructura de tabla."""
    # Crear un cliente para que la tabla tenga contenido
    cli = Cliente(
        nombre='Juan Pérez',
        activo=True,
        empresa_id=empresa.id,
        limite_credito=Decimal('1000'),
        saldo_cuenta_corriente=Decimal('0'),
    )
    _db.session.add(cli)
    _db.session.commit()

    resp = logged_client.get('/clientes/?q=Juan', headers=HTMX_HEADERS)
    html = resp.data.decode()
    assert resp.status_code == 200
    assert 'Juan Pérez' in html


# ─── Tests de links en movimientos de stock ───────────────────────────


def test_movimientos_muestra_link_a_venta(logged_client, empresa, usuario):
    """Movimiento con referencia_tipo='venta' debe mostrar link a la venta."""
    producto = _crear_producto(empresa)
    venta = _crear_venta(empresa, usuario)
    _crear_movimiento(
        empresa, producto, usuario,
        referencia_tipo='venta',
        referencia_id=venta.id,
    )
    _db.session.commit()

    resp = logged_client.get('/inventario/movimientos')
    html = resp.data.decode()
    assert resp.status_code == 200
    assert f'/ventas/{venta.id}' in html


def test_movimientos_muestra_link_anulacion_venta(logged_client, empresa, usuario):
    """Movimiento con referencia_tipo='anulacion_venta' debe mostrar link a la venta."""
    producto = _crear_producto(empresa)
    venta = _crear_venta(empresa, usuario)
    _crear_movimiento(
        empresa, producto, usuario,
        referencia_tipo='anulacion_venta',
        referencia_id=venta.id,
        motivo=f'Anulación de venta #{venta.id}',
    )
    _db.session.commit()

    resp = logged_client.get('/inventario/movimientos')
    html = resp.data.decode()
    assert resp.status_code == 200
    assert f'/ventas/{venta.id}' in html
