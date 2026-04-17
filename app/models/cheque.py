"""Modelo de Cheque."""

from datetime import date

from ..extensions import db
from ..utils.helpers import ahora_argentina
from .mixins import EmpresaMixin


class Cheque(EmpresaMixin, db.Model):
    """Modelo de cheque recibido como forma de pago."""

    __tablename__ = 'cheques'

    id = db.Column(db.Integer, primary_key=True)
    numero_cheque = db.Column(db.String(50), nullable=False)
    banco = db.Column(db.String(100), nullable=False)
    fecha_emision = db.Column(db.Date, nullable=True)
    fecha_vencimiento = db.Column(db.Date, nullable=False)
    importe = db.Column(db.Numeric(12, 2), nullable=False)
    referencia_tipo = db.Column(db.String(30), nullable=False)  # 'venta', 'pago_cc', 'adelanto_cc'
    referencia_id = db.Column(db.Integer, nullable=False)
    estado = db.Column(db.String(20), nullable=False, default='recibido')
    observaciones = db.Column(db.Text, nullable=True)
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey('usuarios.id'),
        nullable=False
    )
    created_at = db.Column(db.DateTime, default=ahora_argentina, index=True)

    # Relaciones
    empresa = db.relationship('Empresa', backref='cheques')
    usuario = db.relationship('Usuario', backref='cheques')

    def __repr__(self):
        return f'<Cheque {self.id} - #{self.numero_cheque} ${self.importe}>'

    @property
    def esta_vencido(self):
        """Verifica si el cheque está vencido."""
        return self.fecha_vencimiento < date.today()

    def to_dict(self):
        """Convierte el cheque a diccionario."""
        return {
            'id': self.id,
            'numero_cheque': self.numero_cheque,
            'banco': self.banco,
            'fecha_emision': (
                self.fecha_emision.isoformat() if self.fecha_emision else None
            ),
            'fecha_vencimiento': (
                self.fecha_vencimiento.isoformat()
                if self.fecha_vencimiento
                else None
            ),
            'importe': float(self.importe) if self.importe else 0,
            'referencia_tipo': self.referencia_tipo,
            'referencia_id': self.referencia_id,
            'estado': self.estado,
            'observaciones': self.observaciones,
            'usuario_nombre': self.usuario.nombre if self.usuario else None,
            'created_at': (
                self.created_at.isoformat() if self.created_at else None
            ),
        }
