# 9. Consulta de Padrón — ws_sr_constancia_inscripcion

## 9.1 Visión General

El servicio de padrón de ARCA permite consultar datos de un contribuyente a partir de su CUIT. Es un servicio **separado** de WSFE — usa su propio WSDL, su propio nombre de servicio para WSAA, y una convención de autenticación diferente.

### Datos que retorna el padrón

| Dato | Uso principal |
|------|---------------|
| Condición IVA | Obligatorio para `CondicionIVAReceptorId` (RG 5616) |
| Razón social / Nombre | Completar datos del receptor |
| Domicilio fiscal | Completar dirección del receptor |

### Cuándo consultar el padrón

```
¿El receptor tiene condicion_iva_id?
│
├── SÍ → No consultar
│
└── NO → ¿Tipo doc = CUIT/CUIL/CDI (80/86/87)?
    │
    ├── SÍ → ¿11 dígitos?
    │   │
    │   ├── SÍ → CONSULTAR PADRÓN
    │   │
    │   └── NO → No consultar (doc inválido)
    │
    └── NO → No consultar (DNI/Otro no está en padrón)
```

---

## 9.2 Diferencias con WSFE

El servicio de padrón es conceptualmente distinto a WSFE en varios aspectos:

### 9.2.1 WSDL y Nombre de Servicio

```python
from arca_arg.settings import (
    WSDL_FEV1_HOM, WSDL_FEV1_PROD,           # WSFE
    WSDL_CONSTANCIA_HOM, WSDL_CONSTANCIA_PROD, # Padrón
)

# WSFE
ws_wsfe = ArcaWebService(WSDL_FEV1_HOM, 'wsfe')

# Padrón — servicio diferente
ws_padron = ArcaWebService(WSDL_CONSTANCIA_HOM, 'ws_sr_constancia_inscripcion')
```

| Aspecto | WSFE | Padrón |
|---------|------|--------|
| WSDL Hom | `WSDL_FEV1_HOM` | `WSDL_CONSTANCIA_HOM` |
| WSDL Prod | `WSDL_FEV1_PROD` | `WSDL_CONSTANCIA_PROD` |
| Service name | `'wsfe'` | `'ws_sr_constancia_inscripcion'` |
| Operación | `FECAESolicitar`, etc. | `getPersona_v2` |
| TA | Propio (12h) | Propio (12h, independiente del de WSFE) |

### 9.2.2 Convención de Autenticación

**WSFE** usa un objeto `FEAuthRequest` tipado:

```python
# WSFE: autenticación via tipo SOAP
auth = ws.get_type('FEAuthRequest')
auth['Token'] = ws.token
auth['Sign'] = ws.sign
auth['Cuit'] = ws.cuit

data = {'Auth': auth, 'PtoVta': 1, 'CbteTipo': 6}
result = ws.send_request('FECompUltimoAutorizado', data)
```

**Padrón** pasa token/sign/cuit como parámetros directos (sin wrapper):

```python
# Padrón: autenticación como parámetros planos
data = {
    'token': ws.token,          # Minúscula, sin wrapper
    'sign': ws.sign,
    'cuitRepresentada': ws.cuit, # Nombre distinto a 'Cuit'
    'idPersona': 20301234567,    # CUIT a consultar (int)
}
result = ws.send_request('getPersona_v2', data)
```

> **Importante**: Esta diferencia es una fuente común de errores. Si se usa la convención de WSFE con el padrón (o viceversa), la llamada falla con error de autenticación.

### 9.2.3 TA Independiente

Cada servicio tiene su propio Ticket de Acceso. Tener un TA válido para WSFE **no** sirve para el padrón. Se necesita obtener un TA específico para `ws_sr_constancia_inscripcion`.

```python
# El ArcaClient mantiene dos instancias separadas:
self._wsfe: ArcaWebService          # TA para wsfe
self._ws_constancia: ArcaWebService  # TA para ws_sr_constancia_inscripcion

# Cada una tiene su propio token/sign:
self.wsfe.token             # Token de WSFE
self.ws_constancia.token    # Token de padrón (diferente)
```

