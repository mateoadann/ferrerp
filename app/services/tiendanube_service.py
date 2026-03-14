"""Servicio de integración con Tienda Nube.

Contiene la lógica de negocio para vincular productos locales con Tienda Nube,
sincronizar stock y precios, y administrar los mapeos producto-a-producto.
"""

import json
import logging

from ..extensions import db
from ..models import Producto, ProductoTiendaNube, SyncLog, TiendaNubeCredencial
from .tiendanube_client import TiendaNubeAPIError, TiendaNubeClient

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Helpers internos
# -------------------------------------------------------------------


def obtener_cliente_tn(empresa_id):
    """Obtiene un cliente HTTP autenticado para la tienda de la empresa.

    Carga las credenciales activas de la empresa y devuelve una instancia
    de TiendaNubeClient lista para operar.

    Args:
        empresa_id: ID de la empresa.

    Returns:
        TiendaNubeClient configurado.

    Raises:
        ValueError: Si la empresa no tiene credenciales activas.
    """
    cred = TiendaNubeCredencial.query.filter_by(
        empresa_id=empresa_id,
        activo=True,
    ).first()

    if not cred:
        raise ValueError(
            'La empresa no tiene credenciales activas de Tienda Nube. '
            'Configurá la integración primero.'
        )

    if not cred.access_token or not cred.tienda_id_externo:
        raise ValueError(
            'Las credenciales de Tienda Nube están incompletas. '
            'Reconectá la tienda desde la configuración.'
        )

    return TiendaNubeClient(
        store_id=cred.tienda_id_externo,
        access_token=cred.access_token,
        app_secret=cred.tn_app_secret,
    )


def _crear_sync_log(
    empresa_id,
    recurso,
    direccion,
    estado,
    mensaje=None,
    referencia_id_externo=None,
    payload=None,
    respuesta=None,
):
    """Crea un registro de sincronización en la base de datos.

    Helper interno que centraliza la creación de SyncLog para evitar
    repetición en cada función del servicio.
    """
    log = SyncLog(
        empresa_id=empresa_id,
        recurso=recurso,
        direccion=direccion,
        estado=estado,
        mensaje=mensaje,
        referencia_id_externo=referencia_id_externo,
        payload=json.dumps(payload, default=str) if payload else None,
        respuesta=json.dumps(respuesta, default=str) if respuesta else None,
    )
    db.session.add(log)
    return log


def _cargar_mapeo_activo(producto_id, empresa_id):
    """Carga el mapeo activo producto↔TN, o lanza ValueError si no existe."""
    mapeo = ProductoTiendaNube.query.filter_by(
        producto_id=producto_id,
        empresa_id=empresa_id,
        activo=True,
    ).first()

    if not mapeo:
        raise ValueError(f'El producto {producto_id} no está vinculado a Tienda Nube.')

    return mapeo


# -------------------------------------------------------------------
# Vinculación / desvinculación de productos
# -------------------------------------------------------------------


