.PHONY: help setup install run worker worker-once kiosk-preflight test clean lint format check

help:
	@echo "Virtual Try-On MVP - Makefile commands"
	@echo ""
	@echo "  make setup      - Setup environment và download models"
	@echo "  make install    - Install dependencies only"
	@echo "  make run        - Run FastAPI server"
	@echo "  make worker     - Run local kiosk worker loop"
	@echo "  make worker-once - Process one local kiosk job"
	@echo "  make kiosk-preflight - Check running kiosk API readiness"
	@echo "  make test       - Run tests với coverage"
	@echo "  make lint       - Run linters (ruff + mypy)"
	@echo "  make format     - Format code (black + ruff)"
	@echo "  make check      - Run all checks (format + lint + test)"
	@echo "  make clean      - Clean temporary files"

setup:
	python3 scripts/setup_env.py

install:
	pip install -U pip
	pip install -r requirements.txt

run:
	python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8080

worker:
	python -m scripts.run_kiosk_worker

worker-once:
	python -m scripts.run_kiosk_worker --once

kiosk-preflight:
	python -m scripts.kiosk_preflight

test:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

lint:
	ruff check src/ tests/
	mypy src/

format:
	black src/ tests/ scripts/
	ruff check --fix src/ tests/ scripts/

check: format lint test

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov
	rm -rf data/*.jpg data/*.png data/*.jpeg
	@echo "✅ Cleaned temporary files"
