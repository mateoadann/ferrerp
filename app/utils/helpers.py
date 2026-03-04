"""Funciones auxiliares de la aplicación."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import flash

ZONA_ARGENTINA = ZoneInfo('America/Argentina/Buenos_Aires')


def ahora_argentina():
    """Retorna la fecha/hora actual en zona horaria Argentina (UTC-3).

    Se retorna naive (sin tzinfo) para compatibilidad con las columnas
    DateTime del esquema actual, que no usan timezone=True.
    """
    return (
        datetime.now(timezone.utc)
        .astimezone(ZONA_ARGENTINA)
        .replace(tzinfo=None)
    )


def flash_errors(form):
    """
    Flash all errors from a form.

    Args:
        form: Flask-WTF form instance
    """
    for field, errors in form.errors.items():
        for error in errors:
            field_label = getattr(form, field).label.text if hasattr(form, field) else field
            flash(f'{field_label}: {error}', 'danger')


def generar_numero_venta(empresa_id=None):
    """
    Genera el siguiente número de venta para el año actual y empresa.

    Args:
        empresa_id: ID de la empresa (requerido para multi-tenancy)

    Returns:
        int: Siguiente número de venta
    """
    from ..models import Venta

    anio_actual = ahora_argentina().year
    inicio_anio = datetime(anio_actual, 1, 1)
    fin_anio = datetime(anio_actual, 12, 31, 23, 59, 59)

    query = Venta.query.filter(
        Venta.fecha >= inicio_anio,
        Venta.fecha <= fin_anio,
    )
    if empresa_id is not None and hasattr(Venta, 'empresa_id'):
        query = query.filter(Venta.empresa_id == empresa_id)

    ultima_venta = query.order_by(Venta.numero.desc()).first()

    if ultima_venta:
        return ultima_venta.numero + 1
    return 1


def generar_numero_presupuesto(empresa_id=None):
    """
    Genera el siguiente número de presupuesto para el año actual y empresa.

    Args:
        empresa_id: ID de la empresa (requerido para multi-tenancy)

    Returns:
        int: Siguiente número de presupuesto
    """
    from ..models import Presupuesto

    anio_actual = ahora_argentina().year
    inicio_anio = datetime(anio_actual, 1, 1)
    fin_anio = datetime(anio_actual, 12, 31, 23, 59, 59)

    query = Presupuesto.query.filter(
        Presupuesto.fecha >= inicio_anio,
        Presupuesto.fecha <= fin_anio,
    )
    if empresa_id is not None and hasattr(Presupuesto, 'empresa_id'):
        query = query.filter(Presupuesto.empresa_id == empresa_id)

    ultimo = query.order_by(Presupuesto.numero.desc()).first()

    if ultimo:
        return ultimo.numero + 1
    return 1


def generar_numero_orden_compra(empresa_id=None):
    """
    Genera el siguiente número de orden de compra para la empresa.

    Args:
        empresa_id: ID de la empresa (requerido para multi-tenancy)

    Returns:
        int: Siguiente número de orden
    """
    from ..models import OrdenCompra

    query = OrdenCompra.query
    if empresa_id is not None and hasattr(OrdenCompra, 'empresa_id'):
        query = query.filter(OrdenCompra.empresa_id == empresa_id)

    ultima_orden = query.order_by(OrdenCompra.numero.desc()).first()

    if ultima_orden:
        return ultima_orden.numero + 1
    return 1


def formatear_moneda(valor):
    """
    Formatea un valor como moneda.

    Args:
        valor: Valor numérico

    Returns:
        str: Valor formateado como moneda
    """
    if valor is None:
        return '$0.00'
    return f'${valor:,.2f}'


def formatear_fecha(fecha, formato='%d/%m/%Y'):
    """
    Formatea una fecha.

    Args:
        fecha: Objeto datetime
        formato: Formato de salida

    Returns:
        str: Fecha formateada
    """
    if fecha is None:
        return ''
    return fecha.strftime(formato)


def formatear_datetime(fecha, formato='%d/%m/%Y %H:%M'):
    """
    Formatea fecha y hora.

    Args:
        fecha: Objeto datetime
        formato: Formato de salida

    Returns:
        str: Fecha y hora formateadas
    """
    if fecha is None:
        return ''
    return fecha.strftime(formato)


def paginar_query(query, page, per_page=20):
    """
    Pagina una consulta SQLAlchemy.

    Args:
        query: Consulta SQLAlchemy
        page: Número de página
        per_page: Items por página

    Returns:
        Pagination object
    """
    return query.paginate(page=page, per_page=per_page, error_out=False)


def es_peticion_htmx():
    """
    Verifica si la petición actual es de HTMX.

    Returns:
        bool: True si es una petición HTMX
    """
    from flask import request
    return request.headers.get('HX-Request') == 'true'


def respuesta_htmx_redirect(url):
    """
    Crea una respuesta de redirección para HTMX.

    Args:
        url: URL de destino

    Returns:
        Response con header HX-Redirect
    """
    from flask import make_response
    response = make_response()
    response.headers['HX-Redirect'] = url
    return response
