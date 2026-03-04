"""Tests del modelo Empresa."""

from app.extensions import db
from app.models import Empresa, Usuario


def test_crear_empresa(app):
    """Verifica la creación de una empresa con todos los campos."""
    empresa = Empresa(
        nombre='Ferretería Test',
        cuit='30-12345678-9',
        direccion='Calle Falsa 123',
        telefono='011-1234-5678',
        email='test@ferreteria.com',
    )
    db.session.add(empresa)
    db.session.commit()

    assert empresa.id is not None
    assert empresa.nombre == 'Ferretería Test'
    assert empresa.cuit == '30-12345678-9'
    assert empresa.direccion == 'Calle Falsa 123'
    assert empresa.telefono == '011-1234-5678'
    assert empresa.email == 'test@ferreteria.com'


def test_empresa_activa_por_defecto(app):
    """Verifica que la empresa se crea activa por defecto."""
    empresa = Empresa(nombre='Empresa Activa')
    db.session.add(empresa)
    db.session.commit()

    assert empresa.activa is True


def test_empresa_tiene_usuarios(app):
    """Verifica la relación empresa -> usuarios."""
    empresa = Empresa(nombre='Empresa con Usuarios')
    db.session.add(empresa)
    db.session.flush()

    usuario = Usuario(
        email='user@empresa.com',
        nombre='Usuario Empresa',
        rol='administrador',
        activo=True,
        empresa_id=empresa.id,
    )
    usuario.set_password('clave123')
    db.session.add(usuario)
    db.session.commit()

    assert empresa.usuarios.count() == 1
    assert empresa.usuarios.first().email == 'user@empresa.com'
    assert usuario.empresa == empresa


def test_empresa_to_dict(app):
    """Verifica la serialización de la empresa."""
    empresa = Empresa(
        nombre='Empresa Dict',
        cuit='30-99999999-9',
    )
    db.session.add(empresa)
    db.session.commit()

    d = empresa.to_dict()
    assert d['nombre'] == 'Empresa Dict'
    assert d['cuit'] == '30-99999999-9'
    assert d['activa'] is True
    assert 'id' in d
