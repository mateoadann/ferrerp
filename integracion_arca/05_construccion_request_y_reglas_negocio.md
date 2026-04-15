# 5. Construcción del Request — FacturaBuilder y Reglas de Negocio

## 5.1 Visión General

El request para `FECAESolicitar` tiene una estructura compleja con múltiples campos obligatorios y condicionales. Para simplificar su construcción y garantizar validación temprana, se usa un **patrón Builder** que:

1. Acumula datos con métodos encadenables (`set_*`, `add_*`)
2. Valida reglas de negocio antes de construir el dict final
3. Aplica transformaciones automáticas (fechas a `YYYYMMDD`, Decimal a float)
4. Fuerza restricciones por clase de comprobante (IVA cero en clase C, condición 5 en clase B)

## 5.2 Estructura Final del FeCAEReq

El dict que produce `FacturaBuilder.build()` tiene esta forma exacta — es lo que `arca_arg` espera recibir:

```python
{
    'FeCAEReq': {
        'FeCabReq': {
            'CantReg': 1,           # Siempre 1 (un comprobante por request)
            'PtoVta': 1,            # Punto de venta (int)
            'CbteTipo': 6,          # Tipo de comprobante (int)
        },
        'FeDetReq': {
            'FECAEDetRequest': [
                {
                    'Concepto': 1,          # 1=Productos, 2=Servicios, 3=Ambos
                    'DocTipo': 80,           # Tipo doc receptor (80=CUIT, 96=DNI, etc.)
                    'DocNro': 20123456789,   # Número de documento (int, sin guiones)
                    'CbteDesde': 15,         # Número de comprobante (= CbteHasta)
                    'CbteHasta': 15,         # Número de comprobante (= CbteDesde)
                    'CbteFch': '20260309',   # Fecha emisión YYYYMMDD
                    'ImpTotal': 12100.00,    # Importe total (float)
                    'ImpTotConc': 0.00,      # Importes no gravados (float)
                    'ImpNeto': 10000.00,     # Importe neto gravado (float)
                    'ImpOpEx': 0.00,         # Importes exentos (float)
                    'ImpTrib': 0.00,         # Importes tributos (float)
                    'ImpIVA': 2100.00,       # Importe IVA (float)
                    'MonId': 'PES',          # Código moneda
                    'MonCotiz': 1.0,         # Cotización moneda

                    # Obligatorio (RG 5616)
                    'CondicionIVAReceptorId': 1,

                    # Solo si Concepto = 2 o 3 (Servicios)
                    'FchServDesde': '20260301',
                    'FchServHasta': '20260331',
                    'FchVtoPago': '20260415',

                    # Solo si tiene IVA y NO es clase C
                    'Iva': {
                        'AlicIva': [
                            {
                                'Id': 5,                # Alícuota (5=21%)
                                'BaseImp': 10000.00,     # Base imponible
                                'Importe': 2100.00,      # Monto IVA
                            }
                        ]
                    },

                    # Solo para NC/ND
                    'CbtesAsoc': {
                        'CbteAsoc': [
                            {
                                'Tipo': 1,      # Tipo del cbte original
                                'PtoVta': 1,    # PV del cbte original
                                'Nro': 10,      # Número del cbte original
                            }
                        ]
                    },
                }
            ]
        }
    }
}
```

### Campos del FeCabReq (Cabecera)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `CantReg` | int | Siempre `1`. Se envía un comprobante por request |
| `PtoVta` | int | Punto de venta del facturador (1-99999) |
| `CbteTipo` | int | Tipo de comprobante (1=FC A, 6=FC B, 11=FC C, etc.) |

### Campos del FECAEDetRequest (Detalle)

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `Concepto` | int | Siempre | 1=Productos, 2=Servicios, 3=Productos y Servicios |
| `DocTipo` | int | Siempre | Tipo documento receptor (80=CUIT, 96=DNI, 99=Otro) |
| `DocNro` | int | Siempre | Número de documento (sin guiones ni espacios) |
| `CbteDesde` | int | Siempre | Número de comprobante (= último autorizado + 1) |
| `CbteHasta` | int | Siempre | Igual a `CbteDesde` |
| `CbteFch` | str | Siempre | Fecha emisión formato `YYYYMMDD` |
| `ImpTotal` | float | Siempre | Total del comprobante |
| `ImpTotConc` | float | Siempre | Importes no gravados. Si no aplica: `0.0` |
| `ImpNeto` | float | Siempre | Importe neto gravado |
| `ImpOpEx` | float | Siempre | Importes exentos. Si no aplica: `0.0` |
| `ImpTrib` | float | Siempre | Tributos. Si no aplica: `0.0` |
| `ImpIVA` | float | Siempre | Total IVA. **Clase C: siempre `0.0`** |
| `MonId` | str | Siempre | Código moneda (`'PES'`, `'DOL'`, `'060'`=Euro) |
| `MonCotiz` | float | Siempre | Cotización. Pesos: `1.0` |
| `CondicionIVAReceptorId` | int | Siempre (RG 5616) | Condición IVA del receptor |
| `FchServDesde` | str | Servicios | Período servicio inicio `YYYYMMDD` |
| `FchServHasta` | str | Servicios | Período servicio fin `YYYYMMDD` |
| `FchVtoPago` | str | Servicios | Vencimiento pago `YYYYMMDD` |
| `Iva` | dict | Clase A/B/M | Detalle alícuotas IVA (no incluir en clase C) |
| `CbtesAsoc` | dict | NC/ND | Comprobante original asociado |

