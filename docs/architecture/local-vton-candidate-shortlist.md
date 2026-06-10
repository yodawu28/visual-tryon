# Local VTON Candidate Shortlist

This document tracks local visual try-on model candidates for the kiosk
architecture. The goal is to find a self-hosted engine that can replace or
complement the Replicate-backed Qwen preview path.

## Selection Criteria

Candidates are evaluated against the current kiosk system:

- Runs on local GPU infrastructure.
- Accepts a person image and garment image, or can be adapted to that contract.
- Can be invoked by a worker process and return an image path plus metadata.
- Does not require a complete rewrite of the API/session/job flow.
- Has public code and weights, or at least a practical path to local inference.
- Has manageable licensing risk for the current research stage.

## Recommended Test Order

### 1. CatVTON

Source:

- GitHub: `https://github.com/Zheng-Chong/CatVTON`
- Paper: `https://arxiv.org/abs/2407.15886`

Why it is the first local candidate:

- Purpose-built VTON model, not a general image-edit model.
- Simple input direction: person image plus garment image.
- Repository claims simplified inference and low VRAM usage for `1024x768`.
- Better fit for our adapter boundary than Qwen image-edit because it is
  smaller and VTON-specific.

Integration fit:

- Candidate adapter name: `LocalCatVtonEngine`.
- Worker contract can stay the same:
  - `session_id`
  - front capture path
  - optional side capture path ignored initially
  - garment image path
  - category
  - output path
- First smoke target:
  - `768x1024` or repo default
  - `bf16`
  - one generated sample from `examples/qwen_edit_smoke`

Risks:

- The repo license is non-commercial oriented. This is acceptable for research,
  but must be reviewed before production use.
- Some app paths can use SCHP/DensePose for masks; we should first test the
  simplest inference path and avoid coupling the kiosk API to those
  preprocessors unless quality requires it.

Verdict: **primary research candidate**.

Recommended RunPod smoke configuration:

- GPU: RTX 3090 24GB or RTX A5000 24GB for first smoke.
- Prefer RTX 3090 if the price gap is acceptable, because it gives better raw
  image-generation throughput while keeping the same 24GB VRAM class.
- RTX A5000 is acceptable for the first install/runtime smoke if it is much
  cheaper, but quality/latency numbers should be rechecked on the final target
  GPU.
- Avoid A100/H100 for the first smoke. CatVTON's published runtime target is
  far below that class, so high-end GPUs should be reserved for later
  fine-tuning or batch evaluation.
- Storage:
  - Container disk: `30G` is enough for the OS/runtime.
  - Persistent network volume: `80G` minimum, `100G` preferred.
  - Keep model/cache paths under `/workspace/tryon-models`.
- First smoke profile:
  - precision: `bf16`
  - output size: `1024x768` if the repo default path works
  - fallback output size: `768x1024` or `768x768`
  - sample count: `1`
  - batch size: `1`

### 2. OOTDiffusion

Source:

- GitHub: `https://github.com/levihsu/OOTDiffusion`
- Paper: `https://arxiv.org/abs/2403.01779`

Why it is useful:

- Official implementation has released checkpoints for half-body VITON-HD and
  full-body DressCode flows.
- CLI-style inference is close to our worker model.
- Supports garment category for full-body mode.

Integration fit:

- Candidate adapter name: `LocalOotDiffusionEngine`.
- Good for testing upper-body and full-body garment transfer.
- The repo command shape already maps to `model_path`, `cloth_path`, category,
  scale, and sample count.

Risks:

- Requires human parsing/openpose/CLIP checkpoint setup.
- Repo notes Linux testing; this is fine for RunPod but less useful for local
  Mac development.
- More preprocessing means more operational surface than CatVTON.

Verdict: **second local smoke candidate if CatVTON is poor or blocked**.

### 3. IDM-VTON Local

Source:

- GitHub: `https://github.com/yisol/IDM-VTON`
- Paper: `https://arxiv.org/abs/2403.05139`

