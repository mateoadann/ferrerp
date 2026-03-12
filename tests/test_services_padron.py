"""Tests para el servicio de consulta de padrón ARCA."""

import pytest

from app.extensions import db
from app.models import Empresa
from app.services.arca_exceptions import ArcaNetworkError, ArcaValidationError
from app.services.padron_service import PadronService


class FakeArcaClientOk:
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

    def consultar_padron(self, cuit_consulta):
        return {
            'success': True,
            'data': {
                'cuit': cuit_consulta,
                'razon_social': 'Cliente de Prueba SA',
                'condicion_iva': 'IVA Responsable Inscripto',
                'condicion_iva_id': 1,
                'doc_tipo': 80,
                'doc_nro': cuit_consulta,
            },
            'raw': {'fake': True},
        }

    def close(self):
        return None


class FakeArcaClientErrorRed(FakeArcaClientOk):
    def consultar_padron(self, cuit_consulta):
        raise ArcaNetworkError('Timeout consultando padrón.', detalle='timeout')


def _crear_empresa_arca_habilitada():
    empresa = Empresa(
        nombre='Empresa Padrón',
        activa=True,
        aprobada=True,
        cuit='20-12345678-3',
        certificado_arca=b'cert',
        clave_privada_arca=b'key',
        ambiente_arca='testing',
        arca_habilitado=True,
    )
    db.session.add(empresa)
    db.session.commit()
    return empresa


def test_consultar_cliente_devuelve_datos_normalizados(app):
    empresa = _crear_empresa_arca_habilitada()
    servicio = PadronService(arca_client_cls=FakeArcaClientOk)

    resultado = servicio.consultar_cliente('20-11112222-3', empresa)

    assert resultado['success'] is True
    assert resultado['data']['cuit'] == '20111122223'
    assert resultado['data']['razon_social'] == 'Cliente de Prueba SA'
    assert resultado['data']['condicion_iva_id'] == 1


def test_consultar_cliente_falla_con_cuit_invalido(app):
    empresa = _crear_empresa_arca_habilitada()
    servicio = PadronService(arca_client_cls=FakeArcaClientOk)

    with pytest.raises(ArcaValidationError, match='11 dígitos'):
        servicio.consultar_cliente('20-123', empresa)


def test_consultar_cliente_falla_sin_configuracion_arca(app):
    empresa = Empresa(nombre='Sin ARCA', activa=True, aprobada=True)
    db.session.add(empresa)
    db.session.commit()

    servicio = PadronService(arca_client_cls=FakeArcaClientOk)

    with pytest.raises(ArcaValidationError, match='Configuración ARCA incompleta'):
        servicio.consultar_cliente('20111122223', empresa)


def test_consultar_cliente_propaga_error_de_red(app):
    empresa = _crear_empresa_arca_habilitada()
    servicio = PadronService(arca_client_cls=FakeArcaClientErrorRed)

    with pytest.raises(ArcaNetworkError, match='Timeout consultando padrón'):
        servicio.consultar_cliente('20111122223', empresa)
