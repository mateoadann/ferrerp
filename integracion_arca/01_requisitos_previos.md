# 01 — Requisitos Previos para Integración con ARCA (WSFE)

> **Audiencia:** Esta documentación está diseñada para ser consumida por una AI o desarrollador que necesite implementar facturación electrónica argentina desde cero usando la librería `arca_arg`.

---

## Contexto General

**ARCA** (anteriormente conocida como **AFIP**) es la entidad tributaria de Argentina. Todos los contribuyentes que emiten comprobantes electrónicos deben hacerlo a través de los **Web Services SOAP** que ARCA expone. El servicio principal para facturación electrónica es **WSFE** (Web Service de Factura Electrónica, versión FEv1).

La comunicación con ARCA requiere:

1. Un **certificado digital** (.crt/.pem) emitido por ARCA
2. Una **clave privada** (.key) generada por el contribuyente
3. Un **CUIT** (Clave Única de Identificación Tributaria) habilitado
4. **Autorización del servicio web** en el portal de ARCA
5. La librería Python **`arca_arg`** como cliente SOAP

---

## 1. Librería arca_arg

### Instalación

```bash
pip install arca_arg
```

### Qué es y qué hace

`arca_arg` es una librería Python (open source, MIT) que simplifica la conexión con los servicios web SOAP de ARCA. Internamente:

- Usa **Zeep** como cliente SOAP para generar las requests XML
- Maneja la **autenticación WSAA** (Web Service de Autenticación y Autorización) de forma automática
- Cachea los **Tickets de Acceso (TA)** en disco para no pedir uno nuevo en cada llamada
- Expone una interfaz unificada (`ArcaWebService`) para interactuar con cualquier servicio web de ARCA

### Dependencias implícitas

La librería trae como dependencias:
- `zeep` — Cliente SOAP para Python
- `cryptography` / `pyOpenSSL` — Para firmar los tickets de autenticación
- `lxml` — Para parseo XML

### Módulos que se usan

```python
# Configuración global (se modifica antes de crear instancias)
import arca_arg.settings as arca_settings

# Módulo de autenticación (WSAA) — usa settings internamente
import arca_arg.auth as arca_auth

# Módulo de webservice — clase principal ArcaWebService
import arca_arg.webservice as arca_ws
from arca_arg.webservice import ArcaWebService

# Constantes de WSDLs (URLs de los servicios)
from arca_arg.settings import (
    WSDL_FEV1_HOM,          # WSFE homologación (testing)
    WSDL_FEV1_PROD,         # WSFE producción
    WSDL_CONSTANCIA_HOM,    # Padrón homologación
    WSDL_CONSTANCIA_PROD,   # Padrón producción
    WSDL_WSAA_PROD,         # WSAA producción
    WSDL_WSAA_HOM,          # WSAA homologación (referencia interna)
)
```

---

## 2. Certificado Digital y Clave Privada

ARCA usa un esquema de **autenticación por certificados X.509**. El contribuyente genera un par de claves (privada + CSR), ARCA firma el CSR y devuelve un certificado. Este certificado se usa para firmar las solicitudes de autenticación al WSAA.

### 2.1 Generar la clave privada

```bash
openssl genrsa -out mi_clave.key 2048
```

**Detalles:**
- Genera una clave RSA de **2048 bits** (mínimo aceptado por ARCA)
- El archivo `.key` es **secreto** y nunca debe compartirse
- Formato: PEM (texto plano con encabezado `-----BEGIN RSA PRIVATE KEY-----`)
- Tamaño típico: ~1.7 KB

### 2.2 Generar el CSR (Certificate Signing Request)

```bash
openssl req -new -key mi_clave.key \
  -subj "/C=AR/O=Mi Empresa SRL/CN=mi_certificado/serialNumber=CUIT 20123456789" \
  -out mi_clave.csr
```

**Campos del subject:**

| Campo | Valor | Descripción |
|-------|-------|-------------|
| `C` | `AR` | País (siempre Argentina) |
| `O` | `Mi Empresa SRL` | Razón social del contribuyente |
| `CN` | `mi_certificado` | Nombre identificador del certificado (libre) |
| `serialNumber` | `CUIT 20123456789` | CUIT del contribuyente con prefijo "CUIT " |

### 2.3 Obtener el certificado en el portal de ARCA

El proceso difiere según el ambiente:

#### Ambiente de Homologación (testing)

