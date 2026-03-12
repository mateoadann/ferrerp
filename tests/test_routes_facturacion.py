"""Tests de rutas de facturación."""

import os
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

import pytest

from app import create_app
from app.extensions import db as _db
from app.models import Empresa, Factura, Usuario, Venta
from app.services.arca_exceptions import ArcaValidationError

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite:///:memory:')


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
def client(app):
    return app.test_client()


@pytest.fixture
def admin(app):
    empresa = Empresa(nombre='Empresa Facturacion', activa=True, aprobada=True)
    _db.session.add(empresa)
    _db.session.flush()

    usuario = Usuario(
        email='admin.facturacion@test.com',
        nombre='Admin Facturacion',
        rol='administrador',
        activo=True,
        empresa_id=empresa.id,
    )
    usuario.set_password('test1234')
    _db.session.add(usuario)
    _db.session.commit()

    return usuario


def _login(client, usuario):
    client.post(
        '/auth/login',
        data={'email': usuario.email, 'password': 'test1234'},
        follow_redirects=False,
    )


def _crear_venta(empresa_id, usuario_id):
    venta = Venta(
        numero=1,
        fecha=datetime(2026, 3, 10, 12, 0, 0),
        usuario_id=usuario_id,
        subtotal=Decimal('100.00'),
        descuento_porcentaje=Decimal('0.00'),
        descuento_monto=Decimal('0.00'),
        total=Decimal('100.00'),
        forma_pago='efectivo',
        estado='completada',
        empresa_id=empresa_id,
    )
    _db.session.add(venta)
    _db.session.commit()
    return venta


def test_listado_facturas_renderiza(app, client, admin):
    _login(client, admin)

    factura = Factura(
        venta_id=None,
        empresa_id=admin.empresa_id,
        tipo_comprobante=6,
        punto_venta=1,
        numero_comprobante=10,
        concepto=1,
        fecha_emision=date(2026, 3, 10),
        condicion_iva_receptor_id=5,
        imp_total=Decimal('100.00'),
        estado='autorizada',
        cae='12345678901234',
    )
    _db.session.add(factura)
    _db.session.commit()

    response = client.get('/facturacion/')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Facturación Electrónica' in html
    assert '00001-00000010' in html


def test_emitir_factura_desde_venta_ok(app, client, admin, monkeypatch):
    _login(client, admin)
    venta = _crear_venta(admin.empresa_id, admin.id)

    class ServicioFake:
        def emitir_factura_desde_venta(self, venta_id, empresa_id, **kwargs):
            factura = Factura(
                venta_id=venta_id,
                empresa_id=empresa_id,
                tipo_comprobante=6,
                punto_venta=1,
                numero_comprobante=99,
                concepto=1,
                fecha_emision=date(2026, 3, 10),
                condicion_iva_receptor_id=5,
                imp_total=Decimal('100.00'),
                imp_neto=Decimal('82.64'),
                imp_iva=Decimal('17.36'),
                estado='autorizada',
                cae='12345678901234',
            )
            _db.session.add(factura)
            _db.session.commit()
            return factura

    from app.routes import facturacion as facturacion_routes

    monkeypatch.setattr(facturacion_routes, 'FacturacionService', ServicioFake)

    response = client.post(f'/facturacion/emitir/{venta.id}', follow_redirects=True)

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Factura emitida correctamente' in html
    assert '12345678901234' in html


def test_emitir_factura_muestra_flash_en_error_validacion(app, client, admin, monkeypatch):
    _login(client, admin)
    venta = _crear_venta(admin.empresa_id, admin.id)

    class ServicioFake:
        def emitir_factura_desde_venta(self, venta_id, empresa_id, **kwargs):
            raise ArcaValidationError('Configuración ARCA incompleta.')

    from app.routes import facturacion as facturacion_routes

    monkeypatch.setattr(facturacion_routes, 'FacturacionService', ServicioFake)

    response = client.post(f'/facturacion/emitir/{venta.id}', follow_redirects=True)

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'No se pudo emitir la factura' in html
    assert 'Configuración ARCA incompleta.' in html


def test_configuracion_arca_persiste_campos_y_archivos(app, client, admin):
    _login(client, admin)

    response = client.post(
        '/facturacion/configuracion-arca',
        data={
            'cuit': '20-12345678-3',
            'condicion_iva_id': '1',
            'condicion_iva': 'IVA Responsable Inscripto',
            'punto_venta_arca': '3',
            'ambiente_arca': 'testing',
            'arca_habilitado': 'y',
            'inicio_actividades': '2024-01-10',
            'certificado_arca': (BytesIO(b'certificado-demo'), 'cert.pem'),
            'clave_privada_arca': (BytesIO(b'clave-demo'), 'clave.key'),
        },
        content_type='multipart/form-data',
        follow_redirects=False,
    )

    assert response.status_code == 302

    empresa = _db.session.get(Empresa, admin.empresa_id)
    assert empresa.cuit == '20-12345678-3'
    assert empresa.condicion_iva_id == 1
    assert empresa.condicion_iva == 'IVA Responsable Inscripto'
    assert empresa.punto_venta_arca == 3
    assert empresa.ambiente_arca == 'testing'
    assert empresa.arca_habilitado is True
    assert empresa.inicio_actividades == date(2024, 1, 10)
    assert empresa.certificado_arca == b'certificado-demo'
    assert empresa.clave_privada_arca == b'clave-demo'


def test_consultar_padron_devuelve_json_ok(app, client, admin, monkeypatch):
    _login(client, admin)

    class ServicioPadronFake:
        def consultar_cliente(self, cuit_consulta, empresa):
            return {
                'success': True,
                'data': {
                    'cuit': '20111122223',
                    'razon_social': 'Cliente Prueba SA',
                    'condicion_iva': 'IVA Responsable Inscripto',
                    'condicion_iva_id': 1,
                    'doc_tipo': 80,
                    'doc_nro': '20111122223',
                },
            }

    from app.routes import facturacion as facturacion_routes

    monkeypatch.setattr(facturacion_routes, 'PadronService', ServicioPadronFake)

    response = client.post('/facturacion/padron/consultar', data={'cuit': '20-11112222-3'})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['data']['cuit'] == '20111122223'
    assert payload['data']['razon_social'] == 'Cliente Prueba SA'


def test_consultar_padron_devuelve_error_validacion(app, client, admin, monkeypatch):
    _login(client, admin)

    class ServicioPadronFake:
        def consultar_cliente(self, cuit_consulta, empresa):
            raise ArcaValidationError('El CUIT a consultar debe contener 11 dígitos.')

    from app.routes import facturacion as facturacion_routes

    monkeypatch.setattr(facturacion_routes, 'PadronService', ServicioPadronFake)

    response = client.post('/facturacion/padron/consultar', data={'cuit': '20-123'})

    assert response.status_code == 400
    payload = response.get_json()
    assert payload['success'] is False
    assert '11 dígitos' in payload['error']


def test_consultar_padron_respuesta_negativa_controlada(app, client, admin, monkeypatch):
    _login(client, admin)

    class ServicioPadronFake:
        def consultar_cliente(self, cuit_consulta, empresa):
            return {
                'success': False,
                'error': 'No se encontró información para el CUIT consultado.',
            }

    from app.routes import facturacion as facturacion_routes

    monkeypatch.setattr(facturacion_routes, 'PadronService', ServicioPadronFake)

    response = client.post('/facturacion/padron/consultar', data={'cuit': '20111122223'})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is False
    assert 'No se encontró' in payload['error']
