# AGENTS.md

Guidance for agentic coding assistants working in this repository.
Focus on matching existing patterns in the Flask app.

## Project snapshot
- Stack: Python 3.11, Flask 3.x, SQLAlchemy 2.x, Jinja2 templates, HTMX-style partials.
- Primary entrypoint: `run.py` using the application factory in `app/__init__.py`.
- Configuration in `app/config.py` (development/testing/production via `FLASK_ENV`).
- Database: PostgreSQL in Docker; SQLite fallback for dev.
- Auth: Flask-Login with roles; bcrypt password hashing.
- Testing: pytest + pytest-flask with base fixtures in `tests/conftest.py`.

## Repo map
- `app/routes/`: Flask blueprints (HTTP endpoints and view logic).
- `app/models/`: SQLAlchemy models and domain methods.
- `app/forms/`: Flask-WTF forms and validation.
- `app/services/`: service-layer business logic.
- `app/utils/`: helpers and decorators (HTMX helpers, auth guards).
- `app/templates/`: Jinja HTML templates, partials, and PDFs.
- `app/static/`: CSS/JS/images.
- `seeds/`: seed data loader.
- `migrations/`: Flask-Migrate / Alembic.

## Environment and setup
- Use Python 3.11 and install deps from `requirements.txt`.
- Load env vars from `.env` (see `.env.example` for defaults).
- `FLASK_APP=run.py` is expected by `flask` CLI commands.
- `FLASK_ENV` controls config selection (`development`, `testing`, `production`).

## Build and run (Docker)
- `make build` builds images (uses `docker-compose.yml`).
- `make up` starts production-like stack at `http://localhost:5000`.
- `make up-dev` starts dev stack with hot reload (host port 5001).
- `make logs` tails web logs.
- `make shell` opens a shell in the web container.
- `make db-shell` opens psql in the DB container.
- `make down` stops containers (both prod/dev compose files).
- `make clean` removes containers, volumes, and local images.

## DB and seed commands
- `make migrate` runs `flask db upgrade` in the container.
- `make init-db` creates tables via `flask init-db`.
- `make seed` loads demo data (`flask seed`).
- `LOAD_SEED_DATA=true` in env triggers seeding on container startup.

## Local run (non-Docker)
- `python -m venv .venv && source .venv/bin/activate`
- `pip install -r requirements.txt`
- `export FLASK_APP=run.py`
- `export FLASK_ENV=development`
- `flask run --debug`

## Linting
- Ruff is the single lint/format tool (config in `pyproject.toml`).
- Run lint: `ruff check .`
- Auto-fix: `ruff check . --fix`
- Format: `ruff format .`

## Testing
- `pytest` runs the full suite.
- `make test` runs tests in the prod stack.
- `make test-dev` runs tests in the dev stack.
- `make test-dev-run` runs tests in a fresh dev container.
- `make install-hooks` installs the pre-push hook (runs tests before push).
- Single test file: `pytest tests/test_products.py`
- Single test function: `pytest tests/test_products.py::test_create_producto`
- By keyword: `pytest -k producto`
- Base fixtures use SQLite in-memory and `LOGIN_DISABLED=True` for simple tests.
- For Flask app tests, use `create_app('testing')` and override config in fixtures.

## Import conventions
- Use absolute package imports within `app` (e.g., `from ..models import Producto`).
- Standard library imports first, third-party second, local modules last.
- Avoid circular imports; do local imports inside functions only when necessary.
- Blueprints modules expose `bp` and are imported in `app/routes/__init__.py`.

## Formatting and style
- Use 4-space indentation, no tabs.
- Keep line length around 100 characters; wrap long function calls across lines.
- Use trailing commas in multi-line collections for cleaner diffs.
- Prefer blank lines to separate logical blocks.
- Docstrings are triple-quoted and written in Spanish.

## Naming conventions
- Variables/functions: `snake_case` and Spanish naming is the norm.
- Classes: `PascalCase`.
- Blueprint instances are named `bp`.
- Routes use Spanish slugs (`/productos`, `/ventas`, etc.).
- Boolean columns default to `True/False` and use clear adjective names (`activo`, `abierta`).

## Types and numeric precision
- Use `Decimal` for money and quantities; convert input with `Decimal(str(value))`.
- Use SQLAlchemy `Numeric` columns for monetary/quantity fields.
- Convert `Decimal` to float only for JSON responses or template convenience.

## Database patterns
- Always add objects to `db.session` and call `db.session.commit()` once per unit of work.
- Use `db.session.flush()` only when you need IDs before commit.
- On exceptions in write flows, rollback with `db.session.rollback()`.
- Prefer query filters with `Model.query.filter(...)` and `filter_by(...)`.
- Use helper `paginar_query` for pagination in routes.

## Service-layer patterns
- Business logic lives in `app/services` and returns model objects.
- Validate inputs early; raise `ValueError` with Spanish messages for bad state.
- Keep service functions pure-ish; avoid direct template rendering except for PDFs.

## Route patterns
- Protect routes with `@login_required` or custom decorators in `app/utils/decorators.py`.
- Use `flash(..., category)` for user-facing errors and success notices.
- Use `render_template` for HTML and `redirect(url_for(...))` after writes.
- For HTMX requests, check `es_peticion_htmx()` and return partials.
- Use `respuesta_htmx_redirect()` when you need client-side redirects.

## Forms
- Forms live in `app/forms` and inherit from `FlaskForm`.
- Provide `render_kw` placeholders and Spanish validation messages.
- Populate select choices in `__init__` via helper methods (`_cargar_*`).

## Templates and static assets
- Jinja templates are under `app/templates`; partials use `_nombre.html`.
- Keep template copy in Spanish and match existing UI tone.
- Static JS/CSS lives in `app/static`.

## Error handling
- Error handlers are registered in `app/__init__.py`.
- On 500 errors, rollback the DB session before rendering the error page.
- Prefer graceful user feedback over raising raw exceptions in routes.

## Security and auth
- Passwords are hashed with bcrypt (`Usuario.set_password` / `check_password`).
- Roles are enforced via decorators and `Usuario.rol` values.
- Avoid exposing sensitive config; use env vars for secrets.

## Migrations
- Migrations are managed by Flask-Migrate (Alembic).
- Update models first, then run `flask db migrate` and `flask db upgrade`.
- Commit migration files with model changes.

## Testing guidance (new tests)
- Place tests under `tests/` using `test_*.py` files.
- Reuse the `app` fixture in `tests/conftest.py`; `client` is provided by pytest-flask.
- Prefer SQLite in-memory for unit tests; use `TEST_DATABASE_URL` for integration tests.
- Keep tests independent; create DB rows inside each test and avoid ordering.

## Cursor/Copilot rules
- No `.cursor/rules`, `.cursorrules`, or `.github/copilot-instructions.md` found.
- If such rules are added later, copy them into this file verbatim.

## Contributions by agents
- Keep changes scoped; avoid refactors unless required.
- Match existing Spanish terminology in code and UI copy.
- If you add dependencies or commands, update this file accordingly.
- Be explicit about new env vars and defaults.
- Do not commit `.env` or secrets.

## Quick sanity checklist
- App boots with `flask run` or `make up-dev`.
- DB migrations applied and seed data loaded if needed.
- Routes follow blueprint structure and use decorators.
- Money math uses `Decimal` and `Numeric`.
- UI text remains in Spanish and uses existing template partials.
