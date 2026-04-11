# Issue #40 - Agregar Logo de la empresa en documentos

- **Fecha:** 2026-04-11
- **Complejidad:** Media
- **Rama:** `feature/029-logo-empresa-documentos`

---

## Estado actual

### Encabezado actual de los PDFs

Los 3 templates PDF (`venta.html`, `presupuesto.html`, `orden_compra.html`) comparten la misma estructura de header:

```html
<div class="header">
    <div class="header-left">
        <div class="logo-text">{{ config_negocio.nombre or 'FerrERP' }}</div>
        <div class="negocio-info">
            CUIT / direccion / telefono
        </div>
    </div>
    <div class="header-right">
        TITULO DEL DOCUMENTO / numero / fecha
    </div>
</div>
```

El logo es actualmente **solo texto** (clase `.logo-text`, font-size 22px, bold). No existe soporte para imagen de logo.

### Generacion de PDFs

Cada servicio (`venta_service.py:8-32`, `presupuesto_service.py:514-539`, `orden_compra_service.py:8-32`) construye un dict `config_negocio` leyendo claves de `Configuracion` y lo pasa al template. WeasyPrint renderiza el HTML a PDF via `HTML(string=html_string).write_pdf()`.

**Importante:** WeasyPrint trabaja con `string=` (no `filename=`), por lo que las imagenes deben ser referenciadas como:
- Data URI (base64 inline) -- funciona siempre, independiente del filesystem
- `file://` con ruta absoluta -- funciona pero acopla al filesystem del servidor
- URL absoluta `http://` -- requiere que el servidor sea accesible desde WeasyPrint

La opcion mas robusta es **base64 inline** dentro del HTML.

### Pagina de configuracion

La ruta `configuracion.index` (`app/routes/configuracion.py:17-54`) renderiza un formulario `ConfiguracionForm` con campos: nombre_negocio, direccion, telefono, cuit, precios_con_iva, mensaje_cumpleanos. No hay campo de upload de archivos.

### Modelo de configuracion

`Configuracion` (`app/models/configuracion.py`) es un modelo clave-valor con tipos (string, integer, decimal, boolean, json). Soporta `Configuracion.get(clave)` y `Configuracion.set(clave, valor, tipo)`. El logo se almacenaria como clave `logo_filename` de tipo `string`.

### Uploads

No existe directorio de uploads ni configuracion de `MAX_CONTENT_LENGTH` en `app/config.py`. El `.gitignore` ya tiene `uploads/` listado (linea preparada para el futuro). No hay dependencia de Pillow en `requirements.txt`.

---

## Diseno tecnico

### 1. Almacenamiento del logo

| Opcion | Pros | Contras |
|--------|------|---------|
| **Filesystem (`app/static/uploads/logos/`)** | Simple, funciona con WeasyPrint via ruta absoluta, facil de servir como static | Requiere volumen persistente en Docker, se pierde en redeploy sin volumen |
| DB (BLOB) | Portable, no depende del filesystem | Complica queries, mas lento, no es practica comun |
| S3 / Object Storage | Escalable, persistente | Over-engineering para este caso, agrega dependencia |

**Recomendacion:** Filesystem en `app/static/uploads/logos/` con las siguientes consideraciones:
- En desarrollo con Docker, el volumen `.:/app` ya monta todo el directorio, asi que los uploads persisten en el host
- En produccion, se debe agregar un volumen nombrado para `app/static/uploads/`
- Para WeasyPrint, se lee el archivo del filesystem y se convierte a **base64 data URI** al generar el PDF, eliminando dependencia de rutas absolutas

**Nomenclatura del archivo:** `empresa_{id}_logo.{ext}` (ej: `empresa_1_logo.png`). Al subir un nuevo logo se elimina el anterior.

**Formatos aceptados:** PNG y JPG. SVG descartado porque WeasyPrint tiene soporte limitado para SVG inline y puede generar problemas de rendering. PNG es el formato recomendado por calidad y transparencia.

**Tamano maximo:** 2 MB

