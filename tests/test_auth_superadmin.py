"""Tests para flujo de login del superadmin y cambio de contraseña."""

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
def superadmin(app):
    u = Usuario(
        email='super@test.com',
        nombre='Super Admin',
        rol='superadmin',
        activo=True,
        empresa_id=None,
    )
    u.set_password('password123')
    _db.session.add(u)
    _db.session.commit()
    return u


@pytest.fixture
def admin_con_cambio_password(app):
    emp = Empresa(nombre='Test', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.flush()
    u = Usuario(
        email='admin@test.com',
        nombre='Admin',
        rol='administrador',
        activo=True,
        empresa_id=emp.id,
        debe_cambiar_password=True,
    )
    u.set_password('temporal123')
    _db.session.add(u)
    _db.session.commit()
    return u


def test_login_superadmin_redirige_a_superadmin_dashboard(app, superadmin):
    """Superadmin es redirigido a /superadmin/ tras login."""
    client = app.test_client()
    resp = client.post(
        '/auth/login',
        data={
            'email': 'super@test.com',
            'password': 'password123',
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert '/superadmin/' in resp.headers['Location']


def test_login_con_debe_cambiar_password_redirige(app, admin_con_cambio_password):
    """Usuario con debe_cambiar_password es redirigido a cambiar contraseña."""
    client = app.test_client()
    resp = client.post(
        '/auth/login',
        data={
            'email': 'admin@test.com',
            'password': 'temporal123',
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert '/auth/cambiar-password' in resp.headers['Location']


def test_registro_crea_empresa_no_aprobada(app):
    """El registro crea empresa con aprobada=False."""
    client = app.test_client()
    client.post(
        '/auth/registro',
        data={
            'nombre': 'Admin Nuevo',
            'email': 'nuevo@test.com',
            'password': 'password123',
            'password_confirm': 'password123',
            'empresa_nombre': 'Mi Taller',
        },
    )
    with app.app_context():
        emp = Empresa.query.filter_by(nombre='Mi Taller').first()
        assert emp is not None
        assert emp.aprobada is False


def test_cambiar_password_exitoso(app, admin_con_cambio_password):
    """El usuario puede cambiar su contraseña temporal."""
    client = app.test_client()
    # Login primero
    client.post(
        '/auth/login',
        data={
            'email': 'admin@test.com',
            'password': 'temporal123',
        },
    )
    # Cambiar contraseña
    resp = client.post(
        '/auth/cambiar-password',
        data={
            'password_actual': 'temporal123',
            'password_nueva': 'nuevapassword123',
            'password_confirmar': 'nuevapassword123',
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    with app.app_context():
        u = Usuario.query.filter_by(email='admin@test.com').first()
        assert u.debe_cambiar_password is False
        assert u.check_password('nuevapassword123')
