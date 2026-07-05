# Local Visual Engine Service Design

## Context

The RunPod kiosk flow currently executes local Leffa visual try-on through
`LocalLeffaKioskGenerator`, which prepares inputs and then starts
`python -m scripts.local_leffa_smoke` as a subprocess for every visual preview
job. Checkpoint preload removes the first Hugging Face download from the user
path, but every job still pays Python process startup and Leffa model loading.

The next step is a persistent local model service. It should keep the expensive
model state warm across jobs while preserving the current API, job queue, input
quality, conditioning, and diagnostic artifact behavior.

This service must be designed as a local visual engine boundary, not as a
Leffa-only dead end. Leffa is the first engine implementation, but future
engines such as OmniVTON, CatVTON, or another in-house model should be able to
reuse the same worker-to-service contract.

## Goals

- Load the active local visual try-on model once per service process.
- Reuse the loaded model across multiple kiosk visual preview jobs.
- Keep the Leffa dependency stack isolated in `LOCAL_LEFFA_PYTHON`.
- Preserve current worker behavior: input quality report, conditioned inputs,
  Leffa report, generated output, and metadata returned to the UI.
- Keep the phase-1 service single-model and single-request-at-a-time to reduce
  VRAM/OOM risk on one-GPU RunPod pods.
- Make the service boundary generic enough for future non-Leffa engines.
- Keep the existing subprocess path as a fallback while the service path is
  being validated.

## Non-Goals

- Do not introduce distributed queue infrastructure.
- Do not support multiple concurrent GPU generations in the first version.
- Do not run the model inside the FastAPI API process.
- Do not remove the existing Leffa smoke script or subprocess debug path.
- Do not redesign the kiosk UI job polling flow.

## Recommended Approach

Add a local-only HTTP service process called the local visual engine service.
The supervisor starts it beside the API and worker. The service listens on
`127.0.0.1` only, loads the selected engine at startup, exposes health/readiness
endpoints, and accepts generation requests from the worker.

The first engine implementation is `leffa`. The service module can be named
generically, for example `scripts.run_local_visual_engine_service`, while the
engine implementation can live in a Leffa-specific module. This avoids baking
Leffa into the worker-service protocol.

## Components

### Local Visual Engine Service

Responsibilities:

- Read engine configuration from environment variables.
- Validate checkpoint assets before model load.
- Load one engine instance at process startup.
- Expose local endpoints:
  - `GET /health`: process is alive.
  - `GET /ready`: active engine is loaded and ready.
  - `POST /v1/generate`: run one generation request.
- Serialize generation with a process-local lock.
- Write output, mask, densepose, and report files to paths provided by the
  worker.
- Return JSON metadata compatible with the current worker metadata shape.

The service must bind to `127.0.0.1` by default. It is an internal process, not
a public RunPod port.

### Engine Interface

The service should depend on a small engine interface rather than calling Leffa
directly from endpoint code.

Required behavior:

- `load() -> EngineMetadata`
- `is_ready() -> bool`
- `generate(request: GenerateRequest) -> GenerateResult`
- `metadata() -> EngineMetadata`

The Leffa engine implements this interface by reusing the logic currently inside
`scripts.local_leffa_smoke`: repo validation, module imports, checkpoint
validation, preprocessing module setup, model construction, transform, and
inference. The load path should create and retain DensePose, Parsing, OpenPose,
LeffaModel, LeffaInference, and LeffaTransform instances.

Future engines can implement the same interface with different checkpoint paths,
input constraints, or output artifacts.

### Worker Adapter

`LocalLeffaKioskGenerator` should keep doing the current kiosk-specific work:

- category normalization,
- input quality scoring,
- person/garment conditioning,
- work directory layout,
- diagnostic JSON writing,
- final base64 response.

Only the model execution step changes. When service mode is enabled, the adapter
sends a local HTTP request instead of spawning `scripts.local_leffa_smoke`.

