# Feature: Persistir Búsqueda y Filtros en Tablas

## Resumen ejecutivo

Esta feature resuelve el problema de que al navegar al detalle o edición de una entidad (producto, cliente, venta, presupuesto, inventario) y volver a la lista, se pierden la búsqueda, los filtros aplicados y la página actual. El usuario tiene que volver a buscar y navegar a la página donde estaba.

La solución recomendada es **persistir el estado de búsqueda en la URL** usando `hx-push-url` y `hx-replace-url` de HTMX, lo cual se integra naturalmente con el stack actual sin agregar JavaScript custom ni estado server-side adicional.

---

## Contexto y problema de negocio

### Situación actual

El usuario entra a Productos, busca "tornillo", navega a la página 3, hace clic en un producto para ver o editar, y al volver (botón atrás o link "Volver a Productos") vuelve a la lista **vacía** — sin búsqueda, sin filtros, en la página 1. Tiene que repetir todo el proceso.

Esto sucede porque:

1. **Las búsquedas HTMX no actualizan la URL del navegador.** Los inputs con `hx-get` reemplazan el contenido del DOM pero la URL queda en `/productos`. No se guarda el estado `?q=tornillo&categoria=5&page=3`.
2. **La paginación HTMX usa `hx-push-url="false"` explícitamente.** El componente `pagination.html` (línea 13 y 38) desactiva el push de URL al cambiar de página.
3. **Los links a detalle/edición son `<a href>` normales**, lo cual navega fuera de la página y el estado DOM (incluidos los valores de los inputs HTMX) se pierde.
4. **Los formularios de ventas y presupuestos usan `method="GET"` con submit**, lo cual SÍ actualiza la URL, pero al volver la página se recarga desde cero.

### Impacto

En una ferretería con 500+ productos, el usuario necesita buscar y filtrar constantemente. Perder la búsqueda al ver un detalle obliga a repetir la operación decenas de veces al día. Es una fuente significativa de fricción.

---

## Análisis del codebase actual

### Páginas afectadas y su comportamiento actual

| Página | Búsqueda | Filtros | Paginación | Mecanismo actual | URL refleja estado? |
|--------|----------|---------|------------|------------------|---------------------|
| **Productos** (`/productos`) | `q` (HTMX keyup) | `categoria`, `activos`, `bajo_stock` (HTMX change) | HTMX (`hx-push-url="false"`) | Inputs disparan `hx-get` a ruta `productos.tabla`, reemplazan `#tabla-productos` | NO |
| **Clientes** (`/clientes`) | `q` (HTMX keyup) | `activos` (HTMX change) | HTMX (sin push-url, pero usa `_tabla.html` sin variable `htmx`) | Input dispara `hx-get` a `clientes.index`, reemplaza `#tabla-clientes` | NO |
| **Inventario** (`/inventario`) | `q` (form submit) | `bajo_minimo` (form submit) | Non-HTMX (links normales en pagination) | Form con botón "Filtrar", submit GET. Ruta detecta `es_peticion_htmx()` para AJAX | PARCIAL (solo al hacer submit) |
| **Ventas** (`/ventas/historial`) | No hay buscador de texto libre | `fecha_desde`, `fecha_hasta`, `estado`, `cliente` (form submit) | Non-HTMX | Form con botón "Filtrar", submit GET | SI (al filtrar) |
| **Presupuestos** (`/presupuestos`) | `q` (form submit) | `estado`, `fecha_desde`, `fecha_hasta` (form submit) | Non-HTMX | Form con botón "Filtrar", submit GET | SI (al filtrar) |

### Patrones técnicos identificados

#### Patrón 1: Búsqueda HTMX sin push a URL (Productos, Clientes)

```html
<!-- productos/index.html -->
<input type="text" name="q" class="form-control"
       value="{{ busqueda }}"
       hx-get="{{ url_for('productos.tabla') }}"
       hx-trigger="keyup changed delay:300ms"
       hx-target="#tabla-productos"
       hx-include="[name='categoria'], [name='activos'], [name='bajo_stock']">
```

