"""
Tests de integración con ARCA Padrón / WS_SR_CONSTANCIA_INSCRIPCION (homologación).

Estos tests consultan el padrón real de homologación de ARCA.
Requieren certificado y clave privada de testing.

Ejecutar:
    pytest -m integracion_arca --arca-test -v
    pytest tests/integracion/test_arca_padron.py --arca-test -v
"""

import pytest

# CUIT de AFIP (ente público, siempre existe en el padrón)
CUIT_AFIP = '33693450239'

# CUIT inexistente (secuencia inválida por dígito verificador)
CUIT_INEXISTENTE = '20000000004'


@pytest.mark.integracion_arca
class TestPadronARCA:
    """Tests de consulta al padrón de ARCA en homologación."""

    def test_consultar_padron_cuit_afip(self, arca_client):
        """Consulta el CUIT de AFIP — debe existir siempre en el padrón."""
        resultado = arca_client.consultar_padron(CUIT_AFIP)

        assert resultado['success'] is True
        assert 'data' in resultado
        datos = resultado['data']
        assert datos['cuit'] == CUIT_AFIP
        assert datos['razon_social']  # No vacío
        assert len(datos['razon_social']) > 0

    def test_consultar_padron_cuit_inexistente(self, arca_client):
        """Consulta un CUIT inexistente — debe retornar success=False."""
        resultado = arca_client.consultar_padron(CUIT_INEXISTENTE)

        assert resultado['success'] is False
        assert 'error' in resultado
        assert resultado['error']  # Mensaje de error no vacío

    def test_consultar_padron_extrae_condicion_iva(self, arca_client):
        """Verifica que se extrae la condición IVA del padrón."""
        resultado = arca_client.consultar_padron(CUIT_AFIP)

        assert resultado['success'] is True
        datos = resultado['data']

        # Debe tener condicion_iva (texto) y condicion_iva_id (int)
        assert datos.get('condicion_iva') is not None
        assert datos.get('condicion_iva_id') is not None
        assert isinstance(datos['condicion_iva_id'], int)
        assert datos['condicion_iva_id'] > 0

    def test_consultar_padron_retorna_doc_tipo(self, arca_client):
        """Verifica que se retorna tipo de documento del contribuyente."""
        resultado = arca_client.consultar_padron(CUIT_AFIP)

        assert resultado['success'] is True
        datos = resultado['data']

        # doc_tipo 80 = CUIT
        assert datos.get('doc_tipo') == 80
        assert datos.get('doc_nro') is not None

    def test_consultar_padron_cuit_con_guiones(self, arca_client):
        """Verifica que el CUIT se normaliza correctamente (acepta guiones)."""
        cuit_con_guiones = '33-69345023-9'
        resultado = arca_client.consultar_padron(cuit_con_guiones)

        assert resultado['success'] is True
        # El CUIT devuelto debe estar sin guiones
        assert resultado['data']['cuit'] == CUIT_AFIP
