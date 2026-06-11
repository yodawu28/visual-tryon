# Local VTON Candidate Shortlist

This document tracks local visual try-on model candidates for the kiosk
architecture. The goal is to find a self-hosted engine that can replace or
outperform the Replicate-backed Qwen reference path for production kiosk use.

## Selection Criteria

Candidates are evaluated against the current kiosk system:

- Runs on local GPU infrastructure.
- Accepts a person image and garment image, or can be adapted to that contract.
- Can be invoked by a worker process and return an image path plus metadata.
- Does not require a complete rewrite of the API/session/job flow.
- Has public code and weights, or at least a practical path to local inference.
- Has manageable licensing risk for the current research stage.

Use `docs/eval/model-quality-gate-matrix.md` as the fixed quality gate before
promoting any candidate to an API adapter.

## Recommended Test Order

### 1. Leffa

Source:

- GitHub: `https://github.com/franciszzj/Leffa`
- Paper: `https://arxiv.org/abs/2412.08486`

Why it is the next high-ROI candidate:

- Public code, model links, Hugging Face demo path, and MIT license.
- Purpose includes virtual try-on and pose transfer.
- The method explicitly targets fine-grained texture distortion, which maps
  directly to our garment fidelity requirement.
- More mature implementation signal than the newer research candidates.

Integration fit:

- Candidate adapter name: `LocalLeffaEngine`.
- Smoke first, no API adapter until it passes the fixed quality gate.
- Reuse the same person/garment fixtures as Qwen-edit and CatVTON.

Risks:

- Uses preprocessing components such as SCHP/DensePose, so dependency setup may
  be heavier than CatVTON.
- Reported fast runtime is on A100-class hardware; we still need RTX 3090 /
  RTX 4000 Ada / L4 numbers.

Verdict: **test next**. This has the best immediate ROI among the current
candidate set.

### 2. OmniVTON

Source:

- GitHub: `https://github.com/Jerome-Young/OmniVTON`
- Paper: `https://arxiv.org/abs/2507.15037`

Why it is useful:

- Training-free universal VTON direction fits the messy garment input problem.
- Claims garment detail preservation and pose consistency across diverse
  settings.
- Public repository exists.

Risks:

- Newer and less mature repository signal than Leffa.
- May have more complex runtime because it is training-free and universal.

Verdict: **second candidate after Leffa**.

### 3. Re-CatVTON

Source:

- Paper: `https://arxiv.org/abs/2511.18775`

Why it is useful:

- Directly addresses CatVTON's efficiency/quality trade-off.
- If code and weights become available, it is the most natural successor to the
  failed CatVTON smoke.

Risks:

- Treat as research watchlist until public local inference code and weights are
  clearly available.

Verdict: **track, but do not smoke before Leffa/OmniVTON unless release status
changes**.

### 4. DiT-VTON

Source:

- Paper: `https://arxiv.org/abs/2510.04797`

Why it is useful:

- Promising direction for multi-category product handling and real-world image
  robustness.
- Strategically relevant if classic VTON pipelines continue failing on messy
  garment inputs.

Risks:

- Lower immediate ROI without a straightforward public local inference path.

Verdict: **research watchlist only for now**.

### 5. CatVTON

Source:

- GitHub: `https://github.com/Zheng-Chong/CatVTON`
- Paper: `https://arxiv.org/abs/2407.15886`

Why it was the first local candidate:

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
  - cheap canary first, then quality-size smoke only after canary passes
  - `bf16`
  - one generated sample from `examples/qwen_edit_smoke`

Risks:

- The repo license is non-commercial oriented. This is acceptable for research,
  but must be reviewed before production use.
- Some app paths can use SCHP/DensePose for masks; we should first test the
  simplest inference path and avoid coupling the kiosk API to those
  preprocessors unless quality requires it.

Retest result:

- CatVTON ran successfully on RTX 4000 Ada 20GB.
- The cheap canary was useful for runtime validation only.
- The quality smoke improved over the canary, but repeated tests were still
  visually soft and below the Qwen-edit/Replicate reference quality.
- Production garments may come from web product images with background,
  watermark, model shots, crops, or non-flat-lay composition. CatVTON did not
  demonstrate enough robustness for this production input profile.

Verdict: **pause after failed quality gate**. Do not build
`LocalCatVtonEngine` until there is a clear new hypothesis, such as better
garment preprocessing, a stronger CatVTON-family checkpoint, or domain
fine-tuning data. Use Qwen-edit as a reference-only quality benchmark.

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
  - canary output size: `512x768`
  - canary steps: `8`
  - quality output size: `768x1024`
  - quality steps: `30`
  - sample count: `1`
  - batch size: `1`

### 6. OOTDiffusion

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

Verdict: **lower ROI than Leffa for the next smoke** because the dependency and
preprocessing surface is heavier. It still needs to be measured against
Qwen-edit on uncontrolled web garment inputs before any adapter work.

### 7. IDM-VTON Local

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
- Useful as a local comparison point against the Qwen reference and CatVTON.

Risks:

- Heavier environment and preprocessing: DensePose, human parsing, OpenPose,
  and IP-Adapter assets.
- The repo is dataset-structured, so direct single-request API wrapping may take
  more glue code.
- More moving parts than desired for the first self-hosted MVP.

Verdict: **comparison reference, not first local production candidate**.

### 8. StableVITON

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

### 9. HR-VITON / GP-VTON

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

1. Add a Leffa smoke command:
   - `make runpod-leffa-smoke-data`
   - `make runpod-install-leffa-deps`
   - `make runpod-leffa-import-check`
   - `make runpod-leffa-smoke`
2. Implement model-specific scripts under `scripts/`:
   - `scripts/local_leffa_smoke.py`
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

Pause **CatVTON** after the RTX 4000 Ada smoke results because it runs but does
not meet the Qwen-edit quality bar. Keep **Qwen-edit/Replicate** as a
reference-only benchmark, not a production kiosk dependency. If local VTON
research continues, test **Leffa** next with the same uncontrolled web garment
requirement before building any API adapter. Keep **OmniVTON** second, keep
**Re-CatVTON** and **DiT-VTON** on the watchlist, keep **IDM-VTON local** as a
comparison reference, and keep **Qwen local** as a research reference until it
can meet the latency and memory gate.
