# Feature: Actualizacion Rapida de Precio Individual

## Resumen ejecutivo

Esta feature agrega un boton de accion rapida en la tabla de productos que abre un modal para actualizar el precio de venta de un producto individual, sin necesidad de entrar al formulario completo de edicion. El modal permite dos modos de actualizacion: precio directo (el usuario ingresa el nuevo precio de venta) y porcentaje (el usuario ingresa un porcentaje de aumento/disminucion). En ambos casos, el sistema calcula automaticamente el precio de costo correspondiente manteniendo la relacion costo-venta via margen, y muestra una previsualizacion en tiempo real del precio final antes de confirmar.

**Issue:** #61

---

## Contexto y problema de negocio

### La necesidad del ferretero

En una ferreteria, la actualizacion de precios no siempre es masiva. Hay situaciones frecuentes donde el ferretero necesita ajustar el precio de UN solo producto:

- El proveedor le aviso que subio el precio de un producto especifico
- Quiere hacer una promo temporal bajando el precio de venta
- Se da cuenta de que un producto tiene un margen demasiado bajo (o alto) y quiere corregirlo

Hoy, para hacer eso, tiene que:

1. Buscar el producto en la tabla
2. Hacer click en "Editar"
3. Esperar que cargue el formulario completo (con todos los campos: stock, proveedor, unidad, etc.)
4. Modificar el campo de precio
5. Calcular mentalmente si el costo/margen tiene sentido
6. Guardar

Son demasiados pasos para algo que deberia tomar 5 segundos. La actualizacion masiva existente (`/productos/actualizacion-masiva`) resuelve cambios por categoria con porcentaje, pero no sirve para el caso de un producto puntual.

### Lo que ya existe en el sistema

| Funcionalidad | Archivo | Descripcion |
|---------------|---------|-------------|
| Tabla de productos | `app/templates/productos/_tabla.html` | Partial HTMX con botones de accion: "Editar" y "Ver" |
| Edicion completa | `app/routes/productos.py` → `editar()` | Formulario completo con todos los campos del producto |
| Actualizacion masiva | `app/routes/productos.py` → `actualizacion_masiva_*()` | Por categoria y porcentaje, con preview |
| Servicio de precios | `app/services/actualizacion_precio_service.py` | Logica de calculo y aplicacion de actualizacion masiva |
| Modelo de auditoria | `app/models/actualizacion_precio.py` → `ActualizacionPrecio` | Registro de cada cambio de precio con tipo `'masiva'` o `'manual'` |
| Modelo de producto | `app/models/producto.py` → `Producto` | Campos: `precio_costo` (Numeric 12,2), `precio_venta` (Numeric 12,2), `iva_porcentaje` (Numeric 5,2) |

---

## Requerimientos funcionales

| ID | Requerimiento | Prioridad |
|----|---------------|-----------|
| PI-01 | Agregar boton de accion "Actualizar precio" en cada fila de la tabla de productos | Alta |
| PI-02 | El boton abre un modal con informacion del producto (nombre, codigo, categoria) | Alta |
| PI-03 | El modal muestra los precios actuales (costo y venta) y el IVA | Alta |
| PI-04 | Input para ingresar nuevo precio de venta directamente | Alta |
| PI-05 | Toggle para cambiar a modo porcentaje (aumento/disminucion) | Alta |
| PI-06 | En modo porcentaje, el input acepta valores positivos (aumento) y negativos (descuento) | Alta |
| PI-07 | En ambos modos, previsualizar el precio final en tiempo real (sin guardar) | Alta |
| PI-08 | Al ingresar un nuevo precio de venta, calcular automaticamente el nuevo precio de costo manteniendo el margen actual | Alta |
| PI-09 | Botones "Guardar" y "Cancelar" en el modal | Alta |
| PI-10 | Registrar el cambio en `ActualizacionPrecio` con tipo `'manual'` | Alta |
| PI-11 | Solo usuarios con rol `administrador` pueden actualizar precios | Alta |
| PI-12 | Validar que el precio de venta sea mayor a cero | Alta |
| PI-13 | Validar que el precio de venta sea mayor o igual al precio de costo | Media |
| PI-14 | Mostrar margen de ganancia resultante en el preview | Media |
| PI-15 | Refrescar la fila del producto en la tabla despues de guardar (sin recargar toda la pagina) | Media |

---

## Diseno de UI: Modal de actualizacion rapida de precio

### Wireframe textual

