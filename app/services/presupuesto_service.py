"""Servicio de presupuestos."""

import io
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import quote

from flask import render_template, url_for

from ..extensions import db
from ..models import (
    Presupuesto, PresupuestoDetalle, Producto, Venta, VentaDetalle,
    Caja, MovimientoCaja, MovimientoStock, Cliente,
    MovimientoCuentaCorriente, Configuracion
)
from ..utils.helpers import generar_numero_presupuesto, generar_numero_venta


def crear_presupuesto(items, usuario_id, cliente_id=None, cliente_nombre=None,
                      cliente_telefono=None, descuento_porcentaje=0,
                      validez_dias=None, notas=None):
    """Crea un nuevo presupuesto con sus líneas de detalle."""
    if validez_dias is None:
        validez_dias = Configuracion.get('presupuesto_validez_dias', 15)

    fecha = datetime.utcnow()
    fecha_vencimiento = fecha + timedelta(days=int(validez_dias))

    presupuesto = Presupuesto(
        numero=generar_numero_presupuesto(),
        fecha=fecha,
        fecha_vencimiento=fecha_vencimiento,
        cliente_id=cliente_id if cliente_id else None,
        cliente_nombre=cliente_nombre,
        cliente_telefono=cliente_telefono,
        usuario_id=usuario_id,
        descuento_porcentaje=Decimal(str(descuento_porcentaje)),
        notas=notas
    )

    subtotal = Decimal('0')

    for item in items:
        producto = db.session.get(Producto, item['producto_id'])
        if not producto:
            raise ValueError(f'Producto no encontrado: {item["producto_id"]}')

        cantidad = Decimal(str(item['cantidad']))
        precio = Decimal(str(item['precio_unitario']))
        item_subtotal = cantidad * precio
        subtotal += item_subtotal

        detalle = PresupuestoDetalle(
            producto_id=producto.id,
            cantidad=cantidad,
            precio_unitario=precio,
            subtotal=item_subtotal
        )
        presupuesto.detalles.append(detalle)

    presupuesto.subtotal = subtotal
    if presupuesto.descuento_porcentaje > 0:
        presupuesto.descuento_monto = subtotal * (presupuesto.descuento_porcentaje / 100)
    else:
        presupuesto.descuento_monto = Decimal('0')
    presupuesto.total = subtotal - presupuesto.descuento_monto

    db.session.add(presupuesto)
    db.session.commit()

    return presupuesto


def actualizar_presupuesto(presupuesto, items, cliente_id=None, cliente_nombre=None,
                           cliente_telefono=None, descuento_porcentaje=0,
                           validez_dias=None, notas=None):
    """Actualiza un presupuesto pendiente."""
    if not presupuesto.puede_editar:
        raise ValueError('El presupuesto no puede editarse en su estado actual.')

    if validez_dias is not None:
        presupuesto.fecha_vencimiento = presupuesto.fecha + timedelta(days=int(validez_dias))

    presupuesto.cliente_id = cliente_id if cliente_id else None
    presupuesto.cliente_nombre = cliente_nombre
    presupuesto.cliente_telefono = cliente_telefono
    presupuesto.descuento_porcentaje = Decimal(str(descuento_porcentaje))
    presupuesto.notas = notas

    # Eliminar detalles existentes
    PresupuestoDetalle.query.filter_by(presupuesto_id=presupuesto.id).delete()

    subtotal = Decimal('0')

    for item in items:
        producto = db.session.get(Producto, item['producto_id'])
        if not producto:
            raise ValueError(f'Producto no encontrado: {item["producto_id"]}')

        cantidad = Decimal(str(item['cantidad']))
        precio = Decimal(str(item['precio_unitario']))
        item_subtotal = cantidad * precio
        subtotal += item_subtotal

        detalle = PresupuestoDetalle(
            presupuesto_id=presupuesto.id,
            producto_id=producto.id,
            cantidad=cantidad,
            precio_unitario=precio,
            subtotal=item_subtotal
        )
        db.session.add(detalle)

    presupuesto.subtotal = subtotal
    if presupuesto.descuento_porcentaje > 0:
        presupuesto.descuento_monto = subtotal * (presupuesto.descuento_porcentaje / 100)
    else:
        presupuesto.descuento_monto = Decimal('0')
    presupuesto.total = subtotal - presupuesto.descuento_monto

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
            f'No se puede cambiar de "{presupuesto.estado_display}" '
            f'a "{nuevo_estado}".'
        )

    presupuesto.estado = nuevo_estado
    db.session.commit()
    return presupuesto


