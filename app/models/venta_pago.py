"""Modelo de VentaPago (pagos individuales de una venta)."""

from ..extensions import db


class VentaPago(db.Model):
    """Modelo de pago individual de una venta.

    Permite registrar uno o más pagos por venta, soportando pagos divididos.
    """

    __tablename__ = 'venta_pagos'

    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(
        db.Integer,
        db.ForeignKey('ventas.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    forma_pago = db.Column(
        db.Enum(
            'efectivo', 'tarjeta_debito', 'tarjeta_credito',
            'transferencia', 'qr', 'cuenta_corriente',
            name='forma_pago',
            create_type=False,
        ),
        nullable=False,
    )
    monto = db.Column(db.Numeric(12, 2), nullable=False)

    # Relacion
    venta = db.relationship(
        'Venta',
        backref=db.backref('pagos', lazy='joined', cascade='all, delete-orphan'),
    )

    def __repr__(self):
        return f'<VentaPago {self.id} - {self.forma_pago} ${self.monto}>'

    @property
    def forma_pago_display(self):
        """Retorna la forma de pago en formato legible."""
        opciones = {
            'efectivo': 'Efectivo',
            'tarjeta_debito': 'Tarjeta Debito',
            'tarjeta_credito': 'Tarjeta Credito',
            'transferencia': 'Transferencia',
            'qr': 'QR',
            'cuenta_corriente': 'Cuenta Corriente',
        }
        return opciones.get(self.forma_pago, self.forma_pago)
