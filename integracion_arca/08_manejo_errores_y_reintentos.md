# 8. Manejo de Errores y Reintentos

Este documento cubre la estrategia completa de manejo de errores en la integración con ARCA: la jerarquía de excepciones, los errores de WSAA (autenticación), los errores de secuencia (10016), la sincronización de fechas, el bloqueo de secuencia para concurrencia, y los patrones de retry en procesamiento masivo.

---

## 8.1 Jerarquía de Excepciones

```python
class ArcaError(Exception):
    """Error base de ARCA. Captura cualquier error de integración."""
    pass

class ArcaAuthError(ArcaError):
    """Error de autenticación con ARCA (WSAA, certificados, TA)."""
    pass

class ArcaValidationError(ArcaError):
    """Error de validación de datos antes de enviar a ARCA."""
    pass

class ArcaNetworkError(ArcaError):
    """Error de red al comunicarse con ARCA (timeout, conexión)."""
    pass
```

### Cuándo se lanza cada una

| Excepción | Origen | Ejemplo |
|-----------|--------|---------|
| `ArcaAuthError` | `ArcaClient._create_webservice_with_ta_fallback` | Token expirado, cert inválido, "ya posee un TA válido" |
| `ArcaValidationError` | `FacturaBuilder.validate()` y `.build()` | Falta tipo_cbte, condición IVA inválida para clase |
| `ArcaNetworkError` | `ArcaClient` (wrapping excepciones de red) | Timeout SOAP, conexión rechazada, DNS |
| `ArcaError` | `ArcaClient` (cualquier error no clasificado) | Error de parseo de response, error interno ARCA |

### Patrón de captura recomendado

```python
try:
    result = procesar_factura(client, factura)
except ArcaValidationError as e:
    # Error de datos — no tiene sentido reintentar
    # Marcar como error y pasar a la siguiente
    factura.estado = 'error'
    factura.error_codigo = 'arca_validacion'
    factura.error_mensaje = str(e)

except (ArcaAuthError, ArcaNetworkError, ConnectionError, TimeoutError, OSError) as e:
    # Error de conexión — podría funcionar si se reintenta
    factura.estado = 'error'
    factura.error_codigo = 'arca_conexion'
    factura.error_mensaje = f'Error de conexión con ARCA: {str(e)}'

except ArcaError as e:
    # Error genérico de integración
    factura.estado = 'error'
    factura.error_codigo = 'arca_error'
    factura.error_mensaje = f'Error de integración con ARCA: {str(e)}'

except (InvalidOperation, ValueError, TypeError, RuntimeError) as e:
    # Error de procesamiento interno (cálculos, datos)
    factura.estado = 'error'
    factura.error_codigo = 'procesamiento_error'
    factura.error_mensaje = str(e)
```

**Regla clave**: `ArcaValidationError` nunca se reintenta — es un error de datos que requiere corrección humana. `ArcaAuthError` y `ArcaNetworkError` pueden reintentarse con estrategias específicas.

---

## 8.2 Errores de WSAA — "Ya posee un TA válido"

### 8.2.1 El Problema

WSAA (Web Service de Autenticación y Autorización) emite Tickets de Acceso (TA) con 12 horas de vigencia. Si se intenta solicitar un nuevo TA mientras uno válido ya existe, WSAA retorna:

```
"El CEE ya posee un TA válido para el acceso al WSN solicitado"
```

Esto ocurre frecuentemente en escenarios de concurrencia:
- Dos workers Celery procesan lotes del mismo CUIT simultáneamente
- Un worker se reinicia mientras el TA anterior sigue vigente
- La cache local del TA se pierde pero el TA sigue válido en WSAA

### 8.2.2 Estrategia en la Inicialización (ArcaClient)

El `ArcaClient` maneja este error durante la creación del `ArcaWebService`:

