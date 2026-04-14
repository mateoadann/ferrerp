"""Servicio de cuenta corriente: estado de cuenta PDF y ajuste de precios CC."""

from decimal import Decimal


def generar_estado_cuenta_pdf(cliente, cantidad_movimientos=20):
    """Genera un PDF con el estado de cuenta del cliente.

    Args:
        cliente: instancia de Cliente.
        cantidad_movimientos: cantidad máxima de movimientos a incluir.

    Returns:
        bytes con el contenido del PDF.
    """
    pass


def obtener_ventas_cc_pendientes(cliente):
    """Obtiene las ventas CC/dividido pendientes de un cliente.

    Args:
        cliente: instancia de Cliente.

    Returns:
        Lista de Venta con forma_pago CC o dividido y estado completada.
    """
    return []


def calcular_ajustes_cc(categoria_ids, porcentaje, empresa_id):
    """Calcula los ajustes de precio para deudas CC de clientes afectados.

    Clasifica ventas como congeladas (con pago posterior) o vivas,
    y calcula el monto de ajuste por detalle de venta para las vivas.

    Args:
        categoria_ids: lista de IDs de categorías actualizadas.
        porcentaje: porcentaje de actualización aplicado (Decimal).
        empresa_id: ID de la empresa.

    Returns:
        Lista de dicts con claves: cliente, venta, total_original,
        total_recalculado, monto_ajuste (todos Decimal).
    """
    return []


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
    de tipo 'pago' posterior o igual a la fecha de la venta para ese cliente.

    Args:
        venta: instancia de Venta.

    Returns:
        True si la venta está congelada, False si está viva.
    """
    return False


def calcular_monto_cc(venta):
    """Calcula el monto de CC de una venta (total para CC puro, porción CC para dividido).

    Args:
        venta: instancia de Venta.

    Returns:
        Decimal con el monto correspondiente a cuenta corriente.
    """
    return Decimal('0')
