"""Modelos de Caja."""

from datetime import datetime
from decimal import Decimal
from ..extensions import db


class Caja(db.Model):
    """Modelo de caja (apertura/cierre diario)."""

    __tablename__ = 'cajas'

    id = db.Column(db.Integer, primary_key=True)
    fecha_apertura = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    fecha_cierre = db.Column(db.DateTime)
    usuario_apertura_id = db.Column(
        db.Integer,
        db.ForeignKey('usuarios.id'),
        nullable=False
    )
    usuario_cierre_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    monto_inicial = db.Column(db.Numeric(12, 2), nullable=False)
    monto_esperado = db.Column(db.Numeric(12, 2))
    monto_real = db.Column(db.Numeric(12, 2))
    diferencia = db.Column(db.Numeric(12, 2))
    estado = db.Column(
        db.Enum('abierta', 'cerrada', name='estado_caja'),
        default='abierta',
        nullable=False
    )
    observaciones = db.Column(db.Text)

    # Relaciones
    usuario_apertura = db.relationship(
        'Usuario',
        foreign_keys=[usuario_apertura_id],
        backref='cajas_abiertas'
    )
    usuario_cierre = db.relationship(
        'Usuario',
        foreign_keys=[usuario_cierre_id],
        backref='cajas_cerradas'
    )
    movimientos = db.relationship(
        'MovimientoCaja',
        backref='caja',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    ventas = db.relationship('Venta', backref='caja', lazy='dynamic')

    def __repr__(self):
        return f'<Caja {self.id} - {self.fecha_apertura.strftime("%d/%m/%Y")}>'

    @property
    def esta_abierta(self):
        """Verifica si la caja está abierta."""
        return self.estado == 'abierta'

    @property
    def total_ingresos(self):
        """Calcula el total de ingresos en efectivo."""
        return sum(
            m.monto for m in self.movimientos
            if m.tipo == 'ingreso' and m.forma_pago == 'efectivo'
        )

    @property
    def total_egresos(self):
        """Calcula el total de egresos en efectivo."""
        return sum(
            m.monto for m in self.movimientos
            if m.tipo == 'egreso' and m.forma_pago == 'efectivo'
        )

    def calcular_monto_esperado(self):
        """Calcula el monto esperado en caja."""
        self.monto_esperado = (
            self.monto_inicial +
            self.total_ingresos -
            self.total_egresos
        )
        return self.monto_esperado

    def cerrar(self, monto_real, usuario_cierre_id, observaciones=None):
        """
        Cierra la caja.

        Args:
            monto_real: Monto contado físicamente
            usuario_cierre_id: ID del usuario que cierra
            observaciones: Observaciones opcionales
        """
        self.calcular_monto_esperado()
        self.monto_real = Decimal(str(monto_real))
        self.diferencia = self.monto_real - self.monto_esperado
        self.usuario_cierre_id = usuario_cierre_id
        self.fecha_cierre = datetime.utcnow()
        self.estado = 'cerrada'
        if observaciones:
            self.observaciones = observaciones

    def to_dict(self):
        """Convierte la caja a diccionario."""
        return {
            'id': self.id,
            'fecha_apertura': self.fecha_apertura.isoformat() if self.fecha_apertura else None,
            'fecha_cierre': self.fecha_cierre.isoformat() if self.fecha_cierre else None,
            'usuario_apertura': self.usuario_apertura.nombre if self.usuario_apertura else None,
            'usuario_cierre': self.usuario_cierre.nombre if self.usuario_cierre else None,
            'monto_inicial': float(self.monto_inicial) if self.monto_inicial else 0,
            'monto_esperado': float(self.monto_esperado) if self.monto_esperado else 0,
            'monto_real': float(self.monto_real) if self.monto_real else 0,
            'diferencia': float(self.diferencia) if self.diferencia else 0,
            'estado': self.estado,
            'total_ingresos': float(self.total_ingresos),
            'total_egresos': float(self.total_egresos)
        }


class MovimientoCaja(db.Model):
    """Modelo de movimiento de caja."""

    __tablename__ = 'movimientos_caja'

    id = db.Column(db.Integer, primary_key=True)
    caja_id = db.Column(
        db.Integer,
        db.ForeignKey('cajas.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    tipo = db.Column(
        db.Enum('ingreso', 'egreso', name='tipo_movimiento_caja'),
        nullable=False
    )
    concepto = db.Column(
        db.Enum(
            'venta', 'cobro_cuenta_corriente', 'pago_proveedor',
            'gasto', 'retiro', 'devolucion', 'otro',
            name='concepto_movimiento_caja'
        ),
        nullable=False
    )
    descripcion = db.Column(db.String(200))
    monto = db.Column(db.Numeric(12, 2), nullable=False)
    forma_pago = db.Column(
        db.Enum(
            'efectivo', 'tarjeta_debito', 'tarjeta_credito', 'transferencia',
            name='forma_pago_movimiento'
        ),
        nullable=False,
        default='efectivo'
    )
    referencia_tipo = db.Column(db.String(20))  # 'venta', 'devolucion', 'pago', etc.
    referencia_id = db.Column(db.Integer)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<MovimientoCaja {self.id} - {self.tipo} ${self.monto}>'

    @property
    def tipo_display(self):
        """Retorna el tipo en formato legible."""
        return 'Ingreso' if self.tipo == 'ingreso' else 'Egreso'

    @property
    def concepto_display(self):
        """Retorna el concepto en formato legible."""
        opciones = {
            'venta': 'Venta',
            'cobro_cuenta_corriente': 'Cobro Cuenta Corriente',
            'pago_proveedor': 'Pago a Proveedor',
            'gasto': 'Gasto',
            'retiro': 'Retiro',
            'devolucion': 'Devolución',
            'otro': 'Otro'
        }
        return opciones.get(self.concepto, self.concepto)

    @property
    def forma_pago_display(self):
        """Retorna la forma de pago en formato legible."""
        opciones = {
            'efectivo': 'Efectivo',
            'tarjeta_debito': 'Tarjeta Débito',
            'tarjeta_credito': 'Tarjeta Crédito',
            'transferencia': 'Transferencia'
        }
        return opciones.get(self.forma_pago, self.forma_pago)

    def to_dict(self):
        """Convierte el movimiento a diccionario."""
        return {
            'id': self.id,
            'caja_id': self.caja_id,
            'tipo': self.tipo,
            'tipo_display': self.tipo_display,
            'concepto': self.concepto,
            'concepto_display': self.concepto_display,
            'descripcion': self.descripcion,
            'monto': float(self.monto) if self.monto else 0,
            'forma_pago': self.forma_pago,
            'forma_pago_display': self.forma_pago_display,
            'usuario_nombre': self.usuario.nombre if self.usuario else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
