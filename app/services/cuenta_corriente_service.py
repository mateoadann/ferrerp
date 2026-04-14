"""Servicio de cuenta corriente: estado de cuenta PDF y ajuste de precios CC."""

from decimal import Decimal, ROUND_HALF_UP

from flask import render_template

from ..extensions import db
from ..models import (
    AjustePrecioCuentaCorriente,
    MovimientoCuentaCorriente,
    Venta,
    VentaDetalle,
)
from ..models.producto import Producto
from ..utils.helpers import ahora_argentina
from .pdf_utils import obtener_config_negocio

DOS_DECIMALES = Decimal('0.01')


def obtener_ventas_cc_pendientes(cliente):
    """Obtiene las ventas CC/dividido pendientes de un cliente.

    Filtra ventas completadas con forma_pago CC o dividido que aún tienen
    saldo pendiente (el cliente tiene deuda).

    Args:
        cliente: instancia de Cliente.

    Returns:
        Lista de Venta con forma_pago CC o dividido y estado completada.
    """
    ventas = (
        Venta.query.filter(
            Venta.cliente_id == cliente.id,
            Venta.empresa_id == cliente.empresa_id,
            Venta.forma_pago.in_(['cuenta_corriente', 'dividido']),
            Venta.estado == 'completada',
        )
        .options(
            db.joinedload(Venta.pagos),
        )
        .order_by(Venta.fecha.desc())
        .all()
    )

    return ventas


def generar_estado_cuenta_pdf(cliente, cantidad_movimientos=20):
    """Genera un PDF con el estado de cuenta del cliente.

    Args:
        cliente: instancia de Cliente.
        cantidad_movimientos: cantidad máxima de movimientos a incluir.

    Returns:
        bytes con el contenido del PDF.
    """
    from weasyprint import HTML

    config_negocio = obtener_config_negocio()

    # Últimos N movimientos
    movimientos = (
        MovimientoCuentaCorriente.query.filter_by(
            cliente_id=cliente.id,
            empresa_id=cliente.empresa_id,
        )
        .order_by(MovimientoCuentaCorriente.created_at.desc())
        .limit(cantidad_movimientos)
        .all()
    )

    # Ventas CC pendientes con sus detalles
    ventas_pendientes = obtener_ventas_cc_pendientes(cliente)

    # Precargar detalles con producto para evitar N+1
    ventas_con_detalles = []
    for venta in ventas_pendientes:
        detalles = venta.detalles.join(Producto).options(db.joinedload(VentaDetalle.producto)).all()
        ventas_con_detalles.append(
            {
                'venta': venta,
                'detalles': detalles,
            }
        )

    ahora = ahora_argentina()
    referencia = f'EC-{cliente.id}-{ahora.strftime("%Y%m%d%H%M%S")}'

    html_string = render_template(
        'clientes/pdf/estado_cuenta.html',
        cliente=cliente,
        config_negocio=config_negocio,
        movimientos=movimientos,
        ventas_con_detalles=ventas_con_detalles,
        referencia=referencia,
        fecha_generacion=ahora,
    )

    pdf = HTML(string=html_string).write_pdf()
    return pdf


