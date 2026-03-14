"""Rutas de inventario."""

from decimal import Decimal

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms.producto_forms import AjusteStockForm
from ..models import MovimientoStock, Producto, ProductoTiendaNube
from ..tasks.tiendanube_tasks import encolar_sync_stock
from ..utils.decorators import empresa_aprobada_required
from ..utils.helpers import es_peticion_htmx, paginar_query

bp = Blueprint('inventario', __name__, url_prefix='/inventario')


@bp.route('/')
@login_required
def index():
    """Vista principal de inventario."""
    page = request.args.get('page', 1, type=int)
    busqueda = request.args.get('q', '')
    solo_bajo_minimo = request.args.get('bajo_minimo', '0') == '1'

    query = Producto.query_empresa().filter(Producto.activo.is_(True))

    if busqueda:
        query = query.filter(
            db.or_(Producto.codigo.ilike(f'%{busqueda}%'), Producto.nombre.ilike(f'%{busqueda}%'))
        )

    if solo_bajo_minimo:
        query = query.filter(Producto.stock_actual < Producto.stock_minimo)

    query = query.order_by(Producto.nombre)
    productos = paginar_query(query, page)

    # Estadísticas
    total_productos = Producto.query_empresa().filter_by(activo=True).count()
    productos_bajo_minimo = (
        Producto.query_empresa()
        .filter(Producto.activo.is_(True), Producto.stock_actual < Producto.stock_minimo)
        .count()
    )

    if es_peticion_htmx():
        return render_template(
            'inventario/_tabla_stock.html', productos=productos, busqueda=busqueda
        )

    return render_template(
        'inventario/index.html',
        productos=productos,
        busqueda=busqueda,
        solo_bajo_minimo=solo_bajo_minimo,
        total_productos=total_productos,
        productos_bajo_minimo=productos_bajo_minimo,
    )


@bp.route('/bajo-minimo')
@login_required
def bajo_minimo():
    """Productos con stock bajo el mínimo."""
    page = request.args.get('page', 1, type=int)

    productos = (
        Producto.query_empresa()
        .filter(Producto.activo.is_(True), Producto.stock_actual < Producto.stock_minimo)
        .order_by(Producto.stock_actual)
        .paginate(page=page, per_page=20)
    )

    return render_template('inventario/bajo_minimo.html', productos=productos)


@bp.route('/ajuste', methods=['GET', 'POST'])
@login_required
@empresa_aprobada_required
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

        producto = Producto.get_o_404(form.producto_id.data)

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
            usuario_id=current_user.id,
            empresa_id=current_user.empresa_id,
        )

        db.session.add(movimiento)
        db.session.commit()

        # Sincronizar stock con Tienda Nube si está vinculado
        try:
            mapeo = ProductoTiendaNube.query.filter_by(
                producto_id=producto.id,
                empresa_id=current_user.empresa_id,
                activo=True,
            ).first()
            if mapeo:
                encolar_sync_stock(producto.id, current_user.empresa_id)
        except Exception as e:
            current_app.logger.error(f'Error al encolar sync TN (ajuste stock): {e}')

        def _fmt(valor):
            if producto.unidad_medida in ('unidad', 'par'):
                return str(int(valor))
            return f'{float(valor):.2f}'

        flash(
            f'Ajuste realizado. Stock de "{producto.nombre}": '
            f'{_fmt(stock_anterior)} → {_fmt(stock_posterior)}',
            'success',
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

    query = MovimientoStock.query_empresa()

    if producto_id:
        query = query.filter(MovimientoStock.producto_id == producto_id)

    if tipo:
        query = query.filter(MovimientoStock.tipo == tipo)

    query = query.order_by(MovimientoStock.created_at.desc())
    movimientos = paginar_query(query, page)

    # Obtener producto si se filtró
    producto = None
    if producto_id:
        producto = Producto.get_o_404(producto_id)

    return render_template(
        'inventario/movimientos.html', movimientos=movimientos, producto=producto, tipo_filtro=tipo
    )


@bp.route('/movimientos/<int:producto_id>')
@login_required
def movimientos_producto(producto_id):
    """Movimientos de un producto específico."""
    producto = Producto.get_o_404(producto_id)
    page = request.args.get('page', 1, type=int)

    movimientos = (
        MovimientoStock.query_empresa()
        .filter_by(producto_id=producto_id)
        .order_by(MovimientoStock.created_at.desc())
        .paginate(page=page, per_page=20)
    )

    return render_template(
        'inventario/movimientos.html', movimientos=movimientos, producto=producto
    )
