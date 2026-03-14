"""Servicio de alto nivel para operaciones WSFE."""

from datetime import datetime

from .arca_exceptions import ArcaRechazoError


class WSFEService:
    """Opera WSFE sobre un cliente ARCA ya configurado."""

    def __init__(self, arca_client):
        self.arca_client = arca_client

    def ultimo_autorizado(self, punto_venta, tipo_cbte):
        """Retorna el ultimo comprobante autorizado para punto/tipo."""
        return self.arca_client.fe_comp_ultimo_autorizado(punto_venta, tipo_cbte)

    def autorizar(self, request_data):
        """Solicita autorizacion de comprobante y normaliza respuesta."""
        payload = self.arca_client.fe_cae_solicitar(request_data)
        resultado = (payload.get('resultado') or '').upper()

        if resultado != 'A':
            errores = payload.get('errores') or []
            observaciones = payload.get('observaciones') or []
            codigo, mensaje = self._extraer_error_principal(errores, observaciones)
            raise ArcaRechazoError(
                mensaje or 'Comprobante rechazado por ARCA.',
                codigo=codigo,
                detalle=payload,
                errores=errores,
                observaciones=observaciones,
            )

        return {
            'resultado': resultado,
            'cae': payload.get('cae'),
            'cae_vencimiento': self.parsear_fecha_arca(payload.get('cae_vencimiento')),
            'numero_comprobante': payload.get('numero_comprobante'),
            'errores': payload.get('errores') or [],
            'observaciones': payload.get('observaciones') or [],
            'raw': payload.get('raw') or payload,
        }

    def consultar_comprobante(self, tipo_cbte, punto_venta, numero):
        """Consulta un comprobante puntual en ARCA."""
        return self.arca_client.fe_comp_consultar(tipo_cbte, punto_venta, numero)

    @staticmethod
    def _extraer_error_principal(errores, observaciones):
        """Obtiene codigo y mensaje principal de rechazo."""
        for origen in (errores or [], observaciones or []):
            for item in origen:
                if isinstance(item, dict):
                    codigo = item.get('Code') or item.get('code') or item.get('Codigo')
                    mensaje = item.get('Msg') or item.get('msg') or item.get('Mensaje')
                    if codigo or mensaje:
                        return str(codigo or ''), mensaje
                else:
                    texto = str(item)
                    if texto:
                        return '', texto
        return '', 'Comprobante rechazado por ARCA.'

    @classmethod
    def es_error_secuencia(cls, error_or_payload):
        """Detecta error de secuencia (codigo 10016) en errores u observaciones."""
        if error_or_payload is None:
            return False

        if isinstance(error_or_payload, ArcaRechazoError):
            payload = {
                'errores': error_or_payload.errores,
                'observaciones': error_or_payload.observaciones,
            }
        else:
            payload = error_or_payload

        colecciones = []
        if isinstance(payload, dict):
            colecciones.extend([payload.get('errores') or [], payload.get('observaciones') or []])
        else:
            colecciones.append(payload)

        for items in colecciones:
            if isinstance(items, dict):
                items = items.get('Err') or items.get('Obs') or [items]
            if not isinstance(items, list):
                items = [items]
            for item in items:
                if isinstance(item, dict):
                    codigo = item.get('Code') or item.get('code') or item.get('Codigo')
                    if str(codigo) == '10016':
                        return True
                elif '10016' in str(item):
                    return True
        return False

    @staticmethod
    def parsear_fecha_arca(valor):
        """Convierte fecha ARCA YYYYMMDD a objeto date."""
        if not valor:
            return None
        if hasattr(valor, 'year'):
            return valor
        return datetime.strptime(str(valor), '%Y%m%d').date()
