# CLAUDE.md

Instrucciones específicas para Claude Code en el proyecto FerrERP.
Para referencia general del proyecto, ver `AGENTS.md`.

## Idioma

- Todo el código, comentarios, docstrings, mensajes de UI, flash messages y nombres de variables deben estar en **español**.
- Los nombres técnicos de frameworks/librerías se mantienen en inglés (Flask, SQLAlchemy, etc.).
- Las respuestas al usuario deben ser en español.

## Stack y arquitectura

- **Backend:** Python 3.11 + Flask 3.x + SQLAlchemy 2.x + Flask-Login + Flask-WTF
- **Frontend:** Jinja2 + HTMX + Bootstrap
- **DB:** PostgreSQL 15 (prod/dev Docker), SQLite (tests y dev local)
- **PDF:** WeasyPrint | **Excel:** openpyxl
- **Lint/Format:** Ruff (config en `pyproject.toml`, línea max 100, comillas simples)
- **Tests:** pytest + pytest-flask
- **Containerización:** Docker + Docker Compose

## Comandos esenciales

```bash
# Desarrollo
make up-dev              # Levantar stack dev (puerto 5001, hot-reload)
make logs                # Ver logs
make shell               # Shell en contenedor web
make db-shell            # psql en contenedor DB

# Base de datos
make migrate             # Aplicar migraciones
make seed                # Cargar datos demo

# Tests y calidad
pytest                   # Suite completa
pytest tests/test_x.py   # Archivo específico
pytest -k keyword        # Por keyword
ruff check .             # Lint
ruff check . --fix       # Auto-fix
ruff format .            # Formatear

# Git hooks
make install-hooks       # Instalar pre-push hook
```

## Flujo de trabajo Git

- **Ramas:** `feature/NNN-slug` -> `dev` -> `main`
- **No push directo** a `dev` ni `main` (protegidos con rulesets + hooks locales)
- PRs requieren que pasen los tests de CI (GitHub Actions)
- Siempre crear commits descriptivos en español
- No hacer `--force-push` ni `--no-verify`

## Patrones clave del código

### Modelos
- Usar `Decimal` para dinero y cantidades, nunca `float`
- Columnas monetarias: `Numeric(12,2)` | Cantidades: `Numeric(12,3)`
- Convertir input: `Decimal(str(value))`
- Convención: `activo=True`, `abierta=False` para booleans

### Rutas (Blueprints)
- Cada módulo en `app/routes/` expone `bp`
- Decoradores: `@login_required`, `@admin_required`, `@caja_abierta_required`
- HTMX: verificar con `es_peticion_htmx()`, responder con partials
- Redirects HTMX: `respuesta_htmx_redirect()`
- Después de escrituras: `redirect(url_for(...))`

### Formularios
- Heredan de `FlaskForm` en `app/forms/`
- Choices dinámicos en `__init__` con métodos `_cargar_*`
- Mensajes de validación en español
- `render_kw` para placeholders HTML5

### Servicios
- Lógica de negocio en `app/services/`
- Retornan objetos del modelo
- Errores de validación: `raise ValueError('mensaje en español')`

### Templates
- Base: `app/templates/base.html`
- Partials: prefijo `_nombre.html`
- Componentes reutilizables en `app/templates/components/`
- Todo el texto UI en español

## Tests

- Fixtures en `tests/conftest.py` con SQLite in-memory
- `LOGIN_DISABLED=True` y CSRF deshabilitado en config testing
- Tests independientes: cada uno crea sus datos
- Nombrar archivos `test_*.py` y funciones `test_*`

## Principios para contribuciones

- Cambios acotados: no refactorizar código que no se pidió
- Mantener terminología española existente
- Si se agregan dependencias, actualizar `requirements.txt` y documentar
- No commitear `.env` ni secretos
- Validar que `make up-dev` y `pytest` sigan funcionando tras cambios
- Usar los decoradores de auth existentes, no reinventar
- Seguir el patrón MVC: modelos -> servicios -> rutas -> templates
