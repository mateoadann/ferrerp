"""Modelos de Presupuesto."""

import secrets
from datetime import datetime, timedelta
from decimal import Decimal
from ..extensions import db


class Presupuesto(db.Model):
    """Modelo de presupuesto / cotización."""

    __tablename__ = 'presupuestos'

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False, index=True)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    fecha_vencimiento = db.Column(db.DateTime, nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), index=True)
    cliente_nombre = db.Column(db.String(100))
    cliente_telefono = db.Column(db.String(20))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    descuento_porcentaje = db.Column(db.Numeric(5, 2), default=0)
    descuento_monto = db.Column(db.Numeric(12, 2), default=0)
    total = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    estado = db.Column(
        db.Enum(
            'pendiente', 'aceptado', 'rechazado', 'vencido', 'convertido',
            name='estado_presupuesto'
        ),
        default='pendiente',
        nullable=False
    )
    notas = db.Column(db.Text)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    detalles = db.relationship(
        'PresupuestoDetalle',
        backref='presupuesto',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    cliente = db.relationship('Cliente', backref=db.backref('presupuestos', lazy='dynamic'))
    usuario = db.relationship('Usuario', backref=db.backref('presupuestos', lazy='dynamic'))

    def __repr__(self):
        return f'<Presupuesto {self.numero_completo}>'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.token:
            self.token = secrets.token_urlsafe(32)

    @property
    def numero_completo(self):
        """Retorna el número con formato AÑO-NNNNNN."""
        anio = self.fecha.year if self.fecha else datetime.utcnow().year
        return f'{anio}-{self.numero:06d}'

    @property
    def estado_display(self):
        """Retorna el estado en formato legible."""
        opciones = {
            'pendiente': 'Pendiente',
            'aceptado': 'Aceptado',
            'rechazado': 'Rechazado',
            'vencido': 'Vencido',
            'convertido': 'Convertido'
        }
        return opciones.get(self.estado, self.estado)

    @property
    def nombre_cliente_display(self):
        """Retorna el nombre del cliente para mostrar."""
        if self.cliente:
            return self.cliente.nombre
        return self.cliente_nombre or 'Sin cliente'

    @property
    def telefono_cliente_display(self):
        """Retorna el teléfono del cliente."""
        if self.cliente and self.cliente.telefono:
            return self.cliente.telefono
        return self.cliente_telefono or ''

    @property
    def esta_vencido(self):
        """Verifica si el presupuesto está vencido."""
        if self.estado != 'pendiente':
            return False
        return datetime.utcnow() > self.fecha_vencimiento

    @property
    def puede_editar(self):
        """Verifica si el presupuesto puede editarse."""
        return self.estado == 'pendiente'

    @property
    def puede_aceptar(self):
        """Verifica si puede pasar a aceptado."""
        return self.estado == 'pendiente' and not self.esta_vencido

    @property
    def puede_rechazar(self):
        """Verifica si puede pasar a rechazado."""
        return self.estado == 'pendiente'

    @property
    def puede_convertir(self):
        """Verifica si puede convertirse a venta."""
        return self.estado == 'aceptado'

    @property
    def cantidad_items(self):
        """Retorna la cantidad total de items."""
        return self.detalles.count()

    def calcular_totales(self):
        """Calcula subtotal y total basado en los detalles."""
        self.subtotal = sum(d.subtotal for d in self.detalles)
        if self.descuento_porcentaje and self.descuento_porcentaje > 0:
            self.descuento_monto = self.subtotal * (self.descuento_porcentaje / 100)
        else:
            self.descuento_monto = Decimal('0')
        self.total = self.subtotal - self.descuento_monto
        return self.total

    def to_dict(self):
        """Convierte el presupuesto a diccionario."""
        return {
            'id': self.id,
            'numero': self.numero,
            'numero_completo': self.numero_completo,
            'fecha': self.fecha.isoformat() if self.fecha else None,
            'fecha_vencimiento': self.fecha_vencimiento.isoformat() if self.fecha_vencimiento else None,
            'cliente_id': self.cliente_id,
            'cliente_nombre': self.nombre_cliente_display,
            'usuario_id': self.usuario_id,
            'subtotal': float(self.subtotal) if self.subtotal else 0,
            'descuento_porcentaje': float(self.descuento_porcentaje) if self.descuento_porcentaje else 0,
            'descuento_monto': float(self.descuento_monto) if self.descuento_monto else 0,
            'total': float(self.total) if self.total else 0,
            'estado': self.estado,
            'estado_display': self.estado_display,
            'notas': self.notas,
            'cantidad_items': self.cantidad_items
        }


class PresupuestoDetalle(db.Model):
    """Modelo de detalle de presupuesto (línea)."""

    __tablename__ = 'presupuesto_detalles'

    id = db.Column(db.Integer, primary_key=True)
    presupuesto_id = db.Column(
        db.Integer,
        db.ForeignKey('presupuestos.id', ondelete='CASCADE'),
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

    # Relación
    producto = db.relationship('Producto')

    def __repr__(self):
        return f'<PresupuestoDetalle {self.id} - Presupuesto {self.presupuesto_id}>'

    def calcular_subtotal(self):
        """Calcula el subtotal de la línea."""
        self.subtotal = Decimal(str(self.cantidad)) * Decimal(str(self.precio_unitario))
        return self.subtotal

    def to_dict(self):
        """Convierte el detalle a diccionario."""
        return {
            'id': self.id,
            'presupuesto_id': self.presupuesto_id,
            'producto_id': self.producto_id,
            'producto_codigo': self.producto.codigo if self.producto else None,
            'producto_nombre': self.producto.nombre if self.producto else None,
            'cantidad': float(self.cantidad) if self.cantidad else 0,
            'precio_unitario': float(self.precio_unitario) if self.precio_unitario else 0,
            'subtotal': float(self.subtotal) if self.subtotal else 0
        }