def vincular_producto(producto_id, empresa_id):
    """Crea un producto en Tienda Nube y lo vincula al producto local.

    Genera el payload con nombre, descripción, precio, stock y SKU del
    producto local, lo publica en la tienda de TN y persiste el mapeo.

    Args:
        producto_id: ID del producto local.
        empresa_id: ID de la empresa.

    Returns:
        ProductoTiendaNube con el mapeo creado.

    Raises:
        ValueError: Si el producto no existe, no pertenece a la empresa,
            está inactivo o ya está vinculado.
    """
    producto = db.session.get(Producto, producto_id)

    if not producto:
        raise ValueError(f'Producto {producto_id} no encontrado.')

    if producto.empresa_id != empresa_id:
        raise ValueError('El producto no pertenece a la empresa.')

    if not producto.activo:
        raise ValueError(
            f'El producto "{producto.nombre}" está inactivo. ' 'Activalo antes de vincularlo.'
        )

    # Verificar que no exista un mapeo activo
    mapeo_existente = ProductoTiendaNube.query.filter_by(
        producto_id=producto_id,
        empresa_id=empresa_id,
        activo=True,
    ).first()

    if mapeo_existente:
        raise ValueError(
            f'El producto "{producto.nombre}" ya está vinculado a Tienda Nube '
            f'(TN ID: {mapeo_existente.tn_producto_id}).'
        )

    client = obtener_cliente_tn(empresa_id)

    payload = {
        'name': {'es': producto.nombre},
        'description': {'es': producto.descripcion or ''},
        'variants': [
            {
                'price': str(producto.precio_venta),
                'stock': float(producto.stock_actual),
                'sku': producto.codigo,
            }
        ],
        'published': True,
    }

    try:
        respuesta_tn = client.crear_producto(payload)
    except TiendaNubeAPIError as e:
        _crear_sync_log(
            empresa_id=empresa_id,
            recurso='producto',
            direccion='exportacion',
            estado='error',
            mensaje=f'Error al crear producto en TN: {e}',
            referencia_id_externo=None,
            payload=payload,
            respuesta=e.response_body,
        )
        db.session.commit()
        raise ValueError(
            f'Error al publicar "{producto.nombre}" en Tienda Nube: {e.message}'
        ) from e

    # Extraer IDs de la respuesta de TN
    tn_producto_id = respuesta_tn['id']
    variantes = respuesta_tn.get('variants', [])
    tn_variante_id = variantes[0]['id'] if variantes else None

    # Crear mapeo local
    mapeo = ProductoTiendaNube(
        empresa_id=empresa_id,
        producto_id=producto_id,
        tn_producto_id=tn_producto_id,
        tn_variante_id=tn_variante_id,
    )
    mapeo.marcar_sincronizado()
    db.session.add(mapeo)

    _crear_sync_log(
        empresa_id=empresa_id,
        recurso='producto',
        direccion='exportacion',
        estado='exitoso',
        mensaje=f'Producto "{producto.nombre}" publicado en TN',
        referencia_id_externo=str(tn_producto_id),
        payload=payload,
        respuesta=respuesta_tn,
    )

    db.session.commit()
    return mapeo


def desvincular_producto(producto_id, empresa_id):
    """Desvincula un producto de Tienda Nube y lo elimina de la tienda.

    Intenta eliminar el producto en TN (si ya fue borrado allá, ignora el
    error) y marca el mapeo local como inactivo.

    Args:
        producto_id: ID del producto local.
        empresa_id: ID de la empresa.

    Raises:
        ValueError: Si el producto no está vinculado.
    """
    mapeo = _cargar_mapeo_activo(producto_id, empresa_id)
    client = obtener_cliente_tn(empresa_id)

    # Intentar eliminar en TN — puede fallar si ya fue borrado manualmente
    try:
        client.eliminar_producto(mapeo.tn_producto_id)
        mensaje = f'Producto TN {mapeo.tn_producto_id} eliminado'
        estado_log = 'exitoso'
    except TiendaNubeAPIError as e:
        # 404 = ya no existe en TN, no es un error real
        if e.status_code == 404:
            mensaje = f'Producto TN {mapeo.tn_producto_id} ya no existía en la tienda'
            estado_log = 'exitoso'
        else:
            mensaje = f'Error al eliminar en TN: {e}'
            estado_log = 'error'
            logger.warning(
                'Error al eliminar producto %s de TN: %s',
                mapeo.tn_producto_id,
                e,
            )

    mapeo.activo = False

    _crear_sync_log(
        empresa_id=empresa_id,
        recurso='producto',
        direccion='exportacion',
        estado=estado_log,
        mensaje=mensaje,
        referencia_id_externo=str(mapeo.tn_producto_id),
    )

    db.session.commit()


# -------------------------------------------------------------------
# Sincronización de stock y precios
# -------------------------------------------------------------------


