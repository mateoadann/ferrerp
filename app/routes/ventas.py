"""Rutas de ventas y punto de venta."""

import json
from datetime import datetime
from decimal import Decimal

from flask import (
    Blueprint,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.exceptions import HTTPException

from ..extensions import db
from ..forms.venta_forms import AnulacionVentaForm, VentaForm
from ..models import (
    Caja,
    Cliente,
    MovimientoCaja,
    MovimientoCuentaCorriente,
    MovimientoStock,
    Producto,
    Venta,
    VentaDetalle,
    VentaPago,
)
from ..services import venta_service
from ..utils.decorators import admin_required, caja_abierta_required, empresa_aprobada_required
from ..utils.helpers import ahora_argentina, generar_numero_venta, paginar_query

bp = Blueprint('ventas', __name__, url_prefix='/ventas')


def _decimal_seguro(valor, default=Decimal('0')):
    """Convierte un valor a Decimal de forma segura.

    Maneja None, cadenas vacías y valores no numéricos
    devolviendo el default en vez de lanzar ConversionSyntax.
    """
    if valor is None or (isinstance(valor, str) and valor.strip() == ''):
        return default
    try:
        return Decimal(str(valor))
    except (ValueError, ArithmeticError):
        return default


@bp.route('/punto-de-venta', methods=['GET', 'POST'])
@login_required
@empresa_aprobada_required
@caja_abierta_required
def punto_de_venta():
    """Pantalla principal de punto de venta."""
    form = VentaForm()

    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            cliente_id = request.form.get('cliente_id', type=int)
            forma_pago = request.form.get('forma_pago', 'efectivo')
            descuento_porcentaje = _decimal_seguro(request.form.get('descuento_porcentaje'))
            descuento_monto_exacto_str = request.form.get('descuento_monto_exacto', '').strip()
            descuento_monto_exacto = (
                _decimal_seguro(descuento_monto_exacto_str)
                if descuento_monto_exacto_str
                else None
            )
            items_json = request.form.get('items_json', '[]')

            # Validar descuento global
            if descuento_porcentaje < 0 or descuento_porcentaje > 100:
                flash('El descuento debe estar entre 0% y 100%.', 'danger')
                return redirect(url_for('ventas.punto_de_venta'))

            items = json.loads(items_json)

            if not items:
                flash('Agrega al menos un producto a la venta.', 'danger')
                return redirect(url_for('ventas.punto_de_venta'))

            # Validaciones de cuenta corriente
            if forma_pago == 'cuenta_corriente':
                if not cliente_id:
                    flash('Debes seleccionar un cliente para pagar a cuenta corriente.', 'danger')
                    return redirect(url_for('ventas.punto_de_venta'))

                cliente = Cliente.get_o_404(cliente_id)
                if not cliente:
                    flash('Cliente no encontrado.', 'danger')
                    return redirect(url_for('ventas.punto_de_venta'))

            # Obtener caja abierta
            caja = Caja.query.filter_by(
                estado='abierta', empresa_id=current_user.empresa_id
            ).first()

            # Crear venta
            venta = Venta(
                numero=generar_numero_venta(current_user.empresa_id),
                fecha=ahora_argentina(),
                cliente_id=cliente_id if cliente_id else None,
                usuario_id=current_user.id,
                descuento_porcentaje=descuento_porcentaje,
                forma_pago=forma_pago,
                estado='completada',
                caja_id=caja.id,
                empresa_id=current_user.empresa_id,
            )

            subtotal = Decimal('0')

            # Procesar items
            for item in items:
                producto = Producto.query.filter_by(
                    id=item['producto_id'],
                    empresa_id=current_user.empresa_id,
                ).first()
                if not producto:
                    db.session.rollback()
                    flash('Producto no encontrado en el carrito.', 'danger')
                    return redirect(url_for('ventas.punto_de_venta'))

                cantidad = _decimal_seguro(item.get('cantidad'))
                precio = _decimal_seguro(item.get('precio_unitario'))
                desc_pct = _decimal_seguro(item.get('descuento_porcentaje'))
                modo_descuento_item = item.get('modoDescuento', 'porcentaje')
                precio_deseado_raw = item.get('precioDeseado')

                # Validar que cantidad y precio sean positivos
                if cantidad <= 0:
                    raise ValueError(
                        f'Cantidad invalida para "{producto.nombre}"'
                    )
                if precio <= 0:
                    raise ValueError(
                        f'Precio invalido para "{producto.nombre}"'
                    )

                if desc_pct < 0 or desc_pct > 100:
                    raise ValueError(
                        'El descuento debe estar entre 0 y 100'
                    )

                # Verificar stock
                if producto.stock_actual < cantidad:
                    flash(
                        f'Stock insuficiente para "{producto.nombre}". '
                        f'Disponible: {producto.stock_actual}',
                        'danger'
                    )
                    return redirect(url_for('ventas.punto_de_venta'))

                # Si la línea está en modo "$" (precio final deseado) usamos el
                # monto exacto en vez de derivarlo del porcentaje redondeado,
                # para evitar diferencias por redondeo.
                precio_deseado = None
                if modo_descuento_item == 'total' and precio_deseado_raw not in (None, ''):
                    pd = _decimal_seguro(precio_deseado_raw)
                    if pd > 0 and pd < precio:
                        precio_deseado = pd

                if precio_deseado is not None:
                    item_subtotal = cantidad * precio_deseado
                else:
                    bruto = cantidad * precio
                    descuento_item = bruto * (desc_pct / Decimal('100'))
                    item_subtotal = bruto - descuento_item
                subtotal += item_subtotal

                # Crear detalle de venta
                detalle = VentaDetalle(
                    producto_id=producto.id,
                    cantidad=cantidad,
                    precio_unitario=precio,
                    iva_porcentaje=producto.iva_porcentaje,
                    descuento_porcentaje=desc_pct,
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
                    usuario_id=current_user.id,
                    empresa_id=current_user.empresa_id,
                )
                db.session.add(movimiento_stock)

            # Validar descuento monto exacto contra subtotal
            if descuento_monto_exacto is not None and descuento_monto_exacto > Decimal('0'):
                if descuento_monto_exacto > subtotal:
                    db.session.rollback()
                    flash('El descuento no puede superar el subtotal.', 'danger')
                    return redirect(url_for('ventas.punto_de_venta'))

            # Calcular totales
            venta.subtotal = subtotal
            if descuento_monto_exacto is not None and descuento_monto_exacto > 0:
                # Modo "total deseado": usar monto exacto para evitar diferencia por redondeo
                venta.descuento_monto = descuento_monto_exacto
            elif descuento_porcentaje > 0:
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

            # Procesar pagos segun forma de pago
            if forma_pago == 'dividido':
                # Parsear y validar pago dividido
                pago_dividido_json = request.form.get('pago_dividido_json', '[]')
                try:
                    pagos_data = json.loads(pago_dividido_json)
                except (json.JSONDecodeError, TypeError):
                    db.session.rollback()
                    flash('Datos de pago dividido invalidos.', 'danger')
                    return redirect(url_for('ventas.punto_de_venta'))

                # Validar estructura
                if len(pagos_data) != 2:
                    db.session.rollback()
                    flash('El pago dividido requiere exactamente 2 formas de pago.', 'danger')
                    return redirect(url_for('ventas.punto_de_venta'))

                # Validar formas distintas
                if pagos_data[0]['forma_pago'] == pagos_data[1]['forma_pago']:
                    db.session.rollback()
                    flash('Las formas de pago deben ser distintas.', 'danger')
                    return redirect(url_for('ventas.punto_de_venta'))

                # Validar montos > 0 y suma correcta
                monto1 = _decimal_seguro(pagos_data[0].get('monto'))
                monto2 = _decimal_seguro(pagos_data[1].get('monto'))

                if monto1 <= 0 or monto2 <= 0:
                    db.session.rollback()
                    flash('Cada monto debe ser mayor a 0.', 'danger')
                    return redirect(url_for('ventas.punto_de_venta'))

                if abs((monto1 + monto2) - venta.total) > Decimal('0.01'):
                    db.session.rollback()
                    flash('Los montos no coinciden con el total de la venta.', 'danger')
                    return redirect(url_for('ventas.punto_de_venta'))

                # Validar CC si alguno es cuenta_corriente
                for pago_data in pagos_data:
                    if pago_data['forma_pago'] == 'cuenta_corriente':
                        if not cliente_id:
                            db.session.rollback()
                            flash(
                                'Debe seleccionar un cliente para cuenta corriente.',
                                'danger',
                            )
                            return redirect(url_for('ventas.punto_de_venta'))
                        cliente = Cliente.get_o_404(cliente_id)
                        monto_cc = _decimal_seguro(pago_data.get('monto'))
                        if not cliente.puede_comprar_a_credito(monto_cc):
                            db.session.rollback()
                            flash(
                                f'El monto de cuenta corriente (${monto_cc:.2f}) '
                                f'excede el limite disponible '
                                f'(${cliente.credito_disponible:.2f}).',
                                'danger',
                            )
                            return redirect(url_for('ventas.punto_de_venta'))

                # Crear VentaPago y movimientos por cada pago
                for pago_data in pagos_data:
                    fp = pago_data['forma_pago']
                    monto = _decimal_seguro(pago_data.get('monto'))

                    venta_pago = VentaPago(
                        venta_id=venta.id,
                        forma_pago=fp,
                        monto=monto,
                    )
                    db.session.add(venta_pago)

                    if fp == 'cuenta_corriente':
                        cliente = Cliente.get_o_404(cliente_id)
                        saldo_anterior, saldo_posterior = cliente.actualizar_saldo(
                            monto, 'cargo'
                        )
                        movimiento_cc = MovimientoCuentaCorriente(
                            cliente_id=cliente.id,
                            tipo='cargo',
                            monto=monto,
                            saldo_anterior=saldo_anterior,
                            saldo_posterior=saldo_posterior,
                            referencia_tipo='venta',
                            referencia_id=venta.id,
                            descripcion=f'Venta #{venta.numero_completo} (pago parcial)',
                            usuario_id=current_user.id,
                            empresa_id=current_user.empresa_id,
                        )
                        db.session.add(movimiento_cc)
                    else:
                        movimiento_caja = MovimientoCaja(
                            caja_id=caja.id,
                            tipo='ingreso',
                            concepto='venta',
                            descripcion=f'Venta #{venta.numero_completo} (pago parcial)',
                            monto=monto,
                            forma_pago=fp,
                            referencia_tipo='venta',
                            referencia_id=venta.id,
                            usuario_id=current_user.id,
                        )
                        db.session.add(movimiento_caja)

            elif forma_pago == 'cuenta_corriente':
                # Verificar limite de credito para cuenta corriente
                if not cliente.puede_comprar_a_credito(venta.total):
                    db.session.rollback()
                    flash(
                        f'El cliente excederia su limite de credito. '
                        f'Disponible: ${cliente.credito_disponible:.2f}',
                        'danger'
                    )
                    return redirect(url_for('ventas.punto_de_venta'))

                # Cargar a cuenta corriente
                saldo_anterior, saldo_posterior = cliente.actualizar_saldo(
                    venta.total, 'cargo'
                )

                movimiento_cc = MovimientoCuentaCorriente(
                    cliente_id=cliente.id,
                    tipo='cargo',
                    monto=venta.total,
                    saldo_anterior=saldo_anterior,
                    saldo_posterior=saldo_posterior,
                    referencia_tipo='venta',
                    referencia_id=venta.id,
                    descripcion=f'Venta #{venta.numero_completo}',
                    usuario_id=current_user.id,
                    empresa_id=current_user.empresa_id,
                )
                db.session.add(movimiento_cc)

                # Crear VentaPago para uniformidad en queries
                venta_pago = VentaPago(
                    venta_id=venta.id,
                    forma_pago=forma_pago,
                    monto=venta.total,
                )
                db.session.add(venta_pago)
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

                # Crear VentaPago para uniformidad en queries
                venta_pago = VentaPago(
                    venta_id=venta.id,
                    forma_pago=forma_pago,
                    monto=venta.total,
                )
                db.session.add(venta_pago)

            db.session.commit()

            flash(f'Venta #{venta.numero_completo} registrada. Total: ${venta.total:.2f}', 'success')

            session['limpiar_carrito'] = True

            # Redirigir al ticket o al POS
            if request.form.get('imprimir_ticket'):
                return redirect(url_for('ventas.ticket', id=venta.id))
            return redirect(url_for('ventas.punto_de_venta'))

        except HTTPException:
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            flash(f'Error al procesar la venta: {str(e)}', 'danger')
            return redirect(url_for('ventas.punto_de_venta'))

    # GET - Mostrar pantalla de POS
    limpiar_carrito = session.pop('limpiar_carrito', False)

    return render_template(
        'ventas/punto_venta.html',
        form=form,
        limpiar_carrito=limpiar_carrito
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

    query = Venta.query_empresa()

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

    # Obtener nombre del cliente seleccionado (para el autocomplete)
    cliente_nombre = ''
    if cliente_id:
        cliente_sel = Cliente.query.get(cliente_id)
        if cliente_sel:
            cliente_nombre = cliente_sel.nombre

    return render_template(
        'ventas/historial.html',
        ventas=ventas,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        estado_filtro=estado,
        cliente_id=cliente_id,
        cliente_nombre=cliente_nombre,
    )


@bp.route('/<int:id>')
@login_required
def detalle(id):
    """Ver detalle de venta."""
    venta = Venta.get_o_404(id)
    return render_template('ventas/detalle.html', venta=venta)


@bp.route('/<int:id>/anular', methods=['GET', 'POST'])
@login_required
@empresa_aprobada_required
@admin_required
def anular(id):
    """Anular venta (solo administradores)."""
    venta = Venta.get_o_404(id)

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
                usuario_id=current_user.id,
                empresa_id=current_user.empresa_id,
            )
            db.session.add(movimiento)

        # Revertir pagos segun forma de pago
        if venta.forma_pago == 'dividido':
            # Revertir cada componente del pago dividido
            for pago in venta.pagos:
                if pago.forma_pago == 'cuenta_corriente' and venta.cliente:
                    saldo_anterior, saldo_posterior = venta.cliente.actualizar_saldo(
                        pago.monto, 'pago'
                    )
                    movimiento_cc = MovimientoCuentaCorriente(
                        cliente_id=venta.cliente.id,
                        tipo='pago',
                        monto=pago.monto,
                        saldo_anterior=saldo_anterior,
                        saldo_posterior=saldo_posterior,
                        referencia_tipo='anulacion_venta',
                        referencia_id=venta.id,
                        descripcion=(
                            f'Anulacion de venta #{venta.numero_completo}'
                            f' (pago parcial)'
                        ),
                        usuario_id=current_user.id,
                        empresa_id=current_user.empresa_id,
                    )
                    db.session.add(movimiento_cc)
                else:
                    # Egreso de caja para componente no-CC
                    movimiento_caja = MovimientoCaja(
                        caja_id=venta.caja_id,
                        tipo='egreso',
                        concepto='devolucion',
                        descripcion=(
                            f'Anulacion de venta #{venta.numero_completo}'
                            f' (pago parcial)'
                        ),
                        monto=pago.monto,
                        forma_pago=pago.forma_pago,
                        referencia_tipo='anulacion_venta',
                        referencia_id=venta.id,
                        usuario_id=current_user.id,
                    )
                    db.session.add(movimiento_caja)
        elif venta.forma_pago == 'cuenta_corriente' and venta.cliente:
            saldo_anterior, saldo_posterior = venta.cliente.actualizar_saldo(
                venta.total, 'pago'
            )

            movimiento_cc = MovimientoCuentaCorriente(
                cliente_id=venta.cliente.id,
                tipo='pago',
                monto=venta.total,
                saldo_anterior=saldo_anterior,
                saldo_posterior=saldo_posterior,
                referencia_tipo='anulacion_venta',
                referencia_id=venta.id,
                descripcion=f'Anulacion de venta #{venta.numero_completo}',
                usuario_id=current_user.id,
                empresa_id=current_user.empresa_id,
            )
            db.session.add(movimiento_cc)
        else:
            # Egreso de caja para ventas con forma de pago simple (no CC)
            movimiento_caja = MovimientoCaja(
                caja_id=venta.caja_id,
                tipo='egreso',
                concepto='devolucion',
                descripcion=f'Anulacion de venta #{venta.numero_completo}',
                monto=venta.total,
                forma_pago=venta.forma_pago,
                referencia_tipo='anulacion_venta',
                referencia_id=venta.id,
                usuario_id=current_user.id,
            )
            db.session.add(movimiento_caja)

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
    venta = Venta.get_o_404(id)
    return render_template('ventas/ticket.html', venta=venta)


@bp.route('/<int:id>/pdf')
@login_required
def pdf(id):
    """Descargar PDF de comprobante de venta."""
    venta = Venta.get_o_404(id)
    sin_precios = request.args.get('sin_precios', '0') == '1'

    pdf_bytes = venta_service.generar_pdf(venta, sin_precios=sin_precios)

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = (
        f'inline; filename=remito_{venta.numero_completo}.pdf'
    )
    return response


@bp.route('/buscar-producto')
@login_required
def buscar_producto():
    """Búsqueda de productos para el POS (HTMX)."""
    q = request.args.get('q', '')

    if len(q) < 2:
        return render_template('ventas/_resultados_busqueda.html', productos=[])

    productos = Producto.query_empresa().filter(
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
    producto = Producto.get_o_404(id)
    return jsonify(producto.to_dict())