---

## 9.3 Habilitación del Servicio

El servicio `ws_sr_constancia_inscripcion` debe estar **habilitado** en el portal de ARCA para el CUIT del facturador. Sin esta habilitación, la obtención del TA falla.

### Pasos para habilitar

1. Ingresar al portal ARCA con el CUIT del facturador
2. Ir a **Servicios Interactivos** → **Administrar relaciones**
3. Buscar el servicio `ws_sr_constancia_inscripcion`
4. Habilitar la relación para el certificado digital asociado

> **Nota**: Si el servicio no está habilitado, el `ArcaClient` lanzará `ArcaAuthError` al intentar crear `ws_constancia`. El autocompletado desde padrón fallará silenciosamente (no bloquea la facturación).

---

## 9.4 Implementación del Cliente

### 9.4.1 Inicialización Lazy

El servicio de padrón se inicializa solo cuando se necesita (lazy):

```python
@property
def ws_constancia(self) -> ArcaWebService:
    """
    Obtiene o crea la instancia del servicio de padrón.
    Se inicializa solo al primer uso.
    """
    if self._ws_constancia is None:
        wsdl = WSDL_CONSTANCIA_PROD if self.is_production else WSDL_CONSTANCIA_HOM
        self._ws_constancia = self._create_webservice_with_ta_fallback(
            wsdl=wsdl,
            service='ws_sr_constancia_inscripcion',
            error_prefix='Error al conectar con servicio de padrón',
        )
    return self._ws_constancia
```

**Por qué lazy**: No todas las operaciones necesitan el padrón. Si solo se emiten facturas donde todos los receptores ya tienen `condicion_iva_id`, nunca se inicializa este servicio (ahorra un login WSAA).

### 9.4.2 Método consultar_padron

```python
def consultar_padron(self, cuit_consulta: str) -> dict:
    """
    Consulta el padrón de ARCA para obtener datos de un contribuyente.

    Args:
        cuit_consulta: CUIT a consultar (sin guiones, 11 dígitos)

    Returns:
        Si éxito:
        {
            'success': True,
            'data': {
                'cuit': '20301234567',
                'razon_social': 'GARCIA, Juan Manuel',
                'direccion': 'Av. Corrientes 1234, CABA, Buenos Aires',
                'condicion_iva': 'IVA Responsable Inscripto',  # Nombre, NO ID
            }
        }

        Si no encontrado:
        {'success': False, 'error': 'Persona no encontrada'}

        Si error:
        Lanza ArcaError
    """
    try:
        self._ensure_settings()
        ws = self.ws_constancia

        cuit_int = int(cuit_consulta.replace('-', ''))

        # Dos formas de llamar según la versión de arca_arg:
        if hasattr(ws, 'get_persona'):
            # Versión nueva: método helper
            result = ws.get_persona(cuit_int)
        else:
            # Versión estándar: send_request directo
            data = {
                'token': ws.token,
                'sign': ws.sign,
                'cuitRepresentada': ws.cuit,
                'idPersona': cuit_int,
            }
            result = ws.send_request('getPersona_v2', data)

        # Parsear response
        if hasattr(result, 'personaReturn') and result.personaReturn:
            return self._parse_persona(result.personaReturn, cuit_consulta)

        return {'success': False, 'error': 'Persona no encontrada'}

    except ArcaError:
        raise
    except Exception as e:
        raise ArcaError(f'Error al consultar padrón: {str(e)}')
```

---

## 9.5 Parseo de la Respuesta del Padrón

### 9.5.1 Estructura del Objeto personaReturn

La respuesta de `getPersona_v2` viene como un objeto Zeep con esta estructura:

```
personaReturn (objeto Zeep)
│
├── idPersona: int              # CUIT consultado
├── tipoPersona: str            # 'FISICA' o 'JURIDICA'
│
├── nombre: str                  # Solo persona física
├── apellido: str                # Solo persona física
├── razonSocial: str            # Solo persona jurídica
│
├── datosGenerales              # Datos fiscales generales
│   ├── idPersona: int
│   ├── tipoPersona: str
│   └── ...
│
├── datosRegimenGeneral         # Presente si es Responsable Inscripto
│   ├── impuesto: list
│   ├── actividad: list
│   └── ...
│
├── datosMonotributo            # Presente si es Monotributo
│   ├── categoriaMonotributo: ...
│   ├── impuesto: list
│   └── ...
│
├── domicilio: list | object    # Domicilio(s) del contribuyente
│   └── [n]
│       ├── direccion: str       # "AV CORRIENTES 1234"
│       ├── localidad: str       # "CABA"
│       ├── descripcionProvincia: str  # "Buenos Aires"
│       ├── codPostal: str       # "C1043AAZ"
│       └── ...
│
└── errorConstancia             # Si hubo error
    ├── error: list
    │   └── [n]: str
    └── ...
```

### 9.5.2 Parseo Completo

```python
def _parse_persona(self, persona, cuit_consulta: str) -> dict:
    """
    Parsea el objeto personaReturn de ARCA.

    Maneja:
    - Personas físicas (nombre + apellido)
    - Personas jurídicas (razonSocial)
    - Domicilio como lista u objeto único
    - Condición IVA inferida desde datos impositivos
    """

    # --- Razón Social ---
    nombre = getattr(persona, 'nombre', '') or ''
    apellido = getattr(persona, 'apellido', '') or ''

    if apellido and nombre:
        # Persona física: "GARCIA, Juan Manuel"
        razon_social = f'{apellido}, {nombre}'
    elif nombre:
        razon_social = nombre
    else:
        # Persona jurídica: "EMPRESA S.A."
        razon_social = getattr(persona, 'razonSocial', '') or str(cuit_consulta)

    # --- Domicilio ---
    direccion = None
    if hasattr(persona, 'domicilio') and persona.domicilio:
        # Puede venir como lista o como objeto único
        dom = (
            persona.domicilio[0]
            if isinstance(persona.domicilio, list)
            else persona.domicilio
        )
        direccion = self._format_domicilio(dom)

    # --- Condición IVA ---
    condicion_iva = self._inferir_condicion_iva(persona)

    return {
        'success': True,
        'data': {
            'cuit': cuit_consulta.replace('-', ''),
            'razon_social': razon_social,
            'direccion': direccion,
            'condicion_iva': condicion_iva,  # Nombre (str), NO ID (int)
        }
    }
```

### 9.5.3 Formateo de Domicilio

```python
def _format_domicilio(self, domicilio) -> str | None:
    """
    Formatea un objeto domicilio de ARCA en un string legible.

    Ejemplo resultado: "AV CORRIENTES 1234, CABA, Buenos Aires"
    """
    parts = []
    for attr in ['direccion', 'localidad', 'descripcionProvincia']:
        val = getattr(domicilio, attr, None)
        if val:
            parts.append(str(val))
    return ', '.join(parts) if parts else None
```

### 9.5.4 Inferencia de Condición IVA

El padrón **no tiene un campo explícito** para la condición IVA. Se infiere desde los datos impositivos:

```python
def _inferir_condicion_iva(self, persona) -> str | None:
    """
    Infiere la condición IVA desde la estructura de datos del padrón.

    Lógica:
    - Si tiene datosRegimenGeneral → es Responsable Inscripto
    - Si tiene datosMonotributo → es Responsable Monotributo
    - Si no tiene ninguno → no se puede determinar (retorna None)

    Returns:
        Nombre de la condición IVA (str) o None.
        NOTA: retorna el NOMBRE, no el ID numérico.
    """
    condicion_iva = None

    if hasattr(persona, 'datosGenerales') and persona.datosGenerales:
        # datosRegimenGeneral indica RI
        if hasattr(persona, 'datosRegimenGeneral') and persona.datosRegimenGeneral:
            condicion_iva = 'IVA Responsable Inscripto'
        # datosMonotributo indica Monotributo
        elif hasattr(persona, 'datosMonotributo') and persona.datosMonotributo:
            condicion_iva = 'Responsable Monotributo'

    return condicion_iva
```

**Limitaciones de la inferencia**:

| Condición real | ¿Se puede detectar? | Cómo |
|----------------|---------------------|------|
| Responsable Inscripto | Sí | `datosRegimenGeneral` presente |
| Monotributo | Sí | `datosMonotributo` presente |
| Exento | No directamente | No hay campo específico |
| Consumidor Final | No | Los CF no tienen CUIT (usan DNI) |
| Sujeto No Categorizado | No | No hay campo específico |

> **Nota**: Para condiciones que no se pueden inferir, la función retorna `None` y el sistema debe usar otro mecanismo (ingreso manual, fallback por tipo de documento).

---

## 9.6 Conversión de Nombre a ID

El padrón retorna la condición IVA como **nombre** (string). Para el campo `CondicionIVAReceptorId` de WSFE se necesita el **ID** (int):

```python
CONDICIONES_IVA = {
    1:  'IVA Responsable Inscripto',
    4:  'IVA Sujeto Exento',
    5:  'Consumidor Final',
    6:  'Responsable Monotributo',
    7:  'Sujeto No Categorizado',
    8:  'Proveedor del Exterior',
    9:  'Cliente del Exterior',
    10: 'IVA Liberado – Ley Nº 19.640',
    11: 'IVA Responsable Inscripto – Agente de Percepción',
    13: 'Monotributista Social',
    15: 'IVA No Alcanzado',
    16: 'Monotributo Trabajador Independiente Promotido',
}


def nombre_condicion_iva_a_id(nombre: str) -> int | None:
    """
    Convierte nombre de condición IVA a su ID numérico.

    Normaliza el texto (minúsculas, quita guiones especiales,
    colapsa espacios) antes de comparar.

    Ejemplos:
        'IVA Responsable Inscripto' → 1
        'Responsable Monotributo'   → 6
        'Consumidor Final'          → 5
        'algo desconocido'          → None
    """
    if not nombre:
        return None

    def normalize(text: str) -> str:
        return ' '.join(text.lower().replace('–', '-').split())

    nombre_norm = normalize(nombre)
    for cond_id, desc in CONDICIONES_IVA.items():
        if normalize(desc) == nombre_norm:
            return cond_id

    return None


# Uso:
condicion_nombre = 'IVA Responsable Inscripto'  # Del padrón
condicion_id = nombre_condicion_iva_a_id(condicion_nombre)
# condicion_id = 1
```

---

## 9.7 Autocompletado de Receptor — Flujo Completo

El autocompletado ocurre automáticamente durante el procesamiento de cada factura, **antes** de construir el request WSFE:

```python
def autocompletar_condicion_iva_receptor(client, factura) -> None:
    """
    Intenta completar la condición IVA del receptor consultando el padrón.

    Precondiciones para consultar:
    1. El receptor NO tiene condicion_iva_id (si ya lo tiene, no consulta)
    2. El tipo de documento es CUIT (80), CUIL (86), o CDI (87)
    3. El número de documento tiene exactamente 11 dígitos

    Datos que se actualizan si la consulta es exitosa:
    - condicion_iva_id: ID numérico de la condición IVA
    - razon_social: solo si estaba vacía o era un placeholder ("CUIT 20...")
    - direccion: solo si estaba vacía

    Si el padrón falla por cualquier motivo, NO bloquea la facturación.
    Se loguea un warning y se continúa con lo que tenga el receptor.
    """
    receptor = factura.receptor
    if not receptor:
        return

    # Si ya tiene condición IVA, no consultar
    if receptor.condicion_iva_id is not None:
        return

    # Solo CUIT/CUIL/CDI pueden consultarse en el padrón
    if receptor.doc_tipo not in (80, 86, 87):
        return

    # Validar formato: 11 dígitos
    doc = (receptor.doc_nro or '').replace('-', '').replace(' ', '')
    if not doc.isdigit() or len(doc) != 11:
        return

    try:
        result = client.consultar_padron(doc)
        if not result.get('success'):
            return

        data = result.get('data') or {}

        # Actualizar condición IVA
        condicion_iva_nombre = data.get('condicion_iva')
        if condicion_iva_nombre:
            receptor.condicion_iva_id = nombre_condicion_iva_a_id(condicion_iva_nombre)

        # Actualizar razón social (solo si vacía o placeholder)
        if data.get('razon_social') and (
            not receptor.razon_social
            or receptor.razon_social.startswith('CUIT ')
        ):
            receptor.razon_social = data['razon_social']

        # Actualizar dirección (solo si vacía)
        if data.get('direccion') and not receptor.direccion:
            receptor.direccion = data['direccion']

        # Flush para que los cambios estén disponibles en la misma transacción
        # (no commit — se commitea con la factura)
        db.session.flush()

    except (
        ArcaAuthError,
        ArcaNetworkError,
        ArcaError,
        ValueError,
        RuntimeError,
        ConnectionError,
        TimeoutError,
        OSError,
    ) as exc:
        # Si padrón falla, NO bloquear.
        # Loguear y continuar con lo que tenga el receptor.
        logger.warning(
            'No se pudo autocompletar condicion IVA para receptor %s: %s',
            receptor.doc_nro,
            str(exc),
        )
```