def sincronizar_stock(producto_id, empresa_id):
    """Sincroniza el stock actual del producto local hacia Tienda Nube.

    Envía el valor absoluto de stock_actual como nuevo stock de la variante
    en TN. El ERP es fuente de verdad para stock.

    Args:
        producto_id: ID del producto local.
        empresa_id: ID de la empresa.

    Returns:
        ProductoTiendaNube actualizado.

    Raises:
        ValueError: Si el producto no está vinculado o falla la API.
    """
    mapeo = _cargar_mapeo_activo(producto_id, empresa_id)
    producto = db.session.get(Producto, producto_id)

    if not producto:
        raise ValueError(f'Producto {producto_id} no encontrado.')

    client = obtener_cliente_tn(empresa_id)

    payload = [
        {
            'id': mapeo.tn_variante_id,
            'stock': float(producto.stock_actual),
        }
    ]

    try:
        respuesta_tn = client.actualizar_stock_variante(
            mapeo.tn_producto_id,
            payload,
        )

        mapeo.marcar_sincronizado()

        _crear_sync_log(
            empresa_id=empresa_id,
            recurso='stock',
            direccion='exportacion',
            estado='exitoso',
            mensaje=f'Stock sincronizado: {float(producto.stock_actual)}',
            referencia_id_externo=str(mapeo.tn_producto_id),
            payload=payload,
            respuesta=respuesta_tn,
        )

        db.session.commit()
        return mapeo

    except TiendaNubeAPIError as e:
        mapeo.marcar_error(str(e))

        _crear_sync_log(
            empresa_id=empresa_id,
            recurso='stock',
            direccion='exportacion',
            estado='error',
            mensaje=f'Error al sincronizar stock: {e}',
            referencia_id_externo=str(mapeo.tn_producto_id),
            payload=payload,
            respuesta=e.response_body,
        )

        db.session.commit()
        raise ValueError(f'Error al sincronizar stock de "{producto.nombre}": {e.message}') from e


def sincronizar_precio(producto_id, empresa_id):
    """Sincroniza el precio de venta del producto local hacia Tienda Nube.

    Actualiza el precio de la variante principal del producto en TN usando
    el precio_venta del producto local.

    Args:
        producto_id: ID del producto local.
        empresa_id: ID de la empresa.

    Returns:
        ProductoTiendaNube actualizado.

    Raises:
        ValueError: Si el producto no está vinculado o falla la API.
    """
    mapeo = _cargar_mapeo_activo(producto_id, empresa_id)
    producto = db.session.get(Producto, producto_id)

    if not producto:
        raise ValueError(f'Producto {producto_id} no encontrado.')

    client = obtener_cliente_tn(empresa_id)

    # Para actualizar precio usamos la variante
    payload = [
        {
            'id': mapeo.tn_variante_id,
            'price': str(producto.precio_venta),
        }
    ]

    try:
        respuesta_tn = client.actualizar_stock_variante(
            mapeo.tn_producto_id,
            payload,
        )

        mapeo.marcar_sincronizado()

        _crear_sync_log(
            empresa_id=empresa_id,
            recurso='precio',
            direccion='exportacion',
            estado='exitoso',
            mensaje=f'Precio sincronizado: ${producto.precio_venta}',
            referencia_id_externo=str(mapeo.tn_producto_id),
            payload=payload,
            respuesta=respuesta_tn,
        )

        db.session.commit()
        return mapeo

    except TiendaNubeAPIError as e:
        mapeo.marcar_error(str(e))

        _crear_sync_log(
            empresa_id=empresa_id,
            recurso='precio',
            direccion='exportacion',
            estado='error',
            mensaje=f'Error al sincronizar precio: {e}',
            referencia_id_externo=str(mapeo.tn_producto_id),
            payload=payload,
            respuesta=e.response_body,
        )

        db.session.commit()
        raise ValueError(f'Error al sincronizar precio de "{producto.nombre}": {e.message}') from e


