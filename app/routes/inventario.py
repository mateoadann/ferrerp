"""Rutas de inventario."""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from decimal import Decimal

from ..extensions import db
from ..models import Producto, MovimientoStock
from ..forms.producto_forms import AjusteStockForm
from ..utils.helpers import paginar_query, es_peticion_htmx

bp = Blueprint('inventario', __name__, url_prefix='/inventario')


@bp.route('/')
@login_required
def index():
    """Vista principal de inventario."""
    page = request.args.get('page', 1, type=int)
    busqueda = request.args.get('q', '')
    solo_bajo_minimo = request.args.get('bajo_minimo', '0') == '1'

    query = Producto.query.filter(Producto.activo == True)

    if busqueda:
        query = query.filter(
            db.or_(
                Producto.codigo.ilike(f'%{busqueda}%'),
                Producto.nombre.ilike(f'%{busqueda}%')
            )
        )

    if solo_bajo_minimo:
        query = query.filter(Producto.stock_actual < Producto.stock_minimo)

    query = query.order_by(Producto.nombre)
    productos = paginar_query(query, page)

    # Estadísticas
    total_productos = Producto.query.filter_by(activo=True).count()
    productos_bajo_minimo = Producto.query.filter(
        Producto.activo == True,
        Producto.stock_actual < Producto.stock_minimo
    ).count()

    if es_peticion_htmx():
        return render_template(
            'inventario/_tabla_stock.html',
            productos=productos,
            busqueda=busqueda
        )

    return render_template(
        'inventario/index.html',
        productos=productos,
        busqueda=busqueda,
        solo_bajo_minimo=solo_bajo_minimo,
        total_productos=total_productos,
        productos_bajo_minimo=productos_bajo_minimo
    )


@bp.route('/bajo-minimo')
@login_required
def bajo_minimo():
    """Productos con stock bajo el mínimo."""
    page = request.args.get('page', 1, type=int)

    productos = Producto.query.filter(
        Producto.activo == True,
        Producto.stock_actual < Producto.stock_minimo
    ).order_by(Producto.stock_actual).paginate(page=page, per_page=20)

    return render_template(
        'inventario/bajo_minimo.html',
        productos=productos
    )


@bp.route('/ajuste', methods=['GET', 'POST'])
@login_required
def ajuste():
    """Formulario de ajuste de stock."""
    form = AjusteStockForm()

    # Pre-seleccionar producto si viene en la URL
    producto_id = request.args.get('producto_id', type=int)
    if producto_id and request.method == 'GET':
        form.producto_id.data = producto_id

    if form.validate_on_submit():
        if not form.producto_id.data:
            flash('Selecciona un producto.', 'danger')
            return render_template('inventario/ajuste.html', form=form)

        producto = Producto.query.get_or_404(form.producto_id.data)

        tipo = form.tipo_ajuste.data
        cantidad = Decimal(str(form.cantidad.data))

        # Calcular nueva cantidad
        if tipo == 'ajuste_negativo':
            cantidad = -cantidad

            # Verificar que no quede stock negativo
            if producto.stock_actual + cantidad < 0:
                flash('No se puede reducir más stock del disponible.', 'danger')
                return render_template('inventario/ajuste.html', form=form)

        # Realizar ajuste
        stock_anterior, stock_posterior = producto.actualizar_stock(cantidad, tipo)

        # Registrar movimiento
        movimiento = MovimientoStock(
            producto_id=producto.id,
            tipo=tipo,
            cantidad=cantidad,
            stock_anterior=stock_anterior,
            stock_posterior=stock_posterior,
            referencia_tipo='ajuste',
            motivo=form.motivo.data,
            usuario_id=current_user.id
        )

        db.session.add(movimiento)
        db.session.commit()

        flash(
            f'Ajuste realizado. Stock de "{producto.nombre}": {stock_anterior} → {stock_posterior}',
            'success'
        )
        return redirect(url_for('inventario.index'))

    return render_template('inventario/ajuste.html', form=form)


@bp.route('/movimientos')
@login_required
def movimientos():
    """Historial de movimientos de stock."""
    page = request.args.get('page', 1, type=int)
    producto_id = request.args.get('producto_id', type=int)
    tipo = request.args.get('tipo', '')

    query = MovimientoStock.query

    if producto_id:
        query = query.filter(MovimientoStock.producto_id == producto_id)

    if tipo:
        query = query.filter(MovimientoStock.tipo == tipo)

    query = query.order_by(MovimientoStock.created_at.desc())
    movimientos = paginar_query(query, page)

    # Obtener producto si se filtró
    producto = None
    if producto_id:
        producto = Producto.query.get(producto_id)

    return render_template(
        'inventario/movimientos.html',
        movimientos=movimientos,
        producto=producto,
        tipo_filtro=tipo
    )


@bp.route('/movimientos/<int:producto_id>')
@login_required
def movimientos_producto(producto_id):
    """Movimientos de un producto específico."""
    producto = Producto.query.get_or_404(producto_id)
    page = request.args.get('page', 1, type=int)

    movimientos = MovimientoStock.query.filter_by(
        producto_id=producto_id
    ).order_by(
        MovimientoStock.created_at.desc()
    ).paginate(page=page, per_page=20)

    return render_template(
        'inventario/movimientos.html',
        movimientos=movimientos,
        producto=producto
    )
