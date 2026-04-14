# Importacion Masiva de Productos

## Resumen ejecutivo

Feature para importar productos de forma masiva mediante archivos Excel (.xlsx) o CSV (.csv). Permite a clientes nuevos migrar su catalogo de productos desde otro sistema o planilla hacia FerrERP sin cargar cada producto manualmente. El flujo sigue el patron existente de **preview - confirmar - aplicar** con validacion exhaustiva, resolucion automatica de categorias/proveedores y auditoria completa de la operacion.

Alcance: creacion y actualizacion masiva de productos con stock inicial, scoped por empresa (multi-tenant).

---

## Contexto y caso de uso

### Problema

Una ferreteria que migra a FerrERP puede tener entre 500 y 5000 productos cargados en otro sistema o en una planilla Excel. Cargarlos uno por uno desde el formulario de alta es inviable.

### Solucion

Proveer un mecanismo de importacion que:

1. Ofrezca una **plantilla estandarizada** con las columnas esperadas y ejemplos reales de productos de ferreteria.
2. **Valide** cada fila antes de tocar la base de datos, mostrando un preview claro con errores y advertencias.
3. **Resuelva** automaticamente relaciones (categorias por nombre, proveedores por nombre).
4. **Cree** los productos y registre movimientos de stock inicial de forma atomica.
5. **Audite** cada importacion con detalle de quien, cuando y cuantos productos.

### Usuarios objetivo

Solo usuarios con rol `administrador` y empresa aprobada.

---

## Plantilla Excel

### Columnas

| Columna | Tipo | Obligatoria | Descripcion | Valores validos / Restricciones |
|---|---|---|---|---|
| `codigo` | Texto | Si | Codigo interno del producto | Max 20 caracteres. Unico por empresa. |
| `codigo_barras` | Texto | No | Codigo de barras (EAN, UPC, etc.) | Max 50 caracteres. |
| `nombre` | Texto | Si | Nombre del producto | Max 100 caracteres. |
| `descripcion` | Texto | No | Descripcion larga | Sin limite practico. |
| `categoria` | Texto | No | Nombre de la categoria | Si no existe, se crea automaticamente. Formato `Padre > Hija` para subcategorias. |
| `unidad_medida` | Texto | No | Unidad de medida | `unidad`, `metro`, `kilo`, `litro`, `par`. Default: `unidad`. |
| `precio_costo` | Numero | Si | Precio de costo sin IVA | >= 0. Hasta 2 decimales. |
| `precio_venta` | Numero | Si | Precio de venta sin IVA | >= 0. Hasta 2 decimales. |
| `iva_porcentaje` | Numero | No | Alicuota de IVA | 0, 10.5, 21, 27. Default: 21. |
| `stock_actual` | Numero | No | Stock inicial a importar | >= 0. Entero para unidad/par. Hasta 3 decimales para metro/kilo/litro. Default: 0. |
| `stock_minimo` | Numero | No | Punto de reposicion | >= 0. Mismas reglas que stock_actual. Default: 0. |
| `proveedor` | Texto | No | Nombre del proveedor | Debe existir en el sistema. No se crea automaticamente. |
| `ubicacion` | Texto | No | Ubicacion en deposito/estanteria | Max 50 caracteres. |

### Ejemplo de plantilla con datos

| codigo | codigo_barras | nombre | descripcion | categoria | unidad_medida | precio_costo | precio_venta | iva_porcentaje | stock_actual | stock_minimo | proveedor | ubicacion |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CLV-4 | 7790001234567 | Clavo 4 pulgadas x kg | Clavo punta paris 4" | Clavos y Tornillos | kilo | 850.00 | 1275.00 | 21 | 150.500 | 20.000 | Acindar | A-01-03 |
| TORN-M6x30 | | Tornillo M6x30 zincado | Tornillo metrico cabeza hexagonal | Clavos y Tornillos > Tornillos | unidad | 12.50 | 22.00 | 21 | 500 | 100 | Bulonera Central | B-02-01 |
| PINT-LAT-4 | 7791234567890 | Latex interior blanco 4L | Pintura latex lavable | Pinturas > Latex | unidad | 4500.00 | 7200.00 | 21 | 30 | 5 | Alba | C-01-01 |
| LLAVE-12 | | Llave combinada 12mm | Acero cromo vanadio | Herramientas > Llaves | unidad | 1800.00 | 3200.00 | 21 | 25 | 5 | | D-03-02 |
| CAÑO-34 | | Caño PPF 3/4 x 4m | Caño termofusion agua fria | Plomeria > Caños | metro | 2100.00 | 3600.00 | 10.5 | 80.000 | 10.000 | Acqua System | E-01-04 |
| DISCO-115 | 7798765432100 | Disco corte 115x1.0 | Disco corte metal 115mm | Herramientas > Discos | unidad | 350.00 | 620.00 | 21 | 200 | 50 | Norton | D-04-01 |