def sincronizar_producto_completo(producto_id, empresa_id):
    """Sincroniza stock Y precio del producto en una sola llamada a TN.

    Combina ambos valores en un único request a la API de variantes
    para reducir consumo de rate limit.

    Args:
        producto_id: ID del producto local.
        empresa_id: ID de la empresa.

    Returns:
        ProductoTiendaNube actualizado.

    Raises:
        ValueError: Si el producto no está vinculado o falla la API.
    """
    mapeo = _cargar_mapeo_activo(producto_id, empresa_id)
    producto = db.session.get(Producto, producto_id)

    if not producto:
        raise ValueError(f'Producto {producto_id} no encontrado.')

    client = obtener_cliente_tn(empresa_id)

    payload = [
        {
            'id': mapeo.tn_variante_id,
            'price': str(producto.precio_venta),
            'stock': float(producto.stock_actual),
        }
    ]

    try:
        respuesta_tn = client.actualizar_stock_variante(
            mapeo.tn_producto_id,
            payload,
        )

        mapeo.marcar_sincronizado()

        _crear_sync_log(
            empresa_id=empresa_id,
            recurso='producto',
            direccion='exportacion',
            estado='exitoso',
            mensaje=(
                f'Sync completo — stock: {float(producto.stock_actual)}, '
                f'precio: ${producto.precio_venta}'
            ),
            referencia_id_externo=str(mapeo.tn_producto_id),
            payload=payload,
            respuesta=respuesta_tn,
        )

        db.session.commit()
        return mapeo

    except TiendaNubeAPIError as e:
        mapeo.marcar_error(str(e))

        _crear_sync_log(
            empresa_id=empresa_id,
            recurso='producto',
            direccion='exportacion',
            estado='error',
            mensaje=f'Error en sync completo: {e}',
            referencia_id_externo=str(mapeo.tn_producto_id),
            payload=payload,
            respuesta=e.response_body,
        )

        db.session.commit()
        raise ValueError(f'Error al sincronizar "{producto.nombre}": {e.message}') from e


# -------------------------------------------------------------------
# Sincronización masiva
# -------------------------------------------------------------------


def sincronizar_stock_masivo(empresa_id):
    """Sincroniza el stock de TODOS los productos vinculados de la empresa.

    Itera los mapeos activos y actualiza el stock de cada uno en TN.
    No interrumpe el proceso si uno falla; acumula errores y devuelve
    un resumen al final.

    Args:
        empresa_id: ID de la empresa.

    Returns:
        dict con claves: total, exitosos, errores, detalle_errores.
    """
    mapeos = ProductoTiendaNube.query.filter_by(
        empresa_id=empresa_id,
        activo=True,
    ).all()

    resultado = {
        'total': len(mapeos),
        'exitosos': 0,
        'errores': 0,
        'detalle_errores': [],
    }

    for mapeo in mapeos:
        try:
            sincronizar_stock(mapeo.producto_id, empresa_id)
            resultado['exitosos'] += 1
        except ValueError as e:
            resultado['errores'] += 1
            resultado['detalle_errores'].append(
                {
                    'producto_id': mapeo.producto_id,
                    'tn_producto_id': mapeo.tn_producto_id,
                    'error': str(e),
                }
            )
            logger.warning(
                'Error en sync masivo para producto %s: %s',
                mapeo.producto_id,
                e,
            )

    return resultado


# -------------------------------------------------------------------
# Consultas
# -------------------------------------------------------------------


def listar_productos_vinculados(empresa_id):
    """Lista todos los productos activamente vinculados a Tienda Nube.

    Carga eager la relación con Producto para evitar N+1 en la vista.

    Args:
        empresa_id: ID de la empresa.

    Returns:
        Lista de ProductoTiendaNube con su producto cargado.
    """
    return (
        ProductoTiendaNube.query.filter_by(empresa_id=empresa_id, activo=True)
        .join(Producto, ProductoTiendaNube.producto_id == Producto.id)
        .options(db.joinedload(ProductoTiendaNube.producto))
        .order_by(Producto.nombre)
        .all()
    )


def listar_productos_disponibles(empresa_id):
    """Lista los productos activos que aún no están vinculados a TN.

    Usa un subquery para excluir los producto_ids que ya tienen un
    mapeo activo en ProductoTiendaNube.

    Args:
        empresa_id: ID de la empresa.

    Returns:
        Lista de Producto disponibles para vincular.
    """
    ids_vinculados = (
        db.session.query(ProductoTiendaNube.producto_id)
        .filter_by(empresa_id=empresa_id, activo=True)
        .subquery()
    )

    return (
        Producto.query.filter_by(empresa_id=empresa_id, activo=True)
        .filter(Producto.id.notin_(db.select(ids_vinculados)))
        .order_by(Producto.nombre)
        .all()
    )
