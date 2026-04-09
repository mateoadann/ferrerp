# Issue #36 -- Descuento al Inverso

| Campo          | Valor                                                    |
|----------------|----------------------------------------------------------|
| **Issue**      | [#36](https://github.com/mateo/ferrerp/issues/36)       |
| **Titulo**     | Descuento al inverso                                     |
| **Fecha**      | 2026-04-05                                               |
| **Complejidad**| Baja (cambios exclusivamente en front-end)               |
| **Archivos**   | 2                                                        |
| **Migracion**  | No requerida                                             |

---

## Indice

1. [Estado actual de los descuentos](#1-estado-actual-de-los-descuentos)
2. [Cambios propuestos](#2-cambios-propuestos)
3. [UI/UX](#3-uiux)
4. [Edge cases](#4-edge-cases)
5. [Interaccion con Issue #35](#5-interaccion-con-issue-35-descuentos-por-producto)
6. [Archivos a modificar](#6-archivos-a-modificar)
7. [Migracion necesaria](#7-migracion-necesaria)
8. [Evaluacion de riesgo](#8-evaluacion-de-riesgo)
9. [Testing sugerido](#9-testing-sugerido)

---

## 1. Estado actual de los descuentos

### 1.1 Modelo de datos

#### `Venta` (`app/models/venta.py`)

| Campo                  | Tipo            | Default | Descripcion                              |
|------------------------|-----------------|---------|------------------------------------------|
| `descuento_porcentaje` | `Numeric(5,2)`  | 0       | Porcentaje de descuento global           |
| `descuento_monto`      | `Numeric(12,2)` | 0       | Monto calculado del descuento            |
| `subtotal`             | `Numeric(12,2)` | --      | Suma de subtotales de detalles           |
| `total`                | `Numeric(12,2)` | --      | `subtotal - descuento_monto`             |

El metodo `calcular_totales()` (lineas 94-103) calcula `descuento_monto` a partir de `descuento_porcentaje`.

#### `Presupuesto` (`app/models/presupuesto.py`)

Mismos campos: `descuento_porcentaje`, `descuento_monto`, `subtotal`, `total`.
El metodo `calcular_totales()` (lineas 124-132) aplica la misma logica.

#### `VentaDetalle` / `PresupuestoDetalle`

**No tienen campo de descuento por linea.** Solo contienen: `cantidad`, `precio_unitario`, `iva_porcentaje`, `subtotal`.

### 1.2 Flujo de descuento actual

1. El usuario ingresa un **porcentaje** en un input numerico (0-100, step 0.5).
2. Alpine.js calcula en tiempo real:
   - `descuentoMonto = subtotal * (descuentoPorcentaje / 100)`
   - `total = subtotal - descuentoMonto`
3. El formulario oculto envia `descuento_porcentaje` al backend.
4. El backend recalcula: `descuento_monto = subtotal * (descuento_porcentaje / 100)` y `total = subtotal - descuento_monto`.

### 1.3 UI actual (punto de venta y presupuestos)

En ambas pantallas, la seccion de totales tiene un input de porcentaje con sufijo `%`. Solo existe el input de porcentaje. **No hay forma de ingresar un total deseado.**

### 1.4 JavaScript (Alpine.js)

#### POS (`punto_venta.html`, lineas 293-303)

```js
get subtotal() {
    return this.cart.reduce(
        (sum, item) => sum + (item.cantidad * item.precio_unitario), 0
    );
},
get descuentoMonto() {
    return this.subtotal * (this.descuentoPorcentaje / 100);
},
get total() {
    return this.subtotal - this.descuentoMonto;
},
```

#### Presupuestos (`crear.html`, lineas 275-288)

Misma logica, con `parseMoneyNumber` para precios editables.

Ambos templates tienen la cadena de IVA agrupado -> `netoSinIva` -> `totalConIva` que depende de `this.total`.

---

## 2. Cambios propuestos

### 2.1 No se necesitan cambios en el modelo ni migracion

La formula inversa es **puramente de UI/JS**. El backend ya recibe `descuento_porcentaje` y calcula todo correctamente. Solo se necesita:

1. Un nuevo input en la UI para el "total deseado".
2. Logica JS que calcule el porcentaje a partir de ese total deseado.
3. Setear `descuentoPorcentaje` automaticamente.

**No hay cambios en modelos, servicios, rutas, ni base de datos.**

### 2.2 Cambios en templates (UI)

#### Archivo: `app/templates/ventas/punto_venta.html`

Agregar toggle con dos botones compactos `%` y `$` para cambiar de modo:

- **Modo `%` (actual):** input numerico de porcentaje.
- **Modo `$` (nuevo):** input de money donde el usuario tipea el total deseado.

#### Archivo: `app/templates/presupuestos/crear.html`

Exactamente el mismo cambio en la seccion de totales.

### 2.3 Cambios en JavaScript (Alpine.js)

En ambos archivos (`posApp()` y `presupuestoApp()`):

#### Nuevas propiedades de estado

```js
modoDescuento: 'porcentaje',  // 'porcentaje' | 'total'
totalDeseado: '',
```

#### Nuevo metodo `calcularDescuentoDesdeTotal()`

```js
calcularDescuentoDesdeTotal() {
    const deseado = parseMoneyNumber(this.totalDeseado);
    if (this.subtotal <= 0 || deseado <= 0) {
        this.descuentoPorcentaje = 0;
        return;
    }
    if (deseado >= this.subtotal) {
        this.descuentoPorcentaje = 0;
        return;
    }
    // Formula inversa: porcentaje = ((subtotal - totalDeseado) / subtotal) * 100
    const porcentaje = ((this.subtotal - deseado) / this.subtotal) * 100;
    this.descuentoPorcentaje = Math.round(porcentaje * 100) / 100;
},
```

#### Sync bidireccional

- Al cambiar a modo `total`: poblar `totalDeseado` con el total actual.
- Al cambiar items del carrito en modo `total`: recalcular porcentaje para mantener el total deseado.

#### Persistencia de estado (solo POS)

Agregar `modoDescuento` y `totalDeseado` al `persistState()` / `restoreState()` del punto de venta.

### 2.4 Detalle de la formula

```
subtotal       = sum(cantidad * precio_unitario) para todos los items
total_deseado  = input del usuario
porcentaje     = ((subtotal - total_deseado) / subtotal) * 100
```

#### Ejemplo concreto

| Dato              | Valor      |
|-------------------|------------|
| Subtotal          | $11,890.00 |
| Total deseado     | $11,000.00 |
| Porcentaje        | ((11890 - 11000) / 11890) * 100 = **7.48%** |
| Descuento monto   | 11890 * 0.0748 = **$889.41** |
| Total final real   | 11890 - 889.41 = **$11,000.59** |

#### Estrategia de redondeo

Usar porcentaje redondeado a 2 decimales y mostrar el **total resultante real** (no el deseado). No requiere cambios en el backend. La diferencia es despreciable (centavos).

---

## 3. UI/UX

### 3.1 Interaccion propuesta

1. Por defecto, modo "porcentaje" (comportamiento actual, sin cambios para el usuario existente).
2. Dos botones compactos `%` y `$` funcionan como toggle.
3. Al presionar `$`, aparece un input de money donde el usuario tipea el total deseado.
4. Al tipear, se recalcula automaticamente el porcentaje.
5. El monto del descuento y total se actualizan en tiempo real.
6. Al cambiar de vuelta a `%`, el porcentaje calculado queda seteado.

### 3.2 Feedback visual

- **Total deseado > subtotal:** porcentaje queda en 0.
- **Total deseado 0 o negativo:** se ignora.
- **Sin items en el carrito:** inputs deshabilitados.
- **Monto del descuento:** mostrar `-$XXX.XX` siempre visible independientemente del modo activo.

---

## 4. Edge cases

| Caso | Comportamiento |
|------|---------------|
| Carrito vacio (subtotal = 0) | Inputs deshabilitados. `porcentaje = 0`. |
| Total deseado > subtotal | `porcentaje = 0`. |
| Total deseado = 0 | Bloquear. Validar que total deseado > 0. |
| Total deseado negativo | `porcentaje = 0`, ignorar. |
| Redondeo del porcentaje | Con `Numeric(5,2)` max 2 decimales. Total real puede diferir por centavos del deseado. |
| Cambio de items en modo total | Recalcular porcentaje para mantener el total deseado. |
| Remocion de todos los items en modo total | Reset a `porcentaje = 0`, limpiar `totalDeseado`. |

---

## 5. Interaccion con Issue #35 (descuentos por producto)

**No hay conflicto.** Son features ortogonales.

Si #35 se implementa primero, el `subtotal` ya contemplaria descuentos individuales por linea, y la formula inversa sigue funcionando exactamente igual porque opera sobre el subtotal final.

---

## 6. Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `app/templates/ventas/punto_venta.html` | Toggle `%`/`$` + nuevas propiedades y metodo en `posApp()` + persistencia de estado |
| `app/templates/presupuestos/crear.html` | Toggle `%`/`$` + nuevas propiedades y metodo en `presupuestoApp()` |

**Total: 2 archivos.**

---

## 7. Migracion necesaria

**No.** Esta feature es 100% front-end. No se modifican modelos, no se agregan columnas, no se necesita migracion de base de datos.

---

## 8. Evaluacion de riesgo

| Riesgo | Nivel | Mitigacion |
|--------|-------|-----------|
| Redondeo causa diferencia con total deseado | Bajo | Mostrar total real calculado, no el deseado |
| Inconsistencia al agregar/quitar items en modo total | Bajo | Recalcular porcentaje via watcher sobre el carrito |
| Confusion UX con dos modos | Bajo | Default es modo porcentaje. Boton `$` es opt-in |
| Rotura de JS existente | Bajo | Solo se agregan propiedades nuevas. No se modifica logica existente |
| Interaccion con IVA agrupado | Nulo | La cadena `total` -> `ivaAgrupado` no cambia |
| Regresion en el submit del formulario | Nulo | El form sigue enviando `descuento_porcentaje` como siempre |

---

## 9. Testing sugerido

### Tests manuales

- Crear venta con subtotal $11,890, ingresar total deseado $11,000, verificar porcentaje ~7.48%.
- Cambiar modo de `$` a `%` y viceversa, verificar coherencia de valores.
- Agregar/quitar items en modo `$`, verificar recalculo automatico del porcentaje.
- Ingresar total deseado mayor que subtotal, verificar que porcentaje = 0.
- Verificar que la persistencia de estado en POS guarda y restaura el modo y total deseado.
- Repetir todos los tests en la pantalla de presupuestos.

### Tests automatizados

Los tests de backend existentes **no deberian verse afectados** ya que no hay cambios en modelos, servicios ni rutas. No se requieren nuevos tests de backend.
