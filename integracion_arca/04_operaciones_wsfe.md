# 04 — Operaciones del WSFE

> **Audiencia:** Referencia técnica completa de las tres operaciones principales del Web Service de Factura Electrónica (WSFE) de ARCA: consultar último comprobante, solicitar CAE y consultar comprobante emitido. Incluye estructura exacta de request y response con todos los campos.

---

## Índice

1. [Resumen de operaciones](#1-resumen-de-operaciones)
2. [FECompUltimoAutorizado](#2-fecompultimoautorizado)
3. [FECAESolicitar](#3-fecaesolicitar)
4. [FECompConsultar](#4-fecompconsultar)
5. [Consulta de padrón (ws_sr_constancia_inscripcion)](#5-consulta-de-padrón-ws_sr_constancia_inscripcion)
6. [FEDummy (health check)](#6-fedummy-health-check)
7. [Parseo de respuestas Zeep](#7-parseo-de-respuestas-zeep)
8. [Flujo completo de emisión](#8-flujo-completo-de-emisión)

---

## 1. Resumen de operaciones

| Operación | Función | Cuándo usarla |
|-----------|---------|---------------|
| `FECompUltimoAutorizado` | Obtiene el último número de comprobante autorizado para un punto de venta y tipo | **Antes** de emitir, para calcular el próximo número |
| `FECAESolicitar` | Emite un comprobante y obtiene el CAE (Código de Autorización Electrónica) | Para **emitir** una factura/NC/ND |
| `FECompConsultar` | Consulta los datos de un comprobante ya emitido | Para **verificar** o **recuperar** datos de un comprobante |
| `FEDummy` | Verifica el estado de los servidores de ARCA | Health check, no requiere autenticación |

### Objeto Auth (común a todas las operaciones excepto FEDummy)

Todas las operaciones requieren un objeto `Auth` con las credenciales del Ticket de Acceso vigente:

```python
auth = ws.get_type('FEAuthRequest')
auth['Token'] = ws.token
auth['Sign'] = ws.sign
auth['Cuit'] = ws.cuit
```

Estructura:

```python
{
    'Token': str,   # Token del TA (~1500 chars)
    'Sign': str,    # Firma del TA (~350 chars)
    'Cuit': str,    # CUIT del emisor sin guiones ('20123456789')
}
```

---

## 2. FECompUltimoAutorizado

### Propósito

Obtiene el **último número de comprobante autorizado** para una combinación de punto de venta + tipo de comprobante. Se usa para calcular el próximo número a emitir (`último + 1`).

### Request

```python
data = {
    'Auth': auth,        # FEAuthRequest (ver sección 1)
    'PtoVta': int,       # Punto de venta (ej: 1, 2, 5)
    'CbteTipo': int,     # Tipo de comprobante (ej: 1=FC A, 6=FC B, 11=FC C)
}
```

#### Campos del request

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `Auth` | `FEAuthRequest` | Sí | Credenciales de autenticación |
| `PtoVta` | `int` | Sí | Número de punto de venta |
| `CbteTipo` | `int` | Sí | Código de tipo de comprobante (ver catálogo doc 03) |

### Response

```python
result = ws.send_request('FECompUltimoAutorizado', data)
```

El objeto `result` tiene la siguiente estructura:

```python
result.PtoVta       # int — Punto de venta consultado
result.CbteTipo     # int — Tipo de comprobante consultado
result.CbteNro      # int — Último número de comprobante autorizado

# Errores (opcional, puede ser None)
result.Errors       # objeto con .Err (lista de errores)
result.Events       # objeto con .Evt (lista de eventos)
```

#### Campos del response

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `result.PtoVta` | `int` | Punto de venta consultado (eco del request) |
| `result.CbteTipo` | `int` | Tipo de comprobante consultado (eco del request) |
| `result.CbteNro` | `int` | Último número autorizado. `0` si nunca se emitió un comprobante de ese tipo en ese PV |
| `result.Errors` | objeto / `None` | Errores globales |
| `result.Events` | objeto / `None` | Eventos informativos |

### Ejemplo completo

```python
# Construir Auth
auth = ws.get_type('FEAuthRequest')
auth['Token'] = ws.token
auth['Sign'] = ws.sign
auth['Cuit'] = ws.cuit

# Consultar
data = {
    'Auth': auth,
    'PtoVta': 1,
    'CbteTipo': 1,   # Factura A
}

result = ws.send_request('FECompUltimoAutorizado', data)

ultimo = result.CbteNro           # Ej: 5
proximo = result.CbteNro + 1      # Ej: 6

print(f'Último autorizado: {ultimo}')
print(f'Próximo a emitir: {proximo}')
```

### Casos especiales

| Caso | `CbteNro` retornado | Significado |
|------|---------------------|-------------|
| Nunca se emitió comprobante de ese tipo/PV | `0` | El primer comprobante será número `1` |
| Punto de venta no existe | Error | ARCA retorna error |
| Tipo de comprobante inválido | Error | ARCA retorna error |

### Uso en el flujo de emisión

```python
# Paso 1: Obtener último número
ultimo = client.fe_comp_ultimo_autorizado(punto_venta=1, tipo_cbte=1)

# Paso 2: Calcular próximo
numero_comprobante = ultimo + 1

# Paso 3: Usar ese número en FECAESolicitar
# det_request['CbteDesde'] = numero_comprobante
# det_request['CbteHasta'] = numero_comprobante
```

> **Importante:** Entre `FECompUltimoAutorizado` y `FECAESolicitar` puede ocurrir que otro proceso emita un comprobante, haciendo que el número ya no sea válido. Si ARCA rechaza con error `10016` ("El campo CbteDesde no es el próximo a autorizar"), se debe re-consultar el último autorizado y reintentar.

---

## 3. FECAESolicitar

### Propósito

**Emite un comprobante electrónico** y obtiene el CAE (Código de Autorización Electrónica). Es la operación principal del WSFE.

### Request — Estructura completa

```python
data = {
    'Auth': auth,                          # FEAuthRequest
    'FeCAEReq': {                          # Request de CAE
        'FeCabReq': {                      # Cabecera
            'CantReg': int,                # Cantidad de comprobantes en el lote
            'PtoVta': int,                 # Punto de venta
            'CbteTipo': int,               # Tipo de comprobante
        },
        'FeDetReq': {                      # Detalle
            'FECAEDetRequest': dict | list # Detalle del/los comprobante(s)
        }
    }
}
```

### Cabecera — FeCabReq

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `CantReg` | `int` | Sí | Cantidad de comprobantes en el request. Para emisión individual, siempre `1` |
| `PtoVta` | `int` | Sí | Punto de venta. Debe coincidir con el del detalle |
| `CbteTipo` | `int` | Sí | Tipo de comprobante. Debe coincidir con el del detalle |

### Detalle — FECAEDetRequest

El detalle contiene toda la información del comprobante. Puede ser un dict (un comprobante) o una lista de dicts (lote).

#### Campos del detalle

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `Concepto` | `int` | Sí | 1=Productos, 2=Servicios, 3=Ambos |
| `DocTipo` | `int` | Sí | Tipo de documento del receptor (80=CUIT, 96=DNI, 99=Otro) |
| `DocNro` | `int` | Sí | Número de documento del receptor (sin guiones, como entero) |
| `CbteDesde` | `int` | Sí | Número de comprobante desde (= último autorizado + 1) |
| `CbteHasta` | `int` | Sí | Número de comprobante hasta (= CbteDesde para 1 factura) |
| `CbteFch` | `str` | Sí | Fecha de emisión en formato `YYYYMMDD` |
| `ImpTotal` | `float` | Sí | Importe total del comprobante |
| `ImpTotConc` | `float` | Sí | Importe neto no gravado. `0` si no aplica |
| `ImpNeto` | `float` | Sí | Importe neto gravado (base imponible) |
| `ImpOpEx` | `float` | Sí | Importe de operaciones exentas. `0` si no aplica |
| `ImpIVA` | `float` | Sí | Importe total de IVA. `0` para clase C |
| `ImpTrib` | `float` | Sí | Importe total de tributos. `0` si no aplica |
| `MonId` | `str` | Sí | Código de moneda (`'PES'`, `'DOL'`, `'060'`, etc.) |
| `MonCotiz` | `float` | Sí | Cotización de la moneda. `1` para pesos |
| `FchServDesde` | `str` | Condicional | Fecha inicio servicio `YYYYMMDD`. Obligatorio si Concepto=2 o 3 |
| `FchServHasta` | `str` | Condicional | Fecha fin servicio `YYYYMMDD`. Obligatorio si Concepto=2 o 3 |
| `FchVtoPago` | `str` | Condicional | Fecha vencimiento pago `YYYYMMDD`. Obligatorio si Concepto=2 o 3 |
| `Iva` | `dict` | Condicional | Array de alícuotas IVA. Obligatorio si ImpIVA > 0 y clase != C |
| `CbtesAsoc` | `dict` | Condicional | Comprobante asociado. Obligatorio para NC/ND |
| `Tributos` | `dict` | Opcional | Array de tributos adicionales |
| `Opcionales` | `dict` | Opcional | Datos opcionales |
| `CondicionIVAReceptorId` | `int` | Sí (RG 5616) | Condición IVA del receptor (ver catálogo doc 03) |

### Relación de importes (regla de validación de ARCA)

```
ImpTotal = ImpNeto + ImpIVA + ImpTrib + ImpOpEx + ImpTotConc
```

Si esta ecuación no se cumple, ARCA rechaza el comprobante.

### Estructura del campo Iva

```python
'Iva': {
    'AlicIva': [                # Lista de alícuotas (o un solo dict)
        {
            'Id': 5,            # Código de alícuota (5=21%, 4=10.5%, etc.)
            'BaseImp': 10000.0, # Base imponible
            'Importe': 2100.0,  # Importe de IVA (BaseImp * porcentaje / 100)
        },
    ]
}
```

**Reglas:**
- Si hay una sola alícuota, puede ser un dict o una lista con un elemento
- La suma de todos los `Importe` debe coincidir con `ImpIVA`
- La suma de todos los `BaseImp` debe coincidir con `ImpNeto`
- **NO enviar** para comprobantes clase C (tipo 11, 12, 13)

### Estructura del campo CbtesAsoc

```python
'CbtesAsoc': {
    'CbteAsoc': [               # Lista de comprobantes asociados
        {
            'Tipo': 1,          # Tipo del comprobante original (1=FC A)
            'PtoVta': 1,        # Punto de venta del original
            'Nro': 6,           # Número del comprobante original
        },
    ]
}
```

**Reglas:**
- Obligatorio para NC (tipos 3, 8, 13, 53) y ND (tipos 2, 7, 12, 52)
- El comprobante asociado debe existir en ARCA
- Puede ser una lista (múltiples asociados) o un solo dict

### Response — Estructura completa

```python
result = ws.send_request('FECAESolicitar', data)
```

El objeto `result` tiene la siguiente estructura:

```python
# === Cabecera de respuesta ===
result.FeCabResp.Cuit           # str — CUIT del emisor
result.FeCabResp.PtoVta         # int — Punto de venta
result.FeCabResp.CbteTipo       # int — Tipo de comprobante
result.FeCabResp.Resultado      # str — 'A' (aprobado), 'R' (rechazado), 'P' (parcial)
result.FeCabResp.Reproceso      # str — 'S' (reproceso) o 'N' (nuevo)
result.FeCabResp.FchProceso     # str — Fecha/hora de procesamiento

# === Detalle de respuesta (por cada comprobante) ===
result.FeDetResp.FECAEDetResponse    # lista de objetos detalle

det = result.FeDetResp.FECAEDetResponse[0]   # Primer (o único) comprobante

det.Concepto        # int — Concepto (eco)
det.DocTipo         # int — Tipo documento (eco)
det.DocNro          # int — Número documento (eco)
det.CbteDesde       # int — Número comprobante desde
det.CbteHasta       # int — Número comprobante hasta
det.CbteFch         # str — Fecha comprobante YYYYMMDD
det.Resultado       # str — 'A' o 'R' (resultado individual)
det.CAE             # str — Código de Autorización Electrónica (14 dígitos)
det.CAEFchVto       # str — Fecha vencimiento del CAE YYYYMMDD

# Observaciones (pueden existir incluso si fue aprobado)
det.Observaciones             # objeto o None
det.Observaciones.Obs         # lista de observaciones
det.Observaciones.Obs[0].Code # int — Código de observación
det.Observaciones.Obs[0].Msg  # str — Mensaje de observación

# === Errores globales ===
result.Errors                 # objeto o None
result.Errors.Err             # lista de errores
result.Errors.Err[0].Code     # int — Código de error
result.Errors.Err[0].Msg      # str — Mensaje de error

# === Eventos ===
result.Events                 # objeto o None
```

#### Campos del detalle de respuesta

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `det.Concepto` | `int` | Eco del concepto enviado |
| `det.DocTipo` | `int` | Eco del tipo de documento |
| `det.DocNro` | `int` | Eco del número de documento |
| `det.CbteDesde` | `int` | Número de comprobante asignado (desde) |
| `det.CbteHasta` | `int` | Número de comprobante asignado (hasta) |
| `det.CbteFch` | `str` | Fecha del comprobante (`YYYYMMDD`) |
| `det.Resultado` | `str` | `'A'` = aprobado, `'R'` = rechazado |
| `det.CAE` | `str` / `None` | CAE de 14 dígitos si aprobado, `None` si rechazado |
| `det.CAEFchVto` | `str` / `None` | Vencimiento del CAE (`YYYYMMDD`) si aprobado |
| `det.Observaciones` | objeto / `None` | Observaciones de ARCA (pueden existir en aprobados) |

### Parseo de la respuesta (función recomendada)

```python
def parsear_respuesta_cae(result) -> dict:
    """
    Parsea la respuesta de FECAESolicitar a un diccionario plano.

    Args:
        result: Objeto Zeep retornado por ws.send_request('FECAESolicitar', data)

    Returns:
        Dict con campos normalizados:
        - resultado: 'A' o 'R'
        - reproceso: 'S' o 'N'
        - cae: str de 14 dígitos o None
        - cae_vencimiento: str YYYYMMDD o None
        - numero_comprobante: int o None
        - observaciones: lista de {'code': int, 'msg': str}
        - errores: lista de {'code': int, 'msg': str}
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

    # Cabecera
    if hasattr(result, 'FeCabResp') and result.FeCabResp:
        response['resultado'] = result.FeCabResp.Resultado
        response['reproceso'] = getattr(result.FeCabResp, 'Reproceso', None)

    # Detalle (primer comprobante)
    if hasattr(result, 'FeDetResp') and result.FeDetResp:
        det_list = result.FeDetResp.FECAEDetResponse
        if det_list:
            det = det_list[0] if isinstance(det_list, list) else det_list

            response['cae'] = str(det.CAE) if det.CAE else None
            response['cae_vencimiento'] = str(det.CAEFchVto) if det.CAEFchVto else None
            response['numero_comprobante'] = det.CbteDesde
            response['resultado'] = det.Resultado

            # Observaciones
            if hasattr(det, 'Observaciones') and det.Observaciones:
                obs_list = (
                    det.Observaciones.Obs
                    if hasattr(det.Observaciones, 'Obs')
                    else det.Observaciones
                )
                if obs_list:
                    if not isinstance(obs_list, list):
                        obs_list = [obs_list]
                    response['observaciones'] = [
                        {
                            'code': getattr(obs, 'Code', None),
                            'msg': getattr(obs, 'Msg', ''),
                        }
                        for obs in obs_list
                    ]

    # Errores globales
    if hasattr(result, 'Errors') and result.Errors:
        err_list = (
            result.Errors.Err
            if hasattr(result.Errors, 'Err')
            else result.Errors
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

### Ejemplo — Factura A con IVA 21%

```python
# 1. Obtener próximo número
ultimo = ws.send_request('FECompUltimoAutorizado', {
    'Auth': auth, 'PtoVta': 1, 'CbteTipo': 1,
}).CbteNro
numero = ultimo + 1

# 2. Construir request
data = {
    'Auth': auth,
    'FeCAEReq': {
        'FeCabReq': {
            'CantReg': 1,
            'PtoVta': 1,
            'CbteTipo': 1,           # Factura A
        },
        'FeDetReq': {
            'FECAEDetRequest': {
                'Concepto': 1,       # Productos
                'DocTipo': 80,       # CUIT
                'DocNro': 27293188217,
                'CbteDesde': numero,
                'CbteHasta': numero,
                'CbteFch': '20260309',
                'ImpTotal': 12100.00,
                'ImpTotConc': 0,
                'ImpNeto': 10000.00,
                'ImpOpEx': 0,
                'ImpIVA': 2100.00,
                'ImpTrib': 0,
                'MonId': 'PES',
                'MonCotiz': 1,
                'CondicionIVAReceptorId': 1,   # RI
                'Iva': {
                    'AlicIva': [{
                        'Id': 5,               # 21%
                        'BaseImp': 10000.00,
                        'Importe': 2100.00,
                    }]
                },
            }
        }
    }
}

# 3. Enviar
result = ws.send_request('FECAESolicitar', data)

# 4. Parsear
parsed = parsear_respuesta_cae(result)

if parsed['resultado'] == 'A':
    print(f"Aprobada. CAE: {parsed['cae']}")
    print(f"Vencimiento CAE: {parsed['cae_vencimiento']}")
    print(f"Comprobante N°: {parsed['numero_comprobante']}")
else:
    print(f"Rechazada.")
    for obs in parsed['observaciones']:
        print(f"  Obs [{obs['code']}]: {obs['msg']}")
    for err in parsed['errores']:
        print(f"  Error [{err['code']}]: {err['msg']}")
```

### Ejemplo — Factura B (Consumidor Final)

```python
data = {
    'Auth': auth,
    'FeCAEReq': {
        'FeCabReq': {
            'CantReg': 1,
            'PtoVta': 1,
            'CbteTipo': 6,                 # Factura B
        },
        'FeDetReq': {
            'FECAEDetRequest': {
                'Concepto': 1,             # Productos
                'DocTipo': 99,             # Doc. Otro (Consumidor Final sin identificar)
                'DocNro': 0,               # 0 para CF genérico
                'CbteDesde': numero,
                'CbteHasta': numero,
                'CbteFch': '20260309',
                'ImpTotal': 12100.00,      # Total con IVA incluido
                'ImpTotConc': 0,
                'ImpNeto': 10000.00,       # Neto (Total - IVA)
                'ImpOpEx': 0,
                'ImpIVA': 2100.00,         # IVA discriminado (RG 5614)
                'ImpTrib': 0,
                'MonId': 'PES',
                'MonCotiz': 1,
                'CondicionIVAReceptorId': 5,   # Siempre 5 para FC B
                'Iva': {
                    'AlicIva': [{
                        'Id': 5,
                        'BaseImp': 10000.00,
                        'Importe': 2100.00,
                    }]
                },
            }
        }
    }
}
```

### Ejemplo — Factura C (Monotributista)

```python
data = {
    'Auth': auth,
    'FeCAEReq': {
        'FeCabReq': {
            'CantReg': 1,
            'PtoVta': 1,
            'CbteTipo': 11,                # Factura C
        },
        'FeDetReq': {
            'FECAEDetRequest': {
                'Concepto': 1,
                'DocTipo': 80,
                'DocNro': 27293188217,
                'CbteDesde': numero,
                'CbteHasta': numero,
                'CbteFch': '20260309',
                'ImpTotal': 10000.00,      # Total = Neto (sin discriminación)
                'ImpTotConc': 0,
                'ImpNeto': 10000.00,       # Igual al total
                'ImpOpEx': 0,
                'ImpIVA': 0,               # Siempre 0 en clase C
                'ImpTrib': 0,
                'MonId': 'PES',
                'MonCotiz': 1,
                'CondicionIVAReceptorId': 1,
                # NO incluir campo 'Iva' para clase C
            }
        }
    }
}
```

### Ejemplo — Factura de Servicios (Concepto 2)

```python
data = {
    'Auth': auth,
    'FeCAEReq': {
        'FeCabReq': {
            'CantReg': 1,
            'PtoVta': 1,
            'CbteTipo': 1,
        },
        'FeDetReq': {
            'FECAEDetRequest': {
                'Concepto': 2,             # Servicios
                'DocTipo': 80,
                'DocNro': 27293188217,
                'CbteDesde': numero,
                'CbteHasta': numero,
                'CbteFch': '20260309',
                'ImpTotal': 12100.00,
                'ImpTotConc': 0,
                'ImpNeto': 10000.00,
                'ImpOpEx': 0,
                'ImpIVA': 2100.00,
                'ImpTrib': 0,
                'MonId': 'PES',
                'MonCotiz': 1,
                'CondicionIVAReceptorId': 1,
                # --- Campos obligatorios para servicios ---
                'FchServDesde': '20260201',   # Inicio del período
                'FchServHasta': '20260228',   # Fin del período
                'FchVtoPago': '20260315',     # Vencimiento del pago
                # ---
                'Iva': {
                    'AlicIva': [{
                        'Id': 5,
                        'BaseImp': 10000.00,
                        'Importe': 2100.00,
                    }]
                },
            }
        }
    }
}
```

### Ejemplo — Nota de Crédito A con comprobante asociado

```python
data = {
    'Auth': auth,
    'FeCAEReq': {
        'FeCabReq': {
            'CantReg': 1,
            'PtoVta': 1,
            'CbteTipo': 3,                 # Nota de Crédito A
        },
        'FeDetReq': {
            'FECAEDetRequest': {
                'Concepto': 1,
                'DocTipo': 80,
                'DocNro': 27293188217,
                'CbteDesde': numero,
                'CbteHasta': numero,
                'CbteFch': '20260309',
                'ImpTotal': 12100.00,
                'ImpTotConc': 0,
                'ImpNeto': 10000.00,
                'ImpOpEx': 0,
                'ImpIVA': 2100.00,
                'ImpTrib': 0,
                'MonId': 'PES',
                'MonCotiz': 1,
                'CondicionIVAReceptorId': 1,
                'Iva': {
                    'AlicIva': [{
                        'Id': 5,
                        'BaseImp': 10000.00,
                        'Importe': 2100.00,
                    }]
                },
                # --- Comprobante asociado (la factura que se anula) ---
                'CbtesAsoc': {
                    'CbteAsoc': [{
                        'Tipo': 1,         # Tipo del original (FC A)
                        'PtoVta': 1,       # PV del original
                        'Nro': 6,          # Número del original
                    }]
                },
                # ---
            }
        }
    }
}
```

### Ejemplo — Factura con múltiples alícuotas de IVA

```python
# Items:
#   - Producto A: $5000 neto al 10.5% → IVA $525
#   - Producto B: $8000 neto al 21%   → IVA $1680
# Total: $5000 + $8000 + $525 + $1680 = $15205

data = {
    'Auth': auth,
    'FeCAEReq': {
        'FeCabReq': {
            'CantReg': 1,
            'PtoVta': 1,
            'CbteTipo': 1,
        },
        'FeDetReq': {
            'FECAEDetRequest': {
                'Concepto': 1,
                'DocTipo': 80,
                'DocNro': 27293188217,
                'CbteDesde': numero,
                'CbteHasta': numero,
                'CbteFch': '20260309',
                'ImpTotal': 15205.00,      # 13000 + 2205
                'ImpTotConc': 0,
                'ImpNeto': 13000.00,       # 5000 + 8000
                'ImpOpEx': 0,
                'ImpIVA': 2205.00,         # 525 + 1680
                'ImpTrib': 0,
                'MonId': 'PES',
                'MonCotiz': 1,
                'CondicionIVAReceptorId': 1,
                'Iva': {
                    'AlicIva': [
                        {
                            'Id': 4,               # 10.5%
                            'BaseImp': 5000.00,
                            'Importe': 525.00,
                        },
                        {
                            'Id': 5,               # 21%
                            'BaseImp': 8000.00,
                            'Importe': 1680.00,
                        },
                    ]
                },
            }
        }
    }
}
```

### Errores comunes de FECAESolicitar

| Código | Mensaje | Causa | Solución |
|--------|---------|-------|----------|
| `10016` | "El campo CbteDesde no es el próximo a autorizar" | El número de comprobante no es consecutivo | Re-consultar `FECompUltimoAutorizado` y usar `último + 1` |
| `10015` | "El campo CbteFch no puede ser anterior..." | La fecha es anterior al último comprobante emitido | Usar fecha >= fecha del último comprobante |
| `10048` | "El campo MonCotiz debe ser igual a 1..." | Se envió cotización != 1 para pesos | Usar `MonCotiz: 1` cuando `MonId: 'PES'` |
| `10013` | "El campo DocNro no es válido" | CUIT/documento inválido | Verificar el número de documento del receptor |
| `10242` | "La condición de IVA del receptor no es válida" | `CondicionIVAReceptorId` inválido para la clase | Verificar valor contra catálogo de condiciones válidas |
| `600` | "No se encontró el servicio" | CUIT sin autorización WSFE | Autorizar servicio en portal ARCA |
| `10018` | "El campo ImpTotal no es igual a..." | Los importes no cuadran | Verificar que `ImpTotal = ImpNeto + ImpIVA + ImpTrib + ImpOpEx + ImpTotConc` |

---

## 4. FECompConsultar

### Propósito

**Consulta los datos de un comprobante ya emitido** y autorizado en ARCA. Permite verificar que un comprobante existe, recuperar su CAE, o verificar sus datos.

### Request

```python
data = {
    'Auth': auth,                    # FEAuthRequest
    'FeCompConsReq': {               # Request de consulta
        'CbteTipo': int,             # Tipo de comprobante
        'CbteNro': int,              # Número de comprobante a consultar
        'PtoVta': int,               # Punto de venta
    }
}
```

#### Campos del request

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `Auth` | `FEAuthRequest` | Sí | Credenciales de autenticación |
| `FeCompConsReq.CbteTipo` | `int` | Sí | Tipo de comprobante (1=FC A, 6=FC B, etc.) |
| `FeCompConsReq.CbteNro` | `int` | Sí | Número del comprobante a consultar |
| `FeCompConsReq.PtoVta` | `int` | Sí | Punto de venta |

### Response

```python
result = ws.send_request('FECompConsultar', data)
```

El objeto `result` tiene la siguiente estructura:

```python
# Datos del comprobante (None si no existe)
result.ResultGet                    # objeto o None

cbte = result.ResultGet
cbte.CbteTipo       # int — Tipo de comprobante
cbte.PtoVta          # int — Punto de venta
cbte.CbteDesde       # int — Número desde
cbte.CbteHasta       # int — Número hasta
cbte.Concepto        # int — Concepto (1, 2, 3)
cbte.DocTipo         # int — Tipo de documento del receptor
cbte.DocNro          # int — Número de documento del receptor
cbte.CbteFch         # str — Fecha del comprobante (YYYYMMDD)
cbte.ImpTotal        # float — Importe total
cbte.ImpNeto         # float — Importe neto gravado
cbte.ImpIVA          # float — Importe de IVA
cbte.ImpTrib         # float — Importe de tributos
cbte.ImpOpEx         # float — Importe operaciones exentas
cbte.ImpTotConc      # float — Importe no gravado
cbte.MonId           # str — Código de moneda
cbte.MonCotiz        # float — Cotización
cbte.CodAutorizacion # str — CAE (14 dígitos)
cbte.FchVto          # str — Fecha vencimiento del CAE (YYYYMMDD)
cbte.Resultado       # str — 'A' (aprobado)
cbte.EmisionTipo     # str — Tipo de emisión

# Fechas de servicio (si aplica)
cbte.FchServDesde    # str — Fecha inicio servicio
cbte.FchServHasta    # str — Fecha fin servicio
cbte.FchVtoPago      # str — Fecha vencimiento pago

# IVA
cbte.Iva             # objeto con AlicIva (lista)
cbte.Tributos        # objeto con Tributo (lista)
cbte.CbtesAsoc       # objeto con CbteAsoc (lista)

# Errores
result.Errors        # objeto o None
```

#### Campos del response

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `result.ResultGet` | objeto / `None` | Datos del comprobante. `None` si no existe |
| `cbte.CbteTipo` | `int` | Tipo de comprobante |
| `cbte.PtoVta` | `int` | Punto de venta |
| `cbte.CbteDesde` | `int` | Número de comprobante (desde) |
| `cbte.CbteHasta` | `int` | Número de comprobante (hasta) |
| `cbte.Concepto` | `int` | Concepto (1=Productos, 2=Servicios, 3=Ambos) |
| `cbte.DocTipo` | `int` | Tipo de documento del receptor |
| `cbte.DocNro` | `int` | Número de documento del receptor |
| `cbte.CbteFch` | `str` | Fecha del comprobante (`YYYYMMDD`) |
| `cbte.ImpTotal` | `float` | Importe total |
| `cbte.ImpNeto` | `float` | Importe neto gravado |
| `cbte.ImpIVA` | `float` | Importe de IVA |
| `cbte.ImpTrib` | `float` | Importe de tributos |
| `cbte.ImpOpEx` | `float` | Importe operaciones exentas |
| `cbte.ImpTotConc` | `float` | Importe no gravado |
| `cbte.MonId` | `str` | Código de moneda |
| `cbte.MonCotiz` | `float` | Cotización de moneda |
| `cbte.CodAutorizacion` | `str` | CAE (14 dígitos) |
| `cbte.FchVto` | `str` | Vencimiento del CAE (`YYYYMMDD`) |
| `cbte.Resultado` | `str` | `'A'` = aprobado |

### Parseo de la respuesta (función recomendada)

```python
def parsear_comprobante_consultado(result) -> dict:
    """
    Parsea la respuesta de FECompConsultar a un diccionario plano.

    Args:
        result: Objeto Zeep retornado por ws.send_request('FECompConsultar', data)

    Returns:
        Dict con datos del comprobante, o {'encontrado': False}
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
        'imp_total': cbte.ImpTotal,
        'imp_neto': cbte.ImpNeto,
        'imp_iva': cbte.ImpIVA,
        'imp_trib': cbte.ImpTrib,
        'imp_op_ex': cbte.ImpOpEx,
        'imp_tot_conc': getattr(cbte, 'ImpTotConc', 0),
        'mon_id': getattr(cbte, 'MonId', 'PES'),
        'mon_cotiz': getattr(cbte, 'MonCotiz', 1),
        'cae': str(cbte.CodAutorizacion) if cbte.CodAutorizacion else None,
        'cae_vto': str(cbte.FchVto) if getattr(cbte, 'FchVto', None) else None,
        'resultado': cbte.Resultado,
    }
```

### Ejemplo completo

```python
# Consultar Factura A, PV 1, N° 6
auth = construir_auth(ws)

data = {
    'Auth': auth,
    'FeCompConsReq': {
        'CbteTipo': 1,       # Factura A
        'CbteNro': 6,        # Número a consultar
        'PtoVta': 1,         # Punto de venta
    }
}

result = ws.send_request('FECompConsultar', data)
parsed = parsear_comprobante_consultado(result)

if parsed['encontrado']:
    print(f"Comprobante: FC A {parsed['punto_venta']:04d}-{parsed['cbte_desde']:08d}")
    print(f"Fecha: {parsed['fecha_cbte']}")
    print(f"Total: ${parsed['imp_total']}")
    print(f"Neto: ${parsed['imp_neto']}")
    print(f"IVA: ${parsed['imp_iva']}")
    print(f"CAE: {parsed['cae']}")
    print(f"Vto CAE: {parsed['cae_vto']}")
    print(f"Receptor: {parsed['doc_tipo']}={parsed['doc_nro']}")
else:
    print('Comprobante no encontrado')
```

### Usos de FECompConsultar

1. **Verificar emisión:** Confirmar que un comprobante fue efectivamente autorizado
2. **Recuperar CAE:** Si se perdió la respuesta de `FECAESolicitar`, se puede recuperar el CAE consultando el comprobante
3. **Auditoría:** Comparar datos locales contra los registrados en ARCA
4. **Sincronización de fechas:** Consultar la fecha del último comprobante para evitar errores de secuencia temporal

---

## 5. Consulta de padrón (ws_sr_constancia_inscripcion)

Esta operación usa un **servicio web diferente** al WSFE. Se usa para consultar datos de un contribuyente por CUIT.

### Creación del servicio

```python
from arca_arg.settings import WSDL_CONSTANCIA_HOM, WSDL_CONSTANCIA_PROD

wsdl = WSDL_CONSTANCIA_PROD if produccion else WSDL_CONSTANCIA_HOM
ws_padron = ArcaWebService(wsdl, 'ws_sr_constancia_inscripcion')
```

### Request

> **Importante:** Este servicio usa una convención de autenticación diferente a WSFE. Los campos van en minúscula y como parámetros directos (no dentro de un objeto `Auth`).

```python
data = {
    'token': ws_padron.token,               # minúscula
    'sign': ws_padron.sign,                 # minúscula
    'cuitRepresentada': ws_padron.cuit,     # camelCase
    'idPersona': 20123456789,               # CUIT a consultar (como int)
}

result = ws_padron.send_request('getPersona_v2', data)
```

#### Campos del request

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `token` | `str` | Token del TA (minúscula) |
| `sign` | `str` | Firma del TA (minúscula) |
| `cuitRepresentada` | `str` | CUIT del contribuyente que consulta (camelCase) |
| `idPersona` | `int` | CUIT de la persona a consultar (como entero, sin guiones) |

### Response

```python
# Datos de la persona (None si no se encontró)
result.personaReturn                       # objeto o None

persona = result.personaReturn
persona.nombre                             # str — Nombre (persona física)
persona.apellido                           # str — Apellido (persona física)
persona.razonSocial                        # str — Razón social (persona jurídica)

# Domicilio (lista de domicilios)
persona.domicilio                          # lista de objetos
persona.domicilio[0].direccion             # str
persona.domicilio[0].localidad             # str
persona.domicilio[0].descripcionProvincia  # str

# Datos impositivos
persona.datosRegimenGeneral                # objeto o None (si es RI)
persona.datosMonotributo                   # objeto o None (si es Monotributista)
persona.datosGenerales                     # objeto — datos generales
```

### Determinación de condición IVA desde el padrón

```python
def determinar_condicion_iva(persona) -> str | None:
    """
    Determina la condición frente al IVA a partir de los datos del padrón.
    """
    if hasattr(persona, 'datosRegimenGeneral') and persona.datosRegimenGeneral:
        return 'IVA Responsable Inscripto'
    elif hasattr(persona, 'datosMonotributo') and persona.datosMonotributo:
        return 'Responsable Monotributo'
    return None
```

### Formateo del domicilio

```python
def formatear_domicilio(domicilio) -> str | None:
    """Formatea un domicilio del padrón de ARCA."""
    parts = []
    for attr in ['direccion', 'localidad', 'descripcionProvincia']:
        val = getattr(domicilio, attr, None)
        if val:
            parts.append(str(val))
    return ', '.join(parts) if parts else None
```

### Ejemplo completo

```python
cuit_a_consultar = 20224107030

data = {
    'token': ws_padron.token,
    'sign': ws_padron.sign,
    'cuitRepresentada': ws_padron.cuit,
    'idPersona': cuit_a_consultar,
}

result = ws_padron.send_request('getPersona_v2', data)

if result.personaReturn:
    persona = result.personaReturn
    nombre = getattr(persona, 'nombre', '') or ''
    apellido = getattr(persona, 'apellido', '') or ''

    if apellido and nombre:
        razon_social = f'{apellido}, {nombre}'
    elif nombre:
        razon_social = nombre
    else:
        razon_social = getattr(persona, 'razonSocial', '')

    print(f'Razón Social: {razon_social}')

    if persona.domicilio:
        dom = persona.domicilio[0]
        print(f'Dirección: {formatear_domicilio(dom)}')

    condicion = determinar_condicion_iva(persona)
    print(f'Condición IVA: {condicion}')
else:
    print('Persona no encontrada')
```

---

## 6. FEDummy (health check)

### Propósito

Verifica el estado de los servidores de ARCA. **No requiere autenticación.**

### Request

```python
result = ws.send_request('FEDummy', {})
```

### Response

```python
result.AppServer    # str — 'OK' si el servidor de aplicación está operativo
result.DbServer     # str — 'OK' si la base de datos está operativa
result.AuthServer   # str — 'OK' si el servidor de autenticación está operativo
```

### Ejemplo

```python
result = ws.send_request('FEDummy', {})

print(f'App Server:  {result.AppServer}')    # 'OK'
print(f'DB Server:   {result.DbServer}')     # 'OK'
print(f'Auth Server: {result.AuthServer}')   # 'OK'

servicios_ok = all(
    getattr(result, attr) == 'OK'
    for attr in ('AppServer', 'DbServer', 'AuthServer')
)
print(f'Servicio operativo: {servicios_ok}')
```

---

## 7. Parseo de respuestas Zeep

Todas las operaciones retornan **objetos Zeep** (no diccionarios). Es importante entender cómo trabajar con ellos.

### Acceso a campos

```python
# Notación de punto (más común)
result.CbteNro
result.FeCabResp.Resultado
result.FeDetResp.FECAEDetResponse[0].CAE

# getattr para campos opcionales (evita AttributeError)
getattr(result, 'Errors', None)
getattr(cbte, 'ImpTotConc', 0)
getattr(cbte, 'FchVto', None)
```

### Conversión a diccionario

```python
from zeep.helpers import serialize_object

# Convierte todo el resultado a un dict Python
result_dict = serialize_object(result)

# Ahora se puede acceder como diccionario
result_dict['FeCabResp']['Resultado']
```

### Manejo de listas

Las listas SOAP pueden venir como:
- Una **lista Python** con múltiples elementos
- Un **solo objeto** (no lista) si hay un solo elemento
- `None` si no hay elementos

```python
# Patrón seguro para manejar listas SOAP
def asegurar_lista(valor):
    """Normaliza un valor SOAP a lista Python."""
    if valor is None:
        return []
    if isinstance(valor, list):
        return valor
    return [valor]

# Uso
det_list = asegurar_lista(result.FeDetResp.FECAEDetResponse)
det = det_list[0]  # Primer elemento

obs_list = asegurar_lista(
    getattr(det.Observaciones, 'Obs', None) if det.Observaciones else None
)
```

### Manejo de None

Los campos opcionales de las respuestas SOAP pueden ser `None`. Siempre usar `hasattr` o `getattr` con default:

```python
# Mal — puede dar AttributeError
cae = result.FeDetResp.FECAEDetResponse[0].CAE

# Bien — manejo seguro
if hasattr(result, 'FeDetResp') and result.FeDetResp:
    det_list = result.FeDetResp.FECAEDetResponse
    if det_list:
        det = det_list[0] if isinstance(det_list, list) else det_list
        cae = str(det.CAE) if det.CAE else None
```

---

## 8. Flujo completo de emisión

Resumen del flujo típico para emitir un comprobante:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    FLUJO DE EMISIÓN DE COMPROBANTE                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. FECompUltimoAutorizado(PtoVta, CbteTipo)                       │
│     → Obtiene último número autorizado                              │
│     → Calcula próximo: último + 1                                   │
│                                                                     │
│  2. (Opcional) Consultar padrón para CondicionIVAReceptorId         │
│     → getPersona_v2(cuit_receptor)                                  │
│     → Determinar condición IVA del receptor                         │
│                                                                     │
│  3. Construir request con FacturaBuilder o manualmente              │
│     → Configurar comprobante (tipo, PV, número, concepto)           │
│     → Configurar receptor (DocTipo, DocNro)                         │
│     → Configurar importes (Total, Neto, IVA, etc.)                  │
│     → Configurar IVA (AlicIva) si clase != C                        │
│     → Configurar fechas de servicio si concepto 2 o 3               │
│     → Configurar comprobante asociado si NC/ND                      │
│     → Configurar CondicionIVAReceptorId (RG 5616)                   │
│                                                                     │
│  4. FECAESolicitar(request)                                         │
│     → Enviar comprobante a ARCA                                     │
│     → Parsear respuesta                                             │
│                                                                     │
│  5. Evaluar resultado                                               │
│     → Si resultado == 'A': guardar CAE, vencimiento, número        │
│     → Si resultado == 'R': registrar error, observaciones           │
│                                                                     │
│  6. (Ante error 10016) Reintentar                                   │
│     → Re-consultar FECompUltimoAutorizado                          │
│     → Recalcular número                                             │
│     → Volver al paso 3                                              │
│                                                                     │
│  7. (Opcional) FECompConsultar para verificar emisión               │
│     → Confirmar que el comprobante existe en ARCA                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Implementación del flujo

```python
def emitir_comprobante(client, ws, factura_data: dict) -> dict:
    """
    Flujo completo de emisión de un comprobante.

    Args:
        client: Instancia de ArcaClient
        ws: Instancia de ArcaWebService (WSFE)
        factura_data: Dict con los datos del comprobante:
            - tipo_comprobante: int (1, 6, 11, etc.)
            - punto_venta: int
            - concepto: int (1, 2, 3)
            - doc_tipo: int (80, 96, 99)
            - doc_nro: int
            - fecha_emision: str YYYYMMDD
            - imp_total: float
            - imp_neto: float
            - imp_iva: float
            - imp_trib: float (default 0)
            - imp_op_ex: float (default 0)
            - imp_tot_conc: float (default 0)
            - mon_id: str (default 'PES')
            - mon_cotiz: float (default 1)
            - condicion_iva_receptor_id: int
            - alicuotas_iva: list[dict] (opcional)
            - fecha_serv_desde: str (opcional)
            - fecha_serv_hasta: str (opcional)
            - fecha_vto_pago: str (opcional)
            - cbte_asoc_tipo: int (opcional)
            - cbte_asoc_pto_vta: int (opcional)
            - cbte_asoc_nro: int (opcional)

    Returns:
        Dict con resultado de la emisión
    """
    auth = ws.get_type('FEAuthRequest')
    auth['Token'] = ws.token
    auth['Sign'] = ws.sign
    auth['Cuit'] = ws.cuit

    tipo = factura_data['tipo_comprobante']
    pv = factura_data['punto_venta']

    # Paso 1: Obtener próximo número
    result_ultimo = ws.send_request('FECompUltimoAutorizado', {
        'Auth': auth, 'PtoVta': pv, 'CbteTipo': tipo,
    })
    numero = result_ultimo.CbteNro + 1

    # Paso 2: Construir detalle
    det = {
        'Concepto': factura_data['concepto'],
        'DocTipo': factura_data['doc_tipo'],
        'DocNro': factura_data['doc_nro'],
        'CbteDesde': numero,
        'CbteHasta': numero,
        'CbteFch': factura_data['fecha_emision'],
        'ImpTotal': factura_data['imp_total'],
        'ImpTotConc': factura_data.get('imp_tot_conc', 0),
        'ImpNeto': factura_data['imp_neto'],
        'ImpOpEx': factura_data.get('imp_op_ex', 0),
        'ImpIVA': factura_data['imp_iva'],
        'ImpTrib': factura_data.get('imp_trib', 0),
        'MonId': factura_data.get('mon_id', 'PES'),
        'MonCotiz': factura_data.get('mon_cotiz', 1),
        'CondicionIVAReceptorId': factura_data['condicion_iva_receptor_id'],
    }

    # Fechas de servicio (concepto 2 o 3)
    if factura_data.get('fecha_serv_desde'):
        det['FchServDesde'] = factura_data['fecha_serv_desde']
    if factura_data.get('fecha_serv_hasta'):
        det['FchServHasta'] = factura_data['fecha_serv_hasta']
    if factura_data.get('fecha_vto_pago'):
        det['FchVtoPago'] = factura_data['fecha_vto_pago']

    # IVA (no enviar para clase C)
    alicuotas = factura_data.get('alicuotas_iva')
    if alicuotas and tipo not in {11, 12, 13}:
        det['Iva'] = {'AlicIva': alicuotas}

    # Comprobante asociado (NC/ND)
    if factura_data.get('cbte_asoc_tipo'):
        det['CbtesAsoc'] = {
            'CbteAsoc': [{
                'Tipo': factura_data['cbte_asoc_tipo'],
                'PtoVta': factura_data['cbte_asoc_pto_vta'],
                'Nro': factura_data['cbte_asoc_nro'],
            }]
        }

    # Paso 3: Enviar
    request_data = {
        'Auth': auth,
        'FeCAEReq': {
            'FeCabReq': {'CantReg': 1, 'PtoVta': pv, 'CbteTipo': tipo},
            'FeDetReq': {'FECAEDetRequest': det},
        }
    }

    result = ws.send_request('FECAESolicitar', request_data)

    # Paso 4: Parsear
    parsed = parsear_respuesta_cae(result)

    if parsed['resultado'] == 'A':
        return {
            'success': True,
            'cae': parsed['cae'],
            'cae_vencimiento': parsed['cae_vencimiento'],
            'numero_comprobante': numero,
            'observaciones': parsed['observaciones'],
        }
    else:
        errores = parsed['errores'] + parsed['observaciones']
        error_msg = '; '.join(e['msg'] for e in errores if e.get('msg'))
        return {
            'success': False,
            'error_code': parsed['errores'][0]['code'] if parsed['errores'] else None,
            'error_message': error_msg or 'Error desconocido',
            'errores': parsed['errores'],
            'observaciones': parsed['observaciones'],
        }
```
