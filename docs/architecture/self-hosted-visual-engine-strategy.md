# Self-Hosted Visual Try-On Engine Strategy

## Context

The product direction is to run the kiosk stack fully on our own infrastructure:
API, worker, capture analysis, fit intelligence, and visual try-on generation.
Replicate remains useful as a baseline, but it should not be the long-term
runtime dependency for the production kiosk.

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

Separate the local visual engine strategy into three tracks:

1. **Self-hosted VTON production candidate**
   - Prioritize a VTON-specific model that is smaller and purpose-built for
     person plus garment try-on.
   - Qwen image edit is a useful quality reference, but not the first
     production local engine on 24GB GPUs.

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
model shortlist and smoke-test order.

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
  - `ReplicateQwenPreviewEngine`
  - `LocalQwenEditEngine` experiment only
  - `LocalVtonEngine` production candidate

The worker should choose an engine from config:

- `VISUAL_TRYON_ENGINE=replicate_qwen`
- `VISUAL_TRYON_ENGINE=local_qwen_edit`
- `VISUAL_TRYON_ENGINE=local_vton`

The request/result schema should stay stable:

- input references: session id, front capture, optional side capture, garment id
- output: generated image path/key, model metadata, warnings, latency, memory
  metrics

## Recommended Next Steps

1. Record the RTX 3090 Qwen local smoke result as a benchmark.
2. Run one more Qwen curve test at `640x640`, input max `640`, `8` steps.
3. Research and select one VTON-specific local candidate for the next smoke.
4. Implement a small `LocalVtonEngine` adapter behind the same worker contract.
5. Compare:
   - Replicate Qwen
   - Local Qwen low-memory
   - Local VTON candidate
6. Only then decide whether to invest in quantization or LoRA/fine-tuning.

## Current Position

The product should continue moving toward a fully self-hosted runtime, but the
local visual generation engine should not be locked to Qwen image edit. Qwen is
valuable as a multimodal quality reference; the production engine may need to be
a smaller VTON-specific model with later fine-tuning.
