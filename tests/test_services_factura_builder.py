from datetime import date, datetime
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import Empresa, Producto, Usuario, Venta, VentaDetalle
from app.services.arca_client import ArcaClient
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


# ---------------------------------------------------------------------------
# Tests de estructura de payload ARCA
# ---------------------------------------------------------------------------


def _crear_empresa_ri():
    """Crea una empresa Responsable Inscripto para tests clase A/B."""
    empresa = Empresa(
        nombre='Empresa RI Builder',
        activa=True,
        aprobada=True,
        condicion_iva_id=1,
    )
    db.session.add(empresa)
    db.session.flush()
    return empresa


def _crear_detalle(venta_id, producto_id, cantidad, precio_unitario, iva_porcentaje, subtotal):
    """Helper para crear un VentaDetalle con Decimal."""
    detalle = VentaDetalle(
        venta_id=venta_id,
        producto_id=producto_id,
        cantidad=Decimal(str(cantidad)),
        precio_unitario=Decimal(str(precio_unitario)),
        iva_porcentaje=Decimal(str(iva_porcentaje)),
        subtotal=Decimal(str(subtotal)),
    )
    db.session.add(detalle)
    return detalle


def _extraer_detalle(payload):
    """Extrae el primer FECAEDetRequest del payload."""
    return payload['FeDetReq']['FECAEDetRequest'][0]


def test_payload_estructura_iva_con_wrapper_aliciva(app):
    """Valida que Iva contiene wrapper AlicIva con estructura correcta para clase A."""
    empresa = _crear_empresa_ri()
    usuario = _crear_usuario(empresa.id)
    prod_21 = _crear_producto(empresa.id, 'IVA21', 21)
    prod_105 = _crear_producto(empresa.id, 'IVA105', 10.5)

    # Factura A, receptor RI — precios con IVA incluido
    # Línea 1: $242.00 (neto ~200, IVA21 ~42)
    # Línea 2: $110.50 (neto ~100, IVA10.5 ~10.50)
    venta = _crear_venta(
        usuario.id,
        empresa.id,
        subtotal='352.50',
        descuento='0.00',
        total='352.50',
    )
    _crear_detalle(venta.id, prod_21.id, 1, '242.00', '21.00', '242.00')
    _crear_detalle(venta.id, prod_105.id, 1, '110.50', '10.50', '110.50')
    db.session.commit()

    payload = FacturaBuilder.desde_venta(
        venta=venta,
        tipo_comprobante=1,  # Factura A
        punto_venta=1,
        numero_comprobante=1,
        concepto=1,
        receptor={'doc_tipo': 80, 'doc_nro': 20111111112, 'condicion_iva_id': 1},
        precios_con_iva=True,
    )

    detalle = _extraer_detalle(payload)

    # Iva DEBE tener wrapper AlicIva (no lista plana)
    assert 'Iva' in detalle
    assert isinstance(detalle['Iva'], dict), 'Iva debe ser un dict con AlicIva'
    assert 'AlicIva' in detalle['Iva']
    alicuotas = detalle['Iva']['AlicIva']
    assert isinstance(alicuotas, list)
    assert len(alicuotas) == 2

    # Cada AlicIva debe tener Id, BaseImp, Importe como numeros
    for alic in alicuotas:
        assert 'Id' in alic
        assert 'BaseImp' in alic
        assert 'Importe' in alic
        assert isinstance(alic['Id'], (int, float))
        assert isinstance(alic['BaseImp'], (int, float))
        assert isinstance(alic['Importe'], (int, float))

    # Verificar que los IDs de alícuota son correctos (5=21%, 4=10.5%)
    ids = sorted(a['Id'] for a in alicuotas)
    assert ids == [4, 5], f'IDs de alícuota esperados [4, 5], obtenidos {ids}'


def test_payload_cbtes_asoc_con_wrapper(app):
    """Valida que CbtesAsoc contiene wrapper CbteAsoc para NC clase A."""
    builder = FacturaBuilder()
    builder.set_comprobante(3, 1, 10, concepto=1)  # NC tipo A
    builder.set_receptor(80, 20111111112)
    builder.set_condicion_iva_receptor(1)
    builder.set_importes(
        imp_total=Decimal('121.00'),
        imp_neto=Decimal('100.00'),
        imp_iva=Decimal('21.00'),
    )
    builder.add_iva(5, Decimal('100.00'), Decimal('21.00'))
    builder.set_comprobante_asociado(
        tipo_comprobante=1,
        punto_venta=1,
        numero_comprobante=5,
    )

    payload = builder.build()
    detalle = _extraer_detalle(payload)

    # CbtesAsoc DEBE tener wrapper CbteAsoc
    assert 'CbtesAsoc' in detalle
    assert isinstance(detalle['CbtesAsoc'], dict), 'CbtesAsoc debe ser un dict con CbteAsoc'
    assert 'CbteAsoc' in detalle['CbtesAsoc']
    asociados = detalle['CbtesAsoc']['CbteAsoc']
    assert isinstance(asociados, list)
    assert len(asociados) == 1

    asoc = asociados[0]
    assert asoc['Tipo'] == 1
    assert asoc['PtoVta'] == 1
    assert asoc['Nro'] == 5