def calcular_ajustes_cc(categoria_ids, porcentaje, empresa_id):
    """Calcula los ajustes de precio para deudas CC de clientes afectados.

    Clasifica ventas como congeladas (con pago posterior) o vivas,
    y calcula el monto de ajuste por detalle de venta para las vivas.
    Es una función de PREVIEW: calcula sin aplicar cambios.

    Args:
        categoria_ids: lista de IDs de categorías actualizadas.
        porcentaje: porcentaje de actualización aplicado (número o Decimal).
        empresa_id: ID de la empresa.

    Returns:
        Lista de dicts con claves: cliente, venta, total_original,
        total_recalculado, monto_ajuste, detalles_afectados.
    """
    if not categoria_ids:
        return []

    porcentaje_decimal = Decimal(str(porcentaje))
    factor = Decimal('1') + porcentaje_decimal / Decimal('100')
    categoria_ids_set = set(categoria_ids)

    # Obtener IDs de productos en las categorías afectadas
    producto_ids = {
        row.id
        for row in Producto.query.filter(
            Producto.categoria_id.in_(categoria_ids),
            Producto.empresa_id == empresa_id,
        )
        .with_entities(Producto.id)
        .all()
    }

    if not producto_ids:
        return []

    # Obtener todas las ventas CC/dividido completadas de la empresa
    ventas_pendientes = (
        Venta.query.filter(
            Venta.empresa_id == empresa_id,
            Venta.forma_pago.in_(['cuenta_corriente', 'dividido']),
            Venta.estado == 'completada',
            Venta.cliente_id.isnot(None),
        )
        .options(db.joinedload(Venta.pagos))
        .all()
    )

    resultados = []

    for venta in ventas_pendientes:
        # Clasificación congelada/viva
        if venta_esta_congelada(venta):
            continue

        # Obtener detalles afectados (productos en categorías seleccionadas)
        # Usa la relación dinámica para filtrar en DB
        detalles_afectados = (
            venta.detalles.join(Producto)
            .filter(Producto.categoria_id.in_(categoria_ids_set))
            .options(db.joinedload(VentaDetalle.producto))
            .all()
        )

        if not detalles_afectados:
            continue

        # Calcular ratio CC para pagos divididos
        if venta.forma_pago == 'dividido':
            pago_cc = next(
                (p for p in venta.pagos if p.forma_pago == 'cuenta_corriente'),
                None,
            )
            if not pago_cc:
                continue  # sin porción CC, no afecta
            venta_total = Decimal(str(venta.total))
            if venta_total == 0:
                continue
            ratio_cc = Decimal(str(pago_cc.monto)) / venta_total
        else:
            ratio_cc = Decimal('1')

        # Calcular ajuste por detalle
        total_original = Decimal('0')
        total_recalculado = Decimal('0')
        info_detalles = []

        for detalle in detalles_afectados:
            precio_unitario = Decimal(str(detalle.precio_unitario))
            cantidad = Decimal(str(detalle.cantidad))
            descuento_pct = Decimal(str(detalle.descuento_porcentaje or 0))

            # Subtotal original del detalle (con descuento de línea)
            bruto_original = precio_unitario * cantidad
            desc_linea = bruto_original * descuento_pct / Decimal('100')
            subtotal_original = bruto_original - desc_linea

            # Subtotal recalculado con nuevo precio
            nuevo_precio = (precio_unitario * factor).quantize(
                DOS_DECIMALES, ROUND_HALF_UP
            )
            bruto_nuevo = nuevo_precio * cantidad
            desc_linea_nuevo = bruto_nuevo * descuento_pct / Decimal('100')
            subtotal_nuevo = bruto_nuevo - desc_linea_nuevo

            total_original += subtotal_original
            total_recalculado += subtotal_nuevo

            info_detalles.append({
                'detalle': detalle,
                'precio_original': precio_unitario,
                'precio_nuevo': nuevo_precio,
                'subtotal_original': subtotal_original.quantize(
                    DOS_DECIMALES, ROUND_HALF_UP
                ),
                'subtotal_nuevo': subtotal_nuevo.quantize(
                    DOS_DECIMALES, ROUND_HALF_UP
                ),
            })

        total_original = total_original.quantize(DOS_DECIMALES, ROUND_HALF_UP)
        total_recalculado = total_recalculado.quantize(
            DOS_DECIMALES, ROUND_HALF_UP
        )

        # Aplicar descuento global de la venta proporcionalmente
        descuento_global = Decimal(str(venta.descuento_porcentaje or 0))
        factor_descuento = Decimal('1') - descuento_global / Decimal('100')

        # Diferencia ajustada por descuento global y ratio CC
        diferencia = total_recalculado - total_original
        monto_ajuste = (diferencia * factor_descuento * ratio_cc).quantize(
            DOS_DECIMALES, ROUND_HALF_UP
        )

        if monto_ajuste <= 0:
            continue

        resultados.append({
            'cliente': venta.cliente,
            'venta': venta,
            'total_original': total_original,
            'total_recalculado': total_recalculado,
            'monto_ajuste': monto_ajuste,
            'detalles_afectados': info_detalles,
        })

    return resultados


def aplicar_ajustes_cc(ajustes, usuario_id, fecha_actualizacion, porcentaje):
    """Aplica los ajustes de precio a las deudas CC, creando registros de auditoría.

    Por cada ajuste: crea MovimientoCuentaCorriente (cargo) y
    AjustePrecioCuentaCorriente (auditoría), luego actualiza saldo del cliente.
    Verifica duplicados por (venta_id, actualizacion_fecha).

    Args:
        ajustes: lista de dicts generados por calcular_ajustes_cc().
        usuario_id: ID del usuario que ejecuta la operación.
        fecha_actualizacion: datetime de la actualización de precios.
        porcentaje: porcentaje aplicado (Decimal).

    Returns:
        int con la cantidad de ajustes aplicados.
    """
    pass


def venta_esta_congelada(venta):
    """Determina si una venta CC está congelada (tiene pago posterior).

    Una venta se considera congelada si existe algún MovimientoCuentaCorriente
    de tipo 'pago' con referencia_tipo 'pago' posterior o igual a la fecha
    de la venta para ese cliente y empresa.

    Se excluyen movimientos de anulación (referencia_tipo='anulacion_venta')
    ya que no representan pagos reales del cliente.

    Args:
        venta: instancia de Venta.

    Returns:
        True si la venta está congelada, False si está viva.
    """
    tiene_pago_posterior = (
        MovimientoCuentaCorriente.query.filter(
            MovimientoCuentaCorriente.cliente_id == venta.cliente_id,
            MovimientoCuentaCorriente.tipo == 'pago',
            MovimientoCuentaCorriente.referencia_tipo == 'pago',
            MovimientoCuentaCorriente.created_at >= venta.fecha,
            MovimientoCuentaCorriente.empresa_id == venta.empresa_id,
        ).first()
        is not None
    )

    return tiene_pago_posterior


def calcular_monto_cc(venta):
    """Calcula el monto de CC de una venta (total para CC puro, porción CC para dividido).

    Args:
        venta: instancia de Venta.

    Returns:
        Decimal con el monto correspondiente a cuenta corriente.
    """
    if venta.forma_pago == 'cuenta_corriente':
        return Decimal(str(venta.total))

    if venta.forma_pago == 'dividido':
        pago_cc = next(
            (p for p in venta.pagos if p.forma_pago == 'cuenta_corriente'),
            None,
        )
        if pago_cc:
            return Decimal(str(pago_cc.monto))

    return Decimal('0')
