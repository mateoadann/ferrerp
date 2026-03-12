"""Servicio para consultar padrón ARCA de clientes."""

import re

from .arca_client import ArcaClient
from .arca_exceptions import ArcaAuthError, ArcaNetworkError, ArcaValidationError


class PadronService:
    """Encapsula la consulta de padrón para uso en rutas y validaciones."""

    def __init__(self, arca_client_cls=ArcaClient):
        self.arca_client_cls = arca_client_cls

    @staticmethod
    def _normalizar_cuit(cuit):
        """Normaliza CUIT a solo dígitos."""
        return re.sub(r'\D+', '', str(cuit or ''))

    @staticmethod
    def _validar_configuracion_empresa(empresa):
        """Valida que la empresa tenga configurada integración ARCA."""
        if not empresa:
            raise ArcaValidationError('Empresa no encontrada.')

        faltantes = []
        if not empresa.arca_habilitado:
            faltantes.append('arca_habilitado')
        if not empresa.certificado_arca:
            faltantes.append('certificado_arca')
        if not empresa.clave_privada_arca:
            faltantes.append('clave_privada_arca')
        if not empresa.cuit:
            faltantes.append('cuit')

        if faltantes:
            raise ArcaValidationError(
                f'Configuración ARCA incompleta: {", ".join(faltantes)}',
            )

    def consultar_cliente(self, cuit_consulta, empresa):
        """Consulta datos fiscales de un cliente por CUIT en padrón ARCA."""
        self._validar_configuracion_empresa(empresa)

        cuit_norm = self._normalizar_cuit(cuit_consulta)
        if len(cuit_norm) != 11:
            raise ArcaValidationError('El CUIT a consultar debe contener 11 dígitos.')

        arca_client = self.arca_client_cls(
            cuit=empresa.cuit,
            certificado=empresa.certificado_arca,
            clave_privada=empresa.clave_privada_arca,
            ambiente=empresa.ambiente_arca or 'testing',
        )

        try:
            return arca_client.consultar_padron(cuit_norm)
        except (ArcaAuthError, ArcaNetworkError):
            raise
        finally:
            arca_client.close()