1. Ingresar al portal de ARCA con CUIT y clave fiscal
2. Ir a **"Administración de Certificados Digitales"**
3. Seleccionar **"WSASS - Autogestión Certificados Homologación"**
4. Crear un nuevo certificado subiendo el archivo `.csr`
5. Descargar el certificado resultante (`.crt` o `.pem`)

#### Ambiente de Producción

1. Ingresar al portal de ARCA con CUIT y clave fiscal
2. Ir a **"Administración de Certificados Digitales"**
3. Crear un nuevo certificado subiendo el archivo `.csr`
4. Descargar el certificado resultante (`.crt` o `.pem`)

### 2.4 Formato de los archivos

Ambos archivos deben estar en formato **PEM** (texto plano, codificado en Base64):

**Certificado (.crt / .pem):**
```
-----BEGIN CERTIFICATE-----
MIIDjTCCAnWgAwIBAgIIE+... (contenido Base64)
-----END CERTIFICATE-----
```

**Clave privada (.key):**
```
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA... (contenido Base64)
-----END RSA PRIVATE KEY-----
```

### 2.5 Manejo programático de certificados

En una aplicación real, los certificados pueden venir como **bytes en memoria** (por ejemplo, si se almacenan encriptados en base de datos). En ese caso, se deben escribir a **archivos temporales** antes de pasarlos a `arca_arg`, porque la librería espera **rutas de archivo** en disco:

```python
import tempfile
import os

def preparar_certificados(cert_bytes: bytes, key_bytes: bytes) -> tuple[str, str]:
    """
    Escribe certificados en archivos temporales y devuelve sus rutas.

    Args:
        cert_bytes: Contenido del certificado (.pem) en bytes
        key_bytes: Contenido de la clave privada (.key) en bytes

    Returns:
        Tupla (ruta_certificado, ruta_clave_privada)
    """
    temp_dir = tempfile.mkdtemp()

    cert_path = os.path.join(temp_dir, 'cert.pem')
    key_path = os.path.join(temp_dir, 'key.key')

    with open(cert_path, 'wb') as f:
        f.write(cert_bytes)
    with open(key_path, 'wb') as f:
        f.write(key_bytes)

    return cert_path, key_path
```

> **Importante:** Siempre limpiar los archivos temporales cuando ya no se necesiten (en el destructor del objeto o con un context manager).

---

## 3. CUIT del Contribuyente

El CUIT es el identificador fiscal único del emisor de comprobantes.

### Formato

- **Con guiones:** `20-12345678-9` (formato legible)
- **Sin guiones:** `20123456789` (formato que espera ARCA y `arca_arg`)

Siempre normalizar el CUIT removiendo guiones antes de pasarlo a la librería:

```python
cuit = '20-12345678-9'
cuit_normalizado = cuit.replace('-', '')  # '20123456789'
```

### Requisitos del CUIT

- Debe estar **inscripto** ante ARCA
- Debe tener **clave fiscal** activa (nivel 2 o superior)
- El certificado digital debe estar asociado a este CUIT
- Debe tener autorizado el servicio web que va a usar

---

## 4. Autorización del Servicio Web en ARCA

Tener certificado no es suficiente. Cada servicio web que se quiera usar debe ser **autorizado explícitamente** en el portal de ARCA para el CUIT y certificado correspondiente.

### Servicios web relevantes para facturación

| Servicio | Nombre técnico | Uso |
|----------|---------------|-----|
| **WSFE** | `wsfe` | Facturación electrónica (emitir, consultar comprobantes) |
| **Constancia de Inscripción** | `ws_sr_constancia_inscripcion` | Consultar datos del padrón (razón social, condición IVA) |

### Procedimiento de autorización

1. Ingresar al portal de ARCA con clave fiscal
2. Ir a **"Administración de Relaciones de Clave Fiscal"**
3. Buscar el servicio (ej: "Facturación Electrónica" o "ws_sr_constancia_inscripcion")
4. Asociar el servicio al certificado digital correspondiente
5. Confirmar la autorización

### Verificación

Si el servicio no está autorizado, al intentar conectar se recibirá un **error 600** de ARCA indicando que el CUIT no tiene permiso para acceder al servicio solicitado.

---

## 5. Ambientes de ARCA

ARCA ofrece dos ambientes completamente separados, con bases de datos y endpoints distintos:

### Homologación (testing)

- **Propósito:** Pruebas y desarrollo
- **Datos:** Ficticios, no tienen validez fiscal
- **Certificados:** Se generan desde "WSASS - Autogestión Certificados Homologación"
- **Comprobantes:** Se pueden emitir libremente sin consecuencias fiscales
- **WSDLs:** Usan las constantes `*_HOM` de `arca_arg.settings`