## 5.3 El FacturaBuilder — Implementación Completa

```python
from datetime import date
from decimal import Decimal
from typing import Optional, List


class FacturaBuilder:
    """
    Builder para construir requests de facturación para ARCA.

    Uso:
        request = (
            FacturaBuilder()
            .set_comprobante(tipo=6, punto_venta=1, numero=15, concepto=1)
            .set_fechas(emision=date(2026, 3, 9))
            .set_receptor(doc_tipo=96, doc_nro='12345678')
            .set_importes(total=12100, neto=10000, iva=2100)
            .set_condicion_iva_receptor(5)
            .add_iva(alicuota_id=5, base_imponible=10000, importe=2100)
            .build()
        )
    """

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

    # --- Métodos encadenables ---

    def set_comprobante(self, tipo: int, punto_venta: int,
                        numero: int, concepto: int) -> 'FacturaBuilder':
        """Configura tipo, punto de venta, número y concepto."""
        self._tipo_cbte = tipo
        self._punto_venta = punto_venta
        self._numero = numero
        self._concepto = concepto
        return self

    def set_fechas(self, emision: date, desde: Optional[date] = None,
                   hasta: Optional[date] = None,
                   vto_pago: Optional[date] = None) -> 'FacturaBuilder':
        """
        Configura fechas.
        - emision: siempre requerida
        - desde/hasta/vto_pago: obligatorias si concepto = 2 o 3 (servicios)
        """
        self._fecha_emision = emision
        self._fecha_desde = desde
        self._fecha_hasta = hasta
        self._fecha_vto_pago = vto_pago
        return self

    def set_receptor(self, doc_tipo: int, doc_nro: str) -> 'FacturaBuilder':
        """
        Configura receptor. Limpia el doc_nro (quita guiones y espacios).
        Lanza error si el documento no es numérico.
        """
        nro = str(doc_nro).replace('-', '').replace(' ', '')
        if not nro.isdigit():
            raise ArcaValidationError('Número de documento del receptor inválido')
        self._doc_tipo = doc_tipo
        self._doc_nro = int(nro)
        return self

    def set_importes(self, total: float, neto: float, iva: float = 0,
                     tributos: float = 0, no_gravado: float = 0,
                     exento: float = 0) -> 'FacturaBuilder':
        """Configura todos los importes. Convierte a Decimal internamente."""
        self._importe_total = Decimal(str(total))
        self._importe_neto = Decimal(str(neto))
        self._importe_iva = Decimal(str(iva))
        self._importe_tributos = Decimal(str(tributos))
        self._importe_no_gravado = Decimal(str(no_gravado))
        self._importe_exento = Decimal(str(exento))
        return self

    def set_moneda(self, moneda: str, cotizacion: float = 1) -> 'FacturaBuilder':
        """Configura moneda. Para pesos argentinos: 'PES' con cotización 1."""
        self._moneda = moneda
        self._cotizacion = Decimal(str(cotizacion))
        return self

    def add_iva(self, alicuota_id: int, base_imponible: float,
                importe: float) -> 'FacturaBuilder':
        """
        Agrega una alícuota IVA. Se puede llamar múltiples veces para
        comprobantes con distintas alícuotas.

        Alícuotas válidas:
          3 = 0%, 4 = 10.5%, 5 = 21%, 6 = 27%, 8 = 5%, 9 = 2.5%
        """
        self._alicuotas_iva.append({
            'Id': alicuota_id,
            'BaseImp': round(base_imponible, 2),
            'Importe': round(importe, 2)
        })
        return self

    def set_comprobante_asociado(self, tipo: int, punto_venta: int,
                                 numero: int) -> 'FacturaBuilder':
        """Comprobante original al que refiere una NC/ND."""
        self._cbte_asoc_tipo = tipo
        self._cbte_asoc_pto_vta = punto_venta
        self._cbte_asoc_nro = numero
        return self

    def set_condicion_iva_receptor(self, condicion_iva_id: int) -> 'FacturaBuilder':
        """
        RG 5616: obligatorio para TODAS las clases (A, B, C, M).
        Códigos comunes: 1=RI, 4=Exento, 5=CF, 6=Monotributo.
        """
        self._condicion_iva_receptor_id = int(condicion_iva_id)
        return self

    # --- Validación ---

    def validate(self) -> bool:
        """
        Valida campos requeridos y reglas de negocio.
        Lanza ArcaValidationError si algo falla.
        """
        # Campos obligatorios básicos
        if not self._tipo_cbte:
            raise ArcaValidationError('Tipo de comprobante es requerido')
        if not self._punto_venta:
            raise ArcaValidationError('Punto de venta es requerido')
        if not self._numero:
            raise ArcaValidationError('Número de comprobante es requerido')
        if not self._concepto:
            raise ArcaValidationError('Concepto es requerido')
        if not self._fecha_emision:
            raise ArcaValidationError('Fecha de emisión es requerida')
        if not self._doc_tipo:
            raise ArcaValidationError('Tipo de documento del receptor es requerido')
        if not self._doc_nro:
            raise ArcaValidationError('Número de documento del receptor es requerido')
        if self._importe_total is None:
            raise ArcaValidationError('Importe total es requerido')
        if self._importe_neto is None:
            raise ArcaValidationError('Importe neto es requerido')

        # REGLA: Servicios requieren fechas de período
        if self._concepto in (2, 3):  # Servicios o Productos y Servicios
            if not self._fecha_desde or not self._fecha_hasta or not self._fecha_vto_pago:
                raise ArcaValidationError(
                    'Para servicios se requieren fecha_desde, fecha_hasta y fecha_vto_pago'
                )

        # REGLA: NC/ND requieren comprobante asociado
        tipos_nota = {2, 3, 7, 8, 12, 13, 52, 53}
        if self._tipo_cbte in tipos_nota:
            if not (self._cbte_asoc_tipo and self._cbte_asoc_pto_vta and self._cbte_asoc_nro):
                raise ArcaValidationError(
                    'Para notas de crédito/débito se requiere comprobante asociado '
                    '(tipo, punto de venta y número)'
                )

        return True

    # --- Build ---

    def build(self) -> dict:
        """
        Construye el dict final para FECAESolicitar.
        Llama a validate() internamente.
        """
        self.validate()

        def format_date(d: date) -> str:
            return d.strftime('%Y%m%d')

        det_request = {
            'Concepto': self._concepto,
            'DocTipo': self._doc_tipo,
            'DocNro': self._doc_nro,
            'CbteDesde': self._numero,
            'CbteHasta': self._numero,
            'CbteFch': format_date(self._fecha_emision),
            'ImpTotal': float(self._importe_total),
            'ImpTotConc': float(self._importe_no_gravado),
            'ImpNeto': float(self._importe_neto),
            'ImpOpEx': float(self._importe_exento),
            'ImpTrib': float(self._importe_tributos),
            'ImpIVA': float(self._importe_iva),
            'MonId': self._moneda,
            'MonCotiz': float(self._cotizacion),
        }

        # REGLA: Clase C → IVA siempre 0
        TIPOS_COMPROBANTE_C = {11, 12, 13}
        if self._tipo_cbte in TIPOS_COMPROBANTE_C:
            det_request['ImpIVA'] = 0.0

        # Fechas de servicio (solo si se proporcionaron)
        if self._fecha_desde:
            det_request['FchServDesde'] = format_date(self._fecha_desde)
        if self._fecha_hasta:
            det_request['FchServHasta'] = format_date(self._fecha_hasta)
        if self._fecha_vto_pago:
            det_request['FchVtoPago'] = format_date(self._fecha_vto_pago)

        # Alícuotas IVA (no incluir en clase C)
        if self._alicuotas_iva and self._tipo_cbte not in TIPOS_COMPROBANTE_C:
            det_request['Iva'] = {'AlicIva': self._alicuotas_iva}

        # Comprobante asociado (para NC/ND)
        if self._cbte_asoc_tipo:
            det_request['CbtesAsoc'] = {
                'CbteAsoc': [{
                    'Tipo': self._cbte_asoc_tipo,
                    'PtoVta': self._cbte_asoc_pto_vta,
                    'Nro': self._cbte_asoc_nro,
                }]
            }

        # RG 5616: Condición IVA del receptor
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
        clase = TIPO_CBTE_CLASE.get(self._tipo_cbte)
        if self._condicion_iva_receptor_id is not None:
            condiciones_validas = CONDICIONES_IVA_POR_CLASE.get(clase, set())
            if self._condicion_iva_receptor_id not in condiciones_validas:
                raise ArcaValidationError(
                    f"Condición IVA {self._condicion_iva_receptor_id} no válida para "
                    f"comprobante clase {clase}. Valores permitidos: {condiciones_validas}"
                )
            det_request['CondicionIVAReceptorId'] = self._condicion_iva_receptor_id

        return {
            'FeCAEReq': {
                'FeCabReq': {
                    'CantReg': 1,
                    'PtoVta': self._punto_venta,
                    'CbteTipo': self._tipo_cbte,
                },
                'FeDetReq': {
                    'FECAEDetRequest': [det_request]
                }
            }
        }
```

