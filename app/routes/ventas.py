"""Rutas de ventas y punto de venta."""

import json
from datetime import date, datetime, timedelta
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
from ..forms.cheque_forms import ChequeEmitidoForm
from ..forms.venta_forms import AnulacionVentaForm, VentaForm
from ..models import (
    Banco,
    Caja,
    Cheque,
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
from ..utils.helpers import (
    ahora_argentina,
    es_peticion_htmx,
    generar_numero_venta,
    paginar_query,
)

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


def _crear_cheque(
    datos,
    referencia_tipo,
    referencia_id,
    importe,
    empresa_id,
    usuario_id,
    cliente_id=None,
):
    """Crea un registro de Cheque a partir de los datos del formulario.

    Args:
        datos: dict con cheque_numero, cheque_banco_id, cheque_fecha_vencimiento,
               cheque_tipo_cheque (opcional)
        referencia_tipo: 'venta' o 'pago_cc'
        referencia_id: ID de la referencia
        importe: monto del cheque (Decimal)
        empresa_id: ID de la empresa
        usuario_id: ID del usuario
        cliente_id: ID del cliente (para cheques recibidos)

    Returns:
        Cheque creado

    Raises:
        ValueError: si faltan campos obligatorios
    """
    numero = (datos.get('cheque_numero') or '').strip()
    banco_id_str = (datos.get('cheque_banco_id') or datos.get('cheque_banco') or '').strip()
    fecha_venc_str = (datos.get('cheque_fecha_vencimiento') or '').strip()
    tipo_cheque = (datos.get('cheque_tipo_cheque') or 'cheque').strip()

    if not numero:
        raise ValueError('El número de cheque es obligatorio.')
    if not banco_id_str:
        raise ValueError('El banco del cheque es obligatorio.')
    if not fecha_venc_str:
        raise ValueError('La fecha de vencimiento del cheque es obligatoria.')

    # Intentar como ID numérico primero, luego como nombre (compatibilidad)
    try:
        banco_id = int(banco_id_str)
        banco = Banco.query.filter_by(id=banco_id, empresa_id=empresa_id).first()
    except (ValueError, TypeError):
        # Fallback: buscar por nombre (compatibilidad con POS texto)
        nombre_norm = banco_id_str.strip().title()
        banco = Banco.query.filter_by(empresa_id=empresa_id, nombre=nombre_norm).first()
        if not banco:
            # Crear banco on-the-fly si no existe
            banco = Banco(
                nombre=nombre_norm,
                empresa_id=empresa_id,
                activo=True,
            )
            db.session.add(banco)
            db.session.flush()

    if not banco:
        raise ValueError('El banco seleccionado no existe.')

    try:
        fecha_vencimiento = datetime.strptime(fecha_venc_str, '%Y-%m-%d').date()
    except ValueError:
        raise ValueError('La fecha de vencimiento del cheque no es válida.')

    cheque = Cheque(
        numero_cheque=numero,
        banco_id=banco.id,
        fecha_vencimiento=fecha_vencimiento,
        importe=importe,
        tipo='recibido',
        tipo_cheque=tipo_cheque,
        estado='en_cartera',
        referencia_tipo=referencia_tipo,
        referencia_id=referencia_id,
        cliente_id=cliente_id,
        empresa_id=empresa_id,
        usuario_id=usuario_id,
    )
    db.session.add(cheque)
    return cheque


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
                _decimal_seguro(descuento_monto_exacto_str) if descuento_monto_exacto_str else None
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

            # Validaciones de cheque: requiere cliente
            if forma_pago == 'cheque':
                if not cliente_id:
                    flash(
                        'Para pago con cheque debe seleccionar un cliente.',
                        'danger',
                    )
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
                    raise ValueError(f'Cantidad invalida para "{producto.nombre}"')
                if precio <= 0:
                    raise ValueError(f'Precio invalido para "{producto.nombre}"')

                if desc_pct < 0 or desc_pct > 100:
                    raise ValueError('El descuento debe estar entre 0 y 100')

                # Verificar stock
                if producto.stock_actual < cantidad:
                    flash(
                        f'Stock insuficiente para "{producto.nombre}". '
                        f'Disponible: {producto.stock_actual}',
                        'danger',
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
                    subtotal=item_subtotal,
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
                mov = (
                    MovimientoStock.query.filter_by(
                        producto_id=detalle.producto_id, referencia_tipo='venta', referencia_id=None
                    )
                    .order_by(MovimientoStock.id.desc())
                    .first()
                )
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

                # Validar formas distintas (se permite cheque+cheque)
                fp1 = pagos_data[0]['forma_pago']
                fp2 = pagos_data[1]['forma_pago']
                if fp1 == fp2 and fp1 != 'cheque':
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

                # Consumo de saldo a favor (aplica solo a porcion CC)
                monto_saldo_favor = _decimal_seguro(request.form.get('monto_saldo_favor'))

                # Validar CC y cheque si requieren cliente
                for pago_data in pagos_data:
                    if pago_data['forma_pago'] == 'cheque':
                        if not cliente_id:
                            db.session.rollback()
                            flash(
                                'Para pago con cheque debe seleccionar un cliente.',
                                'danger',
                            )
                            return redirect(url_for('ventas.punto_de_venta'))
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

                        # Validar saldo a favor contra porcion CC
                        if monto_saldo_favor > 0 and cliente.tiene_saldo_a_favor:
                            if monto_saldo_favor > cliente.saldo_a_favor:
                                db.session.rollback()
                                flash(
                                    'El monto a consumir no puede ser mayor ' 'al saldo a favor.',
                                    'danger',
                                )
                                return redirect(url_for('ventas.punto_de_venta'))
                            if monto_saldo_favor > monto_cc:
                                db.session.rollback()
                                flash(
                                    'El monto a consumir no puede ser mayor '
                                    'al monto de cuenta corriente.',
                                    'danger',
                                )
                                return redirect(url_for('ventas.punto_de_venta'))
                        else:
                            monto_saldo_favor = Decimal('0')

                        monto_cargo_cc_div = monto_cc - monto_saldo_favor
                        if monto_cargo_cc_div > 0 and not cliente.puede_comprar_a_credito(
                            monto_cargo_cc_div
                        ):
                            db.session.rollback()
                            flash(
                                f'El monto de cuenta corriente (${monto_cargo_cc_div:.2f}) '
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

                        # Consumir saldo a favor si corresponde
                        if monto_saldo_favor > 0:
                            saldo_ant_consumo, saldo_post_consumo = cliente.actualizar_saldo_favor(
                                monto_saldo_favor, 'cargo'
                            )
                            movimiento_consumo = MovimientoCuentaCorriente(
                                cliente_id=cliente.id,
                                tipo='cargo',
                                monto=monto_saldo_favor,
                                saldo_anterior=saldo_ant_consumo,
                                saldo_posterior=saldo_post_consumo,
                                referencia_tipo='consumo_saldo_favor',
                                referencia_id=venta.id,
                                descripcion=(
                                    f'Consumo saldo a favor - ' f'Venta #{venta.numero_completo}'
                                ),
                                usuario_id=current_user.id,
                                empresa_id=current_user.empresa_id,
                            )
                            db.session.add(movimiento_consumo)

                        # Cargar solo el remanente a cuenta corriente
                        monto_cargo_cc_div = monto - monto_saldo_favor
                        if monto_cargo_cc_div > 0:
                            saldo_anterior, saldo_posterior = cliente.actualizar_saldo(
                                monto_cargo_cc_div, 'cargo'
                            )
                            movimiento_cc = MovimientoCuentaCorriente(
                                cliente_id=cliente.id,
                                tipo='cargo',
                                monto=monto_cargo_cc_div,
                                saldo_anterior=saldo_anterior,
                                saldo_posterior=saldo_posterior,
                                referencia_tipo='venta',
                                referencia_id=venta.id,
                                descripcion=(f'Venta #{venta.numero_completo} (pago parcial)'),
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

                        # Crear cheque si el sub-pago es con cheque
                        if fp == 'cheque':
                            importe_cheque_div = _decimal_seguro(
                                pago_data.get('cheque_importe'),
                                default=monto,
                            )
                            if importe_cheque_div <= 0:
                                importe_cheque_div = monto

                            cheque_datos = {
                                'cheque_numero': pago_data.get(
                                    'cheque_numero', ''
                                ),
                                'cheque_banco_id': pago_data.get(
                                    'cheque_banco_id',
                                    pago_data.get('cheque_banco', ''),
                                ),
                                'cheque_tipo_cheque': pago_data.get(
                                    'cheque_tipo_cheque', 'cheque'
                                ),
                                'cheque_fecha_vencimiento': pago_data.get(
                                    'cheque_fecha_vencimiento', ''
                                ),
                            }
                            cheque_div = _crear_cheque(
                                datos=cheque_datos,
                                referencia_tipo='venta',
                                referencia_id=venta.id,
                                importe=importe_cheque_div,
                                empresa_id=current_user.empresa_id,
                                usuario_id=current_user.id,
                                cliente_id=cliente_id,
                            )

                            # Manejar diferencia cheque vs monto
                            cliente_ch = Cliente.get_o_404(cliente_id)
                            dif = importe_cheque_div - monto
                            if dif > Decimal('0.01'):
                                s_ant, s_post = (
                                    cliente_ch.actualizar_saldo_favor(
                                        dif, 'adelanto'
                                    )
                                )
                                mov_d = MovimientoCuentaCorriente(
                                    cliente_id=cliente_ch.id,
                                    tipo='pago',
                                    monto=dif,
                                    saldo_anterior=s_ant,
                                    saldo_posterior=s_post,
                                    referencia_tipo='adelanto_cheque',
                                    referencia_id=venta.id,
                                    descripcion=(
                                        'Adelanto por diferencia'
                                        ' cheque nro '
                                        f'{cheque_div.numero_cheque}'
                                        ' - Venta'
                                        f' #{venta.numero_completo}'
                                        ' (pago parcial)'
                                    ),
                                    usuario_id=current_user.id,
                                    empresa_id=(
                                        current_user.empresa_id
                                    ),
                                )
                                db.session.add(mov_d)
                            elif dif < Decimal('-0.01'):
                                monto_d = abs(dif)
                                s_ant, s_post = (
                                    cliente_ch.actualizar_saldo(
                                        monto_d, 'cargo'
                                    )
                                )
                                mov_d = MovimientoCuentaCorriente(
                                    cliente_id=cliente_ch.id,
                                    tipo='cargo',
                                    monto=monto_d,
                                    saldo_anterior=s_ant,
                                    saldo_posterior=s_post,
                                    referencia_tipo='saldo_cheque',
                                    referencia_id=venta.id,
                                    descripcion=(
                                        'Saldo pendiente venta'
                                        ' - pago con cheque nro'
                                        f' {cheque_div.numero_cheque}'
                                        ' (pago parcial)'
                                    ),
                                    usuario_id=current_user.id,
                                    empresa_id=(
                                        current_user.empresa_id
                                    ),
                                )
                                db.session.add(mov_d)

            elif forma_pago == 'cuenta_corriente':
                # Consumo de saldo a favor
                monto_saldo_favor = _decimal_seguro(request.form.get('monto_saldo_favor'))
                if monto_saldo_favor > 0 and cliente.tiene_saldo_a_favor:
                    if monto_saldo_favor > cliente.saldo_a_favor:
                        db.session.rollback()
                        flash(
                            'El monto a consumir no puede ser mayor al saldo a favor.',
                            'danger',
                        )
                        return redirect(url_for('ventas.punto_de_venta'))
                    if monto_saldo_favor > venta.total:
                        db.session.rollback()
                        flash(
                            'El monto a consumir no puede ser mayor al total de la venta.',
                            'danger',
                        )
                        return redirect(url_for('ventas.punto_de_venta'))

                    # Crear movimiento de consumo de saldo a favor
                    saldo_ant_consumo, saldo_post_consumo = cliente.actualizar_saldo_favor(
                        monto_saldo_favor, 'cargo'
                    )
                    movimiento_consumo = MovimientoCuentaCorriente(
                        cliente_id=cliente.id,
                        tipo='cargo',
                        monto=monto_saldo_favor,
                        saldo_anterior=saldo_ant_consumo,
                        saldo_posterior=saldo_post_consumo,
                        referencia_tipo='consumo_saldo_favor',
                        referencia_id=venta.id,
                        descripcion=f'Consumo saldo a favor - Venta #{venta.numero_completo}',
                        usuario_id=current_user.id,
                        empresa_id=current_user.empresa_id,
                    )
                    db.session.add(movimiento_consumo)
                else:
                    monto_saldo_favor = Decimal('0')

                # Monto efectivo a cargar en cuenta corriente
                monto_cargo_cc = venta.total - monto_saldo_favor

                # Verificar limite de credito para cuenta corriente
                if monto_cargo_cc > 0 and not cliente.puede_comprar_a_credito(monto_cargo_cc):
                    db.session.rollback()
                    flash(
                        f'El cliente excederia su limite de credito. '
                        f'Disponible: ${cliente.credito_disponible:.2f}',
                        'danger',
                    )
                    return redirect(url_for('ventas.punto_de_venta'))

                if monto_cargo_cc > 0:
                    # Cargar a cuenta corriente (solo el remanente)
                    saldo_anterior, saldo_posterior = cliente.actualizar_saldo(
                        monto_cargo_cc, 'cargo'
                    )

                    movimiento_cc = MovimientoCuentaCorriente(
                        cliente_id=cliente.id,
                        tipo='cargo',
                        monto=monto_cargo_cc,
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
                    usuario_id=current_user.id,
                )
                db.session.add(movimiento_caja)

                # Crear VentaPago para uniformidad en queries
                venta_pago = VentaPago(
                    venta_id=venta.id,
                    forma_pago=forma_pago,
                    monto=venta.total,
                )
                db.session.add(venta_pago)

                # Crear cheque si corresponde
                if forma_pago == 'cheque':
                    importe_cheque = _decimal_seguro(
                        request.form.get('cheque_importe'),
                        default=venta.total,
                    )
                    if importe_cheque <= 0:
                        importe_cheque = venta.total

                    cheque = _crear_cheque(
                        datos=request.form,
                        referencia_tipo='venta',
                        referencia_id=venta.id,
                        importe=importe_cheque,
                        empresa_id=current_user.empresa_id,
                        usuario_id=current_user.id,
                        cliente_id=cliente_id,
                    )

                    # Manejar diferencia entre cheque y total
                    cliente_cheque = Cliente.get_o_404(cliente_id)
                    diferencia = importe_cheque - venta.total
                    if diferencia > Decimal('0.01'):
                        # Cheque mayor: saldo a favor
                        saldo_ant, saldo_post = (
                            cliente_cheque.actualizar_saldo_favor(
                                diferencia, 'adelanto'
                            )
                        )
                        mov_dif = MovimientoCuentaCorriente(
                            cliente_id=cliente_cheque.id,
                            tipo='pago',
                            monto=diferencia,
                            saldo_anterior=saldo_ant,
                            saldo_posterior=saldo_post,
                            referencia_tipo='adelanto_cheque',
                            referencia_id=venta.id,
                            descripcion=(
                                'Adelanto por diferencia cheque'
                                f' nro {cheque.numero_cheque}'
                                f' - Venta #{venta.numero_completo}'
                            ),
                            usuario_id=current_user.id,
                            empresa_id=current_user.empresa_id,
                        )
                        db.session.add(mov_dif)
                    elif diferencia < Decimal('-0.01'):
                        # Cheque menor: deuda en cuenta corriente
                        monto_deuda = abs(diferencia)
                        saldo_ant, saldo_post = (
                            cliente_cheque.actualizar_saldo(
                                monto_deuda, 'cargo'
                            )
                        )
                        mov_dif = MovimientoCuentaCorriente(
                            cliente_id=cliente_cheque.id,
                            tipo='cargo',
                            monto=monto_deuda,
                            saldo_anterior=saldo_ant,
                            saldo_posterior=saldo_post,
                            referencia_tipo='saldo_cheque',
                            referencia_id=venta.id,
                            descripcion=(
                                'Saldo pendiente venta'
                                f' - pago con cheque'
                                f' nro {cheque.numero_cheque}'
                            ),
                            usuario_id=current_user.id,
                            empresa_id=current_user.empresa_id,
                        )
                        db.session.add(mov_dif)

            db.session.commit()

            flash(
                f'Venta #{venta.numero_completo} registrada. Total: ${venta.total:.2f}', 'success'
            )

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

    return render_template('ventas/punto_venta.html', form=form, limpiar_carrito=limpiar_carrito)


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


@bp.route('/cheques')
@login_required
@empresa_aprobada_required
def cheques():
    """Agenda de cheques: por cobrar (recibidos) y por pagar (emitidos)."""
    page = request.args.get('page', 1, type=int)
    tab = request.args.get('tab', 'por_cobrar')
    q = request.args.get('q', '').strip()
    filtro_kpi = request.args.get('filtro_kpi', '')
    orden = request.args.get('orden', '')
    direccion = request.args.get('dir', 'asc')

    hoy = date.today()
    en_7_dias = hoy + timedelta(days=7)

    # Determinar tipo según tab
    tipo_filtro = 'recibido' if tab == 'por_cobrar' else 'emitido'

    # Query base: todos los cheques del tipo seleccionado
    query = Cheque.query_empresa().filter(
        Cheque.tipo == tipo_filtro,
    )

    # Filtro por KPI clickeado
    if filtro_kpi == 'a_cobrar' and tab == 'por_cobrar':
        query = query.filter(
            Cheque.estado == 'en_cartera',
            Cheque.fecha_vencimiento <= hoy,
        )
    elif filtro_kpi == 'proximos':
        query = query.filter(
            Cheque.estado == 'en_cartera',
            Cheque.fecha_vencimiento >= hoy,
            Cheque.fecha_vencimiento <= en_7_dias,
        )
    elif filtro_kpi == 'vencidos' and tab == 'por_pagar':
        query = query.filter(
            Cheque.estado == 'en_cartera',
            Cheque.fecha_vencimiento < hoy,
        )

    # Búsqueda por número de cheque o nombre de banco
    if q:
        query = query.outerjoin(
            Banco, Cheque.banco_id == Banco.id
        ).filter(
            db.or_(
                Cheque.numero_cheque.ilike(f'%{q}%'),
                Banco.nombre.ilike(f'%{q}%'),
            )
        )

    # Ordenamiento dinámico por columna
    columnas_validas = {
        'fecha_vencimiento': Cheque.fecha_vencimiento,
        'estado': Cheque.estado,
        'importe': Cheque.importe,
    }
    columna_orden = columnas_validas.get(orden)
    if columna_orden is not None:
        if direccion == 'desc':
            query = query.order_by(columna_orden.desc())
        else:
            query = query.order_by(columna_orden.asc())
    else:
        # Default: fecha de vencimiento ascendente
        query = query.order_by(Cheque.fecha_vencimiento.asc())

    # Estadísticas del tab activo (sin filtro de búsqueda)
    stats_query = Cheque.query_empresa().filter(
        Cheque.tipo == tipo_filtro,
        Cheque.estado == 'en_cartera',
    )
    total_cheques = stats_query.count()
    monto_total = (
        db.session.query(
            db.func.coalesce(db.func.sum(Cheque.importe), 0)
        )
        .filter(
            Cheque.empresa_id == current_user.empresa_id,
            Cheque.tipo == tipo_filtro,
            Cheque.estado == 'en_cartera',
        )
        .scalar()
    )

    en_5_dias = hoy + timedelta(days=5)

    if tab == 'por_cobrar':
        # KPIs monetarios para recibidos
        monto_hoy = (
            db.session.query(
                db.func.coalesce(db.func.sum(Cheque.importe), 0)
            )
            .filter(
                Cheque.empresa_id == current_user.empresa_id,
                Cheque.tipo == 'recibido',
                Cheque.estado == 'en_cartera',
                Cheque.fecha_vencimiento <= hoy,
            )
            .scalar()
        )
        monto_proximos = (
            db.session.query(
                db.func.coalesce(db.func.sum(Cheque.importe), 0)
            )
            .filter(
                Cheque.empresa_id == current_user.empresa_id,
                Cheque.tipo == 'recibido',
                Cheque.estado == 'en_cartera',
                Cheque.fecha_vencimiento >= hoy,
                Cheque.fecha_vencimiento <= en_7_dias,
            )
            .scalar()
        )
        cantidad_vencidos = 0
        cantidad_proximos = 0
    else:
        # KPIs de conteo para emitidos (solo en_cartera = pendientes)
        monto_hoy = Decimal('0')
        monto_proximos = Decimal('0')
        kpi_emitidos = Cheque.query_empresa().filter(
            Cheque.tipo == 'emitido',
            Cheque.estado == 'en_cartera',
        )
        cantidad_vencidos = kpi_emitidos.filter(
            Cheque.fecha_vencimiento < hoy,
        ).count()
        cantidad_proximos = kpi_emitidos.filter(
            Cheque.fecha_vencimiento >= hoy,
            Cheque.fecha_vencimiento <= en_7_dias,
        ).count()

    # Paginar resultados
    cheques_pag = paginar_query(query, page)

    # Resolver cliente_id para cheques recibidos con referencia pago_cc o adelanto_cc
    cheque_cliente_map = {}
    if tab == 'por_cobrar':
        refs = [c for c in cheques_pag.items if c.referencia_tipo in ('pago_cc', 'adelanto_cc')]
        for cheque in refs:
            mov = MovimientoCuentaCorriente.query.filter_by(
                id=cheque.referencia_id,
            ).first()
            if mov:
                cheque_cliente_map[cheque.id] = mov.cliente_id

    # Formulario para cheques emitidos (tab por_pagar)
    form_emitido = ChequeEmitidoForm()

    # Si es petición HTMX, devolver solo la tabla parcial
    if es_peticion_htmx():
        return render_template(
            'ventas/_tabla_cheques.html',
            cheques=cheques_pag,
            tab=tab,
            q=q,
            filtro_kpi=filtro_kpi,
            orden=orden,
            direccion=direccion,
            total_cheques=total_cheques,
            monto_total=monto_total,
            monto_hoy=monto_hoy,
            monto_proximos=monto_proximos,
            cantidad_vencidos=cantidad_vencidos,
            cantidad_proximos=cantidad_proximos,
            cheque_cliente_map=cheque_cliente_map,
            hoy=hoy,
            en_5_dias=en_5_dias,
            en_7_dias=en_7_dias,
            form_emitido=form_emitido,
        )

    return render_template(
        'ventas/cheques.html',
        cheques=cheques_pag,
        tab=tab,
        q=q,
        filtro_kpi=filtro_kpi,
        orden=orden,
        direccion=direccion,
        total_cheques=total_cheques,
        monto_total=monto_total,
        monto_hoy=monto_hoy,
        monto_proximos=monto_proximos,
        cantidad_vencidos=cantidad_vencidos,
        cantidad_proximos=cantidad_proximos,
        cheque_cliente_map=cheque_cliente_map,
        hoy=hoy,
        en_5_dias=en_5_dias,
        en_7_dias=en_7_dias,
        form_emitido=form_emitido,
    )


@bp.route('/cheques/kpi')
@login_required
@empresa_aprobada_required
def cheques_kpi():
    """Devolver solo las cards KPI de cheques (para HTMX)."""
    tab = request.args.get('tab', 'por_cobrar')
    q = request.args.get('q', '').strip()
    filtro_kpi = request.args.get('filtro_kpi', '')

    hoy = date.today()
    en_7_dias = hoy + timedelta(days=7)
    tipo_filtro = 'recibido' if tab == 'por_cobrar' else 'emitido'

    stats_query = Cheque.query_empresa().filter(
        Cheque.tipo == tipo_filtro,
        Cheque.estado == 'en_cartera',
    )
    total_cheques = stats_query.count()
    monto_total = (
        db.session.query(
            db.func.coalesce(db.func.sum(Cheque.importe), 0)
        )
        .filter(
            Cheque.empresa_id == current_user.empresa_id,
            Cheque.tipo == tipo_filtro,
            Cheque.estado == 'en_cartera',
        )
        .scalar()
    )

    if tab == 'por_cobrar':
        monto_hoy = (
            db.session.query(
                db.func.coalesce(db.func.sum(Cheque.importe), 0)
            )
            .filter(
                Cheque.empresa_id == current_user.empresa_id,
                Cheque.tipo == 'recibido',
                Cheque.estado == 'en_cartera',
                Cheque.fecha_vencimiento <= hoy,
            )
            .scalar()
        )
        monto_proximos = (
            db.session.query(
                db.func.coalesce(db.func.sum(Cheque.importe), 0)
            )
            .filter(
                Cheque.empresa_id == current_user.empresa_id,
                Cheque.tipo == 'recibido',
                Cheque.estado == 'en_cartera',
                Cheque.fecha_vencimiento >= hoy,
                Cheque.fecha_vencimiento <= en_7_dias,
            )
            .scalar()
        )
        cantidad_vencidos = 0
        cantidad_proximos = 0
    else:
        monto_hoy = Decimal('0')
        monto_proximos = Decimal('0')
        kpi_emitidos = Cheque.query_empresa().filter(
            Cheque.tipo == 'emitido',
            Cheque.estado == 'en_cartera',
        )
        cantidad_vencidos = kpi_emitidos.filter(
            Cheque.fecha_vencimiento < hoy,
        ).count()
        cantidad_proximos = kpi_emitidos.filter(
            Cheque.fecha_vencimiento >= hoy,
            Cheque.fecha_vencimiento <= en_7_dias,
        ).count()

    return render_template(
        'ventas/_kpi_cheques.html',
        tab=tab,
        q=q,
        filtro_kpi=filtro_kpi,
        total_cheques=total_cheques,
        monto_total=monto_total,
        monto_hoy=monto_hoy,
        monto_proximos=monto_proximos,
        cantidad_vencidos=cantidad_vencidos,
        cantidad_proximos=cantidad_proximos,
    )


@bp.route('/cheques/emitido', methods=['POST'])
@login_required
@empresa_aprobada_required
def crear_cheque_emitido():
    """Registrar un cheque emitido."""
    form = ChequeEmitidoForm()

    if form.validate_on_submit():
        cliente_id = form.cliente_id.data if form.cliente_id.data and form.cliente_id.data != 0 else None
        if cliente_id:
            cliente = Cliente.query.get(cliente_id)
            destinatario = cliente.nombre if cliente else form.destinatario.data.strip()
        else:
            destinatario = form.destinatario.data.strip()

        cheque = Cheque(
            numero_cheque=form.numero_cheque.data.strip(),
            banco_id=form.banco_id.data,
            tipo_cheque='echeq' if form.es_echeq.data else 'cheque',
            fecha_vencimiento=form.fecha_vencimiento.data,
            importe=Decimal(str(form.importe.data)),
            tipo='emitido',
            estado='en_cartera',
            cliente_id=cliente_id,
            destinatario=destinatario,
            observaciones=form.observaciones.data or None,
            referencia_tipo=None,
            referencia_id=None,
            empresa_id=current_user.empresa_id,
            usuario_id=current_user.id,
        )
        db.session.add(cheque)
        db.session.commit()

        flash('Cheque emitido registrado correctamente.', 'success')
        return redirect(url_for('ventas.cheques', tab='por_pagar'))

    # Si hay errores de validación, volver a la agenda con los errores
    for campo, errores in form.errors.items():
        for error in errores:
            flash(f'{error}', 'danger')

    return redirect(url_for('ventas.cheques', tab='por_pagar'))


@bp.route('/cheques/<int:id>/acciones', methods=['GET'])
@login_required
@empresa_aprobada_required
def acciones_cheque(id):
    """Devuelve modal con acciones disponibles para un cheque (HTMX)."""
    cheque = Cheque.query.filter_by(
        id=id,
        empresa_id=current_user.empresa_id,
    ).first_or_404()

    return render_template(
        'ventas/_modal_acciones_cheque.html',
        cheque=cheque,
    )


@bp.route('/cheques/<int:id>/cambiar-estado', methods=['POST'])
@login_required
@empresa_aprobada_required
def cambiar_estado_cheque(id):
    """Cambiar estado de un cheque usando máquina de estados (HTMX)."""
    from ..models.cheque import transicion_valida

    cheque = Cheque.query.filter_by(
        id=id,
        empresa_id=current_user.empresa_id,
    ).first_or_404()

    nuevo_estado = request.form.get('nuevo_estado', '').strip()

    if not nuevo_estado:
        flash('Debe seleccionar un estado.', 'danger')
        return '', 422

    if not transicion_valida(cheque.tipo, cheque.estado, nuevo_estado):
        flash(
            f'Transición no válida: {cheque.estado} → {nuevo_estado}.',
            'danger',
        )
        return '', 422

    cheque.estado = nuevo_estado
    db.session.commit()

    etiquetas = {
        'cobrado': 'Cobrado',
        'endosado': 'Endosado',
        'sin_fondos': 'Sin fondos',
    }
    flash(
        f'Estado del cheque actualizado a '
        f'{etiquetas.get(nuevo_estado, nuevo_estado)}.',
        'success',
    )
    resp = make_response(
        render_template(
            'ventas/_fila_cheque.html',
            cheque=cheque,
            tab='por_cobrar' if cheque.tipo == 'recibido' else 'por_pagar',
            cheque_cliente_map={},
            hoy=date.today(),
            en_7_dias=date.today() + timedelta(days=7),
        )
    )
    resp.headers['HX-Trigger'] = 'cheques-actualizados'
    return resp


@bp.route('/<int:id>')
@login_required
def detalle(id):
    """Ver detalle de venta."""
    venta = Venta.get_o_404(id)

    # Buscar cheque asociado a la venta
    cheque_venta = Cheque.query.filter_by(
        referencia_tipo='venta',
        referencia_id=venta.id,
        empresa_id=current_user.empresa_id,
    ).first()

    return render_template(
        'ventas/detalle.html',
        venta=venta,
        cheque_venta=cheque_venta,
    )


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
                    # Obtener el monto real cargado a CC (puede ser menor
                    # al pago si hubo consumo de saldo a favor)
                    mov_venta_cc = MovimientoCuentaCorriente.query.filter_by(
                        referencia_tipo='venta',
                        referencia_id=venta.id,
                        tipo='cargo',
                        empresa_id=current_user.empresa_id,
                    ).first()
                    monto_a_revertir = mov_venta_cc.monto if mov_venta_cc else Decimal('0')

                    if monto_a_revertir > 0:
                        saldo_anterior, saldo_posterior = venta.cliente.actualizar_saldo(
                            monto_a_revertir, 'pago'
                        )
                        movimiento_cc = MovimientoCuentaCorriente(
                            cliente_id=venta.cliente.id,
                            tipo='pago',
                            monto=monto_a_revertir,
                            saldo_anterior=saldo_anterior,
                            saldo_posterior=saldo_posterior,
                            referencia_tipo='anulacion_venta',
                            referencia_id=venta.id,
                            descripcion=(
                                f'Anulacion de venta #{venta.numero_completo}' f' (pago parcial)'
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
                            f'Anulacion de venta #{venta.numero_completo}' f' (pago parcial)'
                        ),
                        monto=pago.monto,
                        forma_pago=pago.forma_pago,
                        referencia_tipo='anulacion_venta',
                        referencia_id=venta.id,
                        usuario_id=current_user.id,
                    )
                    db.session.add(movimiento_caja)
        elif venta.forma_pago == 'cuenta_corriente' and venta.cliente:
            # Obtener el monto real cargado a CC (puede ser menor
            # al total si hubo consumo de saldo a favor)
            mov_venta_cc = MovimientoCuentaCorriente.query.filter_by(
                referencia_tipo='venta',
                referencia_id=venta.id,
                tipo='cargo',
                empresa_id=current_user.empresa_id,
            ).first()
            monto_a_revertir = mov_venta_cc.monto if mov_venta_cc else Decimal('0')

            if monto_a_revertir > 0:
                saldo_anterior, saldo_posterior = venta.cliente.actualizar_saldo(
                    monto_a_revertir, 'pago'
                )

                movimiento_cc = MovimientoCuentaCorriente(
                    cliente_id=venta.cliente.id,
                    tipo='pago',
                    monto=monto_a_revertir,
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

        # Devolver cheques asociados a la venta a en_cartera
        cheques_venta = Cheque.query.filter_by(
            referencia_tipo='venta',
            referencia_id=venta.id,
        ).all()
        for cheque in cheques_venta:
            cheque.estado = 'en_cartera'

        # Revertir consumo de saldo a favor si lo hubo
        if venta.cliente:
            movimientos_consumo = MovimientoCuentaCorriente.query.filter_by(
                referencia_tipo='consumo_saldo_favor',
                referencia_id=venta.id,
                empresa_id=current_user.empresa_id,
            ).all()

            for mov_consumo in movimientos_consumo:
                saldo_ant, saldo_post = venta.cliente.actualizar_saldo_favor(
                    mov_consumo.monto, 'adelanto'
                )
                movimiento_reversion = MovimientoCuentaCorriente(
                    cliente_id=venta.cliente_id,
                    tipo='pago',
                    monto=mov_consumo.monto,
                    saldo_anterior=saldo_ant,
                    saldo_posterior=saldo_post,
                    referencia_tipo='anul_consumo_saldo',
                    referencia_id=venta.id,
                    descripcion=(
                        f'Anulación consumo saldo a favor - ' f'Venta #{venta.numero_completo}'
                    ),
                    usuario_id=current_user.id,
                    empresa_id=current_user.empresa_id,
                )
                db.session.add(movimiento_reversion)

        # Revertir adelantos por diferencia de cheque (cheque > total)
        if venta.cliente:
            movs_adelanto_cheque = (
                MovimientoCuentaCorriente.query.filter_by(
                    referencia_tipo='adelanto_cheque',
                    referencia_id=venta.id,
                    empresa_id=current_user.empresa_id,
                ).all()
            )
            for mov_adel in movs_adelanto_cheque:
                saldo_ant, saldo_post = (
                    venta.cliente.actualizar_saldo_favor(
                        mov_adel.monto, 'cargo'
                    )
                )
                mov_rev = MovimientoCuentaCorriente(
                    cliente_id=venta.cliente_id,
                    tipo='cargo',
                    monto=mov_adel.monto,
                    saldo_anterior=saldo_ant,
                    saldo_posterior=saldo_post,
                    referencia_tipo='anul_adelanto_cheque',
                    referencia_id=venta.id,
                    descripcion=(
                        'Anulación adelanto cheque'
                        f' - Venta #{venta.numero_completo}'
                    ),
                    usuario_id=current_user.id,
                    empresa_id=current_user.empresa_id,
                )
                db.session.add(mov_rev)

            # Revertir deudas por diferencia de cheque (cheque < total)
            movs_saldo_cheque = (
                MovimientoCuentaCorriente.query.filter_by(
                    referencia_tipo='saldo_cheque',
                    referencia_id=venta.id,
                    empresa_id=current_user.empresa_id,
                ).all()
            )
            for mov_saldo in movs_saldo_cheque:
                saldo_ant, saldo_post = (
                    venta.cliente.actualizar_saldo(
                        mov_saldo.monto, 'pago'
                    )
                )
                mov_rev = MovimientoCuentaCorriente(
                    cliente_id=venta.cliente_id,
                    tipo='pago',
                    monto=mov_saldo.monto,
                    saldo_anterior=saldo_ant,
                    saldo_posterior=saldo_post,
                    referencia_tipo='anul_saldo_cheque',
                    referencia_id=venta.id,
                    descripcion=(
                        'Anulación saldo cheque'
                        f' - Venta #{venta.numero_completo}'
                    ),
                    usuario_id=current_user.id,
                    empresa_id=current_user.empresa_id,
                )
                db.session.add(mov_rev)

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
    response.headers['Content-Disposition'] = f'inline; filename=remito_{venta.numero_completo}.pdf'
    return response


@bp.route('/buscar-producto')
@login_required
def buscar_producto():
    """Búsqueda de productos para el POS (HTMX)."""
    q = request.args.get('q', '')

    if len(q) < 2:
        return render_template('ventas/_resultados_busqueda.html', productos=[])

    productos = (
        Producto.query_empresa()
        .filter(
            Producto.activo == True,
            Producto.stock_actual > 0,
            db.or_(
                Producto.codigo.ilike(f'%{q}%'),
                Producto.nombre.ilike(f'%{q}%'),
                Producto.codigo_barras.ilike(f'%{q}%'),
            ),
        )
        .limit(10)
        .all()
    )

    return render_template('ventas/_resultados_busqueda.html', productos=productos)


@bp.route('/api/producto/<int:id>')
@login_required
def api_producto(id):
    """API para obtener datos de producto (para el POS)."""
    producto = Producto.get_o_404(id)
    return jsonify(producto.to_dict())
