"""Modelo de Producto."""

from datetime import datetime
from decimal import Decimal
from ..extensions import db


class Producto(db.Model):
    """Modelo de producto."""

    __tablename__ = 'productos'

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False, index=True)
    codigo_barras = db.Column(db.String(50), index=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias.id'), index=True)
    unidad_medida = db.Column(
        db.Enum('unidad', 'metro', 'kilo', 'litro', 'par', name='unidad_medida'),
        nullable=False,
        default='unidad'
    )
    precio_costo = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    precio_venta = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    stock_actual = db.Column(db.Numeric(12, 3), default=0, nullable=False)
    stock_minimo = db.Column(db.Numeric(12, 3), default=0, nullable=False)
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedores.id'), index=True)
    ubicacion = db.Column(db.String(50))
    activo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    movimientos_stock = db.relationship('MovimientoStock', backref='producto', lazy='dynamic')
    detalles_venta = db.relationship('VentaDetalle', backref='producto', lazy='dynamic')
    detalles_orden_compra = db.relationship('OrdenCompraDetalle', backref='producto', lazy='dynamic')

    def __repr__(self):
        return f'<Producto {self.codigo} - {self.nombre}>'

    @property
    def stock_bajo(self):
        """Verifica si el stock está por debajo del mínimo."""
        return self.stock_actual < self.stock_minimo

    @property
    def margen_ganancia(self):
        """Calcula el margen de ganancia en porcentaje."""
        if self.precio_costo and self.precio_costo > 0:
            return ((self.precio_venta - self.precio_costo) / self.precio_costo) * 100
        return Decimal('0')

    @property
    def unidad_medida_display(self):
        """Retorna la unidad de medida en formato legible."""
        opciones = {
            'unidad': 'Unidad',
            'metro': 'Metro',
            'kilo': 'Kilogramo',
            'litro': 'Litro',
            'par': 'Par'
        }
        return opciones.get(self.unidad_medida, self.unidad_medida)

    @property
    def unidad_medida_abrev(self):
        """Retorna la abreviatura de la unidad de medida."""
        opciones = {
            'unidad': 'u',
            'metro': 'm',
            'kilo': 'kg',
            'litro': 'l',
            'par': 'par'
        }
        return opciones.get(self.unidad_medida, self.unidad_medida)

    def actualizar_stock(self, cantidad, tipo_movimiento):
        """
        Actualiza el stock del producto.

        Args:
            cantidad: Cantidad a modificar (positiva o negativa)
            tipo_movimiento: Tipo de movimiento (venta, compra, ajuste, etc.)

        Returns:
            Tuple con (stock_anterior, stock_nuevo)
        """
        stock_anterior = self.stock_actual
        self.stock_actual = self.stock_actual + Decimal(str(cantidad))
        return stock_anterior, self.stock_actual

    def to_dict(self):
        """Convierte el producto a diccionario."""
        return {
            'id': self.id,
            'codigo': self.codigo,
            'codigo_barras': self.codigo_barras,
            'nombre': self.nombre,
            'descripcion': self.descripcion,
            'categoria_id': self.categoria_id,
            'categoria_nombre': self.categoria.nombre if self.categoria else None,
            'unidad_medida': self.unidad_medida,
            'unidad_medida_display': self.unidad_medida_display,
            'unidad_medida_abrev': self.unidad_medida_abrev,
            'precio_costo': float(self.precio_costo) if self.precio_costo else 0,
            'precio_venta': float(self.precio_venta) if self.precio_venta else 0,
            'stock_actual': float(self.stock_actual) if self.stock_actual else 0,
            'stock_minimo': float(self.stock_minimo) if self.stock_minimo else 0,
            'stock_bajo': self.stock_bajo,
            'proveedor_id': self.proveedor_id,
            'proveedor_nombre': self.proveedor.nombre if self.proveedor else None,
            'ubicacion': self.ubicacion,
            'activo': self.activo
        }