```python
def _create_webservice_with_ta_fallback(
    self, wsdl: str, service: str, error_prefix: str
) -> ArcaWebService:
    """
    Crea webservice con retry automático para error de TA duplicado.

    Estrategia:
    1. Intentar crear ArcaWebService (que internamente pide TA a WSAA)
    2. Si falla con "ya posee un TA válido":
       a. Esperar (backoff incremental: 1s, 2s)
       b. Re-aplicar settings (por si otra instancia los cambió)
       c. Verificar si existe un TA local válido en cache
       d. Reintentar (hasta 3 intentos)
    3. Si falla con otro error: lanzar ArcaAuthError
    """
    # File lock: serializa la inicialización para evitar
    # que dos procesos pidan TA al mismo tiempo
    with self._ta_file_lock(service):
        self._ensure_settings()

        for attempt in range(3):
            try:
                return ArcaWebService(wsdl, service, enable_logging=False)
            except Exception as e:
                message = str(e)
                lowered = self._normalize_wsaa_message(message)

                if 'ya posee un ta valido' in lowered and attempt < 2:
                    time.sleep(attempt + 1)  # Backoff: 1s, 2s
                    self._ensure_settings()
                    if self._has_valid_local_ta(service):
                        continue  # Reintentar con el TA cacheado
                    continue

                raise ArcaAuthError(f'{error_prefix}: {message}')

    raise ArcaAuthError(f'{error_prefix}: no se pudo inicializar el servicio')
```

### 8.2.3 Normalización de Mensajes WSAA

Los mensajes de error de WSAA pueden venir con o sin acentos. Se normalizan antes de comparar:

```python
def _normalize_wsaa_message(self, message: str) -> str:
    """Normaliza mensaje WSAA quitando acentos y pasando a minúsculas."""
    return (
        (message or '')
        .lower()
        .replace('á', 'a')
        .replace('é', 'e')
        .replace('í', 'i')
        .replace('ó', 'o')
        .replace('ú', 'u')
    )

# Variantes que se han observado:
# "El CEE ya posee un TA válido para el acceso al WSN solicitado"
# "El CEE ya posee un TA valido para el acceso al WSN solicitado"
# "ya posee un TA válido"
```

### 8.2.4 Verificación de TA Local

La librería `arca_arg` cachea los TAs como archivos en disco (formato interno de la librería). Se puede verificar si existe uno válido sin consultar WSAA:

```python
def _has_valid_local_ta(self, service: str) -> bool:
    """
    Verifica si existe un TA local válido en cache.

    Los archivos de cache son generados y consumidos localmente
    por la librería arca_arg como mecanismo de cache de TAs.
    No se deserializan datos de fuentes externas.

    Returns:
        True si existe un TA no expirado
    """
    ta_file = os.path.join(self._ta_path, f'{service}.pkl')
    if not os.path.exists(ta_file):
        return False

    try:
        # La librería arca_arg usa su propio formato de serialización
        # para cachear los TAs localmente
        import pickle
        with open(ta_file, 'rb') as f:
            ticket = pickle.load(f)
    except (OSError, EOFError, AttributeError, ValueError):
        return False

    # El objeto TA de arca_arg puede tener distintas interfaces
    # según la versión. Intentar múltiples métodos:

    # Método 1: atributo is_expired (bool)
    is_expired = getattr(ticket, 'is_expired', None)
    if isinstance(is_expired, bool):
        return not is_expired

    # Método 2: atributo expires (timestamp float)
    expires = getattr(ticket, 'expires', None)
    if isinstance(expires, (int, float)):
        return time.time() < float(expires)

    # Método 3: tiene algún dato de expiración (asumir válido)
    expires_str = getattr(ticket, 'expires_str', None)
    if expires_str:
        return True

    return False
```

### 8.2.5 Estrategia en el Procesamiento de Facturas

Además del retry en la inicialización, hay un retry a nivel de factura:

```python
def es_error_wsaa_retryable(result: dict) -> bool:
    """
    Detecta si el resultado de procesar_factura falló por error de WSAA.
    Esto puede pasar si el TA expiró DURANTE el procesamiento de un lote.
    """
    if not isinstance(result, dict) or result.get('success'):
        return False

    message = (result.get('error_message') or '').lower()
    retryable_fragments = [
        'ya posee un ta valido para el acceso al wsn solicitado',
        'ya posee un ta valido',
    ]
    return any(fragment in message for fragment in retryable_fragments)


# En el loop de procesamiento:
result = procesar_factura(client, factura, facturador)

if es_error_wsaa_retryable(result):
    # El TA pudo haber sido renovado por otro proceso.
    # Esperar y reintentar UNA vez.
    sleep(5)
    result = procesar_factura(client, factura, facturador)
    # Si falla de nuevo, se marca como error (no más retries)
```

---

## 8.3 Errores de Secuencia — Error 10016

### 8.3.1 El Problema

ARCA exige que los números de comprobante sean **estrictamente secuenciales**. El flujo normal es:

```
1. FECompUltimoAutorizado → retorna 14
2. CbteDesde = CbteHasta = 15 (próximo)
3. FECAESolicitar → autoriza comprobante 15
```

El error 10016 ocurre cuando entre el paso 1 y el paso 3, otro proceso autorizó el comprobante 15:

```
Observación 10016: "El campo CbteHasta con valor 15 no es menor
o igual al próximo a autorizar que es 16.
Consulte con FECompUltimoAutorizado..."
```

### 8.3.2 Causas

| Escenario | Descripción |
|-----------|-------------|
| **Concurrencia interna** | Dos workers procesan facturas del mismo facturador/PV/tipo |
| **Emisión externa** | El facturador emitió un comprobante desde otro sistema entre consulta y envío |
| **Retry sin re-consulta** | Se reintentó un envío fallido sin actualizar el número |

### 8.3.3 Detección

```python
def es_error_secuencia_retryable(result: dict) -> bool:
    """
    Detecta error 10016 (número de comprobante no secuencial).
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
```

### 8.3.4 Estrategia de Retry

Cuando se detecta error 10016:

1. **Sincronizar fecha**: verificar que la fecha de emisión no sea anterior al último comprobante autorizado (ARCA exige orden cronológico)
2. **Esperar brevemente**: 1 segundo para que el otro proceso termine
3. **Reintentar**: `procesar_factura` internamente re-consulta `FECompUltimoAutorizado`

```python
# En el loop de procesamiento:
result = procesar_factura(client, factura, facturador)

if es_error_secuencia_retryable(result):
    # Paso 1: sincronizar fecha con el último autorizado
    sincronizar_fecha_con_ultimo_autorizado(client, factura)
    # Paso 2: esperar
    sleep(1)
    # Paso 3: reintentar (procesar_factura re-consulta último número)
    result = procesar_factura(client, factura, facturador)
    # Si falla de nuevo, se marca como error
```

---

## 8.4 Sincronización de Fechas

### 8.4.1 El Problema

ARCA exige que las fechas de los comprobantes sean cronológicas dentro de cada combinación de tipo + punto de venta. Si el último comprobante autorizado tiene fecha `2026-03-09`, no se puede emitir uno con fecha `2026-03-08`.

Esto ocurre cuando:
- Se procesa un lote con facturas de fechas pasadas
- Se reintenta una factura que falló ayer
- El sistema tiene facturas encoladas que quedaron sin procesar

### 8.4.2 Implementación Completa

