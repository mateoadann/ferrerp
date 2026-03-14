"""Tests del modelo Facturador y rutas CRUD de facturadores."""

import os
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db as _db
from app.forms.facturador_forms import FacturadorForm
from app.models import Empresa, Usuario
from app.models.facturador import Facturador

os.environ.setdefault('TEST_DATABASE_URL', 'sqlite:///:memory:')


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture
def app():
    """App de testing con login habilitado (las rutas necesitan current_user)."""
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
    """Crea una empresa de prueba."""
    emp = Empresa(nombre='Ferretería Test', activa=True, aprobada=True)
    _db.session.add(emp)
    _db.session.commit()
    return emp


@pytest.fixture
def admin(empresa):
    """Crea un usuario administrador asociado a la empresa."""
    usuario = Usuario(
        email='admin.facturadores@test.com',
        nombre='Admin Facturadores',
        rol='administrador',
        activo=True,
        empresa_id=empresa.id,
    )
    usuario.set_password('test1234')
    _db.session.add(usuario)
    _db.session.commit()
    return usuario


@pytest.fixture
def client(app):
    """Cliente HTTP de prueba."""
    return app.test_client()


def _login(client, usuario):
    """Inicia sesión con el usuario dado."""
    client.post(
        '/auth/login',
        data={'email': usuario.email, 'password': 'test1234'},
        follow_redirects=False,
    )


def _crear_facturador(empresa_id, **kwargs):
    """Helper para crear un facturador de prueba en la BD."""
    defaults = {
        'nombre': 'Sucursal Centro',
        'razon_social': 'Ferretería Test SA',
        'cuit': '20-12345678-3',
        'condicion_iva_id': 1,
        'condicion_iva': 'IVA Responsable Inscripto',
        'punto_venta': 1,
        'ambiente': 'testing',
        'habilitado': False,
        'activo': True,
        'empresa_id': empresa_id,
    }
    defaults.update(kwargs)
    facturador = Facturador(**defaults)
    _db.session.add(facturador)
    _db.session.commit()
    return facturador


# Datos válidos para enviar al formulario de creación/edición
FORM_DATA_VALIDO = {
    'nombre': 'Sucursal Norte',
    'razon_social': 'Ferretería Norte SRL',
    'cuit': '27-98765432-1',
    'condicion_iva_id': '1',
    'punto_venta': '2',
    'ambiente': 'testing',
    'habilitado': '',
}


# =====================================================================
# Tests del modelo Facturador
# =====================================================================