## 5.4 Reglas de Negocio por Clase de Comprobante

### 5.4.1 Ecuación de Importes

ARCA valida que los importes cuadren. La ecuación fundamental es:

```
ImpTotal = ImpNeto + ImpIVA + ImpTotConc + ImpOpEx + ImpTrib
```

Si esta ecuación no se cumple, ARCA rechaza el comprobante con error `10048`.

### 5.4.2 Clase A (FC/ND/NC A — tipos 1, 2, 3)

**Contexto**: Emisor Responsable Inscripto → Receptor Responsable Inscripto.

- IVA **discriminado**: `ImpIVA` lleva el monto del IVA, `ImpNeto` es la base imponible
- El array `Iva.AlicIva` es **obligatorio** si `ImpIVA > 0`
- La suma de `AlicIva[].Importe` **debe coincidir** con `ImpIVA`
- La suma de `AlicIva[].BaseImp` **debe coincidir** con `ImpNeto`
- `CondicionIVAReceptorId`: la condición real del receptor (1=RI, 4=Exento, etc.)

```python
# Ejemplo: Factura A — $10.000 neto + 21% IVA
builder = (
    FacturaBuilder()
    .set_comprobante(tipo=1, punto_venta=1, numero=100, concepto=1)
    .set_fechas(emision=date.today())
    .set_receptor(doc_tipo=80, doc_nro='20301234567')
    .set_importes(total=12100, neto=10000, iva=2100)
    .set_condicion_iva_receptor(1)  # RI
    .add_iva(alicuota_id=5, base_imponible=10000, importe=2100)
    .build()
)
```

