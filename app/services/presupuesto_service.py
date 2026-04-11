"""Servicio de presupuestos."""

import json
from datetime import timedelta
from decimal import Decimal
from urllib.parse import quote

from flask import render_template

from ..extensions import db
from ..models import (
    Caja,
    Configuracion,
    MovimientoCaja,
    MovimientoCuentaCorriente,
    MovimientoStock,
    Presupuesto,
    PresupuestoDetalle,
    Producto,
    Venta,
    VentaDetalle,
    VentaPago,
)
from ..utils.helpers import ahora_argentina, generar_numero_presupuesto, generar_numero_venta


def crear_presupuesto(
    items,
    usuario_id,
    empresa_id=None,
    cliente_id=None,
    cliente_nombre=None,
    cliente_telefono=None,
    descuento_porcentaje=0,
    descuento_monto_exacto=None,
    validez_dias=None,
    notas=None,
):
    """Crea un nuevo presupuesto con sus líneas de detalle."""
    descuento_porcentaje = Decimal(str(descuento_porcentaje))
    if descuento_porcentaje < 0 or descuento_porcentaje > 100:
        raise ValueError('El descuento general debe estar entre 0 y 100')

    if validez_dias is None:
        validez_dias = Configuracion.get('presupuesto_validez_dias', 15)

    fecha = ahora_argentina()
    fecha_vencimiento = fecha + timedelta(days=int(validez_dias))

    presupuesto = Presupuesto(
        numero=generar_numero_presupuesto(empresa_id) if empresa_id else 1,
        fecha=fecha,
        fecha_vencimiento=fecha_vencimiento,
        cliente_id=cliente_id if cliente_id else None,
        cliente_nombre=cliente_nombre,
        cliente_telefono=cliente_telefono,
        usuario_id=usuario_id,
        descuento_porcentaje=descuento_porcentaje,
        notas=notas,
        empresa_id=empresa_id,
    )

    subtotal = Decimal('0')

    for item in items:
        producto = db.session.get(Producto, item['producto_id'])
        if not producto:
            raise ValueError(f'Producto no encontrado: {item["producto_id"]}')

        cantidad = Decimal(str(item['cantidad']))
        precio = Decimal(str(item['precio_unitario']))
        desc_pct = Decimal(str(item.get('descuento_porcentaje', 0)))
        modo_descuento_item = item.get('modoDescuento', 'porcentaje')
        precio_deseado_raw = item.get('precioDeseado')

        if desc_pct < 0 or desc_pct > 100:
            raise ValueError('El descuento debe estar entre 0 y 100')

        # En modo "$" (total deseado por unidad) usamos el monto exacto
        # para evitar diferencias por redondeo del porcentaje.
        precio_deseado = None
        if modo_descuento_item == 'total' and precio_deseado_raw not in (None, ''):
            try:
                pd = Decimal(str(precio_deseado_raw))
                if 0 <= pd < precio:
                    precio_deseado = pd
            except (ValueError, ArithmeticError):
                precio_deseado = None

        if precio_deseado is not None:
            item_subtotal = cantidad * precio_deseado
        else:
            bruto = cantidad * precio
            descuento_item = bruto * (desc_pct / Decimal('100'))
            item_subtotal = bruto - descuento_item
        subtotal += item_subtotal

        detalle = PresupuestoDetalle(
            producto_id=producto.id,
            cantidad=cantidad,
            precio_unitario=precio,
            iva_porcentaje=producto.iva_porcentaje,
            descuento_porcentaje=desc_pct,
            subtotal=item_subtotal,
        )
        presupuesto.detalles.append(detalle)

    presupuesto.subtotal = subtotal
    if descuento_monto_exacto is not None and descuento_monto_exacto > 0:
        # Modo "total deseado": usar monto exacto para evitar diferencia por redondeo
        presupuesto.descuento_monto = descuento_monto_exacto
    elif presupuesto.descuento_porcentaje > 0:
        presupuesto.descuento_monto = subtotal * (presupuesto.descuento_porcentaje / 100)
    else:
        presupuesto.descuento_monto = Decimal('0')
    presupuesto.total = subtotal - presupuesto.descuento_monto

    db.session.add(presupuesto)
    db.session.commit()

    return presupuesto


