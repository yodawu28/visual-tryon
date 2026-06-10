# RunPod Deployment Roadmap

This roadmap splits RunPod deployment into three practical phases. The goal is
to validate the kiosk workflow with the lowest useful cost first, then scale up
only when image generation and full GPU features are ready to benchmark.

## Phase 1: Minimum Smoke Test

Status: passed on June 8, 2026 with a RunPod PyTorch 2.8.0 template on an
A5000-class pod. Ollama was installed manually, Swagger required `DEBUG=true`,
and the kiosk flow worked through the RunPod `8080` HTTP proxy.

### Goal

Validate that the application can run on RunPod and that the Swagger-driven
kiosk workflow works without depending on local image generation.

### Recommended Pod

- GPU: RTX A5000 24 GB VRAM, or the cheapest available GPU that can run the
  configured Ollama/Qwen2.5VL analyzer.
- RAM: 25 GB or more.
- vCPU: 6 or more.
- Storage: local pod storage is acceptable for this phase.
- Exposed HTTP port: `8080`.

Persistent or network volume is optional. Runtime data can be recreated for this
phase.

### Feature Scope

Run and verify:

- FastAPI kiosk API.
- Swagger UI.
- Health/readiness endpoint.
- Garment upload.
- Kiosk session creation.
- Front/side capture upload.
- MediaPipe capture analysis.
- Fit Intelligence analysis.
- Size chart lookup and size recommendation.
- Optional Replicate-backed visual preview if `REPLICATE_API_TOKEN` is present.

Do not optimize local image generation in this phase.

### Setup Steps

1. Create a RunPod Pod.
2. Expose HTTP port `8080`.
3. Clone the repository:

   ```bash
   cd /workspace
   git clone <repo-url> tryon-visual-project
   cd /workspace/tryon-visual-project
   ```

