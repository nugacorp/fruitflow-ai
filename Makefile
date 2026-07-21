.PHONY: help install up down logs test lint fmt typecheck migrate revision seed shell psql ci

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Instala dependencias de desarrollo
	pip install -e ".[dev]"

up: ## Levanta el stack local
	docker compose -f docker/docker-compose.yml up -d --build

down: ## Detiene el stack local
	docker compose -f docker/docker-compose.yml down

logs: ## Sigue los logs
	docker compose -f docker/docker-compose.yml logs -f --tail=100

test: ## Ejecuta la bateria de pruebas
	pytest

lint: ## Verifica formato y estilo
	ruff format --check .
	ruff check .

fmt: ## Formatea el codigo
	ruff format .
	ruff check --fix .

typecheck: ## Verificacion estatica de tipos
	mypy backend

migrate: ## Aplica migraciones
	alembic upgrade head

revision: ## Crea una migracion (make revision m="mensaje")
	alembic revision --autogenerate -m "$(m)"

seed: ## Siembra datos de desarrollo
	python scripts/seed_dev.py

psql: ## Consola de PostgreSQL
	docker compose -f docker/docker-compose.yml exec postgres psql -U fruitflow -d fruitflow

ci: lint typecheck test ## Puerta de calidad completa