**Dimensiones recomendadas:** Hasta 400x200px. Para buena calidad de impresion a ~150 DPI en un espacio de ~5cm x 2.5cm, 300x150px minimo.

### 2. Cambios en el modelo / configuracion

No se modifica el modelo `Empresa` directamente. Se usa el sistema de `Configuracion` existente con una nueva clave:

- **Clave:** `logo_filename`
- **Tipo:** `string`
- **Valor:** nombre del archivo (ej: `empresa_1_logo.png`)

**No se necesita migracion de DB.** El modelo `Configuracion` es clave-valor dinamico; simplemente se agrega un nuevo registro con `Configuracion.set('logo_filename', 'empresa_1_logo.png', 'string')`.

### 3. Configuracion de Flask para uploads

En `app/config.py`, agregar:

```python
# Uploads
MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads', 'logos')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
```

### 4. Flujo de upload

#### Formulario (frontend)

En `app/templates/configuracion/general.html`, agregar una nueva card "Logo del negocio" entre "Datos del Negocio" y "Mensaje de cumpleanos":

```html
<div class="card mb-4">
    <div class="card-header">Logo del Negocio</div>
    <div class="card-body">
        <!-- Preview del logo actual -->
        {% if logo_actual %}
        <div class="mb-3">
            <img src="{{ url_for('static', filename='uploads/logos/' + logo_actual) }}"
                 alt="Logo actual" style="max-height: 80px; max-width: 250px; object-fit: contain;">
            <button type="button" class="btn btn-sm btn-outline-danger ms-3"
                    hx-post="{{ url_for('configuracion.eliminar_logo') }}"
                    hx-confirm="Eliminar el logo?">
                <span class="material-symbols-rounded me-1">delete</span>Eliminar
            </button>
        </div>
        {% endif %}
        <!-- Input de archivo -->
        <input type="file" name="logo" accept="image/png,image/jpeg"
               class="form-control" id="logo_input">
        <small class="text-muted d-block mt-1">
            Formatos: PNG, JPG. Tamano maximo: 2 MB. Recomendado: 400x200px o menor.
        </small>
    </div>
</div>
```

**Importante:** El form debe cambiar a `enctype="multipart/form-data"` para soportar file upload.

#### Ruta de upload (backend)

Modificar `configuracion.index` en `app/routes/configuracion.py` para:

1. Agregar `enctype='multipart/form-data'` al procesar el form
2. Procesar `request.files.get('logo')` dentro del `POST`
3. Validar extension y tamano
4. (Opcional) Redimensionar con Pillow si excede 400x200px
5. Guardar en `app/static/uploads/logos/empresa_{id}_logo.{ext}`
6. Eliminar logo anterior si existe (diferente extension)
7. Guardar filename en `Configuracion.set('logo_filename', filename, 'string')`

Agregar nueva ruta `configuracion.eliminar_logo` (POST) que:
1. Elimina el archivo del filesystem
2. Elimina la clave `logo_filename` de Configuracion

#### Validacion del archivo

```python
import os
from werkzeug.utils import secure_filename

EXTENSIONES_PERMITIDAS = {'png', 'jpg', 'jpeg'}

def extension_permitida(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in EXTENSIONES_PERMITIDAS

def guardar_logo(archivo, empresa_id):
    """Valida y guarda el logo de la empresa."""
    if not archivo or not archivo.filename:
        return None

    if not extension_permitida(archivo.filename):
        raise ValueError('Formato no permitido. Use PNG o JPG.')

    ext = archivo.filename.rsplit('.', 1)[1].lower()
    if ext == 'jpeg':
        ext = 'jpg'
    filename = f'empresa_{empresa_id}_logo.{ext}'

    # Crear directorio si no existe
    upload_dir = os.path.join(
        current_app.root_path, 'static', 'uploads', 'logos'
    )
    os.makedirs(upload_dir, exist_ok=True)

    # Eliminar logo anterior
    eliminar_logo_anterior(empresa_id, upload_dir)

    filepath = os.path.join(upload_dir, filename)
    archivo.save(filepath)

    return filename
```

