"""Tests del modelo Cheque y su integración con formas de pago."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from flask import Blueprint
from flask_login import login_user

from app import create_app
from app.extensions import db
from app.models import Banco, Cheque, Empresa, MovimientoCaja, Usuario, Venta

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


def _crear_cheque(empresa_id, usuario_id, **kwargs):
    """Helper: crea un cheque con datos por defecto."""
    # Si no se pasa banco_id, crear uno automáticamente
    if 'banco_id' not in kwargs:
        banco = Banco.query.filter_by(empresa_id=empresa_id).first()
        if not banco:
            banco = _crear_banco(empresa_id)
        kwargs['banco_id'] = banco.id

    datos = {
        'numero_cheque': '00012345',
        'fecha_emision': date.today(),
        'fecha_vencimiento': date.today() + timedelta(days=30),
        'importe': Decimal('5000.00'),
        'referencia_tipo': 'venta',
        'referencia_id': 1,
        'estado': 'en_cartera',
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
        banco = _crear_banco(empresa.id, 'Banco Galicia')
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            numero_cheque='99887766',
            banco_id=banco.id,
            importe=Decimal('12500.50'),
            referencia_tipo='pago_cc',
            referencia_id=42,
        )

        assert cheque.id is not None
        assert cheque.numero_cheque == '99887766'
        assert cheque.banco_id == banco.id
        assert cheque.banco.nombre == 'Banco Galicia'
        assert cheque.importe == Decimal('12500.50')
        assert cheque.referencia_tipo == 'pago_cc'
        assert cheque.referencia_id == 42
        assert cheque.estado == 'en_cartera'
        assert cheque.tipo_cheque == 'cheque'
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
            'banco_id',
            'banco_nombre',
            'tipo',
            'tipo_cheque',
            'fecha_emision',
            'fecha_vencimiento',
            'importe',
            'referencia_tipo',
            'referencia_id',
            'estado',
            'cliente_id',
            'cliente_nombre',
            'destinatario',
            'observaciones',
            'usuario_nombre',
            'created_at',
        }
        assert set(d.keys()) == claves_esperadas
        assert d['numero_cheque'] == '00012345'
        assert d['banco_nombre'] == 'Banco Nacion'
        assert d['importe'] == 5000.0
        assert d['estado'] == 'en_cartera'
        assert d['tipo_cheque'] == 'cheque'
        assert d['usuario_nombre'] == 'Usuario Cheque'

    def test_tipo_cheque_echeq(self, app):
        """Se puede crear un cheque con tipo_cheque='echeq'."""
        empresa = _crear_empresa()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo_cheque='echeq',
        )

        assert cheque.tipo_cheque == 'echeq'

    def test_cliente_id_nullable(self, app):
        """Un cheque puede no tener cliente_id (emitidos)."""
        empresa = _crear_empresa()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            destinatario='Proveedor X',
            cliente_id=None,
        )

        assert cheque.cliente_id is None

    def test_transiciones_disponibles_recibido(self, app):
        """Un cheque recibido en_cartera tiene 3 transiciones disponibles."""
        empresa = _crear_empresa()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='en_cartera',
        )

        assert set(cheque.transiciones_disponibles) == {
            'endosado', 'cobrado', 'sin_fondos'
        }

    def test_transiciones_disponibles_emitido(self, app):
        """Un cheque emitido en_cartera solo puede ir a cobrado."""
        empresa = _crear_empresa()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='en_cartera',
            destinatario='Proveedor X',
        )

        assert cheque.transiciones_disponibles == ['cobrado']

    def test_transiciones_disponibles_estado_terminal(self, app):
        """Un cheque en estado terminal no tiene transiciones."""
        empresa = _crear_empresa()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='cobrado',
        )

        assert cheque.transiciones_disponibles == []


# ---------------------------------------------------------------------------
# Tests de transición de estado (función helper)
# ---------------------------------------------------------------------------


class TestTransicionValida:
    """Tests de la función transicion_valida."""

    def test_recibido_en_cartera_a_cobrado(self, app):
        from app.models.cheque import transicion_valida
        assert transicion_valida('recibido', 'en_cartera', 'cobrado') is True

    def test_recibido_en_cartera_a_endosado(self, app):
        from app.models.cheque import transicion_valida
        assert transicion_valida('recibido', 'en_cartera', 'endosado') is True

    def test_recibido_en_cartera_a_sin_fondos(self, app):
        from app.models.cheque import transicion_valida
        assert transicion_valida('recibido', 'en_cartera', 'sin_fondos') is True

    def test_emitido_en_cartera_a_cobrado(self, app):
        from app.models.cheque import transicion_valida
        assert transicion_valida('emitido', 'en_cartera', 'cobrado') is True

    def test_emitido_no_puede_endosar(self, app):
        from app.models.cheque import transicion_valida
        assert transicion_valida('emitido', 'en_cartera', 'endosado') is False

    def test_cobrado_no_puede_cambiar(self, app):
        from app.models.cheque import transicion_valida
        assert transicion_valida('recibido', 'cobrado', 'en_cartera') is False

    def test_endosado_no_puede_cambiar(self, app):
        from app.models.cheque import transicion_valida
        assert transicion_valida('recibido', 'endosado', 'cobrado') is False

    def test_sin_fondos_no_puede_cambiar(self, app):
        from app.models.cheque import transicion_valida
        assert transicion_valida('recibido', 'sin_fondos', 'en_cartera') is False


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
# Tests de creación de cheque emitido
# ---------------------------------------------------------------------------


class TestCrearChequeEmitido:
    """Tests de creación de cheques emitidos via POST."""

    def test_crear_cheque_emitido_exitoso(self, app_con_login):
        """POST /ventas/cheques/emitido crea cheque con tipo=emitido."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        banco = _crear_banco(empresa.id, 'Banco Galicia')
        db.session.commit()

        client = _login_client(app_con_login, usuario)

        resp = client.post(
            '/ventas/cheques/emitido',
            data={
                'numero_cheque': '55667788',
                'banco_id': str(banco.id),
                'tipo_cheque': 'cheque',
                'fecha_vencimiento': (
                    date.today() + timedelta(days=30)
                ).isoformat(),
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
        assert cheque.estado == 'en_cartera'
        assert cheque.tipo_cheque == 'cheque'
        assert cheque.destinatario == 'Proveedor ABC'
        assert cheque.importe == Decimal('15000.00')
        assert cheque.banco_id == banco.id
        assert cheque.referencia_tipo is None
        assert cheque.referencia_id is None
        assert cheque.empresa_id == empresa.id
        assert cheque.usuario_id == usuario.id

    def test_crear_cheque_emitido_echeq(self, app_con_login):
        """POST /ventas/cheques/emitido con tipo_cheque=echeq."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        banco = _crear_banco(empresa.id, 'Banco Macro')
        db.session.commit()

        client = _login_client(app_con_login, usuario)

        resp = client.post(
            '/ventas/cheques/emitido',
            data={
                'numero_cheque': '99001122',
                'banco_id': str(banco.id),
                'tipo_cheque': 'echeq',
                'fecha_vencimiento': (
                    date.today() + timedelta(days=60)
                ).isoformat(),
                'importe': '25000.00',
                'destinatario': 'Proveedor ECheq',
            },
            follow_redirects=False,
        )

        assert resp.status_code == 302
        cheque = Cheque.query.filter_by(numero_cheque='99001122').first()
        assert cheque is not None
        assert cheque.tipo_cheque == 'echeq'

    def test_crear_cheque_emitido_sin_destinatario_falla(self, app_con_login):
        """POST /ventas/cheques/emitido sin destinatario redirige con error."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        banco = _crear_banco(empresa.id)
        db.session.commit()

        client = _login_client(app_con_login, usuario)

        resp = client.post(
            '/ventas/cheques/emitido',
            data={
                'numero_cheque': '11111111',
                'banco_id': str(banco.id),
                'tipo_cheque': 'cheque',
                'fecha_vencimiento': (
                    date.today() + timedelta(days=30)
                ).isoformat(),
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
        banco = _crear_banco(empresa.id)
        db.session.commit()

        client = _login_client(app_con_login, usuario)

        resp = client.post(
            '/ventas/cheques/emitido',
            data={
                'numero_cheque': '22222222',
                'banco_id': str(banco.id),
                'tipo_cheque': 'cheque',
                'fecha_vencimiento': (
                    date.today() + timedelta(days=30)
                ).isoformat(),
                'destinatario': 'Proveedor X',
                # importe omitido
            },
            follow_redirects=False,
        )

        assert resp.status_code == 302
        cheque = Cheque.query.filter_by(numero_cheque='22222222').first()
        assert cheque is None


# ---------------------------------------------------------------------------
# Tests de formulario ChequeEmitidoForm
# ---------------------------------------------------------------------------


class TestChequeEmitidoFormValidacion:
    """Tests de validación del formulario ChequeEmitidoForm."""

    def test_form_valido(self, app):
        """Formulario con todos los campos requeridos pasa validación."""
        from app.forms.cheque_forms import ChequeEmitidoForm

        empresa = _crear_empresa()
        usuario = _crear_usuario(empresa.id)
        banco = _crear_banco(empresa.id)
        db.session.commit()

        with app.test_request_context(
            method='POST',
            data={
                'numero_cheque': '12345678',
                'banco_id': str(banco.id),
                'tipo_cheque': 'cheque',
                'fecha_vencimiento': (
                    date.today() + timedelta(days=30)
                ).isoformat(),
                'importe': '10000.00',
                'destinatario': 'Proveedor XYZ',
            },
        ):
            with patch('app.forms.cheque_forms.current_user', usuario):
                form = ChequeEmitidoForm()
                assert form.validate() is True

    def test_form_sin_destinatario_invalido(self, app):
        """Formulario sin destinatario no pasa validación."""
        from app.forms.cheque_forms import ChequeEmitidoForm

        empresa = _crear_empresa()
        usuario = _crear_usuario(empresa.id)
        banco = _crear_banco(empresa.id)
        db.session.commit()

        with app.test_request_context(
            method='POST',
            data={
                'numero_cheque': '12345678',
                'banco_id': str(banco.id),
                'tipo_cheque': 'cheque',
                'fecha_vencimiento': (
                    date.today() + timedelta(days=30)
                ).isoformat(),
                'importe': '10000.00',
                # destinatario omitido
            },
        ):
            with patch('app.forms.cheque_forms.current_user', usuario):
                form = ChequeEmitidoForm()
                assert form.validate() is False
                assert 'destinatario' in form.errors

    def test_form_sin_numero_cheque_invalido(self, app):
        """Formulario sin numero_cheque no pasa validación."""
        from app.forms.cheque_forms import ChequeEmitidoForm

        empresa = _crear_empresa()
        usuario = _crear_usuario(empresa.id)
        banco = _crear_banco(empresa.id)
        db.session.commit()

        with app.test_request_context(
            method='POST',
            data={
                'banco_id': str(banco.id),
                'tipo_cheque': 'cheque',
                'fecha_vencimiento': (
                    date.today() + timedelta(days=30)
                ).isoformat(),
                'importe': '10000.00',
                'destinatario': 'Proveedor XYZ',
            },
        ):
            with patch('app.forms.cheque_forms.current_user', usuario):
                form = ChequeEmitidoForm()
                assert form.validate() is False
                assert 'numero_cheque' in form.errors


# ---------------------------------------------------------------------------
# Tests de cambiar estado (ruta unificada)
# ---------------------------------------------------------------------------


class TestCambiarEstadoCheque:
    """Tests de la ruta POST /ventas/cheques/<id>/cambiar-estado."""

    def test_recibido_en_cartera_a_cobrado(self, app_con_login):
        """Recibido en_cartera -> cobrado es válido."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='en_cartera',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            f'/ventas/cheques/{cheque.id}/cambiar-estado',
            data={'nuevo_estado': 'cobrado'},
        )

        assert resp.status_code == 200
        db.session.refresh(cheque)
        assert cheque.estado == 'cobrado'

    def test_recibido_en_cartera_a_endosado(self, app_con_login):
        """Recibido en_cartera -> endosado es válido."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='en_cartera',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            f'/ventas/cheques/{cheque.id}/cambiar-estado',
            data={'nuevo_estado': 'endosado'},
        )

        assert resp.status_code == 200
        db.session.refresh(cheque)
        assert cheque.estado == 'endosado'

    def test_recibido_en_cartera_a_sin_fondos(self, app_con_login):
        """Recibido en_cartera -> sin_fondos es válido."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='en_cartera',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            f'/ventas/cheques/{cheque.id}/cambiar-estado',
            data={'nuevo_estado': 'sin_fondos'},
        )

        assert resp.status_code == 200
        db.session.refresh(cheque)
        assert cheque.estado == 'sin_fondos'

    def test_emitido_en_cartera_a_cobrado(self, app_con_login):
        """Emitido en_cartera -> cobrado es válido."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='en_cartera',
            destinatario='Proveedor Y',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            f'/ventas/cheques/{cheque.id}/cambiar-estado',
            data={'nuevo_estado': 'cobrado'},
        )

        assert resp.status_code == 200
        db.session.refresh(cheque)
        assert cheque.estado == 'cobrado'

    def test_emitido_no_puede_endosar(self, app_con_login):
        """Emitido en_cartera -> endosado es inválido (retorna 422)."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='en_cartera',
            destinatario='Proveedor Z',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            f'/ventas/cheques/{cheque.id}/cambiar-estado',
            data={'nuevo_estado': 'endosado'},
        )

        assert resp.status_code == 422
        db.session.refresh(cheque)
        assert cheque.estado == 'en_cartera'

    def test_estado_terminal_no_puede_cambiar(self, app_con_login):
        """Un cheque cobrado no puede cambiar de estado (retorna 422)."""
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
        resp = client.post(
            f'/ventas/cheques/{cheque.id}/cambiar-estado',
            data={'nuevo_estado': 'en_cartera'},
        )

        assert resp.status_code == 422
        db.session.refresh(cheque)
        assert cheque.estado == 'cobrado'

    def test_endosado_no_puede_cambiar(self, app_con_login):
        """Un cheque endosado no puede cambiar de estado."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='endosado',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            f'/ventas/cheques/{cheque.id}/cambiar-estado',
            data={'nuevo_estado': 'cobrado'},
        )

        assert resp.status_code == 422
        db.session.refresh(cheque)
        assert cheque.estado == 'endosado'

    def test_sin_nuevo_estado_retorna_422(self, app_con_login):
        """POST sin nuevo_estado retorna 422."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='en_cartera',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            f'/ventas/cheques/{cheque.id}/cambiar-estado',
            data={},
        )

        assert resp.status_code == 422

    def test_multi_tenant_cheque_otra_empresa_404(self, app_con_login):
        """Cambiar estado de cheque de otra empresa retorna 404."""
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
            estado='en_cartera',
            numero_cheque='TENANT001',
        )

        # Usuario A intenta cambiar estado
        client = _login_client(app_con_login, usuario_a)
        resp = client.post(
            f'/ventas/cheques/{cheque_b.id}/cambiar-estado',
            data={'nuevo_estado': 'cobrado'},
        )

        assert resp.status_code == 404
        db.session.refresh(cheque_b)
        assert cheque_b.estado == 'en_cartera'


# ---------------------------------------------------------------------------
# Tests de filtrado por tab en la agenda
# ---------------------------------------------------------------------------


class TestAgendaTabFiltrado:
    """Tests de filtrado por tab en la vista de agenda de cheques."""

    def test_tab_por_cobrar_muestra_solo_recibidos(self, app_con_login):
        """GET /ventas/cheques?tab=por_cobrar muestra solo recibidos en_cartera."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        # Crear cheque recibido en_cartera
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='en_cartera',
            numero_cheque='REC001',
        )
        # Crear cheque emitido en_cartera (no debe aparecer)
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='en_cartera',
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
        """GET /ventas/cheques?tab=por_pagar muestra solo emitidos en_cartera."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='en_cartera',
            numero_cheque='REC002',
        )
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='en_cartera',
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
            estado='en_cartera',
            numero_cheque='REC003',
        )
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='en_cartera',
            numero_cheque='EMI003',
            destinatario='Proveedor Default',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'REC003' in html
        assert 'EMI003' not in html

    def test_cheque_cobrado_no_aparece_en_agenda(self, app_con_login):
        """Un cheque cobrado no aparece en la agenda por_cobrar."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='cobrado',
            numero_cheque='COBRADO001',
        )
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='en_cartera',
            numero_cheque='ACTIVO001',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques?tab=por_cobrar')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'ACTIVO001' in html
        assert 'COBRADO001' not in html


