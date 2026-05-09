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
    """Helper: crea un cheque con datos por defecto.

    El estado por defecto se ajusta según el tipo:
    - tipo='recibido' (default) -> estado='en_cartera'
    - tipo='emitido'             -> estado='emitido'
    El caller puede sobreescribir cualquiera con kwargs.
    """
    # Si no se pasa banco_id, crear uno automáticamente
    if 'banco_id' not in kwargs:
        banco = Banco.query.filter_by(empresa_id=empresa_id).first()
        if not banco:
            banco = _crear_banco(empresa_id)
        kwargs['banco_id'] = banco.id

    tipo_default = kwargs.get('tipo', 'recibido')
    estado_default = (
        'emitido' if tipo_default == 'emitido' else 'en_cartera'
    )

    datos = {
        'numero_cheque': '00012345',
        'fecha_emision': date.today(),
        'fecha_vencimiento': date.today() + timedelta(days=30),
        'importe': Decimal('5000.00'),
        'referencia_tipo': 'venta',
        'referencia_id': 1,
        'estado': estado_default,
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
        """Un cheque emitido puede ir a pagado o sin_fondos."""
        empresa = _crear_empresa()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
            destinatario='Proveedor X',
        )

        assert set(cheque.transiciones_disponibles) == {
            'pagado', 'sin_fondos',
        }

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

    def test_emitido_a_pagado(self, app):
        from app.models.cheque import transicion_valida
        assert transicion_valida('emitido', 'emitido', 'pagado') is True

    def test_emitido_a_sin_fondos(self, app):
        from app.models.cheque import transicion_valida
        assert transicion_valida('emitido', 'emitido', 'sin_fondos') is True

    def test_emitido_no_puede_endosar(self, app):
        from app.models.cheque import transicion_valida
        assert transicion_valida('emitido', 'emitido', 'endosado') is False

    def test_emitido_no_puede_estar_en_cartera(self, app):
        """Un cheque emitido no usa el estado 'en_cartera' (es de recibidos)."""
        from app.models.cheque import transicion_valida
        # No definimos transición desde 'en_cartera' para emitidos
        assert transicion_valida('emitido', 'en_cartera', 'pagado') is False

    def test_pagado_es_terminal(self, app):
        """Un cheque emitido pagado no puede cambiar de estado (terminal)."""
        from app.models.cheque import transicion_valida
        assert transicion_valida('emitido', 'pagado', 'sin_fondos') is False
        assert transicion_valida('emitido', 'pagado', 'emitido') is False

    def test_emitido_sin_fondos_es_terminal(self, app):
        """Un cheque emitido sin_fondos es terminal."""
        from app.models.cheque import transicion_valida
        assert transicion_valida('emitido', 'sin_fondos', 'pagado') is False

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
        assert cheque.estado == 'emitido'
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
                'es_echeq': 'y',
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

    def test_crear_cheque_emitido_sin_destinatario_y_sin_cliente_funciona(self, app_con_login):
        """POST /ventas/cheques/emitido sin destinatario ni cliente crea el cheque correctamente."""
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
                # destinatario omitido intencionalmente
            },
            follow_redirects=False,
        )

        # Debe redirigir correctamente (cheque creado)
        assert resp.status_code == 302
        cheque = Cheque.query.filter_by(numero_cheque='11111111').first()
        assert cheque is not None
        assert cheque.tipo == 'emitido'
        assert cheque.cliente_id is None
        assert cheque.destinatario is None or cheque.destinatario == ''

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

    def test_form_sin_destinatario_es_valido(self, app):
        """Formulario sin destinatario pasa validación (destinatario es opcional)."""
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
                assert form.validate() is True

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

    def test_cheque_emitido_transicion_emitido_a_pagado(self, app_con_login):
        """Emitido emitido -> pagado es válido."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
            destinatario='Proveedor Y',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            f'/ventas/cheques/{cheque.id}/cambiar-estado',
            data={'nuevo_estado': 'pagado'},
        )

        assert resp.status_code == 200
        db.session.refresh(cheque)
        assert cheque.estado == 'pagado'

    def test_cheque_emitido_transicion_emitido_a_sin_fondos(self, app_con_login):
        """Emitido emitido -> sin_fondos es válido."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
            destinatario='Proveedor SF',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            f'/ventas/cheques/{cheque.id}/cambiar-estado',
            data={'nuevo_estado': 'sin_fondos'},
        )

        assert resp.status_code == 200
        db.session.refresh(cheque)
        assert cheque.estado == 'sin_fondos'

    def test_cheque_emitido_transicion_invalida_pagado_a_sin_fondos(
        self, app_con_login
    ):
        """Un cheque emitido en estado terminal pagado no puede cambiar."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='pagado',
            destinatario='Proveedor Pagado',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            f'/ventas/cheques/{cheque.id}/cambiar-estado',
            data={'nuevo_estado': 'sin_fondos'},
        )

        assert resp.status_code == 422
        db.session.refresh(cheque)
        assert cheque.estado == 'pagado'

    def test_emitido_no_puede_endosar(self, app_con_login):
        """Emitido emitido -> endosado es inválido (retorna 422)."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
            destinatario='Proveedor Z',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            f'/ventas/cheques/{cheque.id}/cambiar-estado',
            data={'nuevo_estado': 'endosado'},
        )

        assert resp.status_code == 422
        db.session.refresh(cheque)
        assert cheque.estado == 'emitido'

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
        # Crear cheque emitido (estado vivo 'emitido', no debe aparecer)
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
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
            estado='emitido',
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
            estado='emitido',
            numero_cheque='EMI003',
            destinatario='Proveedor Default',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'REC003' in html
        assert 'EMI003' not in html

    def test_cheque_cobrado_aparece_en_agenda(self, app_con_login):
        """Un cheque cobrado aparece en la agenda por_cobrar (se muestran todos)."""
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
        assert 'COBRADO001' in html


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


