"""Tests para el servicio de integración con Tienda Nube."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.extensions import db
from app.models import (
    Cliente,
    Empresa,
    MovimientoStock,
    Producto,
    ProductoTiendaNube,
    SyncLog,
    TiendaNubeCredencial,
    Usuario,
    Venta,
    VentaDetalle,
)
from app.services.tiendanube_service import (
    desvincular_producto,
    importar_orden_tn,
    listar_productos_disponibles,
    listar_productos_vinculados,
    obtener_o_crear_cliente_web,
    sincronizar_stock,
    vincular_producto,
)

# -------------------------------------------------------------------
# Helpers de test
# -------------------------------------------------------------------


def _crear_empresa():
    """Crea una empresa de prueba."""
    empresa = Empresa(nombre='Ferretería Test', activa=True)
    db.session.add(empresa)
    db.session.flush()
    return empresa


def _crear_usuario(empresa_id, email='tn-svc@ferrerp.test', rol='administrador'):
    """Crea un usuario de prueba."""
    usuario = Usuario(
        email=email,
        nombre='Admin TN',
        rol=rol,
        activo=True,
        empresa_id=empresa_id,
    )
    usuario.set_password('clave')
    db.session.add(usuario)
    db.session.flush()
    return usuario


def _crear_producto(empresa_id, codigo='MART-001', precio='1500.00', stock='10.000'):
    """Crea un producto de prueba."""
    producto = Producto(
        codigo=codigo,
        nombre=f'Producto {codigo}',
        unidad_medida='unidad',
        precio_costo=Decimal('500.00'),
        precio_venta=Decimal(str(precio)),
        stock_actual=Decimal(str(stock)),
        stock_minimo=Decimal('2.000'),
        activo=True,
        empresa_id=empresa_id,
    )
    db.session.add(producto)
    db.session.flush()
    return producto


def _crear_credencial(empresa_id, tienda_id='12345'):
    """Crea una credencial TN activa de prueba."""
    cred = TiendaNubeCredencial(
        empresa_id=empresa_id,
        tn_app_id='app_test_123',
        tn_app_secret='secret_test_456',
        tienda_id_externo=tienda_id,
        usuario_id_externo='user_789',
        access_token='tok_test_abc',
        activo=True,
    )
    db.session.add(cred)
    db.session.flush()
    return cred


def _crear_mapeo(empresa_id, producto_id, tn_producto_id=99999, tn_variante_id=88888):
    """Crea un mapeo producto-TN activo."""
    mapeo = ProductoTiendaNube(
        empresa_id=empresa_id,
        producto_id=producto_id,
        tn_producto_id=tn_producto_id,
        tn_variante_id=tn_variante_id,
        activo=True,
    )
    db.session.add(mapeo)
    db.session.flush()
    return mapeo


# -------------------------------------------------------------------
# vincular_producto
# -------------------------------------------------------------------


@patch('app.services.tiendanube_service.TiendaNubeClient')
def test_vincular_producto_exitoso(mock_client_class, app):
    """vincular_producto crea mapeo y SyncLog exitosamente."""
    mock_client = MagicMock()
    mock_client.crear_producto.return_value = {
        'id': 99999,
        'variants': [{'id': 88888}],
    }
    mock_client_class.return_value = mock_client

    empresa = _crear_empresa()
    _crear_credencial(empresa.id)
    producto = _crear_producto(empresa.id)
    db.session.commit()

    mapeo = vincular_producto(producto.id, empresa.id)

    assert mapeo.tn_producto_id == 99999
    assert mapeo.tn_variante_id == 88888
    assert mapeo.estado_sync == 'sincronizado'
    assert mapeo.activo is True

    # Verificar que se creó un SyncLog exitoso
    log = SyncLog.query.filter_by(
        empresa_id=empresa.id,
        recurso='producto',
        estado='exitoso',
    ).first()
    assert log is not None
    assert 'publicado en TN' in log.mensaje

    mock_client.crear_producto.assert_called_once()


@patch('app.services.tiendanube_service.TiendaNubeClient')
def test_vincular_producto_ya_vinculado(mock_client_class, app):
    """Raise ValueError si producto ya está vinculado."""
    empresa = _crear_empresa()
    _crear_credencial(empresa.id)
    producto = _crear_producto(empresa.id)
    _crear_mapeo(empresa.id, producto.id)
    db.session.commit()

    with pytest.raises(ValueError, match='ya está vinculado'):
        vincular_producto(producto.id, empresa.id)

    # No debe haber llamado a la API
    mock_client_class.assert_not_called()


def test_vincular_producto_sin_credenciales(app):
    """Raise ValueError si no hay credenciales TN activas."""
    empresa = _crear_empresa()
    producto = _crear_producto(empresa.id)
    db.session.commit()

    with pytest.raises(ValueError, match='no tiene credenciales activas'):
        vincular_producto(producto.id, empresa.id)


@patch('app.services.tiendanube_service.TiendaNubeClient')
def test_vincular_producto_inexistente(mock_client_class, app):
    """Raise ValueError si el producto no existe."""
    empresa = _crear_empresa()
    _crear_credencial(empresa.id)
    db.session.commit()

    with pytest.raises(ValueError, match='no encontrado'):
        vincular_producto(99999, empresa.id)


@patch('app.services.tiendanube_service.TiendaNubeClient')
def test_vincular_producto_inactivo(mock_client_class, app):
    """Raise ValueError si el producto está inactivo."""
    empresa = _crear_empresa()
    _crear_credencial(empresa.id)
    producto = _crear_producto(empresa.id)
    producto.activo = False
    db.session.commit()

    with pytest.raises(ValueError, match='inactivo'):
        vincular_producto(producto.id, empresa.id)


# -------------------------------------------------------------------
# desvincular_producto
# -------------------------------------------------------------------


@patch('app.services.tiendanube_service.TiendaNubeClient')
def test_desvincular_producto_exitoso(mock_client_class, app):
    """desvincular_producto desactiva mapeo y elimina en TN."""
    mock_client = MagicMock()
    mock_client.eliminar_producto.return_value = {}
    mock_client_class.return_value = mock_client

    empresa = _crear_empresa()
    _crear_credencial(empresa.id)
    producto = _crear_producto(empresa.id)
    mapeo = _crear_mapeo(empresa.id, producto.id)
    db.session.commit()

    desvincular_producto(producto.id, empresa.id)

    db.session.refresh(mapeo)
    assert mapeo.activo is False

    mock_client.eliminar_producto.assert_called_once_with(99999)

    log = SyncLog.query.filter_by(
        empresa_id=empresa.id,
        recurso='producto',
        estado='exitoso',
    ).first()
    assert log is not None


def test_desvincular_producto_no_vinculado(app):
    """Raise ValueError si el producto no está vinculado."""
    empresa = _crear_empresa()
    _crear_credencial(empresa.id)
    producto = _crear_producto(empresa.id)
    db.session.commit()

    with pytest.raises(ValueError, match='no está vinculado'):
        desvincular_producto(producto.id, empresa.id)


# -------------------------------------------------------------------
# sincronizar_stock
# -------------------------------------------------------------------


@patch('app.services.tiendanube_service.TiendaNubeClient')
def test_sincronizar_stock_exitoso(mock_client_class, app):
    """sincronizar_stock actualiza stock en TN y marca sincronizado."""
    mock_client = MagicMock()
    mock_client.actualizar_stock_variante.return_value = {'status': 'ok'}
    mock_client_class.return_value = mock_client

    empresa = _crear_empresa()
    _crear_credencial(empresa.id)
    producto = _crear_producto(empresa.id, stock='25.000')
    _crear_mapeo(empresa.id, producto.id)
    db.session.commit()

    resultado = sincronizar_stock(producto.id, empresa.id)

    assert resultado.estado_sync == 'sincronizado'
    assert resultado.ultimo_error is None

    # Verificar el payload enviado a la API
    llamada = mock_client.actualizar_stock_variante.call_args
    assert llamada[0][0] == 99999  # tn_producto_id
    payload = llamada[0][1]
    assert payload[0]['stock'] == 25.0
    assert payload[0]['id'] == 88888  # tn_variante_id

    log = SyncLog.query.filter_by(
        empresa_id=empresa.id,
        recurso='stock',
        estado='exitoso',
    ).first()
    assert log is not None


def test_sincronizar_stock_producto_no_vinculado(app):
    """Raise ValueError si producto no está vinculado a TN."""
    empresa = _crear_empresa()
    _crear_credencial(empresa.id)
    producto = _crear_producto(empresa.id)
    db.session.commit()

    with pytest.raises(ValueError, match='no está vinculado'):
        sincronizar_stock(producto.id, empresa.id)


# -------------------------------------------------------------------
# importar_orden_tn
# -------------------------------------------------------------------


@patch('app.services.tiendanube_service.TiendaNubeClient')
def test_importar_orden_exitoso(mock_client_class, app):
    """importar_orden_tn crea Venta + VentaDetalle + MovimientoStock."""
    empresa = _crear_empresa()
    _crear_credencial(empresa.id)
    _crear_usuario(empresa.id)
    producto = _crear_producto(empresa.id, codigo='CLAV-001', precio='500.00', stock='50.000')
    _crear_mapeo(empresa.id, producto.id, tn_producto_id=11111)
    db.session.commit()

    mock_client = MagicMock()
    mock_client.obtener_orden.return_value = {
        'id': 77777,
        'number': '1001',
        'payment_status': 'paid',
        'products': [
            {
                'product_id': 11111,
                'name': 'Clavos 2 pulgadas',
                'quantity': '3',
                'price': '500.00',
            },
        ],
    }
    mock_client_class.return_value = mock_client

    venta = importar_orden_tn(77777, empresa.id)

    assert venta is not None
    assert venta.origen == 'tiendanube'
    assert venta.tn_orden_id == 77777
    assert venta.estado == 'completada'
    assert venta.forma_pago == 'transferencia'
    assert venta.total == Decimal('1500.00')

    # Verificar detalle de venta
    detalles = VentaDetalle.query.filter_by(venta_id=venta.id).all()
    assert len(detalles) == 1
    assert detalles[0].cantidad == Decimal('3')
    assert detalles[0].precio_unitario == Decimal('500.00')

    # Verificar movimiento de stock
    movimiento = MovimientoStock.query.filter_by(
        producto_id=producto.id,
        referencia_tipo='venta',
        referencia_id=venta.id,
    ).first()
    assert movimiento is not None
    assert movimiento.cantidad == Decimal('-3')
    assert movimiento.tipo == 'venta'

    # Verificar stock actualizado
    db.session.refresh(producto)
    assert producto.stock_actual == Decimal('47.000')

    # Verificar SyncLog
    log = SyncLog.query.filter_by(
        empresa_id=empresa.id,
        recurso='orden',
        estado='exitoso',
    ).first()
    assert log is not None


@patch('app.services.tiendanube_service.TiendaNubeClient')
def test_importar_orden_idempotente(mock_client_class, app):
    """Llamar importar_orden_tn dos veces no duplica la venta."""
    empresa = _crear_empresa()
    _crear_credencial(empresa.id)
    _crear_usuario(empresa.id)
    producto = _crear_producto(empresa.id, codigo='TORN-001', precio='100.00', stock='20.000')
    _crear_mapeo(empresa.id, producto.id, tn_producto_id=22222)
    db.session.commit()

    mock_client = MagicMock()
    mock_client.obtener_orden.return_value = {
        'id': 88888,
        'number': '1002',
        'payment_status': 'paid',
        'products': [
            {
                'product_id': 22222,
                'name': 'Tornillo',
                'quantity': '5',
                'price': '100.00',
            },
        ],
    }
    mock_client_class.return_value = mock_client

    venta1 = importar_orden_tn(88888, empresa.id)
    venta2 = importar_orden_tn(88888, empresa.id)

    assert venta1.id == venta2.id

    # Solo debe haber una venta con ese tn_orden_id
    cantidad = Venta.query.filter_by(
        empresa_id=empresa.id,
        tn_orden_id=88888,
    ).count()
    assert cantidad == 1

    # La API solo debió llamarse UNA vez (la segunda usa la venta existente)
    mock_client.obtener_orden.assert_called_once()


@patch('app.services.tiendanube_service.TiendaNubeClient')
def test_importar_orden_no_pagada(mock_client_class, app):
    """Orden no pagada retorna None sin crear venta."""
    empresa = _crear_empresa()
    _crear_credencial(empresa.id)
    _crear_usuario(empresa.id)
    db.session.commit()

    mock_client = MagicMock()
    mock_client.obtener_orden.return_value = {
        'id': 44444,
        'number': '1003',
        'payment_status': 'pending',
        'products': [],
    }
    mock_client_class.return_value = mock_client

    resultado = importar_orden_tn(44444, empresa.id)

    assert resultado is None

    # No debe haberse creado ninguna venta
    cantidad = Venta.query.filter_by(
        empresa_id=empresa.id,
        origen='tiendanube',
    ).count()
    assert cantidad == 0


# -------------------------------------------------------------------
# obtener_o_crear_cliente_web
# -------------------------------------------------------------------


def test_obtener_o_crear_cliente_web_crea_nuevo(app):
    """Crea cliente 'Cliente Web (Tienda Nube)' si no existe."""
    empresa = _crear_empresa()
    db.session.commit()

    cliente = obtener_o_crear_cliente_web(empresa.id)

    assert cliente.id is not None
    assert cliente.nombre == 'Cliente Web (Tienda Nube)'
    assert cliente.empresa_id == empresa.id


def test_obtener_o_crear_cliente_web_idempotente(app):
    """Si el cliente web ya existe, lo retorna sin duplicar."""
    empresa = _crear_empresa()
    db.session.commit()

    cliente1 = obtener_o_crear_cliente_web(empresa.id)
    db.session.commit()

    cliente2 = obtener_o_crear_cliente_web(empresa.id)

    assert cliente1.id == cliente2.id

    cantidad = Cliente.query.filter_by(
        empresa_id=empresa.id,
        nombre='Cliente Web (Tienda Nube)',
    ).count()
    assert cantidad == 1


# -------------------------------------------------------------------
# listar_productos_disponibles / vinculados
# -------------------------------------------------------------------


def test_listar_productos_disponibles(app):
    """Retorna solo productos activos no vinculados a TN."""
    empresa = _crear_empresa()
    prod_vinculado = _crear_producto(empresa.id, codigo='VINC-001')
    prod_libre = _crear_producto(empresa.id, codigo='LIBRE-001')
    prod_inactivo = _crear_producto(empresa.id, codigo='INACT-001')
    prod_inactivo.activo = False
    _crear_mapeo(empresa.id, prod_vinculado.id)
    db.session.commit()

    disponibles = listar_productos_disponibles(empresa.id)
    ids_disponibles = [p.id for p in disponibles]

    assert prod_libre.id in ids_disponibles
    assert prod_vinculado.id not in ids_disponibles
    assert prod_inactivo.id not in ids_disponibles


def test_listar_productos_vinculados(app):
    """Retorna solo productos vinculados activos."""
    empresa = _crear_empresa()
    prod1 = _crear_producto(empresa.id, codigo='VINC-A')
    prod2 = _crear_producto(empresa.id, codigo='VINC-B')
    prod3 = _crear_producto(empresa.id, codigo='LIBRE-B')
    _crear_mapeo(empresa.id, prod1.id, tn_producto_id=11111)
    mapeo_inactivo = _crear_mapeo(empresa.id, prod2.id, tn_producto_id=22222)
    mapeo_inactivo.activo = False
    db.session.commit()

    vinculados = listar_productos_vinculados(empresa.id)
    ids_vinculados = [m.producto_id for m in vinculados]

    assert prod1.id in ids_vinculados
    assert prod2.id not in ids_vinculados  # Mapeo inactivo
    assert prod3.id not in ids_vinculados  # No vinculado
