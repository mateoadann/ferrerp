"""Formularios de configuración."""

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
from wtforms.validators import DataRequired, Length, NumberRange, Optional

CONDICIONES_IVA_CHOICES = [
    (0, 'Seleccionar condición...'),
    (1, 'IVA Responsable Inscripto'),
    (4, 'IVA Sujeto Exento'),
    (5, 'Consumidor Final'),
    (6, 'Responsable Monotributo'),
    (8, 'Proveedor del Exterior'),
    (9, 'Cliente del Exterior'),
    (10, 'IVA Liberado - Ley N° 19.640'),
    (11, 'IVA Responsable Inscripto - Agente de Percepción'),
]


class ConfiguracionForm(FlaskForm):
    """Formulario de configuración general."""

    nombre_negocio = StringField(
        'Nombre del Negocio',
        validators=[
            DataRequired(message='El nombre es requerido'),
            Length(max=100, message='El nombre no puede exceder 100 caracteres'),
        ],
        render_kw={'placeholder': 'Nombre de tu ferretería'},
    )

    direccion = StringField(
        'Dirección',
        validators=[
            Optional(),
            Length(max=200, message='La dirección no puede exceder 200 caracteres'),
        ],
        render_kw={'placeholder': 'Calle, número, ciudad'},
    )

    telefono = StringField(
        'Teléfono',
        validators=[
            Optional(),
            Length(max=20, message='El teléfono no puede exceder 20 caracteres'),
        ],
        render_kw={'placeholder': 'Ej: 11-1234-5678'},
    )

    cuit = StringField(
        'CUIT',
        validators=[Optional(), Length(max=13, message='El CUIT no puede exceder 13 caracteres')],
        render_kw={'placeholder': 'XX-XXXXXXXX-X'},
    )

    precios_con_iva = BooleanField('Precios incluyen IVA', default=False)

    submit = SubmitField('Guardar Configuración')


class ConfiguracionArcaForm(FlaskForm):
    """Formulario de configuración ARCA para la empresa."""

    cuit = StringField(
        'CUIT',
        validators=[
            Optional(),
            Length(max=13, message='El CUIT no puede exceder 13 caracteres'),
        ],
        render_kw={'placeholder': 'XX-XXXXXXXX-X'},
    )

    condicion_iva_id = SelectField(
        'Condición frente al IVA',
        choices=CONDICIONES_IVA_CHOICES,
        coerce=int,
        validators=[Optional()],
    )

    condicion_iva = StringField(
        'Descripción condición IVA',
        validators=[
            Optional(),
            Length(max=100, message='La condición no puede exceder 100 caracteres'),
        ],
        render_kw={'placeholder': 'Ej: IVA Responsable Inscripto'},
    )

    punto_venta_arca = IntegerField(
        'Punto de venta ARCA',
        validators=[
            Optional(),
            NumberRange(min=1, max=99999, message='Debe ser un número entre 1 y 99999'),
        ],
        render_kw={'placeholder': '1'},
    )

    ambiente_arca = SelectField(
        'Ambiente ARCA',
        choices=[('testing', 'Testing'), ('production', 'Producción')],
        validators=[DataRequired(message='Selecciona el ambiente ARCA')],
        default='testing',
    )

    arca_habilitado = BooleanField('Habilitar facturación electrónica ARCA', default=False)

    inicio_actividades = DateField(
        'Inicio de actividades',
        validators=[Optional()],
        format='%Y-%m-%d',
        render_kw={'type': 'date'},
    )

    certificado_arca = FileField(
        'Certificado ARCA',
        validators=[
            Optional(),
            FileAllowed(
                ['crt', 'pem', 'cer'],
                message='Formato de certificado inválido (permitidos: .crt, .pem, .cer).',
            ),
        ],
    )

    clave_privada_arca = FileField(
        'Clave privada ARCA',
        validators=[
            Optional(),
            FileAllowed(
                ['key', 'pem'],
                message='Formato de clave inválido (permitidos: .key, .pem).',
            ),
        ],
    )

    submit = SubmitField('Guardar configuración ARCA')
