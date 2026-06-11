# Development Journal

This journal records product and architecture decisions that affect the long-running try-on project. Keep entries short, dated, and tied to implementation outcomes.

## 2026-06-02: Kiosk Flow, Multimodal Analysis, and Engine Boundaries

### Context

We validated that avatar-based multimodal previews are useful for garment browsing: users can preview a garment on a synthetic avatar before deciding whether to capture themselves for a personalized try-on. For kiosk deployment, the flow now needs to support a physical camera setup and a GPU server package.

The target kiosk flow is:

1. Staff or system uploads/registers a garment.
2. User optionally previews the garment on an avatar.
3. User captures front and optional side photos from the kiosk webcam.
4. System analyzes capture quality and pose before generation.
5. System generates a personalized visual try-on only after capture analysis passes.
6. Fit and size recommendation are handled separately from visual generation.

### Decisions

- Keep avatar preview optional in kiosk sessions. It is valuable for garment exploration, but it is not required for direct user try-on.
- Use MediaPipe-based capture analysis as the gate before personalized try-on. The first pass checks image quality, full-body visibility, front-facing pose, and whether arms block the torso.
- Apply multimodal analysis to kiosk personalized try-on. The analyzer reads the user capture and garment image, produces garment intent, and then the visual generation prompt is built from that intent.
- Separate the product into two engines:
  - Visual Try-On Engine: generates preview images from user/avatar image plus garment image.
  - Fit Intelligence Engine: estimates body measurements, maps product size charts, predicts fit, and recommends size.
- Do not use visual try-on output as size truth. Qwen-style image editing can produce strong previews, but it should not be trusted for measurement or size recommendation.
- Store garment assets through a registry with local file paths first. This keeps the path open for future S3 or object storage without changing the API contract.

### Implemented

- Added kiosk garment registry APIs:
  - `POST /api/v1/kiosk/garments`
  - `GET /api/v1/kiosk/garments`
  - `GET /api/v1/kiosk/garments/{garment_id}`
- Updated kiosk capture upload to `multipart/form-data` for front and optional side images.
- Added personalized kiosk try-on API:
  - `POST /api/v1/kiosk/sessions/{session_id}/try-on`
- Added `KioskVisualTryOnService` for visual generation and cache management.
- Personalized try-on now requires:
  - existing session
  - registered garment
  - front capture
  - passed capture analysis
- Generated kiosk try-on results are cached with metadata under `data/kiosk_tryons`.
- Session status is updated to `personalized_tryon_ready` after a successful visual try-on.

### Notes

- Current visual generation uses the configured Replicate preview generator path and Qwen-style image editing behavior.
- Current multimodal analyzer uses the configured Ollama model where available. If analysis fails, the visual engine falls back to a deterministic prompt and records a warning.
- Future Fit Intelligence work should introduce its own module and API rather than expanding the visual try-on endpoint.

### Next

- Add Fit Intelligence data contracts: body measurement estimate, garment size chart, fit prediction, and recommended size.
- Add kiosk deployment notes for a single CPU + GPU server, monitor, and webcam package.
- Add manual eval cases comparing avatar preview, personalized visual try-on, and eventual fit recommendation accuracy.

## 2026-06-03: Fit Intelligence API Skeleton

### Context

The kiosk visual try-on flow now works end to end. The next product layer is Fit Intelligence: estimate body measurements, compare them with garment size charts, predict fit, and recommend a size. This should learn from commercial fit-product patterns without pretending that visual try-on output is enough for accurate sizing.

### Decisions

- Add a Fit Intelligence API contract now, before choosing the measurement model.
- Keep Fit Intelligence separate from Visual Try-On Engine.
- Require passed kiosk capture analysis before fit analysis.
- Accept optional garment size chart rows in the request, but do not score sizes until body measurement estimation exists.
- Persist fit metadata and attach `fit_analysis_key` to the kiosk session.
- Return explicit skeleton warnings so clients do not present placeholder output as a real recommendation.

### Implemented

- Added `POST /api/v1/kiosk/sessions/{session_id}/fit/analyze`.
- Added `KioskFitIntelligenceService` with deterministic metadata caching under `data/kiosk_fit`.
- Added `KioskFitAnalysisRequest` with `preferred_fit` and optional `size_chart`.
- Added `KioskFitAnalysisResponse` with:
  - `measurement_estimate`
  - `fit_assessment`
  - `size_recommendation`
  - `confidence_score`
  - `warnings`
