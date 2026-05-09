"""Modelo de Banco."""

from sqlalchemy import UniqueConstraint

from ..extensions import db
from ..utils.helpers import ahora_argentina
from .mixins import EmpresaMixin


class Banco(EmpresaMixin, db.Model):
    """Modelo de banco para cheques."""

    __tablename__ = 'bancos'
    __table_args__ = (
        UniqueConstraint(
            'empresa_id',
            'nombre',
            name='uq_bancos_empresa_nombre',
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=ahora_argentina)

    # Relaciones
    empresa = db.relationship('Empresa', backref='bancos')
    cheques = db.relationship('Cheque', backref='banco', lazy='dynamic')

    def __repr__(self):
        return f'<Banco {self.nombre}>'

    def to_dict(self):
        """Convierte el banco a diccionario."""
        return {
            'id': self.id,
            'nombre': self.nombre,
            'activo': self.activo,
        }