# ---------------------------------------------------------------------------
# Tests de KPIs monetarios para cheques emitidos
# ---------------------------------------------------------------------------


class TestKpiChequesEmitidos:
    """KPIs Vencidos y Prox. a vencer ahora devuelven monto, no cantidad."""

    def test_kpi_vencidos_devuelve_monto(self, app_con_login):
        """La card 'Vencidos' suma los importes de cheques emitidos vencidos."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        # Dos cheques vencidos por importes distintos
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
            numero_cheque='VENC001',
            destinatario='Proveedor 1',
            importe=Decimal('1000.00'),
            fecha_vencimiento=date.today() - timedelta(days=5),
        )
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
            numero_cheque='VENC002',
            destinatario='Proveedor 2',
            importe=Decimal('2500.50'),
            fecha_vencimiento=date.today() - timedelta(days=1),
        )
        # Otro pagado (no debe contar)
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='pagado',
            numero_cheque='PAG001',
            destinatario='Proveedor 3',
            importe=Decimal('999.99'),
            fecha_vencimiento=date.today() - timedelta(days=10),
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques?tab=por_pagar')

        assert resp.status_code == 200
        html = resp.data.decode()
        # 1000 + 2500.50 = 3500.50; el filter currency formatea con coma
        assert '$3,500.50' in html

    def test_kpi_proximos_devuelve_monto(self, app_con_login):
        """La card 'Prox. a vencer' suma importes de cheques próximos a vencer."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
            numero_cheque='PROX001',
            destinatario='Proveedor 1',
            importe=Decimal('1500.00'),
            fecha_vencimiento=date.today() + timedelta(days=2),
        )
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
            numero_cheque='PROX002',
            destinatario='Proveedor 2',
            importe=Decimal('500.00'),
            fecha_vencimiento=date.today() + timedelta(days=5),
        )
        # Cheque más allá de los 7 días: no cuenta
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
            numero_cheque='LEJOS001',
            destinatario='Proveedor 3',
            importe=Decimal('99999.00'),
            fecha_vencimiento=date.today() + timedelta(days=30),
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques?tab=por_pagar')

        assert resp.status_code == 200
        html = resp.data.decode()
        # 1500 + 500 = 2000.00
        assert '$2,000.00' in html


