"""Modelo de Factura Electrónica (ARCA / ex-AFIP)."""

from ..extensions import db
from ..utils.helpers import ahora_argentina
from .mixins import EmpresaMixin


class Factura(EmpresaMixin, db.Model):
    """Modelo de factura electrónica autorizada por ARCA."""

    __tablename__ = 'facturas'
    __table_args__ = (
        db.UniqueConstraint(
            'empresa_id',
            'tipo_comprobante',
            'punto_venta',
            'numero_comprobante',
            name='uq_factura_comprobante',
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey('ventas.id'), nullable=True, index=True)

    # Datos del comprobante
    tipo_comprobante = db.Column(db.Integer, nullable=False)
    punto_venta = db.Column(db.Integer, nullable=False)
    numero_comprobante = db.Column(db.Integer, nullable=False)
    concepto = db.Column(db.Integer, nullable=False, default=1)
    fecha_emision = db.Column(db.Date, nullable=False)

    # Datos del receptor
    doc_tipo_receptor = db.Column(db.Integer)
    doc_nro_receptor = db.Column(db.String(20))
    condicion_iva_receptor_id = db.Column(db.Integer, nullable=False)

    # Importes
    imp_total = db.Column(db.Numeric(14, 2), nullable=False)
    imp_neto = db.Column(db.Numeric(14, 2), default=0)
    imp_iva = db.Column(db.Numeric(14, 2), default=0)
    imp_tot_conc = db.Column(db.Numeric(14, 2), default=0)
    imp_op_ex = db.Column(db.Numeric(14, 2), default=0)
    imp_trib = db.Column(db.Numeric(14, 2), default=0)

    # Moneda
    mon_id = db.Column(db.String(5), default='PES')
    mon_cotiz = db.Column(db.Numeric(14, 6), default=1)

    # Autorización ARCA
    cae = db.Column(db.String(20), nullable=True)
    cae_vencimiento = db.Column(db.Date, nullable=True)
    estado = db.Column(db.String(20), default='pendiente')
    error_codigo = db.Column(db.String(20), nullable=True)
    error_mensaje = db.Column(db.Text, nullable=True)

    # Auditoría de request/response completo
    arca_request = db.Column(db.JSON, nullable=True)
    arca_response = db.Column(db.JSON, nullable=True)

    # Fechas de servicio (solo para concepto 2 o 3)
    fch_serv_desde = db.Column(db.Date, nullable=True)
    fch_serv_hasta = db.Column(db.Date, nullable=True)
    fch_vto_pago = db.Column(db.Date, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=ahora_argentina)
    updated_at = db.Column(db.DateTime, default=ahora_argentina, onupdate=ahora_argentina)

    # Relaciones
    detalles = db.relationship(
        'FacturaDetalle',
        backref='factura',
        cascade='all, delete-orphan',
    )
    comprobantes_asociados = db.relationship(
        'ComprobanteAsociado',
        backref='factura',
        cascade='all, delete-orphan',
    )
    venta = db.relationship('Venta', backref=db.backref('facturas', lazy='dynamic'))

    def __repr__(self):
        return f'<Factura {self.numero_completo}>'

    @property
    def numero_completo(self):
        """Retorna número con formato XXXXX-XXXXXXXX."""
        return f'{self.punto_venta:05d}-{self.numero_comprobante:08d}'

    @property
    def tipo_comprobante_display(self):
        """Retorna el nombre legible del tipo de comprobante."""
        from ..services.arca_constants import TIPO_COMPROBANTE

        return TIPO_COMPROBANTE.get(self.tipo_comprobante, str(self.tipo_comprobante))

    @property
    def estado_display(self):
        """Retorna el estado en formato legible."""
        from ..services.arca_constants import ESTADO_FACTURA

        return ESTADO_FACTURA.get(self.estado, self.estado)

    @property
    def clase(self):
        """Retorna la clase del comprobante (A, B o C)."""
        from ..services.arca_constants import CLASE_POR_TIPO

        return CLASE_POR_TIPO.get(self.tipo_comprobante)

    @property
    def esta_autorizada(self):
        """Verifica si la factura fue autorizada por ARCA."""
        return self.estado == 'autorizada'

    def to_dict(self):
        """Convierte la factura a diccionario."""
        return {
            'id': self.id,
            'venta_id': self.venta_id,
            'tipo_comprobante': self.tipo_comprobante,
            'tipo_comprobante_display': self.tipo_comprobante_display,
            'punto_venta': self.punto_venta,
            'numero_comprobante': self.numero_comprobante,
            'numero_completo': self.numero_completo,
            'clase': self.clase,
            'concepto': self.concepto,
            'fecha_emision': (self.fecha_emision.isoformat() if self.fecha_emision else None),
            'doc_tipo_receptor': self.doc_tipo_receptor,
            'doc_nro_receptor': self.doc_nro_receptor,
            'condicion_iva_receptor_id': self.condicion_iva_receptor_id,
            'imp_total': float(self.imp_total) if self.imp_total else 0,
            'imp_neto': float(self.imp_neto) if self.imp_neto else 0,
            'imp_iva': float(self.imp_iva) if self.imp_iva else 0,
            'imp_tot_conc': float(self.imp_tot_conc) if self.imp_tot_conc else 0,
            'imp_op_ex': float(self.imp_op_ex) if self.imp_op_ex else 0,
            'imp_trib': float(self.imp_trib) if self.imp_trib else 0,
            'mon_id': self.mon_id,
            'mon_cotiz': float(self.mon_cotiz) if self.mon_cotiz else 1,
            'cae': self.cae,
            'cae_vencimiento': (self.cae_vencimiento.isoformat() if self.cae_vencimiento else None),
            'estado': self.estado,
            'estado_display': self.estado_display,
            'esta_autorizada': self.esta_autorizada,
            'error_codigo': self.error_codigo,
            'error_mensaje': self.error_mensaje,
            'created_at': (self.created_at.isoformat() if self.created_at else None),
        }