- Added session state `fit_analysis_key` and status `fit_analysis_ready`.

### Current Limitation

This is not a production fit model. It intentionally returns `pending_measurement_model` and `insufficient_measurements` until we add a real body measurement model and size recommendation algorithm.

### Next

- Define body measurement schema and units.
- Define garment size chart normalization rules per category.
- Prototype measurement estimation from front and side captures.
- Add a size recommender that can score provided size-chart rows.

## 2026-06-03: Kiosk Flow Split Between Fit and Optional Visual Preview

### Context

After testing the kiosk try-on path, we clarified that a 3DLOOK-like product
should not depend on generated try-on images for sizing. Qwen-style image
generation is useful for visual preview, but Fit Intelligence should make its
recommendations from captures, landmarks, body estimates, garment metadata, and
size charts.

### Decisions

- Keep `fit/analyze` as the primary sizing and recommendation path.
- Do not call Qwen or any image generator from Fit Intelligence.
- Add a clearer optional visual endpoint for generated previews:
  - `POST /api/v1/kiosk/sessions/{session_id}/visual-preview`
- Keep `POST /api/v1/kiosk/sessions/{session_id}/try-on` only as a deprecated
  compatibility alias.
- Continue treating visual preview output as UX evidence, not measurement truth.

### Implemented

- Added the `/visual-preview` kiosk route.
- Marked the older `/try-on` kiosk route as deprecated in OpenAPI.
- Updated kiosk architecture docs to show the sequence:
  1. garment upload
  2. optional avatar preview
  3. user capture
  4. capture analysis
  5. Fit Intelligence
  6. optional Qwen visual preview

### Next

- Implement Fit Intelligence v1 with measurement estimate and rule-based size
  recommendation.
- Keep visual preview cache and fit cache separate so API cost and sizing logic
  remain independently debuggable.

## 2026-06-04: Hybrid Fit Intelligence V1

### Context

We decided not to make Fit Intelligence either pure rules or pure AI. Pure AI is
too likely to hallucinate measurements or sizes, while pure rules miss useful
visual context from front/side captures and garment photos.

### Decisions

- Use AI only as an advisory fit analyzer.
- Keep final size selection owned by a deterministic scorer.
- Never allow AI analysis to override `recommended_size`.
- Accept optional body measurements from user input or a future measurement
  model. If measurements are missing, the engine must not invent them.
- Keep visual preview/Qwen image generation separate from Fit Intelligence.

### Implemented

- Upgraded Fit Intelligence engine version to `kiosk-fit-intelligence-hybrid-v1`.
- Added optional AI fit analysis output:
  - `body_shape_notes`
  - `garment_fit_intent`
  - `visual_fit_risks`
  - `measurement_uncertainty`
  - `recommendation_explanation_draft`
- Added optional request body measurements:
  - `height_cm`
  - `weight_kg`
  - `chest_cm`
  - `waist_cm`
  - `hip_cm`
  - `shoulder_cm`
  - `inseam_cm`
- Added deterministic `size_scores`.
- Added `size_recommendation.source = deterministic_scorer`.
- Added `use_ai_analysis` flag. If AI analysis fails or is unavailable, fit
  scoring continues with deterministic fallback and warning metadata.

### Current Limitation

The deterministic scorer only works when the request includes body measurements
that overlap with the garment size chart. The next step is replacing manual
measurements with a measurement estimation layer from front/side captures.

## 2026-06-04: Fit Intelligence V1 Report and Size Scoring

### Context

The hybrid Fit Intelligence API needed a more useful product response. Returning
only `recommended_size` and raw scores was not enough for a kiosk demo or a
3DLOOK-like fit experience.

### Decisions

- Keep deterministic size scoring as the source of truth.
- Add per-region fit diagnostics so the UI can explain why a size was selected.
- Keep AI notes separate from deterministic fit risks.
- Add a user-facing `fit_report` object instead of forcing clients to assemble
  explanations from raw scorer internals.

### Implemented

- Added `fit_report` to the Fit Intelligence response.
- Added ranked `candidates` and `alternative_sizes` to `size_recommendation`.
- Added per-metric scoring details under `size_scores[*].evaluated_metrics`:
  - body measurement
  - garment measurement
  - ease
  - target ease
  - fit label
  - risk level
  - guidance