```python
from datetime import date, datetime


def sincronizar_fecha_con_ultimo_autorizado(client, factura) -> bool:
    """
    Ajusta la fecha de emisión de la factura si es anterior
    a la fecha del último comprobante autorizado en ARCA.

    Flujo:
    1. Consultar FECompUltimoAutorizado → obtener número
    2. Consultar FECompConsultar → obtener fecha de ese comprobante
    3. Si factura.fecha_emision < fecha_ultimo → ajustar

    También ajusta fechas de servicio si el concepto es 2 o 3.

    Returns:
        True si se ajustó la fecha, False si no fue necesario.
    """
    try:
        # Paso 1: obtener número del último comprobante
        ultimo_nro = client.fe_comp_ultimo_autorizado(
            punto_venta=factura.punto_venta,
            tipo_cbte=factura.tipo_comprobante,
        )

        if not ultimo_nro or int(ultimo_nro) <= 0:
            return False  # Nunca se emitió un comprobante → no hay restricción

        # Paso 2: consultar datos del último comprobante
        ultimo_data = client.fe_comp_consultar(
            tipo_cbte=factura.tipo_comprobante,
            punto_venta=factura.punto_venta,
            numero=int(ultimo_nro),
        )

        if not isinstance(ultimo_data, dict) or not ultimo_data.get('encontrado'):
            return False

        # Paso 3: parsear fecha del último comprobante
        ultima_fecha = parse_fecha_flexible(ultimo_data.get('fecha_cbte'))
        if not ultima_fecha:
            return False

        # Paso 4: comparar con fecha de nuestra factura
        if factura.fecha_emision and factura.fecha_emision >= ultima_fecha:
            return False  # Nuestra fecha ya es posterior → OK

        # Paso 5: ajustar fecha de emisión
        factura.fecha_emision = ultima_fecha

        # Paso 6: ajustar fechas de servicio (concepto 2 o 3)
        if factura.concepto in (2, 3):
            if factura.fecha_desde and factura.fecha_desde < ultima_fecha:
                factura.fecha_desde = ultima_fecha
            if factura.fecha_hasta and factura.fecha_hasta < ultima_fecha:
                factura.fecha_hasta = ultima_fecha
            if factura.fecha_vto_pago and factura.fecha_vto_pago < ultima_fecha:
                factura.fecha_vto_pago = ultima_fecha

        return True

    except Exception:
        # Si la sincronización falla, no bloquear el procesamiento.
        # El retry con el nuevo número de comprobante puede funcionar igual.
        return False


def parse_fecha_flexible(value) -> 'date | None':
    """
    Parsea fecha que puede venir en múltiples formatos.
    ARCA usa YYYYMMDD, pero FECompConsultar puede retornar como string o date.
    """
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

### 8.4.3 Diagrama de Decisión

```
Error 10016 detectado
        │
        ▼
FECompUltimoAutorizado → último_nro
        │
        ▼
FECompConsultar(último_nro) → última_fecha
        │
        ▼
¿factura.fecha_emision < última_fecha?
        │
   SÍ ──┼── NO ──► No ajustar, solo reintentar
        │           con nuevo número
        ▼
factura.fecha_emision = última_fecha
        │
        ▼
¿Concepto = servicios (2,3)?
        │
   SÍ ──┼── NO ──► Reintentar
        │
        ▼
Ajustar fecha_desde, fecha_hasta,
fecha_vto_pago si < última_fecha
        │
        ▼
Reintentar procesar_factura()
```

---

## 8.5 Bloqueo de Secuencia para Concurrencia

### 8.5.1 El Problema

En facturación masiva, un lote puede tener múltiples facturas del mismo facturador, punto de venta y tipo de comprobante. Si se procesan en paralelo, dos workers podrían consultar `FECompUltimoAutorizado` al mismo tiempo, obtener el mismo número, y causar error 10016.

### 8.5.2 Bloqueo a Nivel de Base de Datos

Se usa `SELECT ... FOR UPDATE` para serializar el acceso a la secuencia de un facturador:

```python
from contextlib import suppress


def lock_facturador_sequence(tenant_id, facturador_id):
    """
    Bloquea la fila del facturador con SELECT FOR UPDATE.
    Esto serializa el acceso: solo un proceso puede estar
    entre FECompUltimoAutorizado y FECAESolicitar.

    Si la base de datos no soporta FOR UPDATE (ej: SQLite en tests),
    ignora el error silenciosamente.

    Returns:
        Facturador bloqueado, o None si no se encontró.
    """
    query = Facturador.query.filter_by(
        id=facturador_id,
        tenant_id=tenant_id,
    )

    # FOR UPDATE puede fallar en SQLite (tests)
    with suppress(Exception):
        query = query.with_for_update()

    return query.first()