### 5. Integracion en PDFs

#### Cambios en los servicios

En los 3 servicios de generacion de PDF, agregar al dict `config_negocio`:

```python
import base64
import os
from flask import current_app

# Dentro de generar_pdf():
logo_filename = Configuracion.get('logo_filename', '')
logo_base64 = None
if logo_filename:
    logo_path = os.path.join(
        current_app.root_path, 'static', 'uploads', 'logos', logo_filename
    )
    if os.path.exists(logo_path):
        with open(logo_path, 'rb') as f:
            logo_data = f.read()
        ext = logo_filename.rsplit('.', 1)[1].lower()
        mime = 'image/png' if ext == 'png' else 'image/jpeg'
        logo_base64 = f'data:{mime};base64,{base64.b64encode(logo_data).decode()}'

config_negocio = {
    # ... campos existentes ...
    'logo_base64': logo_base64,
}
```

Para evitar duplicar este codigo en 3 servicios, crear una funcion helper:

**Nuevo archivo:** `app/services/pdf_utils.py`

```python
"""Utilidades compartidas para generacion de PDFs."""

import base64
import os

from flask import current_app

from ..models import Configuracion


def obtener_config_negocio(**extras):
    """Obtiene la configuracion del negocio para PDFs, incluyendo logo."""
    logo_filename = Configuracion.get('logo_filename', '')
    logo_base64 = None
    if logo_filename:
        logo_path = os.path.join(
            current_app.root_path, 'static', 'uploads', 'logos', logo_filename
        )
        if os.path.exists(logo_path):
            with open(logo_path, 'rb') as f:
                logo_data = f.read()
            ext = logo_filename.rsplit('.', 1)[1].lower()
            mime = 'image/png' if ext == 'png' else 'image/jpeg'
            logo_base64 = f'data:{mime};base64,{base64.b64encode(logo_data).decode()}'

    config = {
        'nombre': Configuracion.get('nombre_negocio', 'FerrERP'),
        'cuit': Configuracion.get('cuit', ''),
        'direccion': Configuracion.get('direccion', ''),
        'telefono': Configuracion.get('telefono', ''),
        'email': Configuracion.get('email', ''),
        'logo_base64': logo_base64,
    }
    config.update(extras)
    return config
```

#### Cambios en los templates PDF

En los 3 templates, reemplazar la seccion `.header-left`:

```html
<div class="header-left">
    {% if config_negocio.logo_base64 %}
    <div class="logo-img">
        <img src="{{ config_negocio.logo_base64 }}"
             alt="{{ config_negocio.nombre }}"
             style="max-height: 60px; max-width: 200px; object-fit: contain;">
    </div>
    <div class="negocio-info" style="margin-top: 4px;">
    {% else %}
    <div class="logo-text">{{ config_negocio.nombre or 'FerrERP' }}</div>
    <div class="negocio-info">
    {% endif %}
        {% if config_negocio.logo_base64 %}
        <strong>{{ config_negocio.nombre }}</strong><br>
        {% endif %}
        {% if config_negocio.cuit %}CUIT: {{ config_negocio.cuit }}<br>{% endif %}
        {% if config_negocio.direccion %}{{ config_negocio.direccion }}<br>{% endif %}
        {% if config_negocio.telefono %}Tel: {{ config_negocio.telefono }}{% endif %}
    </div>
</div>
```

**Comportamiento:**
- **Con logo:** Muestra la imagen + nombre del negocio en texto debajo + datos de contacto
- **Sin logo:** Muestra el nombre grande en texto (`.logo-text`) + datos de contacto (como ahora, retrocompatible)

#### CSS adicional en los templates PDF

```css
.logo-img {
    margin-bottom: 2px;
}

.logo-img img {
    max-height: 60px;
    max-width: 200px;
    object-fit: contain;
}
```

### 6. Consideraciones de formas del logo

