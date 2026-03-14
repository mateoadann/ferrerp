"""Servicio de integración con Tienda Nube.

Contiene la lógica de negocio para vincular productos locales con Tienda Nube,
sincronizar stock y precios, administrar los mapeos producto-a-producto e
importar órdenes de venta desde Tienda Nube al ERP.
"""

import json
import logging
from decimal import Decimal

from flask import url_for

from ..extensions import db
from ..models import (
    Cliente,
    MovimientoStock,
    Producto,
    ProductoTiendaNube,
    SyncLog,
    TiendaNubeCredencial,
    Usuario,
    Venta,
    VentaDetalle,
)
from ..utils.helpers import ahora_argentina, generar_numero_venta
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


# -------------------------------------------------------------------
# Registro y limpieza de webhooks
# -------------------------------------------------------------------

EVENTOS_WEBHOOK = [
    'order/created',
    'order/updated',
    'order/cancelled',
]


def registrar_webhooks_tn(empresa_id, webhook_url=None):
    """Registra los webhooks de órdenes en Tienda Nube.

    Crea webhooks para los eventos de orden (created, updated, cancelled)
    en la tienda del tenant. Si un webhook ya existe (TN devuelve 422),
    se omite silenciosamente.

    Args:
        empresa_id: ID de la empresa.
        webhook_url: URL absoluta del endpoint webhook. Si no se pasa,
            se genera con url_for (requiere request context).

    Returns:
        Lista de dicts con los webhooks creados exitosamente.
    """
    client = obtener_cliente_tn(empresa_id)

    if not webhook_url:
        webhook_url = url_for('tiendanube.webhook', _external=True)

    creados = []

    for evento in EVENTOS_WEBHOOK:
        payload = {'event': evento, 'url': webhook_url}

        try:
            resultado = client.crear_webhook(evento, webhook_url)
            creados.append(resultado)

            _crear_sync_log(
                empresa_id=empresa_id,
                recurso='webhook',
                direccion='exportacion',
                estado='exitoso',
                mensaje=f'Webhook registrado: {evento}',
                referencia_id_externo=str(resultado.get('id', '')),
                payload=payload,
                respuesta=resultado,
            )

            logger.info(
                'Webhook registrado — empresa=%s evento=%s webhook_id=%s',
                empresa_id,
                evento,
                resultado.get('id'),
            )

        except TiendaNubeAPIError as e:
            # 422 = webhook ya existe para ese evento, no es error real
            if e.status_code == 422:
                logger.info(
                    'Webhook ya existe para evento %s — empresa=%s, se omite',
                    evento,
                    empresa_id,
                )
                _crear_sync_log(
                    empresa_id=empresa_id,
                    recurso='webhook',
                    direccion='exportacion',
                    estado='exitoso',
                    mensaje=f'Webhook para {evento} ya existía, se omitió',
                    payload=payload,
                    respuesta=e.response_body,
                )
            else:
                logger.error(
                    'Error al registrar webhook %s — empresa=%s: %s',
                    evento,
                    empresa_id,
                    e,
                )
                _crear_sync_log(
                    empresa_id=empresa_id,
                    recurso='webhook',
                    direccion='exportacion',
                    estado='error',
                    mensaje=f'Error al registrar webhook {evento}: {e}',
                    payload=payload,
                    respuesta=e.response_body,
                )

    db.session.commit()
    return creados


def eliminar_webhooks_tn(empresa_id):
    """Elimina todos los webhooks registrados en Tienda Nube para la empresa.

    Lista los webhooks existentes y los borra uno a uno. Errores en la
    eliminación individual se loguean pero no interrumpen el proceso.

    Args:
        empresa_id: ID de la empresa.
    """
    client = obtener_cliente_tn(empresa_id)

    try:
        webhooks = client.listar_webhooks()
    except TiendaNubeAPIError as e:
        logger.error(
            'Error al listar webhooks para eliminar — empresa=%s: %s',
            empresa_id,
            e,
        )
        _crear_sync_log(
            empresa_id=empresa_id,
            recurso='webhook',
            direccion='exportacion',
            estado='error',
            mensaje=f'Error al listar webhooks para eliminar: {e}',
            respuesta=e.response_body,
        )
        db.session.commit()
        return

    for wh in webhooks:
        wh_id = wh.get('id')
        if not wh_id:
            continue

        try:
            client.eliminar_webhook(wh_id)

            logger.info(
                'Webhook eliminado — empresa=%s webhook_id=%s',
                empresa_id,
                wh_id,
            )

        except TiendaNubeAPIError as e:
            # 404 = ya fue eliminado, no es error real
            if e.status_code != 404:
                logger.warning(
                    'Error al eliminar webhook %s — empresa=%s: %s',
                    wh_id,
                    empresa_id,
                    e,
                )

    _crear_sync_log(
        empresa_id=empresa_id,
        recurso='webhook',
        direccion='exportacion',
        estado='exitoso',
        mensaje=f'Webhooks eliminados: {len(webhooks)} procesados',
    )
    db.session.commit()