### 5.4.3 Clase B (FC/ND/NC B — tipos 6, 7, 8)

**Contexto**: Emisor Responsable Inscripto → Receptor Consumidor Final, Monotributo, Exento, etc.

**Regla especial — `CondicionIVAReceptorId` siempre 5**:

Aunque el receptor real sea Monotributo (6) o Exento (4), para comprobantes clase B **siempre se envía `CondicionIVAReceptorId = 5`** (Consumidor Final). Esto es una convención de ARCA: la clase B ya indica que el receptor no es RI, y ARCA espera el valor 5 para esta clase.

```python
# CORRECTO: siempre condición 5 para Factura B
if es_comprobante_tipo_b(tipo_comprobante):
    condicion_iva_receptor_id = 5
```

**IVA en Factura B — RG 5614 (Transparencia Fiscal)**:

Desde la RG 5614, ARCA requiere que las Facturas B **discriminen IVA** aunque el receptor no sea RI. El IVA está incluido en el total:

```python
from decimal import Decimal, ROUND_HALF_UP

def normalizar_importes_factura_b(importe_total: Decimal) -> tuple:
    """
    Para Factura B: el total INCLUYE IVA.
    Se desglosa el IVA (21%) desde el total.

    Fórmula:
        neto = total / 1.21
        iva = total - neto
    """
    iva = (importe_total / Decimal('1.21') * Decimal('0.21')).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )
    neto = importe_total - iva
    return neto, iva, importe_total

# Ejemplo: total $12.100
neto, iva, total = normalizar_importes_factura_b(Decimal('12100'))
# neto = 10000.00, iva = 2100.00, total = 12100.00
```

El array `Iva.AlicIva` **también es obligatorio** en clase B cuando `ImpIVA > 0`.

```python
# Ejemplo: Factura B — total $12.100 (IVA incluido)
total = Decimal('12100')
neto, iva, total = normalizar_importes_factura_b(total)

builder = (
    FacturaBuilder()
    .set_comprobante(tipo=6, punto_venta=1, numero=200, concepto=1)
    .set_fechas(emision=date.today())
    .set_receptor(doc_tipo=96, doc_nro='12345678')
    .set_importes(total=float(total), neto=float(neto), iva=float(iva))
    .set_condicion_iva_receptor(5)  # Siempre 5 para clase B
    .add_iva(alicuota_id=5, base_imponible=float(neto), importe=float(iva))
    .build()
)
```

### 5.4.4 Clase C (FC/ND/NC C — tipos 11, 12, 13)

**Contexto**: Emisor Monotributo → Cualquier receptor.

**Reglas críticas**:

1. `ImpIVA` **siempre `0.0`** — El Builder lo fuerza automáticamente
2. `ImpNeto` = `ImpTotal` — No hay IVA que separar
3. **NO incluir** el array `Iva.AlicIva` — El Builder lo omite automáticamente
4. `CondicionIVAReceptorId`: la condición real del receptor (obligatorio por RG 5616)

```python
# La normalización de importes para clase C:
def normalizar_importes_tipo_c(neto, iva, total):
    """Clase C: IVA = 0, Total = Neto"""
    return neto, Decimal('0.00'), neto  # total = neto

# Ejemplo: Factura C — $5.000
builder = (
    FacturaBuilder()
    .set_comprobante(tipo=11, punto_venta=1, numero=50, concepto=1)
    .set_fechas(emision=date.today())
    .set_receptor(doc_tipo=80, doc_nro='20301234567')
    .set_importes(total=5000, neto=5000, iva=0)
    .set_condicion_iva_receptor(1)  # La condición real del receptor
    # NO llamar a add_iva() — clase C no lleva IVA
    .build()
)
```

### 5.4.5 Resumen Visual por Clase

