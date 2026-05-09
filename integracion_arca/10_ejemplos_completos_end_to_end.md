# 10. Ejemplos Completos End-to-End

Este documento presenta flujos completos de emisión de comprobantes, desde la configuración inicial hasta la obtención del CAE. Cada ejemplo es autocontenido y copy-paste ready.

---

## 10.1 Setup Inicial (Común a Todos los Ejemplos)

### 10.1.1 Instalación

```bash
pip install arca_arg
```

### 10.1.2 Constantes y Helpers

```python
# constants.py — Copiar este archivo completo

TIPOS_COMPROBANTE = {
    1: 'Factura A',
    2: 'Nota de Débito A',
    3: 'Nota de Crédito A',
    6: 'Factura B',
    7: 'Nota de Débito B',
    8: 'Nota de Crédito B',
    11: 'Factura C',
    12: 'Nota de Débito C',
    13: 'Nota de Crédito C',
    51: 'Factura M',
    52: 'Nota de Débito M',
    53: 'Nota de Crédito M',
}

TIPOS_CONCEPTO = {
    1: 'Productos',
    2: 'Servicios',
    3: 'Productos y Servicios',
}

TIPOS_DOCUMENTO = {
    80: 'CUIT',
    86: 'CUIL',
    87: 'CDI',
    96: 'DNI',
    99: 'Doc. (Otro)',
}

ALICUOTAS_IVA = {
    3: {'porcentaje': 0, 'descripcion': '0%'},
    4: {'porcentaje': 10.5, 'descripcion': '10.5%'},
    5: {'porcentaje': 21, 'descripcion': '21%'},
    6: {'porcentaje': 27, 'descripcion': '27%'},
    8: {'porcentaje': 5, 'descripcion': '5%'},
    9: {'porcentaje': 2.5, 'descripcion': '2.5%'},
}

CONDICIONES_IVA = {
    1: 'IVA Responsable Inscripto',
    4: 'IVA Sujeto Exento',
    5: 'Consumidor Final',
    6: 'Responsable Monotributo',
    7: 'Sujeto No Categorizado',
    8: 'Proveedor del Exterior',
    9: 'Cliente del Exterior',
    10: 'IVA Liberado – Ley Nº 19.640',
    11: 'IVA Responsable Inscripto – Agente de Percepción',
    13: 'Monotributista Social',
    15: 'IVA No Alcanzado',
    16: 'Monotributo Trabajador Independiente Promotido',
}

TIPOS_COMPROBANTE_C = {11, 12, 13}

TIPO_CBTE_CLASE = {
    1: 'A', 2: 'A', 3: 'A',
    6: 'B', 7: 'B', 8: 'B',
    11: 'C', 12: 'C', 13: 'C',
    51: 'M', 52: 'M', 53: 'M',
}

CONDICIONES_IVA_POR_CLASE = {
    'A': {1, 4, 5, 6, 7, 8, 9, 10, 13, 15, 16},
    'B': {1, 4, 5, 6, 7, 8, 9, 10, 13, 15, 16},
    'C': {1, 4, 5, 6, 7, 8, 9, 10, 13, 15, 16},
    'M': {1, 4, 5, 6, 7, 8, 9, 10, 13, 15, 16},
}

MONEDAS = {
    'PES': 'Pesos Argentinos',
    'DOL': 'Dólar Estadounidense',
    '060': 'Euro',
}
```

### 10.1.3 Excepciones

```python
# exceptions.py

class ArcaError(Exception):
    """Error base de ARCA."""
    pass

class ArcaAuthError(ArcaError):
    """Error de autenticación con ARCA."""
    pass

class ArcaValidationError(ArcaError):
    """Error de validación de datos."""
    pass

class ArcaNetworkError(ArcaError):
    """Error de red."""
    pass
```

### 10.1.4 ArcaClient