- El `hx-get` va a una ruta separada (`productos.tabla`) que retorna el partial `_tabla.html`.
- NO hay `hx-push-url`, por lo que la URL del navegador no cambia.
- El componente `pagination.html` cuando se usa en modo HTMX tiene `hx-push-url="false"` explícito.

#### Patrón 2: Form submit GET (Ventas, Presupuestos, Inventario)

```html
<!-- presupuestos/index.html -->
<form method="GET" class="row g-3 align-items-end">
    <input type="text" name="q" ...>
    <button type="submit">Filtrar</button>
</form>
```

- El submit actualiza la URL con query params: `/presupuestos?q=foo&estado=pendiente`.
- Al volver con el botón atrás del navegador, la URL tiene los params pero el navegador hace un full reload.

#### Patrón 3: Rutas con respuesta condicional HTMX

```python
# clientes.py
def index():
    ...
    if es_peticion_htmx():
        return render_template('clientes/_tabla.html', ...)
    return render_template('clientes/index.html', ...)
```

- Las rutas `clientes.index`, `inventario.index` y `productos.tabla` detectan si es HTMX y retornan un partial.
- Productos tiene una ruta separada `productos.tabla` para el partial; clientes e inventario reusan la misma ruta `index`.

#### Patrón 4: Paginación con preservación de args

```html
<!-- components/pagination.html -->
{% set _args = dict(request.view_args, **request.args.to_dict(flat=true)) %}
{% set _ = _args.pop('page', none) %}
<!-- Luego usa url_for(request.endpoint, page=X, **_args) -->
```

- El componente de paginación YA preserva los query params existentes al construir los links de página.
- Pero al estar en modo HTMX con `hx-push-url="false"`, esos params no se reflejan en la URL del navegador.

#### Precedente: localStorage en el proyecto

- `categorias.html` usa `localStorage` para persistir el estado de collapse de categorías.
- `punto_venta.html` usa `localStorage` para persistir el carrito de venta.
- Hay precedente para usar almacenamiento del lado del cliente.

---

## Opciones técnicas

### Opcion A: URL-based con `hx-push-url` / `hx-replace-url` (RECOMENDADA)

**Concepto**: Que cada interacción de búsqueda/filtro/paginación actualice la URL del navegador con los query params. Así, al volver con el botón atrás, la URL contiene el estado completo y la página se renderiza con los filtros aplicados.

**Cambios necesarios**:

1. **Agregar `hx-replace-url="true"` a los inputs de búsqueda y filtros HTMX** (Productos, Clientes).
   - Se usa `hx-replace-url` en vez de `hx-push-url` para no contaminar el historial con cada keystroke.

2. **Cambiar `hx-push-url="false"` a `hx-push-url="true"` en la paginación HTMX** (Productos, Clientes).
   - La paginación SÍ debería crear entradas en el historial (cambiar de página es una acción navegacional).

3. **Unificar las rutas de búsqueda HTMX para que generen URLs correctas**.
   - En Productos, el `hx-get` apunta a `productos.tabla` (ruta `/productos/tabla`), pero la URL que se muestra debería ser `/productos?q=...&page=...`. Hay dos opciones:
     - (a) Que el `hx-get` apunte a `productos.index` (que ya tiene `es_peticion_htmx()`) y el `hx-replace-url` genere la URL correcta automáticamente.
     - (b) Usar `hx-replace-url` con un valor calculado que apunte a `/productos?...`.

4. **Para las páginas con form submit (Ventas, Presupuestos, Inventario)**, no hace falta cambiar nada para la persistencia de filtros (ya usan GET y la URL se actualiza). Solo necesitan que la paginación preserve los params, lo cual YA hace el componente `pagination.html`.

**Pros**:
- Solución nativa de HTMX, cero JavaScript custom
- Funciona con el botón atrás del navegador
- URLs compartibles/bookmarkeables con filtros
- Funciona correctamente con múltiples pestañas (cada una tiene su propia URL)
- Se integra con el patrón existente de `request.args` en las rutas