```
┌──────────┬────────────────────┬─────────────────┬──────────────┬──────────────┐
│  Clase   │ ImpIVA             │ Iva.AlicIva     │ CondIVARec   │ ImpNeto      │
├──────────┼────────────────────┼─────────────────┼──────────────┼──────────────┤
│ A (1,2,3)│ Monto real IVA     │ Obligatorio     │ Cond. real   │ Base sin IVA │
│ B (6,7,8)│ Calculado del total│ Obligatorio     │ Siempre 5    │ Total - IVA  │
│ C (11-13)│ Siempre 0.0        │ NO incluir      │ Cond. real   │ = ImpTotal   │
│ M (51-53)│ Monto real IVA     │ Obligatorio     │ Cond. real   │ Base sin IVA │
└──────────┴────────────────────┴─────────────────┴──────────────┴──────────────┘
```

## 5.5 Reglas de Negocio: Servicios (Concepto 2 y 3)

Cuando el concepto es **Servicios (2)** o **Productos y Servicios (3)**, se requieren tres campos adicionales:

```python
builder.set_fechas(
    emision=date(2026, 3, 9),
    desde=date(2026, 3, 1),      # Inicio del período
    hasta=date(2026, 3, 31),     # Fin del período
    vto_pago=date(2026, 4, 15),  # Vencimiento de pago
)
```

**Restricciones de ARCA**:
- `FchServDesde` ≤ `FchServHasta`
- `FchVtoPago` ≥ `CbteFch` (fecha emisión)
- Las tres fechas son **obligatorias** — si falta alguna, ARCA rechaza con error `10032`
- Para concepto **Productos (1)**, estos campos **no se envían**

## 5.6 Reglas de Negocio: Notas de Crédito y Débito

Las NC y ND requieren informar el comprobante original que modifican:

```python
# Tipos que son NC/ND (y requieren CbtesAsoc):
TIPOS_NOTA = {
    2,   # ND A
    3,   # NC A
    7,   # ND B
    8,   # NC B
    12,  # ND C
    13,  # NC C
    52,  # ND M
    53,  # NC M
}

# Ejemplo: NC A que anula la FC A nro 100 del PV 1
builder = (
    FacturaBuilder()
    .set_comprobante(tipo=3, punto_venta=1, numero=5, concepto=1)
    .set_fechas(emision=date.today())
    .set_receptor(doc_tipo=80, doc_nro='20301234567')
    .set_importes(total=12100, neto=10000, iva=2100)
    .set_condicion_iva_receptor(1)
    .add_iva(alicuota_id=5, base_imponible=10000, importe=2100)
    .set_comprobante_asociado(
        tipo=1,       # Tipo del original (FC A)
        punto_venta=1,
        numero=100
    )
    .build()
)
```

**Regla de correspondencia de clases**: El comprobante asociado debe ser de la misma clase:

```
NC A (3) → asociado a FC A (1) o ND A (2)
NC B (8) → asociado a FC B (6) o ND B (7)
NC C (13) → asociado a FC C (11) o ND C (12)
```

## 5.7 Cálculo de IVA desde Items

Cuando la factura tiene múltiples items con distintas alícuotas, se debe calcular el IVA agrupado por alícuota:

```python
from decimal import Decimal, ROUND_HALF_UP

# Alícuotas IVA de ARCA
ALICUOTAS_IVA = {
    3: {'porcentaje': 0, 'descripcion': '0%'},
    4: {'porcentaje': 10.5, 'descripcion': '10.5%'},
    5: {'porcentaje': 21, 'descripcion': '21%'},
    6: {'porcentaje': 27, 'descripcion': '27%'},
    8: {'porcentaje': 5, 'descripcion': '5%'},
    9: {'porcentaje': 2.5, 'descripcion': '2.5%'},
}


def build_iva_from_items(items: list[dict]) -> list[dict]:
    """
    Agrupa items por alícuota y calcula IVA.

    Cada item debe tener:
    - 'importe_neto': base imponible del item (float/Decimal)
    - 'alicuota_iva_id': código de alícuota (int, default 5=21%)

    Returns:
        Lista de dicts con 'Id', 'BaseImp', 'Importe' para AlicIva
    """
    # Paso 1: agrupar bases por alícuota
    bases_por_alicuota: dict[int, Decimal] = {}
    for item in items:
        alicuota_id = item.get('alicuota_iva_id', 5)  # default 21%
        if alicuota_id not in ALICUOTAS_IVA:
            continue
        base = Decimal(str(item['importe_neto']))
        bases_por_alicuota[alicuota_id] = bases_por_alicuota.get(
            alicuota_id, Decimal('0')
        ) + base

    if not bases_por_alicuota:
        return []

    # Paso 2: calcular IVA por alícuota
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

# --- Ejemplo con múltiples alícuotas ---

items = [
    {'importe_neto': 5000, 'alicuota_iva_id': 5},   # 21%
    {'importe_neto': 3000, 'alicuota_iva_id': 5},   # 21%
    {'importe_neto': 2000, 'alicuota_iva_id': 4},   # 10.5%
]

iva_detalle = build_iva_from_items(items)
# Resultado:
# [
#     {'Id': 4, 'BaseImp': 2000.00, 'Importe': 210.00},   # 10.5%
#     {'Id': 5, 'BaseImp': 8000.00, 'Importe': 1680.00},  # 21%
# ]

# Calcular totales
imp_neto = sum(a['BaseImp'] for a in iva_detalle)    # 10000.00
imp_iva = sum(a['Importe'] for a in iva_detalle)      # 1890.00
imp_total = imp_neto + imp_iva                         # 11890.00

# Construir factura
builder = (
    FacturaBuilder()
    .set_comprobante(tipo=1, punto_venta=1, numero=101, concepto=1)
    .set_fechas(emision=date.today())
    .set_receptor(doc_tipo=80, doc_nro='20301234567')
    .set_importes(total=float(imp_total), neto=float(imp_neto), iva=float(imp_iva))
    .set_condicion_iva_receptor(1)
)
for alicuota in iva_detalle:
    builder.add_iva(
        alicuota_id=alicuota['Id'],
        base_imponible=float(alicuota['BaseImp']),
        importe=float(alicuota['Importe']),
    )

request = builder.build()
```