The worker adapter can remain Leffa-named in phase 1 because its category
mapping is Leffa-specific. The service protocol itself should still be generic.
A later refactor can introduce `LocalVisualEngineKioskGenerator` if another
engine becomes production-worthy.

### Supervisor

`scripts.run_kiosk_all` should be able to start the local visual engine service
as a managed child process before the worker. The worker should not require a
public port to talk to it.

The supervisor should support:

- `LOCAL_VISUAL_ENGINE_START_SERVICE=true` to enable service startup.
- `LOCAL_VISUAL_ENGINE_SERVICE_HOST=127.0.0.1`
- `LOCAL_VISUAL_ENGINE_SERVICE_PORT=8091`
- existing RunPod `runpod-start` behavior when the service is disabled.

## Configuration

Add generic service configuration:

- `LOCAL_VISUAL_ENGINE_MODE=subprocess|service`
- `LOCAL_VISUAL_ENGINE_SERVICE_URL=http://127.0.0.1:8091`
- `LOCAL_VISUAL_ENGINE_START_SERVICE=false`
- `LOCAL_VISUAL_ENGINE_SERVICE_HOST=127.0.0.1`
- `LOCAL_VISUAL_ENGINE_SERVICE_PORT=8091`
- `LOCAL_VISUAL_ENGINE_SERVICE_READY_TIMEOUT=900`
- `LOCAL_VISUAL_ENGINE_SERVICE_REQUEST_TIMEOUT`, defaulting to
  `LOCAL_LEFFA_TIMEOUT` in phase 1
- `LOCAL_VISUAL_ENGINE_ENGINE=leffa`

Keep existing Leffa settings for the Leffa engine:

- `LOCAL_LEFFA_ROOT`
- `LOCAL_LEFFA_REPO_URL`
- `LOCAL_LEFFA_MODEL_REPO_ID`
- `LOCAL_LEFFA_CHECKPOINT_DIR`
- `LOCAL_LEFFA_HF_HOME`
- `LOCAL_LEFFA_TORCH_HOME`
- `LOCAL_LEFFA_XDG_CACHE_HOME`
- `LOCAL_LEFFA_PYTHON`
- `LOCAL_LEFFA_NO_CLONE`
- `LOCAL_LEFFA_SIZE`
- `LOCAL_LEFFA_DEVICE`
- `LOCAL_LEFFA_DTYPE`
- `LOCAL_LEFFA_VT_MODEL_TYPE`
- `LOCAL_LEFFA_STEPS`
- `LOCAL_LEFFA_GUIDANCE_SCALE`
- `LOCAL_LEFFA_SEED`
- `LOCAL_LEFFA_TIMEOUT`

In phase 1, default `LOCAL_VISUAL_ENGINE_MODE` should remain `subprocess` for
local safety. RunPod docs can opt in with `LOCAL_VISUAL_ENGINE_MODE=service` and
`LOCAL_VISUAL_ENGINE_START_SERVICE=true`.

## Request Contract

`POST /v1/generate` accepts JSON with file paths, not image bytes. The worker and
service run on the same pod and share `/workspace/tryon-data`, so passing paths
avoids large JSON payloads.

Required fields:

- `engine`: `leffa`
- `person_image`: conditioned person image path
- `garment_image`: conditioned garment image path
- `output`: generated output image path
- `report`: engine report JSON path
- `garment_type`: engine garment type, for Leffa this is `upper_body`,
  `lower_body`, or `dresses`
- `size`
- `steps`
- `guidance_scale`
- `seed`
- `ref_acceleration`
- `repaint`
- `preprocess_garment`

The service should reject requests for a different engine than the loaded one.

## Response Contract

Successful response:

- `success: true`
- `engine`
- `engine_metadata`, including model repo, checkpoint directory, model type,
  device, dtype, and engine implementation
- `output`
- `report`
- optional artifact paths such as `mask_output` and `densepose_output`
- `queue_wait_seconds`
- `generation_time_seconds`
- `total_time_seconds`

Failed response:

- non-2xx status code
- `success: false`
- `error.type`
- `error.message`
- optional `error.traceback` in local/debug mode only

The worker should turn failed responses into the same `RuntimeError` style it
uses today so job retries and UI status do not need a separate behavior path.

## Data Flow

1. API queues a visual preview job exactly as today.
2. Worker leases the job.
3. `LocalLeffaKioskGenerator` writes source person/garment files.
4. The adapter runs input quality scoring and conditioning exactly as today.
5. In service mode, the adapter sends paths and generation options to
   `LOCAL_VISUAL_ENGINE_SERVICE_URL`.
6. Service serializes the request with a lock.
7. Leffa engine uses the already loaded model objects to generate the image.
8. Service writes output artifacts and report.
9. Worker reads the output image and returns the existing metadata shape.
10. UI polling receives the completed job as it does today.

## Error Handling

- If the service is unreachable, the worker should retry readiness briefly, then
  fail the job with a clear local visual engine service error.
- If `/ready` is false, the worker should fail fast once the configured ready
  timeout expires.
- If the engine request times out, the worker should mark the job attempt failed
  and include service URL, work dir, and report path in the error.
- If the service process crashes, `run_kiosk_all` should terminate the whole
  supervised process group in phase 1. Auto-restart can be added later, but
  silently restarting a GPU model process during a job can hide OOM failures.
- The service must write a failed report when generation starts but raises.

## Concurrency

Phase 1 uses one service process, one loaded engine, and one generation lock.
Requests arriving while a generation is active should wait in-process until the
worker HTTP timeout. This matches the current single local job worker behavior
and avoids accidental concurrent GPU allocations.

Later expansion can add:

- multiple service workers on separate GPUs,
- a lightweight local router,
- per-engine queues,
- model-specific concurrency limits.

The phase-1 protocol should not assume Leffa-only fields outside the
engine-specific request options.

## Observability

The service should log:

- engine selected,
- checkpoint directory,
- model load start/end and duration,
- ready state,
- every request start/end,
- queue wait duration,
- generation duration,
- output/report paths,
- errors with traceback.

The worker metadata should include whether execution used `subprocess` or
`service`, the service URL, and service timing fields.

## Testing

Unit tests:

- service config parses defaults and environment overrides,
- service rejects unsupported engine names,
- service readiness reports false before load and true after fake engine load,
- generation endpoint serializes calls through a lock with a fake engine,
- worker adapter calls service mode instead of subprocess when configured,
- worker adapter preserves current metadata fields.

Makefile/supervisor tests:

- dry-run or command-builder tests include local visual engine service process
  only when enabled.
- RunPod help/docs mention the service mode opt-in.

Manual RunPod validation:

1. `make runpod-install-leffa-deps`
2. `make runpod-leffa-preload`
3. set `LOCAL_VISUAL_ENGINE_MODE=service`
4. set `LOCAL_VISUAL_ENGINE_START_SERVICE=true`
5. `make runpod-start`
6. wait for service ready log
7. submit two visual preview jobs and compare first/second job timings

Pass criteria:

- first job after service readiness does not reload Leffa model,
- second job avoids Python subprocess/model load cost,
- existing UI polling and diagnostic artifacts still work,
- no public RunPod port is required for the service.

## Migration Plan

Phase 1:

- Add generic service config.
- Add generic local visual engine service with fake-engine-testable interface.
- Implement Leffa engine using persistent loaded objects.
- Add service-mode branch in `LocalLeffaKioskGenerator`.
- Extend `run_kiosk_all` to start the service when enabled.
- Add docs and focused tests.

Phase 2:

- Add richer readiness checks and timing metadata in the UI/job output.
- Add service crash diagnostics.
- Evaluate whether service mode should become the RunPod default.

Future:

- Add a second engine behind the same service contract.
- Rename or wrap `LocalLeffaKioskGenerator` into a generic
  `LocalVisualEngineKioskGenerator` only after a second engine needs the same
  kiosk adapter path.
