"""Formularios de cheques."""

from flask_wtf import FlaskForm
from wtforms import DateField, DecimalField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class ChequeEmitidoForm(FlaskForm):
    """Formulario para registrar un cheque emitido."""

    numero_cheque = StringField(
        'Número de cheque',
        validators=[
            DataRequired(message='El número de cheque es requerido'),
            Length(max=50, message='El número no puede exceder 50 caracteres'),
        ],
        render_kw={'placeholder': 'Número de cheque'},
    )

    banco = StringField(
        'Banco',
        validators=[
            DataRequired(message='El banco es requerido'),
            Length(max=100, message='El banco no puede exceder 100 caracteres'),
        ],
        render_kw={'placeholder': 'Nombre del banco'},
    )

    fecha_vencimiento = DateField(
        'Fecha de vencimiento',
        validators=[
            DataRequired(message='La fecha de vencimiento es requerida'),
        ],
        format='%Y-%m-%d',
    )

    importe = DecimalField(
        'Importe',
        validators=[
            DataRequired(message='El importe es requerido'),
            NumberRange(
                min=0.01,
                message='El importe debe ser mayor a cero',
            ),
        ],
        places=2,
        render_kw={'placeholder': '0.00', 'step': '0.01', 'min': '0.01'},
    )

    destinatario = StringField(
        'Destinatario',
        validators=[
            DataRequired(message='El destinatario es requerido'),
            Length(
                max=200,
                message='El destinatario no puede exceder 200 caracteres',
            ),
        ],
        render_kw={'placeholder': 'Nombre del destinatario'},
    )

    observaciones = TextAreaField(
        'Observaciones',
        validators=[Optional()],
        render_kw={'placeholder': 'Observaciones (opcional)', 'rows': 3},
    )