- Added region-level fit output in `fit_assessment.region_fit`.
- Added size-chart support for `shoulder_cm`.
- Added bottoms scoring coverage for waist, hip, and inseam.

### Current Limitation

The scorer still depends on provided or upstream-estimated body measurements. It
does not yet estimate measurements from camera captures. The next Fit Engine
step is a calibrated measurement-estimation layer with confidence intervals.

## 2026-06-04: Measurement Signal Scaffold

### Context

Before training or fine-tuning a measurement model, the kiosk flow needs a
stable data contract for non-identifying body signals. We do not want the Fit
Engine to silently treat raw pose ratios as production measurements.

### Decisions

- Record landmark ratio signals from capture analysis for future calibration.
- Keep those ratios separate from body measurements used by the deterministic
  scorer.
- Do not recommend a size from landmark ratios alone.
- Add estimator metadata so future local or hosted measurement models can be
  swapped without changing the Fit Intelligence response shape.

### Implemented

- Upgraded Fit Intelligence engine version to `kiosk-fit-intelligence-hybrid-v2`.
- Added `LandmarkMeasurementEstimator` as a low-confidence scaffold.
- Added capture-analysis metrics:
  - `body_height_ratio`
  - `shoulder_width_ratio`
  - `hip_width_ratio`
  - `torso_height_ratio`
  - `shoulder_to_hip_ratio`
  - `front_facing_score`
- Added `measurement_estimate.measurement_signals`.
- Added `measurement_estimate.scorer_measurements_cm`.
- Added `measurement_estimate.scorer_eligible`.
- When user/body measurements are missing but landmark signals exist, the engine
  returns `landmark_based_preview` and `scorer_eligible=false`.

### Current Limitation

The landmark estimator is intentionally not a sizing model yet. It only records
calibration-ready ratios. Production sizing still requires provided
measurements or a calibrated measurement-estimation model.

## 2026-06-04: Fit Analysis Readback API

### Context

The kiosk UI needs to reload a session and show the latest Fit Intelligence
result without recomputing the analysis or calling AI providers again.

### Decisions

- Keep Fit Intelligence metadata cache as the source of truth for readback.
- Attach the latest `fit_analysis_key` to the kiosk session.
- Load fit results by session instead of exposing raw filesystem paths.

### Implemented

- Added `KioskFitIntelligenceService.get_analysis(fit_analysis_key)`.
- Added `GET /api/v1/kiosk/sessions/{session_id}/fit/analysis`.
- The endpoint returns the same `KioskFitAnalysisResponse` shape as
  `fit/analyze`, with `cache_hit=true`.

### Current Limitation

The endpoint returns the latest fit result attached to a session. It does not
yet list historical fit analyses for repeated garment or size-chart changes.

## 2026-06-04: Backend-Neutral Job Queue Boundary

### Context

Visual preview work can become GPU-bound and slow. The kiosk API should not be
coupled to one queue technology because local development, Redis deployments,
and Kafka/event-driven deployments have different operational tradeoffs.

### Decisions

- Introduce a small `JobQueueBackend` protocol before choosing Redis or Kafka.
- Keep job payloads as references only, not image bytes.
- Start with a local JSON backend so Swagger and local tests can validate the
  control plane without extra infrastructure.
- Use capability-oriented queues such as `gpu.visual_preview`.

### Implemented

- Added `src.modules.jobs` with `JobRecord`, `JobService`, and
  `LocalJobQueueBackend`.
- Added `JOB_QUEUE_BACKEND` and `JOB_QUEUE_DIR` settings.
- Added `POST /api/v1/kiosk/sessions/{session_id}/visual-preview/jobs`.
- Added `GET /api/v1/kiosk/jobs/{job_id}`.
- Updated kiosk architecture docs with the job queue boundary.

### Current Limitation

The current backend is local and single-node. Redis/Kafka backends and a worker
process still need to be implemented before distributed GPU deployment.

## 2026-06-04: Local Kiosk Worker

### Context

After adding the queue contract, the next useful step is a local worker that can
execute queued jobs without introducing Redis or Kafka yet.

### Decisions

- Use a separate worker process instead of running GPU jobs inside the API
  request.
- Keep the worker generic: lease one job, dispatch by `job_type`, mark result.
- Keep the kiosk-specific visual preview work in a handler.

### Implemented

