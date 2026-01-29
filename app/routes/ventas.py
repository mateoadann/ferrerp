"""Rutas de ventas y punto de venta."""

import json
from datetime import datetime
from decimal import Decimal
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

from ..extensions import db
from ..models import (
    Venta, VentaDetalle, Producto, Cliente, Caja, MovimientoCaja,
    MovimientoStock, MovimientoCuentaCorriente
)
from ..forms.venta_forms import VentaForm, AnulacionVentaForm
from ..utils.helpers import paginar_query, generar_numero_venta, es_peticion_htmx
from ..utils.decorators import admin_required, caja_abierta_required

bp = Blueprint('ventas', __name__, url_prefix='/ventas')


@bp.route('/punto-de-venta', methods=['GET', 'POST'])
@login_required
@caja_abierta_required
def punto_de_venta():
    """Pantalla principal de punto de venta."""
    form = VentaForm()

    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            cliente_id = request.form.get('cliente_id', type=int)
            forma_pago = request.form.get('forma_pago', 'efectivo')
            descuento_porcentaje = Decimal(request.form.get('descuento_porcentaje', '0'))
            items_json = request.form.get('items_json', '[]')

            items = json.loads(items_json)

            if not items:
                flash('Agrega al menos un producto a la venta.', 'danger')
                return redirect(url_for('ventas.punto_de_venta'))

            # Validaciones de cuenta corriente
            if forma_pago == 'cuenta_corriente':
                if not cliente_id:
                    flash('Debes seleccionar un cliente para pagar a cuenta corriente.', 'danger')
                    return redirect(url_for('ventas.punto_de_venta'))

                cliente = Cliente.query.get(cliente_id)
                if not cliente:
                    flash('Cliente no encontrado.', 'danger')
                    return redirect(url_for('ventas.punto_de_venta'))

            # Obtener caja abierta
            caja = Caja.query.filter_by(estado='abierta').first()

            # Crear venta
            venta = Venta(
                numero=generar_numero_venta(),
                fecha=datetime.utcnow(),
                cliente_id=cliente_id if cliente_id else None,
                usuario_id=current_user.id,
                descuento_porcentaje=descuento_porcentaje,
                forma_pago=forma_pago,
                estado='completada',
                caja_id=caja.id
            )

            subtotal = Decimal('0')

            # Procesar items
            for item in items:
                producto = Producto.query.get(item['producto_id'])
                if not producto:
                    flash(f'Producto no encontrado: {item["producto_id"]}', 'danger')
                    return redirect(url_for('ventas.punto_de_venta'))

                cantidad = Decimal(str(item['cantidad']))
                precio = Decimal(str(item['precio_unitario']))

                # Verificar stock
                if producto.stock_actual < cantidad:
                    flash(
                        f'Stock insuficiente para "{producto.nombre}". '
                        f'Disponible: {producto.stock_actual}',
                        'danger'
                    )
                    return redirect(url_for('ventas.punto_de_venta'))

                item_subtotal = cantidad * precio
                subtotal += item_subtotal

                # Crear detalle de venta
                detalle = VentaDetalle(
                    producto_id=producto.id,
                    cantidad=cantidad,
                    precio_unitario=precio,
                    subtotal=item_subtotal
                )
                venta.detalles.append(detalle)

                # Descontar stock
                stock_anterior, stock_posterior = producto.actualizar_stock(-cantidad, 'venta')

                # Registrar movimiento de stock
                movimiento_stock = MovimientoStock(
                    producto_id=producto.id,
                    tipo='venta',
                    cantidad=-cantidad,
                    stock_anterior=stock_anterior,
                    stock_posterior=stock_posterior,
                    referencia_tipo='venta',
                    usuario_id=current_user.id
                )
                db.session.add(movimiento_stock)

            # Calcular totales
            venta.subtotal = subtotal
            if descuento_porcentaje > 0:
                venta.descuento_monto = subtotal * (descuento_porcentaje / 100)
            else:
                venta.descuento_monto = Decimal('0')
            venta.total = subtotal - venta.descuento_monto

            db.session.add(venta)
            db.session.flush()

            # Actualizar referencia en movimientos de stock
            for detalle in venta.detalles:
                mov = MovimientoStock.query.filter_by(
                    producto_id=detalle.producto_id,
                    referencia_tipo='venta',
                    referencia_id=None
                ).order_by(MovimientoStock.id.desc()).first()
                if mov:
                    mov.referencia_id = venta.id

            # Verificar límite de crédito para cuenta corriente
            if forma_pago == 'cuenta_corriente':
                if not cliente.puede_comprar_a_credito(venta.total):
                    db.session.rollback()
                    flash(
                        f'El cliente excedería su límite de crédito. '
                        f'Disponible: ${cliente.credito_disponible:.2f}',
                        'danger'
                    )
                    return redirect(url_for('ventas.punto_de_venta'))

                # Cargar a cuenta corriente
                saldo_anterior, saldo_posterior = cliente.actualizar_saldo(venta.total, 'cargo')

                movimiento_cc = MovimientoCuentaCorriente(
                    cliente_id=cliente.id,
                    tipo='cargo',
                    monto=venta.total,
                    saldo_anterior=saldo_anterior,
                    saldo_posterior=saldo_posterior,
                    referencia_tipo='venta',
                    referencia_id=venta.id,
                    descripcion=f'Venta #{venta.numero_completo}',
                    usuario_id=current_user.id
                )
                db.session.add(movimiento_cc)
            else:
                # Registrar movimiento de caja
                movimiento_caja = MovimientoCaja(
                    caja_id=caja.id,
                    tipo='ingreso',
                    concepto='venta',
                    descripcion=f'Venta #{venta.numero_completo}',
                    monto=venta.total,
                    forma_pago=forma_pago,
                    referencia_tipo='venta',
                    referencia_id=venta.id,
                    usuario_id=current_user.id
                )
                db.session.add(movimiento_caja)

            db.session.commit()

            flash(f'Venta #{venta.numero_completo} registrada. Total: ${venta.total:.2f}', 'success')

            # Redirigir al ticket o al POS
            if request.form.get('imprimir_ticket'):
                return redirect(url_for('ventas.ticket', id=venta.id))
            return redirect(url_for('ventas.punto_de_venta'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al procesar la venta: {str(e)}', 'danger')
            return redirect(url_for('ventas.punto_de_venta'))

    # GET - Mostrar pantalla de POS
    clientes = Cliente.query.filter_by(activo=True).order_by(Cliente.nombre).all()

    return render_template(
        'ventas/punto_venta.html',
        form=form,
        clientes=clientes
    )


@bp.route('/historial')
@login_required
def historial():
    """Historial de ventas."""
    page = request.args.get('page', 1, type=int)
    fecha_desde = request.args.get('fecha_desde')
    fecha_hasta = request.args.get('fecha_hasta')
    estado = request.args.get('estado', '')
    cliente_id = request.args.get('cliente', 0, type=int)

    query = Venta.query

    if fecha_desde:
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d')
        query = query.filter(Venta.fecha >= fecha_desde)

    if fecha_hasta:
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d')
        fecha_hasta = fecha_hasta.replace(hour=23, minute=59, second=59)
        query = query.filter(Venta.fecha <= fecha_hasta)

    if estado:
        query = query.filter(Venta.estado == estado)

    if cliente_id:
        query = query.filter(Venta.cliente_id == cliente_id)

    query = query.order_by(Venta.fecha.desc())
    ventas = paginar_query(query, page)

    # Obtener clientes para el filtro
    clientes = Cliente.query.filter_by(activo=True).order_by(Cliente.nombre).all()

    return render_template(
        'ventas/historial.html',
        ventas=ventas,
        clientes=clientes,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        estado_filtro=estado,
        cliente_id=cliente_id
    )


@bp.route('/<int:id>')
@login_required
def detalle(id):
    """Ver detalle de venta."""
    venta = Venta.query.get_or_404(id)
    return render_template('ventas/detalle.html', venta=venta)


@bp.route('/<int:id>/anular', methods=['GET', 'POST'])
@login_required
@admin_required
def anular(id):
    """Anular venta (solo administradores)."""
    venta = Venta.query.get_or_404(id)

    if not venta.es_anulable:
        flash('Esta venta no puede ser anulada.', 'warning')
        return redirect(url_for('ventas.detalle', id=id))

    form = AnulacionVentaForm()

    if form.validate_on_submit():
        # Revertir stock
        for detalle in venta.detalles:
            producto = detalle.producto
            cantidad = detalle.cantidad

            stock_anterior, stock_posterior = producto.actualizar_stock(cantidad, 'devolucion')

            # Registrar movimiento de stock
            movimiento = MovimientoStock(
                producto_id=producto.id,
                tipo='devolucion',
                cantidad=cantidad,
                stock_anterior=stock_anterior,
                stock_posterior=stock_posterior,
                referencia_tipo='anulacion_venta',
                referencia_id=venta.id,
                motivo=f'Anulación de venta #{venta.numero_completo}',
                usuario_id=current_user.id
            )
            db.session.add(movimiento)

        # Si era cuenta corriente, revertir el cargo
        if venta.forma_pago == 'cuenta_corriente' and venta.cliente:
            saldo_anterior, saldo_posterior = venta.cliente.actualizar_saldo(venta.total, 'pago')

            movimiento_cc = MovimientoCuentaCorriente(
                cliente_id=venta.cliente.id,
                tipo='pago',
                monto=venta.total,
                saldo_anterior=saldo_anterior,
                saldo_posterior=saldo_posterior,
                referencia_tipo='anulacion_venta',
                referencia_id=venta.id,
                descripcion=f'Anulación de venta #{venta.numero_completo}',
                usuario_id=current_user.id
            )
            db.session.add(movimiento_cc)

        # Marcar venta como anulada
        venta.estado = 'anulada'
        venta.motivo_anulacion = form.motivo.data

        db.session.commit()

        flash(f'Venta #{venta.numero_completo} anulada correctamente.', 'success')
        return redirect(url_for('ventas.historial'))

    return render_template('ventas/anular.html', venta=venta, form=form)


@bp.route('/<int:id>/ticket')
@login_required
def ticket(id):
    """Ver/imprimir ticket de venta."""
    venta = Venta.query.get_or_404(id)
    return render_template('ventas/ticket.html', venta=venta)


@bp.route('/buscar-producto')
@login_required
def buscar_producto():
    """Búsqueda de productos para el POS (HTMX)."""
    q = request.args.get('q', '')

    if len(q) < 2:
        return render_template('ventas/_resultados_busqueda.html', productos=[])

    productos = Producto.query.filter(
        Producto.activo == True,
        Producto.stock_actual > 0,
        db.or_(
            Producto.codigo.ilike(f'%{q}%'),
            Producto.nombre.ilike(f'%{q}%'),
            Producto.codigo_barras.ilike(f'%{q}%')
        )
    ).limit(10).all()

    return render_template('ventas/_resultados_busqueda.html', productos=productos)


@bp.route('/api/producto/<int:id>')
@login_required
def api_producto(id):
    """API para obtener datos de producto (para el POS)."""
    producto = Producto.query.get_or_404(id)
    return jsonify(producto.to_dict())
