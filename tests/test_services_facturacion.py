from datetime import datetime
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import Cliente, Empresa, Factura, Producto, Usuario, Venta, VentaDetalle
from app.services.arca_exceptions import ArcaRechazoError, ArcaValidationError
from app.services.facturacion_service import FacturacionService


class FakeArcaClient:
    def __init__(
        self,
        cuit,
        certificado,
        clave_privada,
        ambiente='testing',
        ta_cache_root=None,
        enable_logging=False,
    ):
        self.cuit = cuit
        self.certificado = certificado
        self.clave_privada = clave_privada
        self.ambiente = ambiente

    def close(self):
        return None


class FakeWSFEService:
    resultado = 'A'
    cae = '12345678901234'
    cae_vencimiento = '20260415'
    errores = []
    observaciones = []
    ultimo = 100

    def __init__(self, arca_client):
        self.arca_client = arca_client

    def ultimo_autorizado(self, punto_venta, tipo_cbte):
        return self.__class__.ultimo

    def autorizar(self, request_data):
        if self.__class__.resultado == 'A':
            return {
                'resultado': 'A',
                'cae': self.__class__.cae,
                'cae_vencimiento': self.__class__.cae_vencimiento,
                'numero_comprobante': request_data['FeDetReq']['FECAEDetRequest'][0]['CbteDesde'],
                'errores': [],
                'observaciones': [],
                'raw': {'ok': True},
            }

        raise ArcaRechazoError(
            'Rechazado por ARCA',
            codigo='10000',
            detalle={'resultado': 'R'},
            errores=self.__class__.errores,
            observaciones=self.__class__.observaciones,
        )

    def consultar_comprobante(self, tipo_cbte, punto_venta, numero):
        return {'numero_comprobante': numero}

    @staticmethod
    def es_error_secuencia(error_or_payload):
        return False


def _crear_empresa_valida():
    empresa = Empresa(
        nombre='Empresa Facturacion',
        activa=True,
        aprobada=True,
        cuit='20-12345678-3',
        condicion_iva_id=1,
        punto_venta_arca=1,
        certificado_arca=b'cert',
        clave_privada_arca=b'key',
        ambiente_arca='testing',
        arca_habilitado=True,
    )
    db.session.add(empresa)
    db.session.flush()
    return empresa


def _crear_usuario(empresa_id):
    usuario = Usuario(
        email='facturacion@ferrerp.test',
        nombre='Usuario Facturacion',
        rol='vendedor',
        activo=True,
        empresa_id=empresa_id,
    )
    usuario.set_password('clave')
    db.session.add(usuario)
    db.session.flush()
    return usuario


def _crear_cliente(empresa_id):
    cliente = Cliente(
        nombre='Cliente Fiscal',
        dni_cuit='20111222333',
        razon_social='Cliente Fiscal SA',
        condicion_iva_id=5,
        doc_tipo=80,
        activo=True,
        empresa_id=empresa_id,
    )
    db.session.add(cliente)
    db.session.flush()
    return cliente


def _crear_venta(empresa_id, usuario_id, cliente_id=None):
    producto = Producto(
        codigo='PRD-FAC',
        nombre='Producto Facturable',
        unidad_medida='unidad',
        precio_costo=Decimal('50.00'),
        precio_venta=Decimal('121.00'),
        iva_porcentaje=Decimal('21.00'),
        stock_actual=Decimal('10.000'),
        stock_minimo=Decimal('1.000'),
        activo=True,
        empresa_id=empresa_id,
    )
    db.session.add(producto)
    db.session.flush()

    venta = Venta(
        numero=1,
        fecha=datetime(2026, 3, 12, 10, 0, 0),
        cliente_id=cliente_id,
        usuario_id=usuario_id,
        subtotal=Decimal('121.00'),
        descuento_porcentaje=Decimal('0.00'),
        descuento_monto=Decimal('0.00'),
        total=Decimal('121.00'),
        forma_pago='efectivo',
        estado='completada',
        empresa_id=empresa_id,
    )
    db.session.add(venta)
    db.session.flush()

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
    return venta


def _service():
    return FacturacionService(
        arca_client_cls=FakeArcaClient,
        wsfe_service_cls=FakeWSFEService,
    )


