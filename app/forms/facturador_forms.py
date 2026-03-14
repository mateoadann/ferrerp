"""Formularios de facturadores."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    BooleanField,
    DateField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional

from ..services.arca_constants import CONDICION_IVA
from ..utils.cuit import cuit_valido

CONDICION_IVA_CHOICES = [(0, 'Seleccionar condición...')] + [
    (k, v) for k, v in CONDICION_IVA.items()
]

AMBIENTE_CHOICES = [
    ('testing', 'Testing (Homologación)'),
    ('production', 'Producción (REAL)'),
]


class FacturadorForm(FlaskForm):
    """Formulario para crear y editar facturadores."""

    nombre = StringField(
        'Nombre',
        validators=[
            DataRequired(message='El nombre es requerido'),
            Length(max=150, message='El nombre no puede exceder 150 caracteres'),
        ],
        render_kw={'placeholder': 'Ej: Sucursal Centro'},
    )

    razon_social = StringField(
        'Razón social',
        validators=[
            DataRequired(message='La razón social es requerida'),
            Length(max=200, message='La razón social no puede exceder 200 caracteres'),
        ],
        render_kw={'placeholder': 'Razón social como figura en ARCA'},
    )

    cuit = StringField(
        'CUIT',
        validators=[
            DataRequired(message='El CUIT es requerido'),
            Length(max=13, message='El CUIT no puede exceder 13 caracteres'),
            cuit_valido,
        ],
        render_kw={'placeholder': 'XX-XXXXXXXX-X'},
    )

    condicion_iva_id = SelectField(
        'Condición frente al IVA',
        choices=CONDICION_IVA_CHOICES,
        coerce=int,
        validators=[
            DataRequired(message='La condición frente al IVA es requerida'),
        ],
    )

    domicilio_fiscal = StringField(
        'Domicilio fiscal',
        validators=[
            Optional(),
            Length(max=300, message='El domicilio no puede exceder 300 caracteres'),
        ],
        render_kw={'placeholder': 'Dirección fiscal completa'},
    )

    numero_iibb = StringField(
        'Número de Ingresos Brutos',
        validators=[
            Optional(),
            Length(max=50, message='El número de IIBB no puede exceder 50 caracteres'),
        ],
        render_kw={'placeholder': 'Ej: CM 20-12345678-9'},
    )

    email_fiscal = StringField(
        'Email fiscal',
        validators=[
            Optional(),
            Email(message='El email no es válido'),
            Length(max=120, message='El email no puede exceder 120 caracteres'),
        ],
        render_kw={'placeholder': 'facturacion@miempresa.com'},
    )

    inicio_actividades = DateField(
        'Inicio de actividades',
        validators=[Optional()],
        format='%Y-%m-%d',
        render_kw={'type': 'date'},
    )

    punto_venta = IntegerField(
        'Punto de venta',
        validators=[
            DataRequired(message='El punto de venta es requerido'),
            NumberRange(
                min=1,
                max=99999,
                message='Debe ser un número entre 1 y 99999',
            ),
        ],
        render_kw={'placeholder': 'Ej: 1'},
    )

    ambiente = SelectField(
        'Ambiente',
        choices=AMBIENTE_CHOICES,
        validators=[DataRequired(message='Seleccioná el ambiente')],
        default='testing',
    )

    habilitado = BooleanField('Habilitar facturación electrónica', default=False)

    certificado = FileField(
        'Certificado ARCA',
        validators=[
            Optional(),
            FileAllowed(
                ['crt', 'pem', 'cer'],
                message='Formato inválido (permitidos: .crt, .pem, .cer)',
            ),
        ],
    )

    clave_privada = FileField(
        'Clave privada',
        validators=[
            Optional(),
            FileAllowed(
                ['key', 'pem'],
                message='Formato inválido (permitidos: .key, .pem)',
            ),
        ],
    )

    submit = SubmitField('Guardar facturador')
