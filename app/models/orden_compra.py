"""Modelos de Orden de Compra."""

from datetime import datetime
from decimal import Decimal
from ..extensions import db


class OrdenCompra(db.Model):
    """Modelo de orden de compra a proveedor."""

    __tablename__ = 'ordenes_compra'

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, unique=True, nullable=False, index=True)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    proveedor_id = db.Column(
        db.Integer,
        db.ForeignKey('proveedores.id'),
        nullable=False,
        index=True
    )
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    estado = db.Column(
        db.Enum(
            'pendiente', 'recibida_parcial', 'recibida_completa', 'cancelada',
            name='estado_orden_compra'
        ),
        default='pendiente',
        nullable=False
    )
    total = db.Column(db.Numeric(12, 2), default=0)
    notas = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones
    detalles = db.relationship(
        'OrdenCompraDetalle',
        backref='orden_compra',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    usuario = db.relationship('Usuario', backref='ordenes_compra')

    def __repr__(self):
        return f'<OrdenCompra {self.numero}>'

    @property
    def estado_display(self):
        """Retorna el estado en formato legible."""
        opciones = {
            'pendiente': 'Pendiente',
            'recibida_parcial': 'Recibida Parcial',
            'recibida_completa': 'Recibida Completa',
            'cancelada': 'Cancelada'
        }
        return opciones.get(self.estado, self.estado)

    @property
    def puede_recibir(self):
        """Verifica si la orden puede recibir mercadería."""
        return self.estado in ('pendiente', 'recibida_parcial')

    @property
    def puede_cancelar(self):
        """Verifica si la orden puede ser cancelada."""
        return self.estado == 'pendiente'

    def calcular_total(self):
        """Calcula el total de la orden."""
        self.total = sum(d.subtotal for d in self.detalles if d.subtotal)
        return self.total

    def actualizar_estado(self):
        """Actualiza el estado basado en las cantidades recibidas."""
        detalles = list(self.detalles)
        if not detalles:
            return

        total_pedido = sum(d.cantidad_pedida for d in detalles)
        total_recibido = sum(d.cantidad_recibida or 0 for d in detalles)

        if total_recibido == 0:
            self.estado = 'pendiente'
        elif total_recibido >= total_pedido:
            self.estado = 'recibida_completa'
        else:
            self.estado = 'recibida_parcial'

    def to_dict(self):
        """Convierte la orden a diccionario."""
        return {
            'id': self.id,
            'numero': self.numero,
            'fecha': self.fecha.isoformat() if self.fecha else None,
            'proveedor_id': self.proveedor_id,
            'proveedor_nombre': self.proveedor.nombre if self.proveedor else None,
            'usuario_nombre': self.usuario.nombre if self.usuario else None,
            'estado': self.estado,
            'estado_display': self.estado_display,
            'total': float(self.total) if self.total else 0,
            'notas': self.notas
        }


class OrdenCompraDetalle(db.Model):
    """Modelo de detalle de orden de compra."""

    __tablename__ = 'orden_compra_detalles'

    id = db.Column(db.Integer, primary_key=True)
    orden_compra_id = db.Column(
        db.Integer,
        db.ForeignKey('ordenes_compra.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    producto_id = db.Column(
        db.Integer,
        db.ForeignKey('productos.id'),
        nullable=False
    )
    cantidad_pedida = db.Column(db.Numeric(12, 3), nullable=False)
    cantidad_recibida = db.Column(db.Numeric(12, 3), default=0)
    precio_unitario = db.Column(db.Numeric(12, 2), nullable=False)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)

    # La relacion con Producto se define via backref en Producto.detalles_orden_compra

    def __repr__(self):
        return f'<OrdenCompraDetalle {self.id}>'

    @property
    def cantidad_pendiente(self):
        """Retorna la cantidad pendiente de recibir."""
        return self.cantidad_pedida - (self.cantidad_recibida or 0)

    @property
    def esta_completo(self):
        """Verifica si el ítem está completamente recibido."""
        return (self.cantidad_recibida or 0) >= self.cantidad_pedida

    def calcular_subtotal(self):
        """Calcula el subtotal de la línea."""
        self.subtotal = Decimal(str(self.cantidad_pedida)) * Decimal(str(self.precio_unitario))
        return self.subtotal

    def to_dict(self):
        """Convierte el detalle a diccionario."""
        return {
            'id': self.id,
            'producto_id': self.producto_id,
            'producto_codigo': self.producto.codigo if self.producto else None,
            'producto_nombre': self.producto.nombre if self.producto else None,
            'cantidad_pedida': float(self.cantidad_pedida) if self.cantidad_pedida else 0,
            'cantidad_recibida': float(self.cantidad_recibida) if self.cantidad_recibida else 0,
            'cantidad_pendiente': float(self.cantidad_pendiente),
            'precio_unitario': float(self.precio_unitario) if self.precio_unitario else 0,
            'subtotal': float(self.subtotal) if self.subtotal else 0,
            'esta_completo': self.esta_completo
        }
