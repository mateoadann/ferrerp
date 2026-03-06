"""Formulario para cambio obligatorio de contraseña."""

from flask_wtf import FlaskForm
from wtforms import PasswordField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length


class CambiarPasswordForm(FlaskForm):
    """Formulario de cambio de contraseña."""

    password_actual = PasswordField(
        'Contraseña actual',
        validators=[DataRequired(message='Ingresa tu contraseña actual.')],
        render_kw={'placeholder': 'Contraseña actual'},
    )
    password_nueva = PasswordField(
        'Nueva contraseña',
        validators=[
            DataRequired(message='Ingresa la nueva contraseña.'),
            Length(min=6, message='La contraseña debe tener al menos 6 caracteres.'),
        ],
        render_kw={'placeholder': 'Nueva contraseña'},
    )
    password_confirmar = PasswordField(
        'Confirmar nueva contraseña',
        validators=[
            DataRequired(message='Confirma la nueva contraseña.'),
            EqualTo('password_nueva', message='Las contraseñas no coinciden.'),
        ],
        render_kw={'placeholder': 'Confirmar nueva contraseña'},
    )
    submit = SubmitField('Cambiar contraseña')
