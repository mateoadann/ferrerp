# 7. Parseo de Respuestas — Estructura del Response, Errores y Observaciones

## 7.1 Naturaleza de las Respuestas de ARCA

ARCA expone servicios SOAP. La librería `arca_arg` usa **Zeep** como cliente SOAP, por lo tanto todas las respuestas son **objetos Zeep** — no son dicts ni JSON. Esto tiene implicaciones importantes:

```python
# ❌ INCORRECTO — los responses no son dicts
result['FeCabResp']['Resultado']       # TypeError
result.get('FeCabResp')                # AttributeError

# ✅ CORRECTO — acceso con dot notation
result.FeCabResp.Resultado             # 'A', 'R', o 'P'
result.FeDetResp.FECAEDetResponse      # Lista de objetos Zeep

# Para campos que pueden no existir, usar getattr:
getattr(result.FeCabResp, 'Reproceso', None)
```

### Serialización de Objetos Zeep

Para loguear, guardar en base de datos, o inspeccionar responses, se necesita convertir a dict:

```python
import importlib

def zeep_to_dict(value):
    """Convierte un objeto Zeep a dict/list recursivamente."""
    # Tipos básicos
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    # Decimal
    from decimal import Decimal
    if isinstance(value, Decimal):
        return float(value)

    # Fecha/datetime
    from datetime import date, datetime
    if isinstance(value, (date, datetime)):
        return value.isoformat()

    # Dict (ya convertido)
    if isinstance(value, dict):
        return {str(k): zeep_to_dict(v) for k, v in value.items()}

    # Lista/tupla/set
    if isinstance(value, (list, tuple, set)):
        return [zeep_to_dict(v) for v in value]

    # Objeto Zeep → intentar serialize_object de zeep.helpers
    try:
        zeep_helpers = importlib.import_module('zeep.helpers')
        serialized = zeep_helpers.serialize_object(value)
        if serialized is not value:
            return zeep_to_dict(serialized)
    except Exception:
        pass

    # Fallback: __dict__
    if hasattr(value, '__dict__'):
        result = {}
        for key, attr in vars(value).items():
            if not str(key).startswith('_'):
                result[str(key)] = zeep_to_dict(attr)
        if result:
            return result

    return str(value)
```

---

## 7.2 Respuesta de FECAESolicitar — Estructura Completa

### 7.2.1 Estructura del Objeto Response

```
FECAESolicitarResult (objeto Zeep raíz)
│
├── FeCabResp                    # Cabecera de respuesta
│   ├── Cuit: int                # CUIT del emisor
│   ├── PtoVta: int              # Punto de venta
│   ├── CbteTipo: int            # Tipo de comprobante
│   ├── FchProceso: str          # Fecha/hora de procesamiento (YYYYMMDDHHMMSS)
│   ├── CantReg: int             # Cantidad de registros procesados
│   ├── Resultado: str           # 'A' (Aprobado), 'R' (Rechazado), 'P' (Parcial)
│   └── Reproceso: str           # 'S' si es reproceso, 'N' si es original
│
├── FeDetResp                    # Detalle de respuesta
│   └── FECAEDetResponse: list   # Lista de responses (uno por comprobante)
│       └── [0]                  # Primer (y generalmente único) comprobante
│           ├── Concepto: int
│           ├── DocTipo: int
│           ├── DocNro: int
│           ├── CbteDesde: int   # Número asignado (desde)
│           ├── CbteHasta: int   # Número asignado (hasta)
│           ├── CbteFch: str     # Fecha del comprobante (YYYYMMDD)
│           ├── Resultado: str   # 'A' o 'R' para este comprobante específico
│           ├── CAE: str         # Código de Autorización Electrónica (14 dígitos)
│           ├── CAEFchVto: str   # Vencimiento del CAE (YYYYMMDD)
│           └── Observaciones    # Solo si hay observaciones
│               └── Obs: list
│                   └── [n]
│                       ├── Code: int
│                       └── Msg: str
│
└── Errors                       # Solo si hay errores globales
    └── Err: list
        └── [n]
            ├── Code: int
            └── Msg: str
```

### 7.2.2 Los Tres Resultados Posibles