### 9.7.1 Diagrama del Flujo en Facturación

```
procesar_factura(client, factura)
│
├── FECompUltimoAutorizado → número
│
├── FacturaBuilder.set_comprobante(...)
├── FacturaBuilder.set_fechas(...)
├── FacturaBuilder.set_receptor(...)
│
├── ★ autocompletar_condicion_iva_receptor(client, factura)
│   │
│   ├── ¿Ya tiene condicion_iva_id? → SÍ → skip
│   │
│   ├── ¿doc_tipo = 80/86/87? → NO → skip
│   │
│   ├── ¿11 dígitos? → NO → skip
│   │
│   └── consultar_padron(doc_nro)
│       │
│       ├── Éxito → actualizar receptor
│       │   ├── condicion_iva_id = nombre_a_id(resultado)
│       │   ├── razon_social (si vacía)
│       │   └── direccion (si vacía)
│       │
│       └── Fallo → warning, continuar
│
├── ★ resolver_condicion_iva_receptor_id(factura)
│   │   (busca ID, nombre, tipo doc, o falla)
│   │
│   ├── Encontrado → usar
│   └── None → RECHAZAR factura
│
├── ★ Override clase B → condicion = 5
│
├── normalizar_importes(...)
├── FacturaBuilder.set_importes(...)
├── FacturaBuilder.add_iva(...)
├── FacturaBuilder.build()
│
└── WSFEService.autorizar(request)
```

### 9.7.2 Cuándo No se Consulta el Padrón

| Escenario | Motivo |
|-----------|--------|
| `condicion_iva_id` ya existe | Dato ya resuelto, no gastar una consulta |
| `doc_tipo = 96` (DNI) | Los DNI no están en el padrón ARCA |
| `doc_tipo = 99` (Otro) | Documentos genéricos no están en el padrón |
| `doc_nro` con menos de 11 dígitos | No es un CUIT válido |
| Servicio `ws_sr_constancia_inscripcion` no habilitado | `ArcaAuthError` capturada silenciosamente |

---

## 9.8 Implementación Standalone

Para consultar el padrón fuera del flujo de facturación (por ejemplo, para un endpoint de API):

