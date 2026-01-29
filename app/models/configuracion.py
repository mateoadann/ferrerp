"""Modelo de Configuración."""

import json
from decimal import Decimal
from ..extensions import db


class Configuracion(db.Model):
    """Modelo de configuración del sistema."""

    __tablename__ = 'configuraciones'

    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(50), unique=True, nullable=False, index=True)
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
    def get(cls, clave, default=None):
        """
        Obtiene el valor de una configuración por clave.

        Args:
            clave: Clave de la configuración
            default: Valor por defecto si no existe

        Returns:
            El valor de la configuración o el default
        """
        config = cls.query.filter_by(clave=clave).first()
        return config.get_valor() if config else default

    @classmethod
    def set(cls, clave, valor, tipo='string'):
        """
        Establece el valor de una configuración.

        Args:
            clave: Clave de la configuración
            valor: Valor a establecer
            tipo: Tipo de dato ('string', 'integer', 'decimal', 'boolean', 'json')
        """
        config = cls.query.filter_by(clave=clave).first()
        if not config:
            config = cls(clave=clave, tipo=tipo)
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
