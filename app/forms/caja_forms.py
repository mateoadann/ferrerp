"""Formularios de caja."""

from flask_wtf import FlaskForm
from wtforms import DecimalField, TextAreaField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Optional, NumberRange, Length


class AperturaCajaForm(FlaskForm):
    """Formulario de apertura de caja."""

    monto_inicial = DecimalField(
        'Monto Inicial',
        validators=[
            DataRequired(message='El monto inicial es requerido'),
            NumberRange(min=0, message='El monto debe ser mayor o igual a 0')
        ],
        places=2,
        render_kw={
            'placeholder': '0,00',
            'step': '0.01',
            'autofocus': True,
            'data-mask': 'money',
            'inputmode': 'decimal'
        }
    )

    submit = SubmitField('Abrir Caja')


class CierreCajaForm(FlaskForm):
    """Formulario de cierre de caja."""

    monto_real = DecimalField(
        'Monto en Caja (Contado)',
        validators=[
            DataRequired(message='El monto es requerido'),
            NumberRange(min=0, message='El monto debe ser mayor o igual a 0')
        ],
        places=2,
        render_kw={
            'placeholder': '0,00',
            'step': '0.01',
            'autofocus': True,
            'data-mask': 'money',
            'inputmode': 'decimal'
        }
    )

    observaciones = TextAreaField(
        'Observaciones',
        validators=[Optional()],
        render_kw={'placeholder': 'Observaciones sobre el cierre de caja', 'rows': 3}
    )

    submit = SubmitField('Cerrar Caja')


class EgresoCajaForm(FlaskForm):
    """Formulario de egreso de caja."""

    concepto = SelectField(
        'Concepto',
        choices=[
            ('pago_proveedor', 'Pago a Proveedor'),
            ('gasto', 'Gasto General'),
            ('retiro', 'Retiro de Efectivo'),
            ('otro', 'Otro')
        ]
    )

    descripcion = StringField(
        'Descripción',
        validators=[
            DataRequired(message='La descripción es requerida'),
            Length(max=200, message='La descripción no puede exceder 200 caracteres')
        ],
        render_kw={'placeholder': 'Describe el egreso'}
    )

    monto = DecimalField(
        'Monto',
        validators=[
            DataRequired(message='El monto es requerido'),
            NumberRange(min=0.01, message='El monto debe ser mayor a 0')
        ],
        places=2,
        render_kw={
            'placeholder': '0,00',
            'step': '0.01',
            'data-mask': 'money',
            'inputmode': 'decimal'
        }
    )

    submit = SubmitField('Registrar Egreso')