**Contras**:
- Requiere cuidado con `hx-replace-url` vs `hx-push-url` para no contaminar el historial
- En Productos, hay que redireccionar el `hx-get` de los filtros de `productos.tabla` a `productos.index` (o manejar la URL de replace manualmente)

---

### Opcion B: sessionStorage / localStorage en JavaScript

**Concepto**: Guardar el estado de búsqueda en `sessionStorage` antes de navegar al detalle, y restaurarlo al volver a la lista.

**Cambios necesarios**:

1. Crear un módulo JS (`static/js/persistir-busqueda.js`) que:
   - Al cargar una página de lista, revise si hay estado guardado en `sessionStorage` y lo restaure.
   - Antes de navegar a un detalle, guarde el estado actual (q, filtros, página).
   - Al volver, dispare la búsqueda con los valores restaurados.

2. Interceptar los clicks en links de detalle/edición para guardar estado antes de navegar.

3. Decidir cuándo limpiar el estado (al cambiar de sección, al hacer "Limpiar filtros", etc.).

**Pros**:
- No cambia la URL del navegador
- Funciona sin modificar las rutas Python
- Hay precedente en el proyecto (localStorage en categorías y POS)

**Contras**:
- Código JavaScript custom que hay que mantener
- No funciona con el botón atrás del navegador (la URL sigue siendo `/productos`)
- URLs no compartibles ni bookmarkeables
- Problemas con múltiples pestañas si se usa `localStorage` (estado compartido entre tabs)
- Si se usa `sessionStorage`, el estado se pierde al abrir en nueva pestaña
- Más frágil: depende de interceptar correctamente la navegación

---

### Opcion C: Estado server-side en sesión Flask

**Concepto**: Guardar los últimos filtros de cada página en `session['filtros_productos']`, etc.

**Cambios necesarios**:

1. Modificar cada ruta de lista para:
   - Guardar filtros en `session` al recibir una búsqueda.
   - Si llega sin params, leer de `session` y redireccionar con los params guardados.

2. Endpoint para limpiar los filtros guardados.

**Pros**:
- Funciona sin JavaScript
- Estado persistente incluso si el usuario cierra el navegador

**Contras**:
- Complejidad innecesaria: modifica 5+ rutas Python, agrega lógica de lectura/escritura de sesión
- Comportamiento confuso: la URL dice `/productos` pero muestra resultados filtrados
- Interferencia entre pestañas (la sesión es compartida)
- El estado "se pega" y el usuario no sabe por qué ve filtros que no aplicó
- Anti-patrón: oculta estado que debería ser explícito en la URL

---

## Recomendacion

**Opcion A: URL-based con `hx-push-url` / `hx-replace-url`.**

Razones:

1. **Es la solución más simple y nativa.** HTMX ya tiene esta funcionalidad; solo hay que activarla.
2. **El codebase ya está preparado.** Las rutas leen de `request.args`, los templates populan los inputs con los valores del server (`value="{{ busqueda }}"`), y la paginación ya preserva los query args.
3. **Cero JavaScript custom.** Solo agregar atributos HTML a los elementos existentes.
4. **URLs compartibles.** Un ferretero puede guardar un bookmark a `/productos?q=tornillo&categoria=5` y siempre ver sus tornillos.
5. **Funciona con el botón atrás** del navegador de forma natural.

---

## Cambios tecnicos necesarios

### Cambio 1: Productos — búsqueda y filtros con push a URL

**Archivos**: `app/templates/productos/index.html`, `app/routes/productos.py`

#### Template `index.html`

Agregar `hx-replace-url="true"` a todos los inputs/selects que disparan búsqueda HTMX, y cambiar el `hx-get` de `productos.tabla` a `productos.index` para que la URL reflejada sea `/productos?q=...`:

