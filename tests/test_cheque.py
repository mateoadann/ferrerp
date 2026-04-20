"""Tests del modelo Cheque y su integración con formas de pago."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from flask import Blueprint
from flask_login import login_user

from app import create_app
from app.extensions import db
from app.models import Cheque, Empresa, MovimientoCaja, Usuario, Venta

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _crear_empresa():
    """Helper: crea una empresa de prueba."""
    empresa = Empresa(nombre='Empresa Test', activa=True)
    db.session.add(empresa)
    db.session.flush()
    return empresa


def _crear_usuario(empresa_id):
    """Helper: crea un usuario de prueba."""
    usuario = Usuario(
        email='cheque@ferrerp.test',
        nombre='Usuario Cheque',
        rol='administrador',
        activo=True,
        empresa_id=empresa_id,
    )
    usuario.set_password('clave')
    db.session.add(usuario)
    db.session.flush()
    return usuario


def _crear_cheque(empresa_id, usuario_id, **kwargs):
    """Helper: crea un cheque con datos por defecto."""
    datos = {
        'numero_cheque': '00012345',
        'banco': 'Banco Nación',
        'fecha_emision': date.today(),
        'fecha_vencimiento': date.today() + timedelta(days=30),
        'importe': Decimal('5000.00'),
        'referencia_tipo': 'venta',
        'referencia_id': 1,
        'estado': 'pendiente',
        'empresa_id': empresa_id,
        'usuario_id': usuario_id,
    }
    datos.update(kwargs)
    cheque = Cheque(**datos)
    db.session.add(cheque)
    db.session.commit()
    return cheque


# ---------------------------------------------------------------------------
# Tests del modelo Cheque
# ---------------------------------------------------------------------------


class TestChequeModelo:
    """Tests de creación y propiedades del modelo Cheque."""

    def test_crear_cheque(self, app):
        """Crear un cheque y verificar que los campos se persisten."""
        empresa = _crear_empresa()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            numero_cheque='99887766',
            banco='Banco Galicia',
            importe=Decimal('12500.50'),
            referencia_tipo='pago_cc',
            referencia_id=42,
        )

        assert cheque.id is not None
        assert cheque.numero_cheque == '99887766'
        assert cheque.banco == 'Banco Galicia'
        assert cheque.importe == Decimal('12500.50')
        assert cheque.referencia_tipo == 'pago_cc'
        assert cheque.referencia_id == 42
        assert cheque.estado == 'pendiente'
        assert cheque.empresa_id == empresa.id
        assert cheque.usuario_id == usuario.id

    def test_cheque_esta_vencido(self, app):
        """Un cheque con fecha_vencimiento en el pasado está vencido."""
        empresa = _crear_empresa()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            fecha_vencimiento=date.today() - timedelta(days=1),
        )

        assert cheque.esta_vencido is True

    def test_cheque_no_vencido(self, app):
        """Un cheque con fecha_vencimiento en el futuro NO está vencido."""
        empresa = _crear_empresa()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            fecha_vencimiento=date.today() + timedelta(days=90),
        )

        assert cheque.esta_vencido is False

    def test_cheque_to_dict(self, app):
        """to_dict retorna todas las claves esperadas."""
        empresa = _crear_empresa()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
        )

        d = cheque.to_dict()

        claves_esperadas = {
            'id',
            'numero_cheque',
            'banco',
            'tipo',
            'fecha_emision',
            'fecha_vencimiento',
            'importe',
            'referencia_tipo',
            'referencia_id',
            'estado',
            'destinatario',
            'observaciones',
            'usuario_nombre',
            'created_at',
        }
        assert set(d.keys()) == claves_esperadas
        assert d['numero_cheque'] == '00012345'
        assert d['banco'] == 'Banco Nación'
        assert d['importe'] == 5000.0
        assert d['estado'] == 'pendiente'
        assert d['usuario_nombre'] == 'Usuario Cheque'


# ---------------------------------------------------------------------------
# Tests de display de forma de pago
# ---------------------------------------------------------------------------


class TestFormaPagoDisplayCheque:
    """Tests de que 'cheque' se muestra como 'Cheque' en los modelos."""

    def test_forma_pago_display_cheque_en_venta(self, app):
        """Venta con forma_pago='cheque' muestra 'Cheque'."""
        from unittest.mock import patch

        empresa = _crear_empresa()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        with patch('app.models.mixins.current_user', usuario):
            venta = Venta(
                numero=1,
                fecha=date.today(),
                usuario_id=usuario.id,
                total=Decimal('1000.00'),
                forma_pago='cheque',
                estado='completada',
                empresa_id=empresa.id,
            )
            db.session.add(venta)
            db.session.commit()

            assert venta.forma_pago_display == 'Cheque'

    def test_movimiento_caja_forma_pago_cheque(self, app):
        """MovimientoCaja con forma_pago='cheque' muestra 'Cheque'."""
        from unittest.mock import patch

        from app.models import Caja

        empresa = _crear_empresa()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        with patch('app.models.mixins.current_user', usuario):
            caja = Caja(
                usuario_apertura_id=usuario.id,
                monto_inicial=Decimal('0.00'),
                empresa_id=empresa.id,
            )
            db.session.add(caja)
            db.session.commit()

            movimiento = MovimientoCaja(
                caja_id=caja.id,
                tipo='ingreso',
                concepto='venta',
                monto=Decimal('5000.00'),
                forma_pago='cheque',
                usuario_id=usuario.id,
            )
            db.session.add(movimiento)
            db.session.commit()

        assert movimiento.forma_pago_display == 'Cheque'


# ---------------------------------------------------------------------------
# Tests de formularios
# ---------------------------------------------------------------------------


class TestFormulariosCheque:
    """Tests de que la opción 'cheque' está en los formularios."""

    def test_venta_form_tiene_opcion_cheque(self, app):
        """VentaForm incluye ('cheque', 'Cheque') en las opciones de forma_pago."""
        from app.forms.venta_forms import VentaForm

        empresa = _crear_empresa()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        with app.test_request_context():
            with patch('app.models.mixins.current_user', usuario):
                form = VentaForm()
                valores = [choice[0] for choice in form.forma_pago.choices]
                assert 'cheque' in valores

    def test_pago_cc_form_tiene_opcion_cheque(self, app):
        """PagoCuentaCorrienteForm incluye ('cheque', 'Cheque') en forma_pago."""
        from app.forms.cliente_forms import PagoCuentaCorrienteForm

        with app.test_request_context():
            form = PagoCuentaCorrienteForm()
            valores = [choice[0] for choice in form.forma_pago.choices]
            assert 'cheque' in valores


# ---------------------------------------------------------------------------
# Fixtures para tests de rutas (necesitan LOGIN_DISABLED=False)
# ---------------------------------------------------------------------------


@pytest.fixture
def app_con_login():
    """App con LOGIN_DISABLED=False para tests de rutas con current_user."""
    app = create_app('testing')
    app.config.update(
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_ENGINE_OPTIONS={},
        WTF_CSRF_ENABLED=False,
        TESTING=True,
        LOGIN_DISABLED=False,
    )

    test_bp = Blueprint('test_cheque_login', __name__)

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


def _crear_empresa_aprobada(nombre='Empresa Test'):
    """Helper: crea una empresa aprobada."""
    empresa = Empresa(nombre=nombre, activa=True, aprobada=True)
    db.session.add(empresa)
    db.session.flush()
    return empresa


def _crear_usuario_con_email(empresa_id, email='cheque@ferrerp.test'):
    """Helper: crea un usuario con email específico."""
    usuario = Usuario(
        email=email,
        nombre='Usuario Cheque',
        rol='administrador',
        activo=True,
        empresa_id=empresa_id,
    )
    usuario.set_password('clave')
    db.session.add(usuario)
    db.session.flush()
    return usuario


def _login_client(app_con_login, usuario):
    """Helper: crea un client HTTP autenticado."""
    client = app_con_login.test_client()
    client.get(f'/test-login/{usuario.id}')
    return client


# ---------------------------------------------------------------------------
# 6.1 Tests de creación de cheque emitido
# ---------------------------------------------------------------------------


class TestCrearChequeEmitido:
    """Tests de creación de cheques emitidos via POST."""

    def test_crear_cheque_emitido_exitoso(self, app_con_login):
        """POST /ventas/cheques/emitido crea cheque con tipo=emitido."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        client = _login_client(app_con_login, usuario)

        resp = client.post(
            '/ventas/cheques/emitido',
            data={
                'numero_cheque': '55667788',
                'banco': 'Banco Galicia',
                'fecha_vencimiento': (date.today() + timedelta(days=30)).isoformat(),
                'importe': '15000.00',
                'destinatario': 'Proveedor ABC',
                'observaciones': 'Pago de factura',
            },
            follow_redirects=False,
        )

        # Debe redirigir a la agenda tab por_pagar
        assert resp.status_code == 302

        cheque = Cheque.query.filter_by(numero_cheque='55667788').first()
        assert cheque is not None
        assert cheque.tipo == 'emitido'
        assert cheque.estado == 'pendiente'
        assert cheque.destinatario == 'Proveedor ABC'
        assert cheque.importe == Decimal('15000.00')
        assert cheque.referencia_tipo is None
        assert cheque.referencia_id is None
        assert cheque.empresa_id == empresa.id
        assert cheque.usuario_id == usuario.id

    def test_crear_cheque_emitido_sin_destinatario_falla(self, app_con_login):
        """POST /ventas/cheques/emitido sin destinatario redirige con error."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        client = _login_client(app_con_login, usuario)

        resp = client.post(
            '/ventas/cheques/emitido',
            data={
                'numero_cheque': '11111111',
                'banco': 'Banco Nación',
                'fecha_vencimiento': (date.today() + timedelta(days=30)).isoformat(),
                'importe': '5000.00',
                # destinatario omitido
            },
            follow_redirects=False,
        )

        # Redirige (validación falla, no crea cheque)
        assert resp.status_code == 302
        cheque = Cheque.query.filter_by(numero_cheque='11111111').first()
        assert cheque is None

    def test_crear_cheque_emitido_sin_importe_falla(self, app_con_login):
        """POST /ventas/cheques/emitido sin importe no crea cheque."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        client = _login_client(app_con_login, usuario)

        resp = client.post(
            '/ventas/cheques/emitido',
            data={
                'numero_cheque': '22222222',
                'banco': 'Banco Nación',
                'fecha_vencimiento': (date.today() + timedelta(days=30)).isoformat(),
                'destinatario': 'Proveedor X',
                # importe omitido
            },
            follow_redirects=False,
        )

        assert resp.status_code == 302
        cheque = Cheque.query.filter_by(numero_cheque='22222222').first()
        assert cheque is None