# ---------------------------------------------------------------------------
# Tests de filtros KPI (renombrado a_cobrar -> a_pagar para emitidos)
# ---------------------------------------------------------------------------


class TestFiltroKpiAPagar:
    """El filtro 'a_pagar' (tab emitidos) filtra cheques con vencimiento <= hoy."""

    def test_filtro_kpi_a_pagar_filtra_emitidos(self, app_con_login):
        """filtro_kpi=a_pagar en tab por_pagar filtra cheques vencidos+hoy."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        # Vencido: debe aparecer
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
            numero_cheque='VENCAPAGAR',
            destinatario='Proveedor V',
            fecha_vencimiento=date.today() - timedelta(days=2),
        )
        # Futuro: no debe aparecer
        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
            numero_cheque='FUTUROAPAGAR',
            destinatario='Proveedor F',
            fecha_vencimiento=date.today() + timedelta(days=30),
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get(
            '/ventas/cheques?tab=por_pagar&filtro_kpi=a_pagar'
        )

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'VENCAPAGAR' in html
        assert 'FUTUROAPAGAR' not in html

    def test_filtro_kpi_a_cobrar_compat_emitidos(self, app_con_login):
        """Compat: 'a_cobrar' en tab por_pagar se trata igual que 'a_pagar'."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
            numero_cheque='COMPATVENC',
            destinatario='Proveedor C',
            fecha_vencimiento=date.today() - timedelta(days=3),
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get(
            '/ventas/cheques?tab=por_pagar&filtro_kpi=a_cobrar'
        )

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'COMPATVENC' in html


# ---------------------------------------------------------------------------
# Tests de estados nuevos para cheques emitidos
# ---------------------------------------------------------------------------


class TestEstadosEmitidos:
    """Tests de los estados específicos para cheques emitidos."""

    def test_etiqueta_estado_emitido(self, app):
        """etiqueta_estado para tipo emitido devuelve etiquetas correctas."""
        from app.models.cheque import etiqueta_estado

        assert etiqueta_estado('emitido', 'emitido') == 'Emitido'
        assert etiqueta_estado('emitido', 'pagado') == 'Pagado'
        assert etiqueta_estado('emitido', 'sin_fondos') == 'Sin fondos'

    def test_etiqueta_estado_recibido(self, app):
        """etiqueta_estado para tipo recibido devuelve etiquetas correctas."""
        from app.models.cheque import etiqueta_estado

        assert etiqueta_estado('recibido', 'en_cartera') == 'En cartera'
        assert etiqueta_estado('recibido', 'cobrado') == 'Cobrado'
        assert etiqueta_estado('recibido', 'endosado') == 'Endosado'
        assert etiqueta_estado('recibido', 'sin_fondos') == 'Sin fondos'

    def test_esta_pendiente_emitido(self, app):
        """esta_pendiente devuelve True para emitido en estado 'emitido'."""
        empresa = _crear_empresa()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        cheque_pendiente = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
            destinatario='Proveedor P',
        )
        assert cheque_pendiente.esta_pendiente is True

    def test_esta_pendiente_emitido_pagado(self, app):
        """esta_pendiente devuelve False para emitido en estado 'pagado'."""
        empresa = _crear_empresa()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        cheque_pagado = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='pagado',
            destinatario='Proveedor Pa',
        )
        assert cheque_pagado.esta_pendiente is False

    def test_esta_pendiente_recibido(self, app):
        """esta_pendiente devuelve True para recibido en_cartera."""
        empresa = _crear_empresa()
        usuario = _crear_usuario(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='en_cartera',
        )
        assert cheque.esta_pendiente is True


