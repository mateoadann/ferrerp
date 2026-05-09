# 6. Reglas de Negocio Críticas

Este documento profundiza en las tres reglas de negocio que causan la mayoría de rechazos de ARCA: la obligatoriedad de `CondicionIVAReceptorId` (RG 5616), la normalización de importes según la clase de comprobante, y el cálculo correcto del detalle de IVA desde items. Se incluyen edge cases, errores frecuentes, y estrategias de resolución.

---

## 6.1 RG 5616 — CondicionIVAReceptorId Obligatorio

### 6.1.1 Contexto Regulatorio

La Resolución General 5616 de ARCA (ex-AFIP) establece que el campo `CondicionIVAReceptorId` es **obligatorio** en todas las operaciones de `FECAESolicitar`, para **todas las clases** de comprobante (A, B, C, M). Antes de esta resolución, el campo era opcional y solo algunos sistemas lo enviaban.

El incumplimiento produce el **error 10242**:

```
Error 10242: "El campo CondicionIVAReceptorId es obligatorio para
el tipo de comprobante seleccionado."
```

### 6.1.2 Catálogo Completo de Condiciones IVA

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
```

> **Nota**: Los IDs 2, 3, 12, 14 no existen. No son consecutivos.

### 6.1.3 Condiciones Válidas por Clase de Comprobante

A diferencia de lo que podría suponerse, **todos los códigos son válidos para todas las clases**. Esto fue confirmado mediante la operación `FEParamGetCondicionIvaReceptor` de ARCA:

```python
CONDICIONES_IVA_POR_CLASE = {
    'A': {1, 4, 5, 6, 7, 8, 9, 10, 13, 15, 16},
    'B': {1, 4, 5, 6, 7, 8, 9, 10, 13, 15, 16},
    'C': {1, 4, 5, 6, 7, 8, 9, 10, 13, 15, 16},
    'M': {1, 4, 5, 6, 7, 8, 9, 10, 13, 15, 16},
}
```

> **Advertencia histórica**: Documentación antigua de AFIP y algunas librerías indican que la clase B solo aceptaba `{5, 8, 9}`. Esto es **incorrecto** y fue actualizado. Limitar las condiciones válidas para clase B causaría rechazos innecesarios en tu validación local.

### 6.1.4 Regla Especial: Clase B Siempre Condición 5

Aunque ARCA acepta cualquier código para clase B, en la práctica la convención es enviar **siempre `CondicionIVAReceptorId = 5`** (Consumidor Final) para comprobantes clase B. Esto se debe a que:

- La clase B ya indica que el receptor NO es Responsable Inscripto
- ARCA internamente trata a todos los receptores de Factura B como consumidores finales a efectos del IVA
- Enviar la condición real del receptor (ej: 6 = Monotributo) funciona, pero no agrega valor y puede causar confusión en auditorías

```python
# Implementación: override para clase B
def resolver_condicion_para_wsfe(condicion_iva_id: int, tipo_comprobante: int) -> int:
    """
    Para clase B: siempre retorna 5 (Consumidor Final).
    Para otras clases: retorna la condición real del receptor.
    """
    TIPO_CBTE_CLASE = {
        1: 'A', 2: 'A', 3: 'A',
        6: 'B', 7: 'B', 8: 'B',
        11: 'C', 12: 'C', 13: 'C',
        51: 'M', 52: 'M', 53: 'M',
    }
    if TIPO_CBTE_CLASE.get(tipo_comprobante) == 'B':
        return 5
    return condicion_iva_id