### Ajuste de Redondeo

Cuando hay múltiples alícuotas, la suma de los IVA calculados puede diferir del IVA total informado por centavos de redondeo. Se ajusta el último item:

```python
def ajustar_redondeo_iva(iva_detalle: list[dict], iva_total_factura: Decimal) -> None:
    """
    Ajusta el último AlicIva para que la suma coincida exactamente
    con el IVA total informado en la factura.
    """
    total_calculado = sum(
        Decimal(str(a['Importe'])) for a in iva_detalle
    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    diff = (iva_total_factura - total_calculado).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )

    if diff != Decimal('0') and iva_detalle:
        iva_detalle[-1]['Importe'] = (
            Decimal(str(iva_detalle[-1]['Importe'])) + diff
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
```

## 5.8 Normalización de Importes — Función Completa

Esta función centraliza la normalización de importes según la clase de comprobante:

```python
from decimal import Decimal, ROUND_HALF_UP

# Sets de tipos de comprobante por clase
TIPOS_COMPROBANTE_C = {11, 12, 13}
TIPO_CBTE_CLASE = {
    1: 'A', 2: 'A', 3: 'A',
    6: 'B', 7: 'B', 8: 'B',
    11: 'C', 12: 'C', 13: 'C',
    51: 'M', 52: 'M', 53: 'M',
}


def normalizar_importes_para_tipo(
    tipo_comprobante: int,
    importe_neto,
    importe_iva,
    importe_total,
) -> tuple[Decimal, Decimal, Decimal]:
    """
    Normaliza importes según la clase de comprobante.

    - Clase C: IVA = 0, Total = Neto
    - Clase B: si IVA = 0 y total > 0, calcula IVA desde total (21%)
    - Clase A/M: sin modificación

    Returns:
        (neto, iva, total) como Decimal
    """
    neto = Decimal(str(importe_neto or 0)).quantize(Decimal('0.01'))
    iva = Decimal(str(importe_iva or 0)).quantize(Decimal('0.01'))
    total = Decimal(str(importe_total or 0)).quantize(Decimal('0.01'))

    # Clase C: sin IVA
    if int(tipo_comprobante) in TIPOS_COMPROBANTE_C:
        iva = Decimal('0.00')
        total = neto

    # Clase B: calcular IVA si no viene informado (RG 5614)
    if TIPO_CBTE_CLASE.get(int(tipo_comprobante)) == 'B':
        if iva == Decimal('0.00') and total > 0:
            iva = (total / Decimal('1.21') * Decimal('0.21')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            neto = total - iva

    return neto, iva, total
```

## 5.9 Resolución de CondicionIVAReceptorId

La `CondicionIVAReceptorId` es **obligatoria** para todas las clases desde la RG 5616. La resolución sigue esta prioridad:

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


def resolver_condicion_iva_receptor(
    condicion_iva_id: int | None,
    condicion_iva_nombre: str | None,
    doc_tipo: int,
    tipo_comprobante: int,
) -> int | None:
    """
    Resuelve la CondicionIVAReceptorId para el request WSFE.

    Prioridad de resolución:
    1. ID directo (si el receptor tiene condicion_iva_id guardado)
    2. Nombre → ID (busca en el diccionario CONDICIONES_IVA)
    3. Fallback por tipo de documento (DNI/Otro → Consumidor Final)
    4. None (debe autocompletarse desde padrón ARCA)

    Regla especial:
    - Clase B: siempre retorna 5 (Consumidor Final)
    """
    # Regla especial para clase B
    TIPO_CBTE_CLASE = {
        1: 'A', 2: 'A', 3: 'A',
        6: 'B', 7: 'B', 8: 'B',
        11: 'C', 12: 'C', 13: 'C',
        51: 'M', 52: 'M', 53: 'M',
    }
    if TIPO_CBTE_CLASE.get(tipo_comprobante) == 'B':
        return 5  # Siempre Consumidor Final para clase B

    # Prioridad 1: ID directo
    if condicion_iva_id is not None:
        return condicion_iva_id

    # Prioridad 2: resolver desde nombre
    if condicion_iva_nombre:
        nombre_norm = ' '.join(condicion_iva_nombre.lower().split())
        for cond_id, desc in CONDICIONES_IVA.items():
            if ' '.join(desc.lower().split()) == nombre_norm:
                return cond_id

    # Prioridad 3: fallback por tipo documento
    if doc_tipo in (96, 99):   # DNI o Doc. (Otro)
        return 5  # Consumidor Final

    if doc_tipo in (80, 86, 87):  # CUIT, CUIL, CDI
        return None  # No inferir — consultar padrón

    return 5  # Default: Consumidor Final