Why it is useful:

- Strong known baseline for diffusion VTON.
- The current system already uses IDM-style providers elsewhere, so quality is
  useful for comparison.
- Inference scripts support `768x1024` style output and a category-like path
  through dataset-specific inference.

Integration fit:

- Candidate adapter name: `LocalIdmVtonEngine`.
- Useful as a local baseline against Replicate/Qwen and CatVTON.

Risks:

- Heavier environment and preprocessing: DensePose, human parsing, OpenPose,
  and IP-Adapter assets.
- The repo is dataset-structured, so direct single-request API wrapping may take
  more glue code.
- More moving parts than desired for the first self-hosted MVP.

Verdict: **quality baseline, not first local production candidate**.

### 4. StableVITON

Source:

- GitHub: `https://github.com/rlawjdghek/StableVITON`
- Paper: `https://arxiv.org/abs/2312.01725`

Why it is useful:

- Research-backed VTON model focused on semantic correspondence and garment
  detail preservation.
- Supports repaint behavior, which is conceptually useful for preserving
  unmasked regions.

Integration fit:

- Candidate adapter name: `LocalStableVitonEngine`.
- Good for comparison if we want a ControlNet/latent-diffusion style baseline.

Risks:

- Older dependency stack and CUDA assumptions.
- Requires dataset-style inputs such as densepose, agnostic mask, cloth mask,
  and related checkpoints.
- Less aligned with our simple worker contract than CatVTON.

Verdict: **deferred comparison candidate**.

### 5. HR-VITON / GP-VTON

Sources:

- HR-VITON GitHub: `https://github.com/sangyun884/HR-VITON`
- GP-VTON GitHub: `https://github.com/xiezhy6/GP-VTON`

Why they are useful:

- These are warping/parsing-oriented VTON systems, so they are relevant to
  garment geometry, sleeve handling, and local-flow ideas.
- They may be useful later for fine-tuning or architecture ideas if diffusion
  models do not preserve sleeves/logo regions well enough.

Risks:

- Older stacks and dataset-oriented workflows.
- More preprocessing and checkpoint handling.
- Less direct fit for an MVP worker adapter.

Verdict: **research references, not immediate MVP candidates**.

## Not Recommended As First Local Engine

### Qwen Image Edit

Keep Qwen as the quality reference and optional research path, but not as the
first self-hosted production engine. Current local smoke result:

- RTX 3090 24GB
- `512x512`
- input max side `512`
- `8` steps
- CPU and sequential CPU offload
- about `272s`

This is too slow for kiosk preview, even though it proves local feasibility.

### Kolors Virtual Try-On

Kolors Virtual Try-On is useful as a quality reference, but the public Kolors
repository presents it mainly as a released demo path. It is not currently as
straightforward as CatVTON or OOTDiffusion for a direct local worker adapter in
our system.

## Proposed Smoke Milestones

1. Add a generic local VTON smoke command:
   - `make runpod-local-vton-smoke MODEL=catvton`
2. Implement model-specific scripts under `scripts/`:
   - `scripts/local_catvton_smoke.py`
   - `scripts/local_ootdiffusion_smoke.py`
3. Use the existing example fixtures:
   - `examples/qwen_edit_smoke/front.png`
   - `examples/qwen_edit_smoke/garment.webp`
4. Record for every smoke:
   - model name and commit/tag
   - GPU name and VRAM
   - model storage size
   - output size
   - latency
   - peak VRAM
   - generated output path
   - manual quality score
5. Only build an API adapter after a candidate passes smoke quality and runtime
   gates.

## Current Recommendation

Start with **CatVTON**. If it installs and runs cleanly on RunPod, it is the
best match for our current system boundary. If CatVTON fails on quality or
licensing, test **OOTDiffusion** next. Keep **IDM-VTON local** as a quality
baseline, and keep **Qwen local** as a reference rather than the default local
engine.
