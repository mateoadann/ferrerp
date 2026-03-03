"""Mixins para modelos multi-tenant."""

from flask import abort
from flask_login import current_user

from ..extensions import db


class EmpresaMixin:
    """Mixin que agrega empresa_id y métodos de filtrado por empresa."""

    empresa_id = db.Column(
        db.Integer, db.ForeignKey('empresas.id'), nullable=False, index=True
    )

    @classmethod
    def query_empresa(cls):
        """Retorna query filtrada por la empresa del usuario actual."""
        return cls.query.filter_by(empresa_id=current_user.empresa_id)

    @classmethod
    def get_o_404(cls, id):
        """Obtiene un registro por ID verificando que pertenezca a la empresa actual."""
        registro = cls.query.filter_by(
            id=id, empresa_id=current_user.empresa_id
        ).first()
        if registro is None:
            abort(404)
        return registro