```

### Autocompletado desde Padrón ARCA

Si no se tiene la condición IVA del receptor, se puede consultar el padrón de ARCA:

```python
def autocompletar_condicion_iva_desde_padron(
    client,  # ArcaClient
    doc_nro: str,
    doc_tipo: int,
) -> int | None:
    """
    Consulta el padrón de ARCA para obtener la condición IVA.
    Solo funciona con CUIT/CUIL/CDI de 11 dígitos.

    Returns:
        ID de condición IVA, o None si no se pudo obtener
    """
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
        condicion_iva = data.get('condicion_iva')  # Nombre (str)
        if condicion_iva:
            nombre_norm = ' '.join(condicion_iva.lower().split())
            for cond_id, desc in CONDICIONES_IVA.items():
                if ' '.join(desc.lower().split()) == nombre_norm:
                    return cond_id

        return None
    except Exception:
        return None  # Si el padrón falla, no bloquear la operación
```

## 5.10 Obtención del Número de Comprobante

Antes de construir el request, **siempre** se debe consultar el último número autorizado e incrementar en 1:

```python
def obtener_proximo_numero(client, punto_venta: int, tipo_cbte: int) -> int:
    """
    Obtiene el próximo número de comprobante.

    IMPORTANTE: Llamar lo más cerca posible del FECAESolicitar
    para minimizar el riesgo de colisión en concurrencia.

    Errores comunes:
    - Error 10016: "El campo CbteHasta no es el próximo a autorizar"
      → Otro proceso emitió un comprobante entre la consulta y el envío
      → Reintentar consultando el nuevo último número
    """
    ultimo = client.fe_comp_ultimo_autorizado(
        punto_venta=punto_venta,
        tipo_cbte=tipo_cbte
    )
    return ultimo + 1
```

## 5.11 Flujo Completo de Construcción

```python
from datetime import date
from decimal import Decimal

# --- Flujo para una factura cualquiera ---

def construir_y_enviar_factura(
    client,            # ArcaClient conectado
    tipo_cbte: int,
    punto_venta: int,
    concepto: int,
    doc_tipo: int,
    doc_nro: str,
    importe_total: float,
    importe_neto: float,
    importe_iva: float = 0,
    items: list = None,            # Lista de items con alicuota_iva_id y importe_neto
    condicion_iva_id: int = None,  # ID de condición IVA del receptor
    fecha_emision: date = None,
    fecha_desde: date = None,
    fecha_hasta: date = None,
    fecha_vto_pago: date = None,
    cbte_asoc_tipo: int = None,
    cbte_asoc_pto_vta: int = None,
    cbte_asoc_nro: int = None,
    moneda: str = 'PES',
    cotizacion: float = 1.0,
) -> dict:
    """
    Construye request, normaliza importes, y envía a ARCA.

    Returns:
        dict con 'success', 'cae', 'cae_vencimiento', 'numero_comprobante'
        o 'success': False con 'error_code' y 'error_message'
    """
    from arca_integration.builders import FacturaBuilder
    from arca_integration.services import WSFEService

    if fecha_emision is None:
        fecha_emision = date.today()

    # Paso 1: Normalizar importes según clase
    neto, iva, total = normalizar_importes_para_tipo(
        tipo_cbte, importe_neto, importe_iva, importe_total
    )

    # Paso 2: Resolver condición IVA
    if condicion_iva_id is None:
        condicion_iva_id = autocompletar_condicion_iva_desde_padron(
            client, doc_nro, doc_tipo
        )
    # Override para clase B
    TIPO_CBTE_CLASE = {1:'A',2:'A',3:'A',6:'B',7:'B',8:'B',11:'C',12:'C',13:'C',51:'M',52:'M',53:'M'}
    if TIPO_CBTE_CLASE.get(tipo_cbte) == 'B':
        condicion_iva_id = 5

    if condicion_iva_id is None:
        return {
            'success': False,
            'error_code': 'condicion_iva_faltante',
            'error_message': f'No se pudo determinar la condicion IVA del receptor {doc_nro}',
        }

    # Paso 3: Obtener próximo número
    numero = obtener_proximo_numero(client, punto_venta, tipo_cbte)

    # Paso 4: Construir request
    builder = (
        FacturaBuilder()
        .set_comprobante(tipo=tipo_cbte, punto_venta=punto_venta,
                         numero=numero, concepto=concepto)
        .set_fechas(emision=fecha_emision, desde=fecha_desde,
                    hasta=fecha_hasta, vto_pago=fecha_vto_pago)
        .set_receptor(doc_tipo=doc_tipo, doc_nro=doc_nro)
        .set_importes(
            total=float(total), neto=float(neto), iva=float(iva)
        )
        .set_moneda(moneda=moneda, cotizacion=cotizacion)
        .set_condicion_iva_receptor(condicion_iva_id)
    )

    # Paso 5: Agregar IVA (si aplica)
    TIPOS_COMPROBANTE_C = {11, 12, 13}
    if tipo_cbte not in TIPOS_COMPROBANTE_C and iva > Decimal('0'):
        if items:
            iva_detalle = build_iva_from_items(items)
            ajustar_redondeo_iva(iva_detalle, iva)
            for alicuota in iva_detalle:
                builder.add_iva(
                    alicuota_id=alicuota['Id'],
                    base_imponible=float(alicuota['BaseImp']),
                    importe=float(alicuota['Importe']),
                )
        else:
            # Sin items: asumir 21%
            builder.add_iva(
                alicuota_id=5,
                base_imponible=float(neto),
                importe=float(iva)
            )

    # Paso 6: Comprobante asociado (NC/ND)
    if cbte_asoc_tipo:
        builder.set_comprobante_asociado(
            tipo=cbte_asoc_tipo,
            punto_venta=cbte_asoc_pto_vta,
            numero=cbte_asoc_nro,
        )

    # Paso 7: Build y enviar
    request_data = builder.build()

    wsfe = WSFEService(client)
    response = wsfe.autorizar(request_data)

    if response.get('cae'):
        return {
            'success': True,
            'cae': response['cae'],
            'cae_vencimiento': response['cae_vencimiento'],
            'numero_comprobante': numero,
        }
    else:
        return {
            'success': False,
            'error_code': response.get('error_code'),
            'error_message': response.get('error_message', 'Error desconocido'),
        }
