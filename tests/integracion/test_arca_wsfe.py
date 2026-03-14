"""
Tests de integración con ARCA WSFE (homologación).

Estos tests se conectan al ambiente real de homologación de ARCA.
Requieren certificado y clave privada de testing.

Ejecutar:
    pytest -m integracion_arca --arca-test -v
    pytest tests/integracion/test_arca_wsfe.py --arca-test -v
"""

from datetime import date
from decimal import Decimal

import pytest

from app.services.factura_builder import FacturaBuilder

# Tipo 11 = Factura C (más simple, no requiere desglose IVA)
TIPO_FACTURA_C = 11


@pytest.mark.integracion_arca
class TestConexionWSFE:
    """Tests de conexión y autenticación contra WSFE homologación."""

    def test_autenticar_wsfe(self, arca_client):
        """Verifica que se pueda autenticar contra WSAA y obtener token."""
        # La autenticación ocurre lazy al primer uso de WSFE.
        # Consultamos último autorizado como prueba de que la autenticación funciona.
        resultado = arca_client.fe_comp_ultimo_autorizado(1, TIPO_FACTURA_C)
        assert isinstance(resultado, int)
        assert resultado >= 0

    def test_obtener_ultimo_comprobante(self, wsfe_service, punto_venta):
        """Verifica consulta de último comprobante autorizado."""
        ultimo = wsfe_service.ultimo_autorizado(punto_venta, TIPO_FACTURA_C)
        assert isinstance(ultimo, int)
        assert ultimo >= 0


@pytest.mark.integracion_arca
class TestEmisionFacturaC:
    """Tests de emisión de Factura C contra ARCA homologación.

    Factura C es la más simple: no requiere desglose de IVA,
    ideal para monotributistas y exentos.
    """

    def _construir_factura_c(self, punto_venta, numero, imp_total):
        """Helper para construir payload de Factura C básica."""
        builder = FacturaBuilder()
        builder.set_comprobante(
            tipo_comprobante=TIPO_FACTURA_C,
            punto_venta=punto_venta,
            numero_comprobante=numero,
            concepto=1,  # Productos
        )
        builder.set_fechas(fecha_emision=date.today())
        builder.set_receptor(doc_tipo=99, doc_nro=0)  # Consumidor Final
        builder.set_condicion_iva_receptor(5)  # Consumidor Final
        builder.set_importes(
            imp_total=imp_total,
            imp_neto=imp_total,
            imp_iva=Decimal('0'),
        )
        builder.set_moneda('PES', Decimal('1'))
        return builder.build()

    def test_emitir_factura_c_basica(self, wsfe_service, punto_venta):
        """Emite una Factura C básica con un solo ítem."""
        ultimo = wsfe_service.ultimo_autorizado(punto_venta, TIPO_FACTURA_C)
        numero = ultimo + 1

        request_data = self._construir_factura_c(
            punto_venta=punto_venta,
            numero=numero,
            imp_total=Decimal('1500.00'),
        )

        respuesta = wsfe_service.autorizar(request_data)

        assert respuesta['resultado'] == 'A'
        assert respuesta['cae'] is not None
        assert len(str(respuesta['cae'])) == 14
        assert respuesta['numero_comprobante'] == numero

    def test_emitir_factura_c_multiples_items(self, wsfe_service, punto_venta):
        """Emite una Factura C simulando múltiples ítems (total agregado)."""
        ultimo = wsfe_service.ultimo_autorizado(punto_venta, TIPO_FACTURA_C)
        numero = ultimo + 1

        # ARCA no conoce los ítems individuales, solo los totales
        total = Decimal('100.50') + Decimal('250.00') + Decimal('75.99')
        request_data = self._construir_factura_c(
            punto_venta=punto_venta,
            numero=numero,
            imp_total=total,
        )

        respuesta = wsfe_service.autorizar(request_data)

        assert respuesta['resultado'] == 'A'
        assert respuesta['cae'] is not None

    def test_emitir_factura_c_obtiene_cae(self, wsfe_service, punto_venta):
        """Verifica que el CAE obtenido cumple con el formato esperado."""
        ultimo = wsfe_service.ultimo_autorizado(punto_venta, TIPO_FACTURA_C)
        numero = ultimo + 1

        request_data = self._construir_factura_c(
            punto_venta=punto_venta,
            numero=numero,
            imp_total=Decimal('999.99'),
        )

        respuesta = wsfe_service.autorizar(request_data)

        assert respuesta['resultado'] == 'A'

        # CAE es un número de 14 dígitos
        cae = str(respuesta['cae'])
        assert cae.isdigit(), f'CAE no es numérico: {cae}'
        assert len(cae) == 14, f'CAE no tiene 14 dígitos: {cae}'

        # Vencimiento del CAE debe ser una fecha válida
        assert respuesta['cae_vencimiento'] is not None
        vencimiento = respuesta['cae_vencimiento']
        if hasattr(vencimiento, 'year'):
            assert vencimiento >= date.today()