- Added `JobWorker` and `JobHandler` protocol.
- Added `KioskVisualPreviewJobHandler` for `kiosk_visual_preview`.
- Added `scripts/run_kiosk_worker.py`.
- The worker supports:
  - `python -m scripts.run_kiosk_worker --once`
  - `python -m scripts.run_kiosk_worker`
- Added `make worker-once` and `make worker`.
- Added basic retry support through job `max_attempts`.
- Added stale running job recovery for local MVP deployments. The worker can
  requeue expired running jobs when attempts remain and fail them after the
  final attempt.

### Current Limitation

The worker still uses the local JSON backend and is single-node. Distributed
leases, retry backoff, and Redis/Kafka backends remain future work.

## 2026-06-04: Kiosk E2E Baseline Runner

### Context

Before deploying to a GPU server, the project needs a repeatable baseline that
proves the current model/control-plane flow works end to end with real local
images.

### Decisions

- Keep the default baseline free of paid image generation calls.
- Make visual preview an explicit opt-in via `--run-visual-preview`.
- Use the same local storage, garment registry, session service, Fit
  Intelligence service, local queue, and worker path as the kiosk API.

### Implemented

- Added `scripts/run_kiosk_e2e_baseline.py`.
- Added example size chart and body measurements under `docs/eval/`.
- Added `docs/eval/kiosk-e2e-baseline.md`.
- Updated kiosk architecture docs to require this baseline before GPU deploy.

### Current Limitation

The baseline can validate Fit Intelligence only when body measurements are
provided. Real measurement estimation from front/side captures is still future
work.

## 2026-06-04: Kiosk Swagger Deployment Surface

### Context

The deployment target is a Swagger-runnable kiosk API on a GPU server. The
default docs should show only endpoints needed for a kiosk operator or frontend
developer to run the flow end to end.

### Decisions

- Keep `API_PROFILE=kiosk` as the default profile for deploy/debug demos.
- Mount only health and kiosk routes in the default kiosk profile.
- Hide the deprecated kiosk `/try-on` alias from OpenAPI; `/visual-preview` is
  the primary generated-image endpoint.
- Keep legacy, evaluation, and avatar-preview APIs available through
  `API_PROFILE=full`.

### Implemented

- Updated the router profile registry so kiosk Swagger is focused.
- Updated schema text so kiosk session creation starts from `garment_id` and
  does not imply avatar cache keys are required.
- Updated architecture docs to match the deployable Swagger flow.

## 2026-06-04: Swagger Workflow Checklist

### Context

The kiosk baseline should be testable by a human operator from Swagger, not only
from scripts.

### Implemented

- Added `docs/kiosk-swagger-workflow.md`.
- Documented the exact Swagger sequence: upload garment, create session, upload
  captures, analyze captures, run Fit Intelligence, optional visual preview, job
  polling, and final session reload.
- Linked the checklist from the kiosk GPU architecture doc.

## 2026-06-04: Fit Analyze Swagger Body Simplification

### Context

The original `fit/analyze` body required testers to paste both body
measurements and a full size chart. That made the Swagger workflow too easy to
misuse.

### Decisions

- Treat size chart as garment metadata.
- Let `fit/analyze` use the size chart stored on the uploaded garment.
- Keep `fit/analyze.size_chart` as an override for ad hoc tests.

### Implemented

- Added optional `size_chart_json` to `POST /api/v1/kiosk/garments`.
- Persisted garment size charts in the local SQLite garment registry.
- Simplified the documented `fit/analyze` request body to body measurements,
  preferred fit, and optional AI advisory flag.

## Height/Weight Fit Analyze Input

For kiosk usage, requiring chest, waist, hip, shoulder, and inseam is still too
much friction. Most shoppers know height and weight only.

### Decisions

- Keep detailed body measurements optional.
- Allow `fit/analyze` to run with only `height_cm` and `weight_kg`.
- Mark this path as low-confidence `height_weight_estimate`, not as a real body
  scan or calibrated measurement.
- Preserve the existing deterministic scorer: AI advisory notes still cannot
  override the size recommendation.

### Implemented

- Added a deterministic height/weight estimator for chest, waist, hip,
  shoulder, and inseam fallback values.
- Added warnings when a size recommendation depends on height/weight-derived
  measurement estimates.
- Updated Swagger examples to show the short kiosk body.

## Market Size Chart Catalog

Garment size charts are mostly static market metadata. Vietnam, US, UK, EU, and
JP charts may differ, but the chart rarely changes for every single garment.

