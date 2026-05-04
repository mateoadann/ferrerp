"""Tests del modelo Banco y sus rutas CRUD."""

import pytest
from flask import Blueprint
from flask_login import login_user

from app import create_app
from app.extensions import db
from app.models import Banco, Empresa, Usuario

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _crear_empresa_aprobada(nombre='Empresa Test'):
    """Helper: crea una empresa aprobada."""
    empresa = Empresa(nombre=nombre, activa=True, aprobada=True)
    db.session.add(empresa)
    db.session.flush()
    return empresa


def _crear_usuario(empresa_id, email='banco@ferrerp.test', rol='administrador'):
    """Helper: crea un usuario de prueba."""
    usuario = Usuario(
        email=email,
        nombre='Usuario Banco',
        rol=rol,
        activo=True,
        empresa_id=empresa_id,
    )
    usuario.set_password('clave')
    db.session.add(usuario)
    db.session.flush()
    return usuario


def _crear_banco(empresa_id, nombre='Banco Nacion'):
    """Helper: crea un banco de prueba."""
    banco = Banco(
        nombre=nombre,
        empresa_id=empresa_id,
        activo=True,
    )
    db.session.add(banco)
    db.session.flush()
    return banco


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def app_con_login():
    """App con LOGIN_DISABLED=False para tests de rutas."""
    app = create_app('testing')
    app.config.update(
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_ENGINE_OPTIONS={},
        WTF_CSRF_ENABLED=False,
        TESTING=True,
        LOGIN_DISABLED=False,
    )

    test_bp = Blueprint('test_banco_login', __name__)

    @test_bp.route('/test-login/<int:user_id>')
    def test_login(user_id):
        usuario = db.session.get(Usuario, user_id)
        login_user(usuario)
        return 'logged-in'

    with app.app_context():
        app.register_blueprint(test_bp)
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _login_client(app_con_login, usuario):
    """Helper: crea un client HTTP autenticado."""
    client = app_con_login.test_client()
    client.get(f'/test-login/{usuario.id}')
    return client


# ---------------------------------------------------------------------------
# Tests del modelo Banco
# ---------------------------------------------------------------------------


class TestBancoModelo:
    """Tests unitarios del modelo Banco."""

    def test_crear_banco(self, app_con_login):
        """Crear un banco persiste los campos correctamente."""
        empresa = _crear_empresa_aprobada()
        banco = _crear_banco(empresa.id, 'Banco Galicia')
        db.session.commit()

        assert banco.id is not None
        assert banco.nombre == 'Banco Galicia'
        assert banco.empresa_id == empresa.id
        assert banco.activo is True

    def test_to_dict(self, app_con_login):
        """to_dict retorna id, nombre y activo."""
        empresa = _crear_empresa_aprobada()
        banco = _crear_banco(empresa.id, 'Banco Macro')
        db.session.commit()

        d = banco.to_dict()
        assert d == {
            'id': banco.id,
            'nombre': 'Banco Macro',
            'activo': True,
        }

    def test_repr(self, app_con_login):
        """__repr__ muestra nombre del banco."""
        empresa = _crear_empresa_aprobada()
        banco = _crear_banco(empresa.id, 'HSBC')
        db.session.commit()

        assert 'HSBC' in repr(banco)


# ---------------------------------------------------------------------------
# Tests de rutas CRUD
# ---------------------------------------------------------------------------