```python
# client.py

import tempfile
import os
import time
import fcntl
import logging
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

import arca_arg.settings as arca_settings
import arca_arg.auth as arca_auth
import arca_arg.webservice as arca_ws
from arca_arg.webservice import ArcaWebService
from arca_arg.settings import (
    WSDL_FEV1_HOM, WSDL_FEV1_PROD,
    WSDL_CONSTANCIA_HOM, WSDL_CONSTANCIA_PROD,
)

logger = logging.getLogger(__name__)


class ArcaClient:
    """
    Wrapper para arca_arg que maneja:
    - Archivos temporales de certificado
    - Configuración global de settings (con re-apply)
    - Cache de TA por CUIT/ambiente
    - File locking para concurrencia
    - Retry automático para error "ya posee un TA válido"
    """

    def __init__(self, cuit: str, cert: bytes, key: bytes,
                 ambiente: str = 'testing'):
        self.cuit = cuit.replace('-', '')
        self.ambiente = ambiente
        self.is_production = ambiente == 'production'

        # Crear archivos temporales para cert/key
        self._temp_dir = tempfile.mkdtemp()
        self._cert_path = os.path.join(self._temp_dir, 'cert.pem')
        self._key_path = os.path.join(self._temp_dir, 'key.key')

        with open(self._cert_path, 'wb') as f:
            f.write(cert)
        with open(self._key_path, 'wb') as f:
            f.write(key)

        # Directorio estable para cache de TA
        ta_cache_root = os.getenv('ARCA_TA_CACHE_DIR') or os.path.join(
            tempfile.gettempdir(), 'arca_ta_cache'
        )
        self._ta_path = os.path.join(ta_cache_root, self.ambiente, self.cuit)
        os.makedirs(self._ta_path, exist_ok=True)
        if not self._ta_path.endswith(os.sep):
            self._ta_path += os.sep

        self._configure_settings()
        self._wsfe: Optional[ArcaWebService] = None
        self._ws_constancia: Optional[ArcaWebService] = None

    def _configure_settings(self):
        """Configura arca_arg.settings globales."""
        arca_settings.PRIVATE_KEY_PATH = self._key_path
        arca_settings.CERT_PATH = self._cert_path
        arca_settings.TA_FILES_PATH = self._ta_path
        arca_settings.CUIT = self.cuit
        arca_settings.PROD = self.is_production

        # arca_arg copia valores por valor en otros módulos
        arca_auth.PRIVATE_KEY_PATH = self._key_path
        arca_auth.CERT_PATH = self._cert_path
        arca_auth.TA_FILES_PATH = self._ta_path
        arca_auth.PROD = self.is_production
        arca_auth.WSDL_WSAA = (
            arca_settings.WSDL_WSAA_PROD if self.is_production
            else arca_settings.WSDL_WSAA_HOM
        )
        arca_ws.CUIT = self.cuit

    def _ensure_settings(self):
        """Re-aplica settings antes de cada operación."""
        self._configure_settings()

    @property
    def wsfe(self) -> ArcaWebService:
        if self._wsfe is None:
            wsdl = WSDL_FEV1_PROD if self.is_production else WSDL_FEV1_HOM
            self._wsfe = self._create_ws(wsdl, 'wsfe', 'Error WSFE')
        return self._wsfe

    @property
    def ws_constancia(self) -> ArcaWebService:
        if self._ws_constancia is None:
            wsdl = WSDL_CONSTANCIA_PROD if self.is_production else WSDL_CONSTANCIA_HOM
            self._ws_constancia = self._create_ws(
                wsdl, 'ws_sr_constancia_inscripcion', 'Error padrón'
            )
        return self._ws_constancia

    def _create_ws(self, wsdl, service, error_prefix):
        with self._ta_file_lock(service):
            self._ensure_settings()
            for attempt in range(3):
                try:
                    return ArcaWebService(wsdl, service, enable_logging=False)
                except Exception as e:
                    msg = str(e).lower()
                    if 'ya posee un ta valido' in msg and attempt < 2:
                        time.sleep(attempt + 1)
                        self._ensure_settings()
                        continue
                    raise ArcaAuthError(f'{error_prefix}: {e}')
        raise ArcaAuthError(f'{error_prefix}: no se pudo inicializar')

    @contextmanager
    def _ta_file_lock(self, service):
        lock_path = os.path.join(self._ta_path, f'{service}.lock')
        lock_file = open(lock_path, 'a+')
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    # --- Operaciones WSFE ---

    def fe_comp_ultimo_autorizado(self, punto_venta: int, tipo_cbte: int) -> int:
        self._ensure_settings()
        ws = self.wsfe
        auth = ws.get_type('FEAuthRequest')
        auth['Token'] = ws.token
        auth['Sign'] = ws.sign
        auth['Cuit'] = ws.cuit
        result = ws.send_request('FECompUltimoAutorizado', {
            'Auth': auth, 'PtoVta': punto_venta, 'CbteTipo': tipo_cbte,
        })
        return result.CbteNro

    def fe_cae_solicitar(self, request_data: dict) -> dict:
        self._ensure_settings()
        ws = self.wsfe
        auth = ws.get_type('FEAuthRequest')
        auth['Token'] = ws.token
        auth['Sign'] = ws.sign
        auth['Cuit'] = ws.cuit

        fe_cae_req = request_data['FeCAEReq']
        det_req = fe_cae_req['FeDetReq']['FECAEDetRequest']
        if isinstance(det_req, list):
            det_req = det_req[0]

        result = ws.send_request('FECAESolicitar', {
            'Auth': auth,
            'FeCAEReq': {
                'FeCabReq': fe_cae_req['FeCabReq'],
                'FeDetReq': {'FECAEDetRequest': det_req},
            }
        })
        return self._parse_cae_response(result)

    def fe_comp_consultar(self, tipo_cbte: int, punto_venta: int,
                          numero: int) -> dict:
        self._ensure_settings()
        ws = self.wsfe
        auth = ws.get_type('FEAuthRequest')
        auth['Token'] = ws.token
        auth['Sign'] = ws.sign
        auth['Cuit'] = ws.cuit
        result = ws.send_request('FECompConsultar', {
            'Auth': auth,
            'FeCompConsReq': {
                'CbteTipo': tipo_cbte, 'CbteNro': numero, 'PtoVta': punto_venta,
            }
        })
        if hasattr(result, 'ResultGet') and result.ResultGet:
            cbte = result.ResultGet
            return {
                'encontrado': True,
                'tipo_cbte': cbte.CbteTipo,
                'punto_venta': cbte.PtoVta,
                'cbte_desde': cbte.CbteDesde,
                'fecha_cbte': str(cbte.CbteFch) if cbte.CbteFch else None,
                'imp_total': cbte.ImpTotal,
                'cae': str(cbte.CodAutorizacion) if cbte.CodAutorizacion else None,
                'cae_vto': str(cbte.FchVto) if getattr(cbte, 'FchVto', None) else None,
                'resultado': cbte.Resultado,
            }
        return {'encontrado': False}

    def consultar_padron(self, cuit_consulta: str) -> dict:
        self._ensure_settings()
        ws = self.ws_constancia
        cuit_int = int(cuit_consulta.replace('-', ''))
        data = {
            'token': ws.token, 'sign': ws.sign,
            'cuitRepresentada': ws.cuit, 'idPersona': cuit_int,
        }
        result = ws.send_request('getPersona_v2', data)
        if hasattr(result, 'personaReturn') and result.personaReturn:
            persona = result.personaReturn
            nombre = getattr(persona, 'nombre', '') or ''
            apellido = getattr(persona, 'apellido', '') or ''
            if apellido and nombre:
                razon_social = f'{apellido}, {nombre}'
            elif nombre:
                razon_social = nombre
            else:
                razon_social = getattr(persona, 'razonSocial', '') or ''
            condicion_iva = None
            if hasattr(persona, 'datosRegimenGeneral') and persona.datosRegimenGeneral:
                condicion_iva = 'IVA Responsable Inscripto'
            elif hasattr(persona, 'datosMonotributo') and persona.datosMonotributo:
                condicion_iva = 'Responsable Monotributo'
            return {
                'success': True,
                'data': {
                    'cuit': cuit_consulta.replace('-', ''),
                    'razon_social': razon_social,
                    'condicion_iva': condicion_iva,
                }
            }
        return {'success': False, 'error': 'Persona no encontrada'}

    def _parse_cae_response(self, result) -> dict:
        response = {
            'resultado': None, 'reproceso': None, 'cae': None,
            'cae_vencimiento': None, 'numero_comprobante': None,
            'observaciones': [], 'errores': [],
        }
        if hasattr(result, 'FeCabResp') and result.FeCabResp:
            response['resultado'] = result.FeCabResp.Resultado
            response['reproceso'] = getattr(result.FeCabResp, 'Reproceso', None)
        if hasattr(result, 'FeDetResp') and result.FeDetResp:
            det_list = result.FeDetResp.FECAEDetResponse
            if det_list:
                det = det_list[0] if isinstance(det_list, list) else det_list
                response['cae'] = str(det.CAE) if det.CAE else None
                response['cae_vencimiento'] = str(det.CAEFchVto) if det.CAEFchVto else None
                response['numero_comprobante'] = det.CbteDesde
                response['resultado'] = det.Resultado
                if hasattr(det, 'Observaciones') and det.Observaciones:
                    obs = det.Observaciones.Obs if hasattr(det.Observaciones, 'Obs') else det.Observaciones
                    if obs:
                        if not isinstance(obs, list):
                            obs = [obs]
                        response['observaciones'] = [
                            {'code': getattr(o, 'Code', None), 'msg': getattr(o, 'Msg', '')}
                            for o in obs
                        ]
        if hasattr(result, 'Errors') and result.Errors:
            errs = result.Errors.Err if hasattr(result.Errors, 'Err') else result.Errors
            if errs:
                if not isinstance(errs, list):
                    errs = [errs]
                response['errores'] = [
                    {'code': getattr(e, 'Code', None), 'msg': getattr(e, 'Msg', '')}
                    for e in errs
                ]
        return response

    def __del__(self):
        try:
            for p in [self._cert_path, self._key_path]:
                if os.path.exists(p):
                    os.unlink(p)
            if os.path.exists(self._temp_dir):
                for f in os.listdir(self._temp_dir):
                    os.unlink(os.path.join(self._temp_dir, f))
                os.rmdir(self._temp_dir)
        except Exception:
            pass
```

