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
`safetensors`, and `torchvision`. Qwen image-edit pipelines require
`torchvision` through the Qwen2-VL video/image processor path.

Before running the smoke test, check cache and storage usage:

```bash
make runpod-disk-report
python - <<'PY'
import torch
import torchvision
print("torch", torch.__version__)
print("torchvision", torchvision.__version__)
print("torch cuda build", torch.version.cuda)
print("cuda available", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu", torch.cuda.get_device_name(0))
PY
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

Run one two-image smoke test. Use existing files from the RunPod runtime data,
for example a saved front capture and the uploaded garment image:

```bash
make runpod-qwen-edit-smoke \
  PERSON_IMAGE=/workspace/tryon-data/kiosk_sessions/captures/<front>.png \
  GARMENT_IMAGE=/workspace/tryon-data/garments/images/<garment>.png
```

The default target uses:

- model: `Qwen/Qwen-Image-Edit-2509`
- pipeline: `edit-plus`
- device: `cuda`
- device map: `none`
- steps: `20`
- output: `/workspace/tryon-data/qwen_edit_smoke/qwen-edit-smoke.png`
- report: `/workspace/tryon-data/qwen_edit_smoke/qwen-edit-smoke.json`
- Hugging Face cache: `/workspace/tryon-models/huggingface`
- Torch cache: `/workspace/tryon-models/torch`
- Pip cache: `/workspace/tryon-models/pip-cache`

If the model does not fit in VRAM, try an offload/device-map experiment directly
with the script:

```bash
python -m scripts.local_qwen_edit_smoke \
  --person-image /workspace/tryon-data/kiosk_sessions/captures/<front>.png \
  --garment-image /workspace/tryon-data/garments/images/<garment>.png \
  --output /workspace/tryon-data/qwen_edit_smoke/qwen-edit-smoke.png \
  --report /workspace/tryon-data/qwen_edit_smoke/qwen-edit-smoke.json \
  --model-id Qwen/Qwen-Image-Edit-2509 \
  --pipeline edit-plus \
  --device cuda \
  --device-map auto \
  --cpu-offload \
  --steps 20
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

## Operational Notes

- For the current MVP, keep `JOB_QUEUE_BACKEND=local`; Redis/Kafka can be added
  later behind the same queue interface.
- Stop `make run-kiosk-all` or the standalone worker before resetting runtime
  files.
- Use `make kiosk-preflight` after any `.env`, model, or volume path change.
- If the HTTP proxy returns connection refused, verify `make run-kiosk` is still
  running and listening on `0.0.0.0:8080`, or that `make run-kiosk-all` is still
  alive.