```

### 6.1.5 Algoritmo de Resolución Completo

Cuando el sistema no tiene la condición IVA del receptor guardada, se sigue este algoritmo con fallbacks:

```
┌─────────────────────────────────────────────────────┐
│  ¿El receptor tiene condicion_iva_id guardado?      │
│                                                     │
│  SÍ ──► Usar ese ID directamente                    │
│                                                     │
│  NO ──► ¿Tiene nombre de condición IVA (legacy)?    │
│         │                                           │
│         ├── SÍ ──► ¿Es un número?                   │
│         │          ├── SÍ ──► Validar que existe     │
│         │          │         en CONDICIONES_IVA      │
│         │          └── NO ──► Buscar por nombre      │
│         │                    normalizado             │
│         │                                           │
│         └── NO ──► ¿Tipo doc = DNI (96) u Otro (99)?│
│                    ├── SÍ ──► Usar 5 (Cons. Final)  │
│                    └── NO ──► ¿Tipo doc = CUIT/CUIL? │
│                               ├── SÍ ──► Consultar  │
│                               │         padrón ARCA  │
│                               └── NO ──► Usar 5     │
│                                         (default)    │
└─────────────────────────────────────────────────────┘
```

```python
def resolver_condicion_iva_receptor(
    condicion_iva_id: int | None,
    condicion_iva_nombre: str | None,
    doc_tipo: int,
) -> int | None:
    """
    Resuelve CondicionIVAReceptorId.

    Returns:
        int con el ID, o None si no se pudo resolver
        (y se necesita consultar el padrón de ARCA).
    """
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

    # Prioridad 1: ID directo
    if condicion_iva_id is not None:
        return condicion_iva_id

    # Prioridad 2: resolver desde nombre (backwards compatibility)
    if condicion_iva_nombre:
        raw = condicion_iva_nombre.strip()

        # ¿Es un ID numérico como string?
        if raw.isdigit():
            cond_id = int(raw)
            if cond_id in CONDICIONES_IVA:
                return cond_id

        # Buscar por nombre normalizado
        normalized = ' '.join(raw.lower().replace('–', '-').split())
        for cond_id, desc in CONDICIONES_IVA.items():
            desc_norm = ' '.join(desc.lower().replace('–', '-').split())
            if desc_norm == normalized:
                return cond_id

    # Prioridad 3: fallback por tipo de documento
    if doc_tipo in (96, 99):  # DNI o Doc. (Otro)
        return 5  # Consumidor Final

    if doc_tipo in (80, 86, 87):  # CUIT, CUIL, CDI
        # NO inferir: el receptor con CUIT puede ser RI, Mono, Exento, etc.
        # Enviar un valor incorrecto causa rechazo por inconsistencia.
        return None  # Señal para consultar padrón

    return 5  # Default general: Consumidor Final


# IMPORTANTE: Si retorna None, se DEBE consultar el padrón de ARCA
# antes de enviar el comprobante. Ver sección 6.1.6.
```

### 6.1.6 Autocompletado desde Padrón ARCA

Cuando `resolver_condicion_iva_receptor()` retorna `None`, la condición IVA se obtiene consultando el padrón de ARCA. Esta consulta usa un servicio distinto a WSFE (el padrón `ws_sr_padron_a13`):

```python
def autocompletar_condicion_iva_desde_padron(
    client,        # ArcaClient ya conectado
    doc_nro: str,
    doc_tipo: int,
) -> int | None:
    """
    Consulta padrón ARCA para obtener condición IVA de un CUIT.

    Requisitos:
    - Solo funciona con doc_tipo 80 (CUIT), 86 (CUIL), 87 (CDI)
    - El documento debe tener exactamente 11 dígitos

    Returns:
        ID de condición IVA, o None si no se pudo obtener.
    """
    # Solo CUIT/CUIL/CDI pueden consultarse en el padrón
    if doc_tipo not in (80, 86, 87):
        return None

    doc = doc_nro.replace('-', '').replace(' ', '')
    if not doc.isdigit() or len(doc) != 11:
        return None

    try:
        result = client.consultar_padron(doc)
        if not result.get('success'):
            return None

        data = result.get('data', {})
        condicion_iva_nombre = data.get('condicion_iva')  # Viene como string
        if not condicion_iva_nombre:
            return None

        # Convertir nombre a ID
        CONDICIONES_IVA = {
            1: 'IVA Responsable Inscripto',
            4: 'IVA Sujeto Exento',
            5: 'Consumidor Final',
            6: 'Responsable Monotributo',
            # ... (catálogo completo)
        }
        normalized = ' '.join(condicion_iva_nombre.lower().replace('–', '-').split())
        for cond_id, desc in CONDICIONES_IVA.items():
            if ' '.join(desc.lower().replace('–', '-').split()) == normalized:
                return cond_id

        return None

    except Exception:
        # Si el padrón falla, NO bloquear la facturación.
        # El sistema debe decidir: rechazar la factura o usar un default.
        return None
```

**Beneficios adicionales del padrón**: Además de la condición IVA, el padrón retorna:
- `razon_social`: nombre/razón social actualizado
- `direccion`: domicilio fiscal

Estos datos se pueden usar para enriquecer la información del receptor.

### 6.1.7 Qué Hacer si No se Obtiene la Condición IVA

Si después de todo el algoritmo de resolución (ID guardado → nombre → tipo doc → padrón) no se pudo determinar la condición IVA, hay dos opciones:

**Opción A: Rechazar la factura (recomendado)**
```python
if condicion_iva_id is None:
    raise ValueError(
        f'No se pudo determinar la condicion IVA del receptor {doc_nro}. '
        'Completa la condicion IVA del receptor manualmente.'
    )