def actualizar_presupuesto(
    presupuesto,
    items,
    cliente_id=None,
    cliente_nombre=None,
    cliente_telefono=None,
    descuento_porcentaje=0,
    descuento_monto_exacto=None,
    validez_dias=None,
    notas=None,
):
    """Actualiza un presupuesto pendiente."""
    if not presupuesto.puede_editar:
        raise ValueError('El presupuesto no puede editarse en su estado actual.')

    # Validar descuento global ANTES de modificar datos existentes
    descuento_porcentaje = Decimal(str(descuento_porcentaje))
    if descuento_porcentaje < 0 or descuento_porcentaje > 100:
        raise ValueError('El descuento general debe estar entre 0 y 100')

    # Validar todos los items ANTES de modificar datos existentes
    items_validados = []
    for item in items:
        producto = db.session.get(Producto, item['producto_id'])
        if not producto:
            raise ValueError(f'Producto no encontrado: {item["producto_id"]}')

        cantidad = Decimal(str(item['cantidad']))
        precio = Decimal(str(item['precio_unitario']))
        desc_pct = Decimal(str(item.get('descuento_porcentaje', 0)))
        modo_descuento_item = item.get('modoDescuento', 'porcentaje')
        precio_deseado_raw = item.get('precioDeseado')

        if desc_pct < 0 or desc_pct > 100:
            raise ValueError('El descuento debe estar entre 0 y 100')

        if cantidad <= 0:
            raise ValueError(f'La cantidad debe ser mayor a 0 para "{producto.nombre}"')

        # Resolver precio deseado si la línea está en modo "$"
        precio_deseado = None
        if modo_descuento_item == 'total' and precio_deseado_raw not in (None, ''):
            try:
                pd = Decimal(str(precio_deseado_raw))
                if 0 <= pd < precio:
                    precio_deseado = pd
            except (ValueError, ArithmeticError):
                precio_deseado = None

        items_validados.append(
            {
                'producto': producto,
                'cantidad': cantidad,
                'precio': precio,
                'desc_pct': desc_pct,
                'precio_deseado': precio_deseado,
            }
        )

    # Validación pasó — aplicar cambios dentro de un SAVEPOINT para que
    # cualquier error posterior (constraint, flush, etc.) no deje los
    # detalles eliminados sin posibilidad de rollback limpio.
    try:
        db.session.begin_nested()

        if validez_dias is not None:
            presupuesto.fecha_vencimiento = presupuesto.fecha + timedelta(days=int(validez_dias))

        presupuesto.cliente_id = cliente_id if cliente_id else None
        presupuesto.cliente_nombre = cliente_nombre
        presupuesto.cliente_telefono = cliente_telefono
        presupuesto.descuento_porcentaje = descuento_porcentaje
        presupuesto.notas = notas

        # Eliminar detalles existentes
        PresupuestoDetalle.query.filter_by(presupuesto_id=presupuesto.id).delete()

        subtotal = Decimal('0')

        for iv in items_validados:
            producto = iv['producto']
            cantidad = iv['cantidad']
            precio = iv['precio']
            desc_pct = iv['desc_pct']
            precio_deseado = iv.get('precio_deseado')

            # En modo "$" usamos el monto exacto para evitar redondeo.
            if precio_deseado is not None:
                item_subtotal = cantidad * precio_deseado
            else:
                bruto = cantidad * precio
                descuento_item = bruto * (desc_pct / Decimal('100'))
                item_subtotal = bruto - descuento_item
            subtotal += item_subtotal

            detalle = PresupuestoDetalle(
                presupuesto_id=presupuesto.id,
                producto_id=producto.id,
                cantidad=cantidad,
                precio_unitario=precio,
                iva_porcentaje=producto.iva_porcentaje,
                descuento_porcentaje=desc_pct,
                subtotal=item_subtotal,
            )
            db.session.add(detalle)

        presupuesto.subtotal = subtotal
        if descuento_monto_exacto is not None and descuento_monto_exacto > 0:
            # Modo "total deseado": usar monto exacto para evitar diferencia por redondeo
            presupuesto.descuento_monto = descuento_monto_exacto
        elif presupuesto.descuento_porcentaje > 0:
            presupuesto.descuento_monto = subtotal * (presupuesto.descuento_porcentaje / 100)
        else:
            presupuesto.descuento_monto = Decimal('0')
        presupuesto.total = subtotal - presupuesto.descuento_monto

    except Exception:
        db.session.rollback()
        raise

    db.session.commit()
    return presupuesto


