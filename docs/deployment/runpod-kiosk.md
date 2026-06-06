# RunPod Kiosk Deployment Runbook

This runbook targets the first single-pod MVP deployment on RunPod. The API,
local JSON job queue, worker, Ollama analyzer, and runtime data all run on one
GPU pod.

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
make install

cp .env.runpod.example .env
```

Edit `.env`:

- Set `REPLICATE_API_TOKEN`.
- Set `CORS_ORIGINS` to include `https://<pod-id>-8080.proxy.runpod.net` after
  the pod is created.
- Keep `TEMP_STORAGE_DIR=/workspace/tryon-data`.
- Keep `JOB_QUEUE_DIR=/workspace/tryon-data/jobs`.
- Keep `INSIGHTFACE_MODEL_DIR=/workspace/tryon-models/insightface`.

## Ollama Setup

Install/start Ollama according to the image you selected. Then pull the analyzer
model configured in `.env`:

```bash
ollama serve
ollama pull qwen2.5vl:7b-q4_K_M
ollama list
```

`GET /api/v1/readiness` and `make kiosk-preflight` both verify that
`OLLAMA_BASE_URL/api/tags` is reachable and that
`TRYON_ANALYZER_OLLAMA_MODEL` is installed. They do not run inference.

## Start Services

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
make kiosk-preflight
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
   python -m scripts.reset_kiosk_state \
     --execute \
     --include-runtime-files \
     --seed-default-size-charts
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

## Operational Notes

- For the current MVP, keep `JOB_QUEUE_BACKEND=local`; Redis/Kafka can be added
  later behind the same queue interface.
- Stop the worker before resetting runtime files.
- Use `make kiosk-preflight` after any `.env`, model, or volume path change.
- If the HTTP proxy returns connection refused, verify `make run-kiosk` is still
  running and listening on `0.0.0.0:8080`.
