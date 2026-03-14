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
    def _es_facturador(obj):
        """Determina si el objeto es un Facturador (vs Empresa) por duck-typing."""
        return hasattr(obj, 'certificado') and not hasattr(obj, 'certificado_arca')

    @staticmethod
    def _validar_configuracion_facturador(facturador):
        """Valida que el facturador tenga configuración ARCA completa."""
        if not facturador:
            raise ArcaValidationError('Facturador no encontrado.')

        if not facturador.activo:
            raise ArcaValidationError('El facturador no está activo.')

        if not facturador.habilitado:
            raise ArcaValidationError('El facturador no está habilitado.')

        faltantes = []
        if not facturador.cuit:
            faltantes.append('cuit')
        if not facturador.certificado:
            faltantes.append('certificado')
        if not facturador.clave_privada:
            faltantes.append('clave_privada')

        if faltantes:
            raise ArcaValidationError(
                f'Configuración ARCA del facturador incompleta: {", ".join(faltantes)}',
            )

    @staticmethod
    def _validar_configuracion_empresa(empresa):
        """Valida que la empresa tenga configurada integración ARCA (compatibilidad)."""
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

    def consultar_cliente(self, cuit_consulta, facturador_o_empresa):
        """Consulta datos fiscales de un cliente por CUIT en padrón ARCA.

        Acepta un Facturador o una Empresa para mantener compatibilidad
        durante el periodo de transición.
        """
        es_facturador = self._es_facturador(facturador_o_empresa)

        if es_facturador:
            self._validar_configuracion_facturador(facturador_o_empresa)
            cuit = facturador_o_empresa.cuit
            certificado = facturador_o_empresa.certificado
            clave_privada = facturador_o_empresa.clave_privada
            ambiente = facturador_o_empresa.ambiente or 'testing'
        else:
            self._validar_configuracion_empresa(facturador_o_empresa)
            cuit = facturador_o_empresa.cuit
            certificado = facturador_o_empresa.certificado_arca
            clave_privada = facturador_o_empresa.clave_privada_arca
            ambiente = facturador_o_empresa.ambiente_arca or 'testing'

        cuit_norm = self._normalizar_cuit(cuit_consulta)
        if len(cuit_norm) != 11:
            raise ArcaValidationError('El CUIT a consultar debe contener 11 dígitos.')

        arca_client = self.arca_client_cls(
            cuit=cuit,
            certificado=certificado,
            clave_privada=clave_privada,
            ambiente=ambiente,
        )

        try:
            return arca_client.consultar_padron(cuit_norm)
        except (ArcaAuthError, ArcaNetworkError):
            raise
        finally:
            arca_client.close()
