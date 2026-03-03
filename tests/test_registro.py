"""Tests de la ruta de registro."""

from app.extensions import db
from app.models import Empresa, Usuario


def test_registro_get_muestra_formulario(app, client):
    """GET a /auth/registro devuelve el formulario."""
    response = client.get('/auth/registro')
    assert response.status_code == 200
    assert 'Registrá tu empresa' in response.data.decode()


def test_registro_crea_empresa_y_owner(app, client):
    """POST con datos válidos crea Empresa + Usuario owner."""
    response = client.post(
        '/auth/registro',
        data={
            'nombre': 'Juan Dueño',
            'email': 'juan@miferreteria.com',
            'password': 'clave123',
            'password_confirm': 'clave123',
            'empresa_nombre': 'Ferretería La Llave',
            'empresa_cuit': '30-11111111-1',
            'empresa_direccion': 'Av. Siempre Viva 742',
            'empresa_telefono': '011-5555-1234',
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    # Verificar que se creó la empresa
    empresa = Empresa.query.filter_by(nombre='Ferretería La Llave').first()
    assert empresa is not None
    assert empresa.cuit == '30-11111111-1'
    assert empresa.direccion == 'Av. Siempre Viva 742'
    assert empresa.activa is True

    # Verificar que se creó el usuario owner
    usuario = Usuario.query.filter_by(email='juan@miferreteria.com').first()
    assert usuario is not None
    assert usuario.nombre == 'Juan Dueño'
    assert usuario.rol == 'owner'
    assert usuario.empresa_id == empresa.id
    assert usuario.activo is True
    assert usuario.check_password('clave123') is True


def test_registro_email_duplicado(app, client):
    """POST con email existente muestra error."""
    # Crear usuario existente
    empresa = Empresa(nombre='Empresa Existente')
    db.session.add(empresa)
    db.session.flush()

    usuario = Usuario(
        email='existe@test.com',
        nombre='Ya Existe',
        rol='owner',
        activo=True,
        empresa_id=empresa.id,
    )
    usuario.set_password('clave123')
    db.session.add(usuario)
    db.session.commit()

    # Intentar registrar con el mismo email
    response = client.post(
        '/auth/registro',
        data={
            'nombre': 'Otro Usuario',
            'email': 'existe@test.com',
            'password': 'clave123',
            'password_confirm': 'clave123',
            'empresa_nombre': 'Otra Empresa',
        },
    )

    assert response.status_code == 200
    assert 'ya está registrado' in response.data.decode()
    # No debería crear una segunda empresa
    assert Empresa.query.count() == 1


def test_registro_campos_requeridos(app, client):
    """POST sin campos requeridos muestra errores."""
    response = client.post(
        '/auth/registro',
        data={},
    )

    assert response.status_code == 200
    html = response.data.decode()
    assert 'El nombre es requerido' in html or 'requerido' in html.lower()


def test_registro_passwords_no_coinciden(app, client):
    """POST con contraseñas diferentes muestra error."""
    response = client.post(
        '/auth/registro',
        data={
            'nombre': 'Test User',
            'email': 'test@test.com',
            'password': 'clave123',
            'password_confirm': 'clave456',
            'empresa_nombre': 'Test Empresa',
        },
    )

    assert response.status_code == 200
    assert 'no coinciden' in response.data.decode()


def test_registro_empresa_sin_datos_opcionales(app, client):
    """Registro funciona sin CUIT, dirección ni teléfono."""
    response = client.post(
        '/auth/registro',
        data={
            'nombre': 'María López',
            'email': 'maria@nueva.com',
            'password': 'clave123',
            'password_confirm': 'clave123',
            'empresa_nombre': 'Ferretería Nueva',
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    empresa = Empresa.query.filter_by(nombre='Ferretería Nueva').first()
    assert empresa is not None
    assert empresa.cuit is None
    assert empresa.direccion is None
    assert empresa.telefono is None
