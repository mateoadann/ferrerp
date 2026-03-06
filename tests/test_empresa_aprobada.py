"""Tests para verificar que empresa no aprobada no puede hacer escrituras."""

import os

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite:///:memory:')

import pytest

from app import create_app
from app.extensions import db as _db
from app.models import Empresa, Usuario


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
def admin_no_aprobado(app):
    emp = Empresa(nombre='No Aprobada', activa=True, aprobada=False)
    _db.session.add(emp)
    _db.session.flush()
    u = Usuario(
        email='admin@noaprobada.com', nombre='Admin', rol='administrador',
        activo=True, empresa_id=emp.id,
    )
    u.set_password('test123')
    _db.session.add(u)
    _db.session.commit()
    return u


def _login(client, email, password):
    client.post('/auth/login', data={'email': email, 'password': password})


def test_empresa_no_aprobada_puede_ver_dashboard(app, admin_no_aprobado):
    """Empresa no aprobada puede ver el dashboard (lectura)."""
    client = app.test_client()
    _login(client, admin_no_aprobado.email, 'test123')
    resp = client.get('/')
    assert resp.status_code == 200


def test_empresa_no_aprobada_puede_ver_productos(app, admin_no_aprobado):
    """Empresa no aprobada puede ver listado de productos (lectura)."""
    client = app.test_client()
    _login(client, admin_no_aprobado.email, 'test123')
    resp = client.get('/productos/')
    assert resp.status_code == 200


def test_empresa_no_aprobada_no_puede_crear_producto(app, admin_no_aprobado):
    """Empresa no aprobada no puede crear productos."""
    client = app.test_client()
    _login(client, admin_no_aprobado.email, 'test123')
    resp = client.post('/productos/nuevo', data={}, follow_redirects=False)
    assert resp.status_code == 302  # Redirigido