### 10.1.5 FacturaBuilder

```python
# builder.py

from datetime import date
from decimal import Decimal
from typing import Optional, List
from constants import TIPOS_COMPROBANTE_C, TIPO_CBTE_CLASE, CONDICIONES_IVA_POR_CLASE
from exceptions import ArcaValidationError


class FacturaBuilder:
    def __init__(self):
        self._tipo_cbte: Optional[int] = None
        self._punto_venta: Optional[int] = None
        self._numero: Optional[int] = None
        self._concepto: Optional[int] = None
        self._fecha_emision: Optional[date] = None
        self._fecha_desde: Optional[date] = None
        self._fecha_hasta: Optional[date] = None
        self._fecha_vto_pago: Optional[date] = None
        self._doc_tipo: Optional[int] = None
        self._doc_nro: Optional[int] = None
        self._importe_total: Optional[Decimal] = None
        self._importe_neto: Optional[Decimal] = None
        self._importe_iva: Decimal = Decimal('0')
        self._importe_tributos: Decimal = Decimal('0')
        self._importe_no_gravado: Decimal = Decimal('0')
        self._importe_exento: Decimal = Decimal('0')
        self._moneda: str = 'PES'
        self._cotizacion: Decimal = Decimal('1')
        self._alicuotas_iva: List[dict] = []
        self._cbte_asoc_tipo: Optional[int] = None
        self._cbte_asoc_pto_vta: Optional[int] = None
        self._cbte_asoc_nro: Optional[int] = None
        self._condicion_iva_receptor_id: Optional[int] = None

    def set_comprobante(self, tipo, punto_venta, numero, concepto):
        self._tipo_cbte = tipo
        self._punto_venta = punto_venta
        self._numero = numero
        self._concepto = concepto
        return self

    def set_fechas(self, emision, desde=None, hasta=None, vto_pago=None):
        self._fecha_emision = emision
        self._fecha_desde = desde
        self._fecha_hasta = hasta
        self._fecha_vto_pago = vto_pago
        return self

    def set_receptor(self, doc_tipo, doc_nro):
        nro = str(doc_nro).replace('-', '').replace(' ', '')
        if not nro.isdigit():
            raise ArcaValidationError('Número de documento inválido')
        self._doc_tipo = doc_tipo
        self._doc_nro = int(nro)
        return self

    def set_importes(self, total, neto, iva=0, tributos=0, no_gravado=0, exento=0):
        self._importe_total = Decimal(str(total))
        self._importe_neto = Decimal(str(neto))
        self._importe_iva = Decimal(str(iva))
        self._importe_tributos = Decimal(str(tributos))
        self._importe_no_gravado = Decimal(str(no_gravado))
        self._importe_exento = Decimal(str(exento))
        return self

    def set_moneda(self, moneda, cotizacion=1):
        self._moneda = moneda
        self._cotizacion = Decimal(str(cotizacion))
        return self

    def add_iva(self, alicuota_id, base_imponible, importe):
        self._alicuotas_iva.append({
            'Id': alicuota_id,
            'BaseImp': round(base_imponible, 2),
            'Importe': round(importe, 2),
        })
        return self

    def set_comprobante_asociado(self, tipo, punto_venta, numero):
        self._cbte_asoc_tipo = tipo
        self._cbte_asoc_pto_vta = punto_venta
        self._cbte_asoc_nro = numero
        return self

    def set_condicion_iva_receptor(self, condicion_iva_id):
        self._condicion_iva_receptor_id = int(condicion_iva_id)
        return self

    def validate(self):
        required = [
            (self._tipo_cbte, 'Tipo de comprobante'),
            (self._punto_venta, 'Punto de venta'),
            (self._numero, 'Número de comprobante'),
            (self._concepto, 'Concepto'),
            (self._fecha_emision, 'Fecha de emisión'),
            (self._doc_tipo, 'Tipo de documento'),
            (self._doc_nro, 'Número de documento'),
        ]
        for val, name in required:
            if not val:
                raise ArcaValidationError(f'{name} es requerido')
        if self._importe_total is None:
            raise ArcaValidationError('Importe total es requerido')
        if self._importe_neto is None:
            raise ArcaValidationError('Importe neto es requerido')
        if self._concepto in (2, 3):
            if not (self._fecha_desde and self._fecha_hasta and self._fecha_vto_pago):
                raise ArcaValidationError(
                    'Servicios requieren fecha_desde, fecha_hasta y fecha_vto_pago'
                )
        tipos_nota = {2, 3, 7, 8, 12, 13, 52, 53}
        if self._tipo_cbte in tipos_nota:
            if not (self._cbte_asoc_tipo and self._cbte_asoc_pto_vta and self._cbte_asoc_nro):
                raise ArcaValidationError('NC/ND requieren comprobante asociado')
        return True

    def build(self) -> dict:
        self.validate()
        fmt = lambda d: d.strftime('%Y%m%d')
        det = {
            'Concepto': self._concepto,
            'DocTipo': self._doc_tipo,
            'DocNro': self._doc_nro,
            'CbteDesde': self._numero,
            'CbteHasta': self._numero,
            'CbteFch': fmt(self._fecha_emision),
            'ImpTotal': float(self._importe_total),
            'ImpTotConc': float(self._importe_no_gravado),
            'ImpNeto': float(self._importe_neto),
            'ImpOpEx': float(self._importe_exento),
            'ImpTrib': float(self._importe_tributos),
            'ImpIVA': float(self._importe_iva),
            'MonId': self._moneda,
            'MonCotiz': float(self._cotizacion),
        }
        if self._tipo_cbte in TIPOS_COMPROBANTE_C:
            det['ImpIVA'] = 0.0
        if self._fecha_desde:
            det['FchServDesde'] = fmt(self._fecha_desde)
        if self._fecha_hasta:
            det['FchServHasta'] = fmt(self._fecha_hasta)
        if self._fecha_vto_pago:
            det['FchVtoPago'] = fmt(self._fecha_vto_pago)
        if self._alicuotas_iva and self._tipo_cbte not in TIPOS_COMPROBANTE_C:
            det['Iva'] = {'AlicIva': self._alicuotas_iva}
        if self._cbte_asoc_tipo:
            det['CbtesAsoc'] = {'CbteAsoc': [{
                'Tipo': self._cbte_asoc_tipo,
                'PtoVta': self._cbte_asoc_pto_vta,
                'Nro': self._cbte_asoc_nro,
            }]}
        if self._condicion_iva_receptor_id is not None:
            clase = TIPO_CBTE_CLASE.get(self._tipo_cbte)
            condiciones_validas = CONDICIONES_IVA_POR_CLASE.get(clase, set())
            if self._condicion_iva_receptor_id not in condiciones_validas:
                raise ArcaValidationError(
                    f'Condición IVA {self._condicion_iva_receptor_id} '
                    f'no válida para clase {clase}'
                )
            det['CondicionIVAReceptorId'] = self._condicion_iva_receptor_id
        return {
            'FeCAEReq': {
                'FeCabReq': {
                    'CantReg': 1,
                    'PtoVta': self._punto_venta,
                    'CbteTipo': self._tipo_cbte,
                },
                'FeDetReq': {'FECAEDetRequest': [det]},
            }
        }
```