# ---------------------------------------------------------------------------
# Tests de detalle y edicion de cheque (modal HTMX)
# ---------------------------------------------------------------------------


class TestDetalleCheque:
    """Tests del endpoint GET /ventas/cheques/<id>/detalle."""

    def test_detalle_cheque_recibido(self, app_con_login):
        """GET detalle devuelve campos del cheque recibido."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        banco = _crear_banco(empresa.id, 'Banco Detalle')
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='en_cartera',
            numero_cheque='DET-REC-001',
            banco_id=banco.id,
            importe=Decimal('7500.00'),
            observaciones='Notas del cheque recibido',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get(f'/ventas/cheques/{cheque.id}/detalle')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'DET-REC-001' in html
        assert 'Banco Detalle' in html
        assert 'Notas del cheque recibido' in html
        # Boton de editar presente
        assert 'Editar' in html

    def test_detalle_cheque_emitido(self, app_con_login):
        """GET detalle de cheque emitido muestra destinatario y observaciones."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
            numero_cheque='DET-EMI-001',
            destinatario='Proveedor Detalle',
            observaciones='Pago factura X',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get(f'/ventas/cheques/{cheque.id}/detalle')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'DET-EMI-001' in html
        assert 'Proveedor Detalle' in html
        assert 'Pago factura X' in html

    def test_detalle_cheque_otra_empresa_404(self, app_con_login):
        """GET detalle de cheque de otra empresa devuelve 404."""
        empresa_a = _crear_empresa_aprobada('Empresa A')
        usuario_a = _crear_usuario_con_email(empresa_a.id, 'a-det@test.com')
        empresa_b = _crear_empresa_aprobada('Empresa B')
        usuario_b = _crear_usuario_con_email(empresa_b.id, 'b-det@test.com')
        db.session.commit()

        cheque_b = _crear_cheque(
            empresa_id=empresa_b.id,
            usuario_id=usuario_b.id,
            tipo='emitido',
            estado='emitido',
            numero_cheque='OTRA-EMP-001',
            destinatario='Proveedor X',
        )

        client = _login_client(app_con_login, usuario_a)
        resp = client.get(f'/ventas/cheques/{cheque_b.id}/detalle')

        assert resp.status_code == 404


