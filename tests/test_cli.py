"""Tests para comandos CLI."""

import os

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite:///:memory:')

import pytest

from app import create_app
from app.extensions import db as _db
from app.models import Usuario


@pytest.fixture
def app():
    app = create_app('testing')
    app.config.update(
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_ENGINE_OPTIONS={},
        WTF_CSRF_ENABLED=False,
        TESTING=True,
        LOGIN_DISABLED=True,
    )
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


def test_crear_superadmin(app):
    """Test que el comando crea un superadmin correctamente."""
    runner = app.test_cli_runner()
    result = runner.invoke(args=[
        'crear-superadmin',
        '--email', 'super@test.com',
        '--nombre', 'Super Admin',
        '--password', 'password123',
    ])
    assert 'Superadmin creado exitosamente' in result.output

    with app.app_context():
        usuario = Usuario.query.filter_by(email='super@test.com').first()
        assert usuario is not None
        assert usuario.rol == 'superadmin'
        assert usuario.empresa_id is None
        assert usuario.activo is True
        assert usuario.check_password('password123')


def test_crear_superadmin_duplicado(app):
    """Test que no permite crear un segundo superadmin."""
    runner = app.test_cli_runner()
    runner.invoke(args=[
        'crear-superadmin',
        '--email', 'super1@test.com',
        '--nombre', 'Super Admin 1',
        '--password', 'password123',
    ])
    result = runner.invoke(args=[
        'crear-superadmin',
        '--email', 'super2@test.com',
        '--nombre', 'Super Admin 2',
        '--password', 'password456',
    ])
    assert 'Ya existe un superadmin' in result.output

    with app.app_context():
        count = Usuario.query.filter_by(rol='superadmin').count()
        assert count == 1