```python
from arca_integration import ArcaClient
from arca_integration.exceptions import ArcaError


def consultar_datos_contribuyente(
    cuit_emisor: str,
    cert: bytes,
    key: bytes,
    ambiente: str,
    cuit_consulta: str,
) -> dict:
    """
    Consulta datos de un contribuyente en el padrón de ARCA.

    Args:
        cuit_emisor: CUIT del facturador (quien hace la consulta)
        cert: Certificado digital (bytes)
        key: Clave privada (bytes)
        ambiente: 'testing' o 'production'
        cuit_consulta: CUIT a consultar

    Returns:
        {
            'success': True,
            'data': {
                'cuit': '20301234567',
                'razon_social': 'GARCIA, Juan Manuel',
                'direccion': 'Av. Corrientes 1234, CABA, Buenos Aires',
                'condicion_iva': 'IVA Responsable Inscripto',
                'condicion_iva_id': 1,  # ID numérico (resuelto)
            }
        }
        o
        {'success': False, 'error': 'mensaje'}
    """
    try:
        client = ArcaClient(
            cuit=cuit_emisor,
            cert=cert,
            key=key,
            ambiente=ambiente,
        )

        result = client.consultar_padron(cuit_consulta)

        if not result.get('success'):
            return result

        # Enriquecer con ID numérico
        data = result['data']
        condicion_nombre = data.get('condicion_iva')
        data['condicion_iva_id'] = nombre_condicion_iva_a_id(condicion_nombre)

        return result

    except ArcaError as e:
        return {
            'success': False,
            'error': str(e),
        }


# Uso:
resultado = consultar_datos_contribuyente(
    cuit_emisor='20301234567',
    cert=cert_bytes,
    key=key_bytes,
    ambiente='production',
    cuit_consulta='30712345678',
)

if resultado['success']:
    print(f"Razón Social: {resultado['data']['razon_social']}")
    print(f"Condición IVA: {resultado['data']['condicion_iva']}")
    print(f"Condición IVA ID: {resultado['data']['condicion_iva_id']}")
    print(f"Dirección: {resultado['data']['direccion']}")
```

---

## 9.9 Manejo de Errores del Padrón

### 9.9.1 Errores Comunes

| Error | Causa | Acción |
|-------|-------|--------|
| `ArcaAuthError` "Error al conectar con servicio de padrón" | Servicio no habilitado para el CUIT | Habilitar `ws_sr_constancia_inscripcion` en portal ARCA |
| `ArcaAuthError` "ya posee un TA válido" | Concurrencia en obtención de TA | Reintentar (manejado automáticamente por `_create_webservice_with_ta_fallback`) |
| `{'success': False, 'error': 'Persona no encontrada'}` | CUIT no existe en el padrón | Verificar CUIT o ingresar datos manualmente |
| `ArcaError` "Error al consultar padrón" | Error de red, timeout, o error interno de ARCA | Reintentar o ingresar datos manualmente |

### 9.9.2 Principio de No Bloqueo

La consulta de padrón **nunca debe bloquear** la facturación. Si falla:

1. Se loguea un warning
2. Se continúa con los datos que tenga el receptor
3. Si después no se puede resolver `CondicionIVAReceptorId`, **ahí sí** se rechaza la factura — pero por falta de datos, no por falla del padrón

```python
# CORRECTO: padrón falla → warning → continuar
try:
    autocompletar_condicion_iva_receptor(client, factura)
except Exception:
    pass  # Warning ya logueado dentro de la función

# Después, si sigue sin condición IVA:
condicion = resolver_condicion_iva_receptor_id(factura)
if condicion is None:
    raise ValueError('No se pudo determinar la condicion IVA')
```

### 9.9.3 Caching de Resultados

El resultado del padrón se persiste en el receptor:

```python
# Después de consultar el padrón:
receptor.condicion_iva_id = 1          # Se guarda en BD
receptor.razon_social = 'GARCIA, Juan' # Se guarda en BD
receptor.direccion = 'Av. Corrientes'  # Se guarda en BD
db.session.flush()

# En la próxima factura para el mismo receptor:
if receptor.condicion_iva_id is not None:
    return  # No vuelve a consultar el padrón
```

Esto evita consultar el padrón múltiples veces para el mismo receptor — una vez que se completa, no se vuelve a consultar.

---

## 9.10 Consideraciones de Performance

### 9.10.1 Costo por Consulta

Cada consulta de padrón implica:
1. Si es la primera: obtener TA para `ws_sr_constancia_inscripcion` (~2-5 segundos)
2. La consulta SOAP en sí (~0.5-2 segundos)

En un lote de 500 facturas con 200 receptores únicos sin `condicion_iva_id`, esto agrega ~200-400 segundos al procesamiento.

### 9.10.2 Optimización: Pre-cargar Antes de Facturar