def convertir_a_venta(presupuesto, usuario_id, forma_pago, caja_id):
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
        numero=generar_numero_venta(),
        fecha=datetime.utcnow(),
        cliente_id=presupuesto.cliente_id,
        usuario_id=usuario_id,
        descuento_porcentaje=presupuesto.descuento_porcentaje,
        forma_pago=forma_pago,
        estado='completada',
        caja_id=caja_id,
        presupuesto_id=presupuesto.id
    )

    subtotal = Decimal('0')

    for detalle in detalles:
        producto = detalle.producto
        cantidad = detalle.cantidad
        precio = detalle.precio_unitario
        item_subtotal = cantidad * precio
        subtotal += item_subtotal

        # Detalle de venta
        venta_detalle = VentaDetalle(
            producto_id=producto.id,
            cantidad=cantidad,
            precio_unitario=precio,
            subtotal=item_subtotal
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
            usuario_id=usuario_id
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
        mov = MovimientoStock.query.filter_by(
            producto_id=venta_det.producto_id,
            referencia_tipo='venta',
            referencia_id=None
        ).order_by(MovimientoStock.id.desc()).first()
        if mov:
            mov.referencia_id = venta.id

    # Movimiento de caja o cuenta corriente
    if forma_pago == 'cuenta_corriente':
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
            descripcion=f'Venta #{venta.numero_completo} (Presup. #{presupuesto.numero_completo})',
            usuario_id=usuario_id
        )
        db.session.add(movimiento_cc)
    else:
        movimiento_caja = MovimientoCaja(
            caja_id=caja_id,
            tipo='ingreso',
            concepto='venta',
            descripcion=f'Venta #{venta.numero_completo} (Presup. #{presupuesto.numero_completo})',
            monto=venta.total,
            forma_pago=forma_pago,
            referencia_tipo='venta',
            referencia_id=venta.id,
            usuario_id=usuario_id
        )
        db.session.add(movimiento_caja)

    # Marcar presupuesto como convertido
    presupuesto.estado = 'convertido'

    db.session.commit()
    return venta


def marcar_vencidos():
    """Marca como vencidos los presupuestos pendientes cuya fecha de vencimiento pasó."""
    ahora = datetime.utcnow()
    vencidos = Presupuesto.query.filter(
        Presupuesto.estado == 'pendiente',
        Presupuesto.fecha_vencimiento < ahora
    ).all()

    for p in vencidos:
        p.estado = 'vencido'

    if vencidos:
        db.session.commit()

    return len(vencidos)


def generar_pdf(presupuesto):
    """Genera el PDF del presupuesto usando WeasyPrint."""
    from weasyprint import HTML

    detalles = list(presupuesto.detalles)

    config_negocio = {
        'nombre': Configuracion.get('nombre_negocio', 'FerrERP'),
        'cuit': Configuracion.get('cuit', ''),
        'direccion': Configuracion.get('direccion', ''),
        'telefono': Configuracion.get('telefono', ''),
        'email': Configuracion.get('email', ''),
        'texto_pie': Configuracion.get('presupuesto_texto_pie', ''),
        'iva_porcentaje': Configuracion.get('iva_porcentaje', 21),
        'precios_con_iva': Configuracion.get('precios_con_iva', True),
    }

    html_string = render_template(
        'presupuestos/pdf/presupuesto.html',
        presupuesto=presupuesto,
        detalles=detalles,
        config_negocio=config_negocio
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