### Producción

- **Propósito:** Emisión real de comprobantes con validez fiscal
- **Datos:** Reales, cada comprobante emitido tiene validez legal
- **Certificados:** Se generan desde "Administración de Certificados Digitales" (producción)
- **Comprobantes:** Son fiscalmente válidos y no se pueden eliminar
- **WSDLs:** Usan las constantes `*_PROD` de `arca_arg.settings`

### Selección de ambiente en código

```python
import arca_arg.settings as config
from arca_arg.settings import WSDL_FEV1_HOM, WSDL_FEV1_PROD

# Para homologación:
config.PROD = False
wsdl_wsfe = WSDL_FEV1_HOM

# Para producción:
config.PROD = True
wsdl_wsfe = WSDL_FEV1_PROD
```

> **Regla:** El flag `config.PROD` afecta qué endpoint de WSAA se usa para autenticarse. El WSDL del servicio (FEV1_HOM o FEV1_PROD) determina contra qué servidor se envían las operaciones. **Ambos deben ser consistentes** (no mezclar PROD=True con WSDL_HOM o viceversa).

---

## 6. Configuración de arca_arg

La librería usa **configuración global** a través del módulo `arca_arg.settings`. Esto significa que los valores se setean como atributos del módulo y aplican a todas las instancias.

### Variables de configuración

```python
import arca_arg.settings as config

# OBLIGATORIAS
config.PRIVATE_KEY_PATH = '/ruta/a/clave.key'     # Ruta al archivo de clave privada
config.CERT_PATH = '/ruta/a/certificado.pem'       # Ruta al archivo de certificado
config.TA_FILES_PATH = '/ruta/a/tokens/'           # Directorio para cachear Tickets de Acceso
config.CUIT = '20123456789'                        # CUIT sin guiones
config.PROD = False                                # False=homologación, True=producción
```

### Detalle de TA_FILES_PATH

- Es el directorio donde `arca_arg` guarda los **Tickets de Acceso (TA)** serializados en disco
- Un TA es válido por **12 horas** (lo determina ARCA)
- Si existe un TA válido en este directorio, la librería lo reutiliza sin pedir uno nuevo al WSAA
- El directorio **debe existir** antes de crear una instancia de `ArcaWebService`
- El path debe **terminar con separador** de directorio (`/` en Linux/Mac)
- Los archivos se nombran por servicio: `wsfe.pkl`, `ws_sr_constancia_inscripcion.pkl`, etc.

```python
import os
import tempfile

# Crear directorio de cache de TA
ta_path = os.path.join(tempfile.gettempdir(), 'arca_ta_cache', 'testing', '20123456789')
os.makedirs(ta_path, exist_ok=True)
if not ta_path.endswith(os.sep):
    ta_path = ta_path + os.sep

config.TA_FILES_PATH = ta_path
```

### Problema de la configuración global

Dado que `arca_arg.settings` es un módulo global, **no es thread-safe** si se manejan múltiples CUITs simultáneamente. Además, algunos módulos internos de `arca_arg` importan valores de `settings` **por valor** (no por referencia), por lo que cambiar `config.CERT_PATH` después del import inicial puede no surtir efecto en esos módulos.

**Solución recomendada:** Re-aplicar la configuración también en los módulos internos que copian los valores:

```python
import arca_arg.settings as arca_settings
import arca_arg.auth as arca_auth
import arca_arg.webservice as arca_ws

def configurar_arca(cuit: str, cert_path: str, key_path: str, ta_path: str, produccion: bool):
    """
    Configura arca_arg para un CUIT específico.
    Debe llamarse antes de cada operación si se manejan múltiples CUITs.
    """
    # Configurar módulo settings principal
    arca_settings.PRIVATE_KEY_PATH = key_path
    arca_settings.CERT_PATH = cert_path
    arca_settings.TA_FILES_PATH = ta_path
    arca_settings.CUIT = cuit
    arca_settings.PROD = produccion

    # Re-aplicar en módulos que copian valores por valor
    arca_auth.PRIVATE_KEY_PATH = key_path
    arca_auth.CERT_PATH = cert_path
    arca_auth.TA_FILES_PATH = ta_path
    arca_auth.PROD = produccion
    arca_auth.WSDL_WSAA = (
        arca_settings.WSDL_WSAA_PROD if produccion
        else arca_settings.WSDL_WSAA_HOM
    )

    arca_ws.CUIT = cuit
```