### Notas de la plantilla

- La primera fila de la plantilla contiene los encabezados exactos (en minusculas, sin tildes).
- La segunda fila contiene un ejemplo que se debe eliminar antes de importar.
- La plantilla incluye una hoja adicional `instrucciones` con las reglas de validacion.
- El formato de categoria jerarquica usa ` > ` (espacio-mayor-espacio) como separador.

---

## Flujo de usuario paso a paso

### Paso 1: Acceso a la funcionalidad

```
+----------------------------------------------------------+
| FerrERP > Productos > Importar                           |
+----------------------------------------------------------+
|                                                          |
|  [icon] Importacion Masiva de Productos                  |
|                                                          |
|  Importa productos desde un archivo Excel o CSV.         |
|                                                          |
|  1. Descarga la plantilla con el formato requerido.      |
|  2. Completa los datos de tus productos.                 |
|  3. Subi el archivo para validarlo.                      |
|                                                          |
|  [ Descargar plantilla (.xlsx) ]                         |
|                                                          |
|  ------------------------------------------------        |
|                                                          |
|  Subir archivo:                                          |
|  [============ Elegir archivo ============]              |
|                                                          |
|  Comportamiento ante codigos duplicados:                 |
|  ( ) Saltar - No modificar productos existentes          |
|  (x) Actualizar - Sobreescribir con datos del archivo    |
|  ( ) Error - Marcar como error                           |
|                                                          |
|  [ Validar archivo ]                                     |
|                                                          |
+----------------------------------------------------------+
```

El boton "Validar archivo" envia el formulario via HTMX (`hx-post`) y reemplaza el contenedor de resultados.

### Paso 2: Preview de validacion

```
+----------------------------------------------------------+
| FerrERP > Productos > Importar > Preview                 |
+----------------------------------------------------------+
|                                                          |
|  Resultado de la validacion                              |
|  Archivo: productos_ferreteria.xlsx (847 filas)          |
|                                                          |
|  +----------+----------+-----------+---------+           |
|  | Nuevos   | Actualiz.| Advertenc.| Errores |           |
|  |   812    |    28    |     5     |    2    |           |
|  +----------+----------+-----------+---------+           |
|                                                          |
|  [Filtrar: Todos | Solo errores | Solo advertencias]     |
|                                                          |
|  +-----+--------+------------------+--------+---------+  |
|  | Fila | Codigo | Nombre           | Estado | Detalle |  |
|  +-----+--------+------------------+--------+---------+  |
|  |    2 | CLV-4  | Clavo 4" x kg    |  OK    |         |  |
|  |    3 | TORN.. | Tornillo M6x30   |  OK    | Actualiz|  |
|  |   15 | PINT.. | Latex blanco 4L  |  WARN  | Proveed.|  |
|  |   87 |        | Disco corte 115  |  ERROR | Codigo  |  |
|  |  134 | CLV-4  | Clavo 4" repet.  |  ERROR | Codigo  |  |
|  +-----+--------+------------------+--------+---------+  |
|                                                          |
|  Los productos con errores NO se importaran.             |
|  Los productos con advertencias SI se importaran.        |
|                                                          |
|  [ Cancelar ]  [ Importar 845 productos ]                |
|                                                          |
+----------------------------------------------------------+
```

