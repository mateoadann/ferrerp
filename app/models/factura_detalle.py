"""Modelo de Detalle de Factura Electrónica."""

from decimal import Decimal

from ..extensions import db


class FacturaDetalle(db.Model):
    """Modelo de línea/detalle de factura electrónica."""

    __tablename__ = 'factura_detalles'

    id = db.Column(db.Integer, primary_key=True)
    factura_id = db.Column(
        db.Integer,
        db.ForeignKey('facturas.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    producto_id = db.Column(
        db.Integer,
        db.ForeignKey('productos.id'),
        nullable=True,
        index=True,
    )
    descripcion = db.Column(db.String(200), nullable=False)
    cantidad = db.Column(db.Numeric(12, 3), nullable=False)
    precio_unitario = db.Column(db.Numeric(14, 2), nullable=False)
    subtotal = db.Column(db.Numeric(14, 2), nullable=False)
    iva_porcentaje = db.Column(db.Numeric(5, 2), nullable=False, default=Decimal('21'))
    iva_id = db.Column(db.Integer)
    iva_monto = db.Column(db.Numeric(14, 2), default=0)

    # Relación
    producto = db.relationship('Producto', backref='factura_detalles')

    def __repr__(self):
        return f'<FacturaDetalle {self.id} - Factura {self.factura_id}>'

    def to_dict(self):
        """Convierte el detalle a diccionario."""
        return {
            'id': self.id,
            'factura_id': self.factura_id,
            'producto_id': self.producto_id,
            'descripcion': self.descripcion,
            'cantidad': float(self.cantidad) if self.cantidad else 0,
            'precio_unitario': (float(self.precio_unitario) if self.precio_unitario else 0),
            'subtotal': float(self.subtotal) if self.subtotal else 0,
            'iva_porcentaje': (float(self.iva_porcentaje) if self.iva_porcentaje else 21),
            'iva_id': self.iva_id,
            'iva_monto': float(self.iva_monto) if self.iva_monto else 0,
        }