class TestBancoCRUDRutas:
    """Tests de integración de las rutas de banco."""

    def test_crear_banco_exitoso(self, app_con_login):
        """POST crea banco y redirige."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            '/ventas/cheques/bancos/',
            data={'nombre': 'Banco Nacion', 'activo': 'y'},
            follow_redirects=False,
        )

        assert resp.status_code == 302
        banco = Banco.query.filter_by(
            empresa_id=empresa.id, nombre='Banco Nacion'
        ).first()
        assert banco is not None

    def test_crear_banco_nombre_se_normaliza_title_case(self, app_con_login):
        """El nombre se normaliza a title case."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        client.post(
            '/ventas/cheques/bancos/',
            data={'nombre': 'banco macro', 'activo': 'y'},
        )

        banco = Banco.query.filter_by(empresa_id=empresa.id).first()
        assert banco.nombre == 'Banco Macro'

    def test_crear_banco_duplicado_rechazado(self, app_con_login):
        """No se puede crear un banco con nombre duplicado en misma empresa."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        _crear_banco(empresa.id, 'Banco Galicia')
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            '/ventas/cheques/bancos/',
            data={'nombre': 'banco galicia', 'activo': 'y'},
            follow_redirects=True,
        )

        assert resp.status_code == 200
        bancos = Banco.query.filter_by(
            empresa_id=empresa.id, nombre='Banco Galicia'
        ).all()
        assert len(bancos) == 1

    def test_mismo_nombre_diferente_empresa_ok(self, app_con_login):
        """Dos empresas pueden tener bancos con el mismo nombre."""
        empresa_a = _crear_empresa_aprobada('Empresa A')
        usuario_a = _crear_usuario(empresa_a.id, 'a@test.com')
        empresa_b = _crear_empresa_aprobada('Empresa B')
        _crear_banco(empresa_b.id, 'Banco Galicia')
        db.session.commit()

        client = _login_client(app_con_login, usuario_a)
        resp = client.post(
            '/ventas/cheques/bancos/',
            data={'nombre': 'Banco Galicia', 'activo': 'y'},
            follow_redirects=False,
        )

        assert resp.status_code == 302
        banco_a = Banco.query.filter_by(
            empresa_id=empresa_a.id, nombre='Banco Galicia'
        ).first()
        assert banco_a is not None

    def test_editar_banco(self, app_con_login):
        """POST a editar actualiza el nombre."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        banco = _crear_banco(empresa.id, 'Banco Viejo')
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            f'/ventas/cheques/bancos/{banco.id}/editar',
            data={'nombre': 'Banco Nuevo', 'activo': 'y'},
            follow_redirects=False,
        )

        assert resp.status_code == 302
        db.session.refresh(banco)
        assert banco.nombre == 'Banco Nuevo'

    def test_editar_banco_nombre_duplicado_rechazado(self, app_con_login):
        """Editar banco a un nombre que ya existe es rechazado."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        _crear_banco(empresa.id, 'Banco Galicia')
        banco_b = _crear_banco(empresa.id, 'Banco Macro')
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            f'/ventas/cheques/bancos/{banco_b.id}/editar',
            data={'nombre': 'banco galicia', 'activo': 'y'},
            follow_redirects=True,
        )

        assert resp.status_code == 200
        db.session.refresh(banco_b)
        assert banco_b.nombre == 'Banco Macro'  # No cambió

    def test_eliminar_banco_sin_cheques(self, app_con_login):
        """Eliminar banco sin cheques hace hard delete."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        banco = _crear_banco(empresa.id, 'Banco Descartable')
        banco_id = banco.id
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            f'/ventas/cheques/bancos/{banco_id}/eliminar',
            follow_redirects=False,
        )

        assert resp.status_code == 302
        assert Banco.query.get(banco_id) is None

    def test_eliminar_banco_con_cheques_soft_delete(self, app_con_login):
        """Eliminar banco con cheques hace soft delete (activo=False)."""
        from app.models import Cheque

        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        banco = _crear_banco(empresa.id, 'Banco Referenciado')
        db.session.commit()

        # Crear cheque referenciando este banco
        cheque = Cheque(
            numero_cheque='SOFT001',
            banco_id=banco.id,
            fecha_emision=None,
            fecha_vencimiento=__import__('datetime').date.today(),
            importe=__import__('decimal').Decimal('1000.00'),
            tipo='recibido',
            estado='en_cartera',
            empresa_id=empresa.id,
            usuario_id=usuario.id,
        )
        db.session.add(cheque)
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            f'/ventas/cheques/bancos/{banco.id}/eliminar',
            follow_redirects=False,
        )

        assert resp.status_code == 302
        db.session.refresh(banco)
        assert banco.activo is False

    def test_json_endpoint_solo_activos(self, app_con_login):
        """GET /json retorna solo bancos activos."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario(empresa.id)
        _crear_banco(empresa.id, 'Banco Activo')
        banco_inactivo = Banco(
            nombre='Banco Inactivo',
            empresa_id=empresa.id,
            activo=False,
        )
        db.session.add(banco_inactivo)
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques/bancos/json')

        assert resp.status_code == 200
        data = resp.get_json()
        nombres = [b['nombre'] for b in data]
        assert 'Banco Activo' in nombres
        assert 'Banco Inactivo' not in nombres

    def test_multi_tenant_aislamiento_json(self, app_con_login):
        """JSON solo muestra bancos de la empresa del usuario."""
        empresa_a = _crear_empresa_aprobada('Empresa A')
        usuario_a = _crear_usuario(empresa_a.id, 'a@test.com')
        empresa_b = _crear_empresa_aprobada('Empresa B')
        _crear_banco(empresa_a.id, 'Banco Propio')
        _crear_banco(empresa_b.id, 'Banco Ajeno')
        db.session.commit()

        client = _login_client(app_con_login, usuario_a)
        resp = client.get('/ventas/cheques/bancos/json')

        data = resp.get_json()
        nombres = [b['nombre'] for b in data]
        assert 'Banco Propio' in nombres
        assert 'Banco Ajeno' not in nombres

    def test_vendedor_puede_crear_banco(self, app_con_login):
        """Un vendedor puede crear bancos (no requiere admin)."""
        empresa = _crear_empresa_aprobada()
        vendedor = _crear_usuario(empresa.id, 'vend@test.com', rol='vendedor')
        db.session.commit()

        client = _login_client(app_con_login, vendedor)
        resp = client.post(
            '/ventas/cheques/bancos/',
            data={'nombre': 'Banco Vendedor', 'activo': 'y'},
            follow_redirects=False,
        )

        assert resp.status_code == 302
        banco = Banco.query.filter_by(
            empresa_id=empresa.id, nombre='Banco Vendedor'
        ).first()
        assert banco is not None
