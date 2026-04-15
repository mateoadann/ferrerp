# 02 — Autenticación y Conexión con ARCA

> **Audiencia:** Documentación técnica para que una AI o desarrollador implemente la conexión completa con los servicios web de ARCA usando la librería `arca_arg`.

---

## Índice

1. [Arquitectura de autenticación de ARCA](#1-arquitectura-de-autenticación-de-arca)
2. [Configuración de arca_arg.settings](#2-configuración-de-arca_argsettings)
3. [Creación de ArcaWebService](#3-creación-de-arcawebservice)
4. [Ciclo de vida del Ticket de Acceso (TA)](#4-ciclo-de-vida-del-ticket-de-acceso-ta)
5. [Construcción del objeto Auth para WSFE](#5-construcción-del-objeto-auth-para-wsfe)
6. [Patrón completo: Wrapper de conexión](#6-patrón-completo-wrapper-de-conexión)
7. [Manejo de múltiples CUITs](#7-manejo-de-múltiples-cuits)
8. [Concurrencia y file locking](#8-concurrencia-y-file-locking)
9. [Reintentos y recuperación de errores de autenticación](#9-reintentos-y-recuperación-de-errores-de-autenticación)
10. [Servicios disponibles y sus WSDLs](#10-servicios-disponibles-y-sus-wsdls)
11. [Ejemplo completo end-to-end](#11-ejemplo-completo-end-to-end)

---

## 1. Arquitectura de autenticación de ARCA

ARCA separa la **autenticación** de la **operación**. Son dos servicios web independientes:

### WSAA (Web Service de Autenticación y Autorización)

- **Función:** Emitir Tickets de Acceso (TA)
- **Protocolo:** SOAP
- **Endpoints:**
  - Homologación: `https://wsaahomo.afip.gov.ar/ws/services/LoginCms`
  - Producción: `https://wsaa.afip.gov.ar/ws/services/LoginCms`
- **Operación única:** `loginCms` — recibe un TRA (Ticket de Requerimiento de Acceso) firmado y devuelve un TA

### WSFE (Web Service de Factura Electrónica)

- **Función:** Emitir y consultar comprobantes electrónicos
- **Protocolo:** SOAP
- **Endpoints:**
  - Homologación: definido en `WSDL_FEV1_HOM`
  - Producción: definido en `WSDL_FEV1_PROD`
- **Requiere:** Token y Sign de un TA válido emitido por WSAA para el servicio `wsfe`

### Flujo completo de autenticación

```
┌──────────────────────────────────────────────────────────────────┐
│                     FLUJO DE AUTENTICACIÓN                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Tu app genera un TRA (XML con servicio destino y timestamps) │
│                                                                  │
│  2. El TRA se firma con la clave privada (.key) del contribuyente│
│     usando CMS (Cryptographic Message Syntax) y el certificado   │
│     (.crt/.pem) emitido por ARCA                                 │
│                                                                  │
│  3. Se envía el TRA firmado (CMS en Base64) al WSAA via SOAP     │
│     → Operación: loginCms(in0: string_base64_cms)                │
│                                                                  │
│  4. WSAA valida:                                                 │
│     - Que el certificado sea válido y no esté revocado           │
│     - Que la firma CMS sea correcta                              │
│     - Que el servicio solicitado esté autorizado para ese CUIT   │
│     - Que no exista ya un TA vigente para ese CUIT+servicio      │
│                                                                  │
│  5. WSAA responde con un TA (XML) que contiene:                  │
│     - token: string opaco de autenticación                       │
│     - sign: firma del token                                      │
│     - expirationTime: timestamp de vencimiento (~12 horas)       │
│                                                                  │
│  6. Tu app usa token+sign en cada request al WSFE (u otro WS)   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

> **Nota:** Todo el paso 1-5 lo maneja `arca_arg` automáticamente al crear una instancia de `ArcaWebService`. No es necesario implementar la firma CMS ni la llamada al WSAA manualmente.

### Estructura del TRA (referencia)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<loginTicketRequest version="1.0">
  <header>
    <uniqueId>1234567890</uniqueId>
    <generationTime>2025-01-24T10:00:00-03:00</generationTime>
    <expirationTime>2025-01-24T10:10:00-03:00</expirationTime>
  </header>
  <service>wsfe</service>
</loginTicketRequest>
```

### Estructura del TA (referencia)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<loginTicketResponse version="1.0">
  <header>
    <source>CN=wsaahomo</source>
    <destination>SERIALNUMBER=CUIT 20123456789, CN=mi_cert</destination>
    <uniqueId>1234567890</uniqueId>
    <generationTime>2025-01-24T10:00:00-03:00</generationTime>
    <expirationTime>2025-01-24T22:00:00-03:00</expirationTime>
  </header>
  <credentials>
    <token>PD94bWwgdmVyc2lvbj0i... (string largo)</token>
    <sign>X7k9mN2pQ3rS... (string largo)</sign>
  </credentials>
</loginTicketResponse>
```

---

## 2. Configuración de arca_arg.settings

`arca_arg` usa un **módulo de configuración global** (`arca_arg.settings`) que debe ser configurado antes de crear cualquier instancia de `ArcaWebService`.

### Variables obligatorias

```python
import arca_arg.settings as config

config.PRIVATE_KEY_PATH = '/ruta/a/clave.key'      # Ruta absoluta a la clave privada
config.CERT_PATH = '/ruta/a/certificado.pem'        # Ruta absoluta al certificado
config.TA_FILES_PATH = '/ruta/a/cache_ta/'          # Directorio para cache de TA (debe existir)
config.CUIT = '20123456789'                         # CUIT sin guiones
config.PROD = False                                 # False=homologación, True=producción
```

### Detalle de cada variable

#### PRIVATE_KEY_PATH
- **Tipo:** `str`
- **Valor:** Ruta absoluta al archivo `.key` con la clave privada RSA
- **Formato del archivo:** PEM (`-----BEGIN RSA PRIVATE KEY-----`)
- **Usado por:** `arca_arg.auth` para firmar el TRA

#### CERT_PATH
- **Tipo:** `str`
- **Valor:** Ruta absoluta al archivo `.crt`/`.pem` con el certificado X.509
- **Formato del archivo:** PEM (`-----BEGIN CERTIFICATE-----`)
- **Usado por:** `arca_arg.auth` para incluir en la firma CMS

#### TA_FILES_PATH
- **Tipo:** `str`
- **Valor:** Ruta a un directorio con permisos de escritura
- **Requisitos:**
  - El directorio **debe existir** previamente
  - **Debe terminar con separador** de directorio (`/` en Unix, `\` en Windows)
  - Debe tener permisos de lectura y escritura
- **Contenido:** La librería escribe archivos de cache del TA (uno por servicio)
- **Ejemplo:** `/tmp/arca_ta_cache/testing/20123456789/`

#### CUIT
- **Tipo:** `str`
- **Valor:** CUIT del contribuyente emisor, **sin guiones**
- **Ejemplo:** `'20123456789'` (NO `'20-12345678-9'`)
- **Usado por:** `arca_arg.webservice` para incluir en las requests como `Cuit` en el objeto Auth

#### PROD
- **Tipo:** `bool`
- **Valor:** `False` para homologación (testing), `True` para producción
- **Efecto:** Determina qué endpoint de WSAA se usa para autenticarse:
  - `False` → `WSDL_WSAA_HOM` (wsaahomo.afip.gov.ar)
  - `True` → `WSDL_WSAA_PROD` (wsaa.afip.gov.ar)

### Problema crítico: importación por valor

Algunos módulos internos de `arca_arg` hacen `from arca_arg.settings import CERT_PATH` al momento de importarse. Esto copia el valor **en ese instante**, por lo que cambios posteriores a `config.CERT_PATH` no se reflejan en esos módulos.

**Los módulos afectados son:**

```python
import arca_arg.auth as arca_auth      # Copia PRIVATE_KEY_PATH, CERT_PATH, TA_FILES_PATH, PROD
import arca_arg.webservice as arca_ws   # Copia CUIT
```

**Solución:** Después de cambiar `config.*`, re-aplicar en los módulos afectados:

```python
def aplicar_configuracion(cuit, cert_path, key_path, ta_path, produccion):
    """
    Aplica configuración de arca_arg en todos los módulos necesarios.
    """
    import arca_arg.settings as arca_settings
    import arca_arg.auth as arca_auth
    import arca_arg.webservice as arca_ws

    # 1. Módulo principal de settings
    arca_settings.PRIVATE_KEY_PATH = key_path
    arca_settings.CERT_PATH = cert_path
    arca_settings.TA_FILES_PATH = ta_path
    arca_settings.CUIT = cuit
    arca_settings.PROD = produccion

    # 2. Módulo auth (copia por valor)
    arca_auth.PRIVATE_KEY_PATH = key_path
    arca_auth.CERT_PATH = cert_path
    arca_auth.TA_FILES_PATH = ta_path
    arca_auth.PROD = produccion
    arca_auth.WSDL_WSAA = (
        arca_settings.WSDL_WSAA_PROD if produccion
        else arca_settings.WSDL_WSAA_HOM
    )

    # 3. Módulo webservice (copia por valor)
    arca_ws.CUIT = cuit
```

> **Regla:** Esta función debe llamarse **antes de cada operación** si la aplicación maneja múltiples CUITs o si diferentes partes del código podrían modificar los settings.

---

## 3. Creación de ArcaWebService

`ArcaWebService` es la clase principal de `arca_arg`. Cada instancia representa una conexión a un servicio web específico de ARCA.

### Constructor

```python
from arca_arg.webservice import ArcaWebService

ws = ArcaWebService(wsdl, service_name, enable_logging=False)
```

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `wsdl` | `str` | URL del WSDL del servicio. Usar constantes de `arca_arg.settings` |
| `service_name` | `str` | Nombre técnico del servicio según ARCA |
| `enable_logging` | `bool` | `True` para imprimir XML SOAP en consola (debug) |

### Qué sucede internamente al instanciar

Al ejecutar `ArcaWebService(wsdl, service_name)`, la librería:

1. **Lee la configuración** de `arca_arg.settings` (CUIT, cert, key, etc.)
2. **Busca un TA cacheado** en `TA_FILES_PATH` para el `service_name`
3. **Si el TA existe y es válido** → lo carga y lo usa
4. **Si el TA no existe o está vencido** → ejecuta el flujo WSAA:
   - Genera TRA XML para el servicio solicitado
   - Firma el TRA con la clave privada (CMS)
   - Llama a `loginCms` del WSAA
   - Parsea el TA de la respuesta
   - Guarda el TA en disco (en `TA_FILES_PATH`)
5. **Crea el cliente SOAP** (Zeep) con el WSDL del servicio
6. **Almacena `token`, `sign`, `cuit`** como propiedades de la instancia

### Propiedades de la instancia

```python
ws.token    # str — Token del TA vigente
ws.sign     # str — Firma del TA vigente
ws.cuit     # str — CUIT configurado (leído de arca_ws.CUIT)
```

### Métodos de la instancia

#### `ws.list_methods() → list[str]`

Lista todos los métodos SOAP disponibles del servicio.

```python
ws.list_methods()
# WSFE retorna:
# ['FECAESolicitar', 'FECompUltimoAutorizado', 'FECompConsultar',
#  'FECAEARegInformativo', 'FECAEASolicitar', 'FECAEAConsultar',
#  'FECAEAInformar', 'FEParamGetTiposCbte', 'FEParamGetTiposConcepto',
#  'FEParamGetTiposDoc', 'FEParamGetTiposIva', 'FEParamGetTiposMonedas',
#  'FEParamGetTiposOpcional', 'FEParamGetTiposTributos',
#  'FEParamGetPtosVenta', 'FEParamGetCotizacion',
#  'FECompTotXRequest', 'FEDummy',
#  'FEParamGetCondicionIvaReceptor', ...]
```

#### `ws.method_help(method_name: str) → str`

Muestra la firma del método con sus parámetros y tipos.

```python
ws.method_help('FECompUltimoAutorizado')
# Muestra los parámetros que acepta y sus tipos SOAP
```

#### `ws.get_type(type_name: str) → dict`

Devuelve la estructura de un tipo complejo SOAP como diccionario Python con valores `None`.

```python
ws.get_type('FEAuthRequest')
# → {'Token': None, 'Sign': None, 'Cuit': None}

ws.get_type('FECAECabRequest')
# → {'CantReg': None, 'PtoVta': None, 'CbteTipo': None}

ws.get_type('FECAEDetRequest')
# → {'Concepto': None, 'DocTipo': None, 'DocNro': None,
#    'CbteDesde': None, 'CbteHasta': None, 'CbteFch': None,
#    'ImpTotal': None, 'ImpTotConc': None, 'ImpNeto': None,
#    'ImpOpEx': None, 'ImpIVA': None, 'ImpTrib': None,
#    'FchServDesde': None, 'FchServHasta': None, 'FchVtoPago': None,
#    'MonId': None, 'MonCotiz': None,
#    'CbtesAsoc': None, 'Tributos': None, 'Iva': None,
#    'Opcionales': None, ...}
```

> **Tip:** `get_type()` es muy útil para descubrir la estructura exacta que espera ARCA para cada request. Usalo como referencia al construir los datos.

#### `ws.send_request(method_name: str, data: dict) → objeto Zeep`

Envía una request SOAP al servicio y devuelve la respuesta parseada por Zeep.

```python
result = ws.send_request('FECompUltimoAutorizado', {
    'Auth': auth,
    'PtoVta': 1,
    'CbteTipo': 1,
})
# result es un objeto Zeep con atributos correspondientes a la respuesta SOAP
# Ej: result.CbteNro → int
```

**Sobre el objeto de respuesta:**
- El retorno es un **objeto Zeep** (no un diccionario)
- Se accede a los campos con **notación de punto**: `result.CbteNro`, `result.FeCabResp.Resultado`
- Las listas SOAP se convierten en **listas Python**: `result.FeDetResp.FECAEDetResponse[0]`
- Los campos opcionales pueden ser `None`
- Para convertir a diccionario, usar `zeep.helpers.serialize_object(result)`

---

## 4. Ciclo de vida del Ticket de Acceso (TA)

### Duración

- Un TA es válido por aproximadamente **12 horas** desde su emisión
- El tiempo exacto lo determina ARCA en el campo `expirationTime` del TA

### Cache en disco

La librería guarda el TA en `TA_FILES_PATH/{service_name}.pkl`:

```
/tmp/arca_ta_cache/testing/20123456789/
├── wsfe.pkl                              # TA para WSFE
├── ws_sr_constancia_inscripcion.pkl      # TA para padrón
├── wsfe.lock                             # Lock file (si se usa locking)
└── ws_sr_constancia_inscripcion.lock     # Lock file
```

### Verificación de validez del TA cacheado

Para verificar programáticamente si un TA local sigue vigente (sin llamar al WSAA):

```python
import os
import time

def tiene_ta_valido(ta_path: str, servicio: str) -> bool:
    """Verifica si existe un TA cacheado válido para el servicio."""
    ta_file = os.path.join(ta_path, f'{servicio}.pkl')
    if not os.path.exists(ta_file):
        return False

    try:
        import pickle
        with open(ta_file, 'rb') as f:
            ticket = pickle.load(f)
    except Exception:
        return False

    # Verificar expiración — el objeto TA puede tener diferentes atributos
    # según la versión de arca_arg

    # Opción 1: Atributo is_expired (bool)
    is_expired = getattr(ticket, 'is_expired', None)
    if isinstance(is_expired, bool):
        return not is_expired

    # Opción 2: Atributo expires (timestamp numérico)
    expires = getattr(ticket, 'expires', None)
    if isinstance(expires, (int, float)):
        return time.time() < float(expires)

    # Opción 3: Atributo expires_str (string de fecha)
    expires_str = getattr(ticket, 'expires_str', None)
    if expires_str:
        return True  # Si existe pero no podemos validar, asumir válido

    return False
```

> **Nota sobre seguridad del cache:** Los archivos `.pkl` son generados y consumidos localmente por la librería `arca_arg` como mecanismo de cache. No se deserializan datos de fuentes externas.

### Regla de unicidad del TA en ARCA

ARCA **no permite** que un mismo CUIT tenga dos TA vigentes para el mismo servicio. Si se intenta pedir un nuevo TA cuando ya existe uno válido (aunque el local se haya perdido), ARCA responde con:

```
"El CEE ya posee un TA válido para el acceso al WSN solicitado"
```

Este es uno de los errores más comunes y se maneja con reintentos (ver sección 9).

---

## 5. Construcción del objeto Auth para WSFE

Todas las operaciones de WSFE requieren un objeto `Auth` como primer parámetro. Este objeto lleva las credenciales del TA vigente.

### Cómo construirlo

```python
def construir_auth(ws: ArcaWebService) -> dict:
    """
    Construye el objeto FEAuthRequest para usar en operaciones WSFE.

    Args:
        ws: Instancia de ArcaWebService ya conectada

    Returns:
        Dict con Token, Sign y Cuit del TA vigente
    """
    auth = ws.get_type('FEAuthRequest')
    auth['Token'] = ws.token
    auth['Sign'] = ws.sign
    auth['Cuit'] = ws.cuit
    return auth
```

### Estructura del objeto Auth

```python
{
    'Token': 'PD94bWwgdmVyc2lvbj0i...',   # String largo (~1500 chars)
    'Sign': 'X7k9mN2pQ3rS...',             # String largo (~350 chars)
    'Cuit': '20123456789',                  # CUIT sin guiones (como string)
}
```

### Reutilización del Auth

El objeto Auth se puede reutilizar para **múltiples requests** mientras el TA sea válido (~12 horas). No es necesario reconstruirlo para cada operación:

```python
# Crear una vez
auth = construir_auth(ws)

# Usar en múltiples operaciones
result1 = ws.send_request('FECompUltimoAutorizado', {'Auth': auth, 'PtoVta': 1, 'CbteTipo': 1})
result2 = ws.send_request('FECAESolicitar', {'Auth': auth, 'FeCAEReq': {...}})
result3 = ws.send_request('FECompConsultar', {'Auth': auth, 'FeCompConsReq': {...}})
```

### Diferencia con el servicio de Padrón

El servicio de **Constancia de Inscripción** (`ws_sr_constancia_inscripcion`) usa una convención diferente para la autenticación. En lugar de un objeto `Auth`, pasa los campos directamente como parámetros **en minúscula**:

```python
# WSFE — objeto Auth con mayúsculas
data_wsfe = {
    'Auth': {
        'Token': ws.token,
        'Sign': ws.sign,
        'Cuit': ws.cuit,
    },
    'PtoVta': 1,
    'CbteTipo': 1,
}

# Padrón — parámetros directos en minúscula
data_padron = {
    'token': ws_padron.token,
    'sign': ws_padron.sign,
    'cuitRepresentada': ws_padron.cuit,
    'idPersona': 20123456789,     # CUIT a consultar (como int)
}
```

---

## 6. Patrón completo: Wrapper de conexión

En una aplicación real, conviene encapsular toda la lógica de configuración, conexión y manejo de errores en un wrapper:

```python
import tempfile
import os
import time
from typing import Optional

import arca_arg.settings as arca_settings
import arca_arg.auth as arca_auth
import arca_arg.webservice as arca_ws
from arca_arg.webservice import ArcaWebService
from arca_arg.settings import (
    WSDL_FEV1_HOM, WSDL_FEV1_PROD,
    WSDL_CONSTANCIA_HOM, WSDL_CONSTANCIA_PROD,
)


class ArcaClient:
    """
    Wrapper de conexión a ARCA que maneja:
    - Escritura de certificados a archivos temporales
    - Configuración de arca_arg.settings
    - Creación lazy de instancias de ArcaWebService
    - Reintentos ante errores de TA
    - Limpieza de archivos temporales
    """

    def __init__(self, cuit: str, cert: bytes, key: bytes, ambiente: str = 'testing'):
        """
        Args:
            cuit: CUIT del contribuyente (con o sin guiones)
            cert: Contenido del certificado (.pem) en bytes
            key: Contenido de la clave privada (.key) en bytes
            ambiente: 'testing' (homologación) o 'production' (producción)
        """
        self.cuit = cuit.replace('-', '')
        self.ambiente = ambiente
        self.is_production = ambiente == 'production'

        # Escribir certificados a archivos temporales
        self._temp_dir = tempfile.mkdtemp()
        self._cert_path = os.path.join(self._temp_dir, 'cert.pem')
        self._key_path = os.path.join(self._temp_dir, 'key.key')

        with open(self._cert_path, 'wb') as f:
            f.write(cert)
        with open(self._key_path, 'wb') as f:
            f.write(key)

        # Directorio de cache de TA (separado por ambiente y CUIT)
        ta_cache_root = os.path.join(tempfile.gettempdir(), 'arca_ta_cache')
        self._ta_path = os.path.join(ta_cache_root, self.ambiente, self.cuit, '')
        os.makedirs(self._ta_path, exist_ok=True)

        # Aplicar configuración inicial
        self._configurar_settings()

        # Instancias lazy de servicios
        self._wsfe: Optional[ArcaWebService] = None
        self._ws_padron: Optional[ArcaWebService] = None

    def _configurar_settings(self):
        """Aplica configuración en todos los módulos de arca_arg."""
        # Módulo principal
        arca_settings.PRIVATE_KEY_PATH = self._key_path
        arca_settings.CERT_PATH = self._cert_path
        arca_settings.TA_FILES_PATH = self._ta_path
        arca_settings.CUIT = self.cuit
        arca_settings.PROD = self.is_production

        # Módulos que copian por valor
        arca_auth.PRIVATE_KEY_PATH = self._key_path
        arca_auth.CERT_PATH = self._cert_path
        arca_auth.TA_FILES_PATH = self._ta_path
        arca_auth.PROD = self.is_production
        arca_auth.WSDL_WSAA = (
            arca_settings.WSDL_WSAA_PROD if self.is_production
            else arca_settings.WSDL_WSAA_HOM
        )
        arca_ws.CUIT = self.cuit

    @property
    def wsfe(self) -> ArcaWebService:
        """Obtiene o crea la instancia de WSFE (lazy)."""
        if self._wsfe is None:
            wsdl = WSDL_FEV1_PROD if self.is_production else WSDL_FEV1_HOM
            self._wsfe = self._crear_servicio(wsdl, 'wsfe')
        return self._wsfe

    @property
    def ws_padron(self) -> ArcaWebService:
        """Obtiene o crea la instancia del servicio de Padrón (lazy)."""
        if self._ws_padron is None:
            wsdl = WSDL_CONSTANCIA_PROD if self.is_production else WSDL_CONSTANCIA_HOM
            self._ws_padron = self._crear_servicio(wsdl, 'ws_sr_constancia_inscripcion')
        return self._ws_padron

    def _crear_servicio(self, wsdl: str, servicio: str) -> ArcaWebService:
        """
        Crea una instancia de ArcaWebService con reintentos para el error
        'ya posee un TA válido'.
        """
        for intento in range(3):
            try:
                self._configurar_settings()  # Re-aplicar antes de cada intento
                return ArcaWebService(wsdl, servicio, enable_logging=False)
            except Exception as e:
                mensaje = str(e).lower()
                # Normalizar acentos para comparación robusta
                mensaje_norm = (
                    mensaje
                    .replace('á', 'a').replace('é', 'e')
                    .replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
                )
                if 'ya posee un ta valido' in mensaje_norm and intento < 2:
                    time.sleep(intento + 1)
                    self._configurar_settings()
                    continue
                raise
        raise RuntimeError(f'No se pudo conectar al servicio {servicio} después de 3 intentos')

    def __del__(self):
        """Limpia archivos temporales."""
        try:
            for path in [self._cert_path, self._key_path]:
                if os.path.exists(path):
                    os.unlink(path)
            if os.path.exists(self._temp_dir):
                for f in os.listdir(self._temp_dir):
                    os.unlink(os.path.join(self._temp_dir, f))
                os.rmdir(self._temp_dir)
        except Exception:
            pass
```

### Uso del wrapper

```python
# Crear cliente
client = ArcaClient(
    cuit='20-12345678-9',
    cert=cert_bytes,        # bytes del certificado
    key=key_bytes,          # bytes de la clave privada
    ambiente='testing',     # 'testing' o 'production'
)

# Usar WSFE (se conecta en la primera llamada)
ws = client.wsfe
auth = ws.get_type('FEAuthRequest')
auth['Token'] = ws.token
auth['Sign'] = ws.sign
auth['Cuit'] = ws.cuit

result = ws.send_request('FECompUltimoAutorizado', {
    'Auth': auth,
    'PtoVta': 1,
    'CbteTipo': 1,
})
print(f'Último autorizado: {result.CbteNro}')
```

---

## 7. Manejo de múltiples CUITs

### El problema

Dado que `arca_arg` usa configuración global, si una aplicación maneja múltiples CUITs (multi-tenant), los settings de un CUIT pueden pisar los de otro en un ambiente concurrente.

### Solución: re-aplicar settings antes de cada operación

```python
class ArcaClient:
    def _asegurar_settings(self):
        """Re-aplica settings antes de cada operación."""
        self._configurar_settings()

    def consultar_ultimo(self, punto_venta: int, tipo_cbte: int) -> int:
        self._asegurar_settings()  # ← Siempre antes de operar
        ws = self.wsfe
        auth = ws.get_type('FEAuthRequest')
        auth['Token'] = ws.token
        auth['Sign'] = ws.sign
        auth['Cuit'] = ws.cuit
        result = ws.send_request('FECompUltimoAutorizado', {
            'Auth': auth,
            'PtoVta': punto_venta,
            'CbteTipo': tipo_cbte,
        })
        return result.CbteNro
```

### Separación de cache de TA por CUIT

Cada CUIT debe tener su propio directorio de cache de TA para evitar que un CUIT use el token de otro:

```
/tmp/arca_ta_cache/
├── testing/
│   ├── 20123456789/
│   │   ├── wsfe.pkl
│   │   └── ws_sr_constancia_inscripcion.pkl
│   └── 20987654321/
│       ├── wsfe.pkl
│       └── ws_sr_constancia_inscripcion.pkl
└── production/
    └── 20123456789/
        └── wsfe.pkl
```

---

## 8. Concurrencia y file locking

### El problema

En aplicaciones con múltiples procesos (ej: workers de Celery), pueden ocurrir carreras al obtener TA:

1. Worker A ve que no hay TA cacheado → pide uno al WSAA
2. Worker B ve que no hay TA cacheado → pide uno al WSAA
3. Worker A obtiene TA exitosamente
4. Worker B falla: "ya posee un TA válido" (porque el de Worker A aún está vigente)

### Solución: file locking por servicio

```python
import fcntl
from contextlib import contextmanager

@contextmanager
def lock_servicio(ta_path: str, servicio: str):
    """
    Adquiere un lock exclusivo por servicio para serializar
    la obtención de TA entre procesos.
    """
    lock_path = os.path.join(ta_path, f'{servicio}.lock')
    lock_file = open(lock_path, 'a+')
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)  # Espera hasta obtener el lock
        yield
    finally:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()
```

### Integración en el wrapper

```python
def _crear_servicio(self, wsdl: str, servicio: str) -> ArcaWebService:
    with lock_servicio(self._ta_path, servicio):
        self._configurar_settings()
        for intento in range(3):
            try:
                return ArcaWebService(wsdl, servicio, enable_logging=False)
            except Exception as e:
                mensaje_norm = self._normalizar_mensaje(str(e))
                if 'ya posee un ta valido' in mensaje_norm and intento < 2:
                    time.sleep(intento + 1)
                    self._configurar_settings()
                    continue
                raise
    raise RuntimeError(f'No se pudo conectar a {servicio}')
```

### Notas sobre portabilidad

- `fcntl.flock` es **Unix/Linux/Mac only**
- En Windows, usar `msvcrt.locking` como alternativa
- Los lock files se crean junto a los archivos de cache del TA

---

## 9. Reintentos y recuperación de errores de autenticación

### Error: "ya posee un TA válido"

**Causa:** Se intenta pedir un nuevo TA al WSAA cuando el anterior aún no venció.

**Variantes del mensaje (ARCA no es consistente con acentos):**
- `"El CEE ya posee un TA válido para el acceso al WSN solicitado"`
- `"El CEE ya posee un TA valido para el acceso al WSN solicitado"`

**Estrategia:**

```python
def _normalizar_mensaje(self, mensaje: str) -> str:
    """Normaliza acentos para comparación robusta."""
    return (
        (mensaje or '')
        .lower()
        .replace('á', 'a')
        .replace('é', 'e')
        .replace('í', 'i')
        .replace('ó', 'o')
        .replace('ú', 'u')
    )

def _crear_servicio_con_reintentos(self, wsdl, servicio):
    for intento in range(3):
        try:
            return ArcaWebService(wsdl, servicio, enable_logging=False)
        except Exception as e:
            msg = self._normalizar_mensaje(str(e))
            if 'ya posee un ta valido' in msg and intento < 2:
                time.sleep(intento + 1)  # Backoff: 1s, 2s
                self._configurar_settings()
                continue
            raise
```

### Otros errores de autenticación

| Error | Causa | Acción |
|-------|-------|--------|
| `Error 600` | CUIT no autorizado para el servicio | No reintentar. Verificar autorización en portal ARCA |
| `Certificate verification failed` | Certificado inválido o expirado | No reintentar. Obtener nuevo certificado |
| `Connection refused` / `Timeout` | Servicio ARCA caído | Reintentar con backoff exponencial (hasta 3 veces) |
| `SSL Error` | Problema de red/proxy | Verificar conectividad y configuración SSL |

---

## 10. Servicios disponibles y sus WSDLs

### Constantes de WSDLs en arca_arg.settings

```python
from arca_arg.settings import (
    # WSFE — Factura Electrónica
    WSDL_FEV1_HOM,           # Homologación
    WSDL_FEV1_PROD,          # Producción

    # Constancia de Inscripción — Padrón
    WSDL_CONSTANCIA_HOM,     # Homologación
    WSDL_CONSTANCIA_PROD,    # Producción

    # WSAA — Autenticación (usado internamente)
    WSDL_WSAA_HOM,
    WSDL_WSAA_PROD,
)
```

### Tabla de servicios

| Servicio | `service_name` | WSDL Hom | WSDL Prod | Descripción |
|----------|---------------|----------|-----------|-------------|
| WSFE | `'wsfe'` | `WSDL_FEV1_HOM` | `WSDL_FEV1_PROD` | Factura electrónica (mercado interno) |
| Padrón | `'ws_sr_constancia_inscripcion'` | `WSDL_CONSTANCIA_HOM` | `WSDL_CONSTANCIA_PROD` | Consulta de datos del contribuyente |

### Creación de cada servicio

```python
# WSFE
wsdl_wsfe = WSDL_FEV1_PROD if produccion else WSDL_FEV1_HOM
ws_wsfe = ArcaWebService(wsdl_wsfe, 'wsfe')

# Padrón
wsdl_padron = WSDL_CONSTANCIA_PROD if produccion else WSDL_CONSTANCIA_HOM
ws_padron = ArcaWebService(wsdl_padron, 'ws_sr_constancia_inscripcion')
```

---

## 11. Ejemplo completo end-to-end

Ejemplo funcional que configura, conecta, y hace una consulta simple a WSFE:

```python
import os
import tempfile

import arca_arg.settings as arca_settings
import arca_arg.auth as arca_auth
import arca_arg.webservice as arca_ws
from arca_arg.webservice import ArcaWebService
from arca_arg.settings import WSDL_FEV1_HOM


def main():
    # --- 1. Datos de entrada ---
    cuit = '20123456789'
    ambiente = 'testing'
    produccion = False

    # Leer certificados desde archivos (o desde base de datos, API, etc.)
    with open('/ruta/a/mi_certificado.pem', 'rb') as f:
        cert_bytes = f.read()
    with open('/ruta/a/mi_clave.key', 'rb') as f:
        key_bytes = f.read()

    # --- 2. Preparar archivos temporales ---
    temp_dir = tempfile.mkdtemp()
    cert_path = os.path.join(temp_dir, 'cert.pem')
    key_path = os.path.join(temp_dir, 'key.key')

    with open(cert_path, 'wb') as f:
        f.write(cert_bytes)
    with open(key_path, 'wb') as f:
        f.write(key_bytes)

    # Directorio de cache de TA
    ta_path = os.path.join(tempfile.gettempdir(), 'arca_ta_cache', ambiente, cuit, '')
    os.makedirs(ta_path, exist_ok=True)

    # --- 3. Configurar arca_arg ---
    arca_settings.PRIVATE_KEY_PATH = key_path
    arca_settings.CERT_PATH = cert_path
    arca_settings.TA_FILES_PATH = ta_path
    arca_settings.CUIT = cuit
    arca_settings.PROD = produccion

    arca_auth.PRIVATE_KEY_PATH = key_path
    arca_auth.CERT_PATH = cert_path
    arca_auth.TA_FILES_PATH = ta_path
    arca_auth.PROD = produccion
    arca_auth.WSDL_WSAA = arca_settings.WSDL_WSAA_HOM

    arca_ws.CUIT = cuit

    # --- 4. Crear instancia de WSFE ---
    # Esto dispara autenticación WSAA si no hay TA cacheado
    ws = ArcaWebService(WSDL_FEV1_HOM, 'wsfe', enable_logging=False)
    print(f'Conectado a WSFE. CUIT: {ws.cuit}')

    # --- 5. Construir Auth ---
    auth = ws.get_type('FEAuthRequest')
    auth['Token'] = ws.token
    auth['Sign'] = ws.sign
    auth['Cuit'] = ws.cuit

    # --- 6. Consultar último comprobante autorizado ---
    punto_venta = 1
    tipo_cbte = 1  # Factura A

    result = ws.send_request('FECompUltimoAutorizado', {
        'Auth': auth,
        'PtoVta': punto_venta,
        'CbteTipo': tipo_cbte,
    })

    ultimo = result.CbteNro
    print(f'Último comprobante autorizado: FC A {punto_venta:04d}-{ultimo:08d}')
    print(f'Próximo número a emitir: {ultimo + 1}')

    # --- 7. Explorar métodos disponibles ---
    print('\nMétodos disponibles en WSFE:')
    for metodo in ws.list_methods():
        print(f'  - {metodo}')

    # --- 8. Limpiar temporales ---
    os.unlink(cert_path)
    os.unlink(key_path)
    os.rmdir(temp_dir)


if __name__ == '__main__':
    main()
```

### Salida esperada

```
Conectado a WSFE. CUIT: 20123456789
Último comprobante autorizado: FC A 0001-00000005
Próximo número a emitir: 6

Métodos disponibles en WSFE:
  - FECAESolicitar
  - FECompUltimoAutorizado
  - FECompConsultar
  - FEParamGetTiposCbte
  - FEParamGetTiposDoc
  - FEParamGetTiposIva
  ...
```
