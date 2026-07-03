RUNPOD_DATA_DIR ?= /workspace/tryon-data
RUNPOD_MODEL_DIR ?= /workspace/tryon-models
LOCAL_DATA_DIR ?= ./data
UI_PORT ?= 5173
RUNPOD_REQUIREMENTS ?= requirements-kiosk.txt
RUNPOD_ANALYZER_MODEL ?= qwen2.5vl:7b-q4_K_M
RUNPOD_QWEN_EDIT_MODEL ?= Qwen/Qwen-Image-Edit-2509
RUNPOD_QWEN_EDIT_STEPS ?= 8
RUNPOD_QWEN_EDIT_SIZE ?= 512x512
RUNPOD_QWEN_EDIT_INPUT_MAX_SIZE ?= 512
RUNPOD_SMOKE_GARMENT_CATEGORY ?= upper
RUNPOD_SMOKE_DATA_OVERWRITE ?= 1
RUNPOD_QWEN_EDIT_DEVICE ?= cuda
RUNPOD_QWEN_EDIT_DEVICE_MAP ?= none
RUNPOD_QWEN_EDIT_CPU_OFFLOAD ?= 1
RUNPOD_QWEN_EDIT_SEQUENTIAL_CPU_OFFLOAD ?= 1
RUNPOD_QWEN_EDIT_PERSON_IMAGE ?= $(RUNPOD_DATA_DIR)/kiosk_sessions/captures/kiosk-session-v1-smoke-front.png
RUNPOD_QWEN_EDIT_GARMENT_IMAGE ?= $(RUNPOD_DATA_DIR)/garments/images/garment-v1-smoke.webp
RUNPOD_QWEN_EDIT_FIXTURE_DIR ?= examples/qwen_edit_smoke
RUNPOD_QWEN_EDIT_OUTPUT ?= $(RUNPOD_DATA_DIR)/qwen_edit_smoke/qwen-edit-smoke.png
RUNPOD_QWEN_EDIT_REPORT ?= $(RUNPOD_DATA_DIR)/qwen_edit_smoke/qwen-edit-smoke.json
RUNPOD_VTON_CONDITION_PERSON_IMAGE ?= $(RUNPOD_QWEN_EDIT_PERSON_IMAGE)
RUNPOD_VTON_CONDITION_GARMENT_IMAGE ?= $(RUNPOD_QWEN_EDIT_GARMENT_IMAGE)
RUNPOD_VTON_CONDITION_PERSON_OUTPUT ?= $(RUNPOD_DATA_DIR)/vton_conditioned/person-front.png
RUNPOD_VTON_CONDITION_GARMENT_OUTPUT ?= $(RUNPOD_DATA_DIR)/vton_conditioned/garment.png
RUNPOD_VTON_CONDITION_REPORT ?= $(RUNPOD_DATA_DIR)/vton_conditioned/report.json
RUNPOD_VTON_CONDITION_PERSON_MAX_SIZE ?= 1024
RUNPOD_VTON_CONDITION_PERSON_CANVAS_SIZE ?= 768x1024
RUNPOD_VTON_CONDITION_PERSON_BORDER_RATIO ?= 0.06
RUNPOD_VTON_CONDITION_PERSON_FRAMING ?= full_body
RUNPOD_VTON_CONDITION_PERSON_CLEAN_BACKGROUND ?= 1
RUNPOD_VTON_CONDITION_GARMENT_CANVAS_SIZE ?= 1024
RUNPOD_VTON_CONDITION_GARMENT_BORDER_RATIO ?= 0.08
RUNPOD_VTON_CONDITION_GARMENT_LARGEST_COMPONENT ?= 1
RUNPOD_VTON_CONDITION_BACKGROUND ?= 250,250,250
RUNPOD_VTON_CONDITION_FOREGROUND_THRESHOLD ?= 28
RUNPOD_VTON_INPUT_QUALITY_REPORT ?= $(RUNPOD_DATA_DIR)/vton_input_quality/report.json
RUNPOD_VTON_INPUT_GARMENT_CATEGORY ?= $(RUNPOD_SMOKE_GARMENT_CATEGORY)
RUNPOD_WEB_GARMENT_ID ?= 2
RUNPOD_WEB_GARMENT_SOURCE ?= data/garment_catalog/garment-$(RUNPOD_WEB_GARMENT_ID).webp
RUNPOD_WEB_GARMENT_CONDITION_PERSON_OUTPUT ?= $(RUNPOD_DATA_DIR)/vton_conditioned/web-garment-$(RUNPOD_WEB_GARMENT_ID)-person-front.png
RUNPOD_WEB_GARMENT_CONDITION_GARMENT_OUTPUT ?= $(RUNPOD_DATA_DIR)/vton_conditioned/web-garment-$(RUNPOD_WEB_GARMENT_ID)-garment.png
RUNPOD_WEB_GARMENT_CONDITION_REPORT ?= $(RUNPOD_DATA_DIR)/vton_conditioned/web-garment-$(RUNPOD_WEB_GARMENT_ID)-report.json
RUNPOD_LEFFA_WEB_GARMENT_OUTPUT ?= $(RUNPOD_DATA_DIR)/leffa_smoke/leffa-web-garment-$(RUNPOD_WEB_GARMENT_ID).png
RUNPOD_LEFFA_WEB_GARMENT_REPORT ?= $(RUNPOD_DATA_DIR)/leffa_smoke/leffa-web-garment-$(RUNPOD_WEB_GARMENT_ID).json
RUNPOD_LEFFA_WEB_DETAIL_STEPS ?= 50
RUNPOD_LEFFA_WEB_DETAIL_GUIDANCE_SCALE ?= 3.5
RUNPOD_LEFFA_WEB_DETAIL_OUTPUT ?= $(RUNPOD_DATA_DIR)/leffa_smoke/leffa-web-garment-$(RUNPOD_WEB_GARMENT_ID)-detail.png
RUNPOD_LEFFA_WEB_DETAIL_REPORT ?= $(RUNPOD_DATA_DIR)/leffa_smoke/leffa-web-garment-$(RUNPOD_WEB_GARMENT_ID)-detail.json
RUNPOD_UPPER_BODY_CONDITION_PERSON_OUTPUT ?= $(RUNPOD_DATA_DIR)/vton_conditioned/web-garment-$(RUNPOD_WEB_GARMENT_ID)-upper-person.png
RUNPOD_UPPER_BODY_CONDITION_GARMENT_OUTPUT ?= $(RUNPOD_DATA_DIR)/vton_conditioned/web-garment-$(RUNPOD_WEB_GARMENT_ID)-upper-garment.png
RUNPOD_UPPER_BODY_CONDITION_REPORT ?= $(RUNPOD_DATA_DIR)/vton_conditioned/web-garment-$(RUNPOD_WEB_GARMENT_ID)-upper-report.json
RUNPOD_LEFFA_UPPER_BODY_WEB_GARMENT_OUTPUT ?= $(RUNPOD_DATA_DIR)/leffa_smoke/leffa-web-garment-$(RUNPOD_WEB_GARMENT_ID)-upper.png
RUNPOD_LEFFA_UPPER_BODY_WEB_GARMENT_REPORT ?= $(RUNPOD_DATA_DIR)/leffa_smoke/leffa-web-garment-$(RUNPOD_WEB_GARMENT_ID)-upper.json
RUNPOD_CATVTON_REPO_URL ?= https://github.com/Zheng-Chong/CatVTON.git
RUNPOD_CATVTON_ROOT ?= $(RUNPOD_MODEL_DIR)/external/CatVTON
RUNPOD_CATVTON_BASE_MODEL ?= runwayml/stable-diffusion-inpainting
RUNPOD_CATVTON_RESUME_PATH ?= zhengchong/CatVTON
RUNPOD_CATVTON_SIZE ?= 512x768
RUNPOD_CATVTON_DEVICE ?= cuda
RUNPOD_CATVTON_MIXED_PRECISION ?= bf16
RUNPOD_CATVTON_CLOTH_TYPE ?= $(RUNPOD_SMOKE_GARMENT_CATEGORY)
RUNPOD_CATVTON_MASK_MODE ?= auto
RUNPOD_CATVTON_STEPS ?= 8
RUNPOD_CATVTON_GUIDANCE_SCALE ?= 2.5
RUNPOD_CATVTON_SEED ?= 42
RUNPOD_CATVTON_PERSON_IMAGE ?= $(RUNPOD_QWEN_EDIT_PERSON_IMAGE)
RUNPOD_CATVTON_GARMENT_IMAGE ?= $(RUNPOD_QWEN_EDIT_GARMENT_IMAGE)
RUNPOD_CATVTON_OUTPUT ?= $(RUNPOD_DATA_DIR)/catvton_smoke/catvton-smoke.png
RUNPOD_CATVTON_REPORT ?= $(RUNPOD_DATA_DIR)/catvton_smoke/catvton-smoke.json
RUNPOD_CATVTON_QUALITY_SIZE ?= 768x1024
RUNPOD_CATVTON_QUALITY_STEPS ?= 30
RUNPOD_CATVTON_QUALITY_OUTPUT ?= $(RUNPOD_DATA_DIR)/catvton_smoke/catvton-quality-smoke.png
RUNPOD_CATVTON_QUALITY_REPORT ?= $(RUNPOD_DATA_DIR)/catvton_smoke/catvton-quality-smoke.json
RUNPOD_LEFFA_REPO_URL ?= https://github.com/franciszzj/Leffa.git
RUNPOD_LEFFA_ROOT ?= $(RUNPOD_MODEL_DIR)/external/Leffa
RUNPOD_LEFFA_VENV ?= $(RUNPOD_MODEL_DIR)/venvs/leffa
RUNPOD_LEFFA_PYTHON ?= $(RUNPOD_LEFFA_VENV)/bin/python
RUNPOD_LEFFA_MODEL_REPO_ID ?= franciszzj/Leffa
RUNPOD_LEFFA_CHECKPOINT_DIR ?= $(RUNPOD_LEFFA_ROOT)/ckpts
RUNPOD_LEFFA_SIZE ?= 768x1024
RUNPOD_LEFFA_DEVICE ?= cuda
RUNPOD_LEFFA_DTYPE ?= float16
RUNPOD_LEFFA_VT_MODEL_TYPE ?= viton_hd
RUNPOD_LEFFA_GARMENT_TYPE ?= upper_body
RUNPOD_LEFFA_STEPS ?= 30
RUNPOD_LEFFA_GUIDANCE_SCALE ?= 2.5
RUNPOD_LEFFA_SEED ?= 42
RUNPOD_LEFFA_REF_ACCELERATION ?= 0
RUNPOD_LEFFA_REPAINT ?= 0
RUNPOD_LEFFA_PREPROCESS_GARMENT ?= 0
RUNPOD_LEFFA_PERSON_IMAGE ?= $(RUNPOD_QWEN_EDIT_PERSON_IMAGE)
RUNPOD_LEFFA_GARMENT_IMAGE ?= $(RUNPOD_QWEN_EDIT_GARMENT_IMAGE)
RUNPOD_LEFFA_OUTPUT ?= $(RUNPOD_DATA_DIR)/leffa_smoke/leffa-smoke.png
RUNPOD_LEFFA_REPORT ?= $(RUNPOD_DATA_DIR)/leffa_smoke/leffa-smoke.json
RUNPOD_LEFFA_CONDITIONED_OUTPUT ?= $(RUNPOD_DATA_DIR)/leffa_smoke/leffa-conditioned-smoke.png
RUNPOD_LEFFA_CONDITIONED_REPORT ?= $(RUNPOD_DATA_DIR)/leffa_smoke/leffa-conditioned-smoke.json
RUNPOD_OMNIVTON_REPO_URL ?= https://github.com/Jerome-Young/OmniVTON.git
RUNPOD_OMNIVTON_ROOT ?= $(RUNPOD_MODEL_DIR)/external/OmniVTON
RUNPOD_OMNIVTON_MODEL_ID ?= sd2_inp
RUNPOD_OMNIVTON_STAGE ?= preflight
RUNPOD_OMNIVTON_SIZE ?= 384x512
RUNPOD_OMNIVTON_DEVICE ?= cuda
RUNPOD_OMNIVTON_STEPS ?= 30
RUNPOD_OMNIVTON_GUIDANCE_SCALE ?= 7.5
RUNPOD_OMNIVTON_SEED ?= 42
RUNPOD_OMNIVTON_PERSON_IMAGE ?= $(RUNPOD_QWEN_EDIT_PERSON_IMAGE)
RUNPOD_OMNIVTON_GARMENT_IMAGE ?= $(RUNPOD_QWEN_EDIT_GARMENT_IMAGE)
RUNPOD_OMNIVTON_WORK_DIR ?= $(RUNPOD_DATA_DIR)/omnivton_smoke/work
RUNPOD_OMNIVTON_OUTPUT ?= $(RUNPOD_DATA_DIR)/omnivton_smoke/omnivton-smoke.png
RUNPOD_OMNIVTON_REPORT ?= $(RUNPOD_DATA_DIR)/omnivton_smoke/omnivton-smoke.json
RUNPOD_OMNIVTON_WEB_GARMENT_OUTPUT ?= $(RUNPOD_DATA_DIR)/omnivton_smoke/omnivton-web-garment-$(RUNPOD_WEB_GARMENT_ID).png
RUNPOD_OMNIVTON_WEB_GARMENT_REPORT ?= $(RUNPOD_DATA_DIR)/omnivton_smoke/omnivton-web-garment-$(RUNPOD_WEB_GARMENT_ID).json
RUNPOD_OMNIVTON_WEB_GARMENT_WORK_DIR ?= $(RUNPOD_DATA_DIR)/omnivton_smoke/web-garment-$(RUNPOD_WEB_GARMENT_ID)-work
RUNPOD_HF_HOME ?= $(RUNPOD_MODEL_DIR)/huggingface
RUNPOD_TORCH_HOME ?= $(RUNPOD_MODEL_DIR)/torch
RUNPOD_PIP_CACHE_DIR ?= $(RUNPOD_MODEL_DIR)/pip-cache
RUNPOD_TORCH_VERSION ?= 2.8.0
RUNPOD_TORCHVISION_VERSION ?= 0.23.0
RUNPOD_TORCH_CUDA_INDEX ?= https://download.pytorch.org/whl/cu128
RUNPOD_TORCH_CU124_VERSION ?= 2.6.0
RUNPOD_TORCHVISION_CU124_VERSION ?= 0.21.0
RUNPOD_TORCHAUDIO_CU124_VERSION ?= 2.6.0
RUNPOD_TORCH_CU124_INDEX ?= https://download.pytorch.org/whl/cu124
RUNPOD_LEFFA_FORCE_REINSTALL ?= 0

