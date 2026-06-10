# RunPod Kiosk Deployment Runbook

This runbook targets the first single-pod MVP deployment on RunPod. The API,
local JSON job queue, worker, Ollama analyzer, and runtime data all run on one
GPU pod.

For the phased deployment strategy, see
[RunPod Deployment Roadmap](runpod-roadmap.md).

## Pod Shape

- Expose HTTP port `8080` for FastAPI Swagger and kiosk API.
- Use a persistent volume mounted at `/workspace`.
- Keep mutable project data under `/workspace/tryon-data`.
- Keep local model/cache assets under `/workspace/tryon-models`.

RunPod HTTP services are exposed through a proxy URL shaped like
`https://<pod-id>-<port>.proxy.runpod.net`. RunPod also documents that updating
environment variables restarts the pod and can clear data outside the volume
mount path, which is why this project stores runtime data under `/workspace`.

## First-Time Setup

Run inside the pod shell:

```bash
cd /workspace
git clone <repo-url> tryon-visual-project
cd /workspace/tryon-visual-project

python3 -m venv venv
source venv/bin/activate
make runpod-install
```

Edit `.env`:

- Set `REPLICATE_API_TOKEN`.
- Set `CORS_ORIGINS` to include `https://<pod-id>-8080.proxy.runpod.net` after
  the pod is created.
- Set `DEBUG=true` for the Phase 1 Swagger smoke test. Set it back to `false`
  before exposing the API beyond controlled testing.
- Keep `TEMP_STORAGE_DIR=/workspace/tryon-data`.
- Keep `JOB_QUEUE_DIR=/workspace/tryon-data/jobs`.
- Keep `INSIGHTFACE_MODEL_DIR=/workspace/tryon-models/insightface`.

## Ollama Setup

The RunPod PyTorch 2.8.0 template does not include Ollama by default. Install
and start Ollama according to the image you selected. Then pull the analyzer
model configured in `.env`:

```bash
ollama serve
ollama pull qwen2.5vl:7b-q4_K_M
ollama list
```

You can also pull the configured default model with:

```bash
make runpod-pull-ollama
```

`GET /api/v1/readiness` and `make kiosk-preflight` both verify that
`OLLAMA_BASE_URL/api/tags` is reachable and that
`TRYON_ANALYZER_OLLAMA_MODEL` is installed. They do not run inference.

## Start Services

For the single-pod MVP, start the API and local worker together:

```bash
cd /workspace/tryon-visual-project
source venv/bin/activate
make runpod-start
```

If Ollama is not already managed by the pod image or another shell, you can let
the supervisor start `ollama serve` when `OLLAMA_BASE_URL` is not reachable:

```bash
make runpod-start-with-ollama
```

For debugging, you can still run the API and worker separately.

Terminal 1:

```bash
cd /workspace/tryon-visual-project
source venv/bin/activate
make run-kiosk
```

Terminal 2:

```bash
cd /workspace/tryon-visual-project
source venv/bin/activate
make worker
```

Preflight:

```bash
cd /workspace/tryon-visual-project
source venv/bin/activate
make runpod-preflight
python -m scripts.kiosk_preflight --json
```

Expected result: `READY`. If it reports `NOT READY`, fix the failed check before
opening Swagger for an end-to-end run.

## Swagger Smoke Test

Open:

```text
https://<pod-id>-8080.proxy.runpod.net/docs
```

Run this sequence:

1. `GET /api/v1/readiness`
2. Optional reset/seed from shell:
   ```bash
   make runpod-reset
   ```
3. `GET /api/v1/kiosk/size-charts?country_code=VN&category=tops`
4. `POST /api/v1/kiosk/garments`
5. `POST /api/v1/kiosk/sessions`
6. `POST /api/v1/kiosk/sessions/{session_id}/captures`
7. `POST /api/v1/kiosk/sessions/{session_id}/captures/analyze`
8. `POST /api/v1/kiosk/sessions/{session_id}/fit/analyze`
9. Optional visual preview:
   - `POST /api/v1/kiosk/sessions/{session_id}/visual-preview/jobs`
   - `GET /api/v1/kiosk/jobs/{job_id}`

## Optional Local Qwen-Edit Smoke

Run this only after the Replicate-backed visual preview path is working. The
goal is to benchmark whether local Qwen image editing is viable on the selected
GPU before adding an API adapter.

This smoke test is intentionally separate from the API and worker. It loads a
local Hugging Face/Diffusers Qwen image-edit pipeline, runs one generation, and
writes a PNG plus a JSON report with latency, model, device, and memory metrics.

