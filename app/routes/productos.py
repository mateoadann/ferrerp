"""Rutas de productos."""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Producto, Categoria
from ..forms.producto_forms import ProductoForm, CategoriaForm
from ..utils.helpers import paginar_query, es_peticion_htmx

bp = Blueprint('productos', __name__, url_prefix='/productos')


@bp.route('/')
@login_required
def index():
    """Listado de productos."""
    page = request.args.get('page', 1, type=int)
    busqueda = request.args.get('q', '')
    categoria_id = request.args.get('categoria', 0, type=int)
    solo_activos = request.args.get('activos', '1') == '1'
    solo_bajo_stock = request.args.get('bajo_stock', '0') == '1'

    # Construir query
    query = Producto.query

    # Filtros
    if busqueda:
        query = query.filter(
            db.or_(
                Producto.codigo.ilike(f'%{busqueda}%'),
                Producto.nombre.ilike(f'%{busqueda}%'),
                Producto.codigo_barras.ilike(f'%{busqueda}%')
            )
        )

    if categoria_id:
        query = query.filter(Producto.categoria_id == categoria_id)

    if solo_activos:
        query = query.filter(Producto.activo == True)

    if solo_bajo_stock:
        query = query.filter(Producto.stock_actual < Producto.stock_minimo)

    # Ordenar y paginar
    query = query.order_by(Producto.nombre)
    productos = paginar_query(query, page)

    # Categorías para el filtro
    categorias = Categoria.query.filter_by(activa=True).order_by(Categoria.nombre).all()

    # Si es petición HTMX, devolver solo la tabla
    if es_peticion_htmx():
        return render_template(
            'productos/_tabla.html',
            productos=productos,
            busqueda=busqueda
        )

    return render_template(
        'productos/index.html',
        productos=productos,
        categorias=categorias,
        busqueda=busqueda,
        categoria_id=categoria_id,
        solo_activos=solo_activos,
        solo_bajo_stock=solo_bajo_stock
    )


@bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo():
    """Crear nuevo producto."""
    form = ProductoForm()

    if form.validate_on_submit():
        # Verificar código único
        existente = Producto.query.filter_by(codigo=form.codigo.data).first()
        if existente:
            flash('Ya existe un producto con ese código.', 'danger')
            return render_template('productos/form.html', form=form, titulo='Nuevo Producto')

        producto = Producto(
            codigo=form.codigo.data,
            codigo_barras=form.codigo_barras.data or None,
            nombre=form.nombre.data,
            descripcion=form.descripcion.data,
            categoria_id=form.categoria_id.data if form.categoria_id.data else None,
            unidad_medida=form.unidad_medida.data,
            precio_costo=form.precio_costo.data,
            precio_venta=form.precio_venta.data,
            stock_actual=form.stock_actual.data or 0,
            stock_minimo=form.stock_minimo.data or 0,
            proveedor_id=form.proveedor_id.data if form.proveedor_id.data else None,
            ubicacion=form.ubicacion.data,
            activo=form.activo.data
        )

        db.session.add(producto)
        db.session.commit()

        flash(f'Producto "{producto.nombre}" creado correctamente.', 'success')
        return redirect(url_for('productos.index'))

    return render_template('productos/form.html', form=form, titulo='Nuevo Producto')


@bp.route('/<int:id>')
@login_required
def detalle(id):
    """Ver detalle de producto."""
    producto = Producto.query.get_or_404(id)
    return render_template('productos/detalle.html', producto=producto)


@bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    """Editar producto."""
    producto = Producto.query.get_or_404(id)
    form = ProductoForm(obj=producto)

    if form.validate_on_submit():
        # Verificar código único (excluyendo el actual)
        existente = Producto.query.filter(
            Producto.codigo == form.codigo.data,
            Producto.id != id
        ).first()
        if existente:
            flash('Ya existe otro producto con ese código.', 'danger')
            return render_template(
                'productos/form.html',
                form=form,
                titulo='Editar Producto',
                producto=producto
            )

        producto.codigo = form.codigo.data
        producto.codigo_barras = form.codigo_barras.data or None
        producto.nombre = form.nombre.data
        producto.descripcion = form.descripcion.data
        producto.categoria_id = form.categoria_id.data if form.categoria_id.data else None
        producto.unidad_medida = form.unidad_medida.data
        producto.precio_costo = form.precio_costo.data
        producto.precio_venta = form.precio_venta.data
        producto.stock_minimo = form.stock_minimo.data or 0
        producto.proveedor_id = form.proveedor_id.data if form.proveedor_id.data else None
        producto.ubicacion = form.ubicacion.data
        producto.activo = form.activo.data

        db.session.commit()

        flash(f'Producto "{producto.nombre}" actualizado correctamente.', 'success')
        return redirect(url_for('productos.index'))

    return render_template(
        'productos/form.html',
        form=form,
        titulo='Editar Producto',
        producto=producto
    )


@bp.route('/<int:id>/toggle-activo', methods=['POST'])
@login_required
def toggle_activo(id):
    """Activar/desactivar producto."""
    producto = Producto.query.get_or_404(id)
    producto.activo = not producto.activo
    db.session.commit()

    estado = 'activado' if producto.activo else 'desactivado'
    flash(f'Producto "{producto.nombre}" {estado}.', 'success')

    if es_peticion_htmx():
        return '', 204

    return redirect(url_for('productos.index'))


@bp.route('/buscar')
@login_required
def buscar():
    """Búsqueda de productos para autocompletado (HTMX/AJAX)."""
    q = request.args.get('q', '')
    limit = request.args.get('limit', 10, type=int)

    if len(q) < 2:
        return jsonify([])

    productos = Producto.query.filter(
        Producto.activo == True,
        db.or_(
            Producto.codigo.ilike(f'%{q}%'),
            Producto.nombre.ilike(f'%{q}%'),
            Producto.codigo_barras.ilike(f'%{q}%')
        )
    ).limit(limit).all()

    return jsonify([p.to_dict() for p in productos])


@bp.route('/tabla')
@login_required
def tabla():
    """Partial de tabla de productos (HTMX)."""
    page = request.args.get('page', 1, type=int)
    busqueda = request.args.get('q', '')

    query = Producto.query

    if busqueda:
        query = query.filter(
            db.or_(
                Producto.codigo.ilike(f'%{busqueda}%'),
                Producto.nombre.ilike(f'%{busqueda}%')
            )
        )

    query = query.filter(Producto.activo == True).order_by(Producto.nombre)
    productos = paginar_query(query, page)

    return render_template('productos/_tabla.html', productos=productos, busqueda=busqueda)