### 10.1.6 WSFEService

```python
# wsfe_service.py

from datetime import datetime


class WSFEService:
    def __init__(self, client):
        self.client = client

    def autorizar(self, request_data: dict) -> dict:
        result = self.client.fe_cae_solicitar(request_data)
        if result.get('resultado') == 'A':
            return {
                'success': True,
                'cae': result['cae'],
                'cae_vencimiento': self._parse_fecha(result['cae_vencimiento']),
                'numero_comprobante': result['numero_comprobante'],
                'observaciones': result.get('observaciones', []),
            }
        else:
            errores = result.get('errores', [])
            observaciones = result.get('observaciones', [])
            all_msgs = errores + observaciones
            msg = '; '.join(e.get('msg', '') for e in all_msgs if e.get('msg'))
            return {
                'success': False,
                'error_code': errores[0].get('code') if errores else None,
                'error_message': msg or 'Error desconocido',
            }

    def ultimo_autorizado(self, punto_venta: int, tipo_cbte: int) -> int:
        return self.client.fe_comp_ultimo_autorizado(punto_venta, tipo_cbte)

    def _parse_fecha(self, fecha_str):
        if not fecha_str:
            return None
        try:
            return datetime.strptime(str(fecha_str), '%Y%m%d').date().isoformat()
        except ValueError:
            return str(fecha_str)
```

### 10.1.7 Helper de Normalización de Importes

```python
# importes.py

from decimal import Decimal, ROUND_HALF_UP
from constants import TIPOS_COMPROBANTE_C, TIPO_CBTE_CLASE


def normalizar_importes(tipo_cbte, neto, iva, total):
    """Normaliza importes según la clase de comprobante."""
    neto = Decimal(str(neto or 0)).quantize(Decimal('0.01'))
    iva = Decimal(str(iva or 0)).quantize(Decimal('0.01'))
    total = Decimal(str(total or 0)).quantize(Decimal('0.01'))

    if int(tipo_cbte) in TIPOS_COMPROBANTE_C:
        iva = Decimal('0.00')
        total = neto

    if TIPO_CBTE_CLASE.get(int(tipo_cbte)) == 'B':
        if iva == Decimal('0.00') and total > 0:
            iva = (total / Decimal('1.21') * Decimal('0.21')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            neto = total - iva

    return neto, iva, total
```

---

## 10.2 Ejemplo 1: Factura A — Productos, 21% IVA

**Escenario**: Empresa RI emite Factura A a otro RI por $10.000 + 21% IVA.

```python
from datetime import date
from decimal import Decimal

# --- Datos del escenario ---
CUIT_EMISOR = '20301234567'
PUNTO_VENTA = 1
TIPO_CBTE = 1           # Factura A
CONCEPTO = 1             # Productos
DOC_TIPO = 80            # CUIT
DOC_NRO = '30712345678'  # CUIT del receptor
CONDICION_IVA_RECEPTOR = 1  # IVA Responsable Inscripto

IMP_NETO = Decimal('10000.00')
IMP_IVA = Decimal('2100.00')     # 21% de 10000
IMP_TOTAL = Decimal('12100.00')  # neto + iva

# --- 1. Crear cliente ---
with open('cert.pem', 'rb') as f:
    cert = f.read()
with open('key.key', 'rb') as f:
    key = f.read()

client = ArcaClient(
    cuit=CUIT_EMISOR,
    cert=cert,
    key=key,
    ambiente='testing',  # 'production' para producción
)

# --- 2. Precalentar TA ---
_ = client.wsfe

# --- 3. Obtener próximo número ---
ultimo = client.fe_comp_ultimo_autorizado(PUNTO_VENTA, TIPO_CBTE)
numero = ultimo + 1
print(f'Próximo número: {numero}')

# --- 4. Normalizar importes ---
neto, iva, total = normalizar_importes(TIPO_CBTE, IMP_NETO, IMP_IVA, IMP_TOTAL)
# Clase A: sin cambios → (10000.00, 2100.00, 12100.00)

# --- 5. Construir request ---
builder = (
    FacturaBuilder()
    .set_comprobante(tipo=TIPO_CBTE, punto_venta=PUNTO_VENTA,
                     numero=numero, concepto=CONCEPTO)
    .set_fechas(emision=date.today())
    .set_receptor(doc_tipo=DOC_TIPO, doc_nro=DOC_NRO)
    .set_importes(total=float(total), neto=float(neto), iva=float(iva))
    .set_condicion_iva_receptor(CONDICION_IVA_RECEPTOR)
    .add_iva(alicuota_id=5, base_imponible=float(neto), importe=float(iva))
)

request_data = builder.build()

# --- 6. Verificar request (opcional) ---
det = request_data['FeCAEReq']['FeDetReq']['FECAEDetRequest'][0]
assert abs(det['ImpTotal'] - (det['ImpNeto'] + det['ImpIVA'])) < 0.01
print(f'Request OK: Total={det["ImpTotal"]}, Neto={det["ImpNeto"]}, IVA={det["ImpIVA"]}')

# --- 7. Enviar a ARCA ---
wsfe = WSFEService(client)
response = wsfe.autorizar(request_data)

# --- 8. Procesar resultado ---
if response['success']:
    print(f'✓ APROBADO')
    print(f'  CAE: {response["cae"]}')
    print(f'  Vencimiento: {response["cae_vencimiento"]}')
    print(f'  Comprobante: {TIPOS_COMPROBANTE[TIPO_CBTE]} {PUNTO_VENTA:05d}-{numero:08d}')
else:
    print(f'✗ RECHAZADO')
    print(f'  Código: {response.get("error_code")}')
    print(f'  Mensaje: {response.get("error_message")}')
```

**Request generado**:

