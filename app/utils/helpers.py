"""Funciones auxiliares de la aplicación."""

from datetime import datetime
from flask import flash


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


def generar_numero_venta():
    """
    Genera el siguiente número de venta para el año actual.

    Returns:
        int: Siguiente número de venta
    """
    from ..models import Venta
    from ..extensions import db

    anio_actual = datetime.utcnow().year
    inicio_anio = datetime(anio_actual, 1, 1)
    fin_anio = datetime(anio_actual, 12, 31, 23, 59, 59)

    # Obtener el último número de venta del año
    ultima_venta = Venta.query.filter(
        Venta.fecha >= inicio_anio,
        Venta.fecha <= fin_anio
    ).order_by(Venta.numero.desc()).first()

    if ultima_venta:
        return ultima_venta.numero + 1
    return 1


def generar_numero_presupuesto():
    """
    Genera el siguiente número de presupuesto para el año actual.

    Returns:
        int: Siguiente número de presupuesto
    """
    from ..models import Presupuesto

    anio_actual = datetime.utcnow().year
    inicio_anio = datetime(anio_actual, 1, 1)
    fin_anio = datetime(anio_actual, 12, 31, 23, 59, 59)

    ultimo = Presupuesto.query.filter(
        Presupuesto.fecha >= inicio_anio,
        Presupuesto.fecha <= fin_anio
    ).order_by(Presupuesto.numero.desc()).first()

    if ultimo:
        return ultimo.numero + 1
    return 1


def generar_numero_orden_compra():
    """
    Genera el siguiente número de orden de compra.

    Returns:
        int: Siguiente número de orden
    """
    from ..models import OrdenCompra

    ultima_orden = OrdenCompra.query.order_by(OrdenCompra.numero.desc()).first()

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