| Resultado | Significado | CAE | Observaciones | Errores |
|-----------|-------------|-----|---------------|---------|
| `'A'` (Aprobado) | Comprobante autorizado exitosamente | Presente (14 dígitos) | Puede haber (warnings) | No |
| `'R'` (Rechazado) | Comprobante rechazado por validación | `None` o vacío | Contienen el motivo del rechazo | Puede haber |
| `'P'` (Parcial) | Solo en lotes: algunos aprobados, otros rechazados | Varía por comprobante | Varía por comprobante | Puede haber |

> **Importante**: En nuestro caso siempre enviamos `CantReg = 1`, así que `'P'` (Parcial) no debería ocurrir nunca. Si se envían múltiples comprobantes en un lote, cada `FECAEDetResponse` tiene su propio `Resultado`.

### 7.2.3 Resultado 'A' — Comprobante Aprobado

```python
# Response exitoso (objeto Zeep)
result.FeCabResp.Resultado           # 'A'
result.FeCabResp.Reproceso           # 'N' (original) o 'S' (reproceso)

det = result.FeDetResp.FECAEDetResponse[0]
det.Resultado                        # 'A'
det.CAE                              # '74132917530459' (14 dígitos)
det.CAEFchVto                        # '20260319' (formato YYYYMMDD)
det.CbteDesde                        # 15 (número asignado)
det.CbteHasta                        # 15

# ⚠️ Un comprobante Aprobado PUEDE tener Observaciones (son warnings)
det.Observaciones                    # Puede no ser None
```

### 7.2.4 Resultado 'R' — Comprobante Rechazado

Cuando ARCA rechaza, el motivo viene en **Observaciones del detalle** (no en Errors):

```python
result.FeCabResp.Resultado           # 'R'

det = result.FeDetResp.FECAEDetResponse[0]
det.Resultado                        # 'R'
det.CAE                              # None o ''
det.CAEFchVto                        # None o ''

# El motivo del rechazo está en Observaciones
det.Observaciones.Obs                # Lista de observaciones
# [
#   Obs(Code=10048, Msg='El campo ImpTotal no coincide con la suma...'),
# ]
```

### 7.2.5 Errores Globales vs Observaciones

ARCA tiene **dos** mecanismos para reportar problemas, y es crítico entender la diferencia:

```
┌─────────────────────────────────────────────────────────────────┐
│ Errors (result.Errors.Err)                                     │
│                                                                 │
│ - Errores GLOBALES del request                                  │
│ - Problemas de autenticación, formato, estructura               │
│ - El request completo falló                                     │
│ - Ejemplo: Token expirado, CUIT inválido, estructura malformada│
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Observaciones (det.Observaciones.Obs)                           │
│                                                                 │
│ - Observaciones POR COMPROBANTE                                 │
│ - Motivos de rechazo de validación de negocio                   │
│ - El request se procesó pero el comprobante fue rechazado       │
│ - Ejemplo: importes no cuadran, fecha fuera de rango,           │
│   condición IVA inválida                                        │
│                                                                 │
│ TAMBIÉN pueden ser WARNINGS en comprobantes aprobados ('A')     │
│ - Ejemplo: "Se procesó como reproceso"                          │
└─────────────────────────────────────────────────────────────────┘
```

**Regla práctica**: Para obtener el mensaje de error completo de un rechazo, combinar **ambos**:

```python
# En WSFEService.autorizar():
errores = result.get('errores', [])
observaciones = result.get('observaciones', [])
all_messages = errores + observaciones
error_msg = '; '.join([e.get('msg', '') for e in all_messages if e.get('msg')])
```

---

## 7.3 Función de Parseo Completa — _parse_cae_response

Esta función convierte el objeto Zeep en un dict Python normalizado:

```python
def parse_cae_response(result) -> dict:
    """
    Parsea la respuesta raw de FECAESolicitar (objeto Zeep)
    a un dict normalizado.

    Estructura de retorno:
    {
        'resultado': str,              # 'A', 'R', o 'P'
        'reproceso': str | None,       # 'S' o 'N'
        'cae': str | None,             # 14 dígitos o None
        'cae_vencimiento': str | None, # 'YYYYMMDD' o None
        'numero_comprobante': int | None,
        'observaciones': [{'code': int, 'msg': str}, ...],
        'errores': [{'code': int, 'msg': str}, ...],
    }
    """
    response = {
        'resultado': None,
        'reproceso': None,
        'cae': None,
        'cae_vencimiento': None,
        'numero_comprobante': None,
        'observaciones': [],
        'errores': [],
    }

    # --- 1. Cabecera (FeCabResp) ---
    if hasattr(result, 'FeCabResp') and result.FeCabResp:
        response['resultado'] = result.FeCabResp.Resultado
        response['reproceso'] = getattr(result.FeCabResp, 'Reproceso', None)

    # --- 2. Detalle (FeDetResp) ---
    if hasattr(result, 'FeDetResp') and result.FeDetResp:
        det_list = result.FeDetResp.FECAEDetResponse

        if det_list:
            # Puede venir como lista o como objeto único
            det = det_list[0] if isinstance(det_list, list) else det_list

            # CAE y datos del comprobante
            response['cae'] = str(det.CAE) if det.CAE else None
            response['cae_vencimiento'] = str(det.CAEFchVto) if det.CAEFchVto else None
            response['numero_comprobante'] = det.CbteDesde

            # El resultado del detalle tiene prioridad sobre la cabecera
            # (en caso de lotes, cada detalle tiene su propio resultado)
            response['resultado'] = det.Resultado

            # Observaciones del comprobante
            if hasattr(det, 'Observaciones') and det.Observaciones:
                obs_container = det.Observaciones

                # Zeep puede wrappear en .Obs o dar directamente la lista
                obs_list = (
                    obs_container.Obs
                    if hasattr(obs_container, 'Obs')
                    else obs_container
                )

                if obs_list:
                    # Puede ser un objeto único o una lista
                    if not isinstance(obs_list, list):
                        obs_list = [obs_list]

                    response['observaciones'] = [
                        {
                            'code': getattr(obs, 'Code', None),
                            'msg': getattr(obs, 'Msg', ''),
                        }
                        for obs in obs_list
                    ]

    # --- 3. Errores globales (Errors) ---
    if hasattr(result, 'Errors') and result.Errors:
        err_container = result.Errors

        # Mismo patrón: puede estar en .Err o directamente
        err_list = (
            err_container.Err
            if hasattr(err_container, 'Err')
            else err_container
        )

        if err_list:
            if not isinstance(err_list, list):
                err_list = [err_list]

            response['errores'] = [
                {
                    'code': getattr(err, 'Code', None),
                    'msg': getattr(err, 'Msg', ''),
                }
                for err in err_list
            ]

    return response
```

### 7.3.1 Por Qué el Parseo Defensivo

Zeep tiene comportamientos inconsistentes según la estructura del WSDL y los datos retornados:

```python
# Problema 1: Lista vs objeto único
# A veces FECAEDetResponse es una lista, a veces es un objeto
det_list = result.FeDetResp.FECAEDetResponse
det = det_list[0] if isinstance(det_list, list) else det_list

# Problema 2: Observaciones wrapeadas
# A veces viene det.Observaciones.Obs, a veces det.Observaciones directamente
obs_list = (
    obs_container.Obs
    if hasattr(obs_container, 'Obs')
    else obs_container
)

# Problema 3: Campos que pueden ser None o no existir
# CAE es None cuando el comprobante fue rechazado
response['cae'] = str(det.CAE) if det.CAE else None

# Problema 4: Reproceso puede no existir en versiones antiguas del WSDL
response['reproceso'] = getattr(result.FeCabResp, 'Reproceso', None)
```

**Regla general**: Siempre usar `hasattr()` antes de acceder a sub-objetos, `getattr()` con default para campos opcionales, e `isinstance(x, list)` antes de indexar.

---

## 7.4 Interpretación del Resultado Parseado

### 7.4.1 Determinar Éxito o Fracaso