El issue menciona soporte para logos rectangulares, triangulares, circulares y cuadrados. La estrategia con `object-fit: contain` y dimensiones maximas (no fijas) maneja todas las formas automaticamente:

| Forma | Comportamiento |
|-------|---------------|
| Rectangular horizontal | Ocupa el ancho maximo (200px), altura proporcional |
| Cuadrado | Ocupa la altura maxima (60px), ancho proporcional |
| Circular | Igual que cuadrado, con transparencia si es PNG |
| Triangular | Se ajusta al bounding box, transparencia visible |

No se requiere logica especial por forma. Se recomienda **PNG con fondo transparente** para mejor resultado visual.

### 7. Dependencias

| Dependencia | Necesaria? | Motivo |
|-------------|------------|--------|
| Pillow | Opcional | Para redimensionar imagenes que excedan 400x200px. Si no se agrega, solo se valida tamano en bytes, no dimensiones. |

**Recomendacion:** Agregar Pillow para validar dimensiones y redimensionar automaticamente. Esto mejora la experiencia del usuario que sube una imagen de 2000x1000px.

```
Pillow==10.2.0
```

Si se decide NO agregar Pillow, se omite la validacion de dimensiones y se confia en la recomendacion al usuario (texto de ayuda en el form).

---

## Archivos a crear/modificar

### Archivos a crear

| Archivo | Descripcion |
|---------|-------------|
| `app/services/pdf_utils.py` | Funcion `obtener_config_negocio()` compartida para los 3 servicios de PDF |
| `app/static/uploads/logos/.gitkeep` | Mantener el directorio en git (los archivos de upload estan en `.gitignore`) |

### Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `app/config.py` | Agregar `MAX_CONTENT_LENGTH` y `UPLOAD_FOLDER` |
| `app/forms/configuracion_forms.py` | No se modifica (el file input se maneja con `request.files`, no con WTForms) |
| `app/routes/configuracion.py` | Procesar upload de logo en `index()`, nueva ruta `eliminar_logo()` |
| `app/templates/configuracion/general.html` | Agregar card "Logo del Negocio", `enctype="multipart/form-data"` en el form |
| `app/services/venta_service.py` | Usar `obtener_config_negocio()` de `pdf_utils` |
| `app/services/presupuesto_service.py` | Usar `obtener_config_negocio()` de `pdf_utils` |
| `app/services/orden_compra_service.py` | Usar `obtener_config_negocio()` de `pdf_utils` |
| `app/templates/ventas/pdf/venta.html` | Header con logo condicional + CSS `.logo-img` |
| `app/templates/presupuestos/pdf/presupuesto.html` | Header con logo condicional + CSS `.logo-img` |
| `app/templates/compras/pdf/orden_compra.html` | Header con logo condicional + CSS `.logo-img` |
| `requirements.txt` | Agregar `Pillow==10.2.0` (si se decide incluir) |
| `docker-compose.yml` (prod) | Agregar volumen para `uploads/` |

---

## Evaluacion de riesgos

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|-------------|---------|------------|
| Logo no aparece en PDF (ruta incorrecta) | Media | Alto | Usar base64 data URI en vez de rutas de archivo |
| Archivo subido corrupto o no es imagen | Baja | Medio | Validar extension + intentar abrir con Pillow |
| Logo demasiado grande distorsiona el header | Media | Medio | `max-height: 60px; max-width: 200px; object-fit: contain` |
| Uploads perdidos en redeploy Docker | Media | Alto | Volumen nombrado en docker-compose.yml para produccion |
| `MAX_CONTENT_LENGTH` rechaza requests sin archivo | Baja | Bajo | Solo se aplica si el body total excede 2MB, no afecta forms sin archivo |
| WeasyPrint no renderiza bien el base64 | Muy baja | Alto | Probado: WeasyPrint soporta data URIs nativamente desde v50+ |
| Multi-tenant: un usuario ve logo de otra empresa | Baja | Alto | Filename incluye `empresa_id`, config filtrada por empresa via `Configuracion.get()` |

---

## Tasks

