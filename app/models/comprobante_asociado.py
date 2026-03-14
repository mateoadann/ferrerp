"""Modelo de Comprobante Asociado (para NC/ND que referencian facturas)."""

from ..extensions import db


class ComprobanteAsociado(db.Model):
    """Comprobante asociado a una factura (usado en Notas de Crédito/Débito)."""

    __tablename__ = 'comprobantes_asociados'

    id = db.Column(db.Integer, primary_key=True)
    factura_id = db.Column(
        db.Integer,
        db.ForeignKey('facturas.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    tipo_comprobante = db.Column(db.Integer, nullable=False)
    punto_venta = db.Column(db.Integer, nullable=False)
    numero_comprobante = db.Column(db.Integer, nullable=False)
    cuit_emisor = db.Column(db.String(13))
    fecha_comprobante = db.Column(db.Date)

    def __repr__(self):
        return (
            f'<ComprobanteAsociado {self.tipo_comprobante} '
            f'{self.punto_venta:05d}-{self.numero_comprobante:08d}>'
        )

    def to_dict(self):
        """Convierte el comprobante asociado a diccionario."""
        return {
            'id': self.id,
            'factura_id': self.factura_id,
            'tipo_comprobante': self.tipo_comprobante,
            'punto_venta': self.punto_venta,
            'numero_comprobante': self.numero_comprobante,
            'cuit_emisor': self.cuit_emisor,
            'fecha_comprobante': (
                self.fecha_comprobante.isoformat() if self.fecha_comprobante else None
            ),
        }