# ---------------------------------------------------------------------------
# 6.2 Tests de formulario ChequeEmitidoForm
# ---------------------------------------------------------------------------


class TestChequeEmitidoFormValidacion:
    """Tests de validación del formulario ChequeEmitidoForm."""

    def test_form_valido(self, app):
        """Formulario con todos los campos requeridos pasa validación."""
        from app.forms.cheque_forms import ChequeEmitidoForm

        with app.test_request_context(
            method='POST',
            data={
                'numero_cheque': '12345678',
                'banco': 'Banco Nación',
                'fecha_vencimiento': (date.today() + timedelta(days=30)).isoformat(),
                'importe': '10000.00',
                'destinatario': 'Proveedor XYZ',
            },
        ):
            form = ChequeEmitidoForm()
            assert form.validate() is True

    def test_form_sin_destinatario_invalido(self, app):
        """Formulario sin destinatario no pasa validación."""
        from app.forms.cheque_forms import ChequeEmitidoForm

        with app.test_request_context(
            method='POST',
            data={
                'numero_cheque': '12345678',
                'banco': 'Banco Nación',
                'fecha_vencimiento': (date.today() + timedelta(days=30)).isoformat(),
                'importe': '10000.00',
                # destinatario omitido
            },
        ):
            form = ChequeEmitidoForm()
            assert form.validate() is False
            assert 'destinatario' in form.errors

    def test_form_sin_numero_cheque_invalido(self, app):
        """Formulario sin numero_cheque no pasa validación."""
        from app.forms.cheque_forms import ChequeEmitidoForm

        with app.test_request_context(
            method='POST',
            data={
                'banco': 'Banco Nación',
                'fecha_vencimiento': (date.today() + timedelta(days=30)).isoformat(),
                'importe': '10000.00',
                'destinatario': 'Proveedor XYZ',
            },
        ):
            form = ChequeEmitidoForm()
            assert form.validate() is False
            assert 'numero_cheque' in form.errors