# ---------------------------------------------------------------------------
# Tests de aislamiento multi-tenant
# ---------------------------------------------------------------------------


class TestMultiTenantCheques:
    """Tests de aislamiento entre empresas para cheques."""

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
            estado='en_cartera',
            numero_cheque='EMPA001',
        )
        # Cheques de empresa B
        _crear_cheque(
            empresa_id=empresa_b.id,
            usuario_id=usuario_b.id,
            tipo='recibido',
            estado='en_cartera',
            numero_cheque='EMPB001',
        )

        client = _login_client(app_con_login, usuario_a)
        resp = client.get('/ventas/cheques?tab=por_cobrar')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'EMPA001' in html
        assert 'EMPB001' not in html


# ---------------------------------------------------------------------------
# Tests de Banco CRUD
# ---------------------------------------------------------------------------


class TestBancoCRUD:
    """Tests de las rutas CRUD de bancos."""

    def test_crear_banco(self, app_con_login):
        """POST /ventas/cheques/bancos/ crea un banco."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
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
        assert banco.activo is True

    def test_listar_bancos(self, app_con_login):
        """GET /ventas/cheques/bancos/ muestra los bancos."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        _crear_banco(empresa.id, 'Banco Galicia')
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques/bancos/')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'Banco Galicia' in html

    def test_json_bancos(self, app_con_login):
        """GET /ventas/cheques/bancos/json retorna JSON con bancos activos."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        _crear_banco(empresa.id, 'Banco Macro')
        banco_inactivo = Banco(
            nombre='Banco Cerrado',
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
        assert 'Banco Macro' in nombres
        assert 'Banco Cerrado' not in nombres

    def test_editar_banco(self, app_con_login):
        """POST /ventas/cheques/bancos/<id>/editar actualiza el banco."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
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

    def test_eliminar_banco_sin_cheques_hard_delete(self, app_con_login):
        """DELETE banco sin cheques asociados elimina de la DB."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        banco = _crear_banco(empresa.id, 'Banco Desechable')
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
        """DELETE banco con cheques asociados hace soft delete."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        banco = _crear_banco(empresa.id, 'Banco Referenciado')
        db.session.commit()

        # Crear cheque asociado al banco
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            banco_id=banco.id,
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            f'/ventas/cheques/bancos/{banco.id}/eliminar',
            follow_redirects=False,
        )

        assert resp.status_code == 302
        db.session.refresh(banco)
        assert banco.activo is False  # Soft delete

    def test_duplicar_nombre_mismo_empresa_falla(self, app_con_login):
        """Crear banco con nombre duplicado en misma empresa falla."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        _crear_banco(empresa.id, 'Banco Galicia')
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            '/ventas/cheques/bancos/',
            data={'nombre': 'banco galicia', 'activo': 'y'},
            follow_redirects=True,
        )

        assert resp.status_code == 200
        # Solo debe haber un banco con ese nombre
        bancos = Banco.query.filter_by(
            empresa_id=empresa.id, nombre='Banco Galicia'
        ).all()
        assert len(bancos) == 1

    def test_multi_tenant_banco_aislamiento(self, app_con_login):
        """Bancos de otra empresa no aparecen en el listado."""
        empresa_a = _crear_empresa_aprobada('Empresa A')
        usuario_a = _crear_usuario_con_email(empresa_a.id, 'a5@test.com')
        empresa_b = _crear_empresa_aprobada('Empresa B')
        _crear_banco(empresa_b.id, 'Banco Secreto')
        db.session.commit()

        client = _login_client(app_con_login, usuario_a)
        resp = client.get('/ventas/cheques/bancos/json')

        assert resp.status_code == 200
        data = resp.get_json()
        nombres = [b['nombre'] for b in data]
        assert 'Banco Secreto' not in nombres

    def test_vendedor_puede_acceder_bancos(self, app_con_login):
        """Un vendedor (no admin) puede acceder al CRUD de bancos."""
        empresa = _crear_empresa_aprobada()
        vendedor = Usuario(
            email='vendedor@test.com',
            nombre='Vendedor Test',
            rol='vendedor',
            activo=True,
            empresa_id=empresa.id,
        )
        vendedor.set_password('clave')
        db.session.add(vendedor)
        db.session.commit()

        client = _login_client(app_con_login, vendedor)
        resp = client.get('/ventas/cheques/bancos/')

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests de venta anular -> cheque vuelve a en_cartera
# ---------------------------------------------------------------------------


class TestVentaAnularCheque:
    """Tests de que anular una venta devuelve el cheque a en_cartera."""

    def test_anular_venta_cheque_vuelve_a_en_cartera(self, app_con_login):
        """Al anular una venta, el cheque asociado vuelve a en_cartera."""
        from app.models import Caja, Producto, VentaDetalle

        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        banco = _crear_banco(empresa.id)
        db.session.commit()

        # Crear caja abierta
        caja = Caja(
            usuario_apertura_id=usuario.id,
            monto_inicial=Decimal('10000.00'),
            empresa_id=empresa.id,
        )
        db.session.add(caja)
        db.session.flush()

        # Crear producto
        producto = Producto(
            codigo='TORN001',
            nombre='Tornillo',
            precio_venta=Decimal('100.00'),
            stock_actual=Decimal('50'),
            empresa_id=empresa.id,
        )
        db.session.add(producto)
        db.session.flush()

        # Crear venta
        with patch('app.models.mixins.current_user', usuario):
            venta = Venta(
                numero=1,
                fecha=date.today(),
                usuario_id=usuario.id,
                total=Decimal('100.00'),
                forma_pago='cheque',
                estado='completada',
                empresa_id=empresa.id,
                caja_id=caja.id,
            )
            db.session.add(venta)
            db.session.flush()

        # Crear detalle de venta
        detalle = VentaDetalle(
            venta_id=venta.id,
            producto_id=producto.id,
            cantidad=Decimal('1'),
            precio_unitario=Decimal('100.00'),
            subtotal=Decimal('100.00'),
        )
        db.session.add(detalle)
        db.session.flush()

        # Crear cheque asociado a la venta
        cheque = Cheque(
            numero_cheque='ANULAR001',
            banco_id=banco.id,
            fecha_vencimiento=date.today() + timedelta(days=30),
            importe=Decimal('100.00'),
            tipo='recibido',
            estado='en_cartera',
            referencia_tipo='venta',
            referencia_id=venta.id,
            empresa_id=empresa.id,
            usuario_id=usuario.id,
        )
        db.session.add(cheque)
        db.session.commit()

        # Anular la venta
        client = _login_client(app_con_login, usuario)
        client.post(
            f'/ventas/{venta.id}/anular',
            data={'motivo': 'Test anulacion'},
            follow_redirects=False,
        )

        # Verificar que el cheque volvió a en_cartera (no anulado)
        db.session.refresh(cheque)
        assert cheque.estado == 'en_cartera'