Para evitar el impacto durante la facturación masiva, se puede pre-cargar la condición IVA de los receptores desde el módulo de gestión de receptores:

```python
def precargar_condicion_iva_receptores(
    client: ArcaClient,
    receptores: list,
) -> dict:
    """
    Consulta el padrón para todos los receptores que no tienen condición IVA.
    Útil para ejecutar ANTES de la facturación masiva.

    Returns:
        {'completados': int, 'fallidos': int, 'omitidos': int}
    """
    completados = 0
    fallidos = 0
    omitidos = 0

    for receptor in receptores:
        # Ya tiene condición IVA
        if receptor.condicion_iva_id is not None:
            omitidos += 1
            continue

        # Solo CUIT/CUIL/CDI
        if receptor.doc_tipo not in (80, 86, 87):
            omitidos += 1
            continue

        doc = (receptor.doc_nro or '').replace('-', '').replace(' ', '')
        if not doc.isdigit() or len(doc) != 11:
            omitidos += 1
            continue

        try:
            result = client.consultar_padron(doc)
            if result.get('success'):
                data = result['data']
                if data.get('condicion_iva'):
                    receptor.condicion_iva_id = nombre_condicion_iva_a_id(
                        data['condicion_iva']
                    )
                if data.get('razon_social') and not receptor.razon_social:
                    receptor.razon_social = data['razon_social']
                if data.get('direccion') and not receptor.direccion:
                    receptor.direccion = data['direccion']
                completados += 1
            else:
                fallidos += 1
        except Exception:
            fallidos += 1

    db.session.commit()
    return {
        'completados': completados,
        'fallidos': fallidos,
        'omitidos': omitidos,
    }
```

### 9.10.3 Rate Limiting

ARCA no documenta un límite de rate explícito para el padrón, pero en la práctica:
- Consultas muy rápidas (>10/segundo) pueden resultar en timeouts
- Se recomienda no agregar delay artificial, pero sí manejar timeouts gracefully
- El procesamiento secuencial natural (una consulta por receptor) ya actúa como rate limiting implícito

---

## 9.11 Testing

```python
def test_consulta_padron_exitosa(client):
    """Test con un CUIT conocido (usar CUIT de testing de ARCA)."""
    result = client.consultar_padron('20000000516')  # CUIT de prueba ARCA

    assert result['success'] is True
    assert 'data' in result
    assert result['data']['cuit'] == '20000000516'
    assert result['data']['razon_social']  # No vacío


def test_consulta_padron_cuit_inexistente(client):
    """Test con CUIT que no existe."""
    result = client.consultar_padron('99999999999')

    assert result['success'] is False


def test_nombre_condicion_iva_a_id():
    """Test de conversión nombre → ID."""
    assert nombre_condicion_iva_a_id('IVA Responsable Inscripto') == 1
    assert nombre_condicion_iva_a_id('Responsable Monotributo') == 6
    assert nombre_condicion_iva_a_id('Consumidor Final') == 5
    assert nombre_condicion_iva_a_id('algo inventado') is None
    assert nombre_condicion_iva_a_id(None) is None
    assert nombre_condicion_iva_a_id('') is None


def test_autocompletar_no_consulta_si_ya_tiene_id():
    """Si el receptor ya tiene condicion_iva_id, no debe consultar."""
    # Mock receptor con condicion_iva_id
    receptor = Mock(condicion_iva_id=1, doc_tipo=80, doc_nro='20301234567')
    factura = Mock(receptor=receptor)

    # Si consulta padrón, el mock fallaría
    client = Mock(spec=ArcaClient)

    autocompletar_condicion_iva_receptor(client, factura)

    # No debería haber llamado a consultar_padron
    client.consultar_padron.assert_not_called()


def test_autocompletar_no_consulta_dni():
    """No debe consultar padrón para receptores con DNI."""
    receptor = Mock(condicion_iva_id=None, doc_tipo=96, doc_nro='12345678')
    factura = Mock(receptor=receptor)

    client = Mock(spec=ArcaClient)

    autocompletar_condicion_iva_receptor(client, factura)

    client.consultar_padron.assert_not_called()
```
