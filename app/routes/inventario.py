"""Rutas de inventario."""

import json
from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms.producto_forms import AjusteStockForm
from ..models import MovimientoStock, Producto
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
    """Formulario de ajuste de stock (individual o masivo)."""
    form = AjusteStockForm()

    # Pre-seleccionar producto si viene en la URL
    producto_id = request.args.get('producto_id', type=int)
    if producto_id and request.method == 'GET':
        form.producto_id.data = producto_id

    if form.validate_on_submit():
        # Determinar IDs de productos: masivo (producto_ids) o individual (producto_id)
        producto_ids_json = request.form.get('producto_ids', '')
        producto_ids = []

        if producto_ids_json:
            try:
                producto_ids = json.loads(producto_ids_json)
                if not isinstance(producto_ids, list):
                    producto_ids = []
            except (json.JSONDecodeError, TypeError):
                producto_ids = []

        # Fallback a producto_id individual (compatibilidad)
        if not producto_ids and form.producto_id.data:
            producto_ids = [form.producto_id.data]

        if not producto_ids:
            flash('Seleccioná al menos un producto.', 'danger')
            return render_template('inventario/ajuste.html', form=form)

        tipo = form.tipo_ajuste.data
        cantidad_base = Decimal(str(form.cantidad.data))
        errores = []
        ajustados = 0

        for pid in producto_ids:
            producto = Producto.query_empresa().filter_by(id=pid, activo=True).first()
            if not producto:
                errores.append(f'Producto ID {pid} no encontrado')
                continue

            cantidad = cantidad_base if tipo == 'ajuste_positivo' else -cantidad_base

            # Verificar que no quede stock negativo
            if tipo == 'ajuste_negativo' and producto.stock_actual + cantidad < 0:
                errores.append(
                    f'"{producto.nombre}": stock insuficiente ' f'(actual: {producto.stock_actual})'
                )
                continue

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
            ajustados += 1

        if errores:
            for error in errores:
                flash(error, 'danger')

        if ajustados > 0:
            db.session.commit()
            if ajustados == 1 and len(producto_ids) == 1:
                # Mensaje detallado para ajuste individual
                producto = Producto.query.get(producto_ids[0])

                def _fmt(valor):
                    if producto.unidad_medida in ('unidad', 'par'):
                        return str(int(valor))
                    return f'{float(valor):.2f}'

                ultimo_mov = (
                    MovimientoStock.query.filter_by(producto_id=producto.id)
                    .order_by(MovimientoStock.created_at.desc())
                    .first()
                )
                flash(
                    f'Ajuste realizado. Stock de "{producto.nombre}": '
                    f'{_fmt(ultimo_mov.stock_anterior)} → {_fmt(ultimo_mov.stock_posterior)}',
                    'success',
                )
            else:
                flash(f'Ajuste de stock aplicado a {ajustados} productos.', 'success')
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
