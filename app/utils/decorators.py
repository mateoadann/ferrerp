"""Decoradores personalizados para la aplicación."""

from functools import wraps
from flask import flash, redirect, url_for, request
from flask_login import current_user


def admin_required(f):
    """
    Decorador que requiere que el usuario sea administrador.
    Debe usarse después de @login_required.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Por favor, inicia sesión para acceder a esta página.', 'warning')
            return redirect(url_for('auth.login', next=request.url))

        if not current_user.es_administrador:
            flash('No tienes permisos para acceder a esta sección.', 'danger')
            return redirect(url_for('dashboard.index'))

        return f(*args, **kwargs)
    return decorated_function


def caja_abierta_required(f):
    """
    Decorador que requiere que haya una caja abierta.
    Debe usarse después de @login_required.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from ..models import Caja

        caja_abierta = Caja.query.filter_by(estado='abierta').first()

        if not caja_abierta:
            flash('No hay caja abierta. Debes abrir la caja para realizar esta operación.', 'warning')
            return redirect(url_for('caja.index'))

        return f(*args, **kwargs)
    return decorated_function


def vendedor_o_admin_required(f):
    """
    Decorador que permite acceso a vendedores y administradores.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Por favor, inicia sesión para acceder a esta página.', 'warning')
            return redirect(url_for('auth.login', next=request.url))

        if current_user.rol not in ('administrador', 'vendedor'):
            flash('No tienes permisos para acceder a esta sección.', 'danger')
            return redirect(url_for('dashboard.index'))

        return f(*args, **kwargs)
    return decorated_function