.PHONY: help setup install install-kiosk run run-kiosk run-kiosk-all ui-kiosk kiosk-seed-size-charts kiosk-reset worker worker-once kiosk-preflight runpod-help runpod-init runpod-install runpod-install-qwen-edit-deps runpod-install-torch-cu124 runpod-install-catvton-deps runpod-install-leffa-torch-cu124 runpod-install-leffa-deps runpod-leffa-deps-check runpod-install-omnivton-deps runpod-catvton-import-check runpod-leffa-import-check runpod-omnivton-import-check runpod-pull-ollama runpod-reset runpod-start runpod-start-with-ollama runpod-preflight runpod-disk-report runpod-cuda-report runpod-qwen-edit-smoke-data runpod-vton-smoke-data runpod-vton-input-quality runpod-vton-condition-smoke-inputs runpod-leffa-smoke-data runpod-qwen-edit-smoke runpod-catvton-smoke runpod-catvton-quality-smoke runpod-leffa-smoke runpod-leffa-conditioned-smoke runpod-leffa-web-garment-smoke runpod-leffa-web-garment-detail-smoke runpod-leffa-upper-body-web-garment-smoke runpod-omnivton-smoke runpod-omnivton-outpainting-smoke runpod-omnivton-web-garment-smoke test clean lint format check

