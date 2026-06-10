RUNPOD_DATA_DIR ?= /workspace/tryon-data
RUNPOD_MODEL_DIR ?= /workspace/tryon-models
RUNPOD_ANALYZER_MODEL ?= qwen2.5vl:7b-q4_K_M
RUNPOD_QWEN_EDIT_MODEL ?= Qwen/Qwen-Image-Edit-2509
RUNPOD_QWEN_EDIT_STEPS ?= 20
RUNPOD_QWEN_EDIT_DEVICE ?= cuda
RUNPOD_QWEN_EDIT_DEVICE_MAP ?= none
RUNPOD_QWEN_EDIT_PERSON_IMAGE ?= $(RUNPOD_DATA_DIR)/kiosk_sessions/captures/kiosk-session-v1-smoke-front.png
RUNPOD_QWEN_EDIT_GARMENT_IMAGE ?= $(RUNPOD_DATA_DIR)/garments/images/garment-v1-smoke.webp
RUNPOD_QWEN_EDIT_FIXTURE_DIR ?= examples/qwen_edit_smoke
RUNPOD_QWEN_EDIT_OUTPUT ?= $(RUNPOD_DATA_DIR)/qwen_edit_smoke/qwen-edit-smoke.png
RUNPOD_QWEN_EDIT_REPORT ?= $(RUNPOD_DATA_DIR)/qwen_edit_smoke/qwen-edit-smoke.json
RUNPOD_HF_HOME ?= $(RUNPOD_MODEL_DIR)/huggingface
RUNPOD_TORCH_HOME ?= $(RUNPOD_MODEL_DIR)/torch
RUNPOD_PIP_CACHE_DIR ?= $(RUNPOD_MODEL_DIR)/pip-cache
RUNPOD_TORCH_VERSION ?= 2.8.0
RUNPOD_TORCHVISION_VERSION ?= 0.23.0
RUNPOD_TORCH_CUDA_INDEX ?= https://download.pytorch.org/whl/cu128

.PHONY: help setup install run run-kiosk run-kiosk-all worker worker-once kiosk-preflight runpod-help runpod-init runpod-install runpod-install-qwen-edit-deps runpod-pull-ollama runpod-reset runpod-start runpod-start-with-ollama runpod-preflight runpod-disk-report runpod-cuda-report runpod-qwen-edit-smoke-data runpod-qwen-edit-smoke test clean lint format check

help:
	@echo "Virtual Try-On MVP - Makefile commands"
	@echo ""
	@echo "  make setup      - Setup environment và download models"
	@echo "  make install    - Install dependencies only"
	@echo "  make run        - Run FastAPI server"
	@echo "  make run-kiosk  - Run kiosk API on 0.0.0.0:8080 for deployed pods"
	@echo "  make run-kiosk-all - Run kiosk API + worker in one foreground process"
	@echo "  make worker     - Run local kiosk worker loop"
	@echo "  make worker-once - Process one local kiosk job"
	@echo "  make kiosk-preflight - Check running kiosk API readiness"
	@echo ""
	@echo "RunPod phase 1:"
	@echo "  make runpod-help - Show the minimum RunPod smoke-test commands"
	@echo "  make runpod-init - Create .env from template and runtime directories"
	@echo "  make runpod-install - Install Python dependencies and initialize paths"
	@echo "  make runpod-pull-ollama - Pull the configured Ollama analyzer model"
	@echo "  make runpod-start - Run kiosk API + worker"
	@echo "  make runpod-start-with-ollama - Run kiosk API + worker + ollama serve"
	@echo "  make runpod-preflight - Check running RunPod kiosk readiness"
	@echo "  make runpod-reset - Reset runtime test data and seed default size charts"
	@echo "  make runpod-install-qwen-edit-deps - Install latest Diffusers stack for local Qwen-edit smoke"
	@echo "  make runpod-disk-report - Print storage/cache usage for RunPod debugging"
	@echo "  make runpod-cuda-report - Print NVIDIA/PyTorch CUDA diagnostics"
	@echo "  make runpod-qwen-edit-smoke-data - Prepare synthetic local Qwen-edit smoke inputs"
	@echo "  make runpod-qwen-edit-smoke - Run local Qwen-edit smoke with prepared/default inputs"
	@echo ""
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

run-kiosk:
	API_PROFILE=kiosk python -m uvicorn src.main:app --host 0.0.0.0 --port 8080

run-kiosk-all:
	python -m scripts.run_kiosk_all

worker:
	python -m scripts.run_kiosk_worker

worker-once:
	python -m scripts.run_kiosk_worker --once

kiosk-preflight:
	python -m scripts.kiosk_preflight

runpod-help:
	@echo "RunPod Phase 1 minimum smoke-test flow"
	@echo ""
	@echo "One-time setup:"
	@echo "  make runpod-install"
	@echo "  edit .env and set REPLICATE_API_TOKEN/CORS_ORIGINS if needed"
	@echo "  start Ollama in one shell: ollama serve"
	@echo "  make runpod-pull-ollama"
	@echo ""
	@echo "Run app:"
	@echo "  make runpod-start"
	@echo ""
	@echo "Or run app and let the supervisor start Ollama if needed:"
	@echo "  make runpod-start-with-ollama"
	@echo ""
	@echo "Check readiness from another shell:"
	@echo "  make runpod-preflight"
	@echo ""
	@echo "Reset demo data when needed:"
	@echo "  make runpod-reset"
	@echo ""
	@echo "Optional local Qwen-edit smoke:"
	@echo "  make runpod-install-qwen-edit-deps"
	@echo "  make runpod-disk-report"
	@echo "  make runpod-cuda-report"
	@echo "  make runpod-qwen-edit-smoke-data"
	@echo "  make runpod-qwen-edit-smoke"

