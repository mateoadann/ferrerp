"""Formularios de bancos."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, StringField
from wtforms.validators import DataRequired, Length


class BancoForm(FlaskForm):
    """Formulario para crear/editar un banco."""

    nombre = StringField(
        'Nombre',
        validators=[
            DataRequired(message='El nombre del banco es requerido'),
            Length(
                max=100,
                message='El nombre no puede exceder 100 caracteres',
            ),
        ],
        render_kw={'placeholder': 'Nombre del banco'},
    )

    activo = BooleanField('Activo', default=True)
