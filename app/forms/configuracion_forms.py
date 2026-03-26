"""Formularios de configuración."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


class ConfiguracionForm(FlaskForm):
    """Formulario de configuración general."""

    nombre_negocio = StringField(
        'Nombre del Negocio',
        validators=[
            DataRequired(message='El nombre es requerido'),
            Length(max=100, message='El nombre no puede exceder 100 caracteres')
        ],
        render_kw={'placeholder': 'Nombre de tu ferretería'}
    )

    direccion = StringField(
        'Dirección',
        validators=[
            Optional(),
            Length(max=200, message='La dirección no puede exceder 200 caracteres')
        ],
        render_kw={'placeholder': 'Calle, número, ciudad'}
    )

    telefono = StringField(
        'Teléfono',
        validators=[
            Optional(),
            Length(max=20, message='El teléfono no puede exceder 20 caracteres')
        ],
        render_kw={'placeholder': 'Ej: 11-1234-5678'}
    )

    cuit = StringField(
        'CUIT',
        validators=[
            Optional(),
            Length(max=13, message='El CUIT no puede exceder 13 caracteres')
        ],
        render_kw={'placeholder': 'XX-XXXXXXXX-X'}
    )

    precios_con_iva = BooleanField('Precios incluyen IVA', default=False)

    mensaje_cumpleanos = TextAreaField(
        'Mensaje de cumpleaños (WhatsApp)',
        validators=[
            Optional(),
            Length(
                max=500,
                message='El mensaje no puede superar los 500 caracteres.',
            ),
        ],
        render_kw={
            'rows': 3,
            'placeholder': '¡Feliz cumpleaños {cliente}! Te saluda {negocio}.',
            'class': 'form-control',
        },
    )

    submit = SubmitField('Guardar Configuración')
