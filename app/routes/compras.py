"""Rutas de compras (órdenes de compra)."""

from datetime import datetime
from decimal import Decimal
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

from ..extensions import db
from ..models import OrdenCompra, OrdenCompraDetalle, Producto, Proveedor, MovimientoStock
from ..utils.helpers import paginar_query, generar_numero_orden_compra, es_peticion_htmx

bp = Blueprint('compras', __name__, url_prefix='/compras')


@bp.route('/')
@login_required
def index():
    """Listado de órdenes de compra."""
    page = request.args.get('page', 1, type=int)
    estado = request.args.get('estado', '')
    proveedor_id = request.args.get('proveedor', 0, type=int)

    query = OrdenCompra.query

    if estado:
        query = query.filter(OrdenCompra.estado == estado)

    if proveedor_id:
        query = query.filter(OrdenCompra.proveedor_id == proveedor_id)

    query = query.order_by(OrdenCompra.fecha.desc())
    ordenes = paginar_query(query, page)

    proveedores = Proveedor.query.filter_by(activo=True).order_by(Proveedor.nombre).all()

    return render_template(
        'compras/index.html',
        ordenes=ordenes,
        proveedores=proveedores,
        estado_filtro=estado,
        proveedor_id=proveedor_id
    )


@bp.route('/nueva', methods=['GET', 'POST'])
@login_required
def nueva():
    """Crear nueva orden de compra."""
    if request.method == 'POST':
        proveedor_id = request.form.get('proveedor_id', type=int)
        notas = request.form.get('notas', '')

        if not proveedor_id:
            flash('Selecciona un proveedor.', 'danger')
            return redirect(url_for('compras.nueva'))

        # Obtener items del formulario
        productos_ids = request.form.getlist('producto_id[]')
        cantidades = request.form.getlist('cantidad[]')
        precios = request.form.getlist('precio[]')

        if not productos_ids or not any(productos_ids):
            flash('Agrega al menos un producto a la orden.', 'danger')
            return redirect(url_for('compras.nueva'))

        # Crear orden
        orden = OrdenCompra(
            numero=generar_numero_orden_compra(),
            fecha=datetime.utcnow(),
            proveedor_id=proveedor_id,
            usuario_id=current_user.id,
            estado='pendiente',
            notas=notas
        )
        db.session.add(orden)
        db.session.flush()

        # Agregar detalles
        total = Decimal('0')
        for i, prod_id in enumerate(productos_ids):
            if not prod_id:
                continue

            cantidad = Decimal(cantidades[i]) if cantidades[i] else Decimal('0')
            precio = Decimal(precios[i]) if precios[i] else Decimal('0')

            if cantidad <= 0:
                continue

            subtotal = cantidad * precio
            total += subtotal

            detalle = OrdenCompraDetalle(
                orden_compra_id=orden.id,
                producto_id=int(prod_id),
                cantidad_pedida=cantidad,
                precio_unitario=precio,
                subtotal=subtotal
            )
            db.session.add(detalle)

        orden.total = total
        db.session.commit()

        flash(f'Orden de compra #{orden.numero} creada correctamente.', 'success')
        return redirect(url_for('compras.detalle', id=orden.id))

    # GET - Mostrar formulario
    proveedores = Proveedor.query.filter_by(activo=True).order_by(Proveedor.nombre).all()
    productos = Producto.query.filter_by(activo=True).order_by(Producto.nombre).all()

    return render_template(
        'compras/orden_form.html',
        proveedores=proveedores,
        productos=productos
    )


@bp.route('/<int:id>')
@login_required
def detalle(id):
    """Ver detalle de orden de compra."""
    orden = OrdenCompra.query.get_or_404(id)
    return render_template('compras/orden_detalle.html', orden=orden)