help:
	@echo "Virtual Try-On MVP - Makefile commands"
	@echo ""
	@echo "  make setup      - Setup environment và download models"
	@echo "  make install    - Install dependencies only"
	@echo "  make install-kiosk - Install lightweight kiosk API dependencies"
	@echo "  make run        - Run FastAPI server"
	@echo "  make run-kiosk  - Run kiosk API on 0.0.0.0:8080 for deployed pods"
	@echo "  make run-kiosk-all - Run kiosk API + worker in one foreground process"
	@echo "  make ui-kiosk   - Serve the static kiosk app UI on 127.0.0.1:$(UI_PORT)"
	@echo "  make kiosk-seed-size-charts - Import default local kiosk size charts"
	@echo "  make kiosk-reset - Reset local runtime test data and seed default size charts"
	@echo "  make worker     - Run local kiosk worker loop"
	@echo "  make worker-once - Process one local kiosk job"
	@echo "  make kiosk-preflight - Check running kiosk API readiness"
	@echo ""
	@echo "RunPod phase 1:"
	@echo "  make runpod-help - Show the minimum RunPod smoke-test commands"
	@echo "  make runpod-init - Create .env from template and runtime directories"
	@echo "  make runpod-install - Install kiosk API dependencies and initialize paths"
	@echo "  make runpod-pull-ollama - Pull the configured Ollama analyzer model"
	@echo "  make runpod-start - Run kiosk API + worker"
	@echo "  make runpod-start-with-ollama - Run kiosk API + worker + ollama serve"
	@echo "  make runpod-preflight - Check running RunPod kiosk readiness"
	@echo "  make runpod-reset - Reset runtime test data and seed default size charts"
	@echo "  make runpod-install-qwen-edit-deps - Install latest Diffusers stack for local Qwen-edit smoke"
	@echo "  make runpod-install-torch-cu124 - Downgrade Torch stack for pods with CUDA 12.4 driver"
	@echo "  make runpod-disk-report - Print storage/cache usage for RunPod debugging"
	@echo "  make runpod-cuda-report - Print NVIDIA/PyTorch CUDA diagnostics"
	@echo "  make runpod-qwen-edit-smoke-data - Prepare synthetic local Qwen-edit smoke inputs"
	@echo "  make runpod-vton-smoke-data - Alias for shared Qwen/CatVTON/Leffa smoke inputs"
	@echo "  make runpod-vton-input-quality RUNPOD_VTON_INPUT_GARMENT_CATEGORY=tops - Score person/garment input quality before VTON"
	@echo "  make runpod-vton-condition-smoke-inputs - Normalize person/garment images for VTON smoke A/B"
	@echo "  make runpod-leffa-smoke-data - Alias for shared Qwen/CatVTON/Leffa smoke inputs"
	@echo "  make runpod-qwen-edit-smoke - Run local Qwen-edit smoke with prepared/default inputs"
	@echo "  make runpod-install-catvton-deps - Install extra deps for local CatVTON smoke"
	@echo "  make runpod-catvton-import-check - Validate CatVTON imports without loading models"
	@echo "  make runpod-catvton-smoke - Run cheap local CatVTON canary with prepared/default inputs"
	@echo "  make runpod-catvton-quality-smoke - Run full CatVTON quality smoke after canary passes"
	@echo "  make runpod-install-leffa-deps - Install local Leffa deps into isolated model venv"
	@echo "  make runpod-install-leffa-torch-cu124 - Fix Leffa venv Torch for CUDA 12.4/12.7 drivers"
	@echo "  make runpod-leffa-deps-check - Check cached Leffa runtime without reinstalling"
	@echo "  make runpod-leffa-import-check - Validate Leffa imports without loading models"
	@echo "  make runpod-leffa-smoke - Run local Leffa smoke with prepared/default inputs"
	@echo "  make runpod-leffa-conditioned-smoke - Run Leffa with normalized smoke inputs"
	@echo "  make runpod-leffa-web-garment-smoke RUNPOD_WEB_GARMENT_ID=2 - Run Leffa with data/garment_catalog web garment"
	@echo "  make runpod-leffa-upper-body-web-garment-smoke RUNPOD_WEB_GARMENT_ID=2 - Run Leffa with upper-body crop"
	@echo "  make runpod-install-omnivton-deps - Install extra deps for local OmniVTON smoke"
	@echo "  make runpod-omnivton-import-check - Validate OmniVTON imports without loading models"
	@echo "  make runpod-omnivton-outpainting-smoke - Run OmniVTON stage-1 runtime smoke"
	@echo "  make runpod-omnivton-web-garment-smoke RUNPOD_WEB_GARMENT_ID=2 - Run OmniVTON web-garment preflight/VTON smoke"
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

install-kiosk:
	pip install -U pip
	mkdir -p "$(RUNPOD_PIP_CACHE_DIR)"
	PIP_CACHE_DIR="$(RUNPOD_PIP_CACHE_DIR)" pip install -r $(RUNPOD_REQUIREMENTS)

