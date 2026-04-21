"""Modelo de Cheque."""

from datetime import date, timedelta

from ..extensions import db
from ..utils.helpers import ahora_argentina
from .mixins import EmpresaMixin

# Transiciones de estado válidas por tipo de cheque
TRANSICIONES_CHEQUE = {
    'recibido': {
        'en_cartera': ['endosado', 'cobrado', 'sin_fondos'],
    },
    'emitido': {
        'en_cartera': ['cobrado'],
    },
}


def transicion_valida(tipo, estado_actual, nuevo_estado):
    """Verifica si una transición de estado es válida.

    Args:
        tipo: 'recibido' o 'emitido'
        estado_actual: estado actual del cheque
        nuevo_estado: estado destino propuesto

    Returns:
        True si la transición es válida
    """
    transiciones = TRANSICIONES_CHEQUE.get(tipo, {})
    estados_permitidos = transiciones.get(estado_actual, [])
    return nuevo_estado in estados_permitidos


class Cheque(EmpresaMixin, db.Model):
    """Modelo de cheque recibido o emitido."""

    __tablename__ = 'cheques'

    id = db.Column(db.Integer, primary_key=True)
    numero_cheque = db.Column(db.String(50), nullable=False)
    banco_id = db.Column(
        db.Integer, db.ForeignKey('bancos.id'), nullable=True
    )
    fecha_emision = db.Column(db.Date, nullable=True)
    fecha_vencimiento = db.Column(db.Date, nullable=False)
    importe = db.Column(db.Numeric(12, 2), nullable=False)
    tipo = db.Column(db.String(20), nullable=False, default='recibido')
    tipo_cheque = db.Column(
        db.String(20), nullable=False, default='cheque'
    )
    referencia_tipo = db.Column(db.String(30), nullable=True)
    referencia_id = db.Column(db.Integer, nullable=True)
    estado = db.Column(db.String(20), nullable=False, default='en_cartera')
    destinatario = db.Column(db.String(200), nullable=True)
    observaciones = db.Column(db.Text, nullable=True)
    cliente_id = db.Column(
        db.Integer, db.ForeignKey('clientes.id'), nullable=True
    )
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey('usuarios.id'),
        nullable=False,
    )
    created_at = db.Column(db.DateTime, default=ahora_argentina, index=True)

    # Relaciones
    empresa = db.relationship('Empresa', backref='cheques')
    usuario = db.relationship('Usuario', backref='cheques')
    cliente = db.relationship('Cliente', backref='cheques')

    def __repr__(self):
        return f'<Cheque {self.id} - #{self.numero_cheque} ${self.importe}>'

    @property
    def esta_vencido(self):
        """Verifica si el cheque está vencido."""
        return self.fecha_vencimiento < date.today()

    @property
    def esta_proximo_a_vencer(self):
        """Verifica si el cheque vence en los próximos 7 días."""
        hoy = date.today()
        return hoy <= self.fecha_vencimiento <= hoy + timedelta(days=7)

    @property
    def transiciones_disponibles(self):
        """Retorna las transiciones de estado disponibles."""
        transiciones = TRANSICIONES_CHEQUE.get(self.tipo, {})
        return transiciones.get(self.estado, [])

    def to_dict(self):
        """Convierte el cheque a diccionario."""
        return {
            'id': self.id,
            'numero_cheque': self.numero_cheque,
            'banco_id': self.banco_id,
            'banco_nombre': self.banco.nombre if self.banco else None,
            'tipo': self.tipo,
            'tipo_cheque': self.tipo_cheque,
            'fecha_emision': (
                self.fecha_emision.isoformat() if self.fecha_emision else None
            ),
            'fecha_vencimiento': (
                self.fecha_vencimiento.isoformat()
                if self.fecha_vencimiento
                else None
            ),
            'importe': float(self.importe) if self.importe else 0,
            'referencia_tipo': self.referencia_tipo,
            'referencia_id': self.referencia_id,
            'estado': self.estado,
            'cliente_id': self.cliente_id,
            'cliente_nombre': (
                self.cliente.nombre if self.cliente else None
            ),
            'destinatario': self.destinatario,
            'observaciones': self.observaciones,
            'usuario_nombre': (
                self.usuario.nombre if self.usuario else None
            ),
            'created_at': (
                self.created_at.isoformat() if self.created_at else None
            ),
        }
