"""Modelo de Categoría."""

from sqlalchemy import UniqueConstraint

from ..extensions import db
from ..utils.helpers import ahora_argentina
from .mixins import EmpresaMixin


class Categoria(EmpresaMixin, db.Model):
    """Modelo de categoría de productos."""

    __tablename__ = 'categorias'
    __table_args__ = (
        UniqueConstraint(
            'empresa_id',
            'nombre',
            'padre_id',
            name='uq_categorias_empresa_nombre_padre_id',
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.String(200))
    padre_id = db.Column(db.Integer, db.ForeignKey('categorias.id'), index=True)
    activa = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=ahora_argentina)

    # Relaciones
    productos = db.relationship('Producto', backref='categoria', lazy='dynamic')
    subcategorias = db.relationship(
        'Categoria',
        backref=db.backref('padre', remote_side=[id]),
        lazy='select',
        cascade='all, delete-orphan',
        single_parent=True,
    )

    def __repr__(self):
        return f'<Categoria {self.nombre}>'

    @property
    def cantidad_productos(self):
        """Retorna la cantidad de productos en la categoría."""
        return self.productos.filter_by(activo=True).count()

    @property
    def es_padre(self):
        """Indica si la categoría es de nivel padre."""
        return self.padre_id is None

    @property
    def nombre_completo(self):
        """Retorna el nombre completo en formato jerárquico."""
        if self.padre:
            return f'{self.padre.nombre} > {self.nombre}'
        return self.nombre

    @property
    def tiene_productos(self):
        """Verifica si tiene algún producto asociado (activo o inactivo)."""
        return self.productos.count() > 0

    @property
    def puede_eliminarse(self):
        """Indica si la categoría puede eliminarse (sin productos asociados)."""
        if self.tiene_productos:
            return False
        if self.es_padre:
            return all(sub.puede_eliminarse for sub in self.subcategorias)
        return True

    @property
    def cantidad_productos_total(self):
        """Retorna la cantidad de productos activos incluyendo subcategorías."""
        total = self.cantidad_productos
        for subcategoria in self.subcategorias:
            total += subcategoria.cantidad_productos
        return total

    def to_dict(self):
        """Convierte la categoría a diccionario."""
        return {
            'id': self.id,
            'nombre': self.nombre,
            'padre_id': self.padre_id,
            'descripcion': self.descripcion,
            'activa': self.activa,
            'cantidad_productos': self.cantidad_productos,
            'es_padre': self.es_padre,
            'nombre_completo': self.nombre_completo,
        }
