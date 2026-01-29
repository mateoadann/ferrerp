"""Formularios de proveedores."""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, Email


class ProveedorForm(FlaskForm):
    """Formulario de proveedor."""

    nombre = StringField(
        'Nombre',
        validators=[
            DataRequired(message='El nombre es requerido'),
            Length(max=100, message='El nombre no puede exceder 100 caracteres')
        ],
        render_kw={'placeholder': 'Nombre del proveedor'}
    )

    razon_social = StringField(
        'Razón Social',
        validators=[
            Optional(),
            Length(max=150, message='La razón social no puede exceder 150 caracteres')
        ],
        render_kw={'placeholder': 'Razón social (si aplica)'}
    )

    cuit = StringField(
        'CUIT',
        validators=[
            Optional(),
            Length(max=13, message='El CUIT no puede exceder 13 caracteres')
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
        render_kw={'placeholder': 'proveedor@email.com'}
    )

    direccion = StringField(
        'Dirección',
        validators=[
            Optional(),
            Length(max=200, message='La dirección no puede exceder 200 caracteres')
        ],
        render_kw={'placeholder': 'Calle, número, ciudad'}
    )

    condicion_pago = SelectField(
        'Condición de Pago',
        choices=[
            ('contado', 'Contado'),
            ('30_dias', '30 días'),
            ('60_dias', '60 días')
        ],
        default='contado'
    )

    notas = TextAreaField(
        'Notas',
        validators=[Optional()],
        render_kw={'placeholder': 'Notas adicionales sobre el proveedor', 'rows': 3}
    )

    activo = BooleanField('Proveedor activo', default=True)

    submit = SubmitField('Guardar Proveedor')