# ---------------------------------------------------------------------------
# 6.3 Tests de transición de estado: Cobrar
# ---------------------------------------------------------------------------


class TestTransicionCobrar:
    """Tests de la acción cobrar sobre cheques."""

    def test_cobrar_cheque_recibido_pendiente(self, app_con_login):
        """Cobrar un cheque recibido pendiente cambia estado a cobrado."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='pendiente',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(f'/ventas/cheques/{cheque.id}/cobrar')

        assert resp.status_code == 200
        db.session.refresh(cheque)
        assert cheque.estado == 'cobrado'

    def test_cobrar_cheque_emitido_falla(self, app_con_login):
        """Cobrar un cheque emitido retorna 422."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='pendiente',
            destinatario='Proveedor X',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(f'/ventas/cheques/{cheque.id}/cobrar')

        assert resp.status_code == 422
        db.session.refresh(cheque)
        assert cheque.estado == 'pendiente'

    def test_cobrar_cheque_ya_cobrado_falla(self, app_con_login):
        """Cobrar un cheque que ya está cobrado retorna 422."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='cobrado',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(f'/ventas/cheques/{cheque.id}/cobrar')

        assert resp.status_code == 422
        db.session.refresh(cheque)
        assert cheque.estado == 'cobrado'


# ---------------------------------------------------------------------------
# 6.4 Tests de transición de estado: Debitar
# ---------------------------------------------------------------------------


class TestTransicionDebitar:
    """Tests de la acción debitar sobre cheques."""

    def test_debitar_cheque_emitido_pendiente(self, app_con_login):
        """Debitar un cheque emitido pendiente cambia estado a debitado."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='pendiente',
            destinatario='Proveedor Y',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(f'/ventas/cheques/{cheque.id}/debitar')

        assert resp.status_code == 200
        db.session.refresh(cheque)
        assert cheque.estado == 'debitado'

    def test_debitar_cheque_recibido_falla(self, app_con_login):
        """Debitar un cheque recibido retorna 422."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='pendiente',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(f'/ventas/cheques/{cheque.id}/debitar')

        assert resp.status_code == 422
        db.session.refresh(cheque)
        assert cheque.estado == 'pendiente'

    def test_debitar_cheque_ya_debitado_falla(self, app_con_login):
        """Debitar un cheque que ya está debitado retorna 422."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='debitado',
            destinatario='Proveedor Z',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(f'/ventas/cheques/{cheque.id}/debitar')

        assert resp.status_code == 422
        db.session.refresh(cheque)
        assert cheque.estado == 'debitado'


