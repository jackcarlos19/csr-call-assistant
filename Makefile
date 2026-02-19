.PHONY: up down build test lint

up:
	docker compose up --build

down:
	docker compose down

build:
	docker compose build

test:
	cd apps/api && python -m pytest tests/ -v
	cd apps/web && npm run lint && npm run build

lint:
	cd apps/api && ruff check .
	cd apps/web && npx eslint .

migrate:
	cd apps/api && alembic upgrade head

migrate-create:
	cd apps/api && alembic revision --autogenerate -m "$(msg)"