def test_payload_clase_c_sin_iva(app):
    """Valida que clase C NO incluye Iva y que ImpIVA es 0."""
    empresa = _crear_empresa()  # Monotributo (condicion_iva_id=6)
    usuario = _crear_usuario(empresa.id)
    producto = _crear_producto(empresa.id, 'PRD-C2', 21)
    venta = _crear_venta(
        usuario.id,
        empresa.id,
        subtotal='500.00',
        descuento='0.00',
        total='500.00',
    )
    _crear_detalle(venta.id, producto.id, 2, '250.00', '21.00', '500.00')
    db.session.commit()

    payload = FacturaBuilder.desde_venta(
        venta=venta,
        tipo_comprobante=11,  # Factura C
        punto_venta=1,
        numero_comprobante=1,
        concepto=1,
        receptor={'doc_tipo': 99, 'doc_nro': 0, 'condicion_iva_id': 5},
    )

    detalle = _extraer_detalle(payload)
    assert 'Iva' not in detalle, 'Clase C no debe incluir Iva en el detalle'
    assert detalle['ImpIVA'] == 0.0, 'ImpIVA debe ser 0 para clase C'


def test_payload_clase_b_iva_incluido_en_neto(app):
    """Valida que clase B con precios_con_iva=True calcula neto sin IVA e incluye wrapper AlicIva."""
    empresa = _crear_empresa_ri()
    usuario = _crear_usuario(empresa.id)
    producto = _crear_producto(empresa.id, 'PRD-B1', 21)

    # Precio IVA incluido: $121 → neto=100, IVA=21
    venta = _crear_venta(
        usuario.id,
        empresa.id,
        subtotal='121.00',
        descuento='0.00',
        total='121.00',
    )
    _crear_detalle(venta.id, producto.id, 1, '121.00', '21.00', '121.00')
    db.session.commit()

    payload = FacturaBuilder.desde_venta(
        venta=venta,
        tipo_comprobante=6,  # Factura B
        punto_venta=1,
        numero_comprobante=1,
        concepto=1,
        receptor={'doc_tipo': 96, 'doc_nro': 12345678, 'condicion_iva_id': 5},
        precios_con_iva=True,
    )

    detalle = _extraer_detalle(payload)

    # ImpNeto debe ser neto gravado = 121 / 1.21 = 100
    assert (
        abs(detalle['ImpNeto'] - 100.00) < 0.02
    ), f"ImpNeto esperado ~100.00, obtenido {detalle['ImpNeto']}"
    assert (
        abs(detalle['ImpIVA'] - 21.00) < 0.02
    ), f"ImpIVA esperado ~21.00, obtenido {detalle['ImpIVA']}"

    # Iva debe tener wrapper AlicIva
    assert 'Iva' in detalle
    assert isinstance(detalle['Iva'], dict)
    assert 'AlicIva' in detalle['Iva']
    alicuotas = detalle['Iva']['AlicIva']
    assert len(alicuotas) == 1
    assert alicuotas[0]['Id'] == 5  # 21% = alícuota ARCA 5


def test_payload_servicios_requiere_fechas(app):
    """Valida que concepto=2 (servicios) incluye FchServDesde/Hasta/VtoPago en formato YYYYMMDD."""
    builder = FacturaBuilder()
    builder.set_comprobante(6, 1, 10, concepto=2)
    builder.set_receptor(99, 0)
    builder.set_condicion_iva_receptor(5)
    builder.set_importes(
        imp_total=Decimal('100.00'),
        imp_neto=Decimal('82.64'),
        imp_iva=Decimal('17.36'),
    )
    builder.add_iva(5, Decimal('82.64'), Decimal('17.36'))
    builder.set_fechas(
        fecha_emision=date(2026, 3, 1),
        fch_serv_desde=date(2026, 2, 1),
        fch_serv_hasta=date(2026, 2, 28),
        fch_vto_pago=date(2026, 3, 15),
    )

    payload = builder.build()
    detalle = _extraer_detalle(payload)

    assert 'FchServDesde' in detalle
    assert 'FchServHasta' in detalle
    assert 'FchVtoPago' in detalle

    # Formato YYYYMMDD
    import re

    patron_yyyymmdd = re.compile(r'^\d{8}$')
    assert patron_yyyymmdd.match(
        detalle['FchServDesde']
    ), f"FchServDesde no es YYYYMMDD: {detalle['FchServDesde']}"
    assert patron_yyyymmdd.match(
        detalle['FchServHasta']
    ), f"FchServHasta no es YYYYMMDD: {detalle['FchServHasta']}"
    assert patron_yyyymmdd.match(
        detalle['FchVtoPago']
    ), f"FchVtoPago no es YYYYMMDD: {detalle['FchVtoPago']}"

    assert detalle['FchServDesde'] == '20260201'
    assert detalle['FchServHasta'] == '20260228'
    assert detalle['FchVtoPago'] == '20260315'