```

### 8.5.3 Bloqueo a Nivel de TA (File Lock)

Para evitar que dos procesos soliciten un nuevo TA al mismo tiempo, se usa `fcntl.flock`:

```python
import fcntl
from contextlib import contextmanager


@contextmanager
def ta_file_lock(ta_path: str, service: str):
    """
    File lock exclusivo para serializar la obtención de TA.

    Cada servicio (wsfe, ws_sr_constancia_inscripcion) tiene su
    propio lock file, así que un proceso puede obtener TA de WSFE
    mientras otro obtiene TA de padrón.

    Implementación:
    - Lock exclusivo (LOCK_EX): solo un proceso a la vez
    - Se libera automáticamente al salir del context manager
    - El archivo .lock se crea si no existe (mode='a+')
    """
    lock_path = os.path.join(ta_path, f'{service}.lock')
    lock_file = open(lock_path, 'a+')
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()


# Uso:
with ta_file_lock(self._ta_path, 'wsfe'):
    # Solo un proceso puede estar aquí
    ws = ArcaWebService(wsdl, 'wsfe', enable_logging=False)
```

### 8.5.4 Dos Niveles de Bloqueo

```
┌─────────────────────────────────────────────────────────────┐
│ Nivel 1: File Lock (fcntl.flock)                            │
│                                                             │
│ Alcance: obtención de TA (WSAA login)                       │
│ Granularidad: por servicio + CUIT + ambiente                │
│ Lock file: /tmp/arca_ta_cache/{ambiente}/{cuit}/{svc}.lock  │
│                                                             │
│ Previene: dos procesos pidiendo TA al mismo tiempo          │
│ → evita "ya posee un TA válido"                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Nivel 2: DB Lock (SELECT FOR UPDATE)                        │
│                                                             │
│ Alcance: emisión de comprobantes                            │
│ Granularidad: por facturador (cubre todos sus PV y tipos)   │
│ Lock: fila de tabla facturador                              │
│                                                             │
│ Previene: dos workers emitiendo con el mismo número         │
│ → evita error 10016                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 8.6 Errores de Conexión con ARCA

### 8.6.1 Tipos de Error de Red

```python
# Errores que pueden ocurrir al comunicarse con ARCA:

# 1. Timeout SOAP (servicio no responde)
# requests.exceptions.ReadTimeout
# zeep.exceptions.TransportError

# 2. Conexión rechazada (servicio caído)
# ConnectionRefusedError
# requests.exceptions.ConnectionError

# 3. DNS (servicio no resuelve)
# socket.gaierror

# 4. SSL (certificado inválido)
# ssl.SSLError
# requests.exceptions.SSLError

# 5. Servidor retorna error HTTP
# zeep.exceptions.TransportError (500, 503, etc.)
```

### 8.6.2 Manejo a Nivel de Grupo de Facturas

Cuando la conexión falla al crear el `ArcaClient` o al inicializar el servicio, **todas** las facturas del facturador se marcan como error:

```python
try:
    client = ArcaClient(cuit=cuit, cert=cert, key=key, ambiente=ambiente)
    _ = client.wsfe  # Fuerza obtención/reuso del TA

    for factura in facturas_grupo:
        result = procesar_factura(client, factura, facturador)
        # ... manejar resultado individual

except (
    ArcaAuthError,
    ArcaNetworkError,
    ArcaError,
    ConnectionError,
    TimeoutError,
    OSError,
    RuntimeError,
    ValueError,
) as e:
    # Error de conexión general → marcar TODO el grupo
    for factura in facturas_grupo:
        factura.estado = 'error'
        factura.error_codigo = 'conexion_arca'
        factura.error_mensaje = f'Error de conexión: {str(e)}'
    db.session.commit()
```

**Justificación**: Si no se puede conectar al servicio, no tiene sentido intentar cada factura individualmente — fallarían todas.

### 8.6.3 Manejo a Nivel de Factura Individual

Cuando la conexión funciona pero falla en una factura específica:

```python
try:
    result = procesar_factura(client, factura, facturador)
    # ... manejar resultado

except (ValueError, RuntimeError, ConnectionError, TimeoutError, OSError) as e:
    factura.estado = 'error'
    factura.error_codigo = 'procesamiento_error'
    factura.error_mensaje = str(e)
    # NO abortar el grupo — seguir con la siguiente factura
```

---

## 8.7 Resiliencia en la Inicialización

### 8.7.1 Precalentamiento del TA

Antes de procesar facturas, se fuerza la obtención/reuso del TA:

```python
# Crear cliente
client = ArcaClient(cuit=cuit, cert=cert, key=key, ambiente=ambiente)

# Forzar la obtención del TA UNA vez por facturador.
# Esto evita que la primera factura pague el costo de autenticación
# y permite detectar problemas de certificado/autorización temprano.
_ = client.wsfe

# Ahora procesar facturas — todas reusan el mismo TA
for factura in facturas_grupo:
    result = procesar_factura(client, factura, facturador)
```

### 8.7.2 Re-aplicación de Settings

`arca_arg` usa configuración global (`arca_arg.settings`). Si múltiples instancias de `ArcaClient` coexisten (ej: procesando facturas de dos CUITs distintos), los settings pueden pisarse entre sí:

```python
def _ensure_settings(self):
    """
    Re-aplica settings antes de CADA operación WSFE.

    Necesario porque arca_arg.settings es global y otra instancia
    de ArcaClient (otro CUIT) puede haber cambiado los values.
    """
    self._configure_settings()

# Se llama al inicio de cada método público:
def fe_comp_ultimo_autorizado(self, punto_venta, tipo_cbte):
    self._ensure_settings()  # ← siempre primero
    ws = self.wsfe
    # ...
```

---

## 8.8 Procesamiento Masivo — Arquitectura de Retry

### 8.8.1 Diagrama Completo del Loop de Procesamiento

```
procesar_lote(lote_id)
│
├── Cargar facturas pendientes (ORDER BY facturador, PV, tipo, fecha)
│
├── Agrupar por facturador_id
│
└── Para cada grupo de facturador:
    │
    ├── Cargar facturador + verificar certificados
    │   └── Si no tiene certs → marcar TODAS como error, CONTINUAR
    │
    ├── try: Crear ArcaClient + precalentar TA
    │   └── except: marcar TODAS como error, CONTINUAR
    │
    └── Para cada factura del grupo:
        │
        ├── try:
        │   ├── SELECT FOR UPDATE (lock secuencia)
        │   │
        │   ├── result = procesar_factura(client, factura)
        │   │   │
        │   │   ├── FECompUltimoAutorizado → número
        │   │   ├── FacturaBuilder → request
        │   │   ├── FECAESolicitar → response
        │   │   └── Parsear → dict{success, cae, error_code, ...}
        │   │
        │   ├── ¿Error WSAA retryable?
        │   │   └── SÍ → sleep(5) → procesar_factura de nuevo
        │   │
        │   ├── ¿Error secuencia (10016) retryable?
        │   │   └── SÍ → sincronizar_fecha → sleep(1) → procesar_factura de nuevo
        │   │
        │   ├── ¿success?
        │   │   ├── SÍ → estado='autorizado', guardar CAE
        │   │   └── NO → estado='error', guardar código+mensaje
        │   │
        │   └── db.session.commit()  ← commit POR FACTURA
        │
        ├── except: estado='error', commit
        │
        └── update_state(PROGRESS, {current, total, percent})

    Fin del grupo
│
├── Recalcular stats del lote (query GROUP BY estado)
├── lote.estado = 'completado'
└── db.session.commit()
```

### 8.8.2 Orden de Procesamiento

Las facturas se ordenan estratégicamente para minimizar problemas:

```python
facturas = Factura.query.filter_by(
    tenant_id=tenant_id,
    lote_id=lote_id,
    estado='pendiente'
).order_by(
    Factura.facturador_id.asc(),    # Agrupar por facturador (reusar conexión)
    Factura.punto_venta.asc(),      # Dentro del facturador, por PV
    Factura.tipo_comprobante.asc(), # Dentro del PV, por tipo
    Factura.fecha_emision.asc(),    # Dentro del tipo, cronológico (ARCA exige)
    Factura.id.asc(),               # Desempate estable
).all()
```