El preview se renderiza como partial HTMX. El boton "Importar" hace `hx-post` al endpoint de aplicacion.

### Paso 3: Resultado de la importacion

```
+----------------------------------------------------------+
| FerrERP > Productos > Importar > Resultado               |
+----------------------------------------------------------+
|                                                          |
|  [icon-check] Importacion completada                     |
|                                                          |
|  Se importaron 845 productos correctamente.              |
|  - 812 productos nuevos creados                          |
|  - 28 productos actualizados                             |
|  - 5 con advertencias (importados con valores default)   |
|  - 2 omitidos por errores                                |
|                                                          |
|  [ Descargar reporte de errores (.xlsx) ]                |
|  [ Ir al listado de productos ]                          |
|  [ Importar otro archivo ]                               |
|                                                          |
+----------------------------------------------------------+
```

---

## Requerimientos funcionales y no funcionales

### Funcionales

| ID | Requerimiento | Prioridad |
|---|---|---|
| IMP-01 | Descargar plantilla Excel (.xlsx) con columnas, tipos, valores validos y filas de ejemplo | Alta |
| IMP-02 | Subir archivo .xlsx o .csv (max 10MB) | Alta |
| IMP-03 | Validar cada fila: campos requeridos, tipos de dato, longitudes maximas, unicidad de codigo | Alta |
| IMP-04 | Preview con tabla: fila OK (verde), fila con warning (amarillo), fila con error (rojo) | Alta |
| IMP-05 | Resumen: X productos nuevos, Y actualizados, Z errores | Alta |
| IMP-06 | Comportamiento ante codigo duplicado configurable: saltar, actualizar o error | Alta |
| IMP-07 | Resolver categorias por nombre: vincular a existente o crear automaticamente si no existe | Alta |
| IMP-08 | Resolver proveedores por nombre: vincular a existente, NO crear automaticamente. Warning si no se encuentra. | Alta |
| IMP-09 | Crear MovimientoStock tipo `ajuste_positivo` para el stock inicial de cada producto importado | Media |
| IMP-10 | Operacion atomica: commit completo o rollback total ante error critico | Alta |
| IMP-11 | Registrar auditoria: usuario, fecha/hora, nombre archivo, cantidad importada, cantidad errores | Alta |
| IMP-12 | Limite de 5000 filas por importacion | Media |

### No funcionales

| ID | Requerimiento | Metrica |
|---|---|---|
| NF-01 | Validacion rapida | < 5 segundos para 1000 filas |
| NF-02 | Importacion sin timeout | Hasta 5000 productos en < 30 segundos |
| NF-03 | Tamaño maximo de archivo | 10 MB |
| NF-04 | Multi-tenant | Todo scoped a `current_user.empresa_id` |

---

## Logica de validacion

### Reglas por campo

| Campo | Reglas de validacion |
|---|---|
| `codigo` | Obligatorio. Max 20 chars. Sin espacios al inicio/final (trim). Unico dentro del archivo Y dentro de la empresa. |
| `codigo_barras` | Opcional. Max 50 chars. Trim. |
| `nombre` | Obligatorio. Max 100 chars. Trim. |
| `descripcion` | Opcional. Trim. |
| `categoria` | Opcional. Si contiene ` > `, se interpreta como `padre > hija`. Max 2 niveles. Cada segmento max 50 chars. |
| `unidad_medida` | Opcional. Debe ser uno de: `unidad`, `metro`, `kilo`, `litro`, `par`. Case-insensitive. Default: `unidad`. |
| `precio_costo` | Obligatorio. Numerico >= 0. Hasta 2 decimales. Se convierte con `Decimal(str(valor))`. |
| `precio_venta` | Obligatorio. Numerico >= 0. Hasta 2 decimales. Warning si `precio_venta < precio_costo`. |
| `iva_porcentaje` | Opcional. Debe ser 0, 10.5, 21 o 27. Default: 21. |
| `stock_actual` | Opcional. Numerico >= 0. Si `unidad_medida` es `unidad` o `par`, debe ser entero. Default: 0. |
| `stock_minimo` | Opcional. Numerico >= 0. Mismas reglas de decimales que `stock_actual`. Default: 0. |
| `proveedor` | Opcional. Si se especifica, debe existir un proveedor activo con ese nombre exacto en la empresa. |
| `ubicacion` | Opcional. Max 50 chars. Trim. |

