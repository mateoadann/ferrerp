"""Tests para los modelos de integración con Tienda Nube."""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    Empresa,
    Producto,
    ProductoTiendaNube,
    SyncLog,
    TiendaNubeCredencial,
    Usuario,
    Venta,
)


def _crear_empresa():
    """Crea una empresa de prueba."""
    empresa = Empresa(nombre='Ferretería Test', activa=True)
    db.session.add(empresa)
    db.session.flush()
    return empresa


def _crear_usuario(empresa_id, email='tn@ferrerp.test'):
    """Crea un usuario de prueba."""
    usuario = Usuario(
        email=email,
        nombre='Usuario TN',
        rol='administrador',
        activo=True,
        empresa_id=empresa_id,
    )
    usuario.set_password('clave')
    db.session.add(usuario)
    db.session.flush()
    return usuario


def _crear_producto(empresa_id, codigo='MART-001'):
    """Crea un producto de prueba."""
    producto = Producto(
        codigo=codigo,
        nombre=f'Producto {codigo}',
        unidad_medida='unidad',
        precio_costo=Decimal('500.00'),
        precio_venta=Decimal('1500.00'),
        stock_actual=Decimal('10.000'),
        stock_minimo=Decimal('2.000'),
        activo=True,
        empresa_id=empresa_id,
    )
    db.session.add(producto)
    db.session.flush()
    return producto


def _crear_credencial(empresa_id, tienda_id='12345', activo=True):
    """Crea una credencial TN de prueba."""
    cred = TiendaNubeCredencial(
        empresa_id=empresa_id,
        tn_app_id='app_test_123',
        tn_app_secret='secret_test_456',
        tienda_id_externo=tienda_id,
        usuario_id_externo='user_789',
        access_token='tok_test_abc',
        activo=activo,
    )
    db.session.add(cred)
    db.session.flush()
    return cred


# -------------------------------------------------------------------
# TiendaNubeCredencial
# -------------------------------------------------------------------


def test_credencial_creacion(app):
    """Crear credencial TN con campos requeridos."""
    empresa = _crear_empresa()
    cred = _crear_credencial(empresa.id)
    db.session.commit()

    assert cred.id is not None
    assert cred.empresa_id == empresa.id
    assert cred.tn_app_id == 'app_test_123'
    assert cred.tn_app_secret == 'secret_test_456'
    assert cred.tienda_id_externo == '12345'
    assert cred.access_token == 'tok_test_abc'
    assert cred.activo is True
    assert cred.token_type == 'bearer'
    assert cred.created_at is not None


def test_credencial_unique_empresa(app):
    """Solo una credencial por empresa (unique constraint en empresa_id)."""
    empresa = _crear_empresa()
    _crear_credencial(empresa.id, tienda_id='11111')
    db.session.commit()

    cred2 = TiendaNubeCredencial(
        empresa_id=empresa.id,
        tn_app_id='app_otra',
        tn_app_secret='secret_otra',
        tienda_id_externo='22222',
    )
    db.session.add(cred2)

    with pytest.raises(IntegrityError):
        db.session.commit()

    db.session.rollback()


def test_credencial_to_dict_oculta_token(app):
    """to_dict() no expone el access_token, solo indica si existe."""
    empresa = _crear_empresa()
    cred = _crear_credencial(empresa.id)
    db.session.commit()

    d = cred.to_dict()
    assert 'access_token' not in d
    assert d['tiene_access_token'] is True
    assert d['tienda_id_externo'] == '12345'
    assert d['activo'] is True


# -------------------------------------------------------------------
# SyncLog
# -------------------------------------------------------------------


def test_sync_log_creacion(app):
    """Crear SyncLog con estados válidos."""
    empresa = _crear_empresa()
    db.session.commit()

    log = SyncLog(
        empresa_id=empresa.id,
        recurso='producto',
        direccion='exportacion',
        estado='exitoso',
        mensaje='Producto sincronizado',
        referencia_id_externo='99999',
    )
    db.session.add(log)
    db.session.commit()

    assert log.id is not None
    assert log.recurso == 'producto'
    assert log.direccion == 'exportacion'
    assert log.estado == 'exitoso'
    assert log.created_at is not None


def test_sync_log_to_dict(app):
    """to_dict() retorna todos los campos del log."""
    empresa = _crear_empresa()
    db.session.commit()

    log = SyncLog(
        empresa_id=empresa.id,
        recurso='orden',
        direccion='importacion',
        estado='pendiente',
        mensaje='Webhook recibido',
        referencia_id_externo='55555',
        payload='{"event": "order/created"}',
    )
    db.session.add(log)
    db.session.commit()

    d = log.to_dict()
    assert d['recurso'] == 'orden'
    assert d['direccion'] == 'importacion'
    assert d['estado'] == 'pendiente'
    assert d['referencia_id_externo'] == '55555'
    assert d['payload'] is not None


# -------------------------------------------------------------------
# ProductoTiendaNube
# -------------------------------------------------------------------


