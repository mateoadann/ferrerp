"""Modelo de Movimiento de Stock."""

from datetime import datetime
from ..extensions import db


class MovimientoStock(db.Model):
    """Modelo de movimiento de stock (historial de cambios de inventario)."""

    __tablename__ = 'movimientos_stock'

    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(
        db.Integer,
        db.ForeignKey('productos.id'),
        nullable=False,
        index=True
    )
    tipo = db.Column(
        db.Enum(
            'venta', 'compra', 'ajuste_positivo', 'ajuste_negativo', 'devolucion',
            name='tipo_movimiento_stock'
        ),
        nullable=False
    )
    cantidad = db.Column(db.Numeric(12, 3), nullable=False)  # Positivo o negativo
    stock_anterior = db.Column(db.Numeric(12, 3), nullable=False)
    stock_posterior = db.Column(db.Numeric(12, 3), nullable=False)
    referencia_tipo = db.Column(db.String(20))  # 'venta', 'orden_compra', 'ajuste', 'devolucion'
    referencia_id = db.Column(db.Integer)
    motivo = db.Column(db.Text)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<MovimientoStock {self.id} - {self.tipo}>'

    @property
    def tipo_display(self):
        """Retorna el tipo en formato legible."""
        opciones = {
            'venta': 'Venta',
            'compra': 'Compra',
            'ajuste_positivo': 'Ajuste (+)',
            'ajuste_negativo': 'Ajuste (-)',
            'devolucion': 'Devolución'
        }
        return opciones.get(self.tipo, self.tipo)

    @property
    def es_entrada(self):
        """Verifica si es un movimiento de entrada."""
        return self.tipo in ('compra', 'ajuste_positivo', 'devolucion')

    @property
    def es_salida(self):
        """Verifica si es un movimiento de salida."""
        return self.tipo in ('venta', 'ajuste_negativo')

    def to_dict(self):
        """Convierte el movimiento a diccionario."""
        return {
            'id': self.id,
            'producto_id': self.producto_id,
            'producto_codigo': self.producto.codigo if self.producto else None,
            'producto_nombre': self.producto.nombre if self.producto else None,
            'tipo': self.tipo,
            'tipo_display': self.tipo_display,
            'cantidad': float(self.cantidad) if self.cantidad else 0,
            'stock_anterior': float(self.stock_anterior) if self.stock_anterior else 0,
            'stock_posterior': float(self.stock_posterior) if self.stock_posterior else 0,
            'referencia_tipo': self.referencia_tipo,
            'referencia_id': self.referencia_id,
            'motivo': self.motivo,
            'usuario_nombre': self.usuario.nombre if self.usuario else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