### Clasificacion de problemas

| Tipo | Efecto | Ejemplos |
|---|---|---|
| **Error** | La fila NO se importa | Campo obligatorio vacio, tipo de dato invalido, codigo duplicado dentro del archivo, longitud excedida |
| **Warning** | La fila SI se importa con valor default o ajuste | Proveedor no encontrado (se importa sin proveedor), `precio_venta < precio_costo`, IVA no estandar ajustado a 21% |

### Manejo de codigos duplicados (IMP-06)

El usuario elige el comportamiento al subir el archivo:

| Modo | Codigo ya existe en DB | Efecto |
|---|---|---|
| `saltar` | Si | La fila se omite. Se marca como "saltada" en el preview. |
| `actualizar` | Si | Se actualizan TODOS los campos del producto existente con los valores del archivo. El stock NO se reemplaza; se crea un ajuste si difiere. |
| `error` | Si | La fila se marca como error y no se importa. |

En todos los modos: si el codigo aparece **duplicado dentro del mismo archivo**, siempre es un error.

### Resolucion de categorias (IMP-07)

```
Entrada: "Pinturas > Latex"

1. Buscar categoria "Pinturas" (padre_id=NULL) en la empresa
   - Si no existe → crear categoria "Pinturas" (padre_id=NULL, activa=True)
2. Buscar categoria "Latex" con padre="Pinturas" en la empresa
   - Si no existe → crear categoria "Latex" (padre_id=pinturas.id, activa=True)
3. Asignar categoria_id = latex.id al producto

Entrada: "Herramientas" (sin subcategoria)

1. Buscar categoria "Herramientas" (padre_id=NULL) en la empresa
   - Si no existe → crear categoria "Herramientas" (padre_id=NULL, activa=True)
2. Asignar categoria_id = herramientas.id al producto
```

La busqueda de categorias es case-insensitive y con trim. Se usa un cache en memoria durante la importacion para evitar queries repetidas.

### Resolucion de proveedores (IMP-08)

```
Entrada: "Acindar"

1. Buscar proveedor activo con nombre "Acindar" en la empresa (case-insensitive, trim)
   - Si existe → asignar proveedor_id
   - Si NO existe → warning, se importa sin proveedor (proveedor_id=NULL)
```

No se crean proveedores automaticamente porque tienen datos adicionales (CUIT, contacto, etc.) que no estan en la plantilla.

---

## Arquitectura tecnica

### Archivos nuevos

| Archivo | Descripcion |
|---|---|
| `app/services/importacion_productos.py` | Servicio principal con logica de validacion, resolucion e importacion |
| `app/routes/importacion_productos.py` | Blueprint con rutas de descarga, upload, preview y aplicacion |
| `app/forms/importacion_productos.py` | Formulario de upload con seleccion de modo duplicados |
| `app/templates/productos/importar.html` | Pagina principal de importacion |
| `app/templates/productos/_preview_importacion.html` | Partial HTMX con tabla de preview |
| `app/templates/productos/_resultado_importacion.html` | Partial HTMX con resultado final |
| `app/models/importacion.py` | Modelo ImportacionProducto para auditoria |
| `tests/test_importacion_productos.py` | Tests del servicio y las rutas |

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `app/__init__.py` | Registrar blueprint `importacion_productos_bp` |
| `app/models/__init__.py` | Importar modelo `ImportacionProducto` |
| `app/templates/productos/index.html` | Agregar boton "Importar productos" (solo visible para admin) |

### Blueprint: `app/routes/importacion_productos.py`

```python
from flask import Blueprint

bp = Blueprint('importacion_productos', __name__, url_prefix='/productos/importar')
```

