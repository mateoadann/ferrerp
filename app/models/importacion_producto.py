"""Modelo de auditoría para importaciones masivas de productos."""

from ..extensions import db
from ..utils.helpers import ahora_argentina
from .mixins import EmpresaMixin


class ImportacionProducto(EmpresaMixin, db.Model):
    """Registro de auditoría para importaciones masivas de productos."""

    __tablename__ = 'importaciones_producto'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    nombre_archivo = db.Column(db.String(255), nullable=False)
    total_filas = db.Column(db.Integer, nullable=False, default=0)
    filas_importadas = db.Column(db.Integer, nullable=False, default=0)
    filas_actualizadas = db.Column(db.Integer, nullable=False, default=0)
    filas_omitidas = db.Column(db.Integer, nullable=False, default=0)
    errores_count = db.Column(db.Integer, nullable=False, default=0)
    categorias_creadas = db.Column(db.Integer, nullable=False, default=0)
    modo_duplicados = db.Column(db.String(20), nullable=False, default='saltar')
    created_at = db.Column(db.DateTime, nullable=False, default=ahora_argentina)

    # Relaciones
    usuario = db.relationship('Usuario')
    empresa = db.relationship(
        'Empresa',
        backref=db.backref(
            'importaciones_producto',
            lazy='dynamic',
            order_by='ImportacionProducto.created_at.desc()',
        ),
    )

    def __repr__(self):
        return f'<ImportacionProducto {self.id} ' f'archivo={self.nombre_archivo}>'
