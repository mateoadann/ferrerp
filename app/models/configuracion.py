"""Modelo de Configuración."""

import json
from decimal import Decimal

from flask_login import current_user
from sqlalchemy import UniqueConstraint

from ..extensions import db
from .mixins import EmpresaMixin


class Configuracion(EmpresaMixin, db.Model):
    """Modelo de configuración del sistema."""

    __tablename__ = 'configuraciones'
    __table_args__ = (
        UniqueConstraint(
            'empresa_id', 'clave', name='uq_configuraciones_empresa_clave'
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(50), nullable=False, index=True)
    valor = db.Column(db.Text)
    tipo = db.Column(
        db.Enum('string', 'integer', 'decimal', 'boolean', 'json', name='tipo_configuracion'),
        default='string',
        nullable=False
    )

    def __repr__(self):
        return f'<Configuracion {self.clave}>'

    def get_valor(self):
        """Obtiene el valor convertido al tipo correcto."""
        if self.valor is None:
            return None

        if self.tipo == 'integer':
            return int(self.valor)
        elif self.tipo == 'decimal':
            return Decimal(self.valor)
        elif self.tipo == 'boolean':
            return self.valor.lower() in ('true', '1', 'yes', 'si')
        elif self.tipo == 'json':
            return json.loads(self.valor)
        else:
            return self.valor

    def set_valor(self, valor):
        """Establece el valor convirtiéndolo a string."""
        if valor is None:
            self.valor = None
        elif self.tipo == 'json':
            self.valor = json.dumps(valor)
        elif self.tipo == 'boolean':
            self.valor = 'true' if valor else 'false'
        else:
            self.valor = str(valor)

    @classmethod
    def get(cls, clave, default=None, empresa_id=None):
        """
        Obtiene el valor de una configuración por clave y empresa.

        Args:
            clave: Clave de la configuración
            default: Valor por defecto si no existe
            empresa_id: ID de la empresa (si no se pasa, usa la del usuario actual)

        Returns:
            El valor de la configuración o el default
        """
        if empresa_id is None:
            try:
                if not current_user.is_authenticated:
                    return default
                empresa_id = current_user.empresa_id
            except AttributeError:
                return default
        config = cls.query.filter_by(clave=clave, empresa_id=empresa_id).first()
        return config.get_valor() if config else default

    @classmethod
    def set(cls, clave, valor, tipo='string', empresa_id=None):
        """
        Establece el valor de una configuración.

        Args:
            clave: Clave de la configuración
            valor: Valor a establecer
            tipo: Tipo de dato ('string', 'integer', 'decimal', 'boolean', 'json')
            empresa_id: ID de la empresa (si no se pasa, usa la del usuario actual)
        """
        if empresa_id is None:
            try:
                if not current_user.is_authenticated:
                    raise ValueError('Se requiere empresa_id o usuario autenticado')
                empresa_id = current_user.empresa_id
            except AttributeError:
                raise ValueError('Se requiere empresa_id o usuario autenticado')
        config = cls.query.filter_by(clave=clave, empresa_id=empresa_id).first()
        if not config:
            config = cls(clave=clave, tipo=tipo, empresa_id=empresa_id)
            db.session.add(config)
        config.tipo = tipo
        config.set_valor(valor)
        db.session.commit()
        return config

    def to_dict(self):
        """Convierte la configuración a diccionario."""
        return {
            'id': self.id,
            'clave': self.clave,
            'valor': self.get_valor(),
            'tipo': self.tipo
        }