# -------------------------------------------------------------------
# Importación de órdenes desde Tienda Nube
# -------------------------------------------------------------------


def obtener_o_crear_cliente_web(empresa_id):
    """Obtiene o crea el cliente genérico para ventas de Tienda Nube.

    Busca un cliente con nombre 'Cliente Web (Tienda Nube)' en la empresa.
    Si no existe, lo crea con datos mínimos.

    Args:
        empresa_id: ID de la empresa.

    Returns:
        Cliente genérico para ventas online.
    """
    nombre_cliente = 'Cliente Web (Tienda Nube)'
    cliente = Cliente.query.filter_by(
        empresa_id=empresa_id,
        nombre=nombre_cliente,
    ).first()

    if cliente:
        return cliente

    cliente = Cliente(
        empresa_id=empresa_id,
        nombre=nombre_cliente,
        notas='Cliente genérico para órdenes importadas de Tienda Nube.',
    )
    db.session.add(cliente)
    db.session.flush()

    logger.info(
        'Cliente web genérico creado — empresa=%s cliente_id=%s',
        empresa_id,
        cliente.id,
    )
    return cliente


def importar_orden_tn(tn_orden_id, empresa_id):
    """Importa una orden de Tienda Nube como Venta en el ERP.

    Obtiene la orden desde la API de TN, valida que esté paga, busca los
    mapeos de producto y genera la Venta con sus detalles, movimientos de
    stock y registros de sincronización.

    La función es idempotente: si la orden ya fue importada (existe una
    Venta con el mismo tn_orden_id para la empresa), retorna la venta
    existente sin duplicar.

    Args:
        tn_orden_id: ID de la orden en Tienda Nube.
        empresa_id: ID de la empresa local.

    Returns:
        Venta creada o existente, o None si la orden no está paga.

    Raises:
        ValueError: Si falla la comunicación con TN o faltan datos
            críticos (admin, credenciales).
    """
    # 1. Idempotencia — verificar si ya fue importada
    venta_existente = Venta.query.filter_by(
        empresa_id=empresa_id,
        tn_orden_id=tn_orden_id,
    ).first()

    if venta_existente:
        logger.info(
            'Orden TN %s ya importada como venta %s — empresa=%s',
            tn_orden_id,
            venta_existente.numero_completo,
            empresa_id,
        )
        return venta_existente

    try:
        # 2. Obtener la orden desde la API de TN
        client = obtener_cliente_tn(empresa_id)
        orden = client.obtener_orden(tn_orden_id)

        # 3. Solo importar órdenes pagas
        payment_status = orden.get('payment_status', '')
        if payment_status != 'paid':
            logger.info(
                'Orden TN %s no está paga (status=%s) — empresa=%s',
                tn_orden_id,
                payment_status,
                empresa_id,
            )
            _crear_sync_log(
                empresa_id=empresa_id,
                recurso='orden',
                direccion='importacion',
                estado='pendiente',
                mensaje=(
                    f'Orden TN #{orden.get("number", tn_orden_id)} '
                    f'no importada — payment_status={payment_status}'
                ),
                referencia_id_externo=str(tn_orden_id),
                respuesta=orden,
            )
            db.session.commit()
            return None

        # 4. Obtener cliente web genérico y usuario admin
        cliente_web = obtener_o_crear_cliente_web(empresa_id)

        usuario_admin = Usuario.query.filter_by(
            empresa_id=empresa_id,
            rol='administrador',
            activo=True,
        ).first()

        if not usuario_admin:
            raise ValueError(
                'No se encontró un usuario administrador activo para la empresa. '
                'Se requiere para registrar la venta.'
            )

        # 5. Crear la Venta
        numero_orden_tn = orden.get('number', str(tn_orden_id))

        venta = Venta(
            numero=generar_numero_venta(empresa_id),
            fecha=ahora_argentina(),
            cliente_id=cliente_web.id,
            usuario_id=usuario_admin.id,
            forma_pago='transferencia',
            estado='completada',
            caja_id=None,
            empresa_id=empresa_id,
            origen='tiendanube',
            tn_orden_id=tn_orden_id,
            subtotal=Decimal('0'),
            descuento_porcentaje=Decimal('0'),
            descuento_monto=Decimal('0'),
            total=Decimal('0'),
        )
        db.session.add(venta)
        db.session.flush()  # Necesitamos venta.id para los detalles

        # 6. Procesar cada producto de la orden
        subtotal_venta = Decimal('0')
        productos_sin_mapeo = []

        for item in orden.get('products', []):
            tn_producto_id = item.get('product_id')

            # Buscar mapeo local por tn_producto_id
            mapeo = ProductoTiendaNube.query.filter_by(
                empresa_id=empresa_id,
                tn_producto_id=tn_producto_id,
                activo=True,
            ).first()

            if not mapeo:
                productos_sin_mapeo.append(f'{item.get("name", "?")} (TN ID: {tn_producto_id})')
                logger.warning(
                    'Producto TN %s no tiene mapeo local — '
                    'orden=%s empresa=%s — se omite del detalle',
                    tn_producto_id,
                    tn_orden_id,
                    empresa_id,
                )
                continue

            producto = db.session.get(Producto, mapeo.producto_id)
            if not producto:
                logger.warning(
                    'Producto local %s referenciado por mapeo pero no existe — '
                    'orden=%s empresa=%s',
                    mapeo.producto_id,
                    tn_orden_id,
                    empresa_id,
                )
                continue

            cantidad = Decimal(str(item.get('quantity', '0')))
            precio_unitario = Decimal(str(item.get('price', '0')))
            item_subtotal = cantidad * precio_unitario
            subtotal_venta += item_subtotal

            # Crear detalle de venta
            detalle = VentaDetalle(
                venta_id=venta.id,
                producto_id=producto.id,
                cantidad=cantidad,
                precio_unitario=precio_unitario,
                iva_porcentaje=producto.iva_porcentaje,
                subtotal=item_subtotal,
            )
            db.session.add(detalle)

            # Descontar stock
            stock_anterior, stock_posterior = producto.actualizar_stock(
                -cantidad,
                'venta',
            )

            # Registrar movimiento de stock
            movimiento = MovimientoStock(
                producto_id=producto.id,
                tipo='venta',
                cantidad=-cantidad,
                stock_anterior=stock_anterior,
                stock_posterior=stock_posterior,
                referencia_tipo='venta',
                referencia_id=venta.id,
                motivo=f'Venta Tienda Nube — orden #{numero_orden_tn}',
                usuario_id=usuario_admin.id,
                empresa_id=empresa_id,
            )
            db.session.add(movimiento)

        # 7. Calcular totales
        venta.subtotal = subtotal_venta
        venta.total = subtotal_venta

        # 8. Construir mensaje del SyncLog
        observaciones_extra = ''
        if productos_sin_mapeo:
            observaciones_extra = f' — productos sin mapeo: {", ".join(productos_sin_mapeo)}'

        _crear_sync_log(
            empresa_id=empresa_id,
            recurso='orden',
            direccion='importacion',
            estado='exitoso',
            mensaje=(
                f'Orden TN #{numero_orden_tn} importada como venta '
                f'{venta.numero_completo} — total ${venta.total}'
                f'{observaciones_extra}'
            ),
            referencia_id_externo=str(tn_orden_id),
            respuesta=orden,
        )

        db.session.commit()

        logger.info(
            'Orden TN %s importada exitosamente — venta=%s total=%s empresa=%s',
            tn_orden_id,
            venta.numero_completo,
            venta.total,
            empresa_id,
        )
        return venta

    except TiendaNubeAPIError as e:
        db.session.rollback()
        logger.error(
            'Error de API TN al importar orden %s — empresa=%s: %s',
            tn_orden_id,
            empresa_id,
            e,
        )
        _crear_sync_log(
            empresa_id=empresa_id,
            recurso='orden',
            direccion='importacion',
            estado='error',
            mensaje=f'Error de API TN al importar orden {tn_orden_id}: {e}',
            referencia_id_externo=str(tn_orden_id),
            respuesta=e.response_body,
        )
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        raise ValueError(
            f'Error al importar orden #{tn_orden_id} de Tienda Nube: {e.message}'
        ) from e

    except Exception as e:
        db.session.rollback()
        logger.exception(
            'Error inesperado al importar orden TN %s — empresa=%s',
            tn_orden_id,
            empresa_id,
        )
        _crear_sync_log(
            empresa_id=empresa_id,
            recurso='orden',
            direccion='importacion',
            estado='error',
            mensaje=f'Error inesperado al importar orden {tn_orden_id}: {e}',
            referencia_id_externo=str(tn_orden_id),
        )
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        raise ValueError(f'Error inesperado al importar orden #{tn_orden_id}: {e}') from e