| Ruta | Metodo | Funcion | Descripcion |
|---|---|---|---|
| `/productos/importar/` | GET | `index` | Pagina principal con formulario de upload |
| `/productos/importar/plantilla` | GET | `descargar_plantilla` | Genera y descarga plantilla .xlsx |
| `/productos/importar/validar` | POST | `validar_archivo` | Recibe archivo, valida, guarda en sesion, devuelve partial preview |
| `/productos/importar/aplicar` | POST | `aplicar_importacion` | Ejecuta la importacion desde datos en sesion, devuelve partial resultado |

Todas las rutas llevan los decoradores `@login_required`, `@admin_required`, `@empresa_aprobada_required`.

### Servicio: `app/services/importacion_productos.py`

#### Funciones principales

```python
def generar_plantilla() -> BytesIO:
    """
    Genera un archivo Excel con la hoja 'productos' (encabezados + fila ejemplo)
    y la hoja 'instrucciones' (reglas de validacion por columna).
    Retorna un BytesIO listo para send_file().
    """

def leer_archivo(archivo: FileStorage) -> list[dict]:
    """
    Lee un archivo .xlsx o .csv y retorna una lista de diccionarios
    con los datos crudos de cada fila. Detecta formato por extension.
    Valida tamaño maximo (10MB) y cantidad de filas (5000).
    Normaliza encabezados: lowercase, strip, sin tildes.
    Lanza ValueError si el formato es invalido.
    """

def validar_filas(
    filas: list[dict],
    empresa_id: int,
    modo_duplicados: str  # 'saltar' | 'actualizar' | 'error'
) -> ResultadoValidacion:
    """
    Valida cada fila segun las reglas definidas.
    Resuelve categorias y proveedores.
    Retorna un ResultadoValidacion con:
    - filas_validas: list[FilaValidada] (con datos parseados y relaciones resueltas)
    - filas_error: list[FilaError] (con numero de fila y mensajes de error)
    - filas_warning: list[FilaWarning]
    - filas_saltar: list[FilaSaltada]
    - resumen: dict con conteos
    """

def aplicar_importacion(
    resultado: ResultadoValidacion,
    empresa_id: int,
    usuario_id: int,
    nombre_archivo: str
) -> ImportacionProducto:
    """
    Ejecuta la importacion dentro de una transaccion.
    Crea/actualiza productos, genera MovimientoStock, registra auditoria.
    Retorna el registro de ImportacionProducto con el resumen.
    Lanza exception con rollback si ocurre un error critico.
    """
```

#### Funciones auxiliares

```python
def _validar_fila(fila: dict, numero_fila: int, contexto: ContextoValidacion) -> FilaValidada | FilaError:
    """Valida una fila individual contra todas las reglas."""

def _resolver_categoria(nombre_categoria: str, empresa_id: int, cache: dict) -> int | None:
    """Busca o crea la categoria. Soporta formato 'Padre > Hija'. Usa cache."""

def _resolver_proveedor(nombre_proveedor: str, empresa_id: int, cache: dict) -> tuple[int | None, str | None]:
    """Busca el proveedor. Retorna (id, warning_message). No crea."""

def _parsear_decimal(valor, nombre_campo: str, decimales: int = 2) -> Decimal:
    """Convierte valor a Decimal con validacion. Usa Decimal(str(valor))."""

def _normalizar_encabezados(encabezados: list[str]) -> list[str]:
    """Lowercase, strip, remueve tildes para matching flexible."""
```

#### Dataclasses de resultado

```python
@dataclass
class FilaValidada:
    numero_fila: int
    datos: dict           # Datos parseados listos para crear el modelo
    es_actualizacion: bool
    warnings: list[str]
    producto_existente_id: int | None  # Si es actualizacion

@dataclass
class FilaError:
    numero_fila: int
    datos_crudos: dict
    errores: list[str]

@dataclass
class ResultadoValidacion:
    filas_validas: list[FilaValidada]
    filas_error: list[FilaError]
    filas_saltadas: list[dict]
    resumen: dict  # {'nuevos': int, 'actualizados': int, 'errores': int, 'saltados': int, 'warnings': int}
```

### Formulario: `app/forms/importacion_productos.py`

