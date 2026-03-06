"""Tests para rutas del superadmin."""

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
def empresa_pendiente(app):
    emp = Empresa(nombre='Taller Pendiente', activa=True, aprobada=False)
    _db.session.add(emp)
    _db.session.flush()
    admin = Usuario(
        email='admin@taller.com',
        nombre='Admin Taller',
        rol='administrador',
        activo=True,
        empresa_id=emp.id,
    )
    admin.set_password('password123')
    _db.session.add(admin)
    _db.session.commit()
    return emp


@pytest.fixture
def empresa_aprobada(app):
    emp = Empresa(nombre='Taller Aprobado', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.flush()
    admin = Usuario(
        email='admin@aprobado.com',
        nombre='Admin Aprobado',
        rol='administrador',
        activo=True,
        empresa_id=emp.id,
    )
    admin.set_password('password123')
    _db.session.add(admin)
    _db.session.commit()
    return emp


def _login_superadmin(client):
    """Helper para login del superadmin."""
    client.post(
        '/auth/login',
        data={'email': 'super@test.com', 'password': 'password123'},
    )


def test_dashboard_superadmin(app, superadmin, empresa_pendiente, empresa_aprobada):
    """Dashboard muestra métricas correctas."""
    client = app.test_client()
    _login_superadmin(client)
    resp = client.get('/superadmin/')
    assert resp.status_code == 200


def test_listado_empresas(app, superadmin, empresa_pendiente, empresa_aprobada):
    """Listado muestra todas las empresas."""
    client = app.test_client()
    _login_superadmin(client)
    resp = client.get('/superadmin/empresas')
    assert resp.status_code == 200
    assert b'Taller Pendiente' in resp.data
    assert b'Taller Aprobado' in resp.data


def test_filtro_empresas_pendientes(app, superadmin, empresa_pendiente, empresa_aprobada):
    """Filtro pendientes muestra solo empresas no aprobadas."""
    client = app.test_client()
    _login_superadmin(client)
    resp = client.get('/superadmin/empresas?filtro=pendientes')
    assert resp.status_code == 200
    assert b'Taller Pendiente' in resp.data
    assert b'Taller Aprobado' not in resp.data


def test_aprobar_empresa(app, superadmin, empresa_pendiente):
    """Superadmin puede aprobar empresa pendiente."""
    client = app.test_client()
    _login_superadmin(client)
    resp = client.post(
        f'/superadmin/empresas/{empresa_pendiente.id}/aprobar',
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        emp = _db.session.get(Empresa, empresa_pendiente.id)
        assert emp.aprobada is True


def test_desactivar_admin(app, superadmin, empresa_aprobada):
    """Superadmin puede desactivar admin de empresa."""
    client = app.test_client()
    _login_superadmin(client)
    resp = client.post(
        f'/superadmin/empresas/{empresa_aprobada.id}/desactivar-admin',
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        admin = Usuario.query.filter_by(empresa_id=empresa_aprobada.id, rol='administrador').first()
        assert admin.activo is False


def test_activar_admin(app, superadmin, empresa_aprobada):
    """Superadmin puede reactivar admin desactivado."""
    client = app.test_client()
    _login_superadmin(client)
    # Primero desactivar
    with app.app_context():
        admin = Usuario.query.filter_by(empresa_id=empresa_aprobada.id, rol='administrador').first()
        admin.activo = False
        _db.session.commit()
    # Luego activar
    resp = client.post(
        f'/superadmin/empresas/{empresa_aprobada.id}/activar-admin',
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        admin = Usuario.query.filter_by(empresa_id=empresa_aprobada.id, rol='administrador').first()
        assert admin.activo is True


def test_reset_password_admin(app, superadmin, empresa_aprobada):
    """Superadmin puede resetear contraseña de admin."""
    client = app.test_client()
    _login_superadmin(client)
    resp = client.post(
        f'/superadmin/empresas/{empresa_aprobada.id}/reset-password',
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        admin = Usuario.query.filter_by(empresa_id=empresa_aprobada.id, rol='administrador').first()
        assert admin.debe_cambiar_password is True


def test_acceso_denegado_para_admin_normal(app, empresa_aprobada):
    """Un admin normal no puede acceder a /superadmin/."""
    client = app.test_client()
    client.post(
        '/auth/login',
        data={'email': 'admin@aprobado.com', 'password': 'password123'},
    )
    resp = client.get('/superadmin/', follow_redirects=False)
    assert resp.status_code == 302
