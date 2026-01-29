"""Modelo de Devolución."""

from datetime import datetime
from ..extensions import db


class Devolucion(db.Model):
    """Modelo de devolución de venta."""

    __tablename__ = 'devoluciones'

    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(
        db.Integer,
        db.ForeignKey('ventas.id'),
        nullable=False,
        index=True
    )
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    motivo = db.Column(db.Text, nullable=False)
    accion = db.Column(
        db.Enum(
            'reintegro_efectivo', 'nota_credito', 'credito_cuenta_corriente',
            name='accion_devolucion'
        ),
        nullable=False
    )
    monto_total = db.Column(db.Numeric(12, 2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones
    detalles = db.relationship(
        'DevolucionDetalle',
        backref='devolucion',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    usuario = db.relationship('Usuario', backref='devoluciones')

    def __repr__(self):
        return f'<Devolucion {self.id} - Venta {self.venta_id}>'

    @property
    def accion_display(self):
        """Retorna la acción en formato legible."""
        opciones = {
            'reintegro_efectivo': 'Reintegro en Efectivo',
            'nota_credito': 'Nota de Crédito',
            'credito_cuenta_corriente': 'Crédito en Cuenta Corriente'
        }
        return opciones.get(self.accion, self.accion)

    def to_dict(self):
        """Convierte la devolución a diccionario."""
        return {
            'id': self.id,
            'venta_id': self.venta_id,
            'venta_numero': self.venta.numero_completo if self.venta else None,
            'fecha': self.fecha.isoformat() if self.fecha else None,
            'usuario_nombre': self.usuario.nombre if self.usuario else None,
            'motivo': self.motivo,
            'accion': self.accion,
            'accion_display': self.accion_display,
            'monto_total': float(self.monto_total) if self.monto_total else 0
        }


class DevolucionDetalle(db.Model):
    """Modelo de detalle de devolución."""

    __tablename__ = 'devolucion_detalles'

    id = db.Column(db.Integer, primary_key=True)
    devolucion_id = db.Column(
        db.Integer,
        db.ForeignKey('devoluciones.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    producto_id = db.Column(
        db.Integer,
        db.ForeignKey('productos.id'),
        nullable=False
    )
    cantidad = db.Column(db.Numeric(12, 3), nullable=False)
    precio_unitario = db.Column(db.Numeric(12, 2), nullable=False)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)

    # Relaciones
    producto = db.relationship('Producto')

    def __repr__(self):
        return f'<DevolucionDetalle {self.id}>'

    def to_dict(self):
        """Convierte el detalle a diccionario."""
        return {
            'id': self.id,
            'producto_id': self.producto_id,
            'producto_nombre': self.producto.nombre if self.producto else None,
            'cantidad': float(self.cantidad) if self.cantidad else 0,
            'precio_unitario': float(self.precio_unitario) if self.precio_unitario else 0,
            'subtotal': float(self.subtotal) if self.subtotal else 0
        }