class TestEditarCheque:
    """Tests de los endpoints GET/POST /ventas/cheques/<id>/editar."""

    def test_get_editar_cheque_emitido_vivo(self, app_con_login):
        """GET editar de cheque vivo precarga form con todos los campos."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        banco = _crear_banco(empresa.id, 'Banco Edicion')
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
            numero_cheque='EDIT-001',
            banco_id=banco.id,
            importe=Decimal('1234.56'),
            destinatario='Proveedor Edit',
            observaciones='Obs original',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get(f'/ventas/cheques/{cheque.id}/editar')

        assert resp.status_code == 200
        html = resp.data.decode()
        # Valores precargados
        assert 'EDIT-001' in html
        assert 'Proveedor Edit' in html
        assert 'Obs original' in html
        # Boton Guardar cambios
        assert 'Guardar cambios' in html

    def test_editar_cheque_emitido_vivo(self, app_con_login):
        """POST editar permite cambiar todos los campos de un cheque vivo."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        banco_orig = _crear_banco(empresa.id, 'Banco Original')
        banco_nuevo = _crear_banco(empresa.id, 'Banco Nuevo')
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
            numero_cheque='ANTES-001',
            banco_id=banco_orig.id,
            importe=Decimal('1000.00'),
            destinatario='Destinatario Antes',
            observaciones='Antes',
        )
        nueva_fecha = (date.today() + timedelta(days=45)).isoformat()

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            f'/ventas/cheques/{cheque.id}/editar',
            data={
                'numero_cheque': 'DESPUES-001',
                'banco_id': str(banco_nuevo.id),
                'es_echeq': 'y',
                'fecha_vencimiento': nueva_fecha,
                'importe': '2500.50',
                'destinatario': 'Destinatario Despues',
                'observaciones': 'Despues',
            },
        )

        assert resp.status_code == 200
        db.session.refresh(cheque)
        assert cheque.numero_cheque == 'DESPUES-001'
        assert cheque.banco_id == banco_nuevo.id
        assert cheque.tipo_cheque == 'echeq'
        assert cheque.importe == Decimal('2500.50')
        assert cheque.destinatario == 'Destinatario Despues'
        assert cheque.observaciones == 'Despues'

    def test_editar_cheque_emitido_terminal_no_permite_cambiar_numero(
        self, app_con_login
    ):
        """POST a un cheque pagado no cambia numero/banco/importe pero si destinatario/observaciones."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        banco_orig = _crear_banco(empresa.id, 'Banco Orig Terminal')
        banco_otro = _crear_banco(empresa.id, 'Banco Otro Terminal')
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='pagado',  # Estado terminal
            numero_cheque='TERMINAL-001',
            banco_id=banco_orig.id,
            importe=Decimal('5000.00'),
            destinatario='Destinatario Original',
            observaciones='Obs original',
        )
        nueva_fecha = (date.today() + timedelta(days=20)).isoformat()

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            f'/ventas/cheques/{cheque.id}/editar',
            data={
                'numero_cheque': 'INTENTO-CAMBIO',
                'banco_id': str(banco_otro.id),
                'es_echeq': 'y',
                'fecha_vencimiento': nueva_fecha,
                'importe': '99999.99',
                'destinatario': 'Destinatario Nuevo',
                'observaciones': 'Obs nueva',
            },
        )

        assert resp.status_code == 200
        db.session.refresh(cheque)
        # Campos NO editables en estado terminal: se mantienen
        assert cheque.numero_cheque == 'TERMINAL-001'
        assert cheque.banco_id == banco_orig.id
        assert cheque.importe == Decimal('5000.00')
        assert cheque.tipo_cheque == 'cheque'
        # Campos siempre editables: se actualizan
        assert cheque.destinatario == 'Destinatario Nuevo'
        assert cheque.observaciones == 'Obs nueva'
        assert cheque.fecha_vencimiento.isoformat() == nueva_fecha

    def test_editar_cheque_no_permite_cambiar_estado(self, app_con_login):
        """POST con estado en payload no cambia estado del cheque."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
            numero_cheque='ESTADO-001',
            destinatario='Destinatario',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            f'/ventas/cheques/{cheque.id}/editar',
            data={
                'numero_cheque': 'ESTADO-001',
                'banco_id': str(cheque.banco_id),
                'fecha_vencimiento': cheque.fecha_vencimiento.isoformat(),
                'importe': str(cheque.importe),
                'destinatario': 'Destinatario',
                'observaciones': '',
                # Intentamos forzar el cambio de estado
                'estado': 'pagado',
                'tipo': 'recibido',
            },
        )

        assert resp.status_code == 200
        db.session.refresh(cheque)
        # Estado y tipo se mantienen sin cambios
        assert cheque.estado == 'emitido'
        assert cheque.tipo == 'emitido'

    def test_editar_cheque_recibido_terminal_solo_permite_observaciones(
        self, app_con_login
    ):
        """Cheque recibido cobrado: solo se editan obs y fecha de cobro."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        banco = _crear_banco(empresa.id, 'Banco Recibido Term')
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='cobrado',
            numero_cheque='REC-COBRADO-001',
            banco_id=banco.id,
            importe=Decimal('3000.00'),
            observaciones='',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            f'/ventas/cheques/{cheque.id}/editar',
            data={
                'numero_cheque': 'NUEVO-NUM',
                'banco_id': '0',
                'fecha_vencimiento': cheque.fecha_vencimiento.isoformat(),
                'importe': '12345.67',
                'observaciones': 'Cobrado con demora',
            },
        )

        assert resp.status_code == 200
        db.session.refresh(cheque)
        # Numero, banco e importe NO cambian (terminal)
        assert cheque.numero_cheque == 'REC-COBRADO-001'
        assert cheque.banco_id == banco.id
        assert cheque.importe == Decimal('3000.00')
        # Observaciones SI cambia
        assert cheque.observaciones == 'Cobrado con demora'

    def test_editar_cheque_aislamiento_empresa(self, app_con_login):
        """POST editar a un cheque de otra empresa devuelve 404."""
        empresa_a = _crear_empresa_aprobada('Empresa A')
        usuario_a = _crear_usuario_con_email(empresa_a.id, 'a-edit@test.com')
        empresa_b = _crear_empresa_aprobada('Empresa B')
        usuario_b = _crear_usuario_con_email(empresa_b.id, 'b-edit@test.com')
        db.session.commit()

        cheque_b = _crear_cheque(
            empresa_id=empresa_b.id,
            usuario_id=usuario_b.id,
            tipo='emitido',
            estado='emitido',
            numero_cheque='AISLAMIENTO-001',
            destinatario='Proveedor B',
            observaciones='Obs B',
        )

        client = _login_client(app_con_login, usuario_a)
        resp = client.post(
            f'/ventas/cheques/{cheque_b.id}/editar',
            data={
                'numero_cheque': 'HACKEADO',
                'banco_id': '0',
                'fecha_vencimiento': cheque_b.fecha_vencimiento.isoformat(),
                'importe': '1.00',
                'destinatario': 'Hackeado',
                'observaciones': 'Hackeado',
            },
        )

        assert resp.status_code == 404
        # El cheque de B sigue intacto
        db.session.refresh(cheque_b)
        assert cheque_b.numero_cheque == 'AISLAMIENTO-001'
        assert cheque_b.destinatario == 'Proveedor B'
        assert cheque_b.observaciones == 'Obs B'

    def test_editar_cheque_actualiza_fila(self, app_con_login):
        """POST editar dispara HX-Trigger=cheques-actualizados.

        El listado escucha ese evento (wrapper #cheques-tabla-wrapper en
        cheques.html) y refresca la tabla automaticamente, evitando el
        recargar manual que el usuario tenia que hacer antes.
        """
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        banco = _crear_banco(empresa.id, 'Banco Refresh')
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
            numero_cheque='REFRESH-001',
            banco_id=banco.id,
            importe=Decimal('1000.00'),
            destinatario='Antes',
            observaciones='Antes',
        )
        nueva_fecha = (date.today() + timedelta(days=10)).isoformat()

        client = _login_client(app_con_login, usuario)
        resp = client.post(
            f'/ventas/cheques/{cheque.id}/editar',
            data={
                'numero_cheque': 'REFRESH-001',
                'banco_id': str(banco.id),
                'fecha_vencimiento': nueva_fecha,
                'importe': '1000.00',
                'destinatario': 'Despues',
                'observaciones': 'Despues',
            },
        )

        assert resp.status_code == 200
        # El header HX-Trigger es lo que dispara el refresh del listado
        assert resp.headers.get('HX-Trigger') == 'cheques-actualizados'
        # Y los cambios estan persistidos
        db.session.refresh(cheque)
        assert cheque.destinatario == 'Despues'
        assert cheque.observaciones == 'Despues'

    def test_listado_cheques_tiene_listener_de_refresh(
        self, app_con_login
    ):
        """El listado debe tener un wrapper que escuche cheques-actualizados.

        Sin esto, la tabla no se refresca tras editar un cheque.
        """
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques?tab=por_pagar')

        assert resp.status_code == 200
        html = resp.data.decode()
        # Existe el wrapper de la tabla con el id que se reemplaza
        assert 'cheques-tabla-wrapper' in html
        # Y el listener HTMX para el evento cheques-actualizados
        assert 'cheques-actualizados from:body' in html

    def test_listado_cheques_renderiza_link_modal(self, app_con_login):
        """El listado de cheques debe renderizar el numero como link al modal de detalle."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
            numero_cheque='LINK-MODAL-001',
            destinatario='Proveedor Link',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get('/ventas/cheques?tab=por_pagar')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'LINK-MODAL-001' in html
        # El link apunta al endpoint de detalle del cheque
        assert f'/ventas/cheques/{cheque.id}/detalle' in html
        # Existe el contenedor del modal compartido
        assert 'modalChequeContenido' in html


