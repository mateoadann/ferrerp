"""Formularios de registro de empresa y usuario owner."""

from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    Optional,
    ValidationError,
)


class RegistroForm(FlaskForm):
    """Formulario de registro: datos del owner + datos de la empresa."""

    # --- Datos del usuario owner ---
    nombre = StringField(
        'Nombre completo',
        validators=[
            DataRequired(message='El nombre es requerido'),
            Length(max=100),
        ],
        render_kw={'placeholder': 'Tu nombre y apellido'},
    )
    email = StringField(
        'Email',
        validators=[
            DataRequired(message='El email es requerido'),
            Email(message='Ingresá un email válido'),
            Length(max=120),
        ],
        render_kw={'placeholder': 'tu@email.com'},
    )
    password = PasswordField(
        'Contraseña',
        validators=[
            DataRequired(message='La contraseña es requerida'),
            Length(min=6, message='Mínimo 6 caracteres'),
        ],
        render_kw={'placeholder': '••••••••'},
    )
    password_confirm = PasswordField(
        'Confirmar contraseña',
        validators=[
            DataRequired(message='Confirmá la contraseña'),
            EqualTo('password', message='Las contraseñas no coinciden'),
        ],
        render_kw={'placeholder': '••••••••'},
    )

    # --- Datos de la empresa ---
    empresa_nombre = StringField(
        'Nombre del negocio',
        validators=[
            DataRequired(message='El nombre del negocio es requerido'),
            Length(max=150),
        ],
        render_kw={'placeholder': 'Ferretería El Tornillo'},
    )
    empresa_cuit = StringField(
        'CUIT',
        validators=[Optional(), Length(max=13)],
        render_kw={'placeholder': 'XX-XXXXXXXX-X'},
    )
    empresa_direccion = StringField(
        'Dirección',
        validators=[Optional(), Length(max=200)],
        render_kw={'placeholder': 'Calle y número, ciudad'},
    )
    empresa_telefono = StringField(
        'Teléfono',
        validators=[Optional(), Length(max=20)],
        render_kw={'placeholder': '011-1234-5678'},
    )

    submit = SubmitField('Crear cuenta')

    def validate_email(self, field):
        """Valida que el email no esté registrado."""
        from ..models import Usuario

        usuario = Usuario.query.filter_by(email=field.data.lower()).first()
        if usuario:
            raise ValidationError('Este email ya está registrado.')