```
+------------------------------------------------------------------+
|  Actualizar Precio                                           [X]  |
+------------------------------------------------------------------+
|                                                                    |
|  Producto: Martillo Stanley 500g                                   |
|  Codigo: MAR-001                                                   |
|  Categoria: Herramientas Manuales > Martillos                      |
|                                                                    |
|  +---------------------------+---------------------------+         |
|  | Precio costo actual       | Precio venta actual       |         |
|  | $850,00                   | $1.200,00                 |         |
|  +---------------------------+---------------------------+         |
|  | IVA: 21%                  | Margen actual: 41,18%     |         |
|  +---------------------------+---------------------------+         |
|                                                                    |
|  +---------------------------------------------------------+       |
|  | Modo:  [Precio directo]  |  [Porcentaje]               |       |
|  +---------------------------------------------------------+       |
|                                                                    |
|  --- Modo Precio Directo ---                                       |
|  Nuevo precio de venta:  [ $1.350,00          ]                    |
|                                                                    |
|  --- Modo Porcentaje ---                                           |
|  Porcentaje de ajuste:   [ 12,5               ] %                  |
|                                                                    |
|  +---------------------------------------------------------+       |
|  | PREVIEW                                                 |       |
|  +---------------------------------------------------------+       |
|  | Precio venta nuevo:    $1.350,00   (+$150,00)           |       |
|  | Precio costo nuevo:    $956,25     (+$106,25)           |       |
|  | Margen resultante:     41,18%      (sin cambio)         |       |
|  | Precio con IVA:        $1.633,50                        |       |
|  +---------------------------------------------------------+       |
|                                                                    |
|                            [Cancelar]  [Guardar]                   |
+------------------------------------------------------------------+
```

### Descripcion del modal

**Encabezado:**
- Titulo: "Actualizar Precio"
- Icono: `sell` (Material Symbols Rounded)
- Boton de cierre (X)

**Seccion informativa (solo lectura):**
- Nombre del producto (`Producto.nombre`)
- Codigo (`Producto.codigo`)
- Categoria completa (`Producto.categoria.nombre_completo` — formato "Padre > Hijo")
- Precio costo actual (`Producto.precio_costo`)
- Precio venta actual (`Producto.precio_venta`)
- IVA (`Producto.iva_porcentaje`)
- Margen de ganancia actual (`Producto.margen_ganancia` — propiedad calculada)

**Selector de modo:**
- Dos botones tipo tab/toggle: "Precio directo" y "Porcentaje"
- Por defecto: "Precio directo"
- Al cambiar de modo, limpiar el input y el preview

**Input segun modo:**
- **Precio directo:** Input numerico con placeholder del precio actual. El usuario ingresa el nuevo precio de venta en pesos.
- **Porcentaje:** Input numerico que acepta decimales, positivos y negativos. El usuario ingresa el porcentaje de ajuste (ej: `10` para +10%, `-5` para -5%).

**Preview (se actualiza en tiempo real via JavaScript del lado cliente):**
- Precio venta nuevo (con diferencia respecto al actual)
- Precio costo nuevo (con diferencia respecto al actual)
- Margen de ganancia resultante
- Precio final con IVA incluido

**Botones:**
- "Cancelar": cierra el modal sin cambios
- "Guardar": envia el formulario y aplica el cambio

---

## Logica de calculo de precios

### Relacion entre precio de costo, precio de venta y margen

En el modelo actual de `Producto`, la relacion es:

```
margen_ganancia = ((precio_venta - precio_costo) / precio_costo) * 100
```

O sea:

```
precio_venta = precio_costo * (1 + margen_ganancia / 100)
```

Despejando costo:

```
precio_costo = precio_venta / (1 + margen_ganancia / 100)
```

### Modo "Precio directo"

El usuario ingresa un nuevo `precio_venta`. El sistema calcula el nuevo `precio_costo` **manteniendo el margen de ganancia actual**:

```
margen_actual = producto.margen_ganancia  # propiedad calculada
nuevo_precio_costo = nuevo_precio_venta / (1 + margen_actual / 100)
```

**Caso especial:** Si el `precio_costo` actual es 0, no se puede calcular margen. En ese caso:
- `nuevo_precio_costo` se mantiene en 0
- Se muestra un aviso: "El precio de costo es $0, no se puede calcular el margen. Solo se actualizara el precio de venta."

### Modo "Porcentaje"

El usuario ingresa un porcentaje de ajuste. El sistema aplica el porcentaje a AMBOS precios:

```
factor = 1 + (porcentaje / 100)
nuevo_precio_venta = precio_venta_actual * factor
nuevo_precio_costo = precio_costo_actual * factor
```

Esto mantiene el margen intacto porque ambos precios se escalan proporcionalmente.

