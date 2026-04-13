"""Modelo de historial de actualizaciones de precio."""

from ..extensions import db
from ..utils.helpers import ahora_argentina
from .mixins import EmpresaMixin


class ActualizacionPrecio(EmpresaMixin, db.Model):
    """Registro de auditoría para actualizaciones de precio de productos."""

    __tablename__ = 'actualizaciones_precio'

    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=ahora_argentina)
    tipo = db.Column(db.String(10), nullable=False, default='masiva')  # 'masiva' o 'manual'
    porcentaje = db.Column(db.Numeric(8, 4), nullable=True)
    precio_costo_anterior = db.Column(db.Numeric(12, 2), nullable=False)
    precio_costo_nuevo = db.Column(db.Numeric(12, 2), nullable=False)
    precio_venta_anterior = db.Column(db.Numeric(12, 2), nullable=False)
    precio_venta_nuevo = db.Column(db.Numeric(12, 2), nullable=False)
    actualizo_costo = db.Column(db.Boolean, nullable=False, default=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias.id'), nullable=True)
    notas = db.Column(db.Text, nullable=True)

    # Relaciones
    producto = db.relationship(
        'Producto',
        backref=db.backref(
            'actualizaciones_precio',
            lazy='dynamic',
            order_by='ActualizacionPrecio.fecha.desc()',
        ),
    )
    usuario = db.relationship('Usuario')
    categoria = db.relationship('Categoria')

    def __repr__(self):
        return f'<ActualizacionPrecio {self.id} ' f'producto={self.producto_id} {self.tipo}>'
