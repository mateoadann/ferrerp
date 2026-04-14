"""Rutas de configuración."""

import os

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from ..extensions import db
from ..forms.configuracion_forms import ConfiguracionForm
from ..forms.producto_forms import CategoriaForm
from ..forms.usuario_forms import UsuarioEditForm, UsuarioForm
from ..models import Categoria, Configuracion, Usuario
from ..utils.decorators import admin_required, empresa_aprobada_required
from ..utils.helpers import es_peticion_htmx

bp = Blueprint('configuracion', __name__, url_prefix='/configuracion')

EXTENSIONES_PERMITIDAS = {'png', 'jpg', 'jpeg'}
MAX_LOGO_WIDTH = 400


def _extension_permitida(filename):
    """Verifica que la extensión del archivo sea permitida."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in EXTENSIONES_PERMITIDAS


def _directorio_logos():
    """Retorna la ruta al directorio de logos, creándolo si no existe."""
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'logos')
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def _eliminar_logo_anterior(empresa_id, upload_dir):
    """Elimina archivos de logo anteriores de la empresa."""
    for ext in EXTENSIONES_PERMITIDAS:
        filepath = os.path.join(upload_dir, f'empresa_{empresa_id}_logo.{ext}')
        if os.path.exists(filepath):
            os.remove(filepath)


def _guardar_logo(archivo, empresa_id):
    """Valida, redimensiona y guarda el logo de la empresa.

    Args:
        archivo: FileStorage del archivo subido.
        empresa_id: ID de la empresa.

    Returns:
        Nombre del archivo guardado.

    Raises:
        ValueError: Si el formato no es permitido.
    """
    if not archivo or not archivo.filename:
        return None

    if not _extension_permitida(archivo.filename):
        raise ValueError('Formato no permitido. Use PNG o JPG.')

    ext = archivo.filename.rsplit('.', 1)[1].lower()
    if ext == 'jpeg':
        ext = 'jpg'
    filename = f'empresa_{empresa_id}_logo.{ext}'

    upload_dir = _directorio_logos()
    _eliminar_logo_anterior(empresa_id, upload_dir)

    filepath = os.path.join(upload_dir, filename)
    archivo.save(filepath)

    # Validar que el archivo sea una imagen real y redimensionar
    from PIL import Image

    try:
        with Image.open(filepath) as img:
            img.verify()
    except Exception:
        os.remove(filepath)
        raise ValueError('El archivo no es una imagen válida.')

    with Image.open(filepath) as img:
        if img.width > MAX_LOGO_WIDTH:
            ratio = MAX_LOGO_WIDTH / img.width
            nuevo_alto = int(img.height * ratio)
            img = img.resize((MAX_LOGO_WIDTH, nuevo_alto), Image.LANCZOS)
            img.save(filepath)

    return filename


@bp.route('/', methods=['GET', 'POST'])
@login_required
@empresa_aprobada_required
def index():
    """Configuración general del sistema (solo administradores)."""
    if not current_user.es_administrador:
        return redirect(url_for('configuracion.categorias'))
    form = ConfiguracionForm()

    if request.method == 'GET':
        # Cargar valores actuales (Configuracion.get ya filtra por empresa)
        form.nombre_negocio.data = Configuracion.get('nombre_negocio', default='Ferretería')
        form.direccion.data = Configuracion.get('direccion', default='')
        form.telefono.data = Configuracion.get('telefono', default='')
        form.cuit.data = Configuracion.get('cuit', default='')
        form.precios_con_iva.data = Configuracion.get('precios_con_iva', default=False)
        form.mensaje_cumpleanos.data = Configuracion.get(
            'mensaje_cumpleanos',
            default=(
                '¡Feliz cumpleaños {cliente}! Te saluda {negocio}.' ' ¡Que tengas un gran día!'
            ),
        )

    if request.method == 'POST' and not form.validate():
        flash('Por favor corregí los errores del formulario.', 'danger')

    if form.validate_on_submit():
        # Procesar upload de logo si se envió un archivo
        logo_archivo = request.files.get('logo')
        if logo_archivo and logo_archivo.filename:
            try:
                filename = _guardar_logo(logo_archivo, current_user.empresa_id)
                if filename:
                    Configuracion.set('logo_filename', filename, 'string')
                    flash('Logo actualizado correctamente.', 'success')
            except ValueError as e:
                flash(str(e), 'danger')
                return redirect(url_for('configuracion.index'))

        Configuracion.set('nombre_negocio', form.nombre_negocio.data, 'string')
        Configuracion.set('direccion', form.direccion.data, 'string')
        Configuracion.set('telefono', form.telefono.data, 'string')
        Configuracion.set('cuit', form.cuit.data, 'string')
        Configuracion.set('precios_con_iva', form.precios_con_iva.data, 'boolean')
        Configuracion.set('mensaje_cumpleanos', form.mensaje_cumpleanos.data, 'string')

        flash('Configuración guardada correctamente.', 'success')
        return redirect(url_for('configuracion.index'))

    logo_actual = Configuracion.get('logo_filename', default='')
    # Verificar que el archivo exista en disco
    if logo_actual:
        logo_path = os.path.join(current_app.root_path, 'static', 'uploads', 'logos', logo_actual)
        if not os.path.exists(logo_path):
            logo_actual = ''

    return render_template('configuracion/general.html', form=form, logo_actual=logo_actual)


@bp.route('/logo/eliminar', methods=['POST'])
@login_required
@empresa_aprobada_required
@admin_required
def eliminar_logo():
    """Elimina el logo de la empresa."""
    logo_filename = Configuracion.get('logo_filename', default='')
    if logo_filename:
        upload_dir = _directorio_logos()
        filepath = os.path.join(upload_dir, logo_filename)
        if os.path.exists(filepath):
            os.remove(filepath)

        # Eliminar la configuracion
        config = Configuracion.query.filter_by(
            clave='logo_filename',
            empresa_id=current_user.empresa_id,
        ).first()
        if config:
            db.session.delete(config)
            db.session.commit()

        flash('Logo eliminado correctamente.', 'success')
    else:
        flash('No hay logo para eliminar.', 'info')

    return redirect(url_for('configuracion.index'))


@bp.route('/logo/preview-pdf')
@login_required
@empresa_aprobada_required
@admin_required
def preview_logo_pdf():
    """Genera un PDF de ejemplo con el header para previsualizar el logo."""
    from weasyprint import HTML

    from ..services.pdf_utils import obtener_config_negocio

    config_negocio = obtener_config_negocio()

    html_string = render_template(
        'configuracion/preview_logo_pdf.html',
        config_negocio=config_negocio,
    )

    pdf = HTML(string=html_string).write_pdf()

    from flask import Response

    return Response(
        pdf,
        mimetype='application/pdf',
        headers={'Content-Disposition': 'inline; filename=preview_logo.pdf'},
    )


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
@empresa_aprobada_required
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
@empresa_aprobada_required
@admin_required
def editar_usuario(id):
    """Editar usuario."""
    usuario = Usuario.query.filter_by(id=id, empresa_id=current_user.empresa_id).first_or_404()
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
@empresa_aprobada_required
@admin_required
def toggle_usuario(id):
    """Activar/desactivar usuario."""
    usuario = Usuario.query.filter_by(id=id, empresa_id=current_user.empresa_id).first_or_404()

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
@empresa_aprobada_required
def categorias():
    """Gestión de categorías."""
    form = CategoriaForm()

    if form.validate_on_submit():
        padre_id = form.padre_id.data or None

        # Verificar nombre único por nivel dentro de la empresa
        existente = (
            Categoria.query_empresa()
            .filter_by(
                nombre=form.nombre.data,
                padre_id=padre_id,
            )
            .first()
        )
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
        Categoria.query_empresa().filter_by(padre_id=None).order_by(Categoria.nombre).all()
    )

    return render_template(
        'configuracion/categorias.html', form=form, categorias_padre=categorias_padre
    )


@bp.route('/categorias/<int:id>/editar', methods=['POST'])
@login_required
@empresa_aprobada_required
def editar_categoria(id):
    """Editar categoría (HTMX)."""
    categoria = Categoria.get_o_404(id)

    nombre = request.form.get('nombre')
    descripcion = request.form.get('descripcion')

    if nombre:
        # Verificar nombre único por nivel dentro de la empresa
        existente = (
            Categoria.query_empresa()
            .filter(
                Categoria.nombre == nombre,
                Categoria.padre_id == categoria.padre_id,
                Categoria.id != id,
            )
            .first()
        )
        if existente:
            flash('Ya existe una categoría con ese nombre en ese nivel.', 'danger')
        else:
            categoria.nombre = nombre
            categoria.descripcion = descripcion
            db.session.commit()
            flash(f'Categoría "{categoria.nombre}" actualizada.', 'success')

    return redirect(url_for('configuracion.categorias'))


@bp.route('/categorias/<int:id>/toggle', methods=['POST'])
@login_required
@empresa_aprobada_required
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


@bp.route('/categorias/<int:id>/eliminar', methods=['POST'])
@login_required
@empresa_aprobada_required
def eliminar_categoria(id):
    """Eliminar categoría (solo si no tiene productos asociados)."""
    categoria = Categoria.get_o_404(id)

    if not categoria.puede_eliminarse:
        flash(
            'No se puede eliminar la categoría porque tiene productos asociados.',
            'danger',
        )
        return redirect(url_for('configuracion.categorias'))

    nombre = categoria.nombre
    db.session.delete(categoria)
    db.session.commit()
    flash(f'Categoría "{nombre}" eliminada.', 'success')
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
