"""Rutas de autenticación."""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from ..forms.auth_forms import LoginForm
from ..models import Usuario

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Página de inicio de sesión."""
    # Si ya está autenticado, redirigir al dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    form = LoginForm()

    if form.validate_on_submit():
        # Buscar usuario por email
        usuario = Usuario.query.filter_by(email=form.email.data.lower()).first()

        if usuario and usuario.check_password(form.password.data):
            # Verificar si el usuario está activo
            if not usuario.activo:
                flash('Tu cuenta está desactivada. Contacta al administrador.', 'danger')
                return render_template('auth/login.html', form=form)

            # Iniciar sesión
            login_user(usuario, remember=form.remember.data)

            # Redirigir a la página solicitada o al dashboard
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('dashboard.index'))
        else:
            flash('Email o contraseña incorrectos.', 'danger')

    return render_template('auth/login.html', form=form)


@bp.route('/logout')
@login_required
def logout():
    """Cerrar sesión."""
    logout_user()
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('auth.login'))
