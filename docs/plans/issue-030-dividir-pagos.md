# Issue #30 -- Dividir Pagos (Split Payments)

| Campo | Valor |
|-------|-------|
| **Issue** | [#30](https://github.com/ferrerp/ferrerp/issues/30) |
| **Fecha** | 2026-04-05 |
| **Complejidad** | Alta |
| **Branch** | `feature/030-dividir-pagos` |
| **Afecta** | Modelos, Rutas, Servicios, Templates, Migraciones, Reportes |

---

## Indice

1. [Estado Actual](#1-estado-actual)
2. [Propuesta de Cambios](#2-propuesta-de-cambios)
3. [Edge Cases](#3-edge-cases)
4. [Impacto en Facturacion (ARCA)](#4-impacto-en-facturacion-arca)
5. [Lista Completa de Archivos](#5-lista-completa-de-archivos)
6. [Evaluacion de Riesgos](#6-evaluacion-de-riesgos)
7. [Decisiones de Diseno](#7-decisiones-de-diseno)
8. [Plan de Testing](#8-plan-de-testing)

---

## 1. Estado Actual

### 1.1 Modelo de Datos

#### `Venta` (`app/models/venta.py`)

- `forma_pago`: columna Enum PostgreSQL con valores: `efectivo`, `tarjeta_debito`, `tarjeta_credito`, `transferencia`, `qr`, `cuenta_corriente`
- Una venta tiene **exactamente una** forma de pago
- El `total` es un `Numeric(12,2)` que se asigna completo a esa forma de pago

#### `MovimientoCaja` (`app/models/caja.py`, linea 123-211)

- Cada venta genera **un** `MovimientoCaja` con `tipo='ingreso'`, `concepto='venta'`, `forma_pago=<la forma de la venta>`, `monto=<total de la venta>`
- La forma_pago del movimiento es un Enum separado (`forma_pago_movimiento`) que **NO** incluye `cuenta_corriente`
- Las ventas a `cuenta_corriente` **NO** generan movimiento de caja -- generan un `MovimientoCuentaCorriente`

#### `Caja` (`app/models/caja.py`, linea 10-121)

- `total_ingresos` y `total_egresos` se calculan filtrando movimientos por `forma_pago == 'efectivo'`
- `calcular_monto_esperado()` solo cuenta efectivo
- Los totales por forma de pago se calculan en las rutas de caja iterando movimientos

### 1.2 Flujo de Creacion de Venta (POS)

En `app/routes/ventas.py`, funcion `punto_de_venta()` (linea 39-229):

1. Se recibe `forma_pago` del form como string simple
2. Se crea la `Venta` con esa forma_pago
3. Segun forma_pago:
   - Si `cuenta_corriente`: valida cliente, limite de credito, crea `MovimientoCuentaCorriente`
   - Si cualquier otra: crea **un** `MovimientoCaja` con el total completo

### 1.3 Donde se muestra `forma_pago`

| Lugar | Archivo | Como se muestra |
|-------|---------|-----------------|
| POS (seleccion) | `punto_venta.html` L183-223 | 6 botones Alpine.js |
| Historial ventas | `historial.html` L81-94 | Badges por tipo con colores |
| Detalle venta | `detalle.html` L178-187 | Texto plano con if/elif |
| Ticket | `ticket.html` L249-262 | Texto plano con if/elif |
| PDF remito | `pdf/venta.html` L295 | `venta.forma_pago_display` |
| Caja index | `caja/index.html` L77-81 | `mov.forma_pago_display` |
| Caja detalle | `caja/detalle.html` | Idem |
| Reportes | `reportes.py` L103-135 | `GROUP BY Venta.forma_pago` |
| Export Excel | `reportes.py` L399 | `venta.forma_pago_display` |

---

## 2. Propuesta de Cambios

### 2.1 Decision de Diseno: Exactamente 2 metodos vs N metodos

**Soportar N metodos (con minimo 1, maximo 2 en UI por ahora)**

Se crea una tabla relacional `VentaPago` -- normalizado, extensible, queryable. El costo adicional vs "exactamente 2" es minimo y permite flexibilidad futura sin migraciones adicionales.

### 2.2 Modelo de Datos -- Cambios

#### Nueva tabla `VentaPago`

```python
# app/models/venta_pago.py (NUEVO)

class VentaPago(db.Model):
    __tablename__ = 'venta_pagos'

    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(
        db.Integer,
        db.ForeignKey('ventas.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    forma_pago = db.Column(
        db.Enum(
            'efectivo', 'tarjeta_debito', 'tarjeta_credito',
            'transferencia', 'qr', 'cuenta_corriente',
            name='forma_pago',
            create_type=False,
        ),
        nullable=False,
    )
    monto = db.Column(db.Numeric(12, 2), nullable=False)

    venta = db.relationship(
        'Venta',
        backref=db.backref('pagos', lazy='joined', cascade='all, delete-orphan'),
    )
```

#### Cambios en `Venta`

- **Mantener `forma_pago`** para retrocompatibilidad
- Agregar `'dividido'` como nuevo valor al enum `forma_pago`
- Ventas con pago simple: valor original en `forma_pago`. Ventas divididas: `'dividido'`

- **Actualizar property `forma_pago_display`**:
  - Si `forma_pago == 'dividido'`: iterar `self.pagos` y generar string tipo `"Efectivo + QR"`
  - Si no: comportamiento actual

#### Migracion

```python
# migrations/versions/0008_pago_dividido.py

def upgrade():
    # 1. Agregar 'dividido' al enum forma_pago
    op.execute("ALTER TYPE forma_pago ADD VALUE IF NOT EXISTS 'dividido'")

    # 2. Crear tabla venta_pagos
    op.create_table(
        'venta_pagos',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column(
            'venta_id',
            sa.Integer,
            sa.ForeignKey('ventas.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'forma_pago',
            sa.Enum(
                'efectivo', 'tarjeta_debito', 'tarjeta_credito',
                'transferencia', 'qr', 'cuenta_corriente',
                name='forma_pago',
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column('monto', sa.Numeric(12, 2), nullable=False),
    )

    # 3. Backfill: crear VentaPago para cada venta existente
    op.execute("""
        INSERT INTO venta_pagos (venta_id, forma_pago, monto)
        SELECT id, forma_pago, total FROM ventas WHERE estado = 'completada'
    """)


def downgrade():
    op.drop_table('venta_pagos')
```

**Nota importante sobre el backfill**: Este INSERT migra TODAS las ventas completadas existentes a la nueva tabla `venta_pagos`. Esto es critico para que los reportes funcionen de manera uniforme con la nueva query basada en `VentaPago`. Se debe hacer backup de la base de datos antes de ejecutar la migracion.

### 2.3 Cambios en Servicios / Rutas

#### `app/routes/ventas.py` -- `punto_de_venta()` POST

1. Se recibe `forma_pago` (puede ser `'dividido'`) y `pago_dividido_json` (campo hidden nuevo)
2. Validacion de pago dividido:
   - Parsear JSON: `[{"forma_pago": "efectivo", "monto": 100}, {"forma_pago": "qr", "monto": 100}]`
   - Verificar que la suma de montos == total de la venta
   - Verificar que las formas de pago sean distintas entre si
   - Verificar que cada monto > 0
   - Si incluye `cuenta_corriente`: validar cliente asignado y limite de credito por el monto parcial (no el total)
3. Crear `Venta` con `forma_pago='dividido'`
4. Crear N registros `VentaPago`
5. Para cada pago:
   - Si `cuenta_corriente`: crear `MovimientoCuentaCorriente` por el monto parcial
   - Si otra forma: crear `MovimientoCaja` por el monto parcial

#### `app/routes/ventas.py` -- `anular()`

Si `venta.forma_pago == 'dividido'`: iterar `venta.pagos` y para cada uno que sea `cuenta_corriente`, revertir el monto parcial en la cuenta corriente del cliente. Los movimientos de caja se manejan por la logica existente de anulacion (ya genera movimientos de egreso por cada ingreso).

#### `app/routes/caja.py`

Las queries de ventas a cuenta corriente deben incluir ventas divididas que tengan un componente de cuenta corriente:

```python
# Ventas CC puras (forma_pago directa)
ventas_cc_puras = Venta.query.filter_by(
    caja_id=caja.id,
    forma_pago='cuenta_corriente',
    estado='completada',
).all()

# Ventas divididas que incluyen un componente CC
ventas_divididas_cc = (
    Venta.query.join(VentaPago)
    .filter(
        Venta.caja_id == caja.id,
        Venta.forma_pago == 'dividido',
        Venta.estado == 'completada',
        VentaPago.forma_pago == 'cuenta_corriente',
    )
    .all()
)
```

Para los totales de cuenta corriente en la vista de caja, sumar los montos parciales de `VentaPago` en lugar del total de la venta.

#### `app/routes/reportes.py`

Cambiar la query de ventas por forma de pago para que use `VentaPago` en lugar de `Venta.forma_pago`:

```python
ventas_por_forma_pago_query = (
    db.session.query(
        VentaPago.forma_pago,
        func.sum(VentaPago.monto).label('total'),
        func.count(func.distinct(VentaPago.venta_id)).label('cantidad'),
    )
    .join(Venta)
    .filter(
        Venta.empresa_id == empresa_id,
        Venta.fecha >= inicio,
        Venta.fecha <= fin,
        Venta.estado == 'completada',
    )
    .group_by(VentaPago.forma_pago)
    .all()
)
```

**Beneficio**: Con este enfoque, una venta dividida "efectivo $5000 + QR $3000" aparece como $5000 en la fila de efectivo y $3000 en la fila de QR. No hay una categoria "dividido" en los reportes -- los montos se distribuyen correctamente.

### 2.4 Cambios en UI -- POS

#### Template `app/templates/ventas/punto_venta.html`

**Nuevo boton "Pago Dividido"**: 7mo boton en la grilla de metodos de pago, con icono Material Symbols `call_split`.

**Seccion condicional para pago dividido** (visible cuando `x-show="formaPago === 'dividido'"`):

- **Metodo 1**: select con las 6 formas de pago + input numerico para el monto
- **Metodo 2**: select con las 6 formas de pago + input numerico para el monto (auto-calculado como `total - monto1`)
- **Validacion visual**: indicador que muestra "Los montos suman correctamente" (verde) o "Los montos no coinciden con el total" (rojo)

**Alpine.js -- nuevas propiedades en el componente del POS:**

```javascript
pagoDividido1: { forma: 'efectivo', monto: '' },
pagoDividido2: { forma: 'qr', monto: '' },
```

**Computed `sumaValida`**: verifica que `Math.abs((parseFloat(monto1) + parseFloat(monto2)) - total) < 0.01`

**Metodo `calcularMonto2()`**: calcula automaticamente `monto2 = total - monto1` cada vez que cambia monto1, facilitando la carga rapida.

**Campo hidden en el form**: `pago_dividido_json` que se serializa al confirmar la venta con el JSON de los pagos.

**Validaciones en `confirmarVenta()`**:
- Verificar que `sumaValida` sea true
- Verificar que las formas de pago seleccionadas sean distintas
- Si alguna forma es `cuenta_corriente`, verificar que haya cliente seleccionado

**Persistencia**: incluir `pagoDividido1` y `pagoDividido2` en el estado del componente Alpine.js para que sobreviva a recargas parciales via HTMX.

**Campo de vuelto**: ocultar el campo de vuelto cuando `formaPago === 'dividido'` ya que los montos son exactos por definicion.

### 2.5 Cambios en Visualizacion

#### `Venta.forma_pago_display` (property en modelo)

Si `forma_pago == 'dividido'`:

```python
@property
def forma_pago_display(self):
    if self.forma_pago == 'dividido':
        return ' + '.join([p.forma_pago_display for p in self.pagos])
    # ... comportamiento existente
```

#### `VentaPago.forma_pago_display` (property en modelo nuevo)

Mismas opciones de display que `Venta` pero sin el valor `'dividido'`:

```python
@property
def forma_pago_display(self):
    opciones = {
        'efectivo': 'Efectivo',
        'tarjeta_debito': 'Tarjeta de Debito',
        'tarjeta_credito': 'Tarjeta de Credito',
        'transferencia': 'Transferencia',
        'qr': 'QR',
        'cuenta_corriente': 'Cuenta Corriente',
    }
    return opciones.get(self.forma_pago, self.forma_pago)
```

#### Detalle de venta (`detalle.html`)

Si `venta.forma_pago == 'dividido'`: mostrar cada pago en lineas separadas con forma + monto:

```
Forma de pago: Pago Dividido
  - Efectivo: $5.000,00
  - QR: $3.000,00
```

#### Historial (`historial.html`)

Agregar badge para `'dividido'` con color distintivo (por ejemplo, gradiente o bicolor) e icono `call_split`.

#### Ticket (`ticket.html`)

Si `venta.forma_pago == 'dividido'`: desglose por linea en la seccion de forma de pago del ticket termico:

```
FORMA DE PAGO:
  Efectivo      $5.000,00
  QR            $3.000,00
```

#### PDF remito (`pdf/venta.html`)

Ya usa `venta.forma_pago_display` que mostraria "Efectivo + QR". Opcionalmente agregar desglose con montos si el espacio del layout lo permite.

---

## 3. Edge Cases

| Caso | Comportamiento esperado |
|------|------------------------|
| Misma forma de pago seleccionada dos veces | Validar en backend Y frontend: las formas deben ser distintas. Mostrar error claro al usuario. |
| Montos no suman correctamente | Validar con tolerancia de centavos: `abs(sum - total) < 0.01`. Rechazar si no cumple. |
| `cuenta_corriente` + otra forma | Valido. Validar limite de credito solo por el monto parcial de CC, no por el total de la venta. |
| Anulacion de venta dividida | Iterar `venta.pagos`: revertir CC parcial + los movimientos de caja se reversan por logica existente. |
| Devolucion parcial en venta dividida | No afecta la logica de pagos -- la devolucion opera sobre productos/items, no sobre formas de pago. |
| Vuelto en pago dividido con efectivo | No aplica: los montos son exactos por definicion. Ocultar el campo de vuelto cuando `formaPago === 'dividido'`. |
| Presupuesto convertido a venta | El POS hereda el soporte de pago dividido automaticamente ya que la conversion pasa por el mismo flujo. |

---

## 4. Impacto en Facturacion (ARCA)

Sin impacto inmediato. La integracion con ARCA para facturacion electronica esta en desarrollo por separado. Cuando se implemente la facturacion ARCA completa, se decidira como mapear el pago dividido a los campos requeridos por AFIP.

**Esta feature NO bloquea la implementacion de ARCA y viceversa.**

---

## 5. Lista Completa de Archivos

### Archivos NUEVOS

| Archivo | Descripcion |
|---------|-------------|
| `app/models/venta_pago.py` | Modelo `VentaPago` con relacion a `Venta` |
| `migrations/versions/0008_pago_dividido.py` | Migracion: nueva tabla + enum `'dividido'` + backfill de datos existentes |

### Archivos a MODIFICAR

| Archivo | Que cambia |
|---------|-----------|
| `app/models/__init__.py` | Importar `VentaPago` para que SQLAlchemy lo registre |
| `app/models/venta.py` | Actualizar `forma_pago_display` para manejar `'dividido'`, agregar `'dividido'` al enum, actualizar `to_dict()` |
| `app/routes/ventas.py` | `punto_de_venta()` POST: parsear y validar pago dividido, crear N `VentaPago` + N movimientos. `anular()`: revertir pagos parciales CC |
| `app/routes/caja.py` | `index()` y `detalle()`: queries de CC deben incluir ventas divididas con componente CC. Sumar montos parciales. |
| `app/routes/reportes.py` | Query de ventas por forma de pago usa `VentaPago` en lugar de `Venta.forma_pago` |
| `app/templates/ventas/punto_venta.html` | Boton "Pago Dividido", seccion de montos con 2 selects + 2 inputs, logica Alpine.js, campo hidden `pago_dividido_json` |
| `app/templates/ventas/detalle.html` | Desglose de pagos parciales si `forma_pago == 'dividido'` |
| `app/templates/ventas/historial.html` | Badge para `'dividido'` con icono `call_split` |
| `app/templates/ventas/ticket.html` | Desglose de formas de pago por linea si dividido |
| `app/templates/ventas/pdf/venta.html` | Desglose opcional con montos (ya funciona basico via `forma_pago_display`) |
| `app/templates/caja/index.html` | Sin cambios directos si las queries en la ruta son correctas |

---

## 6. Evaluacion de Riesgos

### Riesgo ALTO

- **Migracion de datos historicos**: El `INSERT INTO venta_pagos` para ventas existentes es critico. Si falla, las ventas historicas no aparecen en reportes que usen la nueva query basada en `VentaPago`.
  - **Mitigacion**: Backup completo de la base de datos antes de ejecutar. Testear la migracion en un dump de datos reales antes de aplicar en produccion. Verificar conteo de registros post-migracion.

### Riesgo MEDIO

- **Queries de caja rotas**: Una venta dividida genera DOS `MovimientoCaja` (uno por cada forma de pago no-CC). Esto podria duplicar conteos si alguna query agrupa por `venta_id` asumiendo un solo movimiento.
  - **Mitigacion**: Verificar que `total_ingresos` y `calcular_monto_esperado()` solo filtran por forma de pago `'efectivo'` -- lo cual es correcto porque cada movimiento individual ya tiene el monto parcial correcto.

- **`cuenta_corriente` + pago dividido**: Validar el limite de credito solo por el monto parcial de CC, no por el total. Una validacion incorrecta podria rechazar ventas validas o permitir exceder el limite.
  - **Mitigacion**: Test especifico para este caso. Revisar todas las validaciones de limite de credito.

### Riesgo BAJO

- **Reportes**: El cambio de query es directo. Peor caso: `'dividido'` aparece como categoria propia en algun reporte que no se actualizo.
  - **Mitigacion**: Buscar TODOS los `GROUP BY` que usen `Venta.forma_pago`.

- **PDFs y tickets**: Solo afectan display. La property `forma_pago_display` cubre la mayoria de los casos automaticamente.

---

## 7. Decisiones de Diseno

| Decision | Opcion elegida | Alternativa descartada | Razon |
|----------|---------------|----------------------|-------|
| Almacenamiento de pagos | Tabla `venta_pagos` (relacional) | Columnas extra (`forma_pago_2`, `monto_2`) o campo JSON | Normalizado, extensible a N metodos, queryable con SQL estandar |
| Valor en `ventas.forma_pago` | `'dividido'` (nuevo valor en enum) | Null o valor calculado | Queries rapidos para filtrar ventas divididas, retrocompatible con codigo existente |
| UI de pago dividido | 7mo boton + seccion inline expandible | Modal separado | Mas fluido, menos clicks, coherente con el flujo actual del POS |
| Calculo de monto 2 | Auto-calculado (`total - monto1`) | Ambos montos manuales | Menos errores del operador, mas rapido en el dia a dia |
| Migracion de datos existentes | Backfill de `venta_pagos` para TODAS las ventas completadas | Solo crear registros para ventas nuevas | Reportes y queries uniformes -- no hay que mantener dos caminos de query |
| Soporte N metodos | Modelo soporta N, UI limita a 2 | Hardcoded a exactamente 2 | Costo cero extra en el modelo, flexibilidad futura sin nueva migracion |

---

## 8. Plan de Testing

### Tests unitarios

1. **Venta con pago simple**: Crear venta con forma de pago unica. Verificar que se crea 1 `VentaPago` + 1 `MovimientoCaja`.
2. **Venta dividida (efectivo + QR)**: Crear venta dividida. Verificar que se crean 2 `VentaPago` + 2 `MovimientoCaja` con montos parciales correctos.
3. **Pago dividido con CC + efectivo**: Crear venta dividida con cuenta corriente. Verificar que se crea 1 `MovimientoCaja` (efectivo) + 1 `MovimientoCuentaCorriente` (CC parcial).
4. **Validacion suma incorrecta**: Enviar montos que no suman el total. Debe rechazarse con error.
5. **Validacion misma forma repetida**: Enviar dos pagos con la misma forma de pago. Debe rechazarse con error.
6. **Anulacion de venta dividida**: Anular venta dividida con componente CC. Verificar que se revierte correctamente el monto parcial en la cuenta corriente.

### Tests de integracion

7. **Reportes con ventas simples y divididas**: Crear mix de ventas. Verificar que los totales por forma de pago son correctos (montos distribuidos, no agrupados como "dividido").
8. **Caja con ventas divididas**: Verificar que `calcular_monto_esperado()` refleja correctamente los montos parciales de efectivo.

### Tests de migracion

9. **Backfill en DB con datos existentes**: Ejecutar migracion sobre una base con ventas historicas. Verificar que el conteo de `venta_pagos` coincide con el de ventas completadas y que los montos son correctos.