> **Importante:** Esta función `configurar_arca()` debe llamarse **antes de cada operación** si la aplicación maneja múltiples CUITs, ya que otra instancia podría haber cambiado los settings entre medio.

---

## 7. Autenticación WSAA (Ticket de Acceso)

El WSAA (Web Service de Autenticación y Autorización) es el servicio que emite los **Tickets de Acceso (TA)** necesarios para operar con cualquier otro servicio de ARCA.

### Flujo de autenticación (manejado automáticamente por arca_arg)

```
┌─────────────┐     1. TRA firmado      ┌──────┐
│  Tu App     │ ────────────────────────→│ WSAA │
│  (arca_arg) │                          │      │
│             │ ←────────────────────────│      │
└─────────────┘     2. TA (token+sign)   └──────┘
       │
       │  3. Usa token+sign en cada request
       ▼
┌──────────────┐
│ WSFE / otro  │
│ servicio     │
└──────────────┘
```

1. **TRA (Ticket de Requerimiento de Acceso):** XML firmado con la clave privada del contribuyente, que solicita acceso a un servicio específico
2. **TA (Ticket de Acceso):** Contiene `token` y `sign`, válidos por 12 horas, para el servicio solicitado
3. **Uso:** Cada request a WSFE (u otro servicio) debe incluir `token` y `sign` del TA vigente

### Comportamiento del cache de TA

- `arca_arg` serializa el TA en archivos en `TA_FILES_PATH`
- Al crear un `ArcaWebService`, la librería:
  1. Busca un TA cacheado para el servicio
  2. Si existe y **no está vencido**, lo reutiliza
  3. Si no existe o está vencido, solicita uno nuevo al WSAA
- Si se intenta pedir un nuevo TA cuando ya existe uno válido, ARCA responde con error: **"El CEE ya posee un TA válido para el acceso al WSN solicitado"**

### Manejo del error "ya posee un TA válido"

Este error ocurre cuando:
- Se eliminó el archivo de cache local pero el TA sigue vigente en ARCA
- Otro proceso/servidor pidió un TA y el local no lo tiene
- Hay una condición de carrera entre múltiples workers

**Estrategia de reintentos:**

```python
for intento in range(3):
    try:
        ws = ArcaWebService(wsdl, servicio)
        break  # Éxito
    except Exception as e:
        mensaje = str(e).lower()
        if 'ya posee un ta valido' in mensaje and intento < 2:
            time.sleep(intento + 1)  # Esperar 1s, luego 2s
            continue  # Reintentar
        raise  # Error no recuperable
```

### Concurrencia y file locking

Si múltiples procesos (ej: workers de Celery) intentan obtener un TA simultáneamente, se puede producir una carrera. **Solución recomendada:** Usar file locking por servicio:

```python
import fcntl
from contextlib import contextmanager

@contextmanager
def ta_file_lock(ta_path: str, servicio: str):
    """Lock exclusivo por servicio para evitar carreras al obtener TA."""
    lock_path = os.path.join(ta_path, f'{servicio}.lock')
    lock_file = open(lock_path, 'a+')
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()

# Uso:
with ta_file_lock(ta_path, 'wsfe'):
    configurar_arca(cuit, cert_path, key_path, ta_path, produccion)
    ws = ArcaWebService(wsdl, 'wsfe')
```

> **Nota:** `fcntl.flock` es específico de sistemas Unix/Linux/Mac. En Windows se necesitaría `msvcrt.locking` o similar.

---

## 8. Creación de ArcaWebService

Una vez cumplidos todos los requisitos anteriores, se crea la instancia del servicio:

```python
from arca_arg.webservice import ArcaWebService
from arca_arg.settings import WSDL_FEV1_HOM, WSDL_FEV1_PROD

# 1. Configurar settings (ver sección 6)
configurar_arca(
    cuit='20123456789',
    cert_path='/tmp/cert.pem',
    key_path='/tmp/key.key',
    ta_path='/tmp/arca_ta_cache/testing/20123456789/',
    produccion=False,
)

# 2. Seleccionar WSDL según ambiente
wsdl = WSDL_FEV1_PROD if produccion else WSDL_FEV1_HOM

# 3. Crear instancia (esto dispara autenticación WSAA si no hay TA válido)
ws = ArcaWebService(wsdl, 'wsfe', enable_logging=False)
```

