# Issue #35 — Descuentos Unitarios por Producto

| Campo             | Valor                                                        |
| ----------------- | ------------------------------------------------------------ |
| **Issue**         | [#35](https://github.com/ferrerp/ferrerp/issues/35)         |
| **Fecha**         | 2026-04-05                                                   |
| **Complejidad**   | Media-Alta                                                   |
| **Módulos**       | Ventas, Presupuestos, PDFs, Reportes                        |
| **Tipo de cambio**| Feature — nueva funcionalidad sobre estructura existente     |

---

## Tabla de Contenidos

1. [Estado Actual](#1-estado-actual)
2. [Cambios Propuestos](#2-cambios-propuestos)
3. [Casos Borde](#3-casos-borde)
4. [Lista Completa de Archivos a Modificar](#4-lista-completa-de-archivos-a-modificar)
5. [Evaluación de Riesgo](#5-evaluación-de-riesgo)
6. [Plan de Testing](#6-plan-de-testing)

---

## 1. Estado Actual

### 1.1 Modelos de Datos

#### Venta (`app/models/venta.py`)

| Columna               | Tipo          | Descripción                                       |
| --------------------- | ------------- | ------------------------------------------------- |
| `subtotal`            | Numeric(12,2) | Suma de todos los `detalle.subtotal`               |
| `descuento_porcentaje`| Numeric(5,2)  | Porcentaje **GLOBAL** de descuento                 |
| `descuento_monto`     | Numeric(12,2) | Monto calculado del descuento global               |
| `total`               | Numeric(12,2) | `subtotal - descuento_monto`                       |

#### VentaDetalle (`app/models/venta_detalle.py`)

| Columna            | Tipo          | Descripción                                         |
| ------------------ | ------------- | --------------------------------------------------- |
| `cantidad`         | Numeric(12,3) | Cantidad vendida                                     |
| `precio_unitario`  | Numeric(12,2) | Precio por unidad                                    |
| `iva_porcentaje`   | Numeric(5,2)  | Porcentaje de IVA aplicable                          |
| `subtotal`         | Numeric(12,2) | `cantidad * precio_unitario` (sin descuento por linea) |

#### Presupuesto (`app/models/presupuesto.py`)

Misma estructura que `Venta`: `subtotal`, `descuento_porcentaje`, `descuento_monto`, `total`.

#### PresupuestoDetalle (`app/models/presupuesto.py`, lineas 156-202)

Misma estructura que `VentaDetalle`. **No posee descuento por linea.**

---

### 1.2 Logica de Calculo — Server Side

#### Ruta `punto_de_venta` POST (`app/routes/ventas.py`, lineas 93-146)

```python
item_subtotal = cantidad * precio
subtotal += item_subtotal
venta.subtotal = subtotal
if descuento_porcentaje > 0:
    venta.descuento_monto = subtotal * (descuento_porcentaje / 100)
venta.total = subtotal - venta.descuento_monto
```

El descuento se aplica **unicamente a nivel global** sobre el subtotal completo de la venta.

#### Servicio `crear_presupuesto` (`app/services/presupuesto_service.py`, lineas 25-79)

Mismo patron: calculo de subtotal por item sin descuento unitario, descuento global sobre la suma.

#### Servicio `convertir_a_venta` (`app/services/presupuesto_service.py`, lineas 153-289)

Copia `descuento_porcentaje` del presupuesto a la venta. No existe campo de descuento por detalle para copiar.

---

### 1.3 Logica de Calculo — Client Side (JavaScript / Alpine.js)

#### POS (`app/templates/ventas/punto_venta.html`, lineas 293-303)

```javascript
get subtotal() {
    return this.cart.reduce((sum, item) => sum + (item.cantidad * item.precio_unitario), 0);
},
get descuentoMonto() {
    return this.subtotal * (this.descuentoPorcentaje / 100);
},
get total() {
    return this.subtotal - this.descuentoMonto;
},
```

#### IVA agrupado (lineas 307-333)

El descuento global se distribuye **proporcionalmente** entre items para calcular IVA. Usa:

```javascript
proporcion = itemSubtotal / this.subtotal
```

#### Presupuesto (`app/templates/presupuestos/crear.html`, lineas 275-288)

Mismo patron de calculo que el POS.

---

### 1.4 PDFs y Vistas de Detalle

Estructura actual de la tabla de items en PDFs y vistas:

| Codigo | Descripcion | Cant. | P.Unit. | Subtotal |
| ------ | ----------- | ----- | ------- | -------- |

Seccion de totales:

- Subtotal
- Descuento (X%)
- Neto gravado
- IVA
- **TOTAL**

**No hay columna de descuento por linea en ninguna tabla.**

---

### 1.5 Datos del Carrito Enviados al Backend

JSON en hidden input `items_json`:

```json
{
    "producto_id": 1,
    "codigo": "TAL-1020",
    "nombre": "Taladro WD 1020",
    "cantidad": 2,
    "precio_unitario": 4333.00,
    "iva_porcentaje": 21.00,
    "stock_disponible": 15
}
```

**No hay campo `descuento_porcentaje` por item.**

---

## 2. Cambios Propuestos

### 2.1 Migracion de Base de Datos

**Archivo**: `migrations/versions/0008_descuento_unitario_detalle.py` (NUEVO)

#### Tabla `venta_detalles`

Agregar columna:

| Columna               | Tipo          | Default | Nullable |
| --------------------- | ------------- | ------- | -------- |
| `descuento_porcentaje`| Numeric(5,2)  | `0`     | NOT NULL |

#### Tabla `presupuesto_detalles`

Agregar columna:

| Columna               | Tipo          | Default | Nullable |
| --------------------- | ------------- | ------- | -------- |
| `descuento_porcentaje`| Numeric(5,2)  | `0`     | NOT NULL |

> `server_default='0'` asegura retrocompatibilidad: todas las filas existentes tendran descuento 0%, lo que mantiene el comportamiento historico intacto.

---

### 2.2 Cambios en Modelos

#### `app/models/venta_detalle.py` — clase `VentaDetalle`

**1. Nueva columna:**

```python
descuento_porcentaje = db.Column(db.Numeric(5, 2), nullable=False, server_default='0', default=0)
```

**2. Modificar `calcular_subtotal()`:**

```python
def calcular_subtotal(self):
    bruto = Decimal(str(self.cantidad)) * Decimal(str(self.precio_unitario))
    descuento = bruto * (Decimal(str(self.descuento_porcentaje)) / Decimal('100'))
    self.subtotal = bruto - descuento
    return self.subtotal
```

**3. Agregar a `to_dict()`:**

Incluir `descuento_porcentaje` en el diccionario de salida para que este disponible en las vistas y APIs que consumen este metodo.

#### `app/models/presupuesto.py` — clase `PresupuestoDetalle`

Mismos tres cambios: nueva columna, `calcular_subtotal()` actualizado, `to_dict()` actualizado.

#### Modelos padre: `Venta.calcular_totales()` y `Presupuesto.calcular_totales()`

**No necesitan cambios.** Ya usan `sum(detalle.subtotal)` para calcular el subtotal de la venta/presupuesto, y el subtotal de cada detalle ya incluira el descuento unitario tras los cambios anteriores.

---

### 2.3 Regla de Apilamiento de Descuentos (Stacking)

Se adopta el modelo **SECUENCIAL (multiplicativo)**:

1. **Primero** se aplica el descuento **UNITARIO** por item:
   ```
   subtotal_item = cantidad * precio_unitario * (1 - descuento_item / 100)
   ```

2. **Luego** se aplica el descuento **GLOBAL** sobre la suma de subtotales:
   ```
   total = SUM(subtotals) * (1 - descuento_global / 100)
   ```

#### Ejemplo practico

| Producto        | Precio   | Cant. | Desc. Unit. | Subtotal Item |
| --------------- | -------- | ----- | ----------- | ------------- |
| Taladro WD 1020 | $4,333.00| 1     | 10%         | $3,899.70     |
| Cricket 1/2     | $500.00  | 1     | 0%          | $500.00       |

- **Subtotal:** $4,399.70
- **Descuento global 5%:** $219.99
- **Total:** $4,179.72

> El descuento unitario reduce el precio antes de que el descuento global se aplique. Esto es intuitivo para el usuario: "le hago 10% a este producto, y ademas 5% a toda la compra".

---

### 2.4 Cambios en Rutas

#### `app/routes/ventas.py` — `punto_de_venta()` POST

```python
desc_pct = Decimal(str(item.get('descuento_porcentaje', 0)))

# Validar rango
if desc_pct < 0 or desc_pct > 100:
    raise ValueError('El descuento debe estar entre 0 y 100')

bruto = cantidad * precio
descuento_item = bruto * (desc_pct / Decimal('100'))
item_subtotal = bruto - descuento_item

detalle = VentaDetalle(
    producto_id=producto.id,
    cantidad=cantidad,
    precio_unitario=precio,
    descuento_porcentaje=desc_pct,
    iva_porcentaje=producto.iva_porcentaje,
    subtotal=item_subtotal
)
```

#### `app/services/presupuesto_service.py`

Mismos cambios en tres metodos:

- **`crear_presupuesto()`**: Leer `descuento_porcentaje` del item, calcular subtotal con descuento, asignar al detalle.
- **`actualizar_presupuesto()`**: Idem al crear.
- **`convertir_a_venta()`**: Copiar `descuento_porcentaje` **explicitamente** de cada `PresupuestoDetalle` al `VentaDetalle` correspondiente.

#### `app/routes/presupuestos.py` — `editar()` GET

Incluir `descuento_porcentaje` en el diccionario `items_existentes` que se pasa al template:

```python
items_existentes = [{
    'producto_id': d.producto_id,
    'codigo': d.producto.codigo,
    'nombre': d.producto.nombre,
    'cantidad': float(d.cantidad),
    'precio_unitario': float(d.precio_unitario),
    'descuento_porcentaje': float(d.descuento_porcentaje),
    'iva_porcentaje': float(d.iva_porcentaje),
    # ...
}]
```

---

### 2.5 Cambios en Templates / UI

#### 2.5.1 POS (`app/templates/ventas/punto_venta.html`)

**Tabla del carrito — nueva columna:**

Agregar columna "Desc. %" entre "P. Unit." y "Subtotal".

**Input por fila:**

```html
<input type="number"
       x-model.number="item.descuento_porcentaje"
       min="0" max="100" step="0.5"
       class="form-control form-control-sm text-end"
       style="width: 70px;">
```

**Calculo subtotal por item:**

```javascript
item.cantidad * item.precio_unitario * (1 - (item.descuento_porcentaje || 0) / 100)
```

**Computed `subtotal` actualizado:**

```javascript
get subtotal() {
    return this.cart.reduce((sum, item) => {
        const desc = item.descuento_porcentaje || 0;
        return sum + (item.cantidad * item.precio_unitario * (1 - desc / 100));
    }, 0);
},
```

**`addToCart()`:**

Agregar `descuento_porcentaje: 0` al objeto del item cuando se agrega al carrito.

**IVA agrupado:**

Actualizar `itemSubtotal` en el calculo de IVA para incluir el descuento unitario:

```javascript
const itemSubtotal = item.cantidad * item.precio_unitario * (1 - (item.descuento_porcentaje || 0) / 100);
```

**`items_json`:**

Incluir `descuento_porcentaje` en el JSON serializado para el backend.

#### 2.5.2 Presupuesto (`app/templates/presupuestos/crear.html`)

Mismos cambios que el POS. Al editar un presupuesto, `items_existentes` debe incluir `descuento_porcentaje` para precargar el valor en el input.

#### 2.5.3 Vista Detalle Venta (`app/templates/ventas/detalle.html`)

Nueva columna "Desc." en la tabla de items:

- Mostrar el porcentaje si > 0 (ej: "10%")
- Mostrar "-" si es 0
- Actualizar `colspan` de filas de totales

#### 2.5.4 Vista Detalle Presupuesto (`app/templates/presupuestos/detalle.html`)

Mismo cambio que la vista de detalle de venta.

#### 2.5.5 Ticket (`app/templates/ventas/ticket.html`)

Si el item tiene descuento, mostrar en formato compacto:

```
2 x $4,333.00 -10%    $7,799.40
```

Si no tiene descuento, mantener formato actual:

```
2 x $4,333.00          $8,666.00
```

#### 2.5.6 PDF Venta (`app/templates/ventas/pdf/venta.html`)

- Nueva columna "Desc." en la tabla de items
- Ajustar anchos CSS de las columnas existentes para acomodar la nueva columna sin desbordar el layout

#### 2.5.7 PDF Presupuesto (`app/templates/presupuestos/pdf/presupuesto.html`)

Mismo cambio que el PDF de venta.

---

### 2.6 Reportes

`app/routes/reportes.py`: Los queries de reportes usan `VentaDetalle.subtotal` como base de calculo. Dado que `subtotal` ya incluira el descuento unitario despues de los cambios en el modelo, **los reportes funcionan correctamente SIN cambios**.

---

## 3. Casos Borde

| Caso                                     | Comportamiento esperado                                                   |
| ---------------------------------------- | ------------------------------------------------------------------------- |
| Descuento unitario 100% en un item       | Subtotal = $0. Valido (regalo, muestra gratis).                           |
| Descuento unitario > 100%                | Validar en JS (`max=100`) y backend. **No permitir.**                     |
| Descuento unitario negativo              | Validar en JS (`min=0`) y backend. **No permitir.**                       |
| Descuento global 100% + descuento unit.  | Total = $0. Valido.                                                       |
| Redondeo JS vs Python                    | `Decimal` server-side es la fuente de verdad. JS solo muestra preview.    |
| Ventas existentes (historicas)            | `server_default='0'` — comportamiento identico al actual.                 |
| Conversion presupuesto a venta           | Copiar `descuento_porcentaje` **explicitamente** en `convertir_a_venta()`. |
| Anulacion de venta                       | No impacta. La anulacion no recalcula montos.                             |

---

## 4. Lista Completa de Archivos a Modificar

### Migracion (crear)

| # | Archivo                                                | Accion                                        |
| - | ------------------------------------------------------ | --------------------------------------------- |
| 1 | `migrations/versions/0008_descuento_unitario_detalle.py` | **NUEVO** — agregar columna a ambas tablas   |

### Modelos (editar)

| # | Archivo                          | Cambios                                                |
| - | -------------------------------- | ------------------------------------------------------ |
| 2 | `app/models/venta_detalle.py`    | Nueva columna + `calcular_subtotal()` + `to_dict()`   |
| 3 | `app/models/presupuesto.py`      | Mismos cambios en `PresupuestoDetalle`                 |

### Servicios (editar)

| # | Archivo                                | Cambios                                           |
| - | -------------------------------------- | ------------------------------------------------- |
| 4 | `app/services/presupuesto_service.py`  | `crear`, `actualizar`, `convertir_a_venta`        |

### Rutas (editar)

| # | Archivo                        | Cambios                                              |
| - | ------------------------------ | ---------------------------------------------------- |
| 5 | `app/routes/ventas.py`         | `punto_de_venta()` POST — leer desc y calcular       |
| 6 | `app/routes/presupuestos.py`   | `editar()` GET — incluir desc en `items_existentes`  |

### Templates (editar)

| #  | Archivo                                                | Cambios                                    |
| -- | ------------------------------------------------------ | ------------------------------------------ |
| 7  | `app/templates/ventas/punto_venta.html`                | Columna + input + JS actualizado           |
| 8  | `app/templates/presupuestos/crear.html`                | Columna + input + JS actualizado           |
| 9  | `app/templates/ventas/detalle.html`                    | Columna desc + colspan                     |
| 10 | `app/templates/presupuestos/detalle.html`              | Columna desc + colspan                     |
| 11 | `app/templates/ventas/ticket.html`                     | Mostrar desc unitario si > 0               |
| 12 | `app/templates/ventas/pdf/venta.html`                  | Columna desc + ajuste CSS                  |
| 13 | `app/templates/presupuestos/pdf/presupuesto.html`      | Columna desc + ajuste CSS                  |

### NO necesitan cambios

| Archivo                          | Razon                                                    |
| -------------------------------- | -------------------------------------------------------- |
| `app/models/venta.py`            | `calcular_totales()` ya usa `sum(d.subtotal)` — funciona |
| `app/services/venta_service.py`  | Solo genera PDF, no calcula montos                       |
| `app/routes/reportes.py`         | Queries sobre `subtotal` siguen validos                  |

---

## 5. Evaluacion de Riesgo

| Riesgo                                   | Probabilidad | Impacto | Mitigacion                                                         |
| ---------------------------------------- | ------------ | ------- | ------------------------------------------------------------------ |
| Confusion calculo unitario + global      | Media        | Alto    | Documentar en UI: "Descuento por item primero, global despues"     |
| Redondeo JS vs Python                    | Baja         | Medio   | Calculo definitivo server-side con `Decimal`                       |
| Ventas historicas                         | Nula         | Nulo    | `server_default='0'` preserva comportamiento                      |
| Reportes incorrectos                     | Nula         | Nulo    | Usan `VentaDetalle.subtotal` que ya incluye descuento              |
| Conversion presupuesto pierde descuento  | Media        | Alto    | Copiar `descuento_porcentaje` explicitamente en `convertir_a_venta()` |
| PDFs deformados con nueva columna        | Baja         | Bajo    | Ajustar anchos CSS de todas las columnas                           |

---

## 6. Plan de Testing

### Tests unitarios

1. `VentaDetalle.calcular_subtotal()` con descuento **0%** — debe dar `cantidad * precio_unitario`
2. `VentaDetalle.calcular_subtotal()` con descuento **10%** — verificar calculo correcto
3. `VentaDetalle.calcular_subtotal()` con descuento **50%** — mitad del bruto
4. `VentaDetalle.calcular_subtotal()` con descuento **100%** — subtotal = $0

### Tests de integracion — Venta

5. `Venta.calcular_totales()` con items mixtos (algunos con descuento, otros sin)
6. Crear venta via POS con descuento unitario + descuento global — verificar stacking secuencial
7. Crear venta POS **sin** descuento unitario — regresion, comportamiento identico al actual

### Tests de integracion — Presupuesto

8. Crear presupuesto con descuentos unitarios
9. Editar presupuesto — verificar que `descuento_porcentaje` persiste y se precarga
10. Convertir presupuesto con descuentos a venta — verificar que `descuento_porcentaje` se copia

### Tests de regresion

11. Crear venta sin ningun descuento (ni unitario ni global) — total = subtotal

### Tests visuales (manuales)

12. PDFs de venta y presupuesto con nueva columna — verificar layout
13. Ticket con y sin descuento unitario — verificar formato