### Decisions

- Manage size charts as a reusable kiosk catalog.
- Let garments reference `size_chart_id` instead of duplicating chart rows.
- Keep inline `size_chart_json` on garment upload for quick Swagger tests and
  one-off overrides.
- Resolve Fit Analyze size chart in this order: request override, inline garment
  chart, reusable `size_chart_id`.

### Implemented

- Added a SQLite `SizeChartRegistry`.
- Added `POST/GET /api/v1/kiosk/size-charts` endpoints.
- Added `size_chart_id` to kiosk garment metadata and upload form.
- Updated Fit Analyze to resolve catalog charts automatically.

## Default Size Chart Seeds

Static market-level size charts are useful for demo, QA, and fallback flows.
They should still be clearly separated from brand or merchant-specific sizing.

### Decisions

- Seed generic VN, US, UK, and EU tops/bottoms charts for local Swagger testing.
- Mark seeded charts with `source_type=generic_reference`.
- Add optional source metadata to every chart: `source_type`, `source_url`, and
  `last_verified_at`.
- Keep seeded charts as approximate references, not official fit guarantees.

### Implemented

- Added `data/seeds/size_charts/default_size_charts.json`.
- Added `scripts/seed_size_charts.py` with idempotent seeding into the local
  SQLite size chart catalog.
- Extended the size chart registry, API requests, and API responses with source
  metadata.
- Updated the Swagger workflow to start from seed/list size chart when testing
  kiosk fit in Swagger.

## Local Kiosk State Reset

Swagger testing frequently needs a clean local state without manually deleting
SQLite files and generated JSON/image artifacts.

### Decisions

- Make reset dry-run by default.
- Reset the kiosk SQLite catalogs by default: size charts and garments.
- Require an explicit flag before clearing generated runtime files such as
  captures, sessions, try-on outputs, job metadata, and local garment images.
- Allow seeding default generic size charts immediately after reset.

### Implemented

- Added `scripts/reset_kiosk_state.py`.
- Added tests for dry-run, SQLite deletion, runtime file cleanup, and reset plus
  default size chart seed.
- Updated the Swagger workflow with reset commands and a note to restart the API
  server after reset.

## Kiosk Readiness Endpoint

Before deploying the kiosk package to a GPU server, the operator needs a cheap
preflight check that does not call Qwen, Replicate, or any expensive generation
path. Swagger should show whether local storage, SQLite catalogs, the job queue,
and provider configuration are ready before a user starts a session.

### Decisions

- Keep readiness under the health tag so it stays visible in the focused kiosk
  Swagger surface.
- Do not perform expensive model inference inside readiness.
- Ping Ollama `/api/tags` and verify the configured analyzer model is installed;
  this is cheap and catches local model/deploy mistakes before a user starts the
  kiosk flow.
- Create missing local SQLite schemas as part of the check, then verify required
  tables are readable.
- Treat missing visual-preview provider config as `not_ready`, because the kiosk
  demo target currently includes optional visual preview.

### Implemented

- Added `GET /api/v1/readiness`.
- Added structured readiness response schemas.
- Added tests for ready state, missing Replicate token, and missing Ollama
  analyzer model configuration.
- Added tests for unreachable Ollama runtime and installed-model mismatch.
- Updated the kiosk Swagger workflow and architecture notes to start with the
  readiness check.

## Kiosk Preflight CLI

The readiness endpoint is useful in Swagger, but deployment scripts need a
single shell command with a meaningful exit code.

### Decisions

- Add a preflight CLI that calls the running API's readiness endpoint instead of
  duplicating setup checks in a separate code path.
- Keep the default target local: `http://127.0.0.1:8080`.
- Return exit code `0` when ready, `1` when readiness reports `not_ready`, and
  `2` when the API cannot be reached or returns invalid JSON.
- Add a Makefile target for operator use.

### Implemented

- Added `scripts/kiosk_preflight.py`.
- Added `make kiosk-preflight`.
- Added tests for ready, not-ready, unreachable API, and JSON output behavior.

## RunPod Phase 1 Smoke Test

The first RunPod deployment test validated the kiosk API on a rented GPU pod
before investing in local image generation.

### Decisions

- Use a RunPod Pod, not RunPod Serverless, because the current app is a
  long-running FastAPI kiosk API plus local worker.
- Deploy the feature branch first instead of merging into `main`.
- Start with an A5000-class pod for cost efficiency; visual generation remains
  remote/optional in this phase.