```html
<!-- Input de búsqueda -->
<input type="text" name="q" class="form-control"
       placeholder="Buscar por código o nombre..."
       value="{{ busqueda }}"
       hx-get="{{ url_for('productos.index') }}"
       hx-trigger="keyup changed delay:300ms"
       hx-target="#tabla-productos"
       hx-include="[name='categoria'], [name='activos'], [name='bajo_stock']"
       hx-replace-url="true">

<!-- Select de categoría -->
<select name="categoria" class="form-select" style="width: 200px;"
        hx-get="{{ url_for('productos.index') }}"
        hx-trigger="change"
        hx-target="#tabla-productos"
        hx-include="[name='q'], [name='activos'], [name='bajo_stock']"
        hx-replace-url="true">

<!-- Checkboxes: activos y bajo_stock (agregar hx-replace-url="true" a cada uno) -->
```

#### Ruta `productos.py`

Agregar detección `es_peticion_htmx()` en la ruta `index()` para retornar el partial `_tabla.html`, de la misma forma que ya lo hacen `clientes.index` e `inventario.index`:

```python
def index():
    # ... (query existente sin cambios) ...

    if es_peticion_htmx():
        return render_template(
            'productos/_tabla.html',
            productos=productos,
        )

    return render_template(
        'productos/index.html',
        # ... (sin cambios) ...
    )
```

**Nota**: La ruta `productos.tabla` puede mantenerse como fallback pero ya no sería usada por los filtros del `index.html`.

---

### Cambio 2: Clientes — búsqueda con push a URL

**Archivo**: `app/templates/clientes/index.html`

Agregar `hx-replace-url="true"` a los inputs de búsqueda y filtro:

```html
<input type="text" name="q" class="form-control" placeholder="Buscar cliente..."
       value="{{ busqueda }}" hx-get="{{ url_for('clientes.index') }}"
       hx-trigger="keyup changed delay:300ms" hx-target="#tabla-clientes"
       hx-replace-url="true">

<input type="checkbox" class="form-check-input" name="activos" value="1" id="activos"
       {% if solo_activos %}checked{% endif %} hx-get="{{ url_for('clientes.index') }}"
       hx-trigger="change" hx-target="#tabla-clientes"
       hx-include="[name='q']"
       hx-replace-url="true">
```

**Nota**: El checkbox de `activos` necesita `hx-include="[name='q']"` para que al cambiar el checkbox, el valor de búsqueda se incluya en la URL.

La ruta `clientes.index()` ya tiene la detección de `es_peticion_htmx()` y retorna `_tabla.html`, por lo que no requiere cambios en el backend.

---

### Cambio 3: Paginación HTMX — activar push a URL

**Archivo**: `app/templates/components/pagination.html`

Cambiar `hx-push-url="false"` por `hx-push-url="true"` en los links de paginación:

```html
<!-- Línea 13: Anterior -->
hx-push-url="true"

<!-- Línea 38: Páginas individuales -->
hx-push-url="true"
```

Esto hace que al cambiar de página, la URL se actualice a `/productos?q=tornillo&page=3`, lo cual permite volver a esa página exacta con el botón atrás.

---

### Cambio 4: Inventario — convertir a HTMX live search

**Archivos**: `app/templates/inventario/index.html`, `app/routes/inventario.py`

Actualmente el inventario usa un form con botón "Filtrar" (submit GET). Para mantener consistencia con productos y clientes, se puede convertir a búsqueda HTMX en vivo:

```html
<input type="text" name="q" class="form-control" placeholder="Buscar producto..."
       value="{{ busqueda }}"
       hx-get="{{ url_for('inventario.index') }}"
       hx-trigger="keyup changed delay:300ms"
       hx-target="#tabla-inventario"
       hx-include="[name='bajo_minimo']"
       hx-replace-url="true">

<input type="checkbox" class="form-check-input" name="bajo_minimo" value="1" id="bajo_minimo"
       {% if solo_bajo_minimo %}checked{% endif %}
       hx-get="{{ url_for('inventario.index') }}"
       hx-trigger="change"
       hx-target="#tabla-inventario"
       hx-include="[name='q']"
       hx-replace-url="true">
```

