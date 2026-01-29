"""Formularios de usuarios."""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional, EqualTo, ValidationError


class UsuarioForm(FlaskForm):
    """Formulario de creación de usuario."""

    email = StringField(
        'Email',
        validators=[
            DataRequired(message='El email es requerido'),
            Email(message='Ingresa un email válido'),
            Length(max=120, message='El email no puede exceder 120 caracteres')
        ],
        render_kw={'placeholder': 'usuario@email.com'}
    )

    nombre = StringField(
        'Nombre Completo',
        validators=[
            DataRequired(message='El nombre es requerido'),
            Length(max=100, message='El nombre no puede exceder 100 caracteres')
        ],
        render_kw={'placeholder': 'Nombre y apellido'}
    )

    password = PasswordField(
        'Contraseña',
        validators=[
            DataRequired(message='La contraseña es requerida'),
            Length(min=6, message='La contraseña debe tener al menos 6 caracteres')
        ],
        render_kw={'placeholder': '••••••••'}
    )

    password_confirm = PasswordField(
        'Confirmar Contraseña',
        validators=[
            DataRequired(message='Confirma la contraseña'),
            EqualTo('password', message='Las contraseñas no coinciden')
        ],
        render_kw={'placeholder': '••••••••'}
    )

    rol = SelectField(
        'Rol',
        choices=[
            ('vendedor', 'Vendedor'),
            ('administrador', 'Administrador')
        ],
        default='vendedor'
    )

    activo = BooleanField('Usuario activo', default=True)

    submit = SubmitField('Crear Usuario')

    def validate_email(self, field):
        """Valida que el email no esté registrado."""
        from ..models import Usuario

        usuario = Usuario.query.filter_by(email=field.data.lower()).first()
        if usuario:
            raise ValidationError('Este email ya está registrado.')


class UsuarioEditForm(FlaskForm):
    """Formulario de edición de usuario."""

    email = StringField(
        'Email',
        validators=[
            DataRequired(message='El email es requerido'),
            Email(message='Ingresa un email válido'),
            Length(max=120, message='El email no puede exceder 120 caracteres')
        ],
        render_kw={'placeholder': 'usuario@email.com'}
    )

    nombre = StringField(
        'Nombre Completo',
        validators=[
            DataRequired(message='El nombre es requerido'),
            Length(max=100, message='El nombre no puede exceder 100 caracteres')
        ],
        render_kw={'placeholder': 'Nombre y apellido'}
    )

    password = PasswordField(
        'Nueva Contraseña (dejar vacío para mantener)',
        validators=[
            Optional(),
            Length(min=6, message='La contraseña debe tener al menos 6 caracteres')
        ],
        render_kw={'placeholder': '••••••••'}
    )

    password_confirm = PasswordField(
        'Confirmar Nueva Contraseña',
        validators=[
            EqualTo('password', message='Las contraseñas no coinciden')
        ],
        render_kw={'placeholder': '••••••••'}
    )

    rol = SelectField(
        'Rol',
        choices=[
            ('vendedor', 'Vendedor'),
            ('administrador', 'Administrador')
        ]
    )

    activo = BooleanField('Usuario activo')

    submit = SubmitField('Guardar Cambios')

    def __init__(self, original_email=None, *args, **kwargs):
        super(UsuarioEditForm, self).__init__(*args, **kwargs)
        self.original_email = original_email

    def validate_email(self, field):
        """Valida que el email no esté registrado por otro usuario."""
        from ..models import Usuario

        if field.data.lower() != self.original_email:
            usuario = Usuario.query.filter_by(email=field.data.lower()).first()
            if usuario:
                raise ValidationError('Este email ya está registrado.')
