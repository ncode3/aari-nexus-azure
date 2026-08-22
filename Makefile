PYTHON ?= .venv/bin/python
COMPOSE ?= docker compose
PLATFORM_PATHS = app/api app/core app/db app/ingestion app/models app/repositories \
	app/schemas app/services app/main.py mcp_server migrations scripts/import_directory.py \
	app/student_report_flow.py scripts/seed_demo_data.py scripts/submit_from_azure.py \
	scripts/ingest_student_reports.py scripts/regenerate_student_report_analytics.py \
	scripts/verify_environment.py \
	tests/unit tests/integration

.PHONY: setup up down logs migrate migration seed test lint format import backup restore

setup:
	python3.12 -m venv .venv
	.venv/bin/pip install -e '.[dev]'
	test -f .env || cp .env.example .env

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f api postgres minio

migrate:
	$(PYTHON) -m alembic upgrade head

migration:
	test -n "$(MESSAGE)"
	$(PYTHON) -m alembic revision --autogenerate -m "$(MESSAGE)"

seed:
	$(PYTHON) scripts/seed_demo_data.py

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check $(PLATFORM_PATHS)
	$(PYTHON) -m mypy app/api app/core app/db app/ingestion app/models \
		app/repositories app/schemas app/services app/main.py app/student_report_flow.py \
		mcp_server scripts/ingest_student_reports.py \
		scripts/regenerate_student_report_analytics.py

format:
	$(PYTHON) -m ruff format $(PLATFORM_PATHS)
	$(PYTHON) -m ruff check --fix $(PLATFORM_PATHS)

import:
	test -n "$(FILE)"
	$(PYTHON) scripts/import_directory.py "$(FILE)"

backup:
	./scripts/backup.sh

restore:
	test -n "$(FILE)"
	./scripts/restore.sh "$(FILE)"
