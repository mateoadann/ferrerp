"""Tests para los decoradores superadmin_required y empresa_aprobada_required."""

import os

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite:///:memory:')

import pytest
from flask import Blueprint
from flask_login import login_required, login_user

from app import create_app
from app.extensions import db as _db
from app.models import Empresa, Usuario
from app.utils.decorators import empresa_aprobada_required, superadmin_required


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

    # Registrar rutas de prueba
    test_bp = Blueprint('test_decorators', __name__)

    @test_bp.route('/test-superadmin')
    @login_required
    @superadmin_required
    def ruta_superadmin():
        return 'ok-superadmin'

    @test_bp.route('/test-aprobada')
    @login_required
    @empresa_aprobada_required
    def ruta_aprobada():
        return 'ok-aprobada'

    # Ruta auxiliar para login en tests
    @test_bp.route('/test-login/<int:user_id>')
    def test_login(user_id):
        usuario = Usuario.query.get(user_id)
        login_user(usuario)
        return 'logged-in'

    with app.app_context():
        app.register_blueprint(test_bp)
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def empresa_aprobada(app):
    """Crea una empresa aprobada."""
    emp = Empresa(nombre='Empresa Aprobada', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.commit()
    return emp


@pytest.fixture
def empresa_pendiente(app):
    """Crea una empresa pendiente de aprobación."""
    emp = Empresa(nombre='Empresa Pendiente', activa=True, aprobada=False)
    _db.session.add(emp)
    _db.session.commit()
    return emp


@pytest.fixture
def superadmin(app):
    """Crea un usuario superadmin (sin empresa)."""
    usuario = Usuario(
        email='super@ferrerp.com',
        nombre='Super Admin',
        rol='superadmin',
        activo=True,
        empresa_id=None,
    )
    usuario.set_password('test1234')
    _db.session.add(usuario)
    _db.session.commit()
    return usuario


@pytest.fixture
def admin_aprobado(app, empresa_aprobada):
    """Crea un admin de empresa aprobada."""
    usuario = Usuario(
        email='admin@aprobada.com',
        nombre='Admin Aprobado',
        rol='administrador',
        activo=True,
        empresa_id=empresa_aprobada.id,
    )
    usuario.set_password('test1234')
    _db.session.add(usuario)
    _db.session.commit()
    return usuario


@pytest.fixture
def admin_pendiente(app, empresa_pendiente):
    """Crea un admin de empresa pendiente."""
    usuario = Usuario(
        email='admin@pendiente.com',
        nombre='Admin Pendiente',
        rol='administrador',
        activo=True,
        empresa_id=empresa_pendiente.id,
    )
    usuario.set_password('test1234')
    _db.session.add(usuario)
    _db.session.commit()
    return usuario


def _login(client, user_id):
    """Helper para loguear un usuario en el test client."""
    client.get(f'/test-login/{user_id}')


# --- Tests superadmin_required ---


def test_superadmin_required_permite_superadmin(client, superadmin):
    """superadmin_required permite acceso a superadmin."""
    _login(client, superadmin.id)
    resp = client.get('/test-superadmin')
    assert resp.status_code == 200
    assert resp.data == b'ok-superadmin'


def test_superadmin_required_bloquea_admin_normal(client, admin_aprobado):
    """superadmin_required bloquea a un admin normal con redirect."""
    _login(client, admin_aprobado.id)
    resp = client.get('/test-superadmin')
    assert resp.status_code == 302
    # dashboard.index está en '/'
    assert resp.headers['Location'].endswith('/')


def test_superadmin_required_bloquea_no_autenticado(client):
    """superadmin_required redirige a login si no está autenticado."""
    resp = client.get('/test-superadmin')
    assert resp.status_code == 302
    assert '/auth/login' in resp.headers['Location']


# --- Tests empresa_aprobada_required ---


def test_empresa_aprobada_permite_empresa_aprobada(client, admin_aprobado):
    """empresa_aprobada_required permite acceso a admin de empresa aprobada."""
    _login(client, admin_aprobado.id)
    resp = client.get('/test-aprobada')
    assert resp.status_code == 200
    assert resp.data == b'ok-aprobada'


def test_empresa_aprobada_bloquea_empresa_pendiente(client, admin_pendiente):
    """empresa_aprobada_required bloquea a admin de empresa pendiente."""
    _login(client, admin_pendiente.id)
    resp = client.get('/test-aprobada')
    assert resp.status_code == 302
    # dashboard.index está en '/'
    assert resp.headers['Location'].endswith('/')


def test_empresa_aprobada_permite_superadmin(client, superadmin):
    """empresa_aprobada_required permite acceso a superadmin (sin empresa)."""
    _login(client, superadmin.id)
    resp = client.get('/test-aprobada')
    assert resp.status_code == 200
    assert resp.data == b'ok-aprobada'