La ruta `inventario.index` ya tiene `es_peticion_htmx()` para retornar `_tabla_stock.html`.

**Alternativa**: Mantener el botón "Filtrar" pero agregar `hx-replace-url="true"` al form. En este caso, como el form ya hace submit GET y la URL se actualiza, el único problema es la paginación (que debe preservar los params, lo cual ya hace).

---

### Cambio 5: Ventas y Presupuestos — sin cambios necesarios

Las páginas de ventas (`historial`) y presupuestos (`index`) ya usan form submit GET, lo cual actualiza la URL con los query params. Al volver con el botón atrás, el navegador restaura la URL completa y la página se renderiza con los filtros.

**La paginación en estas páginas no usa HTMX** (usa links `<a href>` normales), por lo que al cambiar de página la URL ya se actualiza.

Verificación: La paginación usa `url_for(request.endpoint, page=X, **_args)` donde `_args` preserva todos los query params existentes. Esto ya funciona correctamente.

---

### Cambio 6 (opcional): Agregar `id="tabla-*"` donde falte

El inventario necesita que el contenedor de la tabla tenga un id para ser target de HTMX. Verificación:

| Página | ID del contenedor | Estado |
|--------|-------------------|--------|
| Productos | `#tabla-productos` | OK |
| Clientes | `#tabla-clientes` | OK |
| Inventario | Sin id | FALTA — agregar `id="tabla-inventario"` al `<div class="card-body p-0">` |

---

## Edge cases

| Caso | Comportamiento esperado |
|------|------------------------|
| Usuario busca, navega a detalle, vuelve con botón atrás | URL contiene `?q=tornillo&page=3`, el server renderiza la lista filtrada correctamente |
| Usuario busca, navega a detalle, vuelve con link "Productos" del menú | URL es `/productos` limpia, sin filtros. Esto es correcto: es una nueva navegación |
| Múltiples pestañas con diferentes búsquedas | Cada pestaña tiene su propia URL con sus params. No hay interferencia |
| Usuario escribe rápido en el buscador | `hx-replace-url` reemplaza la URL sin agregar entradas al historial, evitando contaminar el historial con cada keystroke |
| Cambio de página luego de búsqueda | `hx-push-url` agrega la nueva página al historial. El botón atrás vuelve a la página anterior |
| Limpiar búsqueda (borrar el texto del input) | `hx-replace-url` actualiza la URL a `/productos?q=&activos=1`, que es equivalente a sin filtro |
| Checkbox "Solo activos" desactivado | La URL refleja `activos=0`. Al volver, el checkbox aparece deseleccionado |
| Presupuestos: botón "Limpiar" | Navega a `/presupuestos` sin params, reseteando todos los filtros (ya funciona así) |
| Inventario: form submit actual | Si se convierte a HTMX, funciona igual. Si se mantiene el submit, la URL ya se actualiza |
| Bookmark de URL con filtros | El usuario puede guardar `/productos?q=tornillo&categoria=5` y siempre llegar a esa vista |
| URL con `page` mayor al total de páginas | Flask-SQLAlchemy/`paginar_query` devuelve la última página o vacío. Comportamiento existente sin cambios |

---

## Resumen de archivos a modificar

| Archivo | Cambio | Complejidad |
|---------|--------|-------------|
| `app/templates/productos/index.html` | Agregar `hx-replace-url="true"`, cambiar `hx-get` de `productos.tabla` a `productos.index` | Baja |
| `app/routes/productos.py` (ruta `index`) | Agregar bloque `if es_peticion_htmx(): return partial` | Baja |
| `app/templates/clientes/index.html` | Agregar `hx-replace-url="true"` y `hx-include` al checkbox | Baja |
| `app/templates/components/pagination.html` | Cambiar `hx-push-url="false"` → `"true"` (2 líneas) | Mínima |
| `app/templates/inventario/index.html` | Agregar `hx-get`, `hx-trigger`, `hx-target`, `hx-replace-url` a inputs + agregar `id` al contenedor | Baja |
| `app/templates/ventas/historial.html` | Sin cambios necesarios | Ninguna |
| `app/templates/presupuestos/index.html` | Sin cambios necesarios | Ninguna |

