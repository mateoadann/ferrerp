"""Rutas del panel de superadministrador."""

from flask import Blueprint

bp = Blueprint('superadmin', __name__, url_prefix='/superadmin')


@bp.route('/')
def index():
    """Panel principal del superadmin (placeholder)."""
    return 'Superadmin'
