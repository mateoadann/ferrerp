"""Modelo de ajuste de precio para deudas de cuenta corriente."""

from ..extensions import db
from ..utils.helpers import ahora_argentina
from .mixins import EmpresaMixin


class AjustePrecioCuentaCorriente(EmpresaMixin, db.Model):
    """Registro de auditoría para ajustes de precio aplicados a deudas CC."""

    __tablename__ = 'ajustes_precio_cuenta_corriente'
    __table_args__ = (
        db.UniqueConstraint(
            'venta_id', 'actualizacion_fecha', 'empresa_id',
            name='uq_ajuste_cc_venta_fecha_empresa',
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey('clientes.id'),
        nullable=False,
        index=True,
    )
    venta_id = db.Column(
        db.Integer,
        db.ForeignKey('ventas.id'),
        nullable=False,
        index=True,
    )
    movimiento_cc_id = db.Column(
        db.Integer,
        db.ForeignKey('movimientos_cuenta_corriente.id'),
        nullable=True,
    )
    actualizacion_fecha = db.Column(db.DateTime, nullable=False, index=True)
    porcentaje_aplicado = db.Column(db.Numeric(8, 4), nullable=False)
    total_original = db.Column(db.Numeric(12, 2), nullable=False)
    total_recalculado = db.Column(db.Numeric(12, 2), nullable=False)
    monto_ajuste = db.Column(db.Numeric(12, 2), nullable=False)
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey('usuarios.id'),
        nullable=False,
    )
    created_at = db.Column(db.DateTime, default=ahora_argentina)

    # Relaciones
    cliente = db.relationship(
        'Cliente',
        backref=db.backref(
            'ajustes_precio_cc',
            lazy='dynamic',
            order_by='AjustePrecioCuentaCorriente.created_at.desc()',
        ),
    )
    venta = db.relationship(
        'Venta',
        backref=db.backref(
            'ajustes_precio_cc',
            lazy='dynamic',
        ),
    )
    movimiento_cc = db.relationship(
        'MovimientoCuentaCorriente',
        backref=db.backref('ajuste_precio_cc', uselist=False),
    )
    usuario = db.relationship('Usuario')

    def __repr__(self):
        return (
            f'<AjustePrecioCuentaCorriente {self.id} '
            f'venta={self.venta_id} {self.porcentaje_aplicado}%>'
        )
