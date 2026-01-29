"""Formularios de autenticación."""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length


class LoginForm(FlaskForm):
    """Formulario de inicio de sesión."""

    email = StringField(
        'Email',
        validators=[
            DataRequired(message='El email es requerido'),
            Email(message='Ingresa un email válido')
        ],
        render_kw={'placeholder': 'tu@email.com', 'autofocus': True}
    )

    password = PasswordField(
        'Contraseña',
        validators=[
            DataRequired(message='La contraseña es requerida'),
            Length(min=4, message='La contraseña debe tener al menos 4 caracteres')
        ],
        render_kw={'placeholder': '••••••••'}
    )

    remember = BooleanField('Recordarme')

    submit = SubmitField('Ingresar')