run:
	python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8080

ui-kiosk:
	python3 -m http.server $(UI_PORT) --bind 127.0.0.1 --directory ui/kiosk-demo

kiosk-seed-size-charts:
	python -m scripts.seed_size_charts --db-path $(LOCAL_DATA_DIR)/size_charts/size_charts.sqlite3

kiosk-reset:
	python -m scripts.reset_kiosk_state --data-dir $(LOCAL_DATA_DIR) --execute --include-runtime-files --seed-default-size-charts

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
	@echo "  edit .env and set CORS_ORIGINS; set REPLICATE_API_TOKEN only for Replicate debug"
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
	@echo "  make runpod-install-torch-cu124  # only when CUDA driver is too old for cu128"
	@echo "  make runpod-disk-report"
	@echo "  make runpod-cuda-report"
	@echo "  make runpod-qwen-edit-smoke-data"
	@echo "  make runpod-qwen-edit-smoke"
	@echo ""
	@echo "Optional local CatVTON smoke:"
	@echo "  make runpod-install-catvton-deps"
	@echo "  make runpod-catvton-import-check"
	@echo "  make runpod-vton-smoke-data"
	@echo "  make runpod-catvton-smoke"
	@echo "  make runpod-catvton-quality-smoke"
	@echo ""
	@echo "Optional local Leffa smoke:"
	@echo "  make runpod-install-leffa-deps"
	@echo "  make runpod-leffa-deps-check"
	@echo "  make runpod-leffa-import-check"
	@echo "  make runpod-leffa-smoke-data"
	@echo "  make runpod-vton-condition-smoke-inputs"
	@echo "  make runpod-leffa-smoke"
	@echo "  make runpod-leffa-conditioned-smoke"
	@echo ""
	@echo "Optional local OmniVTON smoke:"
	@echo "  make runpod-install-omnivton-deps"
	@echo "  make runpod-omnivton-import-check"
	@echo "  make runpod-omnivton-outpainting-smoke"
	@echo "  make runpod-omnivton-web-garment-smoke RUNPOD_WEB_GARMENT_ID=2"
	@echo "  make runpod-leffa-web-garment-smoke RUNPOD_WEB_GARMENT_ID=2"
	@echo "  make runpod-leffa-web-garment-detail-smoke RUNPOD_WEB_GARMENT_ID=2"

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

runpod-install: runpod-init install-kiosk

runpod-install-qwen-edit-deps:
	PIP_CACHE_DIR="$(RUNPOD_PIP_CACHE_DIR)" pip install --force-reinstall \
		torch==$(RUNPOD_TORCH_VERSION) \
		torchvision==$(RUNPOD_TORCHVISION_VERSION) \
		--index-url $(RUNPOD_TORCH_CUDA_INDEX)
	PIP_CACHE_DIR="$(RUNPOD_PIP_CACHE_DIR)" pip install -U "git+https://github.com/huggingface/diffusers" transformers accelerate safetensors

runpod-install-torch-cu124:
	PIP_CACHE_DIR="$(RUNPOD_PIP_CACHE_DIR)" pip install --force-reinstall \
		torch==$(RUNPOD_TORCH_CU124_VERSION) \
		torchvision==$(RUNPOD_TORCHVISION_CU124_VERSION) \
		torchaudio==$(RUNPOD_TORCHAUDIO_CU124_VERSION) \
		--index-url $(RUNPOD_TORCH_CU124_INDEX)

runpod-install-leffa-torch-cu124:
	mkdir -p "$(RUNPOD_LEFFA_VENV)" "$(RUNPOD_PIP_CACHE_DIR)"
	@if [ ! -x "$(RUNPOD_LEFFA_PYTHON)" ]; then \
		python -m venv "$(RUNPOD_LEFFA_VENV)"; \
		PIP_CACHE_DIR="$(RUNPOD_PIP_CACHE_DIR)" "$(RUNPOD_LEFFA_PYTHON)" -m pip install -U pip setuptools wheel; \
	fi
	@if [ "$(RUNPOD_LEFFA_FORCE_REINSTALL)" != "1" ] && "$(RUNPOD_LEFFA_PYTHON)" -m scripts.check_leffa_runtime --torch-only; then \
		echo "Leffa Torch stack already ready; skipping reinstall."; \
	else \
		echo "Installing Leffa Torch stack into $(RUNPOD_LEFFA_VENV)"; \
		PIP_CACHE_DIR="$(RUNPOD_PIP_CACHE_DIR)" "$(RUNPOD_LEFFA_PYTHON)" -m pip install --force-reinstall \
			torch==$(RUNPOD_TORCH_CU124_VERSION) \
			torchvision==$(RUNPOD_TORCHVISION_CU124_VERSION) \
			torchaudio==$(RUNPOD_TORCHAUDIO_CU124_VERSION) \
			--index-url $(RUNPOD_TORCH_CU124_INDEX); \
	fi

runpod-install-catvton-deps:
	PIP_CACHE_DIR="$(RUNPOD_PIP_CACHE_DIR)" pip install -U \
		"huggingface_hub>=0.23.4" \
		"diffusers>=0.29.2" \
		"transformers>=4.27.3" \
		"accelerate>=0.31.0" \
		"safetensors>=0.4.5" \
		"PyYAML>=6.0.1" \
		"omegaconf>=2.3.0" \
		"scipy>=1.10.1" \
		"tqdm>=4.66.4" \
		"packaging>=24.1" \
		"opencv-python-headless==4.10.0.84" \
		"scikit-image>=0.24.0" \
		"matplotlib>=3.9.1" \
		"ninja>=1.11.1"

runpod-install-leffa-deps: runpod-install-leffa-torch-cu124
	@if [ "$(RUNPOD_LEFFA_FORCE_REINSTALL)" != "1" ] && "$(RUNPOD_LEFFA_PYTHON)" -m scripts.check_leffa_runtime; then \
		echo "Leffa runtime already ready; skipping dependency install."; \
	else \
		PIP_CACHE_DIR="$(RUNPOD_PIP_CACHE_DIR)" "$(RUNPOD_LEFFA_PYTHON)" -m pip install \
			"accelerate>=0.31.0" \
			"av>=12.0.0" \
			"cloudpickle>=3.0.0" \
			"diffusers>=0.29.2" \
			"einops>=0.8.0" \
			"fvcore>=0.1.5.post20221221" \
			"huggingface_hub>=0.23.4" \
			"imageio>=2.34.0" \
			"iopath>=0.1.10" \
			"matplotlib>=3.9.1" \
			"numpy==1.26.4" \
			"omegaconf>=2.3.0" \
			"onnxruntime>=1.18.0" \
			"opencv-python-headless==4.10.0.84" \
			"packaging>=24.1" \
			"pandas>=2.2.2" \
			"peft>=0.11.1" \
			"pillow>=10.4.0" \
			"psutil>=6.0.0" \
			"pycocotools>=2.0.8" \
			"PyYAML>=6.0.1" \
			"regex==2024.5.15" \
			"safetensors>=0.4.5" \
			"scikit-image>=0.24.0" \
			"scipy>=1.10.1" \
			"tabulate>=0.9.0" \
			"termcolor>=2.4.0" \
			"timm>=1.0.7" \
			"tokenizers>=0.19.1" \
			"torchmetrics>=1.4.0" \
			"tqdm>=4.66.4" \
			"transformers>=4.43.0" \
			"yacs>=0.1.8"; \
	fi
	@echo "Leffa runtime installed at $(RUNPOD_LEFFA_VENV)"
	@echo "Set LOCAL_LEFFA_PYTHON=$(RUNPOD_LEFFA_PYTHON) before make runpod-start"