```python
def interpretar_resultado(parsed_response: dict) -> dict:
    """
    Interpreta el resultado parseado de FECAESolicitar.

    Returns:
        {
            'success': bool,
            'cae': str | None,
            'cae_vencimiento': str | None,  # ISO format (YYYY-MM-DD)
            'numero_comprobante': int | None,
            'observaciones': list,
            'error_code': str | None,
            'error_message': str | None,
        }
    """
    resultado = parsed_response.get('resultado')

    if resultado == 'A':
        # --- APROBADO ---
        return {
            'success': True,
            'cae': parsed_response['cae'],
            'cae_vencimiento': parse_fecha_arca(parsed_response['cae_vencimiento']),
            'numero_comprobante': parsed_response['numero_comprobante'],
            'observaciones': parsed_response.get('observaciones', []),
            # Aprobado puede tener observaciones (warnings, reproceso info)
        }
    else:
        # --- RECHAZADO ---
        errores = parsed_response.get('errores', [])
        observaciones = parsed_response.get('observaciones', [])

        # Combinar errores y observaciones para el mensaje
        all_messages = errores + observaciones
        error_msg = '; '.join(
            [e.get('msg', '') for e in all_messages if e.get('msg')]
        )

        # El código de error viene del primer error
        error_code = errores[0].get('code') if errores else None

        # Si no hay errores pero sí observaciones, el código viene de ahí
        if error_code is None and observaciones:
            error_code = observaciones[0].get('code')

        return {
            'success': False,
            'error_code': str(error_code) if error_code else None,
            'error_message': error_msg or 'Error desconocido al autorizar comprobante',
            'errores': errores,
            'observaciones': observaciones,
        }


def parse_fecha_arca(fecha_str: str | None) -> str | None:
    """Convierte fecha ARCA (YYYYMMDD) a ISO (YYYY-MM-DD)."""
    if not fecha_str:
        return None
    try:
        from datetime import datetime
        dt = datetime.strptime(str(fecha_str), '%Y%m%d')
        return dt.date().isoformat()  # '2026-03-19'
    except ValueError:
        return str(fecha_str)
```

### 7.4.2 El Caso del Reproceso

Cuando ARCA recibe un request idéntico a uno ya procesado (misma combinación de tipo + PV + número), retorna el CAE original en vez de rechazarlo. Esto se indica con `Reproceso = 'S'`:

```python
# Respuesta de reproceso:
# FeCabResp.Resultado = 'A'
# FeCabResp.Reproceso = 'S'       ← indica reproceso
# det.Resultado = 'A'
# det.CAE = '74132917530459'      ← el CAE original
# det.CAEFchVto = '20260319'      ← el vencimiento original

# Observaciones típicas de reproceso:
# Obs(Code=10251, Msg='Se procesó como reproceso...')
```

**Implicancia práctica**: Si envías la misma factura dos veces (por timeout, retry, etc.), no se duplica — ARCA retorna el mismo CAE. Esto es seguro y por diseño.

```python
def es_reproceso(parsed_response: dict) -> bool:
    """Determina si la respuesta es un reproceso."""
    return parsed_response.get('reproceso') == 'S'
```

---

## 7.5 Respuesta de FECompUltimoAutorizado

Esta operación es mucho más simple:

```python
# Request
data = {
    'Auth': auth,
    'PtoVta': 1,
    'CbteTipo': 6,
}
result = ws.send_request('FECompUltimoAutorizado', data)

# Response (objeto Zeep)
result.PtoVta      # int — Punto de venta consultado
result.CbteTipo    # int — Tipo de comprobante consultado
result.CbteNro     # int — Último número autorizado (0 si nunca se emitió)

# Errores globales (misma estructura que FECAESolicitar)
result.Errors      # Errors.Err[].Code + Msg

# Parseo directo:
ultimo = result.CbteNro  # int, listo para usar
proximo = ultimo + 1
```

**Edge case**: Si nunca se emitió un comprobante de ese tipo en ese PV, retorna `CbteNro = 0`. El próximo a emitir sería el `1`.

```python
def parsear_ultimo_autorizado(result) -> int:
    """Extrae el último número de comprobante autorizado."""
    return result.CbteNro  # int, puede ser 0
```

---

## 7.6 Respuesta de FECompConsultar

Consulta un comprobante ya emitido. La respuesta viene en `ResultGet`:

```python
# Request
data = {
    'Auth': auth,
    'FeCompConsReq': {
        'CbteTipo': 6,
        'CbteNro': 15,
        'PtoVta': 1,
    }
}
result = ws.send_request('FECompConsultar', data)
```

### Parseo del response:

```python
def parsear_comprobante_consultado(result) -> dict:
    """
    Parsea la respuesta de FECompConsultar.

    Returns:
        dict con datos del comprobante, o {'encontrado': False}
    """
    if not hasattr(result, 'ResultGet') or not result.ResultGet:
        return {'encontrado': False}

    cbte = result.ResultGet

    return {
        'encontrado': True,
        'tipo_cbte': cbte.CbteTipo,
        'punto_venta': cbte.PtoVta,
        'cbte_desde': cbte.CbteDesde,
        'cbte_hasta': cbte.CbteHasta,
        'concepto': cbte.Concepto,
        'doc_tipo': cbte.DocTipo,
        'doc_nro': cbte.DocNro,
        'fecha_cbte': str(cbte.CbteFch) if cbte.CbteFch else None,
        'imp_total': cbte.ImpTotal,      # float
        'imp_neto': cbte.ImpNeto,        # float
        'imp_iva': cbte.ImpIVA,          # float
        'imp_trib': cbte.ImpTrib,        # float
        'imp_op_ex': cbte.ImpOpEx,       # float
        'imp_tot_conc': getattr(cbte, 'ImpTotConc', 0),
        'mon_id': getattr(cbte, 'MonId', 'PES'),
        'mon_cotiz': getattr(cbte, 'MonCotiz', 1),
        'cae': str(cbte.CodAutorizacion) if cbte.CodAutorizacion else None,
        'cae_vto': str(cbte.FchVto) if getattr(cbte, 'FchVto', None) else None,
        'resultado': cbte.Resultado,  # 'A'
    }
```

**Nota sobre campos**: Algunos campos como `ImpTotConc`, `MonId`, `MonCotiz` pueden no existir en comprobantes antiguos, por eso se usa `getattr()` con defaults.

**Nota sobre fechas**: `CbteFch`, `FchVto` vienen como strings `YYYYMMDD`. Usar `parse_fecha_arca()` para convertir a ISO antes de almacenar.

---

## 7.7 Respuesta de Consulta de Padrón

La consulta de padrón usa un servicio distinto (`ws_sr_constancia_inscripcion`) con una estructura de response completamente diferente:

```python
def parsear_respuesta_padron(result) -> dict:
    """
    Parsea la respuesta de getPersona_v2 (padrón ARCA).

    La estructura es muy distinta a WSFE — no tiene FeCabResp/FeDetResp
    sino personaReturn con datos del contribuyente.
    """
    if not hasattr(result, 'personaReturn') or not result.personaReturn:
        return {'success': False, 'error': 'Persona no encontrada'}

    persona = result.personaReturn

    # Razón social: personas físicas vs jurídicas
    nombre = getattr(persona, 'nombre', '') or ''
    apellido = getattr(persona, 'apellido', '') or ''

    if apellido and nombre:
        razon_social = f'{apellido}, {nombre}'
    elif nombre:
        razon_social = nombre
    else:
        razon_social = getattr(persona, 'razonSocial', '') or ''

    # Domicilio (puede ser lista o objeto único)
    direccion = None
    if hasattr(persona, 'domicilio') and persona.domicilio:
        dom = (
            persona.domicilio[0]
            if isinstance(persona.domicilio, list)
            else persona.domicilio
        )
        parts = []
        for attr in ['direccion', 'localidad', 'descripcionProvincia']:
            val = getattr(dom, attr, None)
            if val:
                parts.append(str(val))
        direccion = ', '.join(parts) if parts else None

    # Condición IVA: inferir desde datos impositivos
    condicion_iva = None
    if hasattr(persona, 'datosRegimenGeneral') and persona.datosRegimenGeneral:
        condicion_iva = 'IVA Responsable Inscripto'
    elif hasattr(persona, 'datosMonotributo') and persona.datosMonotributo:
        condicion_iva = 'Responsable Monotributo'

    return {
        'success': True,
        'data': {
            'cuit': str(getattr(persona, 'idPersona', '')),
            'razon_social': razon_social,
            'direccion': direccion,
            'condicion_iva': condicion_iva,  # Nombre, no ID
        }
    }
```

**Diferencias clave con WSFE**:
- El padrón retorna `condicion_iva` como **nombre** (string), no como ID numérico
- Hay que convertirlo a ID usando el catálogo `CONDICIONES_IVA` (ver sección 6.1.5)
- El servicio de padrón no siempre puede determinar la condición (retorna `None` si no tiene `datosRegimenGeneral` ni `datosMonotributo`)

---

## 7.8 Catálogo Completo de Errores y Observaciones

### 7.8.1 Errores Globales (Errors.Err)

Estos errores indican que el request no pudo procesarse:

| Code | Mensaje | Causa | Acción |
|------|---------|-------|--------|
| `600` | "ValidacionDeToken: No Autorizado" | Token expirado o inválido | Renovar TA y reintentar |
| `601` | "CUIT representada no válida" | El CUIT no coincide con el cert | Verificar CUIT y certificado |
| `602` | "Sin permiso para acceder al servicio" | Servicio no habilitado en ARCA | Habilitar WSFE en el portal ARCA |
| `1000` | "Error interno del servidor" | Error de ARCA (no de tu código) | Reintentar después de unos segundos |
| `1001` | "El servicio está temporalmente no disponible" | Mantenimiento o sobrecarga | Reintentar con backoff |