def cambiar_estado(presupuesto, nuevo_estado):
    """Cambia el estado del presupuesto validando transiciones."""
    transiciones = {
        'pendiente': ['aceptado', 'rechazado', 'vencido'],
        'aceptado': ['convertido'],
    }

    permitidos = transiciones.get(presupuesto.estado, [])
    if nuevo_estado not in permitidos:
        raise ValueError(
            f'No se puede cambiar de "{presupuesto.estado_display}" ' f'a "{nuevo_estado}".'
        )

    presupuesto.estado = nuevo_estado
    db.session.commit()
    return presupuesto


def convertir_a_venta(
    presupuesto, usuario_id, forma_pago, caja_id, empresa_id=None, pago_dividido_json=None
):
    """Convierte un presupuesto aceptado en venta."""
    if not presupuesto.puede_convertir:
        raise ValueError('Solo presupuestos aceptados pueden convertirse a venta.')

    caja = db.session.get(Caja, caja_id)
    if not caja or caja.estado != 'abierta':
        raise ValueError('No hay caja abierta.')

    # Verificar stock de todos los productos
    detalles = list(presupuesto.detalles)
    for detalle in detalles:
        producto = detalle.producto
        if producto.stock_actual < detalle.cantidad:
            raise ValueError(
                f'Stock insuficiente para "{producto.nombre}". '
                f'Disponible: {producto.stock_actual}, '
                f'Requerido: {detalle.cantidad}'
            )

    # Validar cuenta corriente
    if forma_pago == 'cuenta_corriente':
        cliente = presupuesto.cliente
        if not cliente:
            raise ValueError('Se requiere un cliente registrado para cuenta corriente.')
        if not cliente.puede_comprar_a_credito(presupuesto.total):
            raise ValueError(
                f'El cliente excedería su límite de crédito. '
                f'Disponible: ${cliente.credito_disponible:.2f}'
            )

    # Crear venta
    venta = Venta(
        numero=generar_numero_venta(empresa_id),
        fecha=ahora_argentina(),
        cliente_id=presupuesto.cliente_id,
        usuario_id=usuario_id,
        descuento_porcentaje=presupuesto.descuento_porcentaje,
        forma_pago=forma_pago,
        estado='completada',
        caja_id=caja_id,
        presupuesto_id=presupuesto.id,
        empresa_id=empresa_id,
    )

    subtotal = Decimal('0')

    for detalle in detalles:
        producto = detalle.producto
        cantidad = detalle.cantidad
        precio = detalle.precio_unitario
        desc_pct = detalle.descuento_porcentaje or Decimal('0')
        # Usamos el subtotal persistido del detalle del presupuesto para
        # respetar el monto exacto cuando la línea fue creada en modo "$".
        item_subtotal = detalle.subtotal
        subtotal += item_subtotal

        # Detalle de venta
        venta_detalle = VentaDetalle(
            producto_id=producto.id,
            cantidad=cantidad,
            precio_unitario=precio,
            iva_porcentaje=detalle.iva_porcentaje,
            descuento_porcentaje=desc_pct,
            subtotal=item_subtotal,
        )
        venta.detalles.append(venta_detalle)

        # Descontar stock
        stock_anterior, stock_posterior = producto.actualizar_stock(-cantidad, 'venta')

        movimiento_stock = MovimientoStock(
            producto_id=producto.id,
            tipo='venta',
            cantidad=-cantidad,
            stock_anterior=stock_anterior,
            stock_posterior=stock_posterior,
            referencia_tipo='venta',
            usuario_id=usuario_id,
            empresa_id=empresa_id,
        )
        db.session.add(movimiento_stock)

    venta.subtotal = subtotal
    if presupuesto.descuento_porcentaje > 0:
        venta.descuento_monto = subtotal * (presupuesto.descuento_porcentaje / 100)
    else:
        venta.descuento_monto = Decimal('0')
    venta.total = subtotal - venta.descuento_monto

    db.session.add(venta)
    db.session.flush()

    # Actualizar referencia en movimientos de stock
    for venta_det in venta.detalles:
        mov = (
            MovimientoStock.query.filter_by(
                producto_id=venta_det.producto_id, referencia_tipo='venta', referencia_id=None
            )
            .order_by(MovimientoStock.id.desc())
            .first()
        )
        if mov:
            mov.referencia_id = venta.id

    # Procesar pagos segun forma de pago
    desc_base = f'Venta #{venta.numero_completo} (Presup. #{presupuesto.numero_completo})'

    if forma_pago == 'dividido':
        # Parsear y validar pago dividido
        try:
            pagos_data = json.loads(pago_dividido_json or '[]')
        except (json.JSONDecodeError, TypeError):
            raise ValueError('Datos de pago dividido invalidos.')

        if len(pagos_data) != 2:
            raise ValueError('El pago dividido requiere exactamente 2 formas de pago.')

        if pagos_data[0]['forma_pago'] == pagos_data[1]['forma_pago']:
            raise ValueError('Las formas de pago deben ser distintas.')

        monto1 = Decimal(str(pagos_data[0]['monto']))
        monto2 = Decimal(str(pagos_data[1]['monto']))

        if monto1 <= 0 or monto2 <= 0:
            raise ValueError('Cada monto debe ser mayor a 0.')

        if abs((monto1 + monto2) - venta.total) > Decimal('0.01'):
            raise ValueError('Los montos no coinciden con el total de la venta.')

        # Validar CC si alguno es cuenta_corriente
        for pago_data in pagos_data:
            if pago_data['forma_pago'] == 'cuenta_corriente':
                cliente = presupuesto.cliente
                if not cliente:
                    raise ValueError('Se requiere un cliente registrado para cuenta corriente.')
                monto_cc = Decimal(str(pago_data['monto']))
                if not cliente.puede_comprar_a_credito(monto_cc):
                    raise ValueError(
                        f'El monto de cuenta corriente (${monto_cc:.2f}) '
                        f'excede el limite disponible '
                        f'(${cliente.credito_disponible:.2f}).'
                    )

        # Crear VentaPago y movimientos por cada pago
        for pago_data in pagos_data:
            fp = pago_data['forma_pago']
            monto = Decimal(str(pago_data['monto']))

            venta_pago = VentaPago(
                venta_id=venta.id,
                forma_pago=fp,
                monto=monto,
            )
            db.session.add(venta_pago)

            if fp == 'cuenta_corriente':
                cliente = presupuesto.cliente
                saldo_anterior, saldo_posterior = cliente.actualizar_saldo(monto, 'cargo')
                movimiento_cc = MovimientoCuentaCorriente(
                    cliente_id=cliente.id,
                    tipo='cargo',
                    monto=monto,
                    saldo_anterior=saldo_anterior,
                    saldo_posterior=saldo_posterior,
                    referencia_tipo='venta',
                    referencia_id=venta.id,
                    descripcion=f'{desc_base} (pago parcial)',
                    usuario_id=usuario_id,
                    empresa_id=empresa_id,
                )
                db.session.add(movimiento_cc)
            else:
                movimiento_caja = MovimientoCaja(
                    caja_id=caja_id,
                    tipo='ingreso',
                    concepto='venta',
                    descripcion=f'{desc_base} (pago parcial)',
                    monto=monto,
                    forma_pago=fp,
                    referencia_tipo='venta',
                    referencia_id=venta.id,
                    usuario_id=usuario_id,
                )
                db.session.add(movimiento_caja)

    elif forma_pago == 'cuenta_corriente':
        cliente = presupuesto.cliente
        saldo_anterior, saldo_posterior = cliente.actualizar_saldo(venta.total, 'cargo')

        movimiento_cc = MovimientoCuentaCorriente(
            cliente_id=cliente.id,
            tipo='cargo',
            monto=venta.total,
            saldo_anterior=saldo_anterior,
            saldo_posterior=saldo_posterior,
            referencia_tipo='venta',
            referencia_id=venta.id,
            descripcion=desc_base,
            usuario_id=usuario_id,
            empresa_id=empresa_id,
        )
        db.session.add(movimiento_cc)

        # VentaPago para uniformidad en queries
        venta_pago = VentaPago(
            venta_id=venta.id,
            forma_pago=forma_pago,
            monto=venta.total,
        )
        db.session.add(venta_pago)
    else:
        movimiento_caja = MovimientoCaja(
            caja_id=caja_id,
            tipo='ingreso',
            concepto='venta',
            descripcion=desc_base,
            monto=venta.total,
            forma_pago=forma_pago,
            referencia_tipo='venta',
            referencia_id=venta.id,
            usuario_id=usuario_id,
        )
        db.session.add(movimiento_caja)

        # VentaPago para uniformidad en queries
        venta_pago = VentaPago(
            venta_id=venta.id,
            forma_pago=forma_pago,
            monto=venta.total,
        )
        db.session.add(venta_pago)

    # Marcar presupuesto como convertido
    presupuesto.estado = 'convertido'

    db.session.commit()
    return venta


