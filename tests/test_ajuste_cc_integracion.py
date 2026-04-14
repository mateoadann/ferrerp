"""Tests de integracion para el flujo de ajuste CC via actualizacion masiva.

Verifica los endpoints HTMX de preview-cc y la aplicacion completa
de la actualizacion masiva con y sin ajuste de cuenta corriente.
"""

import json
import os

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite:///:memory:')

from datetime import datetime
from decimal import Decimal

import pytest
from flask import Blueprint
from flask_login import login_user

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
)

# ─── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def app():
    """App con LOGIN_DISABLED=False para probar rutas protegidas."""
    app = create_app('testing')
    app.config.update(
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_ENGINE_OPTIONS={},
        WTF_CSRF_ENABLED=False,
        TESTING=True,
        LOGIN_DISABLED=False,
    )

    test_bp = Blueprint('test_cc_integ_login', __name__)

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

FECHA_BASE = datetime(2026, 1, 1, 10, 0, 0)


def _setup_datos(empresa, usuario):
    """Crea datos base: categoria, producto, cliente, venta CC."""
    cat = Categoria(
        nombre='Herramientas',
        activa=True,
        empresa_id=empresa.id,
    )
    _db.session.add(cat)
    _db.session.flush()

    prod = Producto(
        codigo='PRD-001',
        nombre='Martillo',
        unidad_medida='unidad',
        precio_costo=Decimal('50.00'),
        precio_venta=Decimal('100.00'),
        stock_actual=Decimal('10.000'),
        stock_minimo=Decimal('1.000'),
        activo=True,
        empresa_id=empresa.id,
        categoria_id=cat.id,
    )
    _db.session.add(prod)
    _db.session.flush()

    cliente = Cliente(
        nombre='Cliente CC Test',
        limite_credito=Decimal('50000.00'),
        saldo_cuenta_corriente=Decimal('200.00'),
        activo=True,
        empresa_id=empresa.id,
    )
    _db.session.add(cliente)
    _db.session.flush()

    venta = Venta(
        numero=1,
        fecha=FECHA_BASE,
        total=Decimal('200.00'),
        subtotal=Decimal('200.00'),
        descuento_porcentaje=Decimal('0'),
        descuento_monto=Decimal('0'),
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
        producto_id=prod.id,
        cantidad=Decimal('2.000'),
        precio_unitario=Decimal('100.00'),
        subtotal=Decimal('200.00'),
    )
    _db.session.add(detalle)
    _db.session.commit()

    return cat, prod, cliente, venta


# ─── Tests ───────────────────────────────────────────────────────────


def test_preview_cc_endpoint(logged_client, empresa, usuario):
    """POST a preview-cc con datos validos retorna HTML parcial con tabla."""
    cat, prod, cliente, venta = _setup_datos(empresa, usuario)

    resp = logged_client.post(
        '/productos/actualizacion-masiva/preview-cc',
        data={
            'categorias_ids': json.dumps([cat.id]),
            'porcentaje': '10',
        },
    )

    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    # El parcial debe contener el nombre del cliente afectado
    assert 'Cliente CC Test' in html


def test_aplicar_actualizacion_con_ajuste_cc(logged_client, empresa, usuario):
    """Flujo completo: actualizar precios + ajustar deudas CC."""
    cat, prod, cliente, venta = _setup_datos(empresa, usuario)

    resp = logged_client.post(
        '/productos/actualizacion-masiva/aplicar',
        data={
            'categorias_ids': json.dumps([cat.id]),
            'porcentaje': '10',
            'actualizar_costo': 'y',
            'ajustar_cc': 'y',
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200

    # Verificar que el precio del producto se actualizo
    _db.session.refresh(prod)
    assert prod.precio_venta == Decimal('110.00')

    # Verificar que se creo el ajuste CC
    ajustes = AjustePrecioCuentaCorriente.query.filter_by(
        venta_id=venta.id,
    ).all()
    assert len(ajustes) == 1
    # 2 * 100 -> 2 * 110, diff = 20
    assert ajustes[0].monto_ajuste == Decimal('20.00')

    # Verificar movimiento CC de cargo por ajuste
    mov_ajuste = MovimientoCuentaCorriente.query.filter_by(
        cliente_id=cliente.id,
        referencia_tipo='ajuste_precio',
    ).first()
    assert mov_ajuste is not None
    assert mov_ajuste.monto == Decimal('20.00')

    # Verificar saldo actualizado del cliente
    _db.session.refresh(cliente)
    # Saldo original 200 + ajuste 20 = 220
    assert cliente.saldo_cuenta_corriente == Decimal('220.00')


def test_aplicar_actualizacion_sin_ajuste_cc(logged_client, empresa, usuario):
    """Sin checkbox ajustar_cc: solo se actualizan precios, sin ajuste CC."""
    cat, prod, cliente, venta = _setup_datos(empresa, usuario)

    resp = logged_client.post(
        '/productos/actualizacion-masiva/aplicar',
        data={
            'categorias_ids': json.dumps([cat.id]),
            'porcentaje': '10',
            'actualizar_costo': 'y',
            # Sin ajustar_cc
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200

    # Precio actualizado
    _db.session.refresh(prod)
    assert prod.precio_venta == Decimal('110.00')

    # SIN ajuste CC
    ajustes = AjustePrecioCuentaCorriente.query.filter_by(
        venta_id=venta.id,
    ).all()
    assert len(ajustes) == 0

    # Saldo del cliente NO cambio
    _db.session.refresh(cliente)
    assert cliente.saldo_cuenta_corriente == Decimal('200.00')