def test_payload_nc_sin_asociado_falla(app):
    """Valida que construir NC sin comprobante asociado lanza ArcaValidationError."""
    builder = FacturaBuilder()
    builder.set_comprobante(3, 1, 10, concepto=1)  # NC tipo A
    builder.set_receptor(80, 20111111112)
    builder.set_condicion_iva_receptor(1)
    builder.set_importes(
        imp_total=Decimal('121.00'),
        imp_neto=Decimal('100.00'),
        imp_iva=Decimal('21.00'),
    )
    builder.add_iva(5, Decimal('100.00'), Decimal('21.00'))

    with pytest.raises(ArcaValidationError, match='requiere comprobante asociado'):
        builder.build()


def test_payload_ecuacion_importes_cuadra(app):
    """Valida ImpTotal == ImpNeto + ImpIVA + ImpTotConc + ImpOpEx + ImpTrib con multiples alícuotas y descuento."""
    empresa = _crear_empresa_ri()
    usuario = _crear_usuario(empresa.id)
    prod_21 = _crear_producto(empresa.id, 'EQ21', 21)
    prod_105 = _crear_producto(empresa.id, 'EQ105', 10.5)

    # Dos líneas con descuento, precios con IVA incluido
    # Línea 1: $605.00 (IVA 21%)
    # Línea 2: $221.00 (IVA 10.5%)
    # Subtotal: $826.00, Descuento: $26.00, Total: $800.00
    venta = _crear_venta(
        usuario.id,
        empresa.id,
        subtotal='826.00',
        descuento='26.00',
        total='800.00',
    )
    _crear_detalle(venta.id, prod_21.id, 5, '121.00', '21.00', '605.00')
    _crear_detalle(venta.id, prod_105.id, 2, '110.50', '10.50', '221.00')
    db.session.commit()

    payload = FacturaBuilder.desde_venta(
        venta=venta,
        tipo_comprobante=1,  # Factura A
        punto_venta=2,
        numero_comprobante=100,
        concepto=1,
        receptor={'doc_tipo': 80, 'doc_nro': 20222222223, 'condicion_iva_id': 1},
        precios_con_iva=True,
    )

    detalle = _extraer_detalle(payload)

    # La ecuación ARCA: ImpTotal == ImpNeto + ImpIVA + ImpTotConc + ImpOpEx + ImpTrib
    suma = (
        detalle['ImpNeto']
        + detalle['ImpIVA']
        + detalle['ImpTotConc']
        + detalle['ImpOpEx']
        + detalle['ImpTrib']
    )
    assert round(detalle['ImpTotal'], 2) == round(suma, 2), (
        f"Ecuación no cuadra: ImpTotal={detalle['ImpTotal']}, " f"suma componentes={suma}"
    )

    # Verificar que todos los importes son float (no Decimal)
    for campo in ('ImpTotal', 'ImpNeto', 'ImpIVA', 'ImpTotConc', 'ImpOpEx', 'ImpTrib'):
        assert isinstance(
            detalle[campo], float
        ), f'{campo} debe ser float, es {type(detalle[campo])}'


def test_padron_inferencia_condicion_iva_ri(app):
    """Valida que _normalizar_condicion_iva infiere RI (id=1) desde texto descriptivo de ARCA."""
    condicion_iva, condicion_iva_id = ArcaClient._normalizar_condicion_iva(
        'IVA Responsable Inscripto',
        None,
    )
    assert (
        condicion_iva_id == 1
    ), f'Esperado condicion_iva_id=1 para RI, obtenido {condicion_iva_id}'


def test_padron_inferencia_condicion_iva_monotributo(app):
    """Valida que _normalizar_condicion_iva infiere Monotributo (id=6) desde texto descriptivo."""
    condicion_iva, condicion_iva_id = ArcaClient._normalizar_condicion_iva(
        'Responsable Monotributo',
        None,
    )
    assert (
        condicion_iva_id == 6
    ), f'Esperado condicion_iva_id=6 para Monotributo, obtenido {condicion_iva_id}'