**Por qué este orden importa**:

1. **Por facturador**: Se crea un solo `ArcaClient` por grupo → una sola autenticación WSAA
2. **Por PV + tipo**: La secuencia numérica es por combinación PV+tipo → minimiza colisiones
3. **Por fecha ascendente**: ARCA exige cronología → procesando de más antigua a más reciente se evitan ajustes de fecha
4. **Por ID**: Desempate determinístico para facturas con misma fecha

### 8.8.3 Commit por Factura

El commit se hace después de cada factura, no al final del lote:

```python
for factura in facturas_grupo:
    try:
        result = procesar_factura(client, factura, facturador)
        # ... manejar resultado, actualizar factura
    except ...:
        # ... marcar error

    # Commit individual — si la siguiente factura falla,
    # esta ya quedó guardada
    db.session.commit()

    # Reportar progreso al frontend
    self.update_state(state='PROGRESS', meta={...})
```

**Justificación**: Si se cae el worker en la factura 50 de 100, las 49 anteriores ya están guardadas con su CAE o error. No se pierden.

### 8.8.4 Máximo Un Retry

Cada tipo de error retryable se reintenta **una sola vez**:

```python
result = procesar_factura(client, factura, facturador)

# Retry 1: error WSAA
if es_error_wsaa_retryable(result):
    sleep(5)
    result = procesar_factura(client, factura, facturador)

# Retry 2: error secuencia (solo si no fue WSAA)
if es_error_secuencia_retryable(result):
    sincronizar_fecha_con_ultimo_autorizado(client, factura)
    sleep(1)
    result = procesar_factura(client, factura, facturador)

# Sin más retries — marcar según resultado final
if result.get('success'):
    factura.estado = 'autorizado'
else:
    factura.estado = 'error'
```

**Justificación**: Más retries arriesgan emitir comprobantes duplicados, loops infinitos, o bloquear el procesamiento del lote. Un retry es suficiente para la mayoría de errores transitorios.

---

## 8.9 Errores No Retryables — Fallo Directo

Estos errores nunca se reintentan porque indican problemas que no se resuelven con un retry:

| Error | Código | Por qué no reintentar |
|-------|--------|----------------------|
| Importes no cuadran | `10048` | Error de datos, requiere corrección |
| Condición IVA faltante | `10242` | Falta dato del receptor |
| Fecha fuera de rango | `10013` | La fecha no va a cambiar con un retry |
| Doc inválido | `10015` | CUIT/DNI mal formado |
| Falta cbte asociado | `10025` | Error de datos de NC/ND |
| Facturador sin certificados | — | Requiere upload de certs |
| `ArcaValidationError` | — | Error de validación pre-envío |

---

## 8.10 Manejo de Errores Inesperados (Catch-All)

Si una excepción no esperada llega al nivel del lote, se hace rollback y se marca el lote como error:

```python
@shared_task(bind=True)
def procesar_lote(self, lote_id, tenant_id):
    lote = Lote.query.filter_by(id=lote_id, tenant_id=tenant_id).first()

    try:
        # ... procesamiento normal ...

        lote.estado = 'completado'
        db.session.commit()
        return {'status': 'completed', ...}

    except Exception as exc:
        # Excepción no esperada → rollback + marcar lote como error
        logger.exception('Fallo inesperado procesando lote %s', lote_id)
        db.session.rollback()

        # Intentar marcar el lote como error (nueva transacción)
        lote_fallback = Lote.query.filter_by(
            id=lote_id, tenant_id=tenant_id
        ).first()
        if lote_fallback:
            lote_fallback.estado = 'error'
            lote_fallback.processed_at = datetime.utcnow()
            db.session.commit()

        raise  # Re-raise para que Celery la registre como FAILURE
```