```

**Opción B: Asumir Consumidor Final (solo para Factura B)**
```python
if condicion_iva_id is None:
    if TIPO_CBTE_CLASE.get(tipo_comprobante) == 'B':
        condicion_iva_id = 5  # Para B siempre es 5 de todas formas
    else:
        raise ValueError('Condición IVA no determinada')
```

> **Nunca asumir condición IVA para clase A**: Enviar `CondicionIVAReceptorId = 1` (RI) para un receptor que en realidad es Monotributo causa el error `10242` o peor, emite un comprobante con datos incorrectos que después hay que anular.

### 6.1.8 Validación Cruzada Clase ↔ Condición IVA

Aunque ARCA acepta todos los códigos para todas las clases, existen combinaciones que indican un error lógico:

```python
def validar_coherencia_clase_condicion(tipo_cbte: int, condicion_iva_id: int) -> str | None:
    """
    Detecta combinaciones sospechosas (no rechazadas por ARCA pero
    probablemente erróneas).

    Returns:
        Warning message o None si todo OK.
    """
    TIPO_CBTE_CLASE = {1:'A',2:'A',3:'A',6:'B',7:'B',8:'B',11:'C',12:'C',13:'C',51:'M',52:'M',53:'M'}
    clase = TIPO_CBTE_CLASE.get(tipo_cbte)

    # Factura A a Consumidor Final → probablemente debería ser Factura B
    if clase == 'A' and condicion_iva_id == 5:
        return (
            'WARNING: Factura A con receptor Consumidor Final. '
            '¿Debería ser Factura B?'
        )

    # Factura A a Monotributo → probablemente debería ser Factura B
    if clase == 'A' and condicion_iva_id in (6, 13, 16):
        return (
            'WARNING: Factura A con receptor Monotributo. '
            '¿Debería ser Factura B?'
        )

    # Factura C emitida por RI → el emisor debería emitir A o B
    # (Factura C es solo para Monotributistas)
    if clase == 'C' and condicion_iva_id == 1:
        return (
            'INFO: Factura C con receptor RI. '
            'Verificar que el emisor sea Monotributista.'
        )

    return None
```

---

## 6.2 Normalización de Importes por Clase de Comprobante

### 6.2.1 El Problema

Los importes que el usuario carga (o que vienen de un CSV) no siempre coinciden con lo que ARCA espera según la clase de comprobante. Por ejemplo:

- Un usuario carga una Factura C con `IVA = 2100` → ARCA la rechaza porque clase C no lleva IVA
- Un usuario carga una Factura B con `neto = 12100, IVA = 0` → ARCA la rechaza por RG 5614 (falta discriminar IVA)
- Un usuario carga una Factura C con `total = 12100, neto = 10000` → los importes no cuadran para clase C

La normalización corrige estos datos **antes** de enviarlos a ARCA.

### 6.2.2 Ecuación Fundamental de Importes

ARCA valida esta ecuación para TODOS los comprobantes:

```
ImpTotal = ImpNeto + ImpIVA + ImpTotConc + ImpOpEx + ImpTrib
```

Si `abs(Total - Suma) > 0.01`, ARCA rechaza con **error 10048**.

Para el caso más común (sin tributos, sin exentos, sin no gravados):

```
ImpTotal = ImpNeto + ImpIVA
```

### 6.2.3 Normalización por Clase — Implementación Completa

```python
from decimal import Decimal, ROUND_HALF_UP

TIPOS_COMPROBANTE_C = {11, 12, 13}
TIPO_CBTE_CLASE = {
    1: 'A', 2: 'A', 3: 'A',
    6: 'B', 7: 'B', 8: 'B',
    11: 'C', 12: 'C', 13: 'C',
    51: 'M', 52: 'M', 53: 'M',
}