---

## Fases de implementacion

### Fase 1: Productos y Clientes (búsqueda HTMX)

- Agregar `hx-replace-url="true"` a los inputs/selects de `productos/index.html`
- Cambiar `hx-get` de `productos.tabla` a `productos.index` en los filtros
- Agregar bloque `es_peticion_htmx()` en ruta `productos.index()` para retornar partial
- Agregar `hx-replace-url="true"` y `hx-include` a inputs de `clientes/index.html`
- Cambiar `hx-push-url="false"` → `"true"` en `components/pagination.html`

**Criterios de aceptacion**:
- Al buscar en productos, la URL se actualiza a `/productos?q=...&categoria=...&activos=...`
- Al cambiar de página, la URL incluye `&page=N`
- Al volver con el botón atrás del navegador, la lista muestra los filtros y página correctos
- Al buscar en clientes, la URL se actualiza de la misma forma
- Los inputs muestran los valores correctos (ya lo hacen via `value="{{ busqueda }}"` del server)

### Fase 2: Inventario

- Agregar atributos HTMX a los inputs de `inventario/index.html`
- Agregar `id="tabla-inventario"` al contenedor de la tabla
- Verificar que la ruta `inventario.index` retorna el partial correcto con `es_peticion_htmx()`

**Criterios de aceptacion**:
- Búsqueda en vivo (sin botón "Filtrar") con actualización de URL
- Al volver del detalle de un producto, los filtros se mantienen

### Fase 3: Verificación de Ventas y Presupuestos

- Verificar que el flujo existente (form submit GET + paginación por links) funciona correctamente al volver con el botón atrás
- Si la paginación pierde filtros, agregar los query params a los links de paginación (pero el componente `pagination.html` ya los preserva)

**Criterios de aceptacion**:
- Al filtrar ventas por fecha y estado, navegar a un detalle, y volver, los filtros están presentes
- Idem para presupuestos

---

## Validacion contra el codebase

| Afirmación | Verificada? | Evidencia |
|-----------|-------------|-----------|
| `productos/index.html` usa `hx-get` apuntando a `productos.tabla` | SI | `index.html:31` — `hx-get="{{ url_for('productos.tabla') }}"` |
| `productos.tabla` es una ruta separada que retorna partial | SI | `productos.py:562` — `def tabla()` retorna `_tabla.html` |
| `productos.index` NO tiene `es_peticion_htmx()` | SI | `productos.py:30-90` — no hay detección HTMX |
| `clientes.index` SI tiene `es_peticion_htmx()` | SI | `clientes.py:62` — retorna `_tabla.html` |
| `inventario.index` SI tiene `es_peticion_htmx()` | SI | `inventario.py:47` — retorna `_tabla_stock.html` |
| Pagination usa `hx-push-url="false"` | SI | `pagination.html:13,38` |
| Pagination preserva query args existentes | SI | `pagination.html:2-3` — `dict(request.view_args, **request.args.to_dict())` |
| Ventas y presupuestos usan form submit GET | SI | `historial.html:17`, `presupuestos/index.html:17` — `method="GET"` |
| Proyecto usa HTMX 1.9.10 | SI | `base.html:71` — `htmx.org@1.9.10` |
| `hx-replace-url` disponible en HTMX 1.9.10 | SI | Introducido en HTMX 1.8.0 |
| Precedente de `localStorage` en el proyecto | SI | `categorias.html:289`, `punto_venta.html:761` |
| Inventario no tiene id en contenedor de tabla | SI | `inventario/index.html:53` — `<div class="card-body p-0">` sin id |
| Clientes no incluye `hx-include` en checkbox activos | SI | `clientes/index.html:40-41` — no tiene `hx-include` para `q` |