**Notas**:
- `db.session.rollback()` deshace cualquier cambio no commiteado
- Se re-carga el lote después del rollback (el objeto anterior puede estar "dirty")
- `raise` sin argumento re-lanza la excepción original para que Celery la marque como `FAILURE`
- Las facturas que ya se commitearon individualmente **no se pierden** (cada una tiene su propio commit)

---

## 8.11 Resumen de Tiempos de Espera

| Escenario | Espera | Motivo |
|-----------|--------|--------|
| Error WSAA "ya posee TA válido" (inicialización) | `attempt + 1` segundos (1s, 2s) | Esperar que el TA se estabilice |
| Error WSAA "ya posee TA válido" (procesamiento) | 5 segundos | Dar tiempo a que otro proceso termine |
| Error 10016 de secuencia | 1 segundo | Breve pausa antes de re-consultar |

---

## 8.12 Implementación de Referencia Simplificada

Para una implementación nueva que no tiene la complejidad de Celery/lotes, este es el patrón mínimo:

```python
import time
from arca_integration import ArcaClient
from arca_integration.builders import FacturaBuilder
from arca_integration.services import WSFEService
from arca_integration.exceptions import (
    ArcaError, ArcaAuthError, ArcaValidationError, ArcaNetworkError
)


def emitir_comprobante_con_retry(
    client: ArcaClient,
    builder: FacturaBuilder,
    max_retries: int = 1,
) -> dict:
    """
    Emite un comprobante con retry automático para errores transitorios.

    Returns:
        {'success': True, 'cae': str, ...} o
        {'success': False, 'error_code': str, 'error_message': str}
    """
    wsfe = WSFEService(client)
    last_result = None

    for attempt in range(max_retries + 1):
        try:
            # Obtener próximo número (siempre re-consultar)
            ultimo = client.fe_comp_ultimo_autorizado(
                punto_venta=builder._punto_venta,
                tipo_cbte=builder._tipo_cbte,
            )
            builder._numero = ultimo + 1

            # Rebuild con nuevo número
            request_data = builder.build()

            # Enviar a ARCA
            response = wsfe.autorizar(request_data)

            if response.get('success'):
                return response

            # ¿Error retryable?
            error_msg = (response.get('error_message') or '').lower()
            error_code = str(response.get('error_code') or '')

            is_wsaa_error = 'ya posee un ta valido' in error_msg
            is_sequence_error = (
                error_code == '10016'
                or 'proximo a autorizar' in error_msg
            )

            if (is_wsaa_error or is_sequence_error) and attempt < max_retries:
                wait = 5 if is_wsaa_error else 1
                time.sleep(wait)
                continue  # Reintentar

            # No retryable o último intento
            last_result = response
            break

        except ArcaValidationError as e:
            return {
                'success': False,
                'error_code': 'validacion',
                'error_message': str(e),
            }

        except (ArcaAuthError, ArcaNetworkError) as e:
            if attempt < max_retries:
                time.sleep(3)
                continue
            return {
                'success': False,
                'error_code': 'conexion',
                'error_message': str(e),
            }

        except ArcaError as e:
            return {
                'success': False,
                'error_code': 'arca_error',
                'error_message': str(e),
            }

    return last_result or {
        'success': False,
        'error_code': 'max_retries',
        'error_message': 'Se agotaron los reintentos',
    }
```

### Uso:

```python
from datetime import date

client = ArcaClient(cuit='20301234567', cert=cert_bytes, key=key_bytes)

builder = (
    FacturaBuilder()
    .set_comprobante(tipo=6, punto_venta=1, numero=0, concepto=1)  # número se sobreescribe
    .set_fechas(emision=date.today())
    .set_receptor(doc_tipo=96, doc_nro='12345678')
    .set_importes(total=12100, neto=10000, iva=2100)
    .set_condicion_iva_receptor(5)
    .add_iva(alicuota_id=5, base_imponible=10000, importe=2100)
)

result = emitir_comprobante_con_retry(client, builder, max_retries=1)

if result['success']:
    print(f"CAE: {result['cae']}")
else:
    print(f"Error: {result['error_message']}")
```
