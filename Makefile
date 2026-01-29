# FerrERP - Makefile
# Comandos para facilitar el uso de Docker

.PHONY: help build up down logs shell db-shell seed migrate clean test test-dev test-dev-run install-hooks

# Mostrar ayuda
help:
	@echo "FerrERP - Comandos disponibles:"
	@echo ""
	@echo "  make build      - Construir imagenes Docker"
	@echo "  make up         - Iniciar contenedores (produccion)"
	@echo "  make up-dev     - Iniciar contenedores (desarrollo con hot-reload)"
	@echo "  make down       - Detener contenedores"
	@echo "  make logs       - Ver logs de la aplicacion"
	@echo "  make shell      - Abrir shell en el contenedor web"
	@echo "  make db-shell   - Abrir psql en el contenedor de base de datos"
	@echo "  make seed       - Cargar datos de prueba"
	@echo "  make migrate    - Ejecutar migraciones de base de datos"
	@echo "  make test       - Ejecutar tests (stack prod)"
	@echo "  make test-dev   - Ejecutar tests (stack dev)"
	@echo "  make test-dev-run - Ejecutar tests en contenedor nuevo (dev)"
	@echo "  make install-hooks - Instalar hook pre-push"
	@echo "  make clean      - Eliminar contenedores, volumenes e imagenes"
	@echo ""

# Construir imagenes
build:
	docker-compose build

# Iniciar en modo produccion
up:
	docker-compose up -d
	@echo ""
	@echo "FerrERP iniciado en http://localhost:5000"
	@echo "Para ver logs: make logs"

# Iniciar en modo desarrollo
up-dev:
	docker-compose -f docker-compose.dev.yml up -d
	@echo ""
	@echo "FerrERP (Dev) iniciado en http://localhost:5000"
	@echo "Hot-reload activado"

# Detener contenedores
down:
	docker-compose down
	docker-compose -f docker-compose.dev.yml down 2>/dev/null || true

# Ver logs
logs:
	docker-compose logs -f web

# Shell en contenedor web
shell:
	docker-compose exec web /bin/bash

# Shell de PostgreSQL
db-shell:
	docker-compose exec db psql -U ferrerp -d ferrerp

# Cargar datos de prueba
seed:
	docker-compose exec web flask seed

# Ejecutar migraciones
migrate:
	docker-compose exec web flask db upgrade

# Inicializar base de datos
init-db:
	docker-compose exec web flask init-db

# Ejecutar tests
test:
	docker-compose exec -e PYTHONPATH=/app -e TEST_DATABASE_URL=sqlite:///:memory: -e PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 web pytest

# Ejecutar tests (dev)
test-dev:
	docker-compose -f docker-compose.dev.yml exec -e PYTHONPATH=/app -e TEST_DATABASE_URL=sqlite:///:memory: -e PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 web pytest

# Ejecutar tests (dev, contenedor nuevo)
test-dev-run:
	docker-compose -f docker-compose.dev.yml run --rm -e PYTHONPATH=/app -e TEST_DATABASE_URL=sqlite:///:memory: -e PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 web pytest

# Instalar hook pre-push
install-hooks:
	@if [ -d .git ]; then \
		mkdir -p .git/hooks; \
		cp .githooks/pre-push .git/hooks/pre-push; \
		chmod +x .git/hooks/pre-push; \
		echo "Hook pre-push instalado."; \
	else \
		echo "No existe .git, inicializa el repo antes de instalar hooks."; \
	fi

# Limpiar todo
clean:
	docker-compose down -v --rmi local
	docker-compose -f docker-compose.dev.yml down -v --rmi local 2>/dev/null || true
	@echo "Contenedores, volumenes e imagenes eliminados"

# Reiniciar aplicacion
restart:
	docker-compose restart web

# Ver estado de contenedores
status:
	docker-compose ps