runpod-leffa-deps-check:
	@test -x "$(RUNPOD_LEFFA_PYTHON)" || (echo "Missing Leffa runtime: $(RUNPOD_LEFFA_PYTHON). Run make runpod-install-leffa-deps first."; exit 1)
	"$(RUNPOD_LEFFA_PYTHON)" -m scripts.check_leffa_runtime

runpod-install-omnivton-deps:
	PIP_CACHE_DIR="$(RUNPOD_PIP_CACHE_DIR)" pip install -U \
		"accelerate>=0.31.0" \
		"diffusers>=0.29.2" \
		"einops>=0.7.0" \
		"ftfy>=6.2.0" \
		"huggingface_hub>=0.23.4" \
		"matplotlib>=3.9.1" \
		"omegaconf>=2.3.0" \
		"open_clip_torch>=2.24.0" \
		"opencv-python-headless==4.10.0.84" \
		"packaging>=24.1" \
		"PyYAML>=6.0.1" \
		"safetensors>=0.4.5" \
		"scikit-image>=0.24.0" \
		"scipy>=1.10.1" \
		"tqdm>=4.66.4" \
		"transformers>=4.43.0"

runpod-catvton-import-check:
	HF_HOME="$(RUNPOD_HF_HOME)" \
	TRANSFORMERS_CACHE="$(RUNPOD_HF_HOME)/transformers" \
	HUGGINGFACE_HUB_CACHE="$(RUNPOD_HF_HOME)/hub" \
	TORCH_HOME="$(RUNPOD_TORCH_HOME)" \
	XDG_CACHE_HOME="$(RUNPOD_MODEL_DIR)/xdg-cache" \
	python -m scripts.local_catvton_smoke \
		--person-image "$(RUNPOD_CATVTON_PERSON_IMAGE)" \
		--garment-image "$(RUNPOD_CATVTON_GARMENT_IMAGE)" \
		--output "$(RUNPOD_CATVTON_OUTPUT)" \
		--report "$(RUNPOD_CATVTON_REPORT)" \
		--catvton-root "$(RUNPOD_CATVTON_ROOT)" \
		--repo-url "$(RUNPOD_CATVTON_REPO_URL)" \
			--device cpu \
			--mask-mode "$(RUNPOD_CATVTON_MASK_MODE)" \
			--check-imports-only

runpod-leffa-import-check:
	HF_HOME="$(RUNPOD_HF_HOME)" \
	TRANSFORMERS_CACHE="$(RUNPOD_HF_HOME)/transformers" \
	HUGGINGFACE_HUB_CACHE="$(RUNPOD_HF_HOME)/hub" \
	TORCH_HOME="$(RUNPOD_TORCH_HOME)" \
	XDG_CACHE_HOME="$(RUNPOD_MODEL_DIR)/xdg-cache" \
	"$(RUNPOD_LEFFA_PYTHON)" -m scripts.local_leffa_smoke \
		--person-image "$(RUNPOD_LEFFA_PERSON_IMAGE)" \
		--garment-image "$(RUNPOD_LEFFA_GARMENT_IMAGE)" \
		--output "$(RUNPOD_LEFFA_OUTPUT)" \
		--report "$(RUNPOD_LEFFA_REPORT)" \
		--leffa-root "$(RUNPOD_LEFFA_ROOT)" \
		--repo-url "$(RUNPOD_LEFFA_REPO_URL)" \
		--model-repo-id "$(RUNPOD_LEFFA_MODEL_REPO_ID)" \
		--checkpoint-dir "$(RUNPOD_LEFFA_CHECKPOINT_DIR)" \
		--device cpu \
		--check-imports-only

runpod-omnivton-import-check:
	HF_HOME="$(RUNPOD_HF_HOME)" \
	TRANSFORMERS_CACHE="$(RUNPOD_HF_HOME)/transformers" \
	HUGGINGFACE_HUB_CACHE="$(RUNPOD_HF_HOME)/hub" \
	TORCH_HOME="$(RUNPOD_TORCH_HOME)" \
	XDG_CACHE_HOME="$(RUNPOD_MODEL_DIR)/xdg-cache" \
	python -m scripts.local_omnivton_smoke \
		--person-image "$(RUNPOD_OMNIVTON_PERSON_IMAGE)" \
		--garment-image "$(RUNPOD_OMNIVTON_GARMENT_IMAGE)" \
		--output "$(RUNPOD_OMNIVTON_OUTPUT)" \
		--report "$(RUNPOD_OMNIVTON_REPORT)" \
		--omnivton-root "$(RUNPOD_OMNIVTON_ROOT)" \
		--repo-url "$(RUNPOD_OMNIVTON_REPO_URL)" \
		--device cpu \
		--check-imports-only

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
	python -m scripts.prepare_qwen_edit_smoke_data \
		--data-dir $(RUNPOD_DATA_DIR) \
		--fixture-dir $(RUNPOD_QWEN_EDIT_FIXTURE_DIR) \
		--garment-category $(RUNPOD_SMOKE_GARMENT_CATEGORY) \
		$(if $(filter 1 true yes,$(RUNPOD_SMOKE_DATA_OVERWRITE)),--overwrite,)

runpod-vton-smoke-data: runpod-qwen-edit-smoke-data

runpod-leffa-smoke-data: runpod-qwen-edit-smoke-data

runpod-vton-input-quality: runpod-leffa-smoke-data
	$(eval PERSON_IMAGE_PATH := $(or $(PERSON_IMAGE),$(RUNPOD_QWEN_EDIT_PERSON_IMAGE)))
	$(eval GARMENT_IMAGE_PATH := $(or $(GARMENT_IMAGE),$(RUNPOD_QWEN_EDIT_GARMENT_IMAGE)))
	@test -f "$(PERSON_IMAGE_PATH)" || (echo "Missing PERSON_IMAGE=$(PERSON_IMAGE_PATH). Run make runpod-leffa-smoke-data or pass PERSON_IMAGE=/path/to/front.png"; exit 2)
	@test -f "$(GARMENT_IMAGE_PATH)" || (echo "Missing GARMENT_IMAGE=$(GARMENT_IMAGE_PATH). Run make runpod-leffa-smoke-data or pass GARMENT_IMAGE=/path/to/garment.png"; exit 2)
	python -m scripts.score_vton_input_quality \
		--person-image "$(PERSON_IMAGE_PATH)" \
		--garment-image "$(GARMENT_IMAGE_PATH)" \
		--report "$(RUNPOD_VTON_INPUT_QUALITY_REPORT)" \
		--garment-category "$(RUNPOD_VTON_INPUT_GARMENT_CATEGORY)" \
		--background "$(RUNPOD_VTON_CONDITION_BACKGROUND)" \
		--foreground-threshold "$(RUNPOD_VTON_CONDITION_FOREGROUND_THRESHOLD)"

