"""Modelo de Empresa (tenant)."""

from datetime import datetime

from ..extensions import db


class Empresa(db.Model):
    """Modelo de empresa/negocio (tenant del sistema)."""

    __tablename__ = 'empresas'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    cuit = db.Column(db.String(13))
    direccion = db.Column(db.String(200))
    telefono = db.Column(db.String(20))
    email = db.Column(db.String(120))
    activa = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relaciones
    usuarios = db.relationship('Usuario', backref='empresa', lazy='dynamic')

    def __repr__(self):
        return f'<Empresa {self.nombre}>'

    def to_dict(self):
        """Convierte la empresa a diccionario."""
        return {
            'id': self.id,
            'nombre': self.nombre,
            'cuit': self.cuit,
            'direccion': self.direccion,
            'telefono': self.telefono,
            'email': self.email,
            'activa': self.activa,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