- Use the RunPod PyTorch 2.8.0 template as the base environment.
- Install Ollama manually in the pod because the PyTorch template does not ship
  with Ollama.
- Set `DEBUG=true` during smoke testing so Swagger is exposed at `/docs`.
- Keep runtime data disposable for Phase 1; default size charts can be seeded
  again with Makefile targets.

### Implemented

- Added a single-process supervisor script for the single-pod MVP:
  `scripts/run_kiosk_all.py`.
- Added `make run-kiosk-all` for local all-in-one startup.
- Added RunPod-specific Makefile targets:
  - `make runpod-install`
  - `make runpod-pull-ollama`
  - `make runpod-start`
  - `make runpod-start-with-ollama`
  - `make runpod-preflight`
  - `make runpod-reset`
- Added `docs/deployment/runpod-roadmap.md`.
- Updated the RunPod deployment runbook to use the simplified Makefile flow.

### Result

- RunPod Phase 1 passed on June 8, 2026.
- API started successfully on `0.0.0.0:8080`.
- `GET /api/v1/readiness` returned `200 OK`.
- Ollama `/api/tags` was reachable from the API process.
- Swagger worked after enabling `DEBUG=true`.
- Default size charts were inserted and the Swagger kiosk flow was tested
  successfully.

## RunPod Phase 2 Replicate Visual Preview

The second RunPod deployment test validated the async visual preview path with
Replicate-backed Qwen image edit generation before moving to local GPU
generation.

### Decisions

- Keep visual generation on Replicate for the first full async validation only.
- Use the existing local JSON job queue and worker in the all-in-one RunPod Pod.
- Validate that the worker can update the kiosk session and persist generated
  image artifacts after a successful Replicate prediction.
- Defer local Qwen-edit generation until the async job/session/artifact path is
  stable and we have a reference quality/latency measurement.

### Issues Found

- Reset or fresh RunPod runtime data could remove `kiosk_tryons/images` and
  `kiosk_tryons/metadata`, causing generated output writes to fail.
- Worker job completion could fail when result payloads contained `Path`
  objects, because local JSON job records require JSON-serializable values.

### Implemented

- Made kiosk visual try-on artifact writes recreate output directories before
  writing images or metadata.
- Added JSON normalization for job queue payload/result/error fields, including
  `Path` to string conversion.
- Added regression tests for output directory recreation and serializing
  path-like job results.

### Result

- RunPod Phase 2 Replicate visual preview passed on June 9, 2026.
- Job `job:v1:450fe9e136ed411ba407834d23a174a8` completed with
  `status=succeeded`.
- Model: `qwen/qwen-image-edit-2511`.
- Input mapping: `multi_image_edit`.
- Prompt version: `avatar-qwen-multimodal-preview-v1`.
- Session reached `personalized_tryon_ready`.
- Generated try-on key:
  `kiosk-tryon:v1:fc854b904af7d3bf4b7eb7e991faa333301d7afcdab9ff70c4e1ce218e748691`.
- Generation time was about `9.22s` for the cached result.
- Warnings were empty.

### Next

- Review generated image quality from the persisted output path.
- Run two or three more garments and captures to get a small latency/quality
  baseline.
- Decide how to move production visual preview onto a self-hosted GPU engine.
  Replicate remains reference/debug only.

## RunPod Phase 3 Local Qwen-Edit Smoke

The third RunPod test checked whether Qwen image edit can run fully on our own
GPU infrastructure instead of depending on Replicate for visual preview
generation.

### Decisions

- Treat local Qwen image edit as a benchmark and research track, not the default
  production visual engine yet.
- Keep Replicate-backed Qwen as a reference quality/speed measurement while
  evaluating self-hosted alternatives.
- Split the self-hosted visual engine work into three tracks:
  - VTON-specific local model candidate for production.
  - Quantized or low-memory Qwen image-edit experiment.
  - Fine-tuning or LoRA only after a base local engine meets latency and memory
    targets.
- Do not fine-tune Qwen first. Fine-tuning a model that is too slow or too large
  for the target kiosk GPU would create a harder production problem.

### Issues Found

- `Qwen/Qwen-Image-Edit-2509` requires large local model storage; the download
  is roughly `57.7G`.
- A 24GB RTX 3090 can load and run the model only with aggressive low-memory
  settings.
