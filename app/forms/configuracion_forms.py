"""Formularios de configuración."""

from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, NumberRange


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

    iva_porcentaje = DecimalField(
        'IVA (%)',
        validators=[
            Optional(),
            NumberRange(min=0, max=100, message='El IVA debe estar entre 0 y 100')
        ],
        places=2,
        default=21,
        render_kw={'placeholder': '21', 'step': '0.01'}
    )

    precios_con_iva = BooleanField('Precios incluyen IVA', default=True)

    submit = SubmitField('Guardar Configuración')