### 7.8.2 Observaciones del Comprobante (det.Observaciones.Obs)

Estas son las observaciones que causan rechazo (`Resultado = 'R'`) o warnings (`Resultado = 'A'`):

| Code | Mensaje resumido | Causa | Solución |
|------|------------------|-------|----------|
| `10013` | "La fecha del comprobante no puede ser anterior/posterior..." | Fecha de emisión fuera del rango permitido (±10 días de hoy para productos, ±30 para servicios) | Usar fecha dentro del rango |
| `10015` | "El campo DocNro es inválido" | CUIT/DNI no válido o no existe | Verificar documento del receptor |
| `10016` | "El campo CbteHasta es menor o igual al último autorizado" | Número de comprobante no secuencial | Re-consultar `FECompUltimoAutorizado` y usar `ultimo + 1` |
| `10017` | "El importe total de las alícuotas de IVA no coincide..." | `sum(AlicIva.Importe) ≠ ImpIVA` | Verificar cálculo IVA y ajuste de redondeo |
| `10018` | "La base imponible total de las alícuotas de IVA no coincide..." | `sum(AlicIva.BaseImp) ≠ ImpNeto` | Verificar bases imponibles |
| `10025` | "Para NC/ND se requiere informar comprobantes asociados" | Falta `CbtesAsoc` | Agregar comprobante original |
| `10026` | "El comprobante asociado no existe" | FC original no encontrada en ARCA | Verificar tipo/PV/número del original |
| `10032` | "La fecha desde del servicio debe ser informada" | Falta `FchServDesde` (concepto 2/3) | Agregar fechas de servicio |
| `10048` | "El campo ImpTotal no coincide con la suma..." | Ecuación de importes no cuadra | `Total = Neto + IVA + Conc + OpEx + Trib` |
| `10242` | "El campo CondicionIVAReceptorId es obligatorio..." | Falta o valor inválido | RG 5616: incluir condición IVA |
| `10251` | "Se procesó como reproceso" | Request idéntico a uno ya procesado | No es error — CAE original retornado. OK |

### 7.8.3 Categorización de Observaciones

```python
def categorizar_observacion(code: int | str) -> str:
    """
    Clasifica una observación de ARCA por tipo.

    Returns:
        'warning': informativa (comprobante aprobado)
        'validation': error de validación de datos
        'sequence': error de secuencia/numeración
        'auth': error de autenticación/permisos
        'unknown': no clasificado
    """
    code = int(code) if code else 0

    WARNINGS = {10251}  # Reproceso
    VALIDATION = {10013, 10015, 10017, 10018, 10025, 10026, 10032, 10048, 10242}
    SEQUENCE = {10016}
    AUTH = {600, 601, 602}

    if code in WARNINGS:
        return 'warning'
    if code in VALIDATION:
        return 'validation'
    if code in SEQUENCE:
        return 'sequence'
    if code in AUTH:
        return 'auth'
    return 'unknown'
```

---

## 7.9 Errores Retryables — Detección y Estrategia

### 7.9.1 Error WSAA "Ya posee un TA válido"

Este error ocurre cuando se intenta obtener un nuevo Ticket de Acceso mientras ya existe uno válido:

```python
def es_error_wsaa_retryable(result: dict) -> bool:
    """
    Detecta error de TA duplicado.
    Ocurre cuando dos procesos piden TA al mismo tiempo.
    """
    if not isinstance(result, dict) or result.get('success'):
        return False

    message = (result.get('error_message') or '').lower()
    retryable_fragments = [
        'ya posee un ta valido para el acceso al wsn solicitado',
        'ya posee un ta valido',
    ]
    return any(fragment in message for fragment in retryable_fragments)

# Estrategia: esperar y reintentar (el TA existente puede usarse)
if es_error_wsaa_retryable(result):
    time.sleep(5)  # Esperar que el TA se estabilice
    result = procesar_factura(client, factura)
```

### 7.9.2 Error 10016 "Próximo a Autorizar"

Error de secuencia: el número de comprobante ya fue usado por otro proceso concurrente:

```python
def es_error_secuencia_retryable(result: dict) -> bool:
    """
    Detecta error de secuencia (10016).
    Ocurre cuando otro proceso autorizó un comprobante entre
    nuestra consulta de último y nuestro envío.
    """
    if not isinstance(result, dict) or result.get('success'):
        return False

    code = str(result.get('error_code') or '')
    message = (result.get('error_message') or '').lower()

    return (
        code == '10016'
        or 'proximo a autorizar' in message
        or 'fecompultimoautorizado' in message
    )

# Estrategia: re-consultar último, sincronizar fecha si es necesario, reintentar
if es_error_secuencia_retryable(result):
    sincronizar_fecha_con_ultimo_autorizado(client, factura)
    time.sleep(1)
    result = procesar_factura(client, factura)
```

### 7.9.3 Sincronización de Fecha por Error de Secuencia

Cuando ocurre error 10016, a veces la fecha de emisión es anterior a la del último comprobante autorizado. ARCA exige que las fechas sean cronológicas:

```python
def sincronizar_fecha_con_ultimo_autorizado(client, factura) -> bool:
    """
    Ajusta fecha de emisión si es anterior al último comprobante autorizado.
    ARCA exige que los comprobantes sean cronológicos.

    Returns:
        True si se ajustó la fecha, False si no fue necesario.
    """
    try:
        # Consultar último autorizado
        ultimo_nro = client.fe_comp_ultimo_autorizado(
            punto_venta=factura.punto_venta,
            tipo_cbte=factura.tipo_comprobante,
        )

        if not ultimo_nro or int(ultimo_nro) <= 0:
            return False

        # Obtener datos del último comprobante
        ultimo_data = client.fe_comp_consultar(
            tipo_cbte=factura.tipo_comprobante,
            punto_venta=factura.punto_venta,
            numero=int(ultimo_nro),
        )

        if not isinstance(ultimo_data, dict) or not ultimo_data.get('encontrado'):
            return False

        # Parsear fecha del último comprobante
        ultima_fecha = parse_fecha_flexible(ultimo_data.get('fecha_cbte'))
        if not ultima_fecha:
            return False

        # ¿Nuestra fecha es anterior?
        if factura.fecha_emision and factura.fecha_emision >= ultima_fecha:
            return False  # No necesita ajuste

        # Ajustar fecha de emisión
        factura.fecha_emision = ultima_fecha

        # Si es servicio, ajustar también fechas de período
        if factura.concepto in (2, 3):
            if factura.fecha_desde and factura.fecha_desde < ultima_fecha:
                factura.fecha_desde = ultima_fecha
            if factura.fecha_hasta and factura.fecha_hasta < ultima_fecha:
                factura.fecha_hasta = ultima_fecha
            if factura.fecha_vto_pago and factura.fecha_vto_pago < ultima_fecha:
                factura.fecha_vto_pago = ultima_fecha

        return True

    except Exception:
        return False


def parse_fecha_flexible(value) -> 'date | None':
    """Parsea fecha que puede venir como YYYYMMDD, YYYY-MM-DD, o date."""
    from datetime import date, datetime

    if isinstance(value, date):
        return value
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    for fmt in ('%Y%m%d', '%Y-%m-%d'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue

    return None
```

---

## 7.10 Capa de Servicio — WSFEService

La capa de servicio encapsula el parseo y la interpretación:

```python
from datetime import datetime


class WSFEService:
    """
    Servicio de alto nivel para WSFE.
    Encapsula parseo de respuestas y simplifica la interfaz.
    """

    def __init__(self, client):
        self.client = client

    def autorizar(self, request_data: dict) -> dict:
        """
        Autoriza comprobante y retorna resultado interpretado.

        Returns:
            Si éxito: {'success': True, 'cae': str, 'cae_vencimiento': str,
                       'numero_comprobante': int, 'observaciones': list}
            Si fallo: {'success': False, 'error_code': str, 'error_message': str,
                       'errores': list, 'observaciones': list}
        """
        # client.fe_cae_solicitar ya llama a _parse_cae_response internamente
        result = self.client.fe_cae_solicitar(request_data)

        if result.get('resultado') == 'A':
            return {
                'success': True,
                'cae': result.get('cae'),
                'cae_vencimiento': self._parse_fecha(result.get('cae_vencimiento')),
                'numero_comprobante': result.get('numero_comprobante'),
                'observaciones': result.get('observaciones', []),
            }
        else:
            errores = result.get('errores', [])
            observaciones = result.get('observaciones', [])
            all_messages = errores + observaciones
            error_msg = '; '.join(
                [e.get('msg', '') for e in all_messages if e.get('msg')]
            )
            return {
                'success': False,
                'error_code': errores[0].get('code') if errores else None,
                'error_message': error_msg or 'Error desconocido al autorizar comprobante',
                'errores': errores,
                'observaciones': observaciones,
            }

    def consultar_comprobante(self, tipo_cbte: int, punto_venta: int,
                               numero: int) -> dict:
        """Consulta comprobante y parsea fechas a ISO."""
        result = self.client.fe_comp_consultar(
            tipo_cbte=tipo_cbte,
            punto_venta=punto_venta,
            numero=numero,
        )
        if isinstance(result, dict) and result.get('encontrado'):
            result['fecha_cbte'] = self._parse_fecha(result.get('fecha_cbte'))
            result['cae_vto'] = self._parse_fecha(result.get('cae_vto'))
        return result

    def ultimo_autorizado(self, punto_venta: int, tipo_cbte: int) -> int:
        """Retorna último número de comprobante autorizado."""
        return self.client.fe_comp_ultimo_autorizado(
            punto_venta=punto_venta,
            tipo_cbte=tipo_cbte,
        )

    def _parse_fecha(self, fecha_str: str | None) -> str | None:
        """YYYYMMDD → YYYY-MM-DD"""
        if not fecha_str:
            return None
        try:
            dt = datetime.strptime(str(fecha_str), '%Y%m%d')
            return dt.date().isoformat()
        except ValueError:
            return str(fecha_str)
```

---

## 7.11 Almacenamiento de Request y Response

Es recomendable guardar tanto el request enviado como el response recibido para auditoría y debugging:

```python
# Antes de enviar: guardar request
factura.arca_request = to_json_safe(request_data)

# Después de recibir: guardar response
factura.arca_response = to_json_safe(response)

# to_json_safe maneja Decimal, date, UUID, objetos Zeep
def to_json_safe(value):
    """Convierte a tipos JSON-serializables."""
    from decimal import Decimal
    from datetime import date, datetime
    from uuid import UUID

    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if hasattr(value, 'isoformat') and callable(value.isoformat):
        try:
            return value.isoformat()
        except TypeError:
            pass
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_json_safe(v) for v in value]
    return value
```

**Campos sugeridos en el modelo de factura**:

```python
# Modelo Factura (SQLAlchemy)
arca_request = db.Column(db.JSON, nullable=True)     # Request enviado
arca_response = db.Column(db.JSON, nullable=True)    # Response completo

# Campos extraídos del response (para queries rápidas)
cae = db.Column(db.String(20), nullable=True)         # '74132917530459'
cae_vencimiento = db.Column(db.Date, nullable=True)   # 2026-03-19
numero_comprobante = db.Column(db.Integer, nullable=True)
error_codigo = db.Column(db.String(20), nullable=True) # '10048'
error_mensaje = db.Column(db.Text, nullable=True)
estado = db.Column(db.String(20), default='pendiente')
# estados: 'pendiente' → 'autorizado' | 'error'
```

---

## 7.12 Flujo Completo de Parseo

```
                        FECAESolicitar
                              │
                    ┌─────────┴─────────┐
                    │ Objeto Zeep raw    │
                    │ (result)           │
                    └─────────┬─────────┘
                              │
                    ┌─────────┴─────────┐
                    │ _parse_cae_response│
                    │                   │
                    │ Extrae:           │
                    │ - resultado (A/R) │
                    │ - reproceso (S/N) │
                    │ - cae             │
                    │ - cae_vencimiento │
                    │ - numero_cbte     │
                    │ - observaciones[] │
                    │ - errores[]       │
                    └─────────┬─────────┘
                              │
                    ┌─────────┴─────────┐
                    │ WSFEService       │
                    │ .autorizar()      │
                    │                   │
                    │ Interpreta:       │
                    │ - success: bool   │
                    │ - Parsea fechas   │
                    │   YYYYMMDD → ISO  │
                    │ - Combina errores │
                    │   + observaciones │
                    └─────────┬─────────┘
                              │
                    ┌─────────┴─────────┐
                    │ Código llamador    │
                    │                   │
                    │ Decide:           │
                    │ - Guardar CAE     │
                    │ - Marcar error    │
                    │ - Reintentar      │
                    │ - Guardar request │
                    │   y response      │
                    └───────────────────┘
```
