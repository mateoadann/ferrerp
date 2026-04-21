"""Formularios de cheques."""

from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, DecimalField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from ..models.banco import Banco


class ChequeEmitidoForm(FlaskForm):
    """Formulario para registrar un cheque emitido."""

    numero_cheque = StringField(
        'Numero de cheque',
        validators=[
            DataRequired(message='El numero de cheque es requerido'),
            Length(max=50, message='El numero no puede exceder 50 caracteres'),
        ],
        render_kw={'placeholder': 'Numero de cheque'},
    )

    banco_id = SelectField(
        'Banco',
        validators=[
            DataRequired(message='El banco es requerido'),
        ],
        coerce=int,
    )

    es_echeq = BooleanField('Echeq', default=False)

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cargar_bancos()

    def _cargar_bancos(self):
        """Carga los bancos activos de la empresa del usuario."""
        try:
            bancos = (
                Banco.query.filter_by(
                    empresa_id=current_user.empresa_id,
                    activo=True,
                )
                .order_by(Banco.nombre)
                .all()
            )
            self.banco_id.choices = [
                (b.id, b.nombre) for b in bancos
            ]
        except Exception:
            self.banco_id.choices = []