```python
{
    'FeCAEReq': {
        'FeCabReq': {'CantReg': 1, 'PtoVta': 1, 'CbteTipo': 1},
        'FeDetReq': {'FECAEDetRequest': [{
            'Concepto': 1,
            'DocTipo': 80,
            'DocNro': 30712345678,
            'CbteDesde': 101,   # ejemplo
            'CbteHasta': 101,
            'CbteFch': '20260309',
            'ImpTotal': 12100.0,
            'ImpTotConc': 0.0,
            'ImpNeto': 10000.0,
            'ImpOpEx': 0.0,
            'ImpTrib': 0.0,
            'ImpIVA': 2100.0,
            'MonId': 'PES',
            'MonCotiz': 1.0,
            'CondicionIVAReceptorId': 1,
            'Iva': {'AlicIva': [
                {'Id': 5, 'BaseImp': 10000.0, 'Importe': 2100.0}
            ]},
        }]}
    }
}
```

---

## 10.3 Ejemplo 2: Factura B — Consumidor Final, IVA Incluido en Total

**Escenario**: Empresa RI emite Factura B a un consumidor final por $12.100 (IVA incluido).

```python
from datetime import date
from decimal import Decimal

# --- Datos del escenario ---
TIPO_CBTE = 6            # Factura B
CONCEPTO = 1             # Productos
DOC_TIPO = 96            # DNI
DOC_NRO = '25123456'     # DNI del consumidor
IMP_TOTAL = Decimal('12100.00')  # Total con IVA incluido

# --- 1. Crear cliente (igual que Ejemplo 1) ---
client = ArcaClient(cuit='20301234567', cert=cert, key=key, ambiente='testing')
_ = client.wsfe

# --- 2. Obtener próximo número ---
ultimo = client.fe_comp_ultimo_autorizado(1, TIPO_CBTE)
numero = ultimo + 1

# --- 3. Normalizar importes ---
# Factura B: el usuario solo tiene el total. Se calcula IVA automáticamente.
neto, iva, total = normalizar_importes(TIPO_CBTE, IMP_TOTAL, Decimal('0'), IMP_TOTAL)
# Resultado: neto=10000.00, iva=2100.00, total=12100.00

print(f'Neto: {neto}, IVA: {iva}, Total: {total}')

# --- 4. Condición IVA: SIEMPRE 5 para clase B ---
CONDICION_IVA_RECEPTOR = 5  # Consumidor Final (fijo para Factura B)

# --- 5. Construir request ---
builder = (
    FacturaBuilder()
    .set_comprobante(tipo=TIPO_CBTE, punto_venta=1,
                     numero=numero, concepto=CONCEPTO)
    .set_fechas(emision=date.today())
    .set_receptor(doc_tipo=DOC_TIPO, doc_nro=DOC_NRO)
    .set_importes(total=float(total), neto=float(neto), iva=float(iva))
    .set_condicion_iva_receptor(CONDICION_IVA_RECEPTOR)
    .add_iva(alicuota_id=5, base_imponible=float(neto), importe=float(iva))
)

request_data = builder.build()

# --- 6. Enviar ---
wsfe = WSFEService(client)
response = wsfe.autorizar(request_data)

if response['success']:
    print(f'✓ Factura B {1:05d}-{numero:08d}')
    print(f'  CAE: {response["cae"]}')
    print(f'  Vto: {response["cae_vencimiento"]}')
else:
    print(f'✗ Error: {response["error_message"]}')
```

**Puntos clave de Factura B**:

```python
# 1. Normalización calcula IVA desde total:
#    iva = 12100 / 1.21 * 0.21 = 2100.00
#    neto = 12100 - 2100 = 10000.00

# 2. CondicionIVAReceptorId = 5 SIEMPRE (sin importar quién sea el receptor)

# 3. Iva.AlicIva SÍ se incluye (con los valores calculados)

# 4. El total NO cambia — neto + iva = total
```

---

## 10.4 Ejemplo 3: Factura C — Monotributo, Sin IVA

**Escenario**: Monotributista emite Factura C a un Responsable Inscripto por $5.000.

```python
from datetime import date
from decimal import Decimal

# --- Datos del escenario ---
TIPO_CBTE = 11           # Factura C
CONCEPTO = 1             # Productos
DOC_TIPO = 80            # CUIT
DOC_NRO = '30712345678'  # CUIT del receptor (RI)
IMP_TOTAL = Decimal('5000.00')

# --- 1. Crear cliente ---
# El CUIT del emisor es un Monotributista
client = ArcaClient(cuit='20401234567', cert=cert, key=key, ambiente='testing')
_ = client.wsfe

# --- 2. Obtener próximo número ---
ultimo = client.fe_comp_ultimo_autorizado(1, TIPO_CBTE)
numero = ultimo + 1

# --- 3. Normalizar importes ---
neto, iva, total = normalizar_importes(TIPO_CBTE, IMP_TOTAL, Decimal('0'), IMP_TOTAL)
# Clase C: iva=0.00, total=neto=5000.00

print(f'Neto: {neto}, IVA: {iva}, Total: {total}')
# Neto: 5000.00, IVA: 0.00, Total: 5000.00

# --- 4. Condición IVA del receptor (la condición REAL) ---
# Para Factura C se envía la condición real del receptor.
# Si no la tenemos, consultar padrón:
CONDICION_IVA_RECEPTOR = 1  # RI (la condición real)

# O consultando padrón:
# padron = client.consultar_padron(DOC_NRO)
# if padron['success'] and padron['data']['condicion_iva']:
#     CONDICION_IVA_RECEPTOR = nombre_condicion_iva_a_id(
#         padron['data']['condicion_iva']
#     )

# --- 5. Construir request ---
builder = (
    FacturaBuilder()
    .set_comprobante(tipo=TIPO_CBTE, punto_venta=1,
                     numero=numero, concepto=CONCEPTO)
    .set_fechas(emision=date.today())
    .set_receptor(doc_tipo=DOC_TIPO, doc_nro=DOC_NRO)
    .set_importes(total=float(total), neto=float(neto), iva=float(iva))
    .set_condicion_iva_receptor(CONDICION_IVA_RECEPTOR)
    # NO llamar a add_iva() — clase C no lleva IVA
)

request_data = builder.build()

# --- 6. Verificar que no tiene IVA ---
det = request_data['FeCAEReq']['FeDetReq']['FECAEDetRequest'][0]
assert det['ImpIVA'] == 0.0, 'Clase C: ImpIVA debe ser 0'
assert 'Iva' not in det, 'Clase C: no debe incluir Iva.AlicIva'
print('✓ Request validado: sin IVA')

# --- 7. Enviar ---
wsfe = WSFEService(client)
response = wsfe.autorizar(request_data)

if response['success']:
    print(f'✓ Factura C {1:05d}-{numero:08d}')
    print(f'  CAE: {response["cae"]}')
else:
    print(f'✗ Error: {response["error_message"]}')
```

**Request generado (Factura C)**:

```python
{
    'FeCAEReq': {
        'FeCabReq': {'CantReg': 1, 'PtoVta': 1, 'CbteTipo': 11},
        'FeDetReq': {'FECAEDetRequest': [{
            'Concepto': 1,
            'DocTipo': 80,
            'DocNro': 30712345678,
            'CbteDesde': 51,
            'CbteHasta': 51,
            'CbteFch': '20260309',
            'ImpTotal': 5000.0,
            'ImpTotConc': 0.0,
            'ImpNeto': 5000.0,     # = ImpTotal
            'ImpOpEx': 0.0,
            'ImpTrib': 0.0,
            'ImpIVA': 0.0,         # Siempre 0 en clase C
            'MonId': 'PES',
            'MonCotiz': 1.0,
            'CondicionIVAReceptorId': 1,  # Condición REAL del receptor
            # Sin 'Iva' — el builder lo omite automáticamente
        }]}
    }
}
```

---

## 10.5 Ejemplo 4: Factura A de Servicios con Múltiples Alícuotas

**Escenario**: Factura A por servicios de consultoría ($8.000 al 21%) + licencia de software ($2.000 al 10.5%), período marzo 2026.

```python
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

# --- Items ---
items = [
    {'descripcion': 'Consultoría IT',    'neto': 8000, 'alicuota_id': 5},  # 21%
    {'descripcion': 'Licencia software', 'neto': 2000, 'alicuota_id': 4},  # 10.5%
]

# --- Calcular IVA por alícuota ---
from constants import ALICUOTAS_IVA

bases_por_alicuota = {}
for item in items:
    aid = item['alicuota_id']
    base = Decimal(str(item['neto']))
    bases_por_alicuota[aid] = bases_por_alicuota.get(aid, Decimal('0')) + base

iva_detalle = []
for aid in sorted(bases_por_alicuota):
    base = bases_por_alicuota[aid].quantize(Decimal('0.01'))
    pct = Decimal(str(ALICUOTAS_IVA[aid]['porcentaje']))
    imp = (base * pct / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    iva_detalle.append({'Id': aid, 'BaseImp': base, 'Importe': imp})

imp_neto = sum(a['BaseImp'] for a in iva_detalle)   # 10000.00
imp_iva = sum(a['Importe'] for a in iva_detalle)     # 1890.00
imp_total = imp_neto + imp_iva                        # 11890.00

print(f'Detalle IVA:')
for a in iva_detalle:
    print(f'  {ALICUOTAS_IVA[a["Id"]]["descripcion"]}: base={a["BaseImp"]}, iva={a["Importe"]}')
print(f'Neto: {imp_neto}, IVA: {imp_iva}, Total: {imp_total}')

# --- Construir ---
client = ArcaClient(cuit='20301234567', cert=cert, key=key, ambiente='testing')
ultimo = client.fe_comp_ultimo_autorizado(1, 1)
numero = ultimo + 1

builder = (
    FacturaBuilder()
    .set_comprobante(tipo=1, punto_venta=1, numero=numero, concepto=2)  # Servicios
    .set_fechas(
        emision=date(2026, 3, 9),
        desde=date(2026, 3, 1),      # Período desde
        hasta=date(2026, 3, 31),     # Período hasta
        vto_pago=date(2026, 4, 15),  # Vencimiento pago
    )
    .set_receptor(doc_tipo=80, doc_nro='30712345678')
    .set_importes(total=float(imp_total), neto=float(imp_neto), iva=float(imp_iva))
    .set_condicion_iva_receptor(1)  # RI
)

for alicuota in iva_detalle:
    builder.add_iva(
        alicuota_id=alicuota['Id'],
        base_imponible=float(alicuota['BaseImp']),
        importe=float(alicuota['Importe']),
    )

request_data = builder.build()

# Verificar que tiene fechas de servicio
det = request_data['FeCAEReq']['FeDetReq']['FECAEDetRequest'][0]
assert 'FchServDesde' in det
assert 'FchServHasta' in det
assert 'FchVtoPago' in det
assert len(det['Iva']['AlicIva']) == 2

wsfe = WSFEService(client)
response = wsfe.autorizar(request_data)

if response['success']:
    print(f'✓ FC A Servicios - CAE: {response["cae"]}')
else:
    print(f'✗ Error: {response["error_message"]}')
```

---

## 10.6 Ejemplo 5: Nota de Crédito A (Anulación de Factura)

**Escenario**: NC A que anula la Factura A nro 101 del PV 1.

```python
from datetime import date
from decimal import Decimal

# --- Datos de la factura original que se anula ---
FC_ORIGINAL_TIPO = 1     # Factura A
FC_ORIGINAL_PV = 1
FC_ORIGINAL_NRO = 101
FC_ORIGINAL_NETO = Decimal('10000.00')
FC_ORIGINAL_IVA = Decimal('2100.00')
FC_ORIGINAL_TOTAL = Decimal('12100.00')

# --- Construir NC ---
TIPO_CBTE = 3  # Nota de Crédito A

client = ArcaClient(cuit='20301234567', cert=cert, key=key, ambiente='testing')
ultimo = client.fe_comp_ultimo_autorizado(1, TIPO_CBTE)
numero = ultimo + 1

builder = (
    FacturaBuilder()
    .set_comprobante(tipo=TIPO_CBTE, punto_venta=1,
                     numero=numero, concepto=1)
    .set_fechas(emision=date.today())
    .set_receptor(doc_tipo=80, doc_nro='30712345678')
    .set_importes(
        total=float(FC_ORIGINAL_TOTAL),
        neto=float(FC_ORIGINAL_NETO),
        iva=float(FC_ORIGINAL_IVA),
    )
    .set_condicion_iva_receptor(1)  # RI
    .add_iva(alicuota_id=5, base_imponible=float(FC_ORIGINAL_NETO),
             importe=float(FC_ORIGINAL_IVA))
    # Comprobante asociado: la FC A que se anula
    .set_comprobante_asociado(
        tipo=FC_ORIGINAL_TIPO,   # 1 (FC A)
        punto_venta=FC_ORIGINAL_PV,
        numero=FC_ORIGINAL_NRO,
    )
)

request_data = builder.build()

# Verificar que tiene CbtesAsoc
det = request_data['FeCAEReq']['FeDetReq']['FECAEDetRequest'][0]
assert 'CbtesAsoc' in det
assert det['CbtesAsoc']['CbteAsoc'][0]['Tipo'] == 1
assert det['CbtesAsoc']['CbteAsoc'][0]['Nro'] == 101

wsfe = WSFEService(client)
response = wsfe.autorizar(request_data)

if response['success']:
    print(f'✓ NC A {1:05d}-{numero:08d} anulando FC A {1:05d}-{FC_ORIGINAL_NRO:08d}')
    print(f'  CAE: {response["cae"]}')
else:
    print(f'✗ Error: {response["error_message"]}')
```

---

## 10.7 Ejemplo 6: Flujo Completo con Autocompletado de Padrón

**Escenario**: Emitir Factura A a un receptor del que solo se tiene el CUIT. Se consulta el padrón para obtener condición IVA y razón social.