class TestModalDetalleBadgeYCamposVacios:
    """Tests del modal de detalle: badge Echeq y ocultamiento de
    campos opcionales vacios (banco, fecha_emision)."""

    def test_modal_detalle_muestra_badge_echeq(self, app_con_login):
        """El modal debe renderizar el badge cuando tipo_cheque='echeq'."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
            numero_cheque='ECHEQ-BADGE-001',
            tipo_cheque='echeq',
            destinatario='Proveedor Echeq',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get(f'/ventas/cheques/{cheque.id}/detalle')

        assert resp.status_code == 200
        html = resp.data.decode()
        # La clase de la marca minimalista debe estar presente
        assert 'marca-echeq' in html
        # El atributo accesible "Echeq" debe estar presente (title/aria-label)
        assert 'Echeq' in html

    def test_modal_detalle_no_muestra_badge_si_cheque_fisico(
        self, app_con_login
    ):
        """El badge NO debe renderizarse cuando tipo_cheque='cheque'."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='emitido',
            estado='emitido',
            numero_cheque='FISICO-BADGE-001',
            tipo_cheque='cheque',
            destinatario='Proveedor Fisico',
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get(f'/ventas/cheques/{cheque.id}/detalle')

        assert resp.status_code == 200
        html = resp.data.decode()
        # La clase de la marca NO debe estar (cheque fisico = sin marca)
        assert 'marca-echeq' not in html

    def test_modal_detalle_oculta_banco_si_null(self, app_con_login):
        """Si el cheque no tiene banco asociado, la fila Banco se oculta."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        # banco_id=None: cheque recibido sin banco (caso valido en 036)
        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='en_cartera',
            numero_cheque='SIN-BANCO-001',
            banco_id=None,
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get(f'/ventas/cheques/{cheque.id}/detalle')

        assert resp.status_code == 200
        html = resp.data.decode()
        # La fila <dt>Banco</dt> no debe aparecer
        assert '>Banco</dt>' not in html

    def test_modal_detalle_oculta_fecha_emision_si_null(
        self, app_con_login
    ):
        """Si fecha_emision es null, la fila correspondiente se oculta."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='en_cartera',
            numero_cheque='SIN-FE-001',
            fecha_emision=None,
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get(f'/ventas/cheques/{cheque.id}/detalle')

        assert resp.status_code == 200
        html = resp.data.decode()
        # La fila <dt>Fecha emision</dt> no debe aparecer
        assert '>Fecha emision</dt>' not in html

    def test_modal_detalle_muestra_banco_si_existe(self, app_con_login):
        """Si el cheque tiene banco, la fila Banco aparece en el modal."""
        empresa = _crear_empresa_aprobada()
        usuario = _crear_usuario_con_email(empresa.id)
        banco = _crear_banco(empresa.id, 'Banco Visible')
        db.session.commit()

        cheque = _crear_cheque(
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            tipo='recibido',
            estado='en_cartera',
            numero_cheque='CON-BANCO-001',
            banco_id=banco.id,
        )

        client = _login_client(app_con_login, usuario)
        resp = client.get(f'/ventas/cheques/{cheque.id}/detalle')

        assert resp.status_code == 200
        html = resp.data.decode()
        assert '>Banco</dt>' in html
        assert 'Banco Visible' in html
