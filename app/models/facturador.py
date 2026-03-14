"""Modelo de Facturador — entidad emisora de comprobantes electrónicos."""

from ..extensions import db
from ..utils.helpers import ahora_argentina
from .mixins import EmpresaMixin


class Facturador(EmpresaMixin, db.Model):
    """
    Representa una entidad emisora de comprobantes electrónicos ARCA.
    Una empresa puede tener múltiples facturadores, cada uno con su
    propio CUIT, certificado digital y punto de venta.
    """

    __tablename__ = 'facturadores'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)  # Nombre interno/display
    razon_social = db.Column(db.String(200), nullable=False)  # Razón social legal
    cuit = db.Column(db.String(13), nullable=False)  # XX-XXXXXXXX-X

    # Datos fiscales
    condicion_iva_id = db.Column(db.Integer, nullable=False)
    condicion_iva = db.Column(db.String(100))
    domicilio_fiscal = db.Column(db.String(300))
    numero_iibb = db.Column(db.String(50))  # Ingresos Brutos
    email_fiscal = db.Column(db.String(120))
    inicio_actividades = db.Column(db.Date)

    # ARCA connection
    punto_venta = db.Column(db.Integer, nullable=False)
    certificado = db.Column(db.LargeBinary)
    clave_privada = db.Column(db.LargeBinary)
    certificado_vencimiento = db.Column(db.Date)  # Parsed from cert on upload
    ambiente = db.Column(db.String(20), default='testing')
    habilitado = db.Column(db.Boolean, default=False)

    # State
    activo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=ahora_argentina)
    updated_at = db.Column(db.DateTime, default=ahora_argentina, onupdate=ahora_argentina)

    # Relaciones
    facturas = db.relationship('Factura', backref='facturador', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint(
            'empresa_id',
            'cuit',
            'punto_venta',
            name='uq_facturador_empresa_cuit_pv',
        ),
    )

    @property
    def configuracion_completa(self):
        """Indica si el facturador tiene todos los datos necesarios para emitir."""
        campos = [
            self.cuit,
            self.razon_social,
            self.condicion_iva_id,
            self.punto_venta,
            self.certificado,
            self.clave_privada,
        ]
        return all(c is not None for c in campos)

    @property
    def campos_faltantes(self):
        """Retorna lista de campos requeridos faltantes."""
        faltantes = []
        checks = [
            (self.cuit, 'CUIT'),
            (self.razon_social, 'Razón social'),
            (self.condicion_iva_id, 'Condición IVA'),
            (self.punto_venta, 'Punto de venta'),
            (self.certificado, 'Certificado digital'),
            (self.clave_privada, 'Clave privada'),
        ]
        for valor, nombre in checks:
            if not valor:
                faltantes.append(nombre)
        return faltantes

    @property
    def es_responsable_inscripto(self):
        """Verifica si el facturador es Responsable Inscripto o Agente de Percepción."""
        return self.condicion_iva_id in (1, 11)

    @property
    def es_monotributo(self):
        """Verifica si el facturador es Responsable Monotributo."""
        return self.condicion_iva_id == 6

    @property
    def estado_display(self):
        """Retorna el estado en formato legible."""
        if not self.activo:
            return 'Inactivo'
        if not self.habilitado:
            return 'Deshabilitado'
        if not self.configuracion_completa:
            return 'Incompleto'
        return 'Activo'

    def to_dict(self):
        """Convierte el facturador a diccionario."""
        return {
            'id': self.id,
            'empresa_id': self.empresa_id,
            'nombre': self.nombre,
            'razon_social': self.razon_social,
            'cuit': self.cuit,
            'condicion_iva_id': self.condicion_iva_id,
            'condicion_iva': self.condicion_iva,
            'domicilio_fiscal': self.domicilio_fiscal,
            'numero_iibb': self.numero_iibb,
            'email_fiscal': self.email_fiscal,
            'inicio_actividades': (
                self.inicio_actividades.isoformat() if self.inicio_actividades else None
            ),
            'punto_venta': self.punto_venta,
            'certificado_vencimiento': (
                self.certificado_vencimiento.isoformat() if self.certificado_vencimiento else None
            ),
            'ambiente': self.ambiente,
            'habilitado': self.habilitado,
            'activo': self.activo,
            'configuracion_completa': self.configuracion_completa,
            'campos_faltantes': self.campos_faltantes,
            'estado_display': self.estado_display,
        }

    def __repr__(self):
        return f'<Facturador {self.nombre} ({self.cuit}) PV:{self.punto_venta}>'