@pytest.mark.integracion_arca
class TestValidacionesWSFE:
    """Tests de validación y rechazo por parte de ARCA."""

    def test_emitir_factura_importe_desbalanceado(self, wsfe_service, punto_venta):
        """ARCA debe rechazar cuando los importes no cuadran.

        ImpTotal debe ser igual a ImpNeto + ImpIVA + ImpTotConc + ImpOpEx + ImpTrib.
        Forzamos un desbalance saltando la validación del builder.
        """
        from app.services.arca_exceptions import ArcaRechazoError

        ultimo = wsfe_service.ultimo_autorizado(punto_venta, TIPO_FACTURA_C)
        numero = ultimo + 1

        # Construir payload manualmente con importes desbalanceados
        request_data = {
            'FeCabReq': {
                'CantReg': 1,
                'PtoVta': punto_venta,
                'CbteTipo': TIPO_FACTURA_C,
            },
            'FeDetReq': {
                'FECAEDetRequest': [
                    {
                        'Concepto': 1,
                        'DocTipo': 99,
                        'DocNro': 0,
                        'CbteDesde': numero,
                        'CbteHasta': numero,
                        'CbteFch': date.today().strftime('%Y%m%d'),
                        'ImpTotal': 1000.00,
                        'ImpTotConc': 0,
                        'ImpNeto': 500.00,  # Intencionalmente desbalanceado
                        'ImpOpEx': 0,
                        'ImpTrib': 0,
                        'ImpIVA': 0,
                        'MonId': 'PES',
                        'MonCotiz': 1,
                        'CondicionIVAReceptorId': 5,
                    }
                ]
            },
        }

        with pytest.raises(ArcaRechazoError) as exc_info:
            wsfe_service.autorizar(request_data)

        assert exc_info.value.errores or exc_info.value.observaciones

    def test_emitir_factura_numero_duplicado(self, wsfe_service, punto_venta):
        """ARCA debe rechazar un comprobante con número ya utilizado."""
        from app.services.arca_exceptions import ArcaRechazoError

        ultimo = wsfe_service.ultimo_autorizado(punto_venta, TIPO_FACTURA_C)

        if ultimo == 0:
            pytest.skip('No hay comprobantes previos para probar duplicado')

        # Intentar emitir con un número ya autorizado
        builder = FacturaBuilder()
        builder.set_comprobante(
            tipo_comprobante=TIPO_FACTURA_C,
            punto_venta=punto_venta,
            numero_comprobante=ultimo,  # Número ya usado
            concepto=1,
        )
        builder.set_fechas(fecha_emision=date.today())
        builder.set_receptor(doc_tipo=99, doc_nro=0)
        builder.set_condicion_iva_receptor(5)
        builder.set_importes(
            imp_total=Decimal('100.00'),
            imp_neto=Decimal('100.00'),
            imp_iva=Decimal('0'),
        )
        builder.set_moneda('PES', Decimal('1'))
        request_data = builder.build()

        with pytest.raises(ArcaRechazoError) as exc_info:
            wsfe_service.autorizar(request_data)

        # Error 10016 = comprobante fuera de secuencia
        errores_texto = str(exc_info.value.errores) + str(exc_info.value.observaciones)
        assert '10016' in errores_texto or exc_info.value.codigo == '10016'