```

## 5.12 Errores Comunes en la Construcción del Request

| Error ARCA | Causa | Solución |
|------------|-------|----------|
| `10048` | Importes no cuadran (`Total ≠ Neto + IVA + ...`) | Verificar ecuación de importes |
| `10016` | `CbteHasta` no es el próximo a autorizar | Consultar `FECompUltimoAutorizado` otra vez y reintentar |
| `10032` | Faltan fechas de servicio | Agregar `FchServDesde`, `FchServHasta`, `FchVtoPago` |
| `10242` | `CondicionIVAReceptorId` inválida o faltante | Verificar RG 5616, usar ID correcto para la clase |
| `10013` | Fecha de comprobante fuera de rango permitido | Fecha debe ser ±10 días de la fecha actual |
| `10015` | `DocTipo`/`DocNro` inconsistente | CUIT inválido o tipo documento incorrecto |
| `10025` | NC/ND sin comprobante asociado | Agregar `CbtesAsoc` con tipo, PV y número del original |
| `10026` | Comprobante asociado no existe | Verificar que la FC original esté autorizada en ARCA |
| `10017` | Alícuotas IVA no coinciden con importes | `sum(AlicIva.Importe)` debe = `ImpIVA` |

## 5.13 Checklist de Validación Pre-envío

```python
def validar_request_antes_de_enviar(request_data: dict) -> list[str]:
    """Retorna lista de errores encontrados (vacía = OK)."""
    errores = []
    det = request_data['FeCAEReq']['FeDetReq']['FECAEDetRequest'][0]
    cab = request_data['FeCAEReq']['FeCabReq']

    # 1. Ecuación de importes
    total = det['ImpTotal']
    suma = det['ImpNeto'] + det['ImpIVA'] + det['ImpTotConc'] + det['ImpOpEx'] + det['ImpTrib']
    if abs(total - suma) > 0.01:
        errores.append(
            f'Importes no cuadran: Total={total}, Suma={suma}'
        )

    # 2. CbteDesde = CbteHasta
    if det['CbteDesde'] != det['CbteHasta']:
        errores.append('CbteDesde debe ser igual a CbteHasta')

    # 3. Clase C sin IVA
    if cab['CbteTipo'] in (11, 12, 13):
        if det['ImpIVA'] != 0.0:
            errores.append('Clase C: ImpIVA debe ser 0')
        if 'Iva' in det:
            errores.append('Clase C: no debe incluir Iva.AlicIva')

    # 4. IVA consistente con AlicIva
    if 'Iva' in det:
        suma_iva = sum(a['Importe'] for a in det['Iva']['AlicIva'])
        if abs(det['ImpIVA'] - suma_iva) > 0.01:
            errores.append(
                f'IVA inconsistente: ImpIVA={det["ImpIVA"]}, suma AlicIva={suma_iva}'
            )

    # 5. Servicios requieren fechas
    if det['Concepto'] in (2, 3):
        for campo in ('FchServDesde', 'FchServHasta', 'FchVtoPago'):
            if campo not in det:
                errores.append(f'Servicios requieren {campo}')

    # 6. NC/ND requieren CbtesAsoc
    tipos_nota = {2, 3, 7, 8, 12, 13, 52, 53}
    if cab['CbteTipo'] in tipos_nota and 'CbtesAsoc' not in det:
        errores.append('NC/ND requieren CbtesAsoc')

    # 7. CondicionIVAReceptorId presente
    if 'CondicionIVAReceptorId' not in det:
        errores.append('Falta CondicionIVAReceptorId (RG 5616)')

    return errores
```
