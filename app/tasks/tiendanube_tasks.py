"""Tareas RQ para sincronización con Tienda Nube.

Wrappers que encolan las funciones del servicio TN como jobs de background
usando RQ.  Si Redis no está disponible, ejecutan la operación de forma
sincrónica como fallback para no bloquear la funcionalidad.
"""

import logging

from flask import current_app

from ..services.tiendanube_service import (
    sincronizar_precio,
    sincronizar_producto_completo,
    sincronizar_stock,
    sincronizar_stock_masivo,
    vincular_producto,
)

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Helper interno
# -------------------------------------------------------------------


def _obtener_queue(nombre='sync'):
    """Obtiene la cola RQ solicitada desde las extensiones de la app.

    Args:
        nombre: Nombre de la cola ('sync', 'default', 'webhooks').

    Returns:
        Queue de RQ o None si Redis no está disponible.
    """
    return current_app.extensions.get('redis', {}).get('queues', {}).get(nombre)


# -------------------------------------------------------------------
# Tareas de encolado
# -------------------------------------------------------------------


def encolar_sync_stock(producto_id, empresa_id):
    """Encola la sincronización de stock de un producto hacia Tienda Nube.

    Si Redis está disponible, encola el job en la cola 'sync'.
    Si no, ejecuta la sincronización de forma sincrónica como fallback.

    Args:
        producto_id: ID del producto local.
        empresa_id: ID de la empresa.

    Returns:
        Job de RQ o None si se ejecutó sincrónicamente.
    """
    queue = _obtener_queue('sync')

    if queue:
        logger.info(
            'Encolando sync de stock — producto=%s empresa=%s',
            producto_id,
            empresa_id,
        )
        return queue.enqueue(sincronizar_stock, producto_id, empresa_id)

    logger.warning(
        'Redis no disponible — ejecutando sync de stock sincrónicamente '
        'para producto=%s empresa=%s',
        producto_id,
        empresa_id,
    )
    try:
        sincronizar_stock(producto_id, empresa_id)
    except Exception:
        logger.exception(
            'Error en sync sincrónico de stock — producto=%s empresa=%s',
            producto_id,
            empresa_id,
        )
    return None


def encolar_sync_precio(producto_id, empresa_id):
    """Encola la sincronización de precio de un producto hacia Tienda Nube.

    Si Redis está disponible, encola el job en la cola 'sync'.
    Si no, ejecuta la sincronización de forma sincrónica como fallback.

    Args:
        producto_id: ID del producto local.
        empresa_id: ID de la empresa.

    Returns:
        Job de RQ o None si se ejecutó sincrónicamente.
    """
    queue = _obtener_queue('sync')

    if queue:
        logger.info(
            'Encolando sync de precio — producto=%s empresa=%s',
            producto_id,
            empresa_id,
        )
        return queue.enqueue(sincronizar_precio, producto_id, empresa_id)

    logger.warning(
        'Redis no disponible — ejecutando sync de precio sincrónicamente '
        'para producto=%s empresa=%s',
        producto_id,
        empresa_id,
    )
    try:
        sincronizar_precio(producto_id, empresa_id)
    except Exception:
        logger.exception(
            'Error en sync sincrónico de precio — producto=%s empresa=%s',
            producto_id,
            empresa_id,
        )
    return None


def encolar_sync_completo(producto_id, empresa_id):
    """Encola la sincronización completa (stock + precio) hacia Tienda Nube.

    Si Redis está disponible, encola el job en la cola 'sync'.
    Si no, ejecuta la sincronización de forma sincrónica como fallback.

    Args:
        producto_id: ID del producto local.
        empresa_id: ID de la empresa.

    Returns:
        Job de RQ o None si se ejecutó sincrónicamente.
    """
    queue = _obtener_queue('sync')

    if queue:
        logger.info(
            'Encolando sync completo — producto=%s empresa=%s',
            producto_id,
            empresa_id,
        )
        return queue.enqueue(
            sincronizar_producto_completo,
            producto_id,
            empresa_id,
        )

    logger.warning(
        'Redis no disponible — ejecutando sync completo sincrónicamente '
        'para producto=%s empresa=%s',
        producto_id,
        empresa_id,
    )
    try:
        sincronizar_producto_completo(producto_id, empresa_id)
    except Exception:
        logger.exception(
            'Error en sync sincrónico completo — producto=%s empresa=%s',
            producto_id,
            empresa_id,
        )
    return None


def encolar_sync_masivo(empresa_id):
    """Encola la sincronización masiva de stock para toda la empresa.

    Si Redis está disponible, encola el job en la cola 'sync' con un
    timeout extendido de 600 segundos (las syncs masivas pueden tardar).
    Si no, ejecuta la sincronización de forma sincrónica como fallback.

    Args:
        empresa_id: ID de la empresa.

    Returns:
        Job de RQ o None si se ejecutó sincrónicamente.
    """
    queue = _obtener_queue('sync')

    if queue:
        logger.info(
            'Encolando sync masivo de stock — empresa=%s',
            empresa_id,
        )
        return queue.enqueue(
            sincronizar_stock_masivo,
            empresa_id,
            job_timeout=600,
        )

    logger.warning(
        'Redis no disponible — ejecutando sync masivo sincrónicamente ' 'para empresa=%s',
        empresa_id,
    )
    try:
        sincronizar_stock_masivo(empresa_id)
    except Exception:
        logger.exception(
            'Error en sync sincrónico masivo — empresa=%s',
            empresa_id,
        )
    return None


def encolar_vincular_producto(producto_id, empresa_id):
    """Encola la vinculación de un producto local con Tienda Nube.

    Si Redis está disponible, encola el job en la cola 'sync'.
    Si no, ejecuta la vinculación de forma sincrónica como fallback.

    Args:
        producto_id: ID del producto local.
        empresa_id: ID de la empresa.

    Returns:
        Job de RQ o None si se ejecutó sincrónicamente.
    """
    queue = _obtener_queue('sync')

    if queue:
        logger.info(
            'Encolando vinculación de producto — producto=%s empresa=%s',
            producto_id,
            empresa_id,
        )
        return queue.enqueue(vincular_producto, producto_id, empresa_id)

    logger.warning(
        'Redis no disponible — ejecutando vinculación sincrónicamente '
        'para producto=%s empresa=%s',
        producto_id,
        empresa_id,
    )
    try:
        vincular_producto(producto_id, empresa_id)
    except Exception:
        logger.exception(
            'Error en vinculación sincrónica — producto=%s empresa=%s',
            producto_id,
            empresa_id,
        )
    return None
