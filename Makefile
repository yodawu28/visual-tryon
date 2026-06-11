RUNPOD_DATA_DIR ?= /workspace/tryon-data
RUNPOD_MODEL_DIR ?= /workspace/tryon-models
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
RUNPOD_VTON_CONDITION_PERSON_CLEAN_BACKGROUND ?= 1
RUNPOD_VTON_CONDITION_GARMENT_CANVAS_SIZE ?= 1024
RUNPOD_VTON_CONDITION_GARMENT_BORDER_RATIO ?= 0.08
RUNPOD_VTON_CONDITION_BACKGROUND ?= 250,250,250
RUNPOD_VTON_CONDITION_FOREGROUND_THRESHOLD ?= 28
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
RUNPOD_HF_HOME ?= $(RUNPOD_MODEL_DIR)/huggingface
RUNPOD_TORCH_HOME ?= $(RUNPOD_MODEL_DIR)/torch
RUNPOD_PIP_CACHE_DIR ?= $(RUNPOD_MODEL_DIR)/pip-cache
RUNPOD_TORCH_VERSION ?= 2.8.0
RUNPOD_TORCHVISION_VERSION ?= 0.23.0
RUNPOD_TORCH_CUDA_INDEX ?= https://download.pytorch.org/whl/cu128

.PHONY: help setup install run run-kiosk run-kiosk-all worker worker-once kiosk-preflight runpod-help runpod-init runpod-install runpod-install-qwen-edit-deps runpod-install-catvton-deps runpod-install-leffa-deps runpod-catvton-import-check runpod-leffa-import-check runpod-pull-ollama runpod-reset runpod-start runpod-start-with-ollama runpod-preflight runpod-disk-report runpod-cuda-report runpod-qwen-edit-smoke-data runpod-vton-smoke-data runpod-vton-condition-smoke-inputs runpod-leffa-smoke-data runpod-qwen-edit-smoke runpod-catvton-smoke runpod-catvton-quality-smoke runpod-leffa-smoke runpod-leffa-conditioned-smoke test clean lint format check

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
	@echo "  make runpod-vton-smoke-data - Alias for shared Qwen/CatVTON/Leffa smoke inputs"
	@echo "  make runpod-vton-condition-smoke-inputs - Normalize person/garment images for VTON smoke A/B"
	@echo "  make runpod-leffa-smoke-data - Alias for shared Qwen/CatVTON/Leffa smoke inputs"
	@echo "  make runpod-qwen-edit-smoke - Run local Qwen-edit smoke with prepared/default inputs"
	@echo "  make runpod-install-catvton-deps - Install extra deps for local CatVTON smoke"
	@echo "  make runpod-catvton-import-check - Validate CatVTON imports without loading models"
	@echo "  make runpod-catvton-smoke - Run cheap local CatVTON canary with prepared/default inputs"
	@echo "  make runpod-catvton-quality-smoke - Run full CatVTON quality smoke after canary passes"
	@echo "  make runpod-install-leffa-deps - Install extra deps for local Leffa smoke"
	@echo "  make runpod-leffa-import-check - Validate Leffa imports without loading models"
	@echo "  make runpod-leffa-smoke - Run local Leffa smoke with prepared/default inputs"
	@echo "  make runpod-leffa-conditioned-smoke - Run Leffa with normalized smoke inputs"
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
	@echo "  make runpod-leffa-import-check"
	@echo "  make runpod-leffa-smoke-data"
	@echo "  make runpod-vton-condition-smoke-inputs"
	@echo "  make runpod-leffa-smoke"
	@echo "  make runpod-leffa-conditioned-smoke"

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
		"opencv-python-headless>=4.10.0.84" \
		"scikit-image>=0.24.0" \
		"matplotlib>=3.9.1" \
		"ninja>=1.11.1"

runpod-install-leffa-deps:
	PIP_CACHE_DIR="$(RUNPOD_PIP_CACHE_DIR)" pip install -U \
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
		"numpy>=1.26.4" \
		"omegaconf>=2.3.0" \
		"onnxruntime>=1.18.0" \
		"opencv-python-headless>=4.10.0.84" \
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
		"yacs>=0.1.8"

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
	python -m scripts.local_leffa_smoke \
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
		$(if $(filter 1 true yes,$(RUNPOD_VTON_CONDITION_PERSON_CLEAN_BACKGROUND)),--person-clean-background,--no-person-clean-background) \
		--garment-canvas-size "$(RUNPOD_VTON_CONDITION_GARMENT_CANVAS_SIZE)" \
		--garment-border-ratio "$(RUNPOD_VTON_CONDITION_GARMENT_BORDER_RATIO)" \
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
	python -m scripts.local_leffa_smoke \
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
