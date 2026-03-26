"""Rutas de autenticación."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..forms.auth_forms import LoginForm
from ..forms.registro_forms import RegistroForm
from ..models import Configuracion, Empresa, Usuario

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Página de inicio de sesión."""
    # Si ya está autenticado, redirigir según rol
    if current_user.is_authenticated:
        if current_user.es_superadmin:
            return redirect(url_for('superadmin.index'))
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

            # Verificar si debe cambiar contraseña
            if usuario.debe_cambiar_password:
                flash('Debes cambiar tu contraseña antes de continuar.', 'warning')
                return redirect(url_for('auth.cambiar_password'))

            # Redirigir según rol
            if usuario.es_superadmin:
                return redirect(url_for('superadmin.index'))

            # Redirigir a la página solicitada o al dashboard
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('dashboard.index'))
        else:
            flash('Email o contraseña incorrectos.', 'danger')

    return render_template('auth/login.html', form=form)


@bp.route('/registro', methods=['GET', 'POST'])
def registro():
    """Registro de nueva empresa y usuario administrador."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    form = RegistroForm()

    if form.validate_on_submit():
        # Crear empresa
        empresa = Empresa(
            nombre=form.empresa_nombre.data,
            cuit=form.empresa_cuit.data or None,
            direccion=form.empresa_direccion.data or None,
            telefono=form.empresa_telefono.data or None,
        )
        db.session.add(empresa)
        db.session.flush()

        # Crear usuario administrador
        usuario = Usuario(
            email=form.email.data.lower(),
            nombre=form.nombre.data,
            rol='administrador',
            activo=True,
            empresa_id=empresa.id,
        )
        usuario.set_password(form.password.data)
        db.session.add(usuario)

        db.session.commit()

        # Propagar datos de empresa a configuración
        Configuracion.set(
            'nombre_negocio', empresa.nombre, 'string', empresa_id=empresa.id
        )
        Configuracion.set(
            'cuit', empresa.cuit or '', 'string', empresa_id=empresa.id
        )
        Configuracion.set(
            'direccion', empresa.direccion or '', 'string', empresa_id=empresa.id
        )
        Configuracion.set(
            'telefono', empresa.telefono or '', 'string', empresa_id=empresa.id
        )
        Configuracion.set(
            'precios_con_iva', False, 'boolean', empresa_id=empresa.id
        )

        login_user(usuario)
        flash(
            f'¡Bienvenido a FerrERP! Tu empresa "{empresa.nombre}" '
            'fue creada exitosamente.',
            'success',
        )
        return redirect(url_for('dashboard.index'))

    return render_template('auth/registro.html', form=form)


@bp.route('/logout')
@login_required
def logout():
    """Cerrar sesión."""
    logout_user()
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/cambiar-password', methods=['GET', 'POST'])
@login_required
def cambiar_password():
    """Cambio obligatorio de contraseña."""
    from ..forms.cambiar_password_forms import CambiarPasswordForm

    form = CambiarPasswordForm()

    if form.validate_on_submit():
        if not current_user.check_password(form.password_actual.data):
            flash('La contraseña actual es incorrecta.', 'danger')
            return render_template('auth/cambiar_password.html', form=form)

        current_user.set_password(form.password_nueva.data)
        current_user.debe_cambiar_password = False
        db.session.commit()

        flash('Contraseña cambiada exitosamente.', 'success')

        if current_user.es_superadmin:
            return redirect(url_for('superadmin.index'))
        return redirect(url_for('dashboard.index'))

    return render_template('auth/cambiar_password.html', form=form)
