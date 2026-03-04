"""Tests de protección: mínimo un administrador por empresa."""

from app.extensions import db
from app.models import Empresa, Usuario


def _crear_empresa_con_admin():
    """Helper: crea empresa con un administrador."""
    empresa = Empresa(nombre='Empresa Test')
    db.session.add(empresa)
    db.session.flush()

    admin = Usuario(
        email='admin@test.com',
        nombre='Admin Test',
        rol='administrador',
        activo=True,
        empresa_id=empresa.id,
    )
    admin.set_password('clave123')
    db.session.add(admin)
    db.session.commit()
    return empresa, admin


def test_vendedor_no_es_administrador(app):
    """Verifica que un vendedor no es administrador."""
    vendedor = Usuario(
        email='vendedor@test.com',
        nombre='Vendedor',
        rol='vendedor',
        activo=True,
    )
    vendedor.set_password('clave123')
    db.session.add(vendedor)
    db.session.commit()

    assert vendedor.es_administrador is False
    assert vendedor.es_admin is False


def test_admin_es_administrador(app):
    """Verifica que un administrador es administrador."""
    empresa, admin = _crear_empresa_con_admin()

    assert admin.es_administrador is True
    assert admin.es_admin is True