Install a current Diffusers stack for Qwen image-edit pipelines:

```bash
cd /workspace/tryon-visual-project
source venv/bin/activate
make runpod-install-qwen-edit-deps
```

This target installs current `diffusers`, `transformers`, `accelerate`,
`safetensors`, and a CUDA 12.8-compatible PyTorch stack:

- `torch==2.8.0`
- `torchvision==0.23.0`
- wheel index: `https://download.pytorch.org/whl/cu128`

Qwen image-edit pipelines require `torchvision` through the Qwen2-VL
video/image processor path. Pinning the PyTorch stack avoids pip pulling a
newer CUDA wheel that requires a newer NVIDIA driver than the RunPod template
provides.

This target does not update the pod's NVIDIA driver or host CUDA driver. That
runtime comes from the RunPod host/template. If PyTorch still cannot initialize
CUDA after this install, change the pod template/GPU host or install a PyTorch
wheel compatible with that host driver.

Before running the smoke test, check cache and storage usage:

```bash
make runpod-disk-report
make runpod-cuda-report
```

On RunPod network volumes, `df -h /workspace` can show the shared backing
filesystem rather than the quota available to the pod/account. If a command
fails with `Disk quota exceeded` while `df` still shows free space, inspect the
`du` output from `make runpod-disk-report`, especially:

- `/workspace/tryon-models`
- `/workspace/tryon-models/huggingface`
- `/root/.cache/huggingface`
- `/root/.cache/torch`
- `/root/.cache/pip`
- `/tmp`

The Qwen image-edit smoke model can require more than `57G` of model files
before runtime overhead. Do not use a `50G` workspace/volume for this smoke
test. Start with at least `120G`, preferably `150G+`, if local Qwen-edit is a
deployment goal.

If the CUDA probe prints a warning such as `NVIDIA driver on your system is too
old`, stop the local Qwen-edit smoke. Change the RunPod template or install a
PyTorch build compatible with the pod's NVIDIA driver before downloading the
model. The smoke script also fails early when `--device cuda` is requested but
PyTorch cannot initialize CUDA.

Expected CUDA-compatible probe after `make runpod-install-qwen-edit-deps`:

- `torch` should include `+cu128`.
- `torchvision` should include `+cu128`.
- `torch cuda build` should be `12.8`.
- `cuda available` should be `True`.

Run one two-image smoke test. Use existing files from the RunPod runtime data,
for example a saved front capture and the uploaded garment image:

```bash
make runpod-qwen-edit-smoke \
  PERSON_IMAGE=/workspace/tryon-data/kiosk_sessions/captures/<front>.png \
  GARMENT_IMAGE=/workspace/tryon-data/garments/images/<garment>.png
```

If you only need to validate local model loading/runtime and do not want to run
the full Swagger flow first, prepare smoke inputs from the checked-in example
fixtures:

```bash
make runpod-qwen-edit-smoke-data
make runpod-qwen-edit-smoke
```

This copies `examples/qwen_edit_smoke/front.png` and
`examples/qwen_edit_smoke/garment.webp` into the RunPod data directory:

- `/workspace/tryon-data/kiosk_sessions/captures/kiosk-session-v1-smoke-front.png`
- `/workspace/tryon-data/garments/images/garment-v1-smoke.webp`
- `/workspace/tryon-data/qwen_edit_smoke/inputs/manifest.json`

If the checked-in examples are missing, the prepare script falls back to
synthetic generated images. These fixtures are only for runtime smoke testing.
Use real kiosk captures and uploaded garments when evaluating try-on quality.

The default target uses:

- model: `Qwen/Qwen-Image-Edit-2509`
- pipeline: `edit-plus`
- size: `512x512`
- input max size: `512`
- device: `cuda`
- device map: `none`
- CPU offload: enabled
- sequential CPU offload: enabled
- steps: `8`
- output: `/workspace/tryon-data/qwen_edit_smoke/qwen-edit-smoke.png`
- report: `/workspace/tryon-data/qwen_edit_smoke/qwen-edit-smoke.json`
- Hugging Face cache: `/workspace/tryon-models/huggingface`
- Torch cache: `/workspace/tryon-models/torch`
- Pip cache: `/workspace/tryon-models/pip-cache`

The default smoke target is intentionally configured as a low-memory canary for
24GB GPUs such as RTX 3090/A5000. It avoids moving the whole Qwen image-edit
pipeline to CUDA at once, resizes input reference images before the vision
encoder, uses sequential CPU offload, and sets
`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` to reduce allocator
fragmentation.