def marcar_vencidos():
    """Marca como vencidos los presupuestos pendientes cuya fecha de vencimiento pasó."""
    ahora = ahora_argentina()
    vencidos = Presupuesto.query.filter(
        Presupuesto.estado == 'pendiente', Presupuesto.fecha_vencimiento < ahora
    ).all()

    for p in vencidos:
        p.estado = 'vencido'

    if vencidos:
        db.session.commit()

    return len(vencidos)


def generar_pdf(presupuesto):
    """Genera el PDF del presupuesto usando WeasyPrint."""
    from weasyprint import HTML

    from .pdf_utils import obtener_config_negocio

    detalles = list(presupuesto.detalles)

    config_negocio = obtener_config_negocio(
        texto_pie=Configuracion.get('presupuesto_texto_pie', ''),
        iva_porcentaje=Configuracion.get('iva_porcentaje', 21),
        precios_con_iva=Configuracion.get('precios_con_iva', True),
    )

    html_string = render_template(
        'presupuestos/pdf/presupuesto.html',
        presupuesto=presupuesto,
        detalles=detalles,
        config_negocio=config_negocio,
    )

    pdf = HTML(string=html_string).write_pdf()
    return pdf


def generar_url_whatsapp(presupuesto, base_url, telefono=None):
    """Genera la URL para compartir por WhatsApp."""
    tel = telefono or presupuesto.telefono_cliente_display
    tel = tel.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
    if tel and not tel.startswith('+'):
        tel = '54' + tel.lstrip('0')

    nombre_negocio = Configuracion.get('nombre_negocio', 'FerrERP')
    url_pdf = f'{base_url}/presupuestos/p/{presupuesto.token}'

    mensaje = (
        f'Hola! Te envío el presupuesto #{presupuesto.numero_completo} '
        f'de {nombre_negocio}.\n'
        f'Total: ${presupuesto.total:,.2f}\n'
        f'Válido hasta: {presupuesto.fecha_vencimiento.strftime("%d/%m/%Y")}\n\n'
        f'Podés ver el detalle en: {url_pdf}\n\n'
        f'Cualquier consulta estamos a disposición!'
    )

    mensaje_encoded = quote(mensaje)

    if tel:
        return f'https://wa.me/{tel}?text={mensaje_encoded}'
    return f'https://wa.me/?text={mensaje_encoded}'