class TestFacturadorModelo:
    """Tests unitarios del modelo Facturador."""

    def test_crear_facturador(self, app, empresa):
        """Crear un facturador y verificar que los campos se persisten."""
        facturador = _crear_facturador(
            empresa.id,
            nombre='Sucursal Sur',
            razon_social='FerreTest SRL',
            cuit='30-71234567-8',
            condicion_iva_id=6,
            condicion_iva='Responsable Monotributo',
            punto_venta=3,
            ambiente='testing',
            domicilio_fiscal='Av. Siempreviva 742',
            email_fiscal='sur@ferretest.com',
        )

        guardado = _db.session.get(Facturador, facturador.id)
        assert guardado is not None
        assert guardado.nombre == 'Sucursal Sur'
        assert guardado.razon_social == 'FerreTest SRL'
        assert guardado.cuit == '30-71234567-8'
        assert guardado.condicion_iva_id == 6
        assert guardado.punto_venta == 3
        assert guardado.domicilio_fiscal == 'Av. Siempreviva 742'
        assert guardado.email_fiscal == 'sur@ferretest.com'
        assert guardado.empresa_id == empresa.id

    def test_facturador_empresa_relationship(self, app, empresa):
        """Verificar que el facturador se asocia a la empresa vía empresa_id."""
        facturador = _crear_facturador(empresa.id)

        assert facturador.empresa_id == empresa.id
        # La FK apunta a la tabla empresas
        guardado = Facturador.query.filter_by(empresa_id=empresa.id).first()
        assert guardado is not None
        assert guardado.id == facturador.id

    def test_facturador_repr(self, app, empresa):
        """Verificar el formato de __repr__."""
        facturador = _crear_facturador(
            empresa.id,
            nombre='Central',
            cuit='20-11111111-1',
            punto_venta=5,
        )

        esperado = '<Facturador Central (20-11111111-1) PV:5>'
        assert repr(facturador) == esperado

    def test_facturador_activo_default(self, app, empresa):
        """Verificar que activo tiene valor por defecto True."""
        facturador = Facturador(
            nombre='Default Test',
            razon_social='Default SA',
            cuit='20-22222222-2',
            condicion_iva_id=1,
            punto_venta=1,
            empresa_id=empresa.id,
        )
        _db.session.add(facturador)
        _db.session.commit()

        guardado = _db.session.get(Facturador, facturador.id)
        assert guardado.activo is True

    def test_facturador_unique_cuit_punto_venta(self, app, empresa):
        """Verificar unique constraint empresa_id + cuit + punto_venta."""
        _crear_facturador(
            empresa.id,
            cuit='20-33333333-3',
            punto_venta=1,
        )

        duplicado = Facturador(
            nombre='Duplicado',
            razon_social='Dup SA',
            cuit='20-33333333-3',
            condicion_iva_id=1,
            punto_venta=1,
            empresa_id=empresa.id,
        )
        _db.session.add(duplicado)
        with pytest.raises(IntegrityError):
            _db.session.commit()
        _db.session.rollback()

    def test_configuracion_completa_con_todos_los_campos(self, app, empresa):
        """Verificar que configuracion_completa es True con todos los datos."""
        facturador = _crear_facturador(
            empresa.id,
            certificado=b'cert-data',
            clave_privada=b'key-data',
        )

        assert facturador.configuracion_completa is True
        assert facturador.campos_faltantes == []

    def test_configuracion_incompleta_sin_certificado(self, app, empresa):
        """Verificar que configuracion_completa es False sin certificado."""
        facturador = _crear_facturador(empresa.id)

        assert facturador.configuracion_completa is False
        assert 'Certificado digital' in facturador.campos_faltantes
        assert 'Clave privada' in facturador.campos_faltantes

    def test_estado_display_activo_habilitado_completo(self, app, empresa):
        """estado_display = 'Activo' cuando está activo, habilitado y completo."""
        facturador = _crear_facturador(
            empresa.id,
            activo=True,
            habilitado=True,
            certificado=b'cert',
            clave_privada=b'key',
        )

        assert facturador.estado_display == 'Activo'

    def test_estado_display_inactivo(self, app, empresa):
        """estado_display = 'Inactivo' cuando activo=False."""
        facturador = _crear_facturador(empresa.id, activo=False)

        assert facturador.estado_display == 'Inactivo'

    def test_estado_display_deshabilitado(self, app, empresa):
        """estado_display = 'Deshabilitado' cuando activo=True pero habilitado=False."""
        facturador = _crear_facturador(
            empresa.id,
            activo=True,
            habilitado=False,
            certificado=b'cert',
            clave_privada=b'key',
        )

        assert facturador.estado_display == 'Deshabilitado'

    def test_estado_display_incompleto(self, app, empresa):
        """estado_display = 'Incompleto' cuando activo y habilitado pero sin cert."""
        facturador = _crear_facturador(
            empresa.id,
            activo=True,
            habilitado=True,
        )

        assert facturador.estado_display == 'Incompleto'

    def test_es_responsable_inscripto(self, app, empresa):
        """Verificar propiedad es_responsable_inscripto."""
        ri = _crear_facturador(empresa.id, condicion_iva_id=1, cuit='20-11111111-1')
        assert ri.es_responsable_inscripto is True

        agente = _crear_facturador(
            empresa.id,
            condicion_iva_id=11,
            cuit='20-44444444-4',
            punto_venta=2,
        )
        assert agente.es_responsable_inscripto is True

        mono = _crear_facturador(
            empresa.id,
            condicion_iva_id=6,
            cuit='20-55555555-5',
            punto_venta=3,
        )
        assert mono.es_responsable_inscripto is False

    def test_es_monotributo(self, app, empresa):
        """Verificar propiedad es_monotributo."""
        mono = _crear_facturador(empresa.id, condicion_iva_id=6)
        assert mono.es_monotributo is True

        ri = _crear_facturador(
            empresa.id,
            condicion_iva_id=1,
            cuit='20-66666666-6',
            punto_venta=2,
        )
        assert ri.es_monotributo is False

    def test_to_dict(self, app, empresa):
        """Verificar que to_dict contiene los campos esperados."""
        facturador = _crear_facturador(
            empresa.id,
            inicio_actividades=date(2020, 1, 15),
        )

        datos = facturador.to_dict()
        assert datos['id'] == facturador.id
        assert datos['empresa_id'] == empresa.id
        assert datos['nombre'] == 'Sucursal Centro'
        assert datos['cuit'] == '20-12345678-3'
        assert datos['punto_venta'] == 1
        assert datos['inicio_actividades'] == '2020-01-15'
        assert 'configuracion_completa' in datos
        assert 'campos_faltantes' in datos
        assert 'estado_display' in datos


# =====================================================================
# Tests de rutas CRUD de facturadores
# =====================================================================


