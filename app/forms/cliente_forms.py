"""Formularios de clientes."""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DecimalField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, Optional, Email, NumberRange


class ClienteForm(FlaskForm):
    """Formulario de cliente."""

    nombre = StringField(
        'Nombre',
        validators=[
            DataRequired(message='El nombre es requerido'),
            Length(max=100, message='El nombre no puede exceder 100 caracteres')
        ],
        render_kw={'placeholder': 'Nombre completo o razón social'}
    )

    dni_cuit = StringField(
        'DNI / CUIT',
        validators=[
            Optional(),
            Length(max=13, message='El DNI/CUIT no puede exceder 13 caracteres')
        ],
        render_kw={'placeholder': 'XX-XXXXXXXX-X'}
    )

    telefono = StringField(
        'Teléfono',
        validators=[
            Optional(),
            Length(max=20, message='El teléfono no puede exceder 20 caracteres')
        ],
        render_kw={'placeholder': 'Ej: 11-1234-5678'}
    )

    email = StringField(
        'Email',
        validators=[
            Optional(),
            Email(message='Ingresa un email válido'),
            Length(max=120, message='El email no puede exceder 120 caracteres')
        ],
        render_kw={'placeholder': 'cliente@email.com'}
    )

    direccion = StringField(
        'Dirección',
        validators=[
            Optional(),
            Length(max=200, message='La dirección no puede exceder 200 caracteres')
        ],
        render_kw={'placeholder': 'Calle, número, ciudad'}
    )

    limite_credito = DecimalField(
        'Límite de Crédito',
        validators=[
            Optional(),
            NumberRange(min=0, message='El límite debe ser mayor o igual a 0')
        ],
        places=2,
        default=0,
        render_kw={
            'placeholder': '0,00',
            'step': '0.01',
            'data-mask': 'money',
            'inputmode': 'decimal'
        }
    )

    notas = TextAreaField(
        'Notas',
        validators=[Optional()],
        render_kw={'placeholder': 'Notas adicionales sobre el cliente', 'rows': 3}
    )

    activo = BooleanField('Cliente activo', default=True)

    submit = SubmitField('Guardar Cliente')


class PagoCuentaCorrienteForm(FlaskForm):
    """Formulario de pago de cuenta corriente."""

    monto = DecimalField(
        'Monto a Pagar',
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

    forma_pago = SelectField(
        'Forma de Pago',
        choices=[
            ('efectivo', 'Efectivo'),
            ('tarjeta_debito', 'Tarjeta Débito'),
            ('tarjeta_credito', 'Tarjeta Crédito'),
            ('transferencia', 'Transferencia')
        ],
        default='efectivo',
        validators=[DataRequired(message='Selecciona una forma de pago')]
    )

    descripcion = StringField(
        'Descripción',
        validators=[
            Optional(),
            Length(max=200, message='La descripción no puede exceder 200 caracteres')
        ],
        render_kw={'placeholder': 'Descripción del pago (opcional)'}
    )

    submit = SubmitField('Registrar Pago')
