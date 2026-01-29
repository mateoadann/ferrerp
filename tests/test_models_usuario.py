from app.extensions import db
from app.models import Usuario


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