```python
class ImportacionProductosForm(FlaskForm):
    archivo = FileField(
        'Archivo Excel o CSV',
        validators=[
            FileRequired(message='Debe seleccionar un archivo.'),
            FileAllowed(['xlsx', 'csv'], message='Solo se permiten archivos .xlsx o .csv.')
        ]
    )
    modo_duplicados = RadioField(
        'Comportamiento ante codigos duplicados',
        choices=[
            ('saltar', 'Saltar - No modificar productos existentes'),
            ('actualizar', 'Actualizar - Sobreescribir con datos del archivo'),
            ('error', 'Error - Marcar como error')
        ],
        default='actualizar'
    )
```

### Almacenamiento temporal del preview

Despues de la validacion, el `ResultadoValidacion` se serializa y guarda en la sesion de Flask (o en un archivo temporal si excede el tamaño de sesion). Se identifica con un UUID de importacion para evitar ataques de replay.

```python
# En la ruta validar:
importacion_id = str(uuid4())
session[f'importacion_{importacion_id}'] = {
    'resultado': resultado.to_dict(),
    'nombre_archivo': archivo.filename,
    'modo_duplicados': modo_duplicados,
    'timestamp': datetime.now().isoformat()
}

# En la ruta aplicar:
datos = session.pop(f'importacion_{importacion_id}', None)
if not datos or _importacion_expirada(datos['timestamp']):
    flash('La sesion de importacion expiro. Subi el archivo nuevamente.', 'warning')
    return redirect(url_for('importacion_productos.index'))
```

Para archivos grandes (> 1000 filas), usar almacenamiento en archivo temporal en lugar de sesion:

```python
# Guardar en /tmp/ferrerp_importaciones/{empresa_id}/{importacion_id}.json
ruta_temp = Path(f'/tmp/ferrerp_importaciones/{empresa_id}/{importacion_id}.json')
ruta_temp.parent.mkdir(parents=True, exist_ok=True)
ruta_temp.write_text(json.dumps(resultado.to_dict()))
session[f'importacion_{importacion_id}'] = {
    'ruta_temp': str(ruta_temp),
    'nombre_archivo': archivo.filename,
    'timestamp': datetime.now().isoformat()
}
```

---

## Modelo de datos

### Tabla `importaciones_productos` (nueva)

```python
class ImportacionProducto(EmpresaMixin, db.Model):
    __tablename__ = 'importaciones_productos'

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    nombre_archivo = db.Column(db.String(255), nullable=False)
    modo_duplicados = db.Column(db.String(20), nullable=False)  # saltar | actualizar | error
    total_filas = db.Column(db.Integer, nullable=False)
    productos_creados = db.Column(db.Integer, nullable=False, default=0)
    productos_actualizados = db.Column(db.Integer, nullable=False, default=0)
    productos_saltados = db.Column(db.Integer, nullable=False, default=0)
    productos_error = db.Column(db.Integer, nullable=False, default=0)
    categorias_creadas = db.Column(db.Integer, nullable=False, default=0)
    estado = db.Column(db.String(20), nullable=False, default='completada')  # completada | fallida
    detalle_errores = db.Column(db.Text, nullable=True)  # JSON con errores para reporte

    usuario = db.relationship('Usuario', backref='importaciones_productos')
```

### Migracion

Crear migracion con Alembic:

```bash
flask db revision -m "agregar tabla importaciones_productos"
```

---

## Edge cases y manejo de errores