- `768x768` and `1024x1024` generation are still risky on 24GB VRAM.
- Full CUDA placement causes out-of-memory errors. CPU/sequential offload is
  required for the current smoke path.
- The successful low-memory run is too slow for a production kiosk preview.

### Implemented

- Added local Qwen-edit smoke data preparation with reusable example fixtures.
- Added Makefile defaults for a 24GB-safe smoke profile:
  - output size `512x512`
  - input max side `512`
  - `8` inference steps
  - CPU offload enabled
  - sequential CPU offload enabled
- Added CUDA/runtime reporting helpers for RunPod debugging.
- Added a self-hosted visual engine strategy document:
  `docs/architecture/self-hosted-visual-engine-strategy.md`.
- Added a local VTON candidate shortlist:
  `docs/architecture/local-vton-candidate-shortlist.md`.

### Result

- Local Qwen-edit smoke passed on June 10, 2026 with:
  - GPU: RTX 3090 24GB
  - model: `Qwen/Qwen-Image-Edit-2509`
  - pipeline: `QwenImageEditPlusPipeline`
  - output size: `512x512`
  - input max side: `512`
  - steps: `8`
  - CPU offload: enabled
  - sequential CPU offload: enabled
  - generation time: about `272s`
- The result proves self-hosted feasibility, but not production readiness.

### Next

- Run one more Qwen curve test at `640x640`, input max `640`, `8` steps only if
  the pod has enough headroom.
- Select one VTON-specific local candidate and build a smoke test before adding
  an API adapter.
- Keep the existing Replicate Qwen path only for benchmark/debug until a local
  engine beats it on quality, latency, and reliability.

## CatVTON Local Smoke Harness

After deciding that Qwen local is too slow to be the first production local
engine, CatVTON became the first VTON-specific local candidate to test on
RunPod.

### Decisions

- Add a smoke harness before adding any API adapter.
- Keep CatVTON isolated from the FastAPI app and worker until runtime, quality,
  and licensing are understood.
- Use the existing smoke fixtures so CatVTON can be tested without replaying
  the full Swagger workflow.
- Default to CatVTON auto-mask for quality testing, but provide a rough-mask
  fallback for pipeline/runtime debugging.

### Implemented

- Added `scripts/local_catvton_smoke.py`.
- Added `make runpod-install-catvton-deps`.
- Added `make runpod-catvton-smoke`.
- Split CatVTON smoke into a cheap canary (`512x768`, `8` steps) and a
  quality smoke (`768x1024`, `30` steps) to reduce RunPod spend while debugging.
- Updated the RunPod deployment runbook and roadmap with the CatVTON smoke
  sequence.

### Next

- Run the CatVTON canary first on the cheapest viable 20-24GB VRAM GPU.
- Run `make runpod-catvton-quality-smoke` only after the canary passes.
- If `RUNPOD_CATVTON_MASK_MODE=auto` works and output quality is acceptable,
  design `LocalCatVtonEngine` behind the existing kiosk visual-preview worker
  contract.
- If auto-mask blocks the smoke, use `RUNPOD_CATVTON_MASK_MODE=rough` only to
  validate pipeline load/runtime, then revisit mask generation separately.

### Result

- CatVTON smoke was tested on RTX 4000 Ada 20GB.
- The cheap canary (`512x768`, `8` steps) produced an output but the image was
  not visually clear enough for quality judgment.
- The quality smoke (`768x1024`, `30` steps) improved the result and preserved
  the garment direction, but details were still not clear enough to beat the
  current Qwen/Replicate baseline.
- Conclusion: CatVTON is viable as a local runtime candidate, but not ready for
  a production adapter from this single fixture. Continue with controlled
  comparison rather than repeated blind CatVTON runs.

### Follow-Up

- CatVTON was retested and remained visually soft.
- Production garments can come from web product images with background,
  watermark, model-shot composition, crops, and other uncontrolled artifacts.
  The production quality bar is therefore Qwen-edit-level robustness, not just
  clean benchmark VTON transfer.
- Decision: pause CatVTON. Do not spend more RunPod time on blind CatVTON
  tuning.
- Continue using Qwen-edit/Replicate as a reference-only quality benchmark while
  evaluating either a stronger self-hosted foundation image-edit path or another
  VTON-specific model that can handle uncontrolled garment inputs.

## Kiosk Single-GPU Runtime Constraint

