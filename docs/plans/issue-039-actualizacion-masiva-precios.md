# Issue #039 — Actualización masiva de precio por categoría

| Campo        | Valor                                            |
|--------------|--------------------------------------------------|
| **Issue**    | #039                                             |
| **Título**   | Actualización masiva de precio por categoría     |
| **Fecha**    | 2026-04-06                                       |
| **Complejidad** | Alta — nuevo modelo, servicio, 3 rutas, 3 templates, JS interactivo, audit trail |
| **Rama**     | `feature/039-actualizacion-masiva-precios`       |

---

## Índice

1. [Estado actual](#1-estado-actual)
2. [Requisitos funcionales](#2-requisitos-funcionales)
3. [Escenarios y casos borde](#3-escenarios-y-casos-borde)
4. [Diseño técnico](#4-diseño-técnico)
   - 4.1 [Nuevo modelo: ActualizacionPrecio](#41-nuevo-modelo-actualizacionprecio)
   - 4.2 [Migración](#42-migración)
   - 4.3 [Registro del modelo](#43-registro-del-modelo)
   - 4.4 [Servicio](#44-servicio-actualizacion_precio_servicepy)
   - 4.5 [Formulario](#45-formulario)
   - 4.6 [Rutas](#46-rutas)
   - 4.7 [Templates y UI](#47-templates-y-ui)
   - 4.8 [Navegación](#48-navegación)
   - 4.9 [Flujo de datos completo](#49-flujo-de-datos-completo)
5. [Consideraciones técnicas](#5-consideraciones-técnicas)
6. [Archivos a crear y modificar](#6-archivos-a-crear-y-modificar)
7. [Evaluación de riesgo](#7-evaluación-de-riesgo)
8. [Plan de testing](#8-plan-de-testing)
9. [Tasks por fase](#9-tasks-por-fase)
10. [Criterios de aceptación](#10-criterios-de-aceptación)

---

## 1. Estado actual

### Modelos existentes relevantes

- **`Producto`**: tiene `precio_costo` (`Numeric(12,2)`), `precio_venta` (`Numeric(12,2)`), `categoria_id` (FK a categorías). Hereda `EmpresaMixin` (multi-tenant con `empresa_id`).
- **`Categoria`**: tiene `padre_id` (self-referencial), `subcategorias` (relationship), `productos` (relationship dynamic). Propiedades: `es_padre`, `nombre_completo`, `cantidad_productos_total`.
- La jerarquía es de **2 niveles**: padre (`padre_id=None`) e hijos (`padre_id=padre.id`).
- **`EmpresaMixin`** provee `query_empresa()` y `get_o_404()` para filtrado multi-tenant.

### Problema

FerrERP maneja 1000+ productos. Actualmente los precios se actualizan **uno a uno** desde el formulario de edición de producto. Se necesita una herramienta para actualizar precios masivamente por categoría, con trazabilidad completa (audit trail).

---

## 2. Requisitos funcionales

### R1 — Selección de categoría

- El usuario selecciona una categoría (padre o hija) de un selector jerárquico.
- El selector muestra categorías activas de la empresa del usuario.
- Formato: `"Padre > Hijo"` para subcategorías, solo nombre para padres.

### R2 — Porcentaje de actualización

- Input numérico para porcentaje (positivo = aumento, negativo = descuento).
- Permite decimales (ej: `15.5%`).
- Rango permitido: **-99.99% a 999.99%** (no se permite -100% ni menor, que dejaría precio en 0 o negativo).

### R3 — Inclusión de subcategorías

- Si se selecciona una categoría **padre**: checkbox "Incluir subcategorías" (marcado por defecto).
- Si se desmarca: solo afecta productos directamente en la categoría padre.
- Si se selecciona una categoría **hija**: no se muestra el checkbox, solo afecta esa subcategoría.

### R4 — Control de precio de costo

- Por defecto se actualizan **AMBOS** precios (costo y venta).
- Checkbox "Actualizar precio de costo" (marcado por defecto).
- Al desmarcar: **modal de doble confirmación** advirtiendo que el precio de costo quedará desactualizado y los márgenes serán incorrectos.
- Si confirma: solo se actualiza `precio_venta`.

### R5 — Vista previa

- Antes de aplicar, mostrar tabla con:

| Columna | Descripción |
|---------|-------------|
| Código | Código del producto |
| Nombre | Nombre del producto |
| P. Costo Actual | `precio_costo` actual |
| P. Costo Nuevo | Precio de costo calculado (o "Sin cambio") |
| P. Venta Actual | `precio_venta` actual |
| P. Venta Nuevo | Precio de venta calculado |
| Diferencia | Diferencia monetaria |

- Si no se actualiza costo: columnas de costo muestran **"Sin cambio"**.
- Cantidad total de productos afectados.
- Solo productos **activos** se incluyen en la actualización.

### R6 — Aplicación de cambios

- Botón "Aplicar cambios" con confirmación final.
- Todos los cambios en una **sola transacción** de BD.
- Flash message con resumen: `"Se actualizaron X productos de la categoría Y con un Z%"`.

### R7 — Historial de precios (audit trail)

- Cada producto tiene una sección "Historial de Precios" en su página de detalle.
- Cada registro muestra: fecha, usuario, tipo (masiva/manual), porcentaje, precios anteriores, precios nuevos, categoría (si fue masiva), notas.
- Ordenado por fecha descendente.

---

## 3. Escenarios y casos borde

### Escenarios principales

**E1 — Categoría padre con subcategorías incluidas**
Usuario selecciona "Herramientas" (padre), 15%, incluir subcategorías ON.
Se actualizan todos los productos activos en "Herramientas" y en todas sus subcategorías ("Herramientas > Manuales", "Herramientas > Eléctricas", etc.).

**E2 — Categoría padre sin subcategorías**
Usuario selecciona "Herramientas" (padre), 15%, incluir subcategorías OFF.
Solo se actualizan productos directamente asignados a "Herramientas" (no los de subcategorías).

**E3 — Subcategoría específica**
Usuario selecciona "Herramientas > Manuales" (hija), -10%.
Solo se actualizan productos de esa subcategoría.

**E4 — Solo precio de venta**
Usuario desmarca "Actualizar precio de costo", confirma modal de advertencia.
Solo se modifica `precio_venta`. El audit trail registra que `precio_costo` no fue modificado.

**E5 — Vista previa con categoría vacía**
Usuario selecciona categoría sin productos activos. Se muestra mensaje "No hay productos activos en esta categoría" y el botón de aplicar queda deshabilitado.

### Casos borde

| Caso | Comportamiento |
|------|----------------|
| **Porcentaje 0%** | Se permite pero se muestra advertencia: "El porcentaje es 0%, no se realizarán cambios" |
| **Descuento que deja precio en 0 o negativo** | Se rechaza con error. Validar ANTES de aplicar que ningún producto quede con `precio <= 0` |
| **Producto con `precio_costo = 0`** | Se permite la actualización (`0 * X% = 0`), pero se muestra advertencia en la preview |
| **Categoría con productos activos e inactivos** | Solo se actualizan los activos, los inactivos se ignoran |
| **Redondeo** | Los precios se redondean a 2 decimales usando `ROUND_HALF_UP` |
| **Concurrencia** | La transacción usa `SELECT FOR UPDATE` para evitar actualizaciones concurrentes |

---

## 4. Diseño técnico

### 4.1 Nuevo modelo: ActualizacionPrecio

**Archivo:** `app/models/actualizacion_precio.py`

```python
class ActualizacionPrecio(EmpresaMixin, db.Model):
    __tablename__ = 'actualizaciones_precio'

    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=ahora_argentina)
    tipo = db.Column(
        db.Enum('masiva', 'manual', name='tipo_actualizacion_precio'),
        nullable=False
    )
    porcentaje = db.Column(db.Numeric(8, 4), nullable=True)  # permite decimales finos
    precio_costo_anterior = db.Column(db.Numeric(12, 2), nullable=False)
    precio_costo_nuevo = db.Column(db.Numeric(12, 2), nullable=False)
    precio_venta_anterior = db.Column(db.Numeric(12, 2), nullable=False)
    precio_venta_nuevo = db.Column(db.Numeric(12, 2), nullable=False)
    actualizo_costo = db.Column(db.Boolean, nullable=False, default=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias.id'), nullable=True)
    notas = db.Column(db.Text, nullable=True)

    # Relaciones
    producto = db.relationship('Producto', backref=db.backref(
        'actualizaciones_precio', lazy='dynamic', order_by='ActualizacionPrecio.fecha.desc()'
    ))
    usuario = db.relationship('Usuario')
    categoria = db.relationship('Categoria')
```

**Notas de diseño:**
- `tipo='masiva'` para actualizaciones por categoría, `tipo='manual'` reservado para futuro tracking de ediciones individuales.
- `actualizo_costo=False` cuando el usuario desmarca el checkbox.
- `porcentaje` es `Numeric(8,4)` para guardar con precisión (ej: `15.5000`).
- Multi-tenant vía `EmpresaMixin` (`empresa_id`).

### 4.2 Migración

**Archivo:** `migrations/versions/0010_actualizacion_precio.py`

| Propiedad | Valor |
|-----------|-------|
| Revisión | `0010` |
| Down revision | `0009` |
| Operaciones upgrade | Crear enum `tipo_actualizacion_precio` (`masiva`, `manual`), crear tabla `actualizaciones_precio` |
| Índices | `producto_id`, `empresa_id`, `fecha` |
| Operaciones downgrade | Drop tabla, drop enum |

### 4.3 Registro del modelo

**Archivo:** `app/models/__init__.py`

- Agregar import: `from .actualizacion_precio import ActualizacionPrecio`
- Agregar a `__all__`: `'ActualizacionPrecio'`

### 4.4 Servicio: actualizacion_precio_service.py

**Archivo:** `app/services/actualizacion_precio_service.py`

#### Función `obtener_productos_por_categoria`

```python
def obtener_productos_por_categoria(categoria_id, incluir_subcategorias=True):
    """Retorna productos activos de la empresa filtrados por categoría.

    Si incluir_subcategorias=True y es categoría padre, incluye productos
    de todas las subcategorías.
    Usa Categoria.get_o_404() y Producto.query_empresa().
    Si es padre e incluir_subcategorias: filtra por lista de IDs (padre + hijos).
    Solo productos activos.
    Retorna query ordenada por nombre.
    """
```

#### Función `previsualizar_actualizacion`

```python
def previsualizar_actualizacion(productos, porcentaje, actualizar_costo=True):
    """Calcula precios nuevos sin aplicar cambios.

    Retorna lista de dicts con:
    - producto (obj)
    - precio_costo_anterior, precio_costo_nuevo
    - precio_venta_anterior, precio_venta_nuevo
    - diferencia_costo, diferencia_venta

    Calcula factor = 1 + Decimal(str(porcentaje)) / Decimal('100')
    Para cada producto: calcula precio nuevo con quantize ROUND_HALF_UP.
    Valida que ningún precio quede <= 0.
    Raises ValueError si algún precio quedaría en 0 o negativo.
    """
```

#### Función `aplicar_actualizacion`

```python
def aplicar_actualizacion(categoria_id, porcentaje, actualizar_costo=True,
                           incluir_subcategorias=True, notas=None):
    """Aplica actualización masiva de precios.

    1. Obtiene productos por categoría
    2. Valida precios resultantes
    3. En una transacción:
       a. Actualiza cada producto (con with_for_update() para concurrencia)
       b. Crea registro ActualizacionPrecio por cada producto
    4. Retorna cantidad de productos actualizados

    Usa current_user.id como usuario_id, current_user.empresa_id como empresa_id.
    Raises ValueError si no hay productos o si precios quedarían inválidos.
    """
```

**Patrones obligatorios:**
- Usar `Decimal(str(porcentaje))` para conversión segura.
- Factor = `1 + Decimal(str(porcentaje)) / Decimal('100')`
- Redondeo: `quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)`
- Multi-tenant: usar `Producto.query_empresa()` y `Categoria.get_o_404()`
- **NUNCA** usar `float`. Factor de multiplicación siempre como `Decimal`.

### 4.5 Formulario

**Archivo:** `app/forms/producto_forms.py` (agregar al existente)

```python
class ActualizacionMasivaPreciosForm(FlaskForm):
    categoria_id = SelectField('Categoría', coerce=int, validators=[DataRequired()])
    porcentaje = DecimalField('Porcentaje (%)', validators=[
        DataRequired(),
        NumberRange(min=-99.99, max=999.99)
    ])
    incluir_subcategorias = BooleanField('Incluir subcategorías', default=True)
    actualizar_costo = BooleanField('Actualizar precio de costo', default=True)
    notas = TextAreaField('Notas (opcional)')
```

**Choices de `categoria_id`** se cargan dinámicamente en `__init__` con formato jerárquico:

```python
[
    (0, '-- Seleccionar categoría --'),
    (1, 'Herramientas'),
    (3, '  Herramientas > Manuales'),
    (4, '  Herramientas > Eléctricas'),
    (2, 'Pinturas'),
    (5, '  Pinturas > Interior'),
]
```

### 4.6 Rutas

Se agregan al blueprint existente de productos (`app/routes/productos.py`) con prefijo `/productos/actualizacion-masiva`.

| Método | Ruta | Descripción | Decoradores |
|--------|------|-------------|-------------|
| `GET` | `/productos/actualizacion-masiva` | Página principal con formulario | `@login_required`, `@empresa_aprobada_required`, `@admin_required` |
| `POST` | `/productos/actualizacion-masiva/preview` | Partial HTMX con tabla de preview | `@login_required`, `@empresa_aprobada_required`, `@admin_required` |
| `POST` | `/productos/actualizacion-masiva/aplicar` | Aplica cambios, redirect con flash | `@login_required`, `@empresa_aprobada_required`, `@admin_required` |

**Ruta preview:**
- Recibe: `categoria_id`, `porcentaje`, `actualizar_costo`, `incluir_subcategorias`.
- Retorna partial `_preview_actualizacion.html`.

**Ruta aplicar:**
- Aplica los cambios vía servicio.
- Redirect a `/productos` con flash message de resumen.

**Ruta detalle (modificar):**
- Cargar últimas 20 actualizaciones de precio del producto.
- Pasar al template como variable `actualizaciones_precio`.

### 4.7 Templates y UI

#### 4.7.1 Página principal: `actualizacion_masiva.html`

**Archivo:** `app/templates/productos/actualizacion_masiva.html`

- Extiende `base.html`.
- Card con formulario:
  - Select jerárquico de categorías.
  - Input porcentaje con addon `%`.
  - Checkbox "Incluir subcategorías" (visible solo cuando se selecciona padre, vía JS).
  - Checkbox "Actualizar precio de costo" (marcado por defecto).
  - Textarea notas.
  - Botón "Previsualizar" (HTMX POST a `/preview`).
- Div target para tabla de preview (se carga vía HTMX).
- Botón "Aplicar cambios" (aparece después de preview, con confirmación).

#### 4.7.2 Partial preview: `_preview_actualizacion.html`

**Archivo:** `app/templates/productos/_preview_actualizacion.html`

- Tabla responsiva con datos de preview.
- Filas con colores: **verde** si aumento, **rojo** si descuento.
- Footer con total de productos afectados.
- Botón "Aplicar cambios" con confirmación JS.
- Mensajes de advertencia (precios en 0, categoría vacía, etc.).

#### 4.7.3 Modal de confirmación de costo

JavaScript en el template principal:

- Bootstrap modal que aparece al desmarcar "Actualizar precio de costo".
- Texto: *"ATENCIÓN: Si no actualiza el precio de costo, los márgenes de ganancia quedarán desactualizados. Esto puede generar información incorrecta en reportes de rentabilidad."*
- Botones: **"Entiendo, continuar"** y **"Cancelar"**.
- Si cancela: re-marca el checkbox.

#### 4.7.4 Sección historial en detalle de producto

**Archivo:** `app/templates/productos/detalle.html` (modificar)

- Nueva card debajo de las existentes: **"Historial de Precios"**.
- Tabla con: Fecha, Usuario, Tipo, %, P. Costo Ant., P. Costo Nuevo, P. Venta Ant., P. Venta Nuevo, Notas.
- Si no hay registros: *"No hay historial de actualizaciones de precios"*.
- Limitado a últimos 20 registros con link "ver más".

### 4.8 Navegación

- Agregar link en la página de productos (`index.html`): botón **"Actualizar Precios"** con ícono `price_change` (Material Symbols).
- Solo visible para administradores: `{% if current_user.es_administrador %}`.

### 4.9 Flujo de datos completo

```
1. Admin navega a /productos/actualizacion-masiva
2. Selecciona categoría, ingresa %, configura opciones
3. Click "Previsualizar" → HTMX POST a /preview
4. Servicio calcula precios nuevos, retorna partial con tabla
5. Admin revisa la tabla de preview
6. Click "Aplicar cambios" → Confirmación JS
7. POST a /aplicar
8. Servicio en transacción:
   a. Para cada producto: SELECT FOR UPDATE
   b. Actualiza precios en el producto
   c. Crea registro ActualizacionPrecio
   d. Commit
9. Redirect a /productos con flash success:
   "Se actualizaron X productos de la categoría Y con un Z%"
```

---

## 5. Consideraciones técnicas

| Aspecto | Detalle |
|---------|---------|
| **Rendimiento** | Con 1000+ productos, la preview puede ser pesada. Limitar a 500 productos por página en preview, con indicador de total. |
| **Concurrencia** | Usar `with_for_update()` en la query de aplicación para bloquear filas durante update. |
| **Rollback** | Si falla cualquier producto, se hace rollback de toda la transacción. |
| **Decimal** | NUNCA usar `float`. Factor de multiplicación siempre como `Decimal`. |
| **CSRF** | El form hereda de `FlaskForm`, CSRF incluido automáticamente. |
| **Multi-tenant** | Todos los queries filtran por `empresa_id` vía `query_empresa()` y `get_o_404()`. |

---

## 6. Archivos a crear y modificar

### Archivos a crear

| Archivo | Descripción |
|---------|-------------|
| `app/models/actualizacion_precio.py` | Modelo `ActualizacionPrecio` con audit trail |
| `app/services/actualizacion_precio_service.py` | Servicio con lógica de negocio (obtener, previsualizar, aplicar) |
| `migrations/versions/0010_actualizacion_precio.py` | Migración: tabla + enum + índices |
| `app/templates/productos/actualizacion_masiva.html` | Página principal con formulario y JS interactivo |
| `app/templates/productos/_preview_actualizacion.html` | Partial HTMX con tabla de preview |
| `tests/test_actualizacion_precios.py` | Tests completos (modelo, servicio, rutas, multi-tenant) |

### Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `app/models/__init__.py` | Agregar import `ActualizacionPrecio` y entrada en `__all__` |
| `app/forms/producto_forms.py` | Agregar clase `ActualizacionMasivaPreciosForm` |
| `app/routes/productos.py` | Agregar 3 rutas nuevas + modificar `detalle()` para cargar historial |
| `app/templates/productos/detalle.html` | Agregar sección "Historial de Precios" |
| `app/templates/productos/index.html` | Agregar botón "Actualizar Precios" (solo admin) |

---

## 7. Evaluación de riesgo

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Actualización masiva con porcentaje incorrecto daña precios | Media | Alto | Vista previa obligatoria + confirmación doble + audit trail para revertir |
| Precios quedan en 0 o negativos | Baja | Alto | Validación estricta antes de aplicar (`precio <= 0` → rechazar) |
| Concurrencia: dos admins actualizan la misma categoría simultáneamente | Baja | Medio | `SELECT FOR UPDATE` en la transacción |
| Performance con 1000+ productos en preview | Media | Bajo | Paginación en preview (500 productos por página) |
| Pérdida de datos por error en transacción | Baja | Alto | Transacción atómica con rollback completo |
| Márgenes incorrectos al no actualizar costo | Media | Medio | Modal de doble confirmación con advertencia explícita |

---

## 8. Plan de testing

### Tests del modelo

- Creación de `ActualizacionPrecio` con todos los campos.
- Verificar relaciones: `producto`, `usuario`, `categoría`.
- Verificar backref: `producto.actualizaciones_precio`.

### Tests del servicio

| Test | Descripción |
|------|-------------|
| Categoría padre con subcategorías | Verifica que se incluyen productos de padre + hijos |
| Categoría padre sin subcategorías | Verifica que solo se incluyen productos directos del padre |
| Solo precio de venta | Verifica que `precio_costo` no cambia, `actualizo_costo=False` |
| Validación precio negativo/cero | Verifica `ValueError` cuando descuento dejaría `precio <= 0` |
| Porcentaje 0% | Verifica que los precios no cambian pero la operación es válida |
| Categoría sin productos | Verifica `ValueError` indicando que no hay productos |
| Redondeo ROUND_HALF_UP | Verifica que `$10.005` → `$10.01` (no `$10.00`) |
| Creación de registros audit | Verifica que se crea un `ActualizacionPrecio` por cada producto |

### Tests de rutas

| Test | Descripción |
|------|-------------|
| Acceso admin | Admin puede acceder a `/productos/actualizacion-masiva` (200) |
| Acceso vendedor | Vendedor recibe 403 |
| Preview retorna datos | POST a `/preview` retorna tabla con productos y precios calculados |
| Aplicar crea registros | POST a `/aplicar` crea registros `ActualizacionPrecio` y actualiza precios |

### Tests multi-tenant

- Verificar que no se ven ni actualizan productos de otra empresa.

---

## 9. Tasks por fase

### Fase 1: Modelo y migración

- [ ] **T1.1** Crear modelo `ActualizacionPrecio` en `app/models/actualizacion_precio.py`
  - Campos: `id`, `producto_id` (FK), `usuario_id` (FK), `fecha`, `tipo` (enum masiva/manual), `porcentaje` (Numeric 8,4), `precio_costo_anterior`, `precio_costo_nuevo`, `precio_venta_anterior`, `precio_venta_nuevo` (todos Numeric 12,2), `actualizo_costo` (Boolean), `categoria_id` (FK nullable), `notas` (Text nullable), `empresa_id` (vía EmpresaMixin)
  - Relaciones: `producto` (backref `actualizaciones_precio`), `usuario`, `categoria`
- [ ] **T1.2** Registrar modelo en `app/models/__init__.py`
  - Import `ActualizacionPrecio`
  - Agregar a `__all__`
- [ ] **T1.3** Crear migración `migrations/versions/0010_actualizacion_precio.py`
  - Revisión `0010`, down_revision `0009`
  - Crear enum `tipo_actualizacion_precio`
  - Crear tabla `actualizaciones_precio` con todos los campos e índices
  - downgrade: drop table, drop enum

### Fase 2: Servicio

- [ ] **T2.1** Crear `app/services/actualizacion_precio_service.py`
  - Función `obtener_productos_por_categoria(categoria_id, incluir_subcategorias=True)`
    - Usa `Categoria.get_o_404()` y `Producto.query_empresa()`
    - Si es padre e `incluir_subcategorias`: filtra por lista de IDs (padre + hijos)
    - Solo productos activos
    - Retorna query ordenada por nombre
- [ ] **T2.2** Función `previsualizar_actualizacion(productos, porcentaje, actualizar_costo=True)`
  - Calcula `factor = 1 + Decimal(str(porcentaje)) / Decimal('100')`
  - Para cada producto: calcula precio nuevo con `quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)`
  - Valida que ningún precio quede `<= 0`
  - Retorna lista de dicts con datos para la tabla preview
  - `raise ValueError` si precio inválido
- [ ] **T2.3** Función `aplicar_actualizacion(categoria_id, porcentaje, actualizar_costo, incluir_subcategorias, notas)`
  - Obtiene productos, valida, en transacción: actualiza precios y crea registros `ActualizacionPrecio`
  - Usa `with_for_update()` para concurrencia
  - `current_user.id` como `usuario_id`, `current_user.empresa_id` como `empresa_id`
  - Retorna cantidad de productos actualizados

### Fase 3: Formulario y rutas

- [ ] **T3.1** Agregar `ActualizacionMasivaPreciosForm` en `app/forms/producto_forms.py`
  - Fields: `categoria_id` (SelectField), `porcentaje` (DecimalField), `incluir_subcategorias` (BooleanField), `actualizar_costo` (BooleanField), `notas` (TextAreaField)
  - Choices jerárquicas en `__init__` cargadas desde `Categoria.query_empresa()`
  - Validación: porcentaje entre -99.99 y 999.99
- [ ] **T3.2** Agregar rutas en `app/routes/productos.py`
  - `GET /productos/actualizacion-masiva` → página con formulario (`@admin_required`)
  - `POST /productos/actualizacion-masiva/preview` → partial HTMX con tabla preview
  - `POST /productos/actualizacion-masiva/aplicar` → aplica cambios, redirect con flash

### Fase 4: Templates y UI

- [ ] **T4.1** Crear `app/templates/productos/actualizacion_masiva.html`
  - Extiende `base.html`
  - Card con formulario: select categoría, input porcentaje, checkboxes, notas
  - Div target para preview HTMX
  - JavaScript: toggle visibilidad checkbox subcategorías según tipo categoría seleccionada
  - JavaScript: modal doble confirmación al desmarcar "Actualizar precio de costo"
- [ ] **T4.2** Crear `app/templates/productos/_preview_actualizacion.html`
  - Tabla responsiva con datos de preview
  - Colores: verde aumento, rojo descuento
  - Footer con conteo total
  - Botón "Aplicar cambios" con confirmación JS
  - Mensajes de advertencia (precios en 0, categoría vacía, etc.)
- [ ] **T4.3** Agregar sección historial de precios en `app/templates/productos/detalle.html`
  - Nueva card "Historial de Precios" debajo de las existentes
  - Tabla con: Fecha, Usuario, Tipo, %, Precios anteriores/nuevos, Notas
  - Mensaje si no hay historial
  - Limitar a últimos 20 registros
- [ ] **T4.4** Agregar botón "Actualizar Precios" en `app/templates/productos/index.html`
  - Solo visible para admin (`{% if current_user.es_administrador %}`)
  - Ícono Material Symbols: `price_change`
  - Link a `/productos/actualizacion-masiva`

### Fase 5: Ruta detalle — cargar historial

- [ ] **T5.1** Modificar ruta `detalle()` en `app/routes/productos.py`
  - Cargar últimas 20 actualizaciones de precio del producto
  - Pasar al template como variable `actualizaciones_precio`

### Fase 6: Tests

- [ ] **T6.1** Crear `tests/test_actualizacion_precios.py`
  - Test modelo `ActualizacionPrecio` (creación, relaciones)
  - Test servicio: actualización con categoría padre con/sin subcategorías
  - Test servicio: actualización solo precio venta
  - Test servicio: validación precio negativo/cero
  - Test servicio: porcentaje 0%
  - Test servicio: categoría sin productos
  - Test ruta: acceso admin vs vendedor (403)
  - Test ruta: preview retorna datos correctos
  - Test ruta: aplicar crea registros y actualiza precios
  - Test multi-tenant: no se ven productos de otra empresa

### Orden de implementación

```
Fase 1 → Fase 2 → Fase 3 → Fase 4 → Fase 5 → Fase 6
```

Cada fase puede ser un commit independiente. Se recomienda hacer un PR con todas las fases juntas para review.

---

## 10. Criterios de aceptación

- [ ] **AC1**: Se puede seleccionar cualquier categoría (padre o hija) y aplicar un porcentaje
- [ ] **AC2**: Al seleccionar padre, checkbox de subcategorías aparece y funciona
- [ ] **AC3**: Al desmarcar "Actualizar precio de costo", aparece modal de doble confirmación
- [ ] **AC4**: La vista previa muestra todos los productos afectados con precios actuales y nuevos
- [ ] **AC5**: Los cambios se aplican correctamente con redondeo a 2 decimales
- [ ] **AC6**: Se crea un registro de audit trail por cada producto modificado
- [ ] **AC7**: La sección de historial aparece en el detalle del producto
- [ ] **AC8**: Solo productos activos son afectados
- [ ] **AC9**: Filtrado multi-tenant funciona correctamente (`empresa_id`)
- [ ] **AC10**: No se permite dejar precios en 0 o negativos
- [ ] **AC11**: Solo administradores pueden acceder a esta funcionalidad
