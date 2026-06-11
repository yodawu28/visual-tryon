# Self-Hosted Visual Try-On Engine Strategy

## Context

The product direction is to run the kiosk stack fully on our own infrastructure:
API, worker, capture analysis, fit intelligence, and visual try-on generation.
Coach feedback tightened this into a hard production constraint: all production
kiosk models must run on one GPU server package. Replicate/Qwen-edit remains
useful as a quality reference, notebook benchmark, or future avatar-specific
feature, but it is not a production runtime dependency for kiosk visual preview.

Production garment inputs are expected to be messy: product images downloaded
from websites may include backgrounds, watermarks, model shots, crops, shadows,
non-flat-lay composition, or partial catalog overlays. A self-hosted visual
engine must therefore be judged against Qwen-edit-level robustness, not only on
clean VTON benchmark-style garment images.

The first local Qwen image-edit smoke test on RTX 3090 validated that the
runtime can load and execute, but only with aggressive low-memory settings:

- GPU: RTX 3090, 24GB VRAM
- Model: `Qwen/Qwen-Image-Edit-2509`
- Pipeline: `QwenImageEditPlusPipeline`
- Output: `512x512`
- Input max side: `512`
- Steps: `8`
- CPU offload: enabled
- Sequential CPU offload: enabled
- Result: success
- Latency: about `272s`

This proves feasibility for research, not production readiness. A kiosk preview
cannot depend on a 4-5 minute local image-edit path.

## Decision

Separate the self-hosted visual engine strategy into three tracks:

1. **Self-hosted production visual engine candidate**
   - Prioritize models that run entirely on our GPU server and accept person
     plus garment references.
   - A VTON-specific model is preferred only if it can handle uncontrolled web
     garment images. Otherwise, a self-hosted foundation image-edit model may be
     required.
   - Remote Qwen image edit is a quality reference, not a production fallback.

2. **Qwen local optimization experiment**
   - Keep Qwen image edit as a benchmark and research track.
   - Test quantization, reduced input/output sizes, fewer steps, and better
     offload settings.
   - Do not build the API adapter until latency and memory meet the gate.

3. **Domain adaptation and fine-tuning**
   - Fine-tune or LoRA-adapt the best local VTON candidate after the base
     model is fast enough.
   - Do not start fine-tuning before selecting a base model that can run within
     the target deployment budget.

## Candidate Model Tracks

See `docs/architecture/local-vton-candidate-shortlist.md` for the current
model shortlist and `docs/eval/model-quality-gate-matrix.md` for the fixed
quality gate and ROI order.

### Track A: VTON-Specific Local Model

Goal: find a local model that can run at practical latency on 24GB to 48GB GPUs.

Candidates:

- CatVTON or newer CatVTON-family models
- IDM-VTON or optimized derivatives
- StableVITON-style ControlNet/diffusion VTON
- Other VTON-specific models with public weights and simple person plus garment
  inputs

Why this track is primary:

- VTON models are trained for garment transfer, not general image editing.
- They can be smaller than multimodal foundation image-edit models.
- They often expose garment masks, body masks, or category controls that are
  closer to production try-on requirements.

Success gate:

- Runs locally at `768x1024` or equivalent usable kiosk preview size.
- Latency under `60s` on RTX 3090/A5000 class hardware, ideally under `30s`.
- Preserves garment color, logo/text, sleeve length, and body pose better than
  the current baseline.
- Leaves enough memory headroom for API/worker/Ollama analyzer or runs cleanly
  in a separate GPU worker process.

Current CatVTON status:

- RTX 4000 Ada 20GB can run the cheap canary and full quality smoke.
- The quality smoke is better than the canary but still visually soft on the
  shared fixture, and retesting did not resolve the softness.
- CatVTON has not passed the quality gate. Do not build a production adapter
  until it reaches Qwen-reference quality on the same person/garment
  pair and proves robust on uncontrolled web garment images.