def test_producto_tn_creacion(app):
    """Crear mapeo ProductoTiendaNube con campos requeridos."""
    empresa = _crear_empresa()
    producto = _crear_producto(empresa.id)
    db.session.commit()

    mapeo = ProductoTiendaNube(
        empresa_id=empresa.id,
        producto_id=producto.id,
        tn_producto_id=99999,
        tn_variante_id=88888,
    )
    db.session.add(mapeo)
    db.session.commit()

    assert mapeo.id is not None
    assert mapeo.tn_producto_id == 99999
    assert mapeo.tn_variante_id == 88888
    assert mapeo.estado_sync == 'pendiente'
    assert mapeo.activo is True
    assert mapeo.producto.id == producto.id


def test_producto_tn_marcar_sincronizado(app):
    """marcar_sincronizado() actualiza estado y limpia errores."""
    empresa = _crear_empresa()
    producto = _crear_producto(empresa.id)
    db.session.commit()

    mapeo = ProductoTiendaNube(
        empresa_id=empresa.id,
        producto_id=producto.id,
        tn_producto_id=99999,
        tn_variante_id=88888,
        estado_sync='error',
        ultimo_error='Error previo',
    )
    db.session.add(mapeo)
    db.session.commit()

    mapeo.marcar_sincronizado()
    db.session.commit()

    assert mapeo.estado_sync == 'sincronizado'
    assert mapeo.ultimo_error is None


def test_producto_tn_marcar_error(app):
    """marcar_error() guarda mensaje de error y cambia estado."""
    empresa = _crear_empresa()
    producto = _crear_producto(empresa.id)
    db.session.commit()

    mapeo = ProductoTiendaNube(
        empresa_id=empresa.id,
        producto_id=producto.id,
        tn_producto_id=99999,
        tn_variante_id=88888,
    )
    db.session.add(mapeo)
    db.session.commit()

    mapeo.marcar_error('Timeout en API de TN')
    db.session.commit()

    assert mapeo.estado_sync == 'error'
    assert mapeo.ultimo_error == 'Timeout en API de TN'


def test_producto_tn_unique_producto_empresa(app):
    """No se puede vincular el mismo producto dos veces en la misma empresa."""
    empresa = _crear_empresa()
    producto = _crear_producto(empresa.id)
    db.session.commit()

    mapeo1 = ProductoTiendaNube(
        empresa_id=empresa.id,
        producto_id=producto.id,
        tn_producto_id=99999,
        tn_variante_id=88888,
    )
    db.session.add(mapeo1)
    db.session.commit()

    mapeo2 = ProductoTiendaNube(
        empresa_id=empresa.id,
        producto_id=producto.id,
        tn_producto_id=77777,
        tn_variante_id=66666,
    )
    db.session.add(mapeo2)

    with pytest.raises(IntegrityError):
        db.session.commit()

    db.session.rollback()


def test_producto_tn_to_dict(app):
    """to_dict() retorna todos los campos del mapeo."""
    empresa = _crear_empresa()
    producto = _crear_producto(empresa.id)
    db.session.commit()

    mapeo = ProductoTiendaNube(
        empresa_id=empresa.id,
        producto_id=producto.id,
        tn_producto_id=99999,
        tn_variante_id=88888,
    )
    db.session.add(mapeo)
    db.session.commit()

    d = mapeo.to_dict()
    assert d['producto_id'] == producto.id
    assert d['tn_producto_id'] == 99999
    assert d['tn_variante_id'] == 88888
    assert d['estado_sync'] == 'pendiente'
    assert d['activo'] is True
    assert 'empresa_id' in d
    assert 'creado_en' in d


# -------------------------------------------------------------------
# Venta con origen tiendanube
# -------------------------------------------------------------------


def test_venta_origen_tiendanube(app):
    """Crear venta con origen='tiendanube' y tn_orden_id."""
    empresa = _crear_empresa()
    usuario = _crear_usuario(empresa.id)
    db.session.commit()

    venta = Venta(
        numero=1,
        fecha=datetime(2025, 6, 15),
        usuario_id=usuario.id,
        total=Decimal('5000.00'),
        subtotal=Decimal('5000.00'),
        forma_pago='transferencia',
        estado='completada',
        empresa_id=empresa.id,
        origen='tiendanube',
        tn_orden_id=123456789,
    )
    db.session.add(venta)
    db.session.commit()

    assert venta.origen == 'tiendanube'
    assert venta.tn_orden_id == 123456789
    assert venta.origen_display == 'Tienda Nube'


def test_venta_unique_tn_orden_por_empresa(app):
    """No se puede importar la misma orden TN dos veces para la misma empresa."""
    empresa = _crear_empresa()
    usuario = _crear_usuario(empresa.id)
    db.session.commit()

    venta1 = Venta(
        numero=1,
        fecha=datetime(2025, 6, 15),
        usuario_id=usuario.id,
        total=Decimal('1000.00'),
        forma_pago='transferencia',
        estado='completada',
        empresa_id=empresa.id,
        origen='tiendanube',
        tn_orden_id=123456789,
    )
    db.session.add(venta1)
    db.session.commit()

    venta2 = Venta(
        numero=2,
        fecha=datetime(2025, 6, 16),
        usuario_id=usuario.id,
        total=Decimal('2000.00'),
        forma_pago='transferencia',
        estado='completada',
        empresa_id=empresa.id,
        origen='tiendanube',
        tn_orden_id=123456789,
    )
    db.session.add(venta2)

    with pytest.raises(IntegrityError):
        db.session.commit()

    db.session.rollback()