```python
from datetime import date
from decimal import Decimal

CUIT_RECEPTOR = '30712345678'

client = ArcaClient(cuit='20301234567', cert=cert, key=key, ambiente='testing')

# --- 1. Consultar padrón ---
print(f'Consultando padrón para CUIT {CUIT_RECEPTOR}...')
padron = client.consultar_padron(CUIT_RECEPTOR)

if padron['success']:
    data = padron['data']
    print(f'  Razón social: {data["razon_social"]}')
    print(f'  Condición IVA: {data["condicion_iva"]}')

    # Convertir nombre a ID
    condicion_iva_id = nombre_condicion_iva_a_id(data['condicion_iva'])
    print(f'  Condición IVA ID: {condicion_iva_id}')

    if condicion_iva_id is None:
        print('  ✗ No se pudo determinar condición IVA')
        exit(1)
else:
    print(f'  ✗ No se encontraron datos: {padron.get("error")}')
    exit(1)

# --- 2. Determinar tipo de comprobante ---
# RI emite A a RI, B a CF/Mono/Exento
if condicion_iva_id == 1:
    tipo_cbte = 1   # Factura A → receptor RI
elif condicion_iva_id in (5, 6, 4, 13, 16):
    tipo_cbte = 6   # Factura B → receptor CF/Mono/Exento
    condicion_iva_id = 5  # Override para clase B
else:
    tipo_cbte = 6   # Default: Factura B
    condicion_iva_id = 5

print(f'  Tipo comprobante: {TIPOS_COMPROBANTE[tipo_cbte]}')

# --- 3. Importes ---
neto_original = Decimal('10000.00')
iva_original = Decimal('2100.00')
total_original = Decimal('12100.00')

neto, iva, total = normalizar_importes(tipo_cbte, neto_original, iva_original, total_original)

# --- 4. Construir y enviar ---
ultimo = client.fe_comp_ultimo_autorizado(1, tipo_cbte)
numero = ultimo + 1

builder = (
    FacturaBuilder()
    .set_comprobante(tipo=tipo_cbte, punto_venta=1,
                     numero=numero, concepto=1)
    .set_fechas(emision=date.today())
    .set_receptor(doc_tipo=80, doc_nro=CUIT_RECEPTOR)
    .set_importes(total=float(total), neto=float(neto), iva=float(iva))
    .set_condicion_iva_receptor(condicion_iva_id)
)

if iva > 0 and tipo_cbte not in TIPOS_COMPROBANTE_C:
    builder.add_iva(alicuota_id=5, base_imponible=float(neto), importe=float(iva))

request_data = builder.build()

wsfe = WSFEService(client)
response = wsfe.autorizar(request_data)

if response['success']:
    print(f'\n✓ {TIPOS_COMPROBANTE[tipo_cbte]} emitida')
    print(f'  Receptor: {data["razon_social"]}')
    print(f'  Número: {1:05d}-{numero:08d}')
    print(f'  Total: ${float(total):,.2f}')
    print(f'  CAE: {response["cae"]}')
    print(f'  Vencimiento CAE: {response["cae_vencimiento"]}')
else:
    print(f'\n✗ Error: {response["error_message"]}')
```

---

## 10.8 Ejemplo 7: Factura B en Dólares

**Escenario**: Factura B en USD con cotización del día.

```python
from datetime import date
from decimal import Decimal

TIPO_CBTE = 6   # Factura B
MONEDA = 'DOL'
COTIZACION = Decimal('1250.00')  # Cotización USD del día

# Importes en la moneda de la factura (dólares)
IMP_TOTAL_USD = Decimal('100.00')  # USD 100

# Normalizar (clase B: calcular IVA desde total)
neto, iva, total = normalizar_importes(TIPO_CBTE, IMP_TOTAL_USD, Decimal('0'), IMP_TOTAL_USD)
# neto=82.64, iva=17.36, total=100.00

client = ArcaClient(cuit='20301234567', cert=cert, key=key, ambiente='testing')
ultimo = client.fe_comp_ultimo_autorizado(1, TIPO_CBTE)
numero = ultimo + 1

builder = (
    FacturaBuilder()
    .set_comprobante(tipo=TIPO_CBTE, punto_venta=1,
                     numero=numero, concepto=1)
    .set_fechas(emision=date.today())
    .set_receptor(doc_tipo=96, doc_nro='25123456')
    .set_importes(total=float(total), neto=float(neto), iva=float(iva))
    .set_moneda(moneda=MONEDA, cotizacion=float(COTIZACION))
    .set_condicion_iva_receptor(5)  # Siempre 5 para clase B
    .add_iva(alicuota_id=5, base_imponible=float(neto), importe=float(iva))
)

request_data = builder.build()

# Verificar moneda
det = request_data['FeCAEReq']['FeDetReq']['FECAEDetRequest'][0]
assert det['MonId'] == 'DOL'
assert det['MonCotiz'] == 1250.0

wsfe = WSFEService(client)
response = wsfe.autorizar(request_data)

if response['success']:
    print(f'✓ FC B en USD - CAE: {response["cae"]}')
    print(f'  Total: USD {float(total):,.2f} (cotiz: ${float(COTIZACION):,.2f})')
else:
    print(f'✗ Error: {response["error_message"]}')
```

> **Nota sobre moneda extranjera**: Los importes en el request son en la moneda de la factura (USD en este caso), no en pesos. ARCA usa la cotización (`MonCotiz`) para calcular equivalentes en pesos internamente.

---

## 10.9 Ejemplo 8: Procesamiento Masivo con Retry

**Escenario**: Procesar una lista de facturas con manejo de errores y reintentos.

