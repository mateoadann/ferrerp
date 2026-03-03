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


@bp.route('/registro', methods=['GET', 'POST'])
def registro():
    """Registro de nueva empresa y usuario owner."""
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

        # Crear usuario owner
        usuario = Usuario(
            email=form.email.data.lower(),
            nombre=form.nombre.data,
            rol='owner',
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