| Escenario | Comportamiento |
|---|---|
| Archivo vacio (sin filas de datos) | Error: "El archivo no contiene datos para importar." |
| Archivo con encabezados pero sin filas | Error: "El archivo no contiene datos para importar." |
| Encabezados con nombres incorrectos | Error: "Columnas no reconocidas: X, Y. Las columnas esperadas son: ..." |
| Faltan columnas obligatorias en encabezado | Error: "Faltan las columnas obligatorias: codigo, nombre, ..." |
| Fila completamente vacia | Se ignora silenciosamente (no cuenta como error). |
| Archivo con mas de 5000 filas | Error: "El archivo contiene N filas. El maximo permitido es 5000." |
| Archivo mayor a 10MB | Error: "El archivo excede el tamaño maximo de 10MB." |
| Archivo corrupto / no es Excel valido | Error: "No se pudo leer el archivo. Verifique que sea un .xlsx o .csv valido." |
| Codigo duplicado dentro del mismo archivo | Error en la segunda aparicion: "Codigo 'X' duplicado en fila Y." |
| Codigo ya existe en DB + modo `saltar` | Se omite con estado "saltado". |
| Codigo ya existe en DB + modo `actualizar` | Se actualiza producto existente. |
| Codigo ya existe en DB + modo `error` | Error: "El codigo 'X' ya existe en el sistema." |
| Categoria con mas de 2 niveles (`A > B > C`) | Error: "Solo se permiten hasta 2 niveles de categoria." |
| Proveedor no encontrado en DB | Warning: "Proveedor 'X' no encontrado. Se importa sin proveedor." |
| `precio_venta` < `precio_costo` | Warning: "El precio de venta ($X) es menor al costo ($Y)." |
| `stock_actual` con decimales para unidad/par | Error: "El stock debe ser entero para la unidad de medida 'unidad'." |
| Valor numerico con texto ("abc" en precio) | Error: "El campo precio_costo debe ser numerico." |
| IVA con valor no estandar (ej: 15) | Warning: "Alicuota de IVA no estandar. Se ajusto a 21%." |
| Error de base de datos durante importacion | Rollback completo. Estado de importacion: `fallida`. Flash: "Ocurrio un error al importar. Ningún producto fue modificado." |
| Session de importacion expirada (> 30 min) | Redireccion con mensaje: "La sesion de importacion expiro." |
| CSV con encoding incorrecto | Intentar UTF-8, luego latin-1, luego error con sugerencia de encoding. |
| CSV con separador incorrecto | Detectar automaticamente con `csv.Sniffer`. Soportar `,` y `;`. |

---

## Consideraciones de performance

### Validacion (NF-01: < 5s para 1000 filas)

- **Pre-cargar datos de referencia**: Al iniciar la validacion, hacer UNA query para obtener todos los codigos de producto existentes de la empresa, todas las categorias y todos los proveedores. Guardar en diccionarios para lookup O(1).
- **Cache de categorias**: Durante la importacion, las categorias recien creadas se agregan al cache para no repetir queries.

```python
class ContextoValidacion:
    """Se construye una vez y se pasa a cada validacion de fila."""
    codigos_existentes: dict[str, int]       # {codigo: producto_id}
    categorias: dict[str, int]               # {nombre_normalizado: id}
    categorias_hijas: dict[tuple, int]        # {(padre_nombre, hija_nombre): id}
    proveedores: dict[str, int]              # {nombre_normalizado: id}
    codigos_en_archivo: set[str]             # Para detectar duplicados intra-archivo
```

### Importacion (NF-02: < 30s para 5000 filas)

- **Bulk insert**: Usar `db.session.bulk_save_objects()` para lotes de productos nuevos.
- **Chunking**: Procesar en lotes de 500 productos. Hacer `db.session.flush()` cada lote para liberar memoria del unit of work.
- **Minimizar queries**: Resolver todas las categorias y proveedores en la fase de validacion. La fase de aplicacion solo ejecuta INSERTs y UPDATEs.
- **Una sola transaccion**: Todo dentro del mismo `db.session`. Commit al final, rollback si falla.

```python
TAMAÑO_LOTE = 500

def aplicar_importacion(resultado, empresa_id, usuario_id, nombre_archivo):
    try:
        for i in range(0, len(resultado.filas_validas), TAMAÑO_LOTE):
            lote = resultado.filas_validas[i:i + TAMAÑO_LOTE]
            _procesar_lote(lote, empresa_id)
            db.session.flush()  # Liberar memoria, mantener transaccion

        importacion = ImportacionProducto(...)
        db.session.add(importacion)
        db.session.commit()
        return importacion
    except Exception:
        db.session.rollback()
        raise
```

### Indices relevantes

La tabla `productos` ya tiene indice unico en `(empresa_id, codigo)`. Verificar que exista indice en:
- `categorias(empresa_id, nombre, padre_id)` — para busqueda rapida de categorias
- `proveedores(empresa_id, nombre)` — para busqueda rapida de proveedores

