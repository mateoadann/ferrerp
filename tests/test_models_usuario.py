from app.extensions import db
from app.models import Empresa, Usuario


def test_usuario_password_roles_iniciales(app):
    usuario = Usuario(
        email='admin@ferrerp.test',
        nombre='Juan Perez',
        rol='administrador',
        activo=True,
    )
    usuario.set_password('clave-segura')

    db.session.add(usuario)
    db.session.commit()

    assert usuario.check_password('clave-segura') is True
    assert usuario.check_password('otra-clave') is False
    assert usuario.es_administrador is True
    assert usuario.es_admin is True
    assert usuario.iniciales == 'JP'


def test_usuario_es_owner(app):
    """Verifica la property es_owner."""
    empresa = Empresa(nombre='Empresa Owner Test')
    db.session.add(empresa)
    db.session.flush()

    owner = Usuario(
        email='owner@ferrerp.test',
        nombre='Owner Test',
        rol='owner',
        activo=True,
        empresa_id=empresa.id,
    )
    owner.set_password('clave')
    db.session.add(owner)
    db.session.commit()

    assert owner.es_owner is True
    assert owner.es_administrador is True
    assert owner.es_admin is True


def test_usuario_tiene_empresa(app):
    """Verifica la FK empresa_id."""
    empresa = Empresa(nombre='Empresa FK Test')
    db.session.add(empresa)
    db.session.flush()

    usuario = Usuario(
        email='fk@ferrerp.test',
        nombre='Usuario FK',
        rol='vendedor',
        activo=True,
        empresa_id=empresa.id,
    )
    usuario.set_password('clave')
    db.session.add(usuario)
    db.session.commit()

    assert usuario.empresa_id == empresa.id
    assert usuario.empresa.nombre == 'Empresa FK Test'
    assert usuario.to_dict()['empresa_id'] == empresa.id
