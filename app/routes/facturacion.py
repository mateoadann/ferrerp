"""Rutas de facturación."""

from flask import Blueprint, render_template
from flask_login import login_required

bp = Blueprint('facturacion', __name__, url_prefix='/facturacion')


@bp.route('/')
@login_required
def index():
    """Página placeholder de facturación."""
    return render_template('facturacion/proximamente.html')
