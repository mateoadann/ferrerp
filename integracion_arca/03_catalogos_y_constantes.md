# 03 — Catálogos y Constantes de ARCA (WSFE)

> **Audiencia:** Referencia completa de todos los códigos, tipos y constantes que usa el Web Service de Factura Electrónica (WSFE) de ARCA. Cada valor listado aquí es un código numérico o string que ARCA espera en las requests y devuelve en las responses.

---

## Índice

1. [Tipos de Comprobante (CbteTipo)](#1-tipos-de-comprobante-cbtetipo)
2. [Clases de Comprobante (A, B, C, M)](#2-clases-de-comprobante-a-b-c-m)
3. [Tipos de Concepto (Concepto)](#3-tipos-de-concepto-concepto)
4. [Tipos de Documento (DocTipo)](#4-tipos-de-documento-doctipo)
5. [Alícuotas de IVA (Id en AlicIva)](#5-alícuotas-de-iva-id-en-aliciva)
6. [Condiciones frente al IVA (CondicionIVAReceptorId)](#6-condiciones-frente-al-iva-condicionivarereceptorid)
7. [Monedas (MonId)](#7-monedas-monid)
8. [Formato de Fechas](#8-formato-de-fechas)
9. [Resultados de operaciones](#9-resultados-de-operaciones)
10. [Implementación en código](#10-implementación-en-código)
11. [Consulta dinámica de catálogos via WSFE](#11-consulta-dinámica-de-catálogos-via-wsfe)

---

## 1. Tipos de Comprobante (CbteTipo)

El campo `CbteTipo` identifica el tipo de comprobante electrónico. Se usa en la cabecera del request (`FeCabReq.CbteTipo`) y en consultas.

### Comprobantes soportados

| Código | Descripción | Clase | Uso típico |
|--------|-------------|-------|------------|
| `1` | Factura A | A | Venta entre Responsables Inscriptos |
| `2` | Nota de Débito A | A | Ajuste a favor del emisor (sobre FC A) |
| `3` | Nota de Crédito A | A | Anulación o ajuste a favor del receptor (sobre FC A) |
| `6` | Factura B | B | Venta a Consumidor Final, Monotributista, Exento |
| `7` | Nota de Débito B | B | Ajuste a favor del emisor (sobre FC B) |
| `8` | Nota de Crédito B | B | Anulación o ajuste a favor del receptor (sobre FC B) |
| `11` | Factura C | C | Venta por Monotributista a cualquier receptor |
| `12` | Nota de Débito C | C | Ajuste a favor del emisor (sobre FC C) |
| `13` | Nota de Crédito C | C | Anulación o ajuste a favor del receptor (sobre FC C) |
| `51` | Factura M | M | Responsable Inscripto nuevo (sujeto a retención) |
| `52` | Nota de Débito M | M | Ajuste sobre FC M |
| `53` | Nota de Crédito M | M | Anulación o ajuste sobre FC M |

### Notas de Crédito y Débito

Las Notas de Crédito (NC) y Notas de Débito (ND) **requieren comprobante asociado** — es decir, deben referenciar la factura original que están modificando. Los tipos que requieren comprobante asociado son:

```python
TIPOS_QUE_REQUIEREN_CBTE_ASOCIADO = {2, 3, 7, 8, 12, 13, 52, 53}
```

---

## 2. Clases de Comprobante (A, B, C, M)

Los comprobantes se agrupan en **clases** que determinan reglas fiscales, de IVA y de receptor válido.

### Mapeo tipo → clase

```python
TIPO_CBTE_CLASE = {
    1: 'A',    2: 'A',    3: 'A',     # Factura/ND/NC A
    6: 'B',    7: 'B',    8: 'B',     # Factura/ND/NC B
    11: 'C',   12: 'C',   13: 'C',    # Factura/ND/NC C
    51: 'M',   52: 'M',   53: 'M',    # Factura/ND/NC M
}
```

### Sets por clase (para validaciones rápidas)

```python
TIPOS_COMPROBANTE_A = {1, 2, 3}
TIPOS_COMPROBANTE_B = {6, 7, 8}
TIPOS_COMPROBANTE_C = {11, 12, 13}
TIPOS_COMPROBANTE_M = {51, 52, 53}
```

### Reglas por clase

#### Clase A — Responsable Inscripto a Responsable Inscripto

| Aspecto | Regla |
|---------|-------|
| **Emisor** | IVA Responsable Inscripto |
| **Receptor** | IVA Responsable Inscripto |
| **IVA** | Se **discrimina** (ImpIVA > 0, array `Iva.AlicIva` obligatorio) |
| **ImpNeto** | Base imponible (sin IVA) |
| **ImpTotal** | ImpNeto + ImpIVA + ImpTrib + ImpOpEx + ImpTotConc |

#### Clase B — Responsable Inscripto a Consumidor Final / Monotributo / Exento

| Aspecto | Regla |
|---------|-------|
| **Emisor** | IVA Responsable Inscripto |
| **Receptor** | Consumidor Final, Monotributista, Exento, etc. |
| **IVA** | Se **discrimina** (RG 5614 — Transparencia Fiscal). ImpIVA debe informarse |
| **ImpNeto** | Base imponible (neto sin IVA) |
| **ImpTotal** | Total con IVA incluido (ImpNeto + ImpIVA) |
| **CondicionIVAReceptorId** | Siempre usar `5` (Consumidor Final), sin importar la condición real del receptor |

> **Nota sobre Factura B:** Históricamente el IVA no se discriminaba en FC B. Desde la **RG 5614 (Transparencia Fiscal)**, el IVA sí se informa. Si los items vienen sin IVA desglosado, se calcula automáticamente: `IVA = Total / 1.21 * 0.21` y `Neto = Total - IVA`.

#### Clase C — Monotributista a cualquier receptor

| Aspecto | Regla |
|---------|-------|
| **Emisor** | Responsable Monotributo |
| **Receptor** | Cualquier condición IVA |
| **IVA** | **NO se discrimina** nunca. `ImpIVA = 0`, NO enviar array `Iva.AlicIva` |
| **ImpNeto** | Igual al importe total |
| **ImpTotal** | Igual a ImpNeto (no hay discriminación) |

#### Clase M — Responsable Inscripto nuevo (régimen especial)

| Aspecto | Regla |
|---------|-------|
| **Emisor** | IVA Responsable Inscripto (nuevo, sujeto a retención) |
| **Receptor** | Similar a clase A |
| **IVA** | Se discrimina (igual que clase A) |

### Normalización de importes por clase

```python
from decimal import Decimal, ROUND_HALF_UP

def normalizar_importes(tipo_comprobante, importe_neto, importe_iva, importe_total):
    """
    Normaliza importes según la clase de comprobante.

    Returns:
        (neto, iva, total) normalizados como Decimal
    """
    neto = Decimal(str(importe_neto or 0)).quantize(Decimal('0.01'))
    iva = Decimal(str(importe_iva or 0)).quantize(Decimal('0.01'))
    total = Decimal(str(importe_total or 0)).quantize(Decimal('0.01'))

    # Clase C: nunca discriminar IVA
    if tipo_comprobante in {11, 12, 13}:  # TIPOS_COMPROBANTE_C
        iva = Decimal('0.00')
        total = neto

    # Clase B: siempre discriminar IVA (RG 5614)
    if tipo_comprobante in {6, 7, 8}:  # TIPOS_COMPROBANTE_B
        if iva == Decimal('0.00') and total > 0:
            iva = (total / Decimal('1.21') * Decimal('0.21')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            neto = total - iva

    return neto, iva, total
```

---

## 3. Tipos de Concepto (Concepto)

El campo `Concepto` en el detalle del comprobante indica la naturaleza de lo facturado.

| Código | Descripción | Campos adicionales requeridos |
|--------|-------------|------------------------------|
| `1` | Productos | Ninguno |
| `2` | Servicios | `FchServDesde`, `FchServHasta`, `FchVtoPago` |
| `3` | Productos y Servicios | `FchServDesde`, `FchServHasta`, `FchVtoPago` |

### Regla de fechas para servicios

Cuando `Concepto` es `2` (Servicios) o `3` (Productos y Servicios), ARCA **exige** tres campos de fecha adicionales en el detalle del comprobante:

| Campo | Formato | Descripción |
|-------|---------|-------------|
| `FchServDesde` | `YYYYMMDD` | Fecha de inicio del período de servicio |
| `FchServHasta` | `YYYYMMDD` | Fecha de fin del período de servicio |
| `FchVtoPago` | `YYYYMMDD` | Fecha de vencimiento del pago |

**Si `Concepto` es `1` (Productos), estos campos NO deben enviarse** (o pueden ser `None`).

```python
# Validación
if concepto in (2, 3):
    if not fecha_desde or not fecha_hasta or not fecha_vto_pago:
        raise ValueError(
            'Para servicios (concepto 2 o 3) se requieren '
            'fecha_desde, fecha_hasta y fecha_vto_pago'
        )
```

---

## 4. Tipos de Documento (DocTipo)

El campo `DocTipo` identifica el tipo de documento del receptor del comprobante.

| Código | Descripción | Uso típico |
|--------|-------------|------------|
| `80` | CUIT | Responsable Inscripto, empresas |
| `86` | CUIL | Personas físicas en relación de dependencia |
| `87` | CDI | Clave de Identificación |
| `89` | LE | Libreta de Enrolamiento |
| `90` | LC | Libreta Cívica |
| `91` | CI Extranjera | Cédula de identidad extranjera |
| `92` | En trámite | Documento en trámite |
| `93` | Acta Nacimiento | Acta de nacimiento |
| `95` | CI Bs. As. RNP | Cédula Bs. As. Registro Nacional de las Personas |
| `96` | DNI | Documento Nacional de Identidad |
| `99` | Doc. (Otro) | Consumidor Final sin identificar |
| `0` | CI Policía Federal | Cédula Policía Federal |

### Casos especiales

#### Consumidor Final sin identificar

Para ventas a consumidor final donde no se identifica al comprador:
```python
doc_tipo = 99
doc_nro = 0    # Número 0 para consumidor final genérico
```

#### CUIT (el más común para Factura A)

```python
doc_tipo = 80
doc_nro = 20123456789   # CUIT como entero, sin guiones
```

### Relación DocTipo → Condición IVA (inferencia)

Si no se conoce la condición IVA del receptor, se puede inferir parcialmente del tipo de documento:

| DocTipo | Inferencia posible |
|---------|--------------------|
| `96` (DNI) | Consumidor Final (condición IVA `5`) |
| `99` (Otro) | Consumidor Final (condición IVA `5`) |
| `80` (CUIT) | **No inferir** — puede ser RI, Monotributo, Exento, etc. Consultar padrón |
| `86` (CUIL) | **No inferir** — consultar padrón si es necesario |
| `87` (CDI) | **No inferir** — consultar padrón si es necesario |

---

## 5. Alícuotas de IVA (Id en AlicIva)

El campo `Id` dentro del array `Iva.AlicIva` identifica la alícuota de IVA aplicada.

| Código (`Id`) | Porcentaje | Descripción |
|---------------|-----------|-------------|
| `3` | 0% | IVA 0% |
| `4` | 10.5% | IVA 10.5% |
| `5` | 21% | IVA 21% (alícuota general, la más común) |
| `6` | 27% | IVA 27% |
| `8` | 5% | IVA 5% |
| `9` | 2.5% | IVA 2.5% |

### Estructura del array AlicIva

Cada elemento del array tiene tres campos:

```python
{
    'Id': 5,              # Código de alícuota (ver tabla arriba)
    'BaseImp': 10000.00,  # Base imponible (monto sobre el que se calcula el IVA)
    'Importe': 2100.00,   # Importe de IVA resultante (BaseImp * porcentaje / 100)
}
```

### Reglas sobre el array de IVA

1. **Factura A:** Obligatorio si `ImpIVA > 0`. Debe contener al menos un elemento
2. **Factura B:** Obligatorio si `ImpIVA > 0` (desde RG 5614)
3. **Factura C:** **NO enviar**. El campo `Iva` debe ser `None` o no estar presente
4. **Consistencia:** La suma de todos los `Importe` del array debe coincidir con `ImpIVA` del comprobante
5. **Consistencia:** La suma de todos los `BaseImp` del array debe coincidir con `ImpNeto` del comprobante

### Múltiples alícuotas en un mismo comprobante

Un comprobante puede tener items con diferentes alícuotas. En ese caso, se agrupan por alícuota:

```python
# Ejemplo: factura con items al 21% e items al 10.5%
iva_array = [
    {'Id': 4, 'BaseImp': 5000.00, 'Importe': 525.00},   # 10.5% sobre $5000
    {'Id': 5, 'BaseImp': 10000.00, 'Importe': 2100.00},  # 21% sobre $10000
]

# ImpNeto del comprobante = 5000 + 10000 = 15000
# ImpIVA del comprobante = 525 + 2100 = 2625
# ImpTotal = 15000 + 2625 = 17625
```

### Cálculo de IVA desde items

```python
from decimal import Decimal, ROUND_HALF_UP

ALICUOTAS_IVA = {
    3: {'porcentaje': 0, 'descripcion': '0%'},
    4: {'porcentaje': 10.5, 'descripcion': '10.5%'},
    5: {'porcentaje': 21, 'descripcion': '21%'},
    6: {'porcentaje': 27, 'descripcion': '27%'},
    8: {'porcentaje': 5, 'descripcion': '5%'},
    9: {'porcentaje': 2.5, 'descripcion': '2.5%'},
}

def calcular_iva_por_alicuota(items):
    """
    Agrupa items por alícuota y calcula el IVA total por cada una.

    Args:
        items: Lista de dicts con 'alicuota_iva_id' y 'importe_neto'

    Returns:
        Lista de dicts con 'Id', 'BaseImp', 'Importe' para ARCA
    """
    bases_por_alicuota = {}

    for item in items:
        alicuota_id = item.get('alicuota_iva_id', 5)  # Default: 21%
        if alicuota_id not in ALICUOTAS_IVA:
            continue

        base = Decimal(str(item['importe_neto']))
        bases_por_alicuota[alicuota_id] = (
            bases_por_alicuota.get(alicuota_id, Decimal('0')) + base
        )

    resultado = []
    for alicuota_id in sorted(bases_por_alicuota.keys()):
        base = bases_por_alicuota[alicuota_id].quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        porcentaje = Decimal(str(ALICUOTAS_IVA[alicuota_id]['porcentaje']))
        importe = (base * porcentaje / Decimal('100')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        resultado.append({
            'Id': alicuota_id,
            'BaseImp': float(base),
            'Importe': float(importe),
        })

    return resultado
```

### Ajuste de redondeo

Cuando se calculan IVA desde items individuales, puede haber diferencias de centavos por redondeo. Se recomienda ajustar el último elemento del array para que la suma coincida con el `ImpIVA` total del comprobante:

```python
def ajustar_redondeo_iva(iva_array, imp_iva_total):
    """
    Ajusta el último elemento del array IVA para que la suma
    coincida con el ImpIVA informado en el comprobante.
    """
    if not iva_array:
        return iva_array

    total_calculado = sum(Decimal(str(item['Importe'])) for item in iva_array)
    total_factura = Decimal(str(imp_iva_total)).quantize(Decimal('0.01'))
    diff = total_factura - total_calculado.quantize(Decimal('0.01'))

    if diff != Decimal('0'):
        iva_array[-1]['Importe'] = float(
            (Decimal(str(iva_array[-1]['Importe'])) + diff).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        )

    return iva_array
```

---

## 6. Condiciones frente al IVA (CondicionIVAReceptorId)

El campo `CondicionIVAReceptorId` en el detalle del comprobante indica la condición fiscal del receptor. Es **obligatorio** desde la **RG 5616** para todas las clases de comprobante (A, B, C, M).

### Catálogo de condiciones

| Código | Descripción |
|--------|-------------|
| `1` | IVA Responsable Inscripto |
| `4` | IVA Sujeto Exento |
| `5` | Consumidor Final |
| `6` | Responsable Monotributo |
| `7` | Sujeto No Categorizado |
| `8` | Proveedor del Exterior |
| `9` | Cliente del Exterior |
| `10` | IVA Liberado — Ley N.o 19.640 |
| `11` | IVA Responsable Inscripto — Agente de Percepción |
| `13` | Monotributista Social |
| `15` | IVA No Alcanzado |
| `16` | Monotributo Trabajador Independiente Promovido |

### Condiciones válidas por clase de comprobante

Todos los códigos son válidos para todas las clases (A, B, C, M):

```python
CONDICIONES_IVA_POR_CLASE = {
    'A': {1, 4, 5, 6, 7, 8, 9, 10, 13, 15, 16},
    'B': {1, 4, 5, 6, 7, 8, 9, 10, 13, 15, 16},
    'C': {1, 4, 5, 6, 7, 8, 9, 10, 13, 15, 16},
    'M': {1, 4, 5, 6, 7, 8, 9, 10, 13, 15, 16},
}
```

### Reglas de negocio sobre CondicionIVAReceptorId

1. **Es obligatorio** para todas las clases (A, B, C, M) desde RG 5616
2. **Factura B:** Siempre enviar `5` (Consumidor Final), sin importar la condición real del receptor. ARCA lo exige así para clase B
3. **Resolución del valor:** Se puede obtener de:
   - Base de datos (si el receptor ya tiene la condición registrada)
   - Consulta al padrón de ARCA (`ws_sr_constancia_inscripcion`)
   - Inferencia por tipo de documento (DNI/Otro → Consumidor Final)

### Resolución de CondicionIVAReceptorId (algoritmo recomendado)

```python
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

def resolver_condicion_iva_receptor(receptor, tipo_comprobante):
    """
    Resuelve el CondicionIVAReceptorId para el request a ARCA.

    Args:
        receptor: Objeto/dict con doc_tipo, doc_nro, condicion_iva_id
        tipo_comprobante: Código de tipo de comprobante (1, 6, 11, etc.)

    Returns:
        int — Código de condición IVA para ARCA, o None si no se pudo resolver
    """
    # Para Factura B: siempre Consumidor Final
    if tipo_comprobante in {6, 7, 8}:  # Clase B
        return 5

    # Prioridad 1: ID guardado directamente
    condicion_id = getattr(receptor, 'condicion_iva_id', None)
    if condicion_id is not None and condicion_id in CONDICIONES_IVA:
        return condicion_id

    # Prioridad 2: Resolver desde nombre (si se guardó como string)
    condicion_nombre = getattr(receptor, 'condicion_iva', None)
    if condicion_nombre:
        nombre_norm = condicion_nombre.strip().lower()
        for cid, desc in CONDICIONES_IVA.items():
            if desc.lower() == nombre_norm:
                return cid

    # Prioridad 3: Inferir por tipo de documento
    doc_tipo = getattr(receptor, 'doc_tipo', None)
    if doc_tipo in (96, 99):  # DNI o Doc. Otro
        return 5  # Consumidor Final

    # Para CUIT/CUIL/CDI: no inferir, consultar padrón
    return None
```

### Autocompletado desde padrón de ARCA

Si no se conoce la condición IVA del receptor y tiene CUIT, se puede consultar el padrón:

```python
def autocompletar_condicion_iva(client, receptor):
    """
    Consulta el padrón de ARCA para completar la condición IVA del receptor.

    Args:
        client: Instancia de ArcaClient conectada
        receptor: Objeto con doc_tipo y doc_nro
    """
    # Solo para CUIT/CUIL/CDI con 11 dígitos
    if receptor.doc_tipo not in (80, 86, 87):
        return

    cuit = str(receptor.doc_nro).replace('-', '').replace(' ', '')
    if not cuit.isdigit() or len(cuit) != 11:
        return

    try:
        result = client.consultar_padron(cuit)
        if not result.get('success'):
            return

        data = result.get('data', {})
        condicion_iva = data.get('condicion_iva')

        if condicion_iva == 'IVA Responsable Inscripto':
            receptor.condicion_iva_id = 1
        elif condicion_iva == 'Responsable Monotributo':
            receptor.condicion_iva_id = 6
        # ... mapear otros valores

    except Exception:
        pass  # Si falla, se sigue con lo que tenga el receptor
```

---

## 7. Monedas (MonId)

El campo `MonId` identifica la moneda del comprobante y `MonCotiz` su cotización respecto al peso argentino.

### Monedas soportadas

| Código (`MonId`) | Descripción | `MonCotiz` |
|------------------|-------------|------------|
| `'PES'` | Pesos Argentinos | `1` (siempre) |
| `'DOL'` | Dólar Estadounidense | Cotización del día |
| `'012'` | Real Brasileño | Cotización del día |
| `'014'` | Corona Danesa | Cotización del día |
| `'019'` | Yen Japonés | Cotización del día |
| `'021'` | Libra Esterlina | Cotización del día |
| `'060'` | Euro | Cotización del día |

### Reglas

1. **MonId default:** `'PES'` (Pesos Argentinos)
2. **MonCotiz para pesos:** Siempre `1` (no se permite otro valor)
3. **MonCotiz para moneda extranjera:** Debe ser la cotización oficial del día. Se puede consultar via WSFE con el método `FEParamGetCotizacion`
4. **Importes en moneda extranjera:** Todos los importes (`ImpTotal`, `ImpNeto`, `ImpIVA`, etc.) se expresan en la moneda indicada por `MonId`, y ARCA convierte internamente usando `MonCotiz`

### Consulta de cotización via WSFE

```python
auth = construir_auth(ws)

result = ws.send_request('FEParamGetCotizacion', {
    'Auth': auth,
    'MonId': 'DOL',  # Código de moneda a consultar
})

cotizacion = result.ResultGet.MonCotiz
fecha = result.ResultGet.FchCotiz
print(f'Cotización USD: {cotizacion} (fecha: {fecha})')
```

---

## 8. Formato de Fechas

**Todas las fechas en ARCA usan formato `YYYYMMDD` como string.**

| Ejemplo | Significado |
|---------|-------------|
| `'20250124'` | 24 de enero de 2025 |
| `'20261231'` | 31 de diciembre de 2026 |

### Conversión en Python

```python
from datetime import date

def fecha_a_arca(d: date) -> str:
    """Convierte date de Python a formato ARCA (YYYYMMDD)."""
    return d.strftime('%Y%m%d')

def arca_a_fecha(s: str) -> date:
    """Convierte formato ARCA (YYYYMMDD) a date de Python."""
    from datetime import datetime
    return datetime.strptime(s, '%Y%m%d').date()

# Ejemplos
fecha_a_arca(date(2025, 1, 24))    # → '20250124'
arca_a_fecha('20250124')            # → date(2025, 1, 24)
```

### Campos de fecha en el request

| Campo | Descripción | Obligatorio |
|-------|-------------|-------------|
| `CbteFch` | Fecha de emisión del comprobante | Siempre |
| `FchServDesde` | Fecha inicio del servicio | Solo si Concepto = 2 o 3 |
| `FchServHasta` | Fecha fin del servicio | Solo si Concepto = 2 o 3 |
| `FchVtoPago` | Fecha vencimiento del pago | Solo si Concepto = 2 o 3 |

### Campos de fecha en la respuesta

| Campo | Descripción |
|-------|-------------|
| `CbteFch` | Fecha del comprobante (en `ResultGet` de `FECompConsultar`) |
| `CAEFchVto` | Fecha de vencimiento del CAE |
| `FchProceso` | Fecha/hora de procesamiento por ARCA |

---

## 9. Resultados de operaciones

### Resultado de FECAESolicitar

El campo `Resultado` indica si el comprobante fue aprobado o rechazado:

| Valor | Significado |
|-------|-------------|
| `'A'` | **Aprobado** — El comprobante fue autorizado y se emitió CAE |
| `'R'` | **Rechazado** — El comprobante fue rechazado. Ver `Observaciones` y `Errors` para el motivo |
| `'P'` | **Parcial** — En lotes de múltiples comprobantes, algunos aprobados y otros rechazados |

### Campo Reproceso

| Valor | Significado |
|-------|-------------|
| `'S'` | Es un reproceso — el comprobante ya había sido autorizado previamente |
| `'N'` | No es un reproceso — primera autorización |

> **Reproceso:** Si se envía un comprobante con los mismos datos que uno ya autorizado, ARCA no lo rechaza sino que devuelve el CAE original con `Reproceso = 'S'`. Esto permite recuperar CAE de comprobantes cuya respuesta se perdió.

### Estructura de errores

```python
# Observaciones (dentro del detalle del comprobante)
# Pueden existir incluso si el comprobante fue Aprobado
{
    'Code': 10016,
    'Msg': 'El campo CbteDesde no es el siguiente a autorizar...'
}

# Errores globales (fuera del detalle)
{
    'Code': 600,
    'Msg': 'No se encontró...'
}
```

---

## 10. Implementación en código

### Diccionario completo de constantes (copiar y usar)

```python
# === TIPOS DE COMPROBANTE ===
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

# === MAPEO TIPO → CLASE ===
TIPO_CBTE_CLASE = {
    1: 'A', 2: 'A', 3: 'A',
    6: 'B', 7: 'B', 8: 'B',
    11: 'C', 12: 'C', 13: 'C',
    51: 'M', 52: 'M', 53: 'M',
}

# === SETS POR CLASE ===
TIPOS_COMPROBANTE_A = {1, 2, 3}
TIPOS_COMPROBANTE_B = {6, 7, 8}
TIPOS_COMPROBANTE_C = {11, 12, 13}
TIPOS_COMPROBANTE_M = {51, 52, 53}

# === TIPOS QUE REQUIEREN COMPROBANTE ASOCIADO ===
TIPOS_CON_CBTE_ASOCIADO = {2, 3, 7, 8, 12, 13, 52, 53}

# === TIPOS DE CONCEPTO ===
TIPOS_CONCEPTO = {
    1: 'Productos',
    2: 'Servicios',
    3: 'Productos y Servicios',
}

# === TIPOS DE DOCUMENTO ===
TIPOS_DOCUMENTO = {
    80: 'CUIT',
    86: 'CUIL',
    87: 'CDI',
    89: 'LE',
    90: 'LC',
    91: 'CI Extranjera',
    92: 'en trámite',
    93: 'Acta Nacimiento',
    95: 'CI Bs. As. RNP',
    96: 'DNI',
    99: 'Doc. (Otro)',
    0: 'CI Policía Federal',
}

# === ALÍCUOTAS DE IVA ===
ALICUOTAS_IVA = {
    3: {'porcentaje': 0, 'descripcion': '0%'},
    4: {'porcentaje': 10.5, 'descripcion': '10.5%'},
    5: {'porcentaje': 21, 'descripcion': '21%'},
    6: {'porcentaje': 27, 'descripcion': '27%'},
    8: {'porcentaje': 5, 'descripcion': '5%'},
    9: {'porcentaje': 2.5, 'descripcion': '2.5%'},
}

# === CONDICIONES DE IVA ===
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

# === CONDICIONES VÁLIDAS POR CLASE ===
CONDICIONES_IVA_POR_CLASE = {
    'A': {1, 4, 5, 6, 7, 8, 9, 10, 13, 15, 16},
    'B': {1, 4, 5, 6, 7, 8, 9, 10, 13, 15, 16},
    'C': {1, 4, 5, 6, 7, 8, 9, 10, 13, 15, 16},
    'M': {1, 4, 5, 6, 7, 8, 9, 10, 13, 15, 16},
}

# === MONEDAS ===
MONEDAS = {
    'PES': {'codigo': 'PES', 'descripcion': 'Pesos Argentinos'},
    'DOL': {'codigo': 'DOL', 'descripcion': 'Dólar Estadounidense'},
    '012': {'codigo': '012', 'descripcion': 'Real'},
    '014': {'codigo': '014', 'descripcion': 'Corona Danesa'},
    '019': {'codigo': '019', 'descripcion': 'Yenes'},
    '021': {'codigo': '021', 'descripcion': 'Libra Esterlina'},
    '060': {'codigo': '060', 'descripcion': 'Euro'},
}
```

---

## 11. Consulta dinámica de catálogos via WSFE

ARCA expone métodos para consultar los catálogos vigentes de forma dinámica. Esto es útil para verificar que los códigos hardcodeados sigan siendo válidos:

### Métodos de consulta de parámetros

```python
auth = construir_auth(ws)

# Tipos de comprobante vigentes
result = ws.send_request('FEParamGetTiposCbte', {'Auth': auth})
for tipo in result.ResultGet.CbteTipo:
    print(f'{tipo.Id}: {tipo.Desc} (desde {tipo.FchDesde} hasta {tipo.FchHasta})')

# Tipos de concepto
result = ws.send_request('FEParamGetTiposConcepto', {'Auth': auth})
for concepto in result.ResultGet.ConceptoTipo:
    print(f'{concepto.Id}: {concepto.Desc}')

# Tipos de documento
result = ws.send_request('FEParamGetTiposDoc', {'Auth': auth})
for doc in result.ResultGet.DocTipo:
    print(f'{doc.Id}: {doc.Desc}')

# Alícuotas de IVA
result = ws.send_request('FEParamGetTiposIva', {'Auth': auth})
for iva in result.ResultGet.IvaTipo:
    print(f'{iva.Id}: {iva.Desc}')

# Monedas
result = ws.send_request('FEParamGetTiposMonedas', {'Auth': auth})
for moneda in result.ResultGet.Moneda:
    print(f'{moneda.Id}: {moneda.Desc}')

# Puntos de venta habilitados
result = ws.send_request('FEParamGetPtosVenta', {'Auth': auth})
for pv in result.ResultGet.PtoVta:
    print(f'PV {pv.Nro}: bloqueado={pv.Bloqueado} baja={pv.FchBaja}')

# Condiciones IVA del receptor (RG 5616)
result = ws.send_request('FEParamGetCondicionIvaReceptor', {'Auth': auth})
# Retorna las condiciones válidas para el tipo de contribuyente del CUIT

# Cotización de moneda
result = ws.send_request('FEParamGetCotizacion', {'Auth': auth, 'MonId': 'DOL'})
print(f'Cotización USD: {result.ResultGet.MonCotiz}')

# Estado del servicio (health check)
result = ws.send_request('FEDummy', {})
print(f'AppServer: {result.AppServer}')
print(f'DbServer: {result.DbServer}')
print(f'AuthServer: {result.AuthServer}')
```

> **Nota:** `FEDummy` no requiere `Auth` — es el único método que no necesita autenticación. Es útil para verificar si el servicio de ARCA está operativo.