@bp.route('/<int:id>/recibir', methods=['GET', 'POST'])
@login_required
def recibir(id):
    """Recibir mercadería de una orden."""
    orden = OrdenCompra.query.get_or_404(id)

    if not orden.puede_recibir:
        flash('Esta orden no puede recibir más mercadería.', 'warning')
        return redirect(url_for('compras.detalle', id=id))

    if request.method == 'POST':
        actualizar_precios = request.form.get('actualizar_precios') == '1'

        # Procesar cantidades recibidas
        for detalle in orden.detalles:
            cantidad_recibida = request.form.get(f'cantidad_{detalle.id}', type=float)

            if cantidad_recibida and cantidad_recibida > 0:
                cantidad_decimal = Decimal(str(cantidad_recibida))

                # Actualizar cantidad recibida
                detalle.cantidad_recibida = (detalle.cantidad_recibida or 0) + cantidad_decimal

                # Actualizar stock del producto
                producto = detalle.producto
                stock_anterior, stock_posterior = producto.actualizar_stock(cantidad_decimal, 'compra')

                # Registrar movimiento de stock
                movimiento = MovimientoStock(
                    producto_id=producto.id,
                    tipo='compra',
                    cantidad=cantidad_decimal,
                    stock_anterior=stock_anterior,
                    stock_posterior=stock_posterior,
                    referencia_tipo='orden_compra',
                    referencia_id=orden.id,
                    motivo=f'Recepción de orden #{orden.numero}',
                    usuario_id=current_user.id
                )
                db.session.add(movimiento)

                # Opcionalmente actualizar precio de costo
                if actualizar_precios:
                    producto.precio_costo = detalle.precio_unitario

        # Actualizar estado de la orden
        orden.actualizar_estado()
        db.session.commit()

        flash('Recepción de mercadería registrada correctamente.', 'success')
        return redirect(url_for('compras.detalle', id=id))

    return render_template('compras/recepcion.html', orden=orden)


@bp.route('/<int:id>/cancelar', methods=['POST'])
@login_required
def cancelar(id):
    """Cancelar orden de compra."""
    orden = OrdenCompra.query.get_or_404(id)

    if not orden.puede_cancelar:
        flash('Esta orden no puede ser cancelada.', 'warning')
        return redirect(url_for('compras.detalle', id=id))

    orden.estado = 'cancelada'
    db.session.commit()

    flash(f'Orden #{orden.numero} cancelada.', 'success')
    return redirect(url_for('compras.index'))


@bp.route('/sugerencia')
@login_required
def sugerencia():
    """Sugerencia de compra basada en stock mínimo."""
    # Productos bajo stock mínimo
    productos_bajo_stock = Producto.query.filter(
        Producto.activo == True,
        Producto.stock_actual < Producto.stock_minimo,
        Producto.proveedor_id.isnot(None)
    ).order_by(Producto.proveedor_id, Producto.nombre).all()

    # Agrupar por proveedor
    sugerencias = {}
    for producto in productos_bajo_stock:
        if producto.proveedor_id not in sugerencias:
            sugerencias[producto.proveedor_id] = {
                'proveedor': producto.proveedor,
                'productos': []
            }
        sugerencias[producto.proveedor_id]['productos'].append({
            'producto': producto,
            'cantidad_sugerida': producto.stock_minimo - producto.stock_actual
        })

    return render_template('compras/sugerencia.html', sugerencias=sugerencias)


@bp.route('/sugerencia/generar-orden', methods=['POST'])
@login_required
def generar_orden_sugerencia():
    """Generar orden desde sugerencia."""
    proveedor_id = request.form.get('proveedor_id', type=int)
    productos_ids = request.form.getlist('producto_id[]')
    cantidades = request.form.getlist('cantidad[]')

    if not proveedor_id or not productos_ids:
        flash('Datos incompletos.', 'danger')
        return redirect(url_for('compras.sugerencia'))

    # Crear orden
    orden = OrdenCompra(
        numero=generar_numero_orden_compra(),
        fecha=datetime.utcnow(),
        proveedor_id=proveedor_id,
        usuario_id=current_user.id,
        estado='pendiente',
        notas='Generada desde sugerencia de compra'
    )
    db.session.add(orden)
    db.session.flush()

    total = Decimal('0')
    items_agregados = 0
    for i, prod_id in enumerate(productos_ids):
        if not prod_id:
            continue

        producto = Producto.query.get(int(prod_id))
        if not producto:
            continue

        cantidad = Decimal(cantidades[i]) if i < len(cantidades) and cantidades[i] else Decimal('0')
        if cantidad <= 0:
            continue

        subtotal = cantidad * producto.precio_costo

        detalle = OrdenCompraDetalle(
            orden_compra_id=orden.id,
            producto_id=producto.id,
            cantidad_pedida=cantidad,
            precio_unitario=producto.precio_costo,
            subtotal=subtotal
        )
        db.session.add(detalle)
        total += subtotal
        items_agregados += 1

    if items_agregados == 0:
        db.session.rollback()
        flash('No se seleccionó ningún producto válido.', 'danger')
        return redirect(url_for('compras.sugerencia'))

    orden.total = total
    db.session.commit()

    flash(f'Orden #{orden.numero} creada desde sugerencia con {items_agregados} producto(s).', 'success')
    return redirect(url_for('compras.detalle', id=orden.id))