---

## Fases de implementacion

### Fase 1: Infraestructura y plantilla

**Alcance**: Modelo de auditoria, migracion, blueprint basico, descarga de plantilla.

**Tareas**:
1. Crear modelo `ImportacionProducto` en `app/models/importacion.py`
2. Crear y aplicar migracion Alembic
3. Crear blueprint `importacion_productos` con ruta GET index
4. Implementar `generar_plantilla()` en el servicio
5. Crear ruta `descargar_plantilla`
6. Crear template `importar.html` con formulario de upload
7. Registrar blueprint en `app/__init__.py`
8. Agregar enlace en el listado de productos (solo admin)

**Criterios de aceptacion**:
- El admin puede acceder a `/productos/importar/` y ve el formulario
- El admin puede descargar una plantilla .xlsx con encabezados correctos, hoja de ejemplo y hoja de instrucciones
- El vendedor recibe 403 al intentar acceder
- La tabla `importaciones_productos` existe en la base de datos

### Fase 2: Lectura y validacion

**Alcance**: Lectura de archivos, validacion completa, preview.

**Tareas**:
1. Implementar `leer_archivo()` con soporte .xlsx y .csv
2. Implementar `ContextoValidacion` con pre-carga de datos
3. Implementar `validar_filas()` con todas las reglas
4. Implementar `_resolver_categoria()` y `_resolver_proveedor()`
5. Crear ruta `validar_archivo` que procese el upload y retorne partial
6. Crear template `_preview_importacion.html` con tabla de resultados
7. Implementar filtros por estado (todos / errores / warnings) con HTMX
8. Implementar almacenamiento temporal del resultado

**Criterios de aceptacion**:
- Al subir un archivo valido, se muestra el preview con filas OK, warnings y errores
- Los errores muestran mensajes claros indicando fila y campo
- Los codigos duplicados dentro del archivo se detectan
- Las categorias se resuelven correctamente (padre > hija)
- Los proveedores inexistentes generan warning, no error
- Archivo > 10MB se rechaza
- Archivo > 5000 filas se rechaza
- CSV con distintos separadores y encodings se lee correctamente

### Fase 3: Aplicacion e importacion

**Alcance**: Importacion real, movimientos de stock, auditoria.

**Tareas**:
1. Implementar `aplicar_importacion()` con bulk insert por lotes
2. Implementar creacion de MovimientoStock para stock inicial
3. Implementar actualizacion de productos existentes (modo `actualizar`)
4. Crear registro de `ImportacionProducto` con resumen
5. Crear ruta `aplicar_importacion` que ejecute y retorne partial resultado
6. Crear template `_resultado_importacion.html`
7. Implementar generacion de reporte de errores descargable (.xlsx)
8. Limpiar datos temporales de sesion/archivo

**Criterios de aceptacion**:
- Al confirmar la importacion, se crean los productos en la base de datos
- Cada producto con stock > 0 tiene un MovimientoStock asociado
- La operacion es atomica: si falla, ningun producto se modifica
- Se registra la importacion en `importaciones_productos`
- El admin puede descargar un reporte con las filas que fallaron
- En modo `saltar`, los productos existentes no se modifican
- En modo `actualizar`, los productos existentes se actualizan correctamente

### Fase 4: Tests y polish

**Alcance**: Cobertura de tests, UX final.

**Tareas**:
1. Tests unitarios del servicio: validacion de cada campo, resoluciones, edge cases
2. Tests de integracion de rutas: upload, preview, aplicacion
3. Test de atomicidad: simular error a mitad de importacion, verificar rollback
4. Test de performance: importacion de 1000+ productos
5. Mejoras UX: loading spinner durante importacion, disable boton para evitar doble click
6. Verificar comportamiento multi-tenant: importacion de una empresa no afecta a otra

**Criterios de aceptacion**:
- Cobertura de tests > 90% para el servicio de importacion
- Todos los edge cases documentados tienen test
- La importacion de 1000 productos completa en < 5 segundos
- No hay fugas de datos entre empresas