### Fase 1: Infraestructura de uploads

- [ ] Agregar `MAX_CONTENT_LENGTH` y config de uploads en `app/config.py`
- [ ] Crear directorio `app/static/uploads/logos/` con `.gitkeep`
- [ ] Agregar `Pillow==10.2.0` a `requirements.txt` (opcional)
- [ ] Verificar que `.gitignore` ignora `uploads/` (ya esta)

### Fase 2: Backend de upload

- [ ] Crear funciones `guardar_logo()` y `eliminar_logo_anterior()` (en la ruta o en un helper)
- [ ] Modificar `configuracion.index()` para procesar `request.files['logo']`
- [ ] Crear ruta `configuracion.eliminar_logo()` (POST)
- [ ] Validar extension, tamano, y opcionalmente dimensiones con Pillow

### Fase 3: Frontend de configuracion

- [ ] Agregar `enctype="multipart/form-data"` al form en `general.html`
- [ ] Agregar card "Logo del Negocio" con preview, input file y boton eliminar
- [ ] Agregar texto de ayuda con formatos y dimensiones recomendadas

### Fase 4: Integracion con PDFs

- [ ] Crear `app/services/pdf_utils.py` con `obtener_config_negocio()`
- [ ] Refactorizar `venta_service.generar_pdf()` para usar `obtener_config_negocio()`
- [ ] Refactorizar `presupuesto_service.generar_pdf()` para usar `obtener_config_negocio()`
- [ ] Refactorizar `orden_compra_service.generar_pdf()` para usar `obtener_config_negocio()`
- [ ] Modificar header de `ventas/pdf/venta.html` con logo condicional
- [ ] Modificar header de `presupuestos/pdf/presupuesto.html` con logo condicional
- [ ] Modificar header de `compras/pdf/orden_compra.html` con logo condicional
- [ ] Agregar CSS `.logo-img` en los 3 templates

### Fase 5: Docker y produccion

- [ ] Agregar volumen nombrado para uploads en `docker-compose.yml` (produccion)

### Fase 6: Testing

- [ ] Tests de upload de logo (extension valida/invalida, tamano excedido)
- [ ] Tests de eliminacion de logo
- [ ] Test de generacion de PDF con logo (verificar que no falla)
- [ ] Test de generacion de PDF sin logo (retrocompatibilidad)
- [ ] Test manual: subir logo PNG, generar remito, presupuesto y orden de compra

---

## Plan de testing

### Tests unitarios (`tests/test_configuracion_logo.py`)

1. **test_subir_logo_png_exitoso** - Sube un PNG valido, verifica que se guarda en filesystem y en Configuracion
2. **test_subir_logo_jpg_exitoso** - Sube un JPG valido
3. **test_rechazar_formato_invalido** - Sube un .gif o .bmp, verifica flash de error
4. **test_rechazar_archivo_grande** - Sube archivo >2MB, verifica error 413
5. **test_eliminar_logo** - Sube logo, luego elimina, verifica que se borra del filesystem y de Configuracion
6. **test_reemplazar_logo** - Sube un logo, luego sube otro, verifica que el anterior se elimino
7. **test_generar_pdf_con_logo** - Genera PDF de venta con logo configurado, verifica que no falla
8. **test_generar_pdf_sin_logo** - Genera PDF de venta sin logo, verifica retrocompatibilidad
9. **test_logo_aislamiento_empresa** - Verifica que empresa A no accede al logo de empresa B

### Test manual

1. Ir a Configuracion > General
2. Subir logo PNG con fondo transparente (~300x150px)
3. Verificar preview en la pagina
4. Crear una venta y descargar remito PDF - verificar que el logo aparece
5. Crear presupuesto y descargar PDF - verificar logo
6. Crear orden de compra y descargar PDF - verificar logo
7. Eliminar logo desde configuracion
8. Generar PDF nuevamente - verificar que muestra solo texto (retrocompatible)
9. Probar con logo JPG rectangular, cuadrado y muy ancho - verificar que no distorsiona