class TestFacturadorRutas:
    """Tests de las rutas CRUD de facturadores."""

    def test_listar_facturadores(self, app, client, admin, empresa):
        """GET /facturacion/facturadores devuelve 200 con listado."""
        _login(client, admin)
        _crear_facturador(empresa.id, nombre='Sucursal Prueba')

        response = client.get('/facturacion/facturadores')

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'Sucursal Prueba' in html

    def test_crear_facturador_get(self, app, client, admin):
        """GET /facturacion/facturadores/nuevo devuelve 200 con formulario."""
        _login(client, admin)

        response = client.get('/facturacion/facturadores/nuevo')

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'Nuevo Facturador' in html

    def test_crear_facturador_post(self, app, client, admin, empresa):
        """POST con datos válidos crea facturador y redirige al listado."""
        _login(client, admin)

        response = client.post(
            '/facturacion/facturadores/nuevo',
            data=FORM_DATA_VALIDO,
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert '/facturacion/facturadores' in response.headers['Location']

        # Verificar que se creó en la BD
        facturador = Facturador.query.filter_by(empresa_id=empresa.id).first()
        assert facturador is not None
        assert facturador.nombre == 'Sucursal Norte'
        assert facturador.razon_social == 'Ferretería Norte SRL'
        assert facturador.cuit == '27-98765432-1'
        assert facturador.punto_venta == 2

    def test_crear_facturador_post_flash_success(self, app, client, admin):
        """POST con datos válidos muestra flash de éxito."""
        _login(client, admin)

        response = client.post(
            '/facturacion/facturadores/nuevo',
            data=FORM_DATA_VALIDO,
            follow_redirects=True,
        )

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'creado correctamente' in html

    def test_crear_facturador_post_sin_nombre(self, app, client, admin):
        """POST sin nombre requerido vuelve al formulario con error."""
        _login(client, admin)

        datos_incompletos = {**FORM_DATA_VALIDO, 'nombre': ''}
        response = client.post(
            '/facturacion/facturadores/nuevo',
            data=datos_incompletos,
        )

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'El nombre es requerido' in html

    def test_crear_facturador_post_cuit_invalido(self, app, client, admin):
        """POST con CUIT inválido muestra error de formato."""
        _login(client, admin)

        datos_cuit_malo = {**FORM_DATA_VALIDO, 'cuit': '123'}
        response = client.post(
            '/facturacion/facturadores/nuevo',
            data=datos_cuit_malo,
        )

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert '11 dígitos' in html

    def test_editar_facturador_get(self, app, client, admin, empresa):
        """GET /facturacion/facturadores/{id}/editar devuelve 200 con form."""
        _login(client, admin)
        facturador = _crear_facturador(empresa.id)

        response = client.get(f'/facturacion/facturadores/{facturador.id}/editar')

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'Editar Facturador' in html
        assert facturador.nombre in html

    def test_editar_facturador_post(self, app, client, admin, empresa):
        """POST con datos válidos actualiza el facturador."""
        _login(client, admin)
        facturador = _crear_facturador(empresa.id)

        datos_editados = {
            **FORM_DATA_VALIDO,
            'nombre': 'Sucursal Renombrada',
            'cuit': facturador.cuit,
            'punto_venta': str(facturador.punto_venta),
        }
        response = client.post(
            f'/facturacion/facturadores/{facturador.id}/editar',
            data=datos_editados,
            follow_redirects=False,
        )

        assert response.status_code == 302

        actualizado = _db.session.get(Facturador, facturador.id)
        assert actualizado.nombre == 'Sucursal Renombrada'

    def test_editar_facturador_post_flash_success(self, app, client, admin, empresa):
        """POST exitoso muestra flash 'actualizado correctamente'."""
        _login(client, admin)
        facturador = _crear_facturador(empresa.id)

        datos_editados = {
            **FORM_DATA_VALIDO,
            'cuit': facturador.cuit,
            'punto_venta': str(facturador.punto_venta),
        }
        response = client.post(
            f'/facturacion/facturadores/{facturador.id}/editar',
            data=datos_editados,
            follow_redirects=True,
        )

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'actualizado correctamente' in html

    def test_editar_facturador_inexistente_404(self, app, client, admin):
        """GET a un facturador que no existe devuelve 404."""
        _login(client, admin)

        response = client.get('/facturacion/facturadores/99999/editar')

        assert response.status_code == 404

    def test_toggle_facturador_desactivar(self, app, client, admin, empresa):
        """POST con accion=desactivar pone activo=False."""
        _login(client, admin)
        facturador = _crear_facturador(empresa.id, activo=True)

        response = client.post(
            f'/facturacion/facturadores/{facturador.id}/toggle',
            data={'accion': 'desactivar'},
            follow_redirects=False,
        )

        assert response.status_code == 302
        actualizado = _db.session.get(Facturador, facturador.id)
        assert actualizado.activo is False

    def test_toggle_facturador_activar(self, app, client, admin, empresa):
        """POST con accion=activar pone activo=True."""
        _login(client, admin)
        facturador = _crear_facturador(empresa.id, activo=False)

        response = client.post(
            f'/facturacion/facturadores/{facturador.id}/toggle',
            data={'accion': 'activar'},
            follow_redirects=False,
        )

        assert response.status_code == 302
        actualizado = _db.session.get(Facturador, facturador.id)
        assert actualizado.activo is True

    def test_toggle_facturador_flash_success(self, app, client, admin, empresa):
        """POST toggle muestra flash de éxito con el estado correcto."""
        _login(client, admin)
        facturador = _crear_facturador(empresa.id, activo=True)

        response = client.post(
            f'/facturacion/facturadores/{facturador.id}/toggle',
            data={'accion': 'desactivar'},
            follow_redirects=True,
        )

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'desactivado correctamente' in html

    def test_probar_conexion_facturador(self, app, client, admin, empresa, monkeypatch):
        """POST probar-conexion retorna JSON con resultado."""
        _login(client, admin)
        facturador = _crear_facturador(
            empresa.id,
            certificado=b'cert',
            clave_privada=b'key',
            habilitado=True,
        )

        class ServicioFake:
            def probar_conexion(self, facturador_obj):
                return {'success': True, 'message': 'Conexión exitosa'}

        from app.routes import facturacion as facturacion_routes

        monkeypatch.setattr(facturacion_routes, 'FacturacionService', ServicioFake)

        response = client.post(
            f'/facturacion/facturadores/{facturador.id}/probar-conexion',
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload['success'] is True

    def test_probar_conexion_facturador_error(self, app, client, admin, empresa, monkeypatch):
        """POST probar-conexion con error retorna 400."""
        _login(client, admin)
        facturador = _crear_facturador(empresa.id)

        class ServicioFake:
            def probar_conexion(self, facturador_obj):
                return {'success': False, 'error': 'Sin certificado'}

        from app.routes import facturacion as facturacion_routes

        monkeypatch.setattr(facturacion_routes, 'FacturacionService', ServicioFake)

        response = client.post(
            f'/facturacion/facturadores/{facturador.id}/probar-conexion',
        )

        assert response.status_code == 400
        payload = response.get_json()
        assert payload['success'] is False

    def test_listar_facturadores_sin_login_redirige(self, app, client):
        """GET sin sesión redirige a login."""
        response = client.get('/facturacion/facturadores')

        assert response.status_code == 302
        assert '/auth/login' in response.headers['Location']


# =====================================================================
# Tests del formulario FacturadorForm
# =====================================================================


class TestFacturadorForm:
    """Tests de validación del formulario FacturadorForm."""

    def test_facturador_form_valid(self, app):
        """Formulario con todos los campos requeridos valida correctamente."""
        with app.test_request_context():
            form = FacturadorForm(
                data={
                    'nombre': 'Sucursal Test',
                    'razon_social': 'Test SRL',
                    'cuit': '20-12345678-3',
                    'condicion_iva_id': 1,
                    'punto_venta': 1,
                    'ambiente': 'testing',
                },
            )

            assert form.validate() is True

    def test_facturador_form_missing_required(self, app):
        """Formulario sin campos requeridos no valida."""
        with app.test_request_context():
            form = FacturadorForm(data={})

            assert form.validate() is False
            assert 'nombre' in form.errors
            assert 'razon_social' in form.errors
            assert 'cuit' in form.errors
            assert 'punto_venta' in form.errors

    def test_facturador_form_punto_venta_fuera_de_rango(self, app):
        """Punto de venta fuera de rango 1-99999 no valida."""
        with app.test_request_context():
            form = FacturadorForm(
                data={
                    'nombre': 'Test',
                    'razon_social': 'Test SA',
                    'cuit': '20-12345678-3',
                    'condicion_iva_id': 1,
                    'punto_venta': 0,
                    'ambiente': 'testing',
                },
            )

            assert form.validate() is False
            assert 'punto_venta' in form.errors

    def test_facturador_form_email_vacio_es_valido(self, app):
        """Email fiscal vacío es válido (campo Optional)."""
        with app.test_request_context():
            form = FacturadorForm(
                data={
                    'nombre': 'Test',
                    'razon_social': 'Test SA',
                    'cuit': '20-12345678-3',
                    'condicion_iva_id': 1,
                    'punto_venta': 1,
                    'ambiente': 'testing',
                    'email_fiscal': '',
                },
            )

            assert form.validate() is True
