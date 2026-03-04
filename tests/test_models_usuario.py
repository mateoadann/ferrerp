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


def test_usuario_es_administrador(app):
    """Verifica la property es_administrador."""
    empresa = Empresa(nombre='Empresa Admin Test')
    db.session.add(empresa)
    db.session.flush()

    admin = Usuario(
        email='admin2@ferrerp.test',
        nombre='Admin Test',
        rol='administrador',
        activo=True,
        empresa_id=empresa.id,
    )
    admin.set_password('clave')
    db.session.add(admin)
    db.session.commit()

    assert admin.es_administrador is True
    assert admin.es_admin is True


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