def normalizar_importes(
    tipo_comprobante: int,
    importe_neto: Decimal | int | float | None,
    importe_iva: Decimal | int | float | None,
    importe_total: Decimal | int | float | None,
) -> tuple[Decimal, Decimal, Decimal]:
    """
    Normaliza importes según la clase del comprobante.

    Reglas:
    - Clase A: sin modificación (el usuario debe informar neto + IVA correctamente)
    - Clase B: si IVA = 0 y total > 0, calcula IVA desde el total (21%)
    - Clase C: IVA = 0, Total = Neto
    - Clase M: igual que clase A

    Returns:
        (neto, iva, total) como Decimal con 2 decimales
    """
    neto = Decimal(str(importe_neto or 0)).quantize(Decimal('0.01'))
    iva = Decimal(str(importe_iva or 0)).quantize(Decimal('0.01'))
    total = Decimal(str(importe_total or 0)).quantize(Decimal('0.01'))

    clase = TIPO_CBTE_CLASE.get(int(tipo_comprobante))

    if clase == 'C':
        # Clase C: Monotributo → NO discrimina IVA
        # IVA siempre 0, Total = Neto
        iva = Decimal('0.00')
        total = neto

    elif clase == 'B':
        # Clase B: IVA incluido en el total (RG 5614 - Transparencia Fiscal)
        # Si el IVA no viene informado, lo calculamos desde el total
        if iva == Decimal('0.00') and total > 0:
            iva = (total / Decimal('1.21') * Decimal('0.21')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            neto = total - iva

    # Clase A y M: sin modificación
    # El usuario/sistema debe proporcionar neto, IVA y total correctamente

    return neto, iva, total
```

### 6.2.4 Clase A — Sin Modificación

Para Factura A, los importes deben venir correctos desde el origen:

```python
# Factura A: el usuario informa neto e IVA por separado
neto = Decimal('10000.00')
iva = Decimal('2100.00')      # 21% de 10000
total = Decimal('12100.00')   # neto + iva

neto, iva, total = normalizar_importes(1, neto, iva, total)
# Sin cambios: (10000.00, 2100.00, 12100.00)
```

**Si los importes no cuadran en clase A, ARCA rechaza.** La normalización no los corrige porque no puede asumir qué valor es incorrecto.

### 6.2.5 Clase B — Cálculo de IVA desde Total (RG 5614)

La RG 5614 (Transparencia Fiscal) obliga a discriminar el IVA en Factura B. El problema es que muchos sistemas cargan la Factura B con el total (IVA incluido) sin desglosar:

```python
# Caso 1: usuario carga total sin IVA → se calcula automáticamente
neto, iva, total = normalizar_importes(6, Decimal('0'), Decimal('0'), Decimal('12100'))
# Resultado: (10000.00, 2100.00, 12100.00)

# Caso 2: usuario carga neto sin IVA, total incluye IVA → se calcula
neto, iva, total = normalizar_importes(6, Decimal('12100'), Decimal('0'), Decimal('12100'))
# Resultado: (10000.00, 2100.00, 12100.00)
# NOTA: neto se recalcula como total - iva, no se usa el valor original

# Caso 3: usuario ya informa IVA correctamente → sin cambios
neto, iva, total = normalizar_importes(6, Decimal('10000'), Decimal('2100'), Decimal('12100'))
# Resultado: (10000.00, 2100.00, 12100.00)
# El IVA no era 0, así que no se recalcula
```

**Fórmula de desglose IVA 21% desde total**:

```
iva = total / 1.21 * 0.21
neto = total - iva
```

> **Limitación**: Esta fórmula asume 21% de IVA. Si el comprobante tiene alícuotas distintas (10.5%, 27%), el cálculo automático no es correcto. En esos casos, el IVA debe venir informado desde el origen.

### 6.2.6 Clase C — IVA Siempre Cero

El Monotributo no discrimina IVA, por lo que ARCA exige:

```python
# Clase C: cualquier IVA informado se fuerza a 0
neto, iva, total = normalizar_importes(11, Decimal('10000'), Decimal('2100'), Decimal('12100'))
# Resultado: (10000.00, 0.00, 10000.00)
# IVA forzado a 0, Total forzado a Neto
```

**Consecuencias en el request**:
- `ImpIVA` = `0.0`
- `ImpNeto` = `ImpTotal`
- **No incluir** el array `Iva.AlicIva` en el request
- Si se incluye `Iva.AlicIva`, ARCA rechaza con error

### 6.2.7 Escenarios Edge Case

```python
# Edge case 1: Total = 0 (factura de $0 — puede pasar en NC que anula otra)
neto, iva, total = normalizar_importes(6, Decimal('0'), Decimal('0'), Decimal('0'))
# Resultado: (0.00, 0.00, 0.00)
# No intenta calcular IVA porque total = 0

# Edge case 2: Valores None
neto, iva, total = normalizar_importes(11, None, None, None)
# Resultado: (0.00, 0.00, 0.00)
# None se convierte a 0

# Edge case 3: Valores float con muchos decimales
neto, iva, total = normalizar_importes(1, 10000.333, 2100.0699, 12100.403)
# Resultado: (10000.33, 2100.07, 12100.40)
# Se quantiza a 2 decimales

# Edge case 4: Factura B donde el neto viene como total (error de carga)
# Usuario puso total=12100 en el campo neto, dejó total en 0
neto, iva, total = normalizar_importes(6, Decimal('12100'), Decimal('0'), Decimal('0'))
# Resultado: (12100.00, 0.00, 0.00)
# ⚠️ No se corrige porque total = 0 → la condición "total > 0" no se cumple
# Este caso debe manejarse en validación previa
```

### 6.2.8 Cuándo Aplicar la Normalización

La normalización se aplica **después** de leer los datos del usuario y **antes** de construir el request con FacturaBuilder:

```python
# Flujo correcto:
# 1. Leer datos (CSV, UI, API)
# 2. Normalizar importes
neto, iva, total = normalizar_importes(tipo_cbte, factura.neto, factura.iva, factura.total)

# 3. Actualizar el modelo local (para que refleje los valores reales enviados)
factura.importe_neto = neto
factura.importe_iva = iva
factura.importe_total = total

# 4. Construir request con valores normalizados
builder.set_importes(total=float(total), neto=float(neto), iva=float(iva))
```

---

## 6.3 Cálculo de IVA desde Items

### 6.3.1 Por Qué se Necesita el Detalle por Alícuota

ARCA no solo requiere el total de IVA (`ImpIVA`), sino el **desglose por alícuota** en el array `Iva.AlicIva`. Cada entrada especifica:

```python
{
    'Id': 5,              # Código de alícuota (5 = 21%)
    'BaseImp': 10000.00,  # Base imponible gravada a esa alícuota
    'Importe': 2100.00,   # Monto de IVA resultante
}
```

ARCA valida dos consistencias:
1. `sum(AlicIva[].Importe)` **debe coincidir** con `ImpIVA` (error 10017 si no)
2. `sum(AlicIva[].BaseImp)` **debe coincidir** con `ImpNeto` (error 10048 si no)

### 6.3.2 Alícuotas Válidas de ARCA

```python
ALICUOTAS_IVA = {
    3: {'porcentaje': 0,    'descripcion': '0%'},
    4: {'porcentaje': 10.5, 'descripcion': '10.5%'},
    5: {'porcentaje': 21,   'descripcion': '21%'},
    6: {'porcentaje': 27,   'descripcion': '27%'},
    8: {'porcentaje': 5,    'descripcion': '5%'},
    9: {'porcentaje': 2.5,  'descripcion': '2.5%'},
}
```

> **IDs no consecutivos**: No existen las alícuotas 1, 2, 7. El ID 3 es 0% (no gravado a tasa 0), no "sin IVA".

### 6.3.3 Caso Simple: Una Sola Alícuota (21%)

El 90% de las facturas tiene una sola alícuota al 21%:

```python
# Todos los items al 21%
imp_neto = Decimal('10000.00')
imp_iva = Decimal('2100.00')

# Un solo AlicIva
builder.add_iva(
    alicuota_id=5,              # 21%
    base_imponible=float(imp_neto),
    importe=float(imp_iva),
)
```

### 6.3.4 Caso Complejo: Múltiples Alícuotas

Cuando la factura tiene items con distintas alícuotas, se debe agrupar por alícuota y calcular cada IVA:

```python
from decimal import Decimal, ROUND_HALF_UP

ALICUOTAS_IVA = {
    3: {'porcentaje': 0},
    4: {'porcentaje': 10.5},
    5: {'porcentaje': 21},
    6: {'porcentaje': 27},
    8: {'porcentaje': 5},
    9: {'porcentaje': 2.5},
}


def build_iva_from_items(items: list[dict]) -> list[dict]:
    """
    Agrupa items por alícuota IVA y calcula el detalle.

    Cada item debe tener:
    - 'importe_neto': base imponible del item (obligatorio)
    - 'alicuota_iva_id': código alícuota (opcional, default 5 = 21%)

    Returns:
        Lista de dicts con 'Id', 'BaseImp', 'Importe' para Iva.AlicIva
    """
    # Paso 1: agrupar bases imponibles por alícuota
    bases_por_alicuota: dict[int, Decimal] = {}

    for item in items:
        alicuota_id = item.get('alicuota_iva_id', 5)  # Default: 21%

        # Ignorar alícuotas desconocidas
        if alicuota_id not in ALICUOTAS_IVA:
            continue

        base = Decimal(str(item['importe_neto']))
        bases_por_alicuota[alicuota_id] = (
            bases_por_alicuota.get(alicuota_id, Decimal('0')) + base
        )

    if not bases_por_alicuota:
        return []

    # Paso 2: calcular IVA por cada alícuota
    iva_result = []
    for alicuota_id in sorted(bases_por_alicuota.keys()):
        base = bases_por_alicuota[alicuota_id].quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        porcentaje = Decimal(str(ALICUOTAS_IVA[alicuota_id]['porcentaje']))
        importe = (base * porcentaje / Decimal('100')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        iva_result.append({
            'Id': alicuota_id,
            'BaseImp': base,
            'Importe': importe,
        })

    return iva_result
```

**Ejemplo con 3 alícuotas distintas:**

```python
items = [
    # 3 items al 21%
    {'importe_neto': 5000, 'alicuota_iva_id': 5},
    {'importe_neto': 3000, 'alicuota_iva_id': 5},
    {'importe_neto': 2000, 'alicuota_iva_id': 5},
    # 1 item al 10.5%
    {'importe_neto': 4000, 'alicuota_iva_id': 4},
    # 1 item al 27%
    {'importe_neto': 1000, 'alicuota_iva_id': 6},
]

iva_detalle = build_iva_from_items(items)
# Resultado:
# [
#     {'Id': 4, 'BaseImp': Decimal('4000.00'), 'Importe': Decimal('420.00')},   # 10.5%
#     {'Id': 5, 'BaseImp': Decimal('10000.00'), 'Importe': Decimal('2100.00')}, # 21%
#     {'Id': 6, 'BaseImp': Decimal('1000.00'), 'Importe': Decimal('270.00')},   # 27%
# ]

# Totales:
imp_neto = sum(a['BaseImp'] for a in iva_detalle)   # 15000.00
imp_iva = sum(a['Importe'] for a in iva_detalle)     # 2790.00
imp_total = imp_neto + imp_iva                        # 17790.00
```

### 6.3.5 Ajuste de Redondeo

Cuando se suman los IVA calculados individualmente por alícuota, el total puede diferir del IVA informado en la factura por centavos de redondeo. ARCA rechaza si no coinciden exactamente.

**Estrategia**: ajustar la última alícuota para absorber la diferencia.

```python
def ajustar_redondeo_iva(
    iva_detalle: list[dict],
    iva_total_factura: Decimal,
) -> None:
    """
    Ajusta el último AlicIva para que sum(Importe) == iva_total_factura.
    Modifica iva_detalle in-place.

    Ejemplo:
        Si sum(Importe) = 2099.99 pero iva_total_factura = 2100.00,
        incrementa el último Importe en 0.01.
    """
    if not iva_detalle:
        return

    total_calculado = sum(
        Decimal(str(a['Importe'])) for a in iva_detalle
    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    diff = (iva_total_factura - total_calculado).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )

    if diff != Decimal('0'):
        iva_detalle[-1]['Importe'] = (
            Decimal(str(iva_detalle[-1]['Importe'])) + diff
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
```

**Ejemplo de ajuste:**

```python
# Items que generan redondeo problemático
items = [
    {'importe_neto': 33.33, 'alicuota_iva_id': 5},
    {'importe_neto': 33.33, 'alicuota_iva_id': 5},
    {'importe_neto': 33.34, 'alicuota_iva_id': 5},
]
# Neto total: 100.00
# IVA teórico: 21.00
# IVA calculado item por item:
#   33.33 * 0.21 = 7.00 (redondeado)
#   33.33 * 0.21 = 7.00 (redondeado)
#   33.34 * 0.21 = 7.00 (redondeado)
# Suma IVA items: 21.00 ← coincide, pero no siempre

# Con valores más complejos:
items2 = [
    {'importe_neto': 33.33, 'alicuota_iva_id': 5},
    {'importe_neto': 33.33, 'alicuota_iva_id': 4},  # 10.5%
]
iva_detalle = build_iva_from_items(items2)
# iva_detalle = [
#     {'Id': 4, 'BaseImp': 33.33, 'Importe': 3.50},   # 33.33 * 10.5% = 3.49965 → 3.50
#     {'Id': 5, 'BaseImp': 33.33, 'Importe': 7.00},   # 33.33 * 21% = 6.9993 → 7.00
# ]
# Suma: 10.50
# Si el total factura dice IVA = 10.49, hay que ajustar:
ajustar_redondeo_iva(iva_detalle, Decimal('10.49'))
# Resultado: último Importe cambia de 7.00 a 6.99
```

### 6.3.6 Caso Especial: Factura B sin IVA en Items (items_sin_iva)

Cuando una Factura B se importa desde un CSV donde los items tienen el precio **con IVA incluido** (sin discriminar), los items no tienen `importe_neto` desglosado. En este caso, no se puede calcular IVA por item y se usa un fallback:

```python
def build_iva_for_factura_b_sin_desglose(
    importe_neto: Decimal,
    importe_iva: Decimal,
) -> list[dict]:
    """
    Fallback para Factura B cuando los items no tienen IVA discriminado.
    Usa los importes normalizados de la factura completa.
    Asume 21% (alícuota por defecto).

    Precondición: importe_neto e importe_iva ya fueron normalizados
    por normalizar_importes() (que calcula IVA desde total para clase B).
    """
    base = importe_neto.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    iva = importe_iva.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    if base <= 0 or iva <= 0:
        return []

    return [{
        'Id': 5,         # 21%
        'BaseImp': base,
        'Importe': iva,
    }]
```

### 6.3.7 Fallback: Sin Items Detallados

Si la factura no tiene items individuales (solo totales), se usa directamente neto e IVA como una sola alícuota al 21%:

```python
def build_iva_fallback(
    importe_neto: Decimal,
    importe_iva: Decimal,
) -> list[dict]:
    """
    Fallback cuando no hay items: asume alícuota única de 21%.
    """
    if importe_iva <= Decimal('0'):
        return []

    return [{
        'Id': 5,                        # 21%
        'BaseImp': float(importe_neto),
        'Importe': float(importe_iva),
    }]
```

### 6.3.8 Cuándo Incluir y Cuándo Omitir el Array Iva

```python
def debe_incluir_iva_en_request(tipo_comprobante: int, importe_iva: Decimal) -> bool:
    """
    Determina si el request debe incluir el array Iva.AlicIva.

    Reglas:
    - Clase C (11, 12, 13): NUNCA incluir → ARCA rechaza si se incluye
    - Otras clases: incluir solo si ImpIVA > 0
    - Si ImpIVA = 0 en clase A/B/M: no incluir (comprobante exento/no gravado)
    """
    TIPOS_COMPROBANTE_C = {11, 12, 13}

    if int(tipo_comprobante) in TIPOS_COMPROBANTE_C:
        return False

    return importe_iva > Decimal('0')
```

### 6.3.9 Alícuota 0% (Id = 3)

La alícuota 0% existe en ARCA y tiene un uso específico: **operaciones gravadas a tasa 0%** (no es lo mismo que exento o no gravado).

```python
# Alícuota 0% — caso poco frecuente pero válido
items = [
    {'importe_neto': 10000, 'alicuota_iva_id': 5},  # 21%
    {'importe_neto': 5000, 'alicuota_iva_id': 3},   # 0%
]

iva_detalle = build_iva_from_items(items)
# [
#     {'Id': 3, 'BaseImp': 5000.00, 'Importe': 0.00},   # 0%
#     {'Id': 5, 'BaseImp': 10000.00, 'Importe': 2100.00}, # 21%
# ]

# IMPORTANTE: la alícuota 0% se INCLUYE en el array AlicIva
# con Importe = 0. Su BaseImp contribuye a ImpNeto.
# Pero el Importe 0 no suma a ImpIVA.
```

---

## 6.4 Diagrama de Decisión Completo

Este diagrama resume todas las reglas de negocio que se aplican al construir un request:

```
Datos de entrada: tipo_cbte, neto, iva, total, condicion_iva_id, items[]
                                    │
                    ┌───────────────┴───────────────┐
                    │   1. NORMALIZAR IMPORTES       │
                    │                               │
                    │ ¿Clase C?                     │
                    │  SÍ → iva=0, total=neto       │
                    │                               │
                    │ ¿Clase B y iva=0 y total>0?   │
                    │  SÍ → iva=total/1.21*0.21     │
                    │       neto=total-iva           │
                    │                               │
                    │ ¿Clase A/M?                   │
                    │  → sin cambios                │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │  2. RESOLVER CONDICIÓN IVA     │
                    │                               │
                    │ ¿Clase B?                     │
                    │  SÍ → condicion = 5           │
                    │                               │
                    │ ¿Tiene ID guardado?            │
                    │  SÍ → usar ID                 │
                    │  NO → ¿Tiene nombre?           │
                    │       SÍ → resolver a ID      │
                    │       NO → ¿DNI/Otro?          │
                    │            SÍ → 5 (CF)        │
                    │            NO → consultar      │
                    │                   padrón       │
                    │                               │
                    │ ¿Aún None?                    │
                    │  SÍ → RECHAZAR factura         │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │   3. CALCULAR IVA DETALLE      │
                    │                               │
                    │ ¿Clase C?                     │
                    │  SÍ → NO incluir AlicIva       │
                    │                               │
                    │ ¿ImpIVA = 0?                  │
                    │  SÍ → NO incluir AlicIva       │
                    │                               │
                    │ ¿Tiene items con alícuota?     │
                    │  SÍ → agrupar por alícuota,   │
                    │       calcular, ajustar        │
                    │       redondeo                 │
                    │                               │
                    │ ¿Factura B sin desglose?       │
                    │  SÍ → usar neto/iva de factura │
                    │       con alícuota 5 (21%)     │
                    │                               │
                    │ ¿Sin items?                    │
                    │  SÍ → fallback: alícuota 5,   │
                    │       BaseImp=neto, Imp=iva    │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │   4. VALIDAR ECUACIÓN          │
                    │                               │
                    │ Total = Neto + IVA + Conc      │
                    │         + OpEx + Trib           │
                    │                               │
                    │ sum(AlicIva.Importe) = ImpIVA  │
                    │ sum(AlicIva.BaseImp) = ImpNeto │
                    │                               │
                    │ ¿Todo OK? → BUILD REQUEST      │
                    │ ¿Falla?   → RECHAZAR           │
                    └───────────────────────────────┘
```

---

## 6.5 Resumen de Errores ARCA Relacionados

| Error | Campo | Causa | Regla |
|-------|-------|-------|-------|
| `10242` | `CondicionIVAReceptorId` | Falta o valor inválido | RG 5616 |
| `10048` | Importes | `Total ≠ Neto + IVA + Conc + OpEx + Trib` | Ecuación importes |
| `10017` | `Iva.AlicIva` | `sum(AlicIva.Importe) ≠ ImpIVA` | Consistencia IVA |
| `10018` | `Iva.AlicIva` | `sum(AlicIva.BaseImp) ≠ ImpNeto` | Consistencia neto |
| `10015` | `DocNro` | CUIT inválido o formato incorrecto | Receptor |
| `10032` | `FchServ*` | Faltan fechas para concepto servicios | Servicios |
| `10013` | `CbteFch` | Fecha fuera de rango (±10 días) | Fecha emisión |
| `10025` | `CbtesAsoc` | NC/ND sin comprobante asociado | Notas |
| `10016` | `CbteHasta` | No es el próximo a autorizar | Secuencia |

---

## 6.6 Testing de Reglas de Negocio

```python
# Tests unitarios para validar las reglas antes de enviar a ARCA

def test_normalizacion_clase_c():
    neto, iva, total = normalizar_importes(11, 10000, 2100, 12100)
    assert iva == Decimal('0.00')
    assert total == neto
    assert total == Decimal('10000.00')

def test_normalizacion_clase_b_sin_iva():
    neto, iva, total = normalizar_importes(6, 0, 0, 12100)
    assert total == Decimal('12100.00')
    assert iva == Decimal('2100.00')
    assert neto == Decimal('10000.00')

def test_normalizacion_clase_b_con_iva():
    neto, iva, total = normalizar_importes(6, 10000, 2100, 12100)
    # Ya tiene IVA → no recalcular
    assert neto == Decimal('10000.00')
    assert iva == Decimal('2100.00')

def test_normalizacion_clase_a_sin_cambios():
    neto, iva, total = normalizar_importes(1, 10000, 2100, 12100)
    assert neto == Decimal('10000.00')
    assert iva == Decimal('2100.00')
    assert total == Decimal('12100.00')

def test_condicion_iva_clase_b_siempre_5():
    cond = resolver_condicion_para_wsfe(1, 6)   # RI + FC B
    assert cond == 5
    cond = resolver_condicion_para_wsfe(6, 7)   # Mono + ND B
    assert cond == 5

def test_condicion_iva_clase_a_respeta_real():
    cond = resolver_condicion_para_wsfe(1, 1)   # RI + FC A
    assert cond == 1
    cond = resolver_condicion_para_wsfe(4, 1)   # Exento + FC A
    assert cond == 4

def test_build_iva_multiples_alicuotas():
    items = [
        {'importe_neto': 5000, 'alicuota_iva_id': 5},
        {'importe_neto': 3000, 'alicuota_iva_id': 4},
    ]
    result = build_iva_from_items(items)
    assert len(result) == 2
    assert result[0]['Id'] == 4  # Ordenado por ID
    assert result[0]['BaseImp'] == Decimal('3000.00')
    assert result[0]['Importe'] == Decimal('315.00')  # 3000 * 10.5%
    assert result[1]['Id'] == 5
    assert result[1]['BaseImp'] == Decimal('5000.00')
    assert result[1]['Importe'] == Decimal('1050.00')  # 5000 * 21%

def test_ecuacion_importes():
    """Verifica que los importes cuadren después de normalizar."""
    neto, iva, total = normalizar_importes(6, 0, 0, 12100)
    assert abs(total - (neto + iva)) < Decimal('0.01')
```