### Parámetros del constructor

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `wsdl` | `str` | URL del WSDL del servicio. Usar las constantes de `arca_arg.settings` |
| `service_name` | `str` | Nombre del servicio web según ARCA (`'wsfe'`, `'ws_sr_constancia_inscripcion'`, etc.) |
| `enable_logging` | `bool` | Si `True`, imprime en consola las requests/responses SOAP XML completas. Default: depende de la versión |

### Propiedades disponibles después de crear la instancia

```python
ws.token   # str — Token del TA (necesario para cada request)
ws.sign    # str — Firma del TA (necesario para cada request)
ws.cuit    # str — CUIT configurado en settings
```

### Métodos de la instancia

| Método | Retorno | Descripción |
|--------|---------|-------------|
| `ws.list_methods()` | `list[str]` | Lista todos los métodos disponibles del servicio |
| `ws.method_help('Metodo')` | `str` | Muestra la firma y parámetros de un método |
| `ws.get_type('NombreTipo')` | `dict` | Devuelve la estructura de un tipo complejo SOAP como diccionario |
| `ws.send_request('Metodo', data)` | objeto Zeep | Envía una request y devuelve la respuesta parseada por Zeep |

### Exploración del servicio

```python
# Ver todos los métodos disponibles de WSFE
ws.list_methods()
# → ['FECAESolicitar', 'FECompUltimoAutorizado', 'FECompConsultar',
#    'FEParamGetTiposCbte', 'FEParamGetTiposDoc', 'FEParamGetTiposIva', ...]

# Ver qué parámetros necesita un método
ws.method_help('FECAESolicitar')

# Ver la estructura de un tipo complejo
ws.get_type('FEAuthRequest')
# → {'Token': None, 'Sign': None, 'Cuit': None}

ws.get_type('FECAECabRequest')
# → {'CantReg': None, 'PtoVta': None, 'CbteTipo': None}
```

### Objeto Auth (requerido en cada request a WSFE)

Todas las operaciones de WSFE requieren un objeto `Auth` con las credenciales del TA:

```python
auth = ws.get_type('FEAuthRequest')
auth['Token'] = ws.token
auth['Sign'] = ws.sign
auth['Cuit'] = ws.cuit
```

Este objeto `auth` se pasa como campo `'Auth'` en el diccionario de datos de cada request.

---

## 9. Checklist de Requisitos

Antes de poder emitir comprobantes electrónicos, verificar que se cumplan todos estos puntos:

- [ ] **Clave privada RSA** generada (`.key`, 2048 bits mínimo)
- [ ] **CSR** generado y firmado por ARCA → certificado (`.crt` / `.pem`) descargado
- [ ] **CUIT** inscripto y con clave fiscal activa
- [ ] **Servicio `wsfe`** autorizado en el portal de ARCA para el certificado
- [ ] **Servicio `ws_sr_constancia_inscripcion`** autorizado (si se va a consultar el padrón)
- [ ] **Librería `arca_arg`** instalada (`pip install arca_arg`)
- [ ] **Directorio de TA** creado con permisos de escritura
- [ ] **Ambiente definido** (homologación o producción) con certificados correspondientes
- [ ] **Certificado y clave** accesibles como archivos en disco (o escritos a temporales)
- [ ] **Settings de `arca_arg`** configurados (incluyendo los módulos internos `auth` y `webservice`)

---

## 10. Errores Comunes en la Etapa de Setup

| Error | Causa | Solución |
|-------|-------|----------|
| `Error de autenticación` | Certificado y clave no coinciden | Regenerar CSR con la misma clave y obtener nuevo certificado |
| `Error 600` | CUIT no autorizado para el servicio | Autorizar el servicio web en el portal de ARCA |
| `ya posee un TA válido` | Se eliminó el cache local pero el TA sigue vigente en ARCA | Esperar y reintentar (ver sección 7), o esperar a que expire (~12h) |
| `FileNotFoundError` en cert/key | Los archivos no existen en la ruta configurada | Verificar rutas en `config.CERT_PATH` y `config.PRIVATE_KEY_PATH` |
| `TA_FILES_PATH` error | El directorio no existe o no tiene permisos | Crear el directorio con `os.makedirs(path, exist_ok=True)` |
| Certificado expirado | Los certificados de ARCA tienen fecha de vencimiento | Generar nuevo CSR, obtener nuevo certificado en el portal |
| `Connection refused` / timeout | Servicio de ARCA caído o red bloqueada | Verificar conectividad a los endpoints de ARCA (puertos 443) |