- Current decision: pause CatVTON work. Keep Qwen-edit/Replicate as a
  reference-only benchmark while evaluating stronger self-hosted options.

### Track B: Quantized Qwen Image Edit

Goal: determine whether Qwen image edit can be made practical through
quantization or compile/runtime optimizations.

Experiments:

- FP8 or 8-bit quantization if pipeline components support it.
- 4-bit/8-bit transformer quantization if compatible with Diffusers/Qwen image
  edit internals.
- Reduced input size and output size curves: `512`, `640`, `768`, `1024`.
- Step count curve: `4`, `8`, `12`, `20`.
- CPU offload vs sequential CPU offload vs device map.

Risks:

- Quantization support may not cover all Qwen image-edit components.
- Quality can degrade on text/logo preservation.
- CPU offload can make latency too slow for kiosk usage.

Success gate:

- `768x768` or better output under `90s` on 24GB GPU.
- No OOM across repeated runs.
- Output quality is meaningfully better than a smaller VTON model.

### Track C: Fine-Tuning / LoRA

Goal: adapt the selected local visual engine to our product domain after the
base runtime is viable.

Do not fine-tune Qwen first unless quantized/local Qwen already meets the
latency and memory gate. Full multimodal image-edit fine-tuning is likely too
expensive and operationally heavy for the current stage.

Prefer:

- LoRA on a smaller VTON-specific model.
- Fine-tune on our target categories first: tops, jerseys, t-shirts, shorts.
- Train with pairs that reflect kiosk captures: front-facing person, optional
  side capture, product garment image, generated or real target try-on.

Dataset needs:

- Garment image.
- Person capture.
- Target try-on image or high-quality pseudo-label.
- Garment metadata: category, sleeve length, neckline, color, logo/text zones.
- Optional masks/pose landmarks/body parsing outputs.

Success gate:

- Improves garment fidelity and sleeve/arm quality over the base local model.
- Does not overfit to one avatar/body type.
- Keeps inference latency inside the selected production target.

## Engine Architecture

Keep the API contract independent from the model implementation:

- `VisualTryOnEngine`
  - `ReplicateQwenPreviewEngine` benchmark/debug only
  - `LocalQwenEditEngine` experiment only
  - `LocalVtonEngine` production candidate

The worker should choose an engine from config:

- `VISUAL_TRYON_ENGINE=disabled`
- `VISUAL_TRYON_ENGINE=local_qwen_edit`
- `VISUAL_TRYON_ENGINE=local_vton`

Production gate:

- Kiosk production must not call remote image generation providers.
- `KIOSK_VISUAL_PREVIEW_PROVIDER=replicate_qwen` is allowed only for
  benchmark/debug runs and should not be used in the production RunPod template.
- `KIOSK_VISUAL_PREVIEW_PROVIDER=disabled` is the safe default until a
  self-hosted visual engine passes quality, latency, memory, and licensing
  gates.

The request/result schema should stay stable:

- input references: session id, front capture, optional side capture, garment id
- output: generated image path/key, model metadata, warnings, latency, memory
  metrics

## Recommended Next Steps

1. Record the RTX 3090 Qwen local smoke result as a benchmark.
2. Run one more Qwen curve test at `640x640`, input max `640`, `8` steps.
3. Build a Leffa smoke harness as the next high-ROI candidate.
4. Implement a production adapter only after a candidate passes the fixed
   quality gate.
5. Compare against the reference:
   - Replicate Qwen reference output
   - Local Qwen low-memory
   - Local VTON candidate
6. Only then decide whether to invest in quantization or LoRA/fine-tuning.

## Current Position

The product should continue moving toward a fully self-hosted runtime, but the
local visual generation engine should not be locked to Qwen image edit. Qwen is
valuable as a multimodal quality reference; the production engine may need to be
a smaller VTON-specific model with later fine-tuning, or a self-hosted
foundation image-edit model if VTON-specific candidates remain too weak on
messy production garment inputs.
