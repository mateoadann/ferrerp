"""Rutas de configuración."""

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms.configuracion_forms import ConfiguracionForm
from ..forms.producto_forms import CategoriaForm
from ..forms.usuario_forms import UsuarioEditForm, UsuarioForm
from ..models import Categoria, Configuracion, Usuario
from ..utils.decorators import admin_required
from ..utils.helpers import es_peticion_htmx

bp = Blueprint('configuracion', __name__, url_prefix='/configuracion')


@bp.route('/', methods=['GET', 'POST'])
@login_required
@admin_required
def index():
    """Configuración general del sistema."""
    form = ConfiguracionForm()

    if request.method == 'GET':
        # Cargar valores actuales (Configuracion.get ya filtra por empresa)
        form.nombre_negocio.data = Configuracion.get('nombre_negocio', default='Ferretería')
        form.direccion.data = Configuracion.get('direccion', default='')
        form.telefono.data = Configuracion.get('telefono', default='')
        form.cuit.data = Configuracion.get('cuit', default='')
        form.precios_con_iva.data = Configuracion.get('precios_con_iva', default=False)

    if form.validate_on_submit():
        Configuracion.set('nombre_negocio', form.nombre_negocio.data, 'string')
        Configuracion.set('direccion', form.direccion.data, 'string')
        Configuracion.set('telefono', form.telefono.data, 'string')
        Configuracion.set('cuit', form.cuit.data, 'string')
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
    usuarios = (
        Usuario.query.filter_by(empresa_id=current_user.empresa_id)
        .order_by(Usuario.nombre)
        .paginate(page=page, per_page=20)
    )

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
            activo=form.activo.data,
            empresa_id=current_user.empresa_id,
        )
        usuario.set_password(form.password.data)

        db.session.add(usuario)
        db.session.commit()

        flash(f'Usuario "{usuario.nombre}" creado correctamente.', 'success')
        return redirect(url_for('configuracion.usuarios'))

    return render_template('configuracion/usuario_form.html', form=form, titulo='Nuevo Usuario')


@bp.route('/usuarios/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_usuario(id):
    """Editar usuario."""
    usuario = Usuario.query.filter_by(
        id=id, empresa_id=current_user.empresa_id
    ).first_or_404()
    form = UsuarioEditForm(original_email=usuario.email, obj=usuario)

    if form.validate_on_submit():
        # Validar que no quede la empresa sin administradores
        if usuario.rol == 'administrador' and form.rol.data == 'vendedor':
            admins_empresa = Usuario.query.filter_by(
                empresa_id=current_user.empresa_id,
                rol='administrador',
                activo=True,
            ).count()
            if admins_empresa <= 1:
                flash(
                    'No se puede cambiar el rol. Debe haber al menos '
                    'un administrador activo en la empresa.',
                    'danger',
                )
                return redirect(url_for('configuracion.editar_usuario', id=id))

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
        'configuracion/usuario_form.html', form=form, titulo='Editar Usuario', usuario=usuario
    )


@bp.route('/usuarios/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_usuario(id):
    """Activar/desactivar usuario."""
    usuario = Usuario.query.filter_by(
        id=id, empresa_id=current_user.empresa_id
    ).first_or_404()

    if usuario.id == current_user.id:
        flash('No puedes desactivar tu propio usuario.', 'danger')
        return redirect(url_for('configuracion.usuarios'))

    # Validar que no quede la empresa sin administradores activos
    if usuario.rol == 'administrador' and usuario.activo:
        admins_activos = Usuario.query.filter_by(
            empresa_id=current_user.empresa_id,
            rol='administrador',
            activo=True,
        ).count()
        if admins_activos <= 1:
            flash(
                'No se puede desactivar. Debe haber al menos '
                'un administrador activo en la empresa.',
                'danger',
            )
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
        padre_id = form.padre_id.data or None

        # Verificar nombre único por nivel dentro de la empresa
        existente = Categoria.query_empresa().filter_by(
            nombre=form.nombre.data,
            padre_id=padre_id,
        ).first()
        if existente:
            flash('Ya existe una categoría con ese nombre en ese nivel.', 'danger')
        else:
            categoria = Categoria(
                nombre=form.nombre.data,
                descripcion=form.descripcion.data,
                padre_id=padre_id,
                activa=form.activa.data,
                empresa_id=current_user.empresa_id,
            )
            db.session.add(categoria)
            db.session.commit()
            flash(f'Categoría "{categoria.nombre}" creada.', 'success')
            return redirect(url_for('configuracion.categorias'))

    categorias_padre = (
        Categoria.query_empresa()
        .filter_by(padre_id=None)
        .order_by(Categoria.nombre)
        .all()
    )

    return render_template(
        'configuracion/categorias.html', form=form, categorias_padre=categorias_padre
    )


@bp.route('/categorias/<int:id>/editar', methods=['POST'])
@login_required
@admin_required
def editar_categoria(id):
    """Editar categoría (HTMX)."""
    categoria = Categoria.get_o_404(id)

    nombre = request.form.get('nombre')
    descripcion = request.form.get('descripcion')
    padre_id = request.form.get('padre_id', 0, type=int) or None

    if nombre:
        # Verificar nombre único por nivel dentro de la empresa
        existente = Categoria.query_empresa().filter(
            Categoria.nombre == nombre, Categoria.padre_id == padre_id, Categoria.id != id
        ).first()
        if existente:
            flash('Ya existe una categoría con ese nombre en ese nivel.', 'danger')
        else:
            categoria.nombre = nombre
            categoria.descripcion = descripcion
            categoria.padre_id = padre_id
            db.session.commit()
            flash(f'Categoría "{categoria.nombre}" actualizada.', 'success')

    return redirect(url_for('configuracion.categorias'))


@bp.route('/categorias/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_categoria(id):
    """Activar/desactivar categoría."""
    categoria = Categoria.get_o_404(id)
    categoria.activa = not categoria.activa

    if not categoria.activa and categoria.es_padre:
        for subcategoria in categoria.subcategorias:
            subcategoria.activa = False

    db.session.commit()

    estado = 'activada' if categoria.activa else 'desactivada'
    flash(f'Categoría "{categoria.nombre}" {estado}.', 'success')

    if es_peticion_htmx():
        return '', 204

    return redirect(url_for('configuracion.categorias'))


@bp.route('/api/subcategorias/<int:padre_id>')
@login_required
def api_subcategorias(padre_id):
    """Retorna subcategorías activas por categoría padre."""
    subcategorias = (
        Categoria.query_empresa()
        .filter_by(padre_id=padre_id, activa=True)
        .order_by(Categoria.nombre)
        .all()
    )

    return jsonify(
        [
            {
                'id': subcategoria.id,
                'nombre': subcategoria.nombre,
                'nombre_completo': subcategoria.nombre_completo,
            }
            for subcategoria in subcategorias
        ]
    )
