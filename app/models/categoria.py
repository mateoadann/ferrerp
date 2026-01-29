"""Modelo de Categoría."""

from datetime import datetime
from ..extensions import db


class Categoria(db.Model):
    """Modelo de categoría de productos."""

    __tablename__ = 'categorias'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    descripcion = db.Column(db.String(200))
    activa = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones
    productos = db.relationship('Producto', backref='categoria', lazy='dynamic')

    def __repr__(self):
        return f'<Categoria {self.nombre}>'

    @property
    def cantidad_productos(self):
        """Retorna la cantidad de productos en la categoría."""
        return self.productos.filter_by(activo=True).count()

    def to_dict(self):
        """Convierte la categoría a diccionario."""
        return {
            'id': self.id,
            'nombre': self.nombre,
            'descripcion': self.descripcion,
            'activa': self.activa,
            'cantidad_productos': self.cantidad_productos
        }