runpod-vton-condition-smoke-inputs:
	$(eval PERSON_IMAGE_PATH := $(or $(PERSON_IMAGE),$(RUNPOD_VTON_CONDITION_PERSON_IMAGE)))
	$(eval GARMENT_IMAGE_PATH := $(or $(GARMENT_IMAGE),$(RUNPOD_VTON_CONDITION_GARMENT_IMAGE)))
	@test -f "$(PERSON_IMAGE_PATH)" || (echo "Missing PERSON_IMAGE=$(PERSON_IMAGE_PATH). Run make runpod-leffa-smoke-data or pass PERSON_IMAGE=/path/to/front.png"; exit 2)
	@test -f "$(GARMENT_IMAGE_PATH)" || (echo "Missing GARMENT_IMAGE=$(GARMENT_IMAGE_PATH). Run make runpod-leffa-smoke-data or pass GARMENT_IMAGE=/path/to/garment.png"; exit 2)
	python -m scripts.prepare_vton_conditioned_inputs \
		--person-image "$(PERSON_IMAGE_PATH)" \
		--garment-image "$(GARMENT_IMAGE_PATH)" \
		--person-output "$(RUNPOD_VTON_CONDITION_PERSON_OUTPUT)" \
		--garment-output "$(RUNPOD_VTON_CONDITION_GARMENT_OUTPUT)" \
		--report "$(RUNPOD_VTON_CONDITION_REPORT)" \
		--person-max-size "$(RUNPOD_VTON_CONDITION_PERSON_MAX_SIZE)" \
		--person-canvas-size "$(RUNPOD_VTON_CONDITION_PERSON_CANVAS_SIZE)" \
		--person-border-ratio "$(RUNPOD_VTON_CONDITION_PERSON_BORDER_RATIO)" \
		--person-framing "$(RUNPOD_VTON_CONDITION_PERSON_FRAMING)" \
		$(if $(filter 1 true yes,$(RUNPOD_VTON_CONDITION_PERSON_CLEAN_BACKGROUND)),--person-clean-background,--no-person-clean-background) \
		--garment-canvas-size "$(RUNPOD_VTON_CONDITION_GARMENT_CANVAS_SIZE)" \
		--garment-border-ratio "$(RUNPOD_VTON_CONDITION_GARMENT_BORDER_RATIO)" \
		$(if $(filter 1 true yes,$(RUNPOD_VTON_CONDITION_GARMENT_LARGEST_COMPONENT)),--garment-largest-component,--no-garment-largest-component) \
		--background "$(RUNPOD_VTON_CONDITION_BACKGROUND)" \
		--foreground-threshold "$(RUNPOD_VTON_CONDITION_FOREGROUND_THRESHOLD)"

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
	PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True" \
	python -m scripts.local_qwen_edit_smoke \
		--person-image "$(PERSON_IMAGE_PATH)" \
		--garment-image "$(GARMENT_IMAGE_PATH)" \
		--output "$(RUNPOD_QWEN_EDIT_OUTPUT)" \
		--report "$(RUNPOD_QWEN_EDIT_REPORT)" \
		--model-id "$(RUNPOD_QWEN_EDIT_MODEL)" \
		--pipeline edit-plus \
		--size "$(RUNPOD_QWEN_EDIT_SIZE)" \
		--input-max-size "$(RUNPOD_QWEN_EDIT_INPUT_MAX_SIZE)" \
		--device "$(RUNPOD_QWEN_EDIT_DEVICE)" \
		--device-map "$(RUNPOD_QWEN_EDIT_DEVICE_MAP)" \
		$(if $(filter 1 true yes,$(RUNPOD_QWEN_EDIT_CPU_OFFLOAD)),--cpu-offload,--no-cpu-offload) \
		$(if $(filter 1 true yes,$(RUNPOD_QWEN_EDIT_SEQUENTIAL_CPU_OFFLOAD)),--sequential-cpu-offload,--no-sequential-cpu-offload) \
		--steps "$(RUNPOD_QWEN_EDIT_STEPS)"

runpod-catvton-smoke:
	$(eval PERSON_IMAGE_PATH := $(or $(PERSON_IMAGE),$(RUNPOD_CATVTON_PERSON_IMAGE)))
	$(eval GARMENT_IMAGE_PATH := $(or $(GARMENT_IMAGE),$(RUNPOD_CATVTON_GARMENT_IMAGE)))
	@test -f "$(PERSON_IMAGE_PATH)" || (echo "Missing PERSON_IMAGE=$(PERSON_IMAGE_PATH). Run make runpod-qwen-edit-smoke-data or pass PERSON_IMAGE=/path/to/front.png"; exit 2)
	@test -f "$(GARMENT_IMAGE_PATH)" || (echo "Missing GARMENT_IMAGE=$(GARMENT_IMAGE_PATH). Run make runpod-qwen-edit-smoke-data or pass GARMENT_IMAGE=/path/to/garment.png"; exit 2)
	HF_HOME="$(RUNPOD_HF_HOME)" \
	TRANSFORMERS_CACHE="$(RUNPOD_HF_HOME)/transformers" \
	HUGGINGFACE_HUB_CACHE="$(RUNPOD_HF_HOME)/hub" \
	TORCH_HOME="$(RUNPOD_TORCH_HOME)" \
	XDG_CACHE_HOME="$(RUNPOD_MODEL_DIR)/xdg-cache" \
	PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True" \
	python -m scripts.local_catvton_smoke \
		--person-image "$(PERSON_IMAGE_PATH)" \
		--garment-image "$(GARMENT_IMAGE_PATH)" \
		--output "$(RUNPOD_CATVTON_OUTPUT)" \
		--report "$(RUNPOD_CATVTON_REPORT)" \
		--catvton-root "$(RUNPOD_CATVTON_ROOT)" \
		--repo-url "$(RUNPOD_CATVTON_REPO_URL)" \
		--base-model-path "$(RUNPOD_CATVTON_BASE_MODEL)" \
		--resume-path "$(RUNPOD_CATVTON_RESUME_PATH)" \
		--size "$(RUNPOD_CATVTON_SIZE)" \
		--device "$(RUNPOD_CATVTON_DEVICE)" \
		--mixed-precision "$(RUNPOD_CATVTON_MIXED_PRECISION)" \
		--cloth-type "$(RUNPOD_CATVTON_CLOTH_TYPE)" \
		--mask-mode "$(RUNPOD_CATVTON_MASK_MODE)" \
		--steps "$(RUNPOD_CATVTON_STEPS)" \
		--guidance-scale "$(RUNPOD_CATVTON_GUIDANCE_SCALE)" \
		--seed "$(RUNPOD_CATVTON_SEED)"

