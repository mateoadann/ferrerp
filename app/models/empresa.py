"""Modelo de Empresa (tenant)."""

from ..extensions import db
from ..utils.helpers import ahora_argentina


class Empresa(db.Model):
    """Modelo de empresa/negocio (tenant del sistema)."""

    __tablename__ = 'empresas'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    cuit = db.Column(db.String(13))
    direccion = db.Column(db.String(200))
    telefono = db.Column(db.String(20))
    email = db.Column(db.String(120))
    activa = db.Column(db.Boolean, default=True, nullable=False)
    aprobada = db.Column(db.Boolean, default=False, nullable=False)

    # Datos fiscales ARCA
    condicion_iva_id = db.Column(db.Integer, nullable=True)
    condicion_iva = db.Column(db.String(100), nullable=True)
    inicio_actividades = db.Column(db.Date, nullable=True)

    # Configuración facturación electrónica ARCA
    punto_venta_arca = db.Column(db.Integer, nullable=True)
    certificado_arca = db.Column(db.LargeBinary, nullable=True)
    clave_privada_arca = db.Column(db.LargeBinary, nullable=True)
    ambiente_arca = db.Column(db.String(20), default='testing')
    arca_habilitado = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=ahora_argentina)
    updated_at = db.Column(db.DateTime, default=ahora_argentina, onupdate=ahora_argentina)

    # Relaciones
    usuarios = db.relationship('Usuario', backref='empresa', lazy='dynamic')

    def __repr__(self):
        return f'<Empresa {self.nombre}>'

    @property
    def es_responsable_inscripto(self):
        """Verifica si la empresa es Responsable Inscripto o Agente de Percepción."""
        return self.condicion_iva_id in (1, 11)

    @property
    def es_monotributo(self):
        """Verifica si la empresa es Responsable Monotributo."""
        return self.condicion_iva_id == 6

    def to_dict(self):
        """Convierte la empresa a diccionario."""
        return {
            'id': self.id,
            'nombre': self.nombre,
            'cuit': self.cuit,
            'direccion': self.direccion,
            'telefono': self.telefono,
            'email': self.email,
            'activa': self.activa,
            'condicion_iva_id': self.condicion_iva_id,
            'condicion_iva': self.condicion_iva,
            'inicio_actividades': (
                self.inicio_actividades.isoformat() if self.inicio_actividades else None
            ),
            'punto_venta_arca': self.punto_venta_arca,
            'ambiente_arca': self.ambiente_arca,
            'arca_habilitado': self.arca_habilitado,
            'es_responsable_inscripto': self.es_responsable_inscripto,
            'es_monotributo': self.es_monotributo,
            'created_at': (self.created_at.isoformat() if self.created_at else None),
        }
