"""Formularios de ventas."""

from flask_wtf import FlaskForm
from wtforms import SelectField, DecimalField, TextAreaField, SubmitField, HiddenField
from wtforms.validators import Optional, NumberRange, DataRequired


class VentaForm(FlaskForm):
    """Formulario de venta (punto de venta)."""

    cliente_id = SelectField(
        'Cliente',
        coerce=int,
        validators=[Optional()]
    )

    forma_pago = SelectField(
        'Forma de Pago',
        choices=[
            ('efectivo', 'Efectivo'),
            ('tarjeta_debito', 'Tarjeta Débito'),
            ('tarjeta_credito', 'Tarjeta Crédito'),
            ('transferencia', 'Transferencia'),
            ('cuenta_corriente', 'Cuenta Corriente')
        ],
        default='efectivo'
    )

    descuento_porcentaje = DecimalField(
        'Descuento (%)',
        validators=[
            Optional(),
            NumberRange(min=0, max=100, message='El descuento debe estar entre 0 y 100')
        ],
        places=2,
        default=0,
        render_kw={'placeholder': '0', 'step': '0.01'}
    )

    # Campo oculto para los items del carrito (JSON)
    items_json = HiddenField('Items')

    submit = SubmitField('Confirmar Venta')

    def __init__(self, *args, **kwargs):
        super(VentaForm, self).__init__(*args, **kwargs)
        self._cargar_clientes()

    def _cargar_clientes(self):
        """Carga las opciones de clientes."""
        from ..models import Cliente

        clientes = Cliente.query.filter_by(activo=True).order_by(Cliente.nombre).all()
        self.cliente_id.choices = [(0, 'Consumidor Final')] + [
            (c.id, f'{c.nombre} ({c.dni_cuit or "S/D"})') for c in clientes
        ]


class AnulacionVentaForm(FlaskForm):
    """Formulario de anulación de venta."""

    motivo = TextAreaField(
        'Motivo de Anulación',
        validators=[
            DataRequired(message='El motivo es requerido')
        ],
        render_kw={'placeholder': 'Explica el motivo de la anulación', 'rows': 3}
    )

    submit = SubmitField('Anular Venta')


class DevolucionForm(FlaskForm):
    """Formulario de devolución."""

    motivo = TextAreaField(
        'Motivo de Devolución',
        validators=[
            DataRequired(message='El motivo es requerido')
        ],
        render_kw={'placeholder': 'Explica el motivo de la devolución', 'rows': 3}
    )

    accion = SelectField(
        'Acción',
        choices=[
            ('reintegro_efectivo', 'Reintegro en Efectivo'),
            ('nota_credito', 'Nota de Crédito'),
            ('credito_cuenta_corriente', 'Crédito en Cuenta Corriente')
        ]
    )

    # Campo oculto para los items a devolver (JSON)
    items_json = HiddenField('Items a Devolver')

    submit = SubmitField('Procesar Devolución')
