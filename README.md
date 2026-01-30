<div align="center">
  <img src="app/static/img/favicon.svg" alt="FerrERP logo" width="72" height="72">
  <h1>FerrERP</h1>
</div>

Sistema de gestión para ferreterías.

## Stack
- Python 3.11
- Flask 3.x + SQLAlchemy 2.x
- Jinja2 + HTMX
- PostgreSQL en Docker; SQLite solo para tests y fallback local sin Docker

## Requisitos
- Docker + Docker Compose
- Python 3.11 (opcional para ejecución local)

## Configuración
Variables principales en `.env.example`:
- `FLASK_APP=run.py`
- `FLASK_ENV=development`
- `DATABASE_URL=...`

`.env` no se versiona. Copia `.env.example` si necesitas ajustes locales.

## Ejecutar con Docker
```bash
make build
make up       # prod-like en http://localhost:5000
make up-dev   # dev con hot reload en http://localhost:5001
```

## DB y seeds
```bash
make migrate
make init-db
make seed
```

## Ejecutar local (sin Docker)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=run.py
export FLASK_ENV=development
flask run --debug
```

## Tests
```bash
make test
make test-dev
make test-dev-run
```

Test específico:
```bash
pytest tests/test_products.py
pytest tests/test_products.py::test_create_producto
pytest -k producto
```

## Linting (Ruff)
```bash
ruff check .
ruff check . --fix
ruff format .
```

## CI / Hooks
- CI en GitHub Actions: `.github/workflows/tests.yml`
- Hook pre-push (local): `make install-hooks`
