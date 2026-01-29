"""Modelo de Detalle de Venta."""

from decimal import Decimal
from ..extensions import db


class VentaDetalle(db.Model):
    """Modelo de detalle de venta (línea de venta)."""

    __tablename__ = 'venta_detalles'

    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(
        db.Integer,
        db.ForeignKey('ventas.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    producto_id = db.Column(
        db.Integer,
        db.ForeignKey('productos.id'),
        nullable=False,
        index=True
    )
    cantidad = db.Column(db.Numeric(12, 3), nullable=False)
    precio_unitario = db.Column(db.Numeric(12, 2), nullable=False)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)

    def __repr__(self):
        return f'<VentaDetalle {self.id} - Venta {self.venta_id}>'

    def calcular_subtotal(self):
        """Calcula el subtotal de la línea."""
        self.subtotal = Decimal(str(self.cantidad)) * Decimal(str(self.precio_unitario))
        return self.subtotal

    def to_dict(self):
        """Convierte el detalle a diccionario."""
        return {
            'id': self.id,
            'venta_id': self.venta_id,
            'producto_id': self.producto_id,
            'producto_codigo': self.producto.codigo if self.producto else None,
            'producto_nombre': self.producto.nombre if self.producto else None,
            'cantidad': float(self.cantidad) if self.cantidad else 0,
            'precio_unitario': float(self.precio_unitario) if self.precio_unitario else 0,
            'subtotal': float(self.subtotal) if self.subtotal else 0
        }