runpod-catvton-quality-smoke:
	$(MAKE) runpod-catvton-smoke \
		RUNPOD_CATVTON_SIZE="$(RUNPOD_CATVTON_QUALITY_SIZE)" \
		RUNPOD_CATVTON_STEPS="$(RUNPOD_CATVTON_QUALITY_STEPS)" \
		RUNPOD_CATVTON_OUTPUT="$(RUNPOD_CATVTON_QUALITY_OUTPUT)" \
		RUNPOD_CATVTON_REPORT="$(RUNPOD_CATVTON_QUALITY_REPORT)"

runpod-leffa-smoke:
	$(eval PERSON_IMAGE_PATH := $(or $(PERSON_IMAGE),$(RUNPOD_LEFFA_PERSON_IMAGE)))
	$(eval GARMENT_IMAGE_PATH := $(or $(GARMENT_IMAGE),$(RUNPOD_LEFFA_GARMENT_IMAGE)))
	@test -f "$(PERSON_IMAGE_PATH)" || (echo "Missing PERSON_IMAGE=$(PERSON_IMAGE_PATH). Run make runpod-qwen-edit-smoke-data or pass PERSON_IMAGE=/path/to/front.png"; exit 2)
	@test -f "$(GARMENT_IMAGE_PATH)" || (echo "Missing GARMENT_IMAGE=$(GARMENT_IMAGE_PATH). Run make runpod-qwen-edit-smoke-data or pass GARMENT_IMAGE=/path/to/garment.png"; exit 2)
	HF_HOME="$(RUNPOD_HF_HOME)" \
	TRANSFORMERS_CACHE="$(RUNPOD_HF_HOME)/transformers" \
	HUGGINGFACE_HUB_CACHE="$(RUNPOD_HF_HOME)/hub" \
	TORCH_HOME="$(RUNPOD_TORCH_HOME)" \
	XDG_CACHE_HOME="$(RUNPOD_MODEL_DIR)/xdg-cache" \
	PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True" \
	"$(RUNPOD_LEFFA_PYTHON)" -m scripts.local_leffa_smoke \
		--person-image "$(PERSON_IMAGE_PATH)" \
		--garment-image "$(GARMENT_IMAGE_PATH)" \
		--output "$(RUNPOD_LEFFA_OUTPUT)" \
		--report "$(RUNPOD_LEFFA_REPORT)" \
		--leffa-root "$(RUNPOD_LEFFA_ROOT)" \
		--repo-url "$(RUNPOD_LEFFA_REPO_URL)" \
		--model-repo-id "$(RUNPOD_LEFFA_MODEL_REPO_ID)" \
		--checkpoint-dir "$(RUNPOD_LEFFA_CHECKPOINT_DIR)" \
		--size "$(RUNPOD_LEFFA_SIZE)" \
		--device "$(RUNPOD_LEFFA_DEVICE)" \
		--dtype "$(RUNPOD_LEFFA_DTYPE)" \
		--vt-model-type "$(RUNPOD_LEFFA_VT_MODEL_TYPE)" \
		--garment-type "$(RUNPOD_LEFFA_GARMENT_TYPE)" \
		$(if $(filter 1 true yes,$(RUNPOD_LEFFA_REF_ACCELERATION)),--ref-acceleration,--no-ref-acceleration) \
		$(if $(filter 1 true yes,$(RUNPOD_LEFFA_REPAINT)),--repaint,--no-repaint) \
		$(if $(filter 1 true yes,$(RUNPOD_LEFFA_PREPROCESS_GARMENT)),--preprocess-garment,--no-preprocess-garment) \
		--steps "$(RUNPOD_LEFFA_STEPS)" \
		--guidance-scale "$(RUNPOD_LEFFA_GUIDANCE_SCALE)" \
		--seed "$(RUNPOD_LEFFA_SEED)"

runpod-leffa-conditioned-smoke: runpod-vton-condition-smoke-inputs
	$(MAKE) runpod-leffa-smoke \
		PERSON_IMAGE="$(RUNPOD_VTON_CONDITION_PERSON_OUTPUT)" \
		GARMENT_IMAGE="$(RUNPOD_VTON_CONDITION_GARMENT_OUTPUT)" \
		RUNPOD_LEFFA_OUTPUT="$(RUNPOD_LEFFA_CONDITIONED_OUTPUT)" \
		RUNPOD_LEFFA_REPORT="$(RUNPOD_LEFFA_CONDITIONED_REPORT)"

runpod-leffa-web-garment-smoke: runpod-leffa-smoke-data
	@test -f "$(RUNPOD_WEB_GARMENT_SOURCE)" || (echo "Missing RUNPOD_WEB_GARMENT_SOURCE=$(RUNPOD_WEB_GARMENT_SOURCE). Use RUNPOD_WEB_GARMENT_ID=2 or 3, or pass RUNPOD_WEB_GARMENT_SOURCE=/path/to/garment.webp"; exit 2)
	$(MAKE) runpod-vton-condition-smoke-inputs \
		PERSON_IMAGE="$(RUNPOD_QWEN_EDIT_PERSON_IMAGE)" \
		GARMENT_IMAGE="$(RUNPOD_WEB_GARMENT_SOURCE)" \
		RUNPOD_VTON_CONDITION_PERSON_OUTPUT="$(RUNPOD_WEB_GARMENT_CONDITION_PERSON_OUTPUT)" \
		RUNPOD_VTON_CONDITION_GARMENT_OUTPUT="$(RUNPOD_WEB_GARMENT_CONDITION_GARMENT_OUTPUT)" \
		RUNPOD_VTON_CONDITION_REPORT="$(RUNPOD_WEB_GARMENT_CONDITION_REPORT)"
	$(MAKE) runpod-leffa-smoke \
		PERSON_IMAGE="$(RUNPOD_WEB_GARMENT_CONDITION_PERSON_OUTPUT)" \
		GARMENT_IMAGE="$(RUNPOD_WEB_GARMENT_CONDITION_GARMENT_OUTPUT)" \
		RUNPOD_LEFFA_OUTPUT="$(RUNPOD_LEFFA_WEB_GARMENT_OUTPUT)" \
		RUNPOD_LEFFA_REPORT="$(RUNPOD_LEFFA_WEB_GARMENT_REPORT)"

runpod-leffa-web-garment-detail-smoke:
	$(MAKE) runpod-leffa-web-garment-smoke \
		RUNPOD_LEFFA_STEPS="$(RUNPOD_LEFFA_WEB_DETAIL_STEPS)" \
		RUNPOD_LEFFA_GUIDANCE_SCALE="$(RUNPOD_LEFFA_WEB_DETAIL_GUIDANCE_SCALE)" \
		RUNPOD_LEFFA_WEB_GARMENT_OUTPUT="$(RUNPOD_LEFFA_WEB_DETAIL_OUTPUT)" \
		RUNPOD_LEFFA_WEB_GARMENT_REPORT="$(RUNPOD_LEFFA_WEB_DETAIL_REPORT)"