After the low-memory smoke passes, increase settings explicitly:

```bash
make runpod-qwen-edit-smoke \
  RUNPOD_QWEN_EDIT_SIZE=768x768 \
  RUNPOD_QWEN_EDIT_INPUT_MAX_SIZE=768 \
  RUNPOD_QWEN_EDIT_STEPS=12
```

Then try the original quality target:

```bash
make runpod-qwen-edit-smoke \
  RUNPOD_QWEN_EDIT_SIZE=1024x1024 \
  RUNPOD_QWEN_EDIT_INPUT_MAX_SIZE=1024 \
  RUNPOD_QWEN_EDIT_STEPS=20
```

To intentionally test full-GPU residency on a larger GPU, disable offload:

```bash
make runpod-qwen-edit-smoke \
  RUNPOD_QWEN_EDIT_CPU_OFFLOAD=0 \
  RUNPOD_QWEN_EDIT_SEQUENTIAL_CPU_OFFLOAD=0
```

Treat the local Qwen-edit smoke as passed only when:

- the command exits with code `0`,
- the report has `"success": true`,
- the PNG exists and is visually usable,
- the report latency is acceptable for kiosk preview,
- GPU/CPU memory usage leaves enough headroom for the API and worker.

If the command fails, keep the generated failure report. It includes the Python
exception and traceback so the failure can be compared across GPU shapes.

For quota failures, do not build an API adapter yet. Either increase the RunPod
disk/volume quota, move caches to a larger mounted path by overriding
`RUNPOD_MODEL_DIR`, or continue with the Replicate-backed preview baseline.

## Optional Local CatVTON Smoke

Run this after the local Qwen-edit canary or directly after the Replicate path
is stable. CatVTON is the first VTON-specific local candidate because its
person plus garment input shape is close to the kiosk worker contract.

Install the extra dependencies used by the CatVTON smoke script:

```bash
cd /workspace/tryon-visual-project
source venv/bin/activate
make runpod-install-catvton-deps
```

Prepare reusable smoke inputs from the checked-in fixtures:

```bash
make runpod-qwen-edit-smoke-data
```

Run the default CatVTON smoke:

```bash
make runpod-catvton-smoke
```

The default target uses:

- CatVTON repo: `/workspace/tryon-models/external/CatVTON`
- base model: `runwayml/stable-diffusion-inpainting`
- checkpoint: `zhengchong/CatVTON`
- size: `768x1024`
- precision: `bf16`
- cloth type: `upper`
- mask mode: `auto`
- steps: `30`
- guidance scale: `2.5`
- output: `/workspace/tryon-data/catvton_smoke/catvton-smoke.png`
- report: `/workspace/tryon-data/catvton_smoke/catvton-smoke.json`

`MASK_MODE=auto` uses CatVTON's DensePose/SCHP AutoMasker. This is the real
quality path, but it downloads and loads additional preprocessing checkpoints.
If that blocks the first runtime smoke, validate only the CatVTON pipeline with
a rough synthetic mask:

```bash
make runpod-catvton-smoke RUNPOD_CATVTON_MASK_MODE=rough
```

Use real kiosk captures and uploaded garments when evaluating quality:

```bash
make runpod-catvton-smoke \
  PERSON_IMAGE=/workspace/tryon-data/kiosk_sessions/captures/<front>.png \
  GARMENT_IMAGE=/workspace/tryon-data/garments/images/<garment>.png
```

Treat the CatVTON smoke as passed only when:

- the command exits with code `0`,
- the report has `"success": true`,
- the PNG exists and is visually usable,
- latency is acceptable for kiosk preview,
- the report memory metrics leave enough headroom for the API, worker, and
  analyzer.

Do not build the production `LocalCatVtonEngine` adapter from a rough-mask
result alone. The adapter should wait until the auto-mask quality path is
working or until we design a production mask generator.

## Operational Notes

- For the current MVP, keep `JOB_QUEUE_BACKEND=local`; Redis/Kafka can be added
  later behind the same queue interface.
- Stop `make run-kiosk-all` or the standalone worker before resetting runtime
  files.
- Use `make kiosk-preflight` after any `.env`, model, or volume path change.
- If the HTTP proxy returns connection refused, verify `make run-kiosk` is still
  running and listening on `0.0.0.0:8080`, or that `make run-kiosk-all` is still
  alive.