# ---------------------------------------------------------------------------
# 6.5 Tests de transición de estado: Anular
# ---------------------------------------------------------------------------


class TestTransicionAnular:
    """Tests de la acción anular sobre cheques."""

    def test_anular_cheque_recibido_pendiente(self, app_con_login):
        """Anular un cheque recibido pendiente cambia estado a anulado."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='pendiente',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(f'/ventas/cheques/{cheque.id}/anular')

        assert resp.status_code == 200
        db.session.refresh(cheque)
        assert cheque.estado == 'anulado'

    def test_anular_cheque_emitido_pendiente(self, app_con_login):
        """Anular un cheque emitido pendiente cambia estado a anulado."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='pendiente',
            destinatario='Proveedor W',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(f'/ventas/cheques/{cheque.id}/anular')

        assert resp.status_code == 200
        db.session.refresh(cheque)
        assert cheque.estado == 'anulado'

    def test_anular_cheque_cobrado_falla(self, app_con_login):
        """Anular un cheque cobrado retorna 422."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='cobrado',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(f'/ventas/cheques/{cheque.id}/anular')

        assert resp.status_code == 422
        db.session.refresh(cheque)
        assert cheque.estado == 'cobrado'

    def test_anular_cheque_debitado_falla(self, app_con_login):
        """Anular un cheque debitado retorna 422."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='debitado',
            destinatario='Proveedor V',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(f'/ventas/cheques/{cheque.id}/anular')

        assert resp.status_code == 422
        db.session.refresh(cheque)
        assert cheque.estado == 'debitado'

    def test_anular_cheque_ya_anulado_falla(self, app_con_login):
        """Anular un cheque ya anulado retorna 422."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='anulado',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(f'/ventas/cheques/{cheque.id}/anular')

        assert resp.status_code == 422
        db.session.refresh(cheque)
        assert cheque.estado == 'anulado'


# ---------------------------------------------------------------------------
# 6.6 Tests de filtrado por tab en la agenda
# ---------------------------------------------------------------------------


class TestAgendaTabFiltrado:
    """Tests de filtrado por tab en la vista de agenda de cheques."""

    def test_tab_por_cobrar_muestra_solo_recibidos(self, app_con_login):
        """GET /ventas/cheques?tab=por_cobrar muestra solo recibidos pendientes."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        # Crear cheque recibido pendiente
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='pendiente',
            numero_cheque='REC001',
        )
        # Crear cheque emitido pendiente (no debe aparecer)
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='pendiente',
            numero_cheque='EMI001',
            destinatario='Proveedor Tab',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques?tab=por_cobrar')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'REC001' in html
        assert 'EMI001' not in html

    def test_tab_por_pagar_muestra_solo_emitidos(self, app_con_login):
        """GET /ventas/cheques?tab=por_pagar muestra solo emitidos pendientes."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='pendiente',
            numero_cheque='REC002',
        )
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='pendiente',
            numero_cheque='EMI002',
            destinatario='Proveedor Tab2',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques?tab=por_pagar')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'EMI002' in html
        assert 'REC002' not in html

    def test_tab_default_muestra_por_cobrar(self, app_con_login):
        """GET /ventas/cheques sin tab muestra por_cobrar (recibidos)."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='pendiente',
            numero_cheque='REC003',
        )
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='pendiente',
            numero_cheque='EMI003',
            destinatario='Proveedor Default',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'REC003' in html
        assert 'EMI003' not in html


