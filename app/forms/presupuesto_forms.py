"""Formularios de presupuestos."""

from flask_wtf import FlaskForm
from wtforms import (
    SelectField, DecimalField, TextAreaField, HiddenField,
    StringField, IntegerField
)
from wtforms.validators import Optional, NumberRange, DataRequired


class PresupuestoForm(FlaskForm):
    """Formulario de presupuesto."""

    cliente_id = SelectField(
        'Cliente',
        coerce=int,
        validators=[Optional()]
    )

    cliente_nombre = StringField(
        'Nombre del cliente',
        validators=[Optional()],
        render_kw={'placeholder': 'Nombre del cliente'}
    )

    cliente_telefono = StringField(
        'Teléfono',
        validators=[Optional()],
        render_kw={'placeholder': 'Teléfono para WhatsApp'}
    )

    descuento_porcentaje = DecimalField(
        'Descuento (%)',
        validators=[
            Optional(),
            NumberRange(min=0, max=100, message='El descuento debe estar entre 0 y 100')
        ],
        places=2,
        default=0
    )

    validez_dias = IntegerField(
        'Validez (días)',
        validators=[
            Optional(),
            NumberRange(min=1, max=365, message='La validez debe estar entre 1 y 365 días')
        ],
        default=15
    )

    notas = TextAreaField(
        'Notas / Observaciones',
        validators=[Optional()],
        render_kw={'placeholder': 'Observaciones para el cliente...', 'rows': 3}
    )

    items_json = HiddenField('Items')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cargar_clientes()

    def _cargar_clientes(self):
        """Carga las opciones de clientes."""
        from ..models import Cliente
        clientes = Cliente.query.filter_by(activo=True).order_by(Cliente.nombre).all()
        self.cliente_id.choices = [(0, 'Sin cliente')] + [
            (c.id, f'{c.nombre} ({c.dni_cuit or "S/D"})') for c in clientes
        ]


class ConvertirPresupuestoForm(FlaskForm):
    """Formulario para convertir presupuesto a venta."""

    forma_pago = SelectField(
        'Forma de Pago',
        choices=[
            ('efectivo', 'Efectivo'),
            ('tarjeta_debito', 'Tarjeta Débito'),
            ('tarjeta_credito', 'Tarjeta Crédito'),
            ('transferencia', 'Transferencia'),
            ('cuenta_corriente', 'Cuenta Corriente')
        ],
        default='efectivo',
        validators=[DataRequired()]
    )