def test_emision_exitosa_actualiza_factura_autorizada(app):
    FakeWSFEService.resultado = 'A'
    empresa = _crear_empresa_valida()
    usuario = _crear_usuario(empresa.id)
    cliente = _crear_cliente(empresa.id)
    venta = _crear_venta(empresa.id, usuario.id, cliente.id)

    factura = _service().emitir_factura_desde_venta(
        venta_id=venta.id,
        empresa_id=empresa.id,
    )

    assert factura.estado == 'autorizada'
    assert factura.cae == FakeWSFEService.cae
    assert factura.arca_response == {'ok': True}


def test_rechazo_guarda_error_y_estado_rechazada(app):
    FakeWSFEService.resultado = 'R'
    FakeWSFEService.errores = [{'Code': 10000, 'Msg': 'Error de validacion'}]
    empresa = _crear_empresa_valida()
    usuario = _crear_usuario(empresa.id)
    venta = _crear_venta(empresa.id, usuario.id, None)

    factura = _service().emitir_factura_desde_venta(
        venta_id=venta.id,
        empresa_id=empresa.id,
    )

    assert factura.estado == 'rechazada'
    assert factura.error_codigo == '10000'
    assert 'Rechazado' in factura.error_mensaje


def test_bloquea_duplicado_mismo_tipo_y_venta(app):
    FakeWSFEService.resultado = 'A'
    empresa = _crear_empresa_valida()
    usuario = _crear_usuario(empresa.id)
    venta = _crear_venta(empresa.id, usuario.id)

    existente = Factura(
        venta_id=venta.id,
        empresa_id=empresa.id,
        tipo_comprobante=6,
        punto_venta=1,
        numero_comprobante=10,
        concepto=1,
        fecha_emision=venta.fecha.date(),
        doc_tipo_receptor=99,
        doc_nro_receptor='0',
        condicion_iva_receptor_id=5,
        imp_total=Decimal('100.00'),
        estado='autorizada',
    )
    db.session.add(existente)
    db.session.commit()

    with pytest.raises(ArcaValidationError, match='Ya existe factura autorizada'):
        _service().emitir_factura_desde_venta(
            venta_id=venta.id,
            empresa_id=empresa.id,
            tipo_comprobante=6,
        )


def test_falta_configuracion_arca_lanza_error(app):
    empresa = Empresa(nombre='Empresa Sin ARCA', activa=True, aprobada=True)
    db.session.add(empresa)
    db.session.flush()
    usuario = _crear_usuario(empresa.id)
    venta = _crear_venta(empresa.id, usuario.id)

    with pytest.raises(ArcaValidationError, match='Configuracion ARCA incompleta'):
        _service().emitir_factura_desde_venta(
            venta_id=venta.id,
            empresa_id=empresa.id,
        )


def test_reintenta_una_vez_en_error_de_secuencia_10016(app):
    class FakeWSFEServiceSecuencia(FakeWSFEService):
        llamadas_ultimo = 0
        llamadas_autorizar = 0

        def ultimo_autorizado(self, punto_venta, tipo_cbte):
            self.__class__.llamadas_ultimo += 1
            if self.__class__.llamadas_ultimo == 1:
                return 100
            return 101

        def autorizar(self, request_data):
            self.__class__.llamadas_autorizar += 1
            if self.__class__.llamadas_autorizar == 1:
                raise ArcaRechazoError(
                    'Secuencia invalida',
                    codigo='10016',
                    detalle={'resultado': 'R'},
                    errores=[{'Code': 10016, 'Msg': 'Cbte fuera de secuencia'}],
                    observaciones=[],
                )

            return {
                'resultado': 'A',
                'cae': '12345678901234',
                'cae_vencimiento': '20260415',
                'numero_comprobante': request_data['FeDetReq']['FECAEDetRequest'][0]['CbteDesde'],
                'errores': [],
                'observaciones': [],
                'raw': {'ok': True, 'retry': True},
            }

        @staticmethod
        def es_error_secuencia(error_or_payload):
            if isinstance(error_or_payload, ArcaRechazoError):
                return str(error_or_payload.codigo) == '10016'
            return False

    empresa = _crear_empresa_valida()
    usuario = _crear_usuario(empresa.id)
    venta = _crear_venta(empresa.id, usuario.id)

    servicio = FacturacionService(
        arca_client_cls=FakeArcaClient,
        wsfe_service_cls=FakeWSFEServiceSecuencia,
    )
    factura = servicio.emitir_factura_desde_venta(venta.id, empresa.id)

    assert factura.estado == 'autorizada'
    assert factura.numero_comprobante == 102