```python
import time
from datetime import date
from decimal import Decimal


def procesar_lote_simple(
    client: ArcaClient,
    facturas: list[dict],
) -> dict:
    """
    Procesa un lote de facturas secuencialmente con retry.

    Cada factura es un dict con:
    - tipo_cbte, punto_venta, concepto
    - doc_tipo, doc_nro
    - total, neto, iva (opcionales, se normalizan)
    - condicion_iva_id
    - fecha_emision (opcional, default hoy)
    - items (opcional, para múltiples alícuotas)

    Returns:
        {'ok': int, 'errores': int, 'resultados': list}
    """
    resultados = []
    ok = 0
    errores = 0

    for i, factura_data in enumerate(facturas):
        tipo_cbte = factura_data['tipo_cbte']
        pv = factura_data['punto_venta']
        concepto = factura_data.get('concepto', 1)
        fecha = factura_data.get('fecha_emision', date.today())

        # Normalizar importes
        neto, iva, total = normalizar_importes(
            tipo_cbte,
            factura_data.get('neto', 0),
            factura_data.get('iva', 0),
            factura_data.get('total', 0),
        )

        # Resolver condición IVA
        cond_iva = factura_data.get('condicion_iva_id')
        if TIPO_CBTE_CLASE.get(tipo_cbte) == 'B':
            cond_iva = 5

        if cond_iva is None:
            resultados.append({
                'index': i, 'success': False,
                'error': 'Condición IVA no determinada',
            })
            errores += 1
            continue

        # Intentar emitir (con hasta 1 retry)
        for attempt in range(2):
            try:
                ultimo = client.fe_comp_ultimo_autorizado(pv, tipo_cbte)
                numero = ultimo + 1

                builder = (
                    FacturaBuilder()
                    .set_comprobante(tipo=tipo_cbte, punto_venta=pv,
                                     numero=numero, concepto=concepto)
                    .set_fechas(emision=fecha)
                    .set_receptor(
                        doc_tipo=factura_data['doc_tipo'],
                        doc_nro=factura_data['doc_nro'],
                    )
                    .set_importes(total=float(total), neto=float(neto),
                                  iva=float(iva))
                    .set_condicion_iva_receptor(cond_iva)
                )

                if iva > 0 and tipo_cbte not in TIPOS_COMPROBANTE_C:
                    builder.add_iva(alicuota_id=5,
                                    base_imponible=float(neto),
                                    importe=float(iva))

                request_data = builder.build()
                wsfe = WSFEService(client)
                response = wsfe.autorizar(request_data)

                if response['success']:
                    resultados.append({
                        'index': i, 'success': True,
                        'numero': numero,
                        'cae': response['cae'],
                        'cae_vencimiento': response['cae_vencimiento'],
                    })
                    ok += 1
                    break  # Éxito, no reintentar
                else:
                    error_msg = response.get('error_message', '')
                    error_code = str(response.get('error_code', ''))

                    # ¿Retryable?
                    is_retryable = (
                        'ya posee un ta valido' in error_msg.lower()
                        or error_code == '10016'
                        or 'proximo a autorizar' in error_msg.lower()
                    )

                    if is_retryable and attempt == 0:
                        wait = 5 if 'ta valido' in error_msg.lower() else 1
                        time.sleep(wait)
                        continue  # Reintentar

                    resultados.append({
                        'index': i, 'success': False,
                        'error_code': error_code,
                        'error': error_msg,
                    })
                    errores += 1
                    break

            except ArcaValidationError as e:
                resultados.append({
                    'index': i, 'success': False, 'error': str(e),
                })
                errores += 1
                break  # No reintentar errores de validación

            except (ArcaError, ConnectionError, TimeoutError) as e:
                if attempt == 0:
                    time.sleep(3)
                    continue
                resultados.append({
                    'index': i, 'success': False, 'error': str(e),
                })
                errores += 1
                break

    return {'ok': ok, 'errores': errores, 'resultados': resultados}


# --- Uso ---
facturas = [
    {
        'tipo_cbte': 6, 'punto_venta': 1, 'doc_tipo': 96,
        'doc_nro': '25123456', 'total': 12100,
        'condicion_iva_id': 5,
    },
    {
        'tipo_cbte': 6, 'punto_venta': 1, 'doc_tipo': 96,
        'doc_nro': '30987654', 'total': 6050,
        'condicion_iva_id': 5,
    },
    {
        'tipo_cbte': 11, 'punto_venta': 1, 'doc_tipo': 80,
        'doc_nro': '30712345678', 'neto': 5000, 'total': 5000,
        'condicion_iva_id': 1,
    },
]

client = ArcaClient(cuit='20301234567', cert=cert, key=key, ambiente='testing')
_ = client.wsfe  # Precalentar TA

stats = procesar_lote_simple(client, facturas)
print(f'\nResultado: {stats["ok"]} OK, {stats["errores"]} errores')
for r in stats['resultados']:
    if r['success']:
        print(f'  [{r["index"]}] ✓ Nro {r["numero"]} - CAE {r["cae"]}')
    else:
        print(f'  [{r["index"]}] ✗ {r["error"]}')
```

---

## 10.10 Resumen: Diferencias Clave entre Clases

```
┌──────────────────────────────────────────────────────────────────────┐
│                    FACTURA A (tipo 1)                                │
│                                                                      │
│  Emisor: Responsable Inscripto                                       │
│  Receptor: Responsable Inscripto (condición real)                    │
│  IVA: discriminado (neto + iva = total)                              │
│  AlicIva: obligatorio si ImpIVA > 0                                  │
│  CondicionIVAReceptorId: condición real del receptor                 │
│  Importes: el usuario informa neto e IVA por separado               │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                    FACTURA B (tipo 6)                                │
│                                                                      │
│  Emisor: Responsable Inscripto                                       │
│  Receptor: CF, Monotributo, Exento (cualquiera que no sea RI)        │
│  IVA: incluido en total, se desglosa (RG 5614)                       │
│  AlicIva: obligatorio (con el IVA calculado)                         │
│  CondicionIVAReceptorId: SIEMPRE 5 (Consumidor Final)                │
│  Importes: normalización calcula iva = total/1.21*0.21               │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                    FACTURA C (tipo 11)                               │
│                                                                      │
│  Emisor: Monotributo                                                 │
│  Receptor: cualquiera (condición real)                               │
│  IVA: CERO (Monotributo no discrimina IVA)                           │
│  AlicIva: NO incluir                                                 │
│  CondicionIVAReceptorId: condición real del receptor                 │
│  Importes: normalización fuerza iva=0, total=neto                    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 10.11 Checklist de Implementación

```
[ ] 1. Instalar arca_arg
[ ] 2. Obtener certificado digital (.crt) y clave privada (.key)
[ ] 3. Habilitar servicios en portal ARCA:
      [ ] wsfe (facturación electrónica)
      [ ] ws_sr_constancia_inscripcion (padrón, opcional)
[ ] 4. Implementar ArcaClient con:
      [ ] Archivos temporales para cert/key
      [ ] Re-apply de settings globales
      [ ] File locking para concurrencia de TA
      [ ] Retry para "ya posee un TA válido"
[ ] 5. Implementar FacturaBuilder con:
      [ ] Validación de campos requeridos
      [ ] Regla: servicios requieren fechas
      [ ] Regla: NC/ND requieren cbte asociado
      [ ] Regla: clase C sin IVA
      [ ] Regla: condición IVA validada por clase
[ ] 6. Implementar normalización de importes:
      [ ] Clase A: sin cambios
      [ ] Clase B: calcular IVA desde total (21%)
      [ ] Clase C: IVA=0, total=neto
[ ] 7. Implementar resolución de CondicionIVAReceptorId:
      [ ] Prioridad: ID guardado → nombre → tipo doc → padrón
      [ ] Override clase B → siempre 5
[ ] 8. Implementar manejo de errores:
      [ ] Retry para WSAA (5s)
      [ ] Retry para secuencia 10016 (1s + sincronizar fecha)
      [ ] Sin retry para errores de validación
[ ] 9. Testing:
      [ ] Ambiente testing primero
      [ ] FC A, FC B, FC C, NC, servicios
      [ ] Verificar CAE obtenido
[ ] 10. Producción:
       [ ] Cambiar ambiente a 'production'
       [ ] Verificar certificado de producción
       [ ] Monitorear errores
```
