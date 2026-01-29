"""Modelo de Cliente."""

from datetime import datetime
from decimal import Decimal
from ..extensions import db


class Cliente(db.Model):
    """Modelo de cliente."""

    __tablename__ = 'clientes'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    dni_cuit = db.Column(db.String(13), index=True)
    telefono = db.Column(db.String(20))
    email = db.Column(db.String(120))
    direccion = db.Column(db.String(200))
    limite_credito = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    saldo_cuenta_corriente = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    notas = db.Column(db.Text)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones
    ventas = db.relationship('Venta', backref='cliente', lazy='dynamic')
    movimientos_cuenta = db.relationship('MovimientoCuentaCorriente', backref='cliente', lazy='dynamic')

    def __repr__(self):
        return f'<Cliente {self.nombre}>'

    @property
    def tiene_deuda(self):
        """Verifica si el cliente tiene deuda."""
        return self.saldo_cuenta_corriente > 0

    @property
    def credito_disponible(self):
        """Calcula el crédito disponible."""
        return self.limite_credito - self.saldo_cuenta_corriente

    def puede_comprar_a_credito(self, monto):
        """
        Verifica si el cliente puede comprar a crédito por un monto dado.

        Args:
            monto: Monto de la compra

        Returns:
            bool: True si puede, False si no
        """
        if self.limite_credito <= 0:
            return False
        return (self.saldo_cuenta_corriente + Decimal(str(monto))) <= self.limite_credito

    def actualizar_saldo(self, monto, tipo='cargo'):
        """
        Actualiza el saldo de cuenta corriente.

        Args:
            monto: Monto a modificar
            tipo: 'cargo' para aumentar deuda, 'pago' para disminuir

        Returns:
            Tuple con (saldo_anterior, saldo_nuevo)
        """
        saldo_anterior = self.saldo_cuenta_corriente
        monto_decimal = Decimal(str(monto))

        if tipo == 'cargo':
            self.saldo_cuenta_corriente += monto_decimal
        elif tipo == 'pago':
            self.saldo_cuenta_corriente -= monto_decimal

        return saldo_anterior, self.saldo_cuenta_corriente

    def to_dict(self):
        """Convierte el cliente a diccionario."""
        return {
            'id': self.id,
            'nombre': self.nombre,
            'dni_cuit': self.dni_cuit,
            'telefono': self.telefono,
            'email': self.email,
            'direccion': self.direccion,
            'limite_credito': float(self.limite_credito) if self.limite_credito else 0,
            'saldo_cuenta_corriente': float(self.saldo_cuenta_corriente) if self.saldo_cuenta_corriente else 0,
            'tiene_deuda': self.tiene_deuda,
            'credito_disponible': float(self.credito_disponible),
            'activo': self.activo
        }