4. Create and activate a virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   make runpod-install
   ```

   This installs Python dependencies, creates `.env` from
   `.env.runpod.example` when missing, and creates the default RunPod runtime
   directories.

5. Review `.env`:

   - Set `REPLICATE_API_TOKEN` if visual preview will be tested.
   - Set `CORS_ORIGINS` to include the RunPod proxy URL.
   - Keep `API_PROFILE=kiosk`.
   - Keep `TEMP_STORAGE_DIR=/workspace/tryon-data`.
   - Keep `JOB_QUEUE_DIR=/workspace/tryon-data/jobs`.
   - Keep `TRYON_ANALYZER_OLLAMA_MODEL=qwen2.5vl:7b-q4_K_M`.

6. Start Ollama in one shell:

   ```bash
   ollama serve
   ```

7. Pull the analyzer model from another shell:

   ```bash
   cd /workspace/tryon-visual-project
   source venv/bin/activate
   make runpod-pull-ollama
   ```

8. Start the app:

   ```bash
   cd /workspace/tryon-visual-project
   source venv/bin/activate
   make runpod-start
   ```

9. Run preflight from another shell:

   ```bash
   cd /workspace/tryon-visual-project
   source venv/bin/activate
   make runpod-preflight
   python -m scripts.kiosk_preflight --json
   ```

Alternative: if Ollama should be started by the app supervisor instead of a
separate shell, use:

```bash
make runpod-start-with-ollama
```

### Swagger Test Sequence

Open:

```text
https://<pod-id>-8080.proxy.runpod.net/docs
```

Run:

1. `GET /api/v1/readiness`
2. Optional reset from shell:

   ```bash
   make runpod-reset
   ```

3. `GET /api/v1/kiosk/size-charts?country_code=VN&category=tops`
4. `POST /api/v1/kiosk/garments`
5. `POST /api/v1/kiosk/sessions`
6. `POST /api/v1/kiosk/sessions/{session_id}/captures`
7. `POST /api/v1/kiosk/sessions/{session_id}/captures/analyze`
8. `POST /api/v1/kiosk/sessions/{session_id}/fit/analyze`
9. Optional:
   - `POST /api/v1/kiosk/sessions/{session_id}/visual-preview/jobs`
   - `GET /api/v1/kiosk/jobs/{job_id}`

### Exit Criteria

- `make kiosk-preflight` returns ready.
- Swagger loads through the RunPod proxy URL.
- Garment upload and session creation work.
- Capture upload and capture analysis pass.
- Fit Intelligence returns a recommendation.
- No manual terminal-only data patching is required during the workflow.

## Phase 2: Full Feature GPU Test

Status: partially passed on June 9, 2026. The Replicate-backed async visual
preview path completed successfully on RunPod with the local JSON worker queue.
Local Qwen-edit generation remains deferred.

### Goal

Benchmark full visual preview behavior and decide whether the project should
continue using Replicate for image generation or move generation onto the GPU
Pod.

### Recommended Pod

Start with:

- GPU: RTX 4090 24 GB VRAM.
- RAM: 41 GB or more.
- vCPU: 6 or more.
- Storage: 50-100 GB is enough for Replicate-backed testing. Use at least
  120 GB, preferably 150 GB or more, before testing local Qwen-edit model
  downloads.

If local image generation hits VRAM limits or has unacceptable latency, retest
with a 48 GB class GPU such as L40, L40S, A40, A6000, or similar.

### Feature Scope

Run and verify everything from Phase 1, plus:

- Visual preview job queue.
- Worker stability under repeated jobs.
- Replicate image generation latency and quality.
- Local Qwen-edit smoke script before any API adapter is implemented.
- Optional local image generation adapter only after smoke passes.
- Qwen multimodal analyzer quality.
- Memory usage during analyzer and generation workloads.

### Setup Steps

1. Create a new RunPod Pod with the stronger GPU.
2. Repeat the Phase 1 setup.
3. Pull Ollama model again unless model cache is preserved:

   ```bash
   ollama pull qwen2.5vl:7b-q4_K_M
   ```

4. Start services:

   ```bash
   make run-kiosk-all
   ```

5. Run preflight:

   ```bash
   make kiosk-preflight
   ```

6. Run the full Swagger flow, including visual preview jobs.
7. If the Replicate path is stable, run the isolated local Qwen-edit smoke:

   ```bash
   make runpod-install-qwen-edit-deps
   make runpod-cuda-report
   make runpod-qwen-edit-smoke-data
   make runpod-qwen-edit-smoke
   ```

   Or run against real kiosk outputs:

   ```bash
   make runpod-qwen-edit-smoke \
     PERSON_IMAGE=/workspace/tryon-data/kiosk_sessions/captures/<front>.png \
     GARMENT_IMAGE=/workspace/tryon-data/garments/images/<garment>.png
   ```

8. Build a local image generation adapter only if the smoke report proves that
   local generation can meet quality, latency, and memory constraints.
9. If the local smoke fails with disk quota, storage, or cache errors, keep the
   Replicate-backed preview path as the MVP baseline and revisit local
   generation after increasing RunPod storage/quota.

### Benchmark Notes

Track:

- Readiness startup time.
- Capture analysis latency.
- Fit Intelligence latency.
- Visual preview queue wait time.
- Visual preview generation latency.
- GPU memory usage.
- Output quality.
- Failure modes and retry behavior.

Current baseline:

- Replicate visual preview job completed successfully with
  `qwen/qwen-image-edit-2511`.
- Worker persisted generated image and metadata artifacts under
  `/workspace/tryon-data/kiosk_tryons`.
- The successful job reached `personalized_tryon_ready` and returned no
  warnings.
- Cached result generation time was about `9.22s`.
- Local Qwen-edit is now treated as a separate smoke benchmark, not an API
  dependency.

### Exit Criteria

- Visual preview jobs complete reliably.
- Worker can process multiple jobs without manual restart.
- Latency is acceptable for demo use.
- A clear decision exists:
  - keep Replicate for generation,
  - implement local GPU generation,
  - or use a hybrid fallback.

## Phase 3: Production Readiness Review

### Goal

Turn the validated MVP into a deployable application architecture.

### Review Areas

- Packaging:
  - Keep manual Pod setup for now.
  - Add Docker later if deployment repetition becomes painful.
- Runtime topology:
  - All-in-one Pod for MVP.
  - Split CPU API and GPU worker when traffic or cost requires it.
- Queue backend:
  - Keep local JSON queue for single-node MVP.
  - Add Redis or Kafka behind the existing queue interface when multi-node
    workers are needed.
- Storage:
  - Local `data/` for MVP.
  - S3-compatible storage for production assets and generated images.
- Database:
  - SQLite for MVP.
  - Postgres or managed database when multiple API instances are required.
- Security:
  - Do not commit `.env`.
  - Add API auth before public deployment.
  - Restrict CORS to known domains.
- Observability:
  - Structured logs.
  - Request/job IDs.
  - Worker job metrics.
  - Error dashboards.
- Cost:
  - Compare A5000, 4090, and 48 GB GPU classes.
  - Decide whether generation should stay remote or move local.
- Product completeness:
  - Clean Swagger workflow.
  - Stable reset/seed path for demos.
  - Clear fit recommendation explanation.
  - Optional visual preview only when the user asks for it.

### Exit Criteria

- Deployment steps are repeatable by a second developer.
- Swagger E2E can be run from a fresh Pod.
- Runtime data reset is safe and documented.
- GPU and cost choice is backed by measured latency and quality.
- Known limitations are documented before sharing the app externally.

## Current Recommendation

Start with Phase 1 on the lower-cost A5000-class Pod. Do not spend effort on
local image generation until the API, Ollama analyzer, Swagger flow, and Fit
Intelligence are proven to run cleanly on RunPod.
