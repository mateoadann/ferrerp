"""Modelos de integracion con Tienda Nube."""

from sqlalchemy import UniqueConstraint

from ..extensions import db
from ..utils.helpers import ahora_argentina
from .mixins import EmpresaMixin


class TiendaNubeCredencial(EmpresaMixin, db.Model):
    """Credenciales OAuth de Tienda Nube por empresa."""

    __tablename__ = 'tiendanube_credenciales'
    __table_args__ = (
        UniqueConstraint('empresa_id', name='uq_tiendanube_credenciales_empresa'),
        UniqueConstraint('tienda_id_externo', name='uq_tiendanube_credenciales_tienda_id_externo'),
    )

    id = db.Column(db.Integer, primary_key=True)
    tn_app_id = db.Column(db.String(100), nullable=False)
    tn_app_secret = db.Column(db.String(255), nullable=False)
    tienda_id_externo = db.Column(db.String(50), nullable=True, index=True)
    usuario_id_externo = db.Column(db.String(50), nullable=True)
    access_token = db.Column(db.Text, nullable=True)
    token_type = db.Column(db.String(30), nullable=False, default='bearer')
    scope = db.Column(db.String(255))
    activo = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=ahora_argentina)
    updated_at = db.Column(db.DateTime, default=ahora_argentina, onupdate=ahora_argentina)

    def __repr__(self):
        return f'<TiendaNubeCredencial {self.tienda_id_externo}>'

    def to_dict(self):
        """Convierte la credencial a diccionario."""
        return {
            'id': self.id,
            'empresa_id': self.empresa_id,
            'tienda_id_externo': self.tienda_id_externo,
            'usuario_id_externo': self.usuario_id_externo,
            'token_type': self.token_type,
            'scope': self.scope,
            'activo': self.activo,
            'tiene_access_token': bool(self.access_token),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class SyncLog(EmpresaMixin, db.Model):
    """Registro de sincronizaciones de Tienda Nube."""

    __tablename__ = 'tiendanube_sync_logs'

    id = db.Column(db.Integer, primary_key=True)
    recurso = db.Column(db.String(50), nullable=False, index=True)
    direccion = db.Column(
        db.Enum('importacion', 'exportacion', name='direccion_sync'),
        nullable=False,
    )
    estado = db.Column(
        db.Enum('pendiente', 'exitoso', 'error', name='estado_sync'),
        nullable=False,
        default='pendiente',
        index=True,
    )
    referencia_id_externo = db.Column(db.String(100), index=True)
    mensaje = db.Column(db.Text)
    payload = db.Column(db.Text)
    respuesta = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=ahora_argentina, index=True)
    updated_at = db.Column(db.DateTime, default=ahora_argentina, onupdate=ahora_argentina)

    def __repr__(self):
        return f'<SyncLog {self.recurso} - {self.estado}>'

    def to_dict(self):
        """Convierte el log de sincronizacion a diccionario."""
        return {
            'id': self.id,
            'empresa_id': self.empresa_id,
            'recurso': self.recurso,
            'direccion': self.direccion,
            'estado': self.estado,
            'referencia_id_externo': self.referencia_id_externo,
            'mensaje': self.mensaje,
            'payload': self.payload,
            'respuesta': self.respuesta,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