Coach feedback clarified the production deployment target: the kiosk runtime
should package all required models on one GPU server. The production kiosk path
should therefore not depend on Replicate/Qwen-edit for visual preview
generation.

### Decisions

- Keep Replicate/Qwen-edit only as a benchmark/debug reference for comparing
  output quality.
- Do not treat Replicate as the MVP production fallback for kiosk visual
  preview.
- Keep remote avatar/user-avatar experiments separate from the kiosk production
  visual-preview path.
- Default RunPod kiosk config should disable visual preview until a self-hosted
  GPU engine passes the quality gate.
- Continue searching for a self-hosted visual engine that can handle messy web
  garment images with Qwen-like robustness.

### Implemented

- Added `KIOSK_VISUAL_PREVIEW_PROVIDER`.
- Set the RunPod kiosk template default to
  `KIOSK_VISUAL_PREVIEW_PROVIDER=disabled`.
- Updated readiness so a self-hosted kiosk deployment no longer requires a
  Replicate API token.
- Added a guard so kiosk visual-preview endpoints/jobs do not call Replicate
  unless `KIOSK_VISUAL_PREVIEW_PROVIDER=replicate_qwen` is explicitly enabled
  for benchmark/debug.

### Next

- Define the production self-hosted visual engine contract.
- Shortlist stronger local candidates before spending more RunPod time.
- Keep CatVTON paused until there is a concrete hypothesis that improves the
  soft-output issue.

## Fixed Model Quality Gate

After CatVTON produced soft outputs on the same smoke fixture, the project now
uses a fixed Model Quality Gate Matrix before any new self-hosted visual engine
gets an API adapter.

### Decisions

- Added `docs/eval/model-quality-gate-matrix.md` as the fixed evaluation gate.
- The production gate prioritizes garment fidelity, web-garment robustness,
  human preservation, sleeve quality, latency/VRAM, integration simplicity, and
  license/commercial path.
- Qwen-edit remains the visual quality reference only; it is not the production
  kiosk fallback.
- CatVTON remains paused because the local smoke output is below the required
  quality bar.

### Candidate ROI Order

1. Leffa.
2. OmniVTON.
3. Re-CatVTON, only after code/weights are clearly available.
4. DiT-VTON, research watchlist only until there is a straightforward local
   inference path.

### Next

- Build a Leffa smoke harness first:
  - `make runpod-leffa-smoke-data`
  - `make runpod-install-leffa-deps`
  - `make runpod-leffa-import-check`
  - `make runpod-leffa-smoke`
- Do not build `LocalLeffaEngine` or wire it into the kiosk worker until Leffa
  passes the fixed quality gate.

## Leffa Local Smoke Harness

Implemented the first Leffa adaptation layer as a smoke harness, not as a
production engine adapter.

### Implemented

- Added `scripts/local_leffa_smoke.py`.
- Added `make runpod-install-leffa-deps`.
- Added `make runpod-leffa-import-check`.
- Added `make runpod-leffa-smoke-data` as an alias for shared smoke inputs.
- Added `make runpod-leffa-smoke`.
- Extended the shared smoke-data manifest with:
  - `leffa_garment_type`
  - `leffa_smoke_command`
- Updated RunPod docs with the Leffa smoke sequence.

### Decision

Leffa remains a candidate under evaluation. Do not wire it into
`KIOSK_VISUAL_PREVIEW_PROVIDER` yet. The next RunPod run should answer whether
Leffa can beat the fixed quality gate on the same Qwen reference fixture and
messy web-style garment fixtures.

### Follow-Up

- Initial Leffa smoke on RTX 4000 Ada 20GB looked materially better than
  CatVTON and preserved the shirt structure/pattern better.
- Remaining issue: output is still somewhat soft, especially around garment
  detail and input-image artifacts.
- Added a deterministic conditioning A/B path:
  - `scripts/prepare_vton_conditioned_inputs.py`
  - `make runpod-vton-condition-smoke-inputs`
  - `make runpod-leffa-conditioned-smoke`
- This conditioning stage does not use another ML model. It normalizes image
  contrast/sharpness, crops/recenters the person foreground on a clean neutral
  canvas, crops/centers the garment, converts the references to PNG, and writes
  a conditioning report.
- Decision: run conditioned Leffa smoke before changing model weights,
  fine-tuning, or trying another candidate. If conditioning improves clarity,
  add an explicit input conditioning stage to the production architecture.