**Nota:** Este es el mismo comportamiento que la actualizacion masiva existente en `actualizacion_precio_service.previsualizar_actualizacion()`.

### Precio con IVA (solo para preview, no se persiste)

```
precio_con_iva = nuevo_precio_venta * (1 + iva_porcentaje / 100)
```

### Redondeo

Todos los calculos monetarios se redondean a 2 decimales con `ROUND_HALF_UP`, consistente con el servicio existente:

```python
dos_decimales = Decimal('0.01')
nuevo_precio = (precio * factor).quantize(dos_decimales, rounding=ROUND_HALF_UP)
```

---

## Implementacion tecnica

### Endpoint HTMX: cargar modal

**Ruta nueva en `app/routes/productos.py`:**

```python
@bp.route('/<int:id>/modal-precio')
@login_required
@empresa_aprobada_required
@admin_required
def modal_precio(id):
    """Retorna el HTML del modal de actualizacion rapida de precio."""
    producto = Producto.get_o_404(id)
    return render_template('productos/_modal_precio.html', producto=producto)
```

**Patron HTMX:** El boton en la tabla hace `hx-get` al endpoint, que devuelve el HTML del modal completo. Luego se muestra con Bootstrap JS.

### Endpoint POST: guardar precio

**Ruta nueva en `app/routes/productos.py`:**

```python
@bp.route('/<int:id>/actualizar-precio', methods=['POST'])
@login_required
@empresa_aprobada_required
@admin_required
def actualizar_precio(id):
    """Aplica actualizacion individual de precio."""
    producto = Producto.get_o_404(id)

    try:
        nuevo_precio_venta = Decimal(str(request.form.get('precio_venta', '0')))
        nuevo_precio_costo = Decimal(str(request.form.get('precio_costo', '0')))
    except Exception:
        flash('Los valores ingresados no son validos.', 'danger')
        return redirect(url_for('productos.index'))

    if nuevo_precio_venta <= 0:
        flash('El precio de venta debe ser mayor a cero.', 'danger')
        return redirect(url_for('productos.index'))

    # Registrar auditoria
    registro = ActualizacionPrecio(
        producto_id=producto.id,
        usuario_id=current_user.id,
        tipo='manual',
        porcentaje=None,  # o el porcentaje si se uso modo porcentaje
        precio_costo_anterior=producto.precio_costo,
        precio_costo_nuevo=nuevo_precio_costo,
        precio_venta_anterior=producto.precio_venta,
        precio_venta_nuevo=nuevo_precio_venta,
        actualizo_costo=True,
        notas='Actualizacion individual desde tabla de productos',
        empresa_id=current_user.empresa_id,
    )
    db.session.add(registro)

    # Actualizar producto
    producto.precio_costo = nuevo_precio_costo
    producto.precio_venta = nuevo_precio_venta
    db.session.commit()

    flash(f'Precio de "{producto.nombre}" actualizado correctamente.', 'success')

    # Si es HTMX, devolver la fila actualizada
    if es_peticion_htmx():
        return render_template('productos/_fila_producto.html', producto=producto)

    return redirect(url_for('productos.index'))
```

### Preview en tiempo real

La previsualizacion se calcula **en el cliente con JavaScript**, no con un endpoint HTMX. Razon: el calculo es trivial (multiplicacion y division), y hacer un request al servidor por cada tecla que tipea el usuario seria excesivo.

```javascript
// Pseudocodigo del calculo en el cliente
function calcularPreview(modo, valor, precioVentaActual, precioCostoActual, ivaPorcentaje) {
    let nuevoPrecioVenta, nuevoPrecioCosto;

    if (modo === 'directo') {
        nuevoPrecioVenta = parseFloat(valor);
        // Mantener margen actual
        if (precioCostoActual > 0) {
            const margen = (precioVentaActual - precioCostoActual) / precioCostoActual;
            nuevoPrecioCosto = nuevoPrecioVenta / (1 + margen);
        } else {
            nuevoPrecioCosto = 0;
        }
    } else {
        // Modo porcentaje
        const factor = 1 + parseFloat(valor) / 100;
        nuevoPrecioVenta = precioVentaActual * factor;
        nuevoPrecioCosto = precioCostoActual * factor;
    }

    const margenResultante = nuevoPrecioCosto > 0
        ? ((nuevoPrecioVenta - nuevoPrecioCosto) / nuevoPrecioCosto) * 100
        : 0;
    const precioConIva = nuevoPrecioVenta * (1 + ivaPorcentaje / 100);

    return { nuevoPrecioVenta, nuevoPrecioCosto, margenResultante, precioConIva };
}
```