runpod-init:
	@test -f .env || cp .env.runpod.example .env
	@mkdir -p $(RUNPOD_DATA_DIR)/jobs
	@mkdir -p $(RUNPOD_MODEL_DIR)/insightface
	@mkdir -p $(RUNPOD_HF_HOME) $(RUNPOD_TORCH_HOME) $(RUNPOD_PIP_CACHE_DIR)
	@echo "RunPod env/data initialized"
	@echo "  .env: $$(pwd)/.env"
	@echo "  data: $(RUNPOD_DATA_DIR)"
	@echo "  models: $(RUNPOD_MODEL_DIR)"
	@echo "  HF_HOME: $(RUNPOD_HF_HOME)"
	@echo "Review .env before starting the app."

runpod-install: install runpod-init

runpod-install-qwen-edit-deps:
	PIP_CACHE_DIR="$(RUNPOD_PIP_CACHE_DIR)" pip install --force-reinstall \
		torch==$(RUNPOD_TORCH_VERSION) \
		torchvision==$(RUNPOD_TORCHVISION_VERSION) \
		--index-url $(RUNPOD_TORCH_CUDA_INDEX)
	PIP_CACHE_DIR="$(RUNPOD_PIP_CACHE_DIR)" pip install -U "git+https://github.com/huggingface/diffusers" transformers accelerate safetensors

runpod-pull-ollama:
	ollama pull $(RUNPOD_ANALYZER_MODEL)
	ollama list

runpod-reset:
	python -m scripts.reset_kiosk_state --data-dir $(RUNPOD_DATA_DIR) --execute --include-runtime-files --seed-default-size-charts

runpod-start:
	python -m scripts.run_kiosk_all

runpod-start-with-ollama:
	python -m scripts.run_kiosk_all --start-ollama

runpod-preflight:
	python -m scripts.kiosk_preflight

runpod-disk-report:
	@echo "== df -h =="
	@df -h
	@echo ""
	@echo "== df -ih =="
	@df -ih
	@echo ""
	@echo "== configured cache/data sizes =="
	@du -sh $(RUNPOD_DATA_DIR) 2>/dev/null || true
	@du -sh $(RUNPOD_MODEL_DIR) 2>/dev/null || true
	@du -sh $(RUNPOD_HF_HOME) 2>/dev/null || true
	@du -sh $(RUNPOD_TORCH_HOME) 2>/dev/null || true
	@du -sh $(RUNPOD_PIP_CACHE_DIR) 2>/dev/null || true
	@du -sh ~/.cache/huggingface 2>/dev/null || true
	@du -sh ~/.cache/torch 2>/dev/null || true
	@du -sh ~/.cache/pip 2>/dev/null || true
	@du -sh /tmp 2>/dev/null || true
	@echo ""
	@echo "== largest /workspace entries =="
	@du -xhd1 /workspace 2>/dev/null | sort -h | tail -20 || true

runpod-cuda-report:
	python -m scripts.runpod_cuda_report

runpod-qwen-edit-smoke-data:
	python -m scripts.prepare_qwen_edit_smoke_data --data-dir $(RUNPOD_DATA_DIR) --fixture-dir $(RUNPOD_QWEN_EDIT_FIXTURE_DIR)

runpod-qwen-edit-smoke:
	$(eval PERSON_IMAGE_PATH := $(or $(PERSON_IMAGE),$(RUNPOD_QWEN_EDIT_PERSON_IMAGE)))
	$(eval GARMENT_IMAGE_PATH := $(or $(GARMENT_IMAGE),$(RUNPOD_QWEN_EDIT_GARMENT_IMAGE)))
	@test -f "$(PERSON_IMAGE_PATH)" || (echo "Missing PERSON_IMAGE=$(PERSON_IMAGE_PATH). Run make runpod-qwen-edit-smoke-data or pass PERSON_IMAGE=/path/to/front.png"; exit 2)
	@test -f "$(GARMENT_IMAGE_PATH)" || (echo "Missing GARMENT_IMAGE=$(GARMENT_IMAGE_PATH). Run make runpod-qwen-edit-smoke-data or pass GARMENT_IMAGE=/path/to/garment.png"; exit 2)
	HF_HOME="$(RUNPOD_HF_HOME)" \
	TRANSFORMERS_CACHE="$(RUNPOD_HF_HOME)/transformers" \
	HUGGINGFACE_HUB_CACHE="$(RUNPOD_HF_HOME)/hub" \
	TORCH_HOME="$(RUNPOD_TORCH_HOME)" \
	XDG_CACHE_HOME="$(RUNPOD_MODEL_DIR)/xdg-cache" \
	python -m scripts.local_qwen_edit_smoke \
		--person-image "$(PERSON_IMAGE_PATH)" \
		--garment-image "$(GARMENT_IMAGE_PATH)" \
		--output "$(RUNPOD_QWEN_EDIT_OUTPUT)" \
		--report "$(RUNPOD_QWEN_EDIT_REPORT)" \
		--model-id "$(RUNPOD_QWEN_EDIT_MODEL)" \
		--pipeline edit-plus \
		--device "$(RUNPOD_QWEN_EDIT_DEVICE)" \
		--device-map "$(RUNPOD_QWEN_EDIT_DEVICE_MAP)" \
		--steps "$(RUNPOD_QWEN_EDIT_STEPS)"

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
