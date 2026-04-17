"""Tests para actualización de precio individual de productos."""

import os

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite:///:memory:')

from decimal import Decimal
from unittest.mock import patch

import pytest

from app import create_app
from app.extensions import db as _db
from app.models import ActualizacionPrecio, Empresa, Producto, Usuario


@pytest.fixture
def app():
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
    emp = Empresa(nombre='Ferretería Test', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.commit()
    return emp


@pytest.fixture
def admin(empresa):
    u = Usuario(
        email='admin@test.com',
        nombre='Admin Test',
        rol='administrador',
        activo=True,
        empresa_id=empresa.id,
    )
    u.set_password('test123')
    _db.session.add(u)
    _db.session.commit()
    return u


@pytest.fixture
def vendedor(empresa):
    u = Usuario(
        email='vendedor@test.com',
        nombre='Vendedor Test',
        rol='vendedor',
        activo=True,
        empresa_id=empresa.id,
    )
    u.set_password('test123')
    _db.session.add(u)
    _db.session.commit()
    return u


@pytest.fixture
def producto(empresa):
    p = Producto(
        codigo='PRD-001',
        nombre='Martillo',
        unidad_medida='unidad',
        precio_costo=Decimal('100.00'),
        precio_venta=Decimal('150.00'),
        iva_porcentaje=Decimal('21.00'),
        stock_actual=Decimal('10.000'),
        stock_minimo=Decimal('5.000'),
        activo=True,
        empresa_id=empresa.id,
    )
    _db.session.add(p)
    _db.session.commit()
    return p


def _login(client, email, password='test123'):
    client.post('/auth/login', data={'email': email, 'password': password})


# --- Tests del servicio ---


def test_actualizar_precio_directo(app, admin, producto):
    """Modo directo: actualizar precio de venta y recalcular costo."""
    from app.services.actualizacion_precio_service import actualizar_precio_individual

    with app.app_context():
        with patch('app.services.actualizacion_precio_service.current_user', admin):
            registro = actualizar_precio_individual(
                producto_id=producto.id,
                precio_costo_nuevo=Decimal('120.00'),
                precio_venta_nuevo=Decimal('180.00'),
                precio_costo_anterior=Decimal('100.00'),
                precio_venta_anterior=Decimal('150.00'),
                porcentaje=None,
                notas='Ajuste manual de precio',
            )
            _db.session.commit()

        assert registro is not None
        assert registro.tipo == 'manual'
        assert registro.porcentaje is None
        assert registro.precio_costo_anterior == Decimal('100.00')
        assert registro.precio_costo_nuevo == Decimal('120.00')
        assert registro.precio_venta_anterior == Decimal('150.00')
        assert registro.precio_venta_nuevo == Decimal('180.00')
        assert registro.actualizo_costo is True

        # Verificar que el producto fue actualizado
        p = _db.session.get(Producto, producto.id)
        assert p.precio_costo == Decimal('120.00')
        assert p.precio_venta == Decimal('180.00')


def test_actualizar_precio_porcentaje(app, admin, producto):
    """Modo porcentaje: aplicar 10% y verificar cálculos correctos."""
    from app.services.actualizacion_precio_service import actualizar_precio_individual

    with app.app_context():
        with patch('app.services.actualizacion_precio_service.current_user', admin):
            registro = actualizar_precio_individual(
                producto_id=producto.id,
                precio_costo_nuevo=Decimal('110.00'),
                precio_venta_nuevo=Decimal('165.00'),
                precio_costo_anterior=Decimal('100.00'),
                precio_venta_anterior=Decimal('150.00'),
                porcentaje=Decimal('10'),
            )
            _db.session.commit()

        assert registro.porcentaje == Decimal('10')
        assert registro.precio_costo_nuevo == Decimal('110.00')
        assert registro.precio_venta_nuevo == Decimal('165.00')

        p = _db.session.get(Producto, producto.id)
        assert p.precio_costo == Decimal('110.00')
        assert p.precio_venta == Decimal('165.00')


def test_audit_trail_creado(app, admin, producto):
    """Verificar que se crea registro ActualizacionPrecio con tipo='manual'."""
    from app.services.actualizacion_precio_service import actualizar_precio_individual

    with app.app_context():
        # Verificar que no hay registros previos
        count_antes = ActualizacionPrecio.query.count()

        with patch('app.services.actualizacion_precio_service.current_user', admin):
            actualizar_precio_individual(
                producto_id=producto.id,
                precio_costo_nuevo=Decimal('110.00'),
                precio_venta_nuevo=Decimal('165.00'),
                precio_costo_anterior=Decimal('100.00'),
                precio_venta_anterior=Decimal('150.00'),
            )
            _db.session.commit()

        count_despues = ActualizacionPrecio.query.count()
        assert count_despues == count_antes + 1

        registro = ActualizacionPrecio.query.order_by(ActualizacionPrecio.id.desc()).first()
        assert registro.tipo == 'manual'
        assert registro.usuario_id == admin.id
        assert registro.producto_id == producto.id
        assert registro.empresa_id == admin.empresa_id


def test_stale_data_rechazado(app, admin, producto):
    """Detectar datos obsoletos y rechazar actualización."""
    from app.services.actualizacion_precio_service import actualizar_precio_individual

    with app.app_context():
        with patch('app.services.actualizacion_precio_service.current_user', admin):
            with pytest.raises(ValueError, match='modificados por otro usuario'):
                actualizar_precio_individual(
                    producto_id=producto.id,
                    precio_costo_nuevo=Decimal('120.00'),
                    precio_venta_nuevo=Decimal('180.00'),
                    # Precios anteriores incorrectos (simula stale data)
                    precio_costo_anterior=Decimal('90.00'),
                    precio_venta_anterior=Decimal('140.00'),
                )


def test_precio_venta_cero_rechazado(app, admin, producto):
    """Precio de venta <= 0 es rechazado."""
    from app.services.actualizacion_precio_service import actualizar_precio_individual

    with app.app_context():
        with patch('app.services.actualizacion_precio_service.current_user', admin):
            with pytest.raises(ValueError, match='mayor a cero'):
                actualizar_precio_individual(
                    producto_id=producto.id,
                    precio_costo_nuevo=Decimal('100.00'),
                    precio_venta_nuevo=Decimal('0.00'),
                    precio_costo_anterior=Decimal('100.00'),
                    precio_venta_anterior=Decimal('150.00'),
                )

        # Verificar que el producto no cambió
        p = _db.session.get(Producto, producto.id)
        assert p.precio_venta == Decimal('150.00')


# --- Tests de rutas ---


def test_ruta_modal_precio_admin(app, admin, producto):
    """Admin puede acceder al modal de precio (GET 200)."""
    client = app.test_client()
    _login(client, admin.email)
    resp = client.get(f'/productos/{producto.id}/actualizar-precio')
    assert resp.status_code == 200
    assert b'Actualizar precio' in resp.data
    assert producto.nombre.encode() in resp.data


def test_ruta_modal_precio_vendedor_redirige(app, vendedor, producto):
    """Vendedor no puede acceder al modal de precio."""
    client = app.test_client()
    _login(client, vendedor.email)
    resp = client.get(
        f'/productos/{producto.id}/actualizar-precio',
        follow_redirects=False,
    )
    assert resp.status_code == 302


def test_ruta_aplicar_precio_directo(app, admin, producto):
    """POST con datos válidos en modo directo actualiza el producto."""
    client = app.test_client()
    _login(client, admin.email)
    resp = client.post(
        f'/productos/{producto.id}/actualizar-precio',
        data={
            'modo': 'directo',
            'precio_costo_nuevo': '120.00',
            'precio_venta_nuevo': '180.00',
            'precio_costo_anterior': '100.00',
            'precio_venta_anterior': '150.00',
            'notas': 'Test directo',
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get('HX-Trigger') == 'productos-actualizado'

    # Verificar producto actualizado
    with app.app_context():
        p = _db.session.get(Producto, producto.id)
        assert p.precio_costo == Decimal('120.00')
        assert p.precio_venta == Decimal('180.00')


def test_ruta_aplicar_precio_porcentaje(app, admin, producto):
    """POST con datos válidos en modo porcentaje actualiza el producto."""
    client = app.test_client()
    _login(client, admin.email)
    resp = client.post(
        f'/productos/{producto.id}/actualizar-precio',
        data={
            'modo': 'porcentaje',
            'porcentaje': '10',
            'actualizar_costo': 'y',
            'precio_costo_anterior': '100.00',
            'precio_venta_anterior': '150.00',
        },
    )
    assert resp.status_code == 200

    with app.app_context():
        p = _db.session.get(Producto, producto.id)
        assert p.precio_costo == Decimal('110.00')
        assert p.precio_venta == Decimal('165.00')


def test_ruta_aplicar_stale_data(app, admin, producto):
    """POST con precios anteriores incorrectos devuelve error 422."""
    client = app.test_client()
    _login(client, admin.email)
    resp = client.post(
        f'/productos/{producto.id}/actualizar-precio',
        data={
            'modo': 'directo',
            'precio_costo_nuevo': '120.00',
            'precio_venta_nuevo': '180.00',
            'precio_costo_anterior': '90.00',
            'precio_venta_anterior': '140.00',
        },
    )
    assert resp.status_code == 422

    # Producto no cambió
    with app.app_context():
        p = _db.session.get(Producto, producto.id)
        assert p.precio_venta == Decimal('150.00')
