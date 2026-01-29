"""Modelo de Movimiento de Cuenta Corriente."""

from datetime import datetime
from ..extensions import db


class MovimientoCuentaCorriente(db.Model):
    """Modelo de movimiento de cuenta corriente de cliente."""

    __tablename__ = 'movimientos_cuenta_corriente'

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey('clientes.id'),
        nullable=False,
        index=True
    )
    tipo = db.Column(
        db.Enum('cargo', 'pago', name='tipo_movimiento_cc'),
        nullable=False
    )
    monto = db.Column(db.Numeric(12, 2), nullable=False)
    saldo_anterior = db.Column(db.Numeric(12, 2), nullable=False)
    saldo_posterior = db.Column(db.Numeric(12, 2), nullable=False)
    referencia_tipo = db.Column(db.String(20))  # 'venta', 'pago', 'devolucion'
    referencia_id = db.Column(db.Integer)
    descripcion = db.Column(db.String(200))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relaciones
    usuario = db.relationship('Usuario', backref='movimientos_cc')

    def __repr__(self):
        return f'<MovimientoCC {self.id} - {self.tipo} ${self.monto}>'

    @property
    def tipo_display(self):
        """Retorna el tipo en formato legible."""
        return 'Cargo' if self.tipo == 'cargo' else 'Pago'

    @property
    def es_cargo(self):
        """Verifica si es un cargo (aumenta deuda)."""
        return self.tipo == 'cargo'

    @property
    def es_pago(self):
        """Verifica si es un pago (disminuye deuda)."""
        return self.tipo == 'pago'

    def to_dict(self):
        """Convierte el movimiento a diccionario."""
        return {
            'id': self.id,
            'cliente_id': self.cliente_id,
            'cliente_nombre': self.cliente.nombre if self.cliente else None,
            'tipo': self.tipo,
            'tipo_display': self.tipo_display,
            'monto': float(self.monto) if self.monto else 0,
            'saldo_anterior': float(self.saldo_anterior) if self.saldo_anterior else 0,
            'saldo_posterior': float(self.saldo_posterior) if self.saldo_posterior else 0,
            'referencia_tipo': self.referencia_tipo,
            'referencia_id': self.referencia_id,
            'descripcion': self.descripcion,
            'usuario_nombre': self.usuario.nombre if self.usuario else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