**Evento de actualizacion:** `input` (se dispara con cada tecla), con un debounce de 150ms para evitar recalculos excesivos.

---

## Cambios en la tabla de productos

### Boton nuevo en `_tabla.html`

Actualmente la columna de acciones tiene dos botones (lineas 45-52 de `_tabla.html`):

```html
<div class="action-icons">
    <a href="..." class="action-icon" title="Editar">
        <span class="material-symbols-rounded">edit</span>
    </a>
    <a href="..." class="action-icon" title="Ver">
        <span class="material-symbols-rounded">visibility</span>
    </a>
</div>
```

Se agrega un tercer boton **antes** de los existentes:

```html
<button type="button"
        class="action-icon"
        title="Actualizar precio"
        hx-get="{{ url_for('productos.modal_precio', id=producto.id) }}"
        hx-target="#modal-precio-container"
        hx-swap="innerHTML"
        hx-on::after-request="new bootstrap.Modal(document.getElementById('modalPrecio')).show()">
    <span class="material-symbols-rounded">sell</span>
</button>
```

**Visibilidad:** El boton solo se muestra si `current_user.es_admin` (consistente con el patron de la actualizacion masiva que requiere `@admin_required`).

### Contenedor del modal

Agregar un `<div id="modal-precio-container"></div>` en `productos/index.html` (fuera de la tabla), donde HTMX inyecta el HTML del modal.

---

## Template del modal

**Archivo nuevo:** `app/templates/productos/_modal_precio.html`

Estructura Bootstrap 5 modal siguiendo el patron existente en `components/modal_confirm.html` y `clientes/_modal_cumpleanos.html`:

- `modal-dialog-centered` para centrar verticalmente
- Iconos Material Symbols Rounded (como en todo el proyecto)
- Formulario con `method="POST"` y `csrf_token()`
- Datos del producto pasados como data-attributes al form para que JS haga los calculos
- Hidden inputs para `precio_venta` y `precio_costo` que se actualizan con JS antes del submit

---

## Edge cases

| Edge case | Comportamiento |
|-----------|----------------|
| **Precio costo actual es $0** | No se puede calcular margen. En modo directo, el costo nuevo se mantiene en 0. En modo porcentaje, el costo sigue en 0 (0 * factor = 0). Mostrar aviso informativo. |
| **Precio venta nuevo menor al costo actual** | Mostrar warning visual (texto en rojo) pero permitir guardar. El ferretero puede querer liquidar stock. |
| **Precio venta nuevo es $0 o negativo** | No permitir guardar. Mostrar error de validacion. |
| **Porcentaje de -100% o menor** | Resultaria en precio $0 o negativo. No permitir guardar. |
| **Producto inactivo** | El boton se muestra igual. El admin puede querer actualizar el precio antes de reactivarlo. |
| **Input no numerico** | Validar en JS (input type="number" con step="0.01"). Validar en backend con try/except Decimal. |
| **Dos admins actualizando el mismo producto simultaneamente** | El ultimo en guardar gana (last-write-wins). El registro de `ActualizacionPrecio` deja auditoria de ambos cambios. No se requiere locking optimista para esta feature. |
| **Producto sin categoria** | El modal muestra "-" en el campo de categoria (consistente con la tabla actual). |
| **Valores con muchos decimales** | Redondeo a 2 decimales con `ROUND_HALF_UP` antes de persistir. |

---

## Cambios tecnicos necesarios

### Archivos nuevos

| Archivo | Descripcion |
|---------|-------------|
| `app/templates/productos/_modal_precio.html` | Modal Bootstrap con formulario de actualizacion rapida de precio |
| `app/templates/productos/_fila_producto.html` | Partial con una sola fila `<tr>` de la tabla, para refresco HTMX post-guardado (opcional, ver nota) |

**Nota sobre `_fila_producto.html`:** Actualmente la fila esta inline en `_tabla.html` dentro del `{% for %}`. Para hacer el refresco HTMX de una sola fila, hay que extraer el `<tr>` a un partial reutilizable e incluirlo desde `_tabla.html` con `{% include %}`. Alternativamente, se puede refrescar toda la tabla con `hx-target="#tabla-productos"` — es mas simple y con la paginacion actual (pocos productos por pagina) no hay impacto de performance.

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `app/routes/productos.py` | Agregar rutas `modal_precio()` y `actualizar_precio()` |
| `app/templates/productos/_tabla.html` | Agregar boton de accion "Actualizar precio" con icono `sell` |
| `app/templates/productos/index.html` | Agregar `<div id="modal-precio-container"></div>` para inyeccion HTMX del modal |

