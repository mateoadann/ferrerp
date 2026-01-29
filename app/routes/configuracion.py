"""Rutas de configuración."""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required

from ..extensions import db
from ..models import Usuario, Categoria, Configuracion
from ..forms.usuario_forms import UsuarioForm, UsuarioEditForm
from ..forms.producto_forms import CategoriaForm
from ..forms.configuracion_forms import ConfiguracionForm
from ..utils.helpers import paginar_query, es_peticion_htmx
from ..utils.decorators import admin_required

bp = Blueprint('configuracion', __name__, url_prefix='/configuracion')


@bp.route('/', methods=['GET', 'POST'])
@login_required
@admin_required
def index():
    """Configuración general del sistema."""
    form = ConfiguracionForm()

    if request.method == 'GET':
        # Cargar valores actuales
        form.nombre_negocio.data = Configuracion.get('nombre_negocio', 'Ferretería')
        form.direccion.data = Configuracion.get('direccion', '')
        form.telefono.data = Configuracion.get('telefono', '')
        form.cuit.data = Configuracion.get('cuit', '')
        form.iva_porcentaje.data = Configuracion.get('iva_porcentaje', 21)
        form.precios_con_iva.data = Configuracion.get('precios_con_iva', True)

    if form.validate_on_submit():
        Configuracion.set('nombre_negocio', form.nombre_negocio.data, 'string')
        Configuracion.set('direccion', form.direccion.data, 'string')
        Configuracion.set('telefono', form.telefono.data, 'string')
        Configuracion.set('cuit', form.cuit.data, 'string')
        Configuracion.set('iva_porcentaje', str(form.iva_porcentaje.data), 'decimal')
        Configuracion.set('precios_con_iva', form.precios_con_iva.data, 'boolean')

        flash('Configuración guardada correctamente.', 'success')
        return redirect(url_for('configuracion.index'))

    return render_template('configuracion/general.html', form=form)


@bp.route('/usuarios')
@login_required
@admin_required
def usuarios():
    """Listado de usuarios."""
    page = request.args.get('page', 1, type=int)
    usuarios = Usuario.query.order_by(Usuario.nombre).paginate(page=page, per_page=20)

    return render_template('configuracion/usuarios.html', usuarios=usuarios)


@bp.route('/usuarios/nuevo', methods=['GET', 'POST'])
@login_required
@admin_required
def nuevo_usuario():
    """Crear nuevo usuario."""
    form = UsuarioForm()

    if form.validate_on_submit():
        usuario = Usuario(
            email=form.email.data.lower(),
            nombre=form.nombre.data,
            rol=form.rol.data,
            activo=form.activo.data
        )
        usuario.set_password(form.password.data)

        db.session.add(usuario)
        db.session.commit()

        flash(f'Usuario "{usuario.nombre}" creado correctamente.', 'success')
        return redirect(url_for('configuracion.usuarios'))

    return render_template(
        'configuracion/usuario_form.html',
        form=form,
        titulo='Nuevo Usuario'
    )


@bp.route('/usuarios/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_usuario(id):
    """Editar usuario."""
    usuario = Usuario.query.get_or_404(id)
    form = UsuarioEditForm(original_email=usuario.email, obj=usuario)

    if form.validate_on_submit():
        usuario.email = form.email.data.lower()
        usuario.nombre = form.nombre.data
        usuario.rol = form.rol.data
        usuario.activo = form.activo.data

        if form.password.data:
            usuario.set_password(form.password.data)

        db.session.commit()

        flash(f'Usuario "{usuario.nombre}" actualizado correctamente.', 'success')
        return redirect(url_for('configuracion.usuarios'))

    return render_template(
        'configuracion/usuario_form.html',
        form=form,
        titulo='Editar Usuario',
        usuario=usuario
    )


@bp.route('/usuarios/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_usuario(id):
    """Activar/desactivar usuario."""
    usuario = Usuario.query.get_or_404(id)

    # No permitir desactivar al propio usuario
    from flask_login import current_user
    if usuario.id == current_user.id:
        flash('No puedes desactivar tu propio usuario.', 'danger')
        return redirect(url_for('configuracion.usuarios'))

    usuario.activo = not usuario.activo
    db.session.commit()

    estado = 'activado' if usuario.activo else 'desactivado'
    flash(f'Usuario "{usuario.nombre}" {estado}.', 'success')

    if es_peticion_htmx():
        return '', 204

    return redirect(url_for('configuracion.usuarios'))


@bp.route('/categorias', methods=['GET', 'POST'])
@login_required
@admin_required
def categorias():
    """Gestión de categorías."""
    form = CategoriaForm()

    if form.validate_on_submit():
        # Verificar nombre único
        existente = Categoria.query.filter_by(nombre=form.nombre.data).first()
        if existente:
            flash('Ya existe una categoría con ese nombre.', 'danger')
        else:
            categoria = Categoria(
                nombre=form.nombre.data,
                descripcion=form.descripcion.data,
                activa=form.activa.data
            )
            db.session.add(categoria)
            db.session.commit()
            flash(f'Categoría "{categoria.nombre}" creada.', 'success')
            return redirect(url_for('configuracion.categorias'))

    categorias = Categoria.query.order_by(Categoria.nombre).all()

    return render_template(
        'configuracion/categorias.html',
        form=form,
        categorias=categorias
    )


@bp.route('/categorias/<int:id>/editar', methods=['POST'])
@login_required
@admin_required
def editar_categoria(id):
    """Editar categoría (HTMX)."""
    categoria = Categoria.query.get_or_404(id)

    nombre = request.form.get('nombre')
    descripcion = request.form.get('descripcion')

    if nombre:
        # Verificar nombre único
        existente = Categoria.query.filter(
            Categoria.nombre == nombre,
            Categoria.id != id
        ).first()
        if existente:
            flash('Ya existe una categoría con ese nombre.', 'danger')
        else:
            categoria.nombre = nombre
            categoria.descripcion = descripcion
            db.session.commit()
            flash(f'Categoría "{categoria.nombre}" actualizada.', 'success')

    return redirect(url_for('configuracion.categorias'))


@bp.route('/categorias/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_categoria(id):
    """Activar/desactivar categoría."""
    categoria = Categoria.query.get_or_404(id)
    categoria.activa = not categoria.activa
    db.session.commit()

    estado = 'activada' if categoria.activa else 'desactivada'
    flash(f'Categoría "{categoria.nombre}" {estado}.', 'success')

    if es_peticion_htmx():
        return '', 204

    return redirect(url_for('configuracion.categorias'))
