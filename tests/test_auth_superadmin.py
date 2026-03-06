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


def test_login_admin_desactivado(app):
    """Un admin desactivado por superadmin no puede loguearse."""
    emp = Empresa(nombre='Empresa Desact', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.flush()
    u = Usuario(
        email='desact@test.com',
        nombre='Admin Desact',
        rol='administrador',
        activo=False,
        empresa_id=emp.id,
    )
    u.set_password('password123')
    _db.session.add(u)
    _db.session.commit()

    client = app.test_client()
    resp = client.post(
        '/auth/login',
        data={'email': 'desact@test.com', 'password': 'password123'},
        follow_redirects=True,
    )
    assert b'Tu cuenta est' in resp.data  # "Tu cuenta está desactivada"


def test_cambiar_password_actual_incorrecta(app, admin_con_cambio_password):
    """El cambio falla si la contraseña actual es incorrecta."""
    client = app.test_client()
    client.post(
        '/auth/login',
        data={'email': 'admin@test.com', 'password': 'temporal123'},
    )
    resp = client.post(
        '/auth/cambiar-password',
        data={
            'password_actual': 'incorrecta',
            'password_nueva': 'nuevapassword123',
            'password_confirmar': 'nuevapassword123',
        },
        follow_redirects=True,
    )
    assert b'incorrecta' in resp.data
    with app.app_context():
        u = Usuario.query.filter_by(email='admin@test.com').first()
        assert u.debe_cambiar_password is True


def test_cambiar_password_confirmacion_no_coincide(app, admin_con_cambio_password):
    """El cambio falla si la confirmación no coincide."""
    client = app.test_client()
    client.post(
        '/auth/login',
        data={'email': 'admin@test.com', 'password': 'temporal123'},
    )
    resp = client.post(
        '/auth/cambiar-password',
        data={
            'password_actual': 'temporal123',
            'password_nueva': 'nuevapassword123',
            'password_confirmar': 'otrapassword456',
        },
        follow_redirects=True,
    )
    assert b'no coinciden' in resp.data
    with app.app_context():
        u = Usuario.query.filter_by(email='admin@test.com').first()
        assert u.debe_cambiar_password is True


def test_superadmin_con_debe_cambiar_password(app):
    """Superadmin con debe_cambiar_password es forzado y luego redirige a /superadmin/."""
    u = Usuario(
        email='super2@test.com',
        nombre='Super Admin 2',
        rol='superadmin',
        activo=True,
        empresa_id=None,
        debe_cambiar_password=True,
    )
    u.set_password('temporal123')
    _db.session.add(u)
    _db.session.commit()

    client = app.test_client()
    # Login redirige a cambiar password
    resp = client.post(
        '/auth/login',
        data={'email': 'super2@test.com', 'password': 'temporal123'},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert '/auth/cambiar-password' in resp.headers['Location']

    # Cambiar password redirige a /superadmin/
    resp = client.post(
        '/auth/cambiar-password',
        data={
            'password_actual': 'temporal123',
            'password_nueva': 'nuevapass123',
            'password_confirmar': 'nuevapass123',
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert '/superadmin/' in resp.headers['Location']

    with app.app_context():
        u = Usuario.query.filter_by(email='super2@test.com').first()
        assert u.debe_cambiar_password is False
