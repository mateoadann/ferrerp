"""Modelo de Venta."""

from datetime import datetime
from decimal import Decimal
from ..extensions import db


class Venta(db.Model):
    """Modelo de venta."""

    __tablename__ = 'ventas'

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False, index=True)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    subtotal = db.Column(db.Numeric(12, 2), default=0)
    descuento_porcentaje = db.Column(db.Numeric(5, 2), default=0)
    descuento_monto = db.Column(db.Numeric(12, 2), default=0)
    total = db.Column(db.Numeric(12, 2), nullable=False)
    forma_pago = db.Column(
        db.Enum(
            'efectivo', 'tarjeta_debito', 'tarjeta_credito',
            'transferencia', 'cuenta_corriente',
            name='forma_pago'
        ),
        nullable=False,
        default='efectivo'
    )
    estado = db.Column(
        db.Enum('completada', 'anulada', name='estado_venta'),
        default='completada',
        nullable=False
    )
    motivo_anulacion = db.Column(db.Text)
    caja_id = db.Column(db.Integer, db.ForeignKey('cajas.id'), index=True)
    presupuesto_id = db.Column(db.Integer, db.ForeignKey('presupuestos.id'), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones
    detalles = db.relationship(
        'VentaDetalle',
        backref='venta',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    devoluciones = db.relationship('Devolucion', backref='venta', lazy='dynamic')
    presupuesto = db.relationship('Presupuesto', backref=db.backref('venta', uselist=False))

    def __repr__(self):
        return f'<Venta {self.numero_completo}>'

    @property
    def numero_completo(self):
        """Retorna el número de venta con formato año-número."""
        anio = self.fecha.year if self.fecha else datetime.utcnow().year
        return f'{anio}-{self.numero:06d}'

    @property
    def forma_pago_display(self):
        """Retorna la forma de pago en formato legible."""
        opciones = {
            'efectivo': 'Efectivo',
            'tarjeta_debito': 'Tarjeta Débito',
            'tarjeta_credito': 'Tarjeta Crédito',
            'transferencia': 'Transferencia',
            'cuenta_corriente': 'Cuenta Corriente'
        }
        return opciones.get(self.forma_pago, self.forma_pago)

    @property
    def estado_display(self):
        """Retorna el estado en formato legible."""
        opciones = {
            'completada': 'Completada',
            'anulada': 'Anulada'
        }
        return opciones.get(self.estado, self.estado)

    @property
    def cantidad_items(self):
        """Retorna la cantidad total de items."""
        return sum(d.cantidad for d in self.detalles)

    @property
    def es_anulable(self):
        """Verifica si la venta puede ser anulada."""
        return self.estado == 'completada'

    def calcular_totales(self):
        """Calcula subtotal y total basado en los detalles."""
        self.subtotal = sum(d.subtotal for d in self.detalles)

        # Aplicar descuento
        if self.descuento_porcentaje and self.descuento_porcentaje > 0:
            self.descuento_monto = self.subtotal * (self.descuento_porcentaje / 100)

        self.total = self.subtotal - (self.descuento_monto or 0)
        return self.total

    def to_dict(self):
        """Convierte la venta a diccionario."""
        return {
            'id': self.id,
            'numero': self.numero,
            'numero_completo': self.numero_completo,
            'fecha': self.fecha.isoformat() if self.fecha else None,
            'cliente_id': self.cliente_id,
            'cliente_nombre': self.cliente.nombre if self.cliente else 'Consumidor Final',
            'usuario_id': self.usuario_id,
            'usuario_nombre': self.usuario.nombre if self.usuario else None,
            'subtotal': float(self.subtotal) if self.subtotal else 0,
            'descuento_porcentaje': float(self.descuento_porcentaje) if self.descuento_porcentaje else 0,
            'descuento_monto': float(self.descuento_monto) if self.descuento_monto else 0,
            'total': float(self.total) if self.total else 0,
            'forma_pago': self.forma_pago,
            'forma_pago_display': self.forma_pago_display,
            'estado': self.estado,
            'estado_display': self.estado_display,
            'cantidad_items': self.cantidad_items
        }