### Modelos

No se crean modelos nuevos. Se reutiliza `ActualizacionPrecio` existente con `tipo='manual'` (el campo `tipo` ya soporta este valor — ver linea 17 de `app/models/actualizacion_precio.py`).

### Servicios

No se crea un servicio nuevo. La logica es lo suficientemente simple para vivir en la ruta:
- Crear registro de `ActualizacionPrecio`
- Actualizar `precio_costo` y `precio_venta` del producto
- Commit

Si en el futuro se necesita reutilizar esta logica (ej: API, importacion), se puede extraer a `actualizacion_precio_service.py` como `aplicar_actualizacion_individual()`.

### Migraciones

No se requieren migraciones. Todos los campos necesarios ya existen en los modelos.

---

## Fases de implementacion sugeridas

### Fase 1: Modal basico con modo precio directo

**Estimacion:** 0.5 dia de desarrollo

**Alcance:**
- Crear ruta `modal_precio()` en `app/routes/productos.py`
- Crear template `app/templates/productos/_modal_precio.html` con datos del producto y modo precio directo
- Agregar boton en `_tabla.html` (solo para admins)
- Agregar contenedor del modal en `index.html`
- JavaScript para preview en tiempo real (modo directo)
- Crear ruta `actualizar_precio()` con validacion y persistencia
- Registro de auditoria en `ActualizacionPrecio`

**Criterios de aceptacion:**
- El boton aparece solo para admins en cada fila de la tabla
- Al hacer click, se abre el modal con los datos del producto
- Se puede ingresar un nuevo precio de venta y ver el preview en tiempo real
- Al guardar, se actualiza el producto y se registra la auditoria
- Al cancelar, no se modifica nada
- Mensaje flash de confirmacion post-guardado

### Fase 2: Modo porcentaje y mejoras de UX

**Estimacion:** 0.5 dia de desarrollo

**Alcance:**
- Agregar toggle de modo (directo / porcentaje) al modal
- JavaScript para calculo en modo porcentaje
- Validaciones de edge cases (precio <= 0, porcentaje extremo, costo en 0)
- Warnings visuales (precio menor al costo, margen negativo)
- Refrescar fila o tabla post-guardado sin recarga completa (HTMX swap)
- Guardar el porcentaje en `ActualizacionPrecio.porcentaje` cuando se usa ese modo

**Criterios de aceptacion:**
- Se puede alternar entre modo directo y porcentaje
- Ambos modos calculan correctamente costo, venta, margen y precio con IVA
- Las validaciones previenen guardar precios invalidos
- La tabla se actualiza sin recargar la pagina completa

---

## Validacion contra el codebase

| Aspecto | Estado | Detalle |
|---------|--------|---------|
| Modelo `Producto` tiene `precio_costo` y `precio_venta` | Verificado | `Numeric(12,2)` — lineas 31-32 de `producto.py` |
| Propiedad `margen_ganancia` existe | Verificado | Lineas 58-63 de `producto.py` — calcula `((venta - costo) / costo) * 100` |
| `iva_porcentaje` existe en el modelo | Verificado | `Numeric(5,2)`, default `Decimal('21')` — linea 33 de `producto.py` |
| `ActualizacionPrecio` soporta tipo `'manual'` | Verificado | Campo `tipo` es `String(10)`, default `'masiva'`, comentario dice `'masiva' o 'manual'` — linea 17 de `actualizacion_precio.py` |
| `ActualizacionPrecio.porcentaje` es nullable | Verificado | `Numeric(8,4), nullable=True` — linea 18 de `actualizacion_precio.py` |
| `Categoria.nombre_completo` retorna "Padre > Hijo" | Verificado | Lineas 54-58 de `categoria.py` |
| Decoradores de auth: `@admin_required` existe | Verificado | Importado en `productos.py` desde `app/utils/decorators` — linea 13 |
| `es_peticion_htmx()` existe | Verificado | Importado en `productos.py` — linea 14, usado en `index()` y `toggle_activo()` |
| Patron de modal existente | Verificado | `components/modal_confirm.html` y `clientes/_modal_cumpleanos.html` usan Bootstrap 5 + Material Symbols |
| Tabla de productos tiene columna "Acciones" | Verificado | `_tabla.html` lineas 44-53 con `div.action-icons` |
| `Producto.get_o_404()` existe | Verificado | Usado en `detalle()`, `editar()`, `toggle_activo()` — heredado de `EmpresaMixin` |
| `EmpresaMixin` valida que el producto pertenezca a la empresa | Verificado | `get_o_404` filtra por `empresa_id` — patron multi-tenant consistente |
