"""Tests del modelo Cheque y su integración con formas de pago."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch



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
        'estado': 'recibido',
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
        assert cheque.estado == 'recibido'
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
            'fecha_emision',
            'fecha_vencimiento',
            'importe',
            'referencia_tipo',
            'referencia_id',
            'estado',
            'observaciones',
            'usuario_nombre',
            'created_at',
        }
        assert set(d.keys()) == claves_esperadas
        assert d['numero_cheque'] == '00012345'
        assert d['banco'] == 'Banco Nación'
        assert d['importe'] == 5000.0
        assert d['estado'] == 'recibido'
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
