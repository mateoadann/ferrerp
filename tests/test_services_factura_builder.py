from datetime import datetime
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import Empresa, Producto, Usuario, Venta, VentaDetalle
from app.services.arca_exceptions import ArcaValidationError
from app.services.factura_builder import FacturaBuilder


def _crear_empresa():
    empresa = Empresa(
        nombre='Empresa Builder',
        activa=True,
        aprobada=True,
        condicion_iva_id=6,
    )
    db.session.add(empresa)
    db.session.flush()
    return empresa


def _crear_usuario(empresa_id):
    usuario = Usuario(
        email='builder@ferrerp.test',
        nombre='Usuario Builder',
        rol='vendedor',
        activo=True,
        empresa_id=empresa_id,
    )
    usuario.set_password('clave')
    db.session.add(usuario)
    db.session.flush()
    return usuario


def _crear_producto(empresa_id, codigo, iva_porcentaje):
    producto = Producto(
        codigo=codigo,
        nombre=f'Producto {codigo}',
        unidad_medida='unidad',
        precio_costo=Decimal('5.00'),
        precio_venta=Decimal('12.10'),
        iva_porcentaje=Decimal(str(iva_porcentaje)),
        stock_actual=Decimal('10.000'),
        stock_minimo=Decimal('1.000'),
        activo=True,
        empresa_id=empresa_id,
    )
    db.session.add(producto)
    db.session.flush()
    return producto


def _crear_venta(usuario_id, empresa_id, subtotal='121.00', descuento='10.00', total='111.00'):
    venta = Venta(
        numero=1,
        fecha=datetime(2026, 3, 12, 10, 0, 0),
        usuario_id=usuario_id,
        subtotal=Decimal(subtotal),
        descuento_monto=Decimal(descuento),
        descuento_porcentaje=Decimal('0'),
        total=Decimal(total),
        forma_pago='efectivo',
        estado='completada',
        empresa_id=empresa_id,
    )
    db.session.add(venta)
    db.session.flush()
    return venta


def test_clase_c_no_envia_iva(app):
    empresa = _crear_empresa()
    usuario = _crear_usuario(empresa.id)
    producto = _crear_producto(empresa.id, 'PRD-C', 21)
    venta = _crear_venta(
        usuario.id, empresa.id, subtotal='121.00', descuento='0.00', total='121.00'
    )

    detalle = VentaDetalle(
        venta_id=venta.id,
        producto_id=producto.id,
        cantidad=Decimal('1.000'),
        precio_unitario=Decimal('121.00'),
        iva_porcentaje=Decimal('21.00'),
        subtotal=Decimal('121.00'),
    )
    db.session.add(detalle)
    db.session.commit()

    request = FacturaBuilder.desde_venta(
        venta=venta,
        tipo_comprobante=11,
        punto_venta=1,
        numero_comprobante=1,
        concepto=1,
        receptor={'doc_tipo': 99, 'doc_nro': 0, 'condicion_iva_id': 5},
    )

    detalle_req = request['FeDetReq']['FECAEDetRequest'][0]
    assert 'Iva' not in detalle_req
    assert detalle_req['ImpIVA'] == 0.0


def test_balancea_ecuacion_con_redondeo_y_descuento(app):
    empresa = _crear_empresa()
    usuario = _crear_usuario(empresa.id)
    producto_a = _crear_producto(empresa.id, 'PRD-A', 21)
    producto_b = _crear_producto(empresa.id, 'PRD-B', 10.5)
    venta = _crear_venta(
        usuario.id, empresa.id, subtotal='133.10', descuento='3.10', total='130.00'
    )

    db.session.add_all(
        [
            VentaDetalle(
                venta_id=venta.id,
                producto_id=producto_a.id,
                cantidad=Decimal('1.000'),
                precio_unitario=Decimal('121.00'),
                iva_porcentaje=Decimal('21.00'),
                subtotal=Decimal('121.00'),
            ),
            VentaDetalle(
                venta_id=venta.id,
                producto_id=producto_b.id,
                cantidad=Decimal('1.000'),
                precio_unitario=Decimal('12.10'),
                iva_porcentaje=Decimal('10.50'),
                subtotal=Decimal('12.10'),
            ),
        ]
    )
    db.session.commit()

    request = FacturaBuilder.desde_venta(
        venta=venta,
        tipo_comprobante=6,
        punto_venta=2,
        numero_comprobante=15,
        concepto=1,
        receptor={'doc_tipo': 99, 'doc_nro': 0, 'condicion_iva_id': 5},
    )

    det = request['FeDetReq']['FECAEDetRequest'][0]
    suma = det['ImpNeto'] + det['ImpIVA'] + det['ImpTotConc'] + det['ImpOpEx'] + det['ImpTrib']
    assert round(det['ImpTotal'], 2) == round(suma, 2)


def test_servicios_requiere_fechas(app):
    builder = FacturaBuilder()
    builder.set_comprobante(6, 1, 10, concepto=2)
    builder.set_receptor(99, 0)
    builder.set_condicion_iva_receptor(5)
    builder.set_importes(100, 82.64, 17.36)

    with pytest.raises(ArcaValidationError, match='se requieren FchServDesde'):
        builder.build()


def test_nc_requiere_comprobante_asociado(app):
    builder = FacturaBuilder()
    builder.set_comprobante(3, 1, 10, concepto=1)
    builder.set_receptor(99, 0)
    builder.set_condicion_iva_receptor(5)
    builder.set_importes(100, 100, 0)

    with pytest.raises(ArcaValidationError, match='requiere comprobante asociado'):
        builder.build()