# ---------------------------------------------------------------------------
# 6.7 Tests de aislamiento multi-tenant
# ---------------------------------------------------------------------------


class TestMultiTenantCheques:
    """Tests de aislamiento entre empresas para cheques."""

    def test_cobrar_cheque_otra_empresa_retorna_404(self, app_con_login):
        """Intentar cobrar cheque de otra empresa retorna 404."""
        empresa_a = _crear_empresa_aprobada('Empresa A')
        usuario_a = _crear_usuario_con_email(empresa_a.id, 'a@test.com')
        empresa_b = _crear_empresa_aprobada('Empresa B')
        usuario_b = _crear_usuario_con_email(empresa_b.id, 'b@test.com')
        db.session.commit()

        # Cheque pertenece a empresa B
        cheque_b = _crear_cheque(
            empresa_id=empresa_b.id,
            usuario_id=usuario_b.id,
            tipo='recibido',
            estado='pendiente',
            numero_cheque='TENANT001',
        )

        # Usuario A intenta cobrar
        client = _login_client(app_con_login, usuario_a)
        resp = client.post(f'/ventas/cheques/{cheque_b.id}/cobrar')

        assert resp.status_code == 404
        db.session.refresh(cheque_b)
        assert cheque_b.estado == 'pendiente'

    def test_debitar_cheque_otra_empresa_retorna_404(self, app_con_login):
        """Intentar debitar cheque de otra empresa retorna 404."""
        empresa_a = _crear_empresa_aprobada('Empresa A')
        usuario_a = _crear_usuario_con_email(empresa_a.id, 'a2@test.com')
        empresa_b = _crear_empresa_aprobada('Empresa B')
        usuario_b = _crear_usuario_con_email(empresa_b.id, 'b2@test.com')
        db.session.commit()

        cheque_b = _crear_cheque(
            empresa_id=empresa_b.id,
            usuario_id=usuario_b.id,
            tipo='emitido',
            estado='pendiente',
            destinatario='Proveedor Tenant',
            numero_cheque='TENANT002',
        )

        client = _login_client(app_con_login, usuario_a)
        resp = client.post(f'/ventas/cheques/{cheque_b.id}/debitar')

        assert resp.status_code == 404
        db.session.refresh(cheque_b)
        assert cheque_b.estado == 'pendiente'

    def test_anular_cheque_otra_empresa_retorna_404(self, app_con_login):
        """Intentar anular cheque de otra empresa retorna 404."""
        empresa_a = _crear_empresa_aprobada('Empresa A')
        usuario_a = _crear_usuario_con_email(empresa_a.id, 'a3@test.com')
        empresa_b = _crear_empresa_aprobada('Empresa B')
        usuario_b = _crear_usuario_con_email(empresa_b.id, 'b3@test.com')
        db.session.commit()

        cheque_b = _crear_cheque(
            empresa_id=empresa_b.id,
            usuario_id=usuario_b.id,
            tipo='recibido',
            estado='pendiente',
            numero_cheque='TENANT003',
        )

        client = _login_client(app_con_login, usuario_a)
        resp = client.post(f'/ventas/cheques/{cheque_b.id}/anular')

        assert resp.status_code == 404
        db.session.refresh(cheque_b)
        assert cheque_b.estado == 'pendiente'

    def test_agenda_solo_muestra_cheques_propia_empresa(self, app_con_login):
        """La agenda solo muestra cheques de la empresa del usuario."""
        empresa_a = _crear_empresa_aprobada('Empresa A')
        usuario_a = _crear_usuario_con_email(empresa_a.id, 'a4@test.com')
        empresa_b = _crear_empresa_aprobada('Empresa B')
        usuario_b = _crear_usuario_con_email(empresa_b.id, 'b4@test.com')
        db.session.commit()

        # Cheques de empresa A
        _crear_cheque(
            empresa_id=empresa_a.id,
            usuario_id=usuario_a.id,
            tipo='recibido',
            estado='pendiente',
            numero_cheque='EMPA001',
        )
        # Cheques de empresa B
        _crear_cheque(
            empresa_id=empresa_b.id,
            usuario_id=usuario_b.id,
            tipo='recibido',
            estado='pendiente',
            numero_cheque='EMPB001',
        )

        client = _login_client(app_con_login, usuario_a)
        resp = client.get('/ventas/cheques?tab=por_cobrar')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'EMPA001' in html
        assert 'EMPB001' not in html