runpod-leffa-upper-body-web-garment-smoke: runpod-leffa-smoke-data
	@test -f "$(RUNPOD_WEB_GARMENT_SOURCE)" || (echo "Missing RUNPOD_WEB_GARMENT_SOURCE=$(RUNPOD_WEB_GARMENT_SOURCE). Use RUNPOD_WEB_GARMENT_ID=2 or 3, or pass RUNPOD_WEB_GARMENT_SOURCE=/path/to/garment.webp"; exit 2)
	$(MAKE) runpod-vton-condition-smoke-inputs \
		PERSON_IMAGE="$(RUNPOD_QWEN_EDIT_PERSON_IMAGE)" \
		GARMENT_IMAGE="$(RUNPOD_WEB_GARMENT_SOURCE)" \
		RUNPOD_VTON_CONDITION_PERSON_FRAMING="upper_body" \
		RUNPOD_VTON_CONDITION_PERSON_OUTPUT="$(RUNPOD_UPPER_BODY_CONDITION_PERSON_OUTPUT)" \
		RUNPOD_VTON_CONDITION_GARMENT_OUTPUT="$(RUNPOD_UPPER_BODY_CONDITION_GARMENT_OUTPUT)" \
		RUNPOD_VTON_CONDITION_REPORT="$(RUNPOD_UPPER_BODY_CONDITION_REPORT)"
	$(MAKE) runpod-leffa-smoke \
		PERSON_IMAGE="$(RUNPOD_UPPER_BODY_CONDITION_PERSON_OUTPUT)" \
		GARMENT_IMAGE="$(RUNPOD_UPPER_BODY_CONDITION_GARMENT_OUTPUT)" \
		RUNPOD_LEFFA_OUTPUT="$(RUNPOD_LEFFA_UPPER_BODY_WEB_GARMENT_OUTPUT)" \
		RUNPOD_LEFFA_REPORT="$(RUNPOD_LEFFA_UPPER_BODY_WEB_GARMENT_REPORT)"

runpod-omnivton-smoke:
	$(eval PERSON_IMAGE_PATH := $(or $(PERSON_IMAGE),$(RUNPOD_OMNIVTON_PERSON_IMAGE)))
	$(eval GARMENT_IMAGE_PATH := $(or $(GARMENT_IMAGE),$(RUNPOD_OMNIVTON_GARMENT_IMAGE)))
	@test -f "$(PERSON_IMAGE_PATH)" || (echo "Missing PERSON_IMAGE=$(PERSON_IMAGE_PATH). Run make runpod-qwen-edit-smoke-data or pass PERSON_IMAGE=/path/to/front.png"; exit 2)
	@test -f "$(GARMENT_IMAGE_PATH)" || (echo "Missing GARMENT_IMAGE=$(GARMENT_IMAGE_PATH). Run make runpod-qwen-edit-smoke-data or pass GARMENT_IMAGE=/path/to/garment.png"; exit 2)
	HF_HOME="$(RUNPOD_HF_HOME)" \
	TRANSFORMERS_CACHE="$(RUNPOD_HF_HOME)/transformers" \
	HUGGINGFACE_HUB_CACHE="$(RUNPOD_HF_HOME)/hub" \
	TORCH_HOME="$(RUNPOD_TORCH_HOME)" \
	XDG_CACHE_HOME="$(RUNPOD_MODEL_DIR)/xdg-cache" \
	PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True" \
	python -m scripts.local_omnivton_smoke \
		--person-image "$(PERSON_IMAGE_PATH)" \
		--garment-image "$(GARMENT_IMAGE_PATH)" \
		--output "$(RUNPOD_OMNIVTON_OUTPUT)" \
		--report "$(RUNPOD_OMNIVTON_REPORT)" \
		--omnivton-root "$(RUNPOD_OMNIVTON_ROOT)" \
		--repo-url "$(RUNPOD_OMNIVTON_REPO_URL)" \
		--stage "$(RUNPOD_OMNIVTON_STAGE)" \
		--model-id "$(RUNPOD_OMNIVTON_MODEL_ID)" \
		--size "$(RUNPOD_OMNIVTON_SIZE)" \
		--device "$(RUNPOD_OMNIVTON_DEVICE)" \
		--steps "$(RUNPOD_OMNIVTON_STEPS)" \
		--guidance-scale "$(RUNPOD_OMNIVTON_GUIDANCE_SCALE)" \
		--seed "$(RUNPOD_OMNIVTON_SEED)" \
		--work-dir "$(RUNPOD_OMNIVTON_WORK_DIR)"

runpod-omnivton-outpainting-smoke: runpod-leffa-smoke-data
	$(MAKE) runpod-vton-condition-smoke-inputs
	$(MAKE) runpod-omnivton-smoke \
		PERSON_IMAGE="$(RUNPOD_VTON_CONDITION_PERSON_OUTPUT)" \
		GARMENT_IMAGE="$(RUNPOD_VTON_CONDITION_GARMENT_OUTPUT)" \
		RUNPOD_OMNIVTON_STAGE="outpainting"

runpod-omnivton-web-garment-smoke: runpod-leffa-smoke-data
	@test -f "$(RUNPOD_WEB_GARMENT_SOURCE)" || (echo "Missing RUNPOD_WEB_GARMENT_SOURCE=$(RUNPOD_WEB_GARMENT_SOURCE). Use RUNPOD_WEB_GARMENT_ID=2 or 3, or pass RUNPOD_WEB_GARMENT_SOURCE=/path/to/garment.webp"; exit 2)
	$(MAKE) runpod-vton-condition-smoke-inputs \
		PERSON_IMAGE="$(RUNPOD_QWEN_EDIT_PERSON_IMAGE)" \
		GARMENT_IMAGE="$(RUNPOD_WEB_GARMENT_SOURCE)" \
		RUNPOD_VTON_CONDITION_PERSON_OUTPUT="$(RUNPOD_WEB_GARMENT_CONDITION_PERSON_OUTPUT)" \
		RUNPOD_VTON_CONDITION_GARMENT_OUTPUT="$(RUNPOD_WEB_GARMENT_CONDITION_GARMENT_OUTPUT)" \
		RUNPOD_VTON_CONDITION_REPORT="$(RUNPOD_WEB_GARMENT_CONDITION_REPORT)"
	$(MAKE) runpod-omnivton-smoke \
		PERSON_IMAGE="$(RUNPOD_WEB_GARMENT_CONDITION_PERSON_OUTPUT)" \
		GARMENT_IMAGE="$(RUNPOD_WEB_GARMENT_CONDITION_GARMENT_OUTPUT)" \
		RUNPOD_OMNIVTON_OUTPUT="$(RUNPOD_OMNIVTON_WEB_GARMENT_OUTPUT)" \
		RUNPOD_OMNIVTON_REPORT="$(RUNPOD_OMNIVTON_WEB_GARMENT_REPORT)" \
		RUNPOD_OMNIVTON_WORK_DIR="$(RUNPOD_OMNIVTON_WEB_GARMENT_WORK_DIR)"

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
