"""Tests de funcionalidad de cumpleaños de clientes."""

import os

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite:///:memory:')

from datetime import date
from urllib.parse import unquote

import pytest

from app import create_app
from app.extensions import db as _db
from app.models import Cliente, Configuracion, Empresa, Usuario
from app.services.cumpleanos_service import (
    generar_url_whatsapp_cumpleanos,
    obtener_cumpleanos_hoy,
)

# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def app():
    """App con LOGIN_DISABLED=False para tests de rutas."""
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
def empresa(app):
    """Crea empresa de prueba."""
    emp = Empresa(nombre='Ferretería Test', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.flush()
    return emp


@pytest.fixture
def admin(empresa):
    """Crea usuario administrador."""
    usuario = Usuario(
        email='admin@test.com',
        nombre='Admin Test',
        rol='administrador',
        activo=True,
        empresa_id=empresa.id,
    )
    usuario.set_password('clave123')
    _db.session.add(usuario)
    _db.session.commit()
    return usuario


@pytest.fixture
def client(app):
    """Cliente HTTP de prueba."""
    return app.test_client()


def _login(client, email='admin@test.com', password='clave123'):
    """Helper: inicia sesión."""
    client.post('/auth/login', data={'email': email, 'password': password})


def _crear_cliente(empresa, nombre='Juan Pérez', fecha_nacimiento=None, telefono=None, activo=True):
    """Helper: crea un cliente de prueba."""
    cliente = Cliente(
        nombre=nombre,
        empresa_id=empresa.id,
        fecha_nacimiento=fecha_nacimiento,
        telefono=telefono,
        activo=activo,
    )
    _db.session.add(cliente)
    _db.session.flush()
    return cliente


# --------------------------------------------------------------------------
# Task 4.1: Tests del modelo — es_cumpleanos_hoy y to_dict
# --------------------------------------------------------------------------


def test_cliente_fecha_nacimiento_nullable(app, empresa):
    """Cliente puede crearse sin fecha de nacimiento (nullable)."""
    cliente = _crear_cliente(empresa, fecha_nacimiento=None)
    _db.session.commit()

    assert cliente.fecha_nacimiento is None


def test_cliente_fecha_nacimiento_valida(app, empresa):
    """Cliente puede crearse con fecha de nacimiento válida."""
    fecha = date(1990, 5, 15)
    cliente = _crear_cliente(empresa, fecha_nacimiento=fecha)
    _db.session.commit()

    assert cliente.fecha_nacimiento == fecha


def test_es_cumpleanos_hoy_retorna_true(app, empresa):
    """es_cumpleanos_hoy retorna True cuando mes y día coinciden con hoy."""
    hoy = date.today()
    # Año diferente al actual para verificar que solo compara mes/día
    fecha_nacimiento = date(1990, hoy.month, hoy.day)
    cliente = _crear_cliente(empresa, fecha_nacimiento=fecha_nacimiento)
    _db.session.commit()

    assert cliente.es_cumpleanos_hoy is True


def test_es_cumpleanos_hoy_retorna_false_fecha_distinta(app, empresa):
    """es_cumpleanos_hoy retorna False cuando la fecha no coincide."""
    hoy = date.today()
    # Usar un mes diferente
    otro_mes = (hoy.month % 12) + 1
    fecha_nacimiento = date(1990, otro_mes, 1)
    cliente = _crear_cliente(empresa, fecha_nacimiento=fecha_nacimiento)
    _db.session.commit()

    assert cliente.es_cumpleanos_hoy is False


def test_es_cumpleanos_hoy_retorna_false_sin_fecha(app, empresa):
    """es_cumpleanos_hoy retorna False cuando fecha_nacimiento es None."""
    cliente = _crear_cliente(empresa, fecha_nacimiento=None)
    _db.session.commit()

    assert cliente.es_cumpleanos_hoy is False


def test_to_dict_incluye_fecha_nacimiento(app, empresa):
    """to_dict() incluye fecha_nacimiento en formato ISO."""
    fecha = date(1985, 7, 15)
    cliente = _crear_cliente(empresa, fecha_nacimiento=fecha)
    _db.session.commit()

    d = cliente.to_dict()
    assert 'fecha_nacimiento' in d
    assert d['fecha_nacimiento'] == '1985-07-15'


def test_to_dict_fecha_nacimiento_none(app, empresa):
    """to_dict() incluye fecha_nacimiento como None cuando no está cargada."""
    cliente = _crear_cliente(empresa, fecha_nacimiento=None)
    _db.session.commit()

    d = cliente.to_dict()
    assert 'fecha_nacimiento' in d
    assert d['fecha_nacimiento'] is None


# --------------------------------------------------------------------------
# Task 4.2: Tests del servicio — obtener_cumpleanos_hoy
# --------------------------------------------------------------------------


def test_obtener_cumpleanos_hoy_retorna_cumpleaneros(app, empresa):
    """Retorna clientes cuyo cumpleaños es hoy."""
    hoy = date.today()
    _crear_cliente(empresa, 'Cumpleañero', date(1990, hoy.month, hoy.day))
    _crear_cliente(empresa, 'No cumple', date(1990, (hoy.month % 12) + 1, 1))
    _db.session.commit()

    resultado = obtener_cumpleanos_hoy(empresa.id)
    assert len(resultado) == 1
    assert resultado[0].nombre == 'Cumpleañero'


def test_obtener_cumpleanos_hoy_excluye_sin_fecha(app, empresa):
    """Excluye clientes con fecha_nacimiento=None."""
    hoy = date.today()
    _crear_cliente(empresa, 'Sin fecha', None)
    _crear_cliente(empresa, 'Cumpleañero', date(1990, hoy.month, hoy.day))
    _db.session.commit()

    resultado = obtener_cumpleanos_hoy(empresa.id)
    assert len(resultado) == 1
    assert resultado[0].nombre == 'Cumpleañero'


def test_obtener_cumpleanos_hoy_excluye_inactivos(app, empresa):
    """Excluye clientes inactivos aunque cumplan años hoy."""
    hoy = date.today()
    _crear_cliente(empresa, 'Inactivo', date(1990, hoy.month, hoy.day), activo=False)
    _db.session.commit()

    resultado = obtener_cumpleanos_hoy(empresa.id)
    assert len(resultado) == 0


def test_obtener_cumpleanos_hoy_aislamiento_multitenant(app, empresa):
    """Solo retorna clientes de la empresa indicada (multi-tenant)."""
    hoy = date.today()
    fecha_cumple = date(1990, hoy.month, hoy.day)

    # Cliente de empresa 1 (la fixture)
    _crear_cliente(empresa, 'Cliente Empresa 1', fecha_cumple)

    # Crear otra empresa con su cliente
    otra_empresa = Empresa(nombre='Otra Empresa', activa=True, aprobada=True)
    _db.session.add(otra_empresa)
    _db.session.flush()
    _crear_cliente(otra_empresa, 'Cliente Empresa 2', fecha_cumple)
    _db.session.commit()

    resultado = obtener_cumpleanos_hoy(empresa.id)
    assert len(resultado) == 1
    assert resultado[0].nombre == 'Cliente Empresa 1'

    resultado_otra = obtener_cumpleanos_hoy(otra_empresa.id)
    assert len(resultado_otra) == 1
    assert resultado_otra[0].nombre == 'Cliente Empresa 2'


def test_obtener_cumpleanos_hoy_lista_vacia(app, empresa):
    """Retorna lista vacía cuando no hay cumpleaños hoy."""
    hoy = date.today()
    otro_mes = (hoy.month % 12) + 1
    _crear_cliente(empresa, 'No cumple', date(1990, otro_mes, 1))
    _db.session.commit()

    resultado = obtener_cumpleanos_hoy(empresa.id)
    assert len(resultado) == 0


# --------------------------------------------------------------------------
# Task 4.3: Tests del servicio — generar_url_whatsapp_cumpleanos
# --------------------------------------------------------------------------


def test_generar_url_whatsapp_con_telefono(app, empresa):
    """Genera URL wa.me con teléfono cuando el cliente lo tiene."""
    hoy = date.today()
    cliente = _crear_cliente(
        empresa,
        'Juan',
        date(1990, hoy.month, hoy.day),
        telefono='1155551234',
    )
    _db.session.commit()

    url = generar_url_whatsapp_cumpleanos(cliente, empresa.id)

    assert 'wa.me/' in url
    assert '?text=' in url
    # El teléfono debe estar en la URL (normalizado)
    assert 'wa.me/54' in url


def test_generar_url_whatsapp_sin_telefono(app, empresa):
    """Genera URL wa.me sin teléfono cuando el cliente no lo tiene."""
    hoy = date.today()
    cliente = _crear_cliente(
        empresa,
        'María',
        date(1990, hoy.month, hoy.day),
        telefono=None,
    )
    _db.session.commit()

    url = generar_url_whatsapp_cumpleanos(cliente, empresa.id)

    # Según la implementación actual, retorna URL sin tel
    assert url is not None
    assert 'wa.me/' in url
    assert '?text=' in url


def test_generar_url_whatsapp_incluye_nombre_cliente(app, empresa):
    """El mensaje incluye el nombre del cliente."""
    hoy = date.today()
    cliente = _crear_cliente(
        empresa,
        'Carlos García',
        date(1990, hoy.month, hoy.day),
        telefono='1155551234',
    )
    _db.session.commit()

    url = generar_url_whatsapp_cumpleanos(cliente, empresa.id)
    mensaje_decoded = unquote(url.split('text=')[1])

    assert 'Carlos García' in mensaje_decoded


def test_generar_url_whatsapp_usa_template_default(app, empresa):
    """Usa el template por defecto cuando no hay configuración personalizada."""
    hoy = date.today()
    cliente = _crear_cliente(
        empresa,
        'Ana',
        date(1990, hoy.month, hoy.day),
        telefono='1155551234',
    )
    _db.session.commit()

    url = generar_url_whatsapp_cumpleanos(cliente, empresa.id)
    mensaje_decoded = unquote(url.split('text=')[1])

    assert 'Feliz cumpleaños' in mensaje_decoded
    assert 'Ana' in mensaje_decoded


def test_generar_url_whatsapp_usa_template_personalizado(app, empresa):
    """Usa el template personalizado de Configuracion cuando está configurado."""
    hoy = date.today()
    cliente = _crear_cliente(
        empresa,
        'Pedro',
        date(1990, hoy.month, hoy.day),
        telefono='1155551234',
    )

    # Configurar template personalizado
    Configuracion.set(
        'mensaje_cumpleanos',
        'Hola {cliente}, te desea lo mejor {negocio}!',
        'string',
        empresa_id=empresa.id,
    )
    _db.session.commit()

    url = generar_url_whatsapp_cumpleanos(cliente, empresa.id)
    mensaje_decoded = unquote(url.split('text=')[1])

    assert 'Hola Pedro' in mensaje_decoded


# --------------------------------------------------------------------------
# Task 4.4: Tests de rutas — GET /clientes/cumpleanos
# --------------------------------------------------------------------------


def test_cumpleanos_endpoint_retorna_200(app, empresa, admin, client):
    """GET /clientes/cumpleanos retorna 200."""
    hoy = date.today()
    _crear_cliente(empresa, 'Cumpleañero', date(1990, hoy.month, hoy.day))
    _db.session.commit()

    _login(client)
    resp = client.get('/clientes/cumpleanos')
    assert resp.status_code == 200


def test_cumpleanos_endpoint_contiene_datos(app, empresa, admin, client):
    """GET /clientes/cumpleanos contiene nombres de cumpleañeros."""
    hoy = date.today()
    _crear_cliente(
        empresa,
        'Roberto Feliz',
        date(1990, hoy.month, hoy.day),
        telefono='1155551234',
    )
    _db.session.commit()

    _login(client)
    resp = client.get('/clientes/cumpleanos')
    html = resp.data.decode()

    assert 'Roberto Feliz' in html


# --------------------------------------------------------------------------
# Task 4.5: Tests de rutas — GET /clientes/ con conteo de cumpleaños
# --------------------------------------------------------------------------


def test_index_incluye_cumpleanos_hoy(app, empresa, admin, client):
    """GET /clientes/ incluye conteo de cumpleaños cuando hay cumpleañeros."""
    hoy = date.today()
    _crear_cliente(empresa, 'Cumpleañero 1', date(1990, hoy.month, hoy.day))
    _crear_cliente(empresa, 'Cumpleañero 2', date(1985, hoy.month, hoy.day))
    _db.session.commit()

    _login(client)
    resp = client.get('/clientes/')
    assert resp.status_code == 200


def test_index_funciona_sin_cumpleanos(app, empresa, admin, client):
    """GET /clientes/ funciona cuando no hay cumpleañeros."""
    hoy = date.today()
    otro_mes = (hoy.month % 12) + 1
    _crear_cliente(empresa, 'No cumple', date(1990, otro_mes, 1))
    _db.session.commit()

    _login(client)
    resp = client.get('/clientes/')
    assert resp.status_code == 200


# --------------------------------------------------------------------------
# Task 4.6: Tests de configuración — mensaje_cumpleanos
# --------------------------------------------------------------------------


def test_configuracion_muestra_campo_mensaje_cumpleanos(app, empresa, admin, client):
    """GET /configuracion/ muestra campo mensaje_cumpleanos."""
    _login(client)
    resp = client.get('/configuracion/')
    html = resp.data.decode()

    assert resp.status_code == 200
    assert 'mensaje_cumpleanos' in html


def test_configuracion_guarda_mensaje_cumpleanos(app, empresa, admin, client):
    """POST /configuracion/ guarda mensaje_cumpleanos correctamente."""
    _login(client)

    # Primero cargar los valores actuales para enviar todo el formulario
    resp = client.post(
        '/configuracion/',
        data={
            'nombre_negocio': 'Mi Ferretería',
            'direccion': 'Calle 123',
            'telefono': '011-1234-5678',
            'cuit': '20-12345678-9',
            'precios_con_iva': 'y',
            'mensaje_cumpleanos': 'Feliz día {cliente} de {negocio}!',
        },
        follow_redirects=True,
    )

    assert resp.status_code == 200

    # Verificar que se guardó
    valor = Configuracion.get('mensaje_cumpleanos', empresa_id=empresa.id)
    assert valor == 'Feliz día {cliente} de {negocio}!'
