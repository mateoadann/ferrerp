"""Modelo de Proveedor."""

from datetime import datetime
from ..extensions import db


class Proveedor(db.Model):
    """Modelo de proveedor."""

    __tablename__ = 'proveedores'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    razon_social = db.Column(db.String(150))
    cuit = db.Column(db.String(13))
    telefono = db.Column(db.String(20))
    email = db.Column(db.String(120))
    direccion = db.Column(db.String(200))
    condicion_pago = db.Column(
        db.Enum('contado', '30_dias', '60_dias', name='condicion_pago'),
        default='contado'
    )
    notas = db.Column(db.Text)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones
    productos = db.relationship('Producto', backref='proveedor', lazy='dynamic')
    ordenes_compra = db.relationship('OrdenCompra', backref='proveedor', lazy='dynamic')

    def __repr__(self):
        return f'<Proveedor {self.nombre}>'

    @property
    def condicion_pago_display(self):
        """Retorna la condición de pago en formato legible."""
        opciones = {
            'contado': 'Contado',
            '30_dias': '30 días',
            '60_dias': '60 días'
        }
        return opciones.get(self.condicion_pago, self.condicion_pago)

    def to_dict(self):
        """Convierte el proveedor a diccionario."""
        return {
            'id': self.id,
            'nombre': self.nombre,
            'razon_social': self.razon_social,
            'cuit': self.cuit,
            'telefono': self.telefono,
            'email': self.email,
            'direccion': self.direccion,
            'condicion_pago': self.condicion_pago,
            'activo': self.activo
        }
