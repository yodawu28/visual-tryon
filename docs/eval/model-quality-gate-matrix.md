# Model Quality Gate Matrix

This matrix defines the fixed quality gate for choosing a self-hosted kiosk
visual try-on engine. A model is not production-ready just because it can run on
RunPod. It must pass visual quality, robustness, runtime, integration, and
licensing gates on the same evaluation fixture set.

## Mission

Find a self-hosted visual try-on model that can run on one GPU server and
produce production-quality kiosk previews without Replicate/Qwen-edit remote
generation.

Replicate/Qwen-edit is a reference-only benchmark. It is not a production
fallback for kiosk visual preview.

## Fixed Fixture Set

Use the same fixtures for every candidate:

- `examples/qwen_edit_smoke/front.png`
- `examples/qwen_edit_smoke/garment.webp`
- at least two additional web-style garment images:
  - `data/garment_catalog/garment-2.webp`: product image with web background
    artifacts/icons
  - `data/garment_catalog/garment-3.webp`: product image with watermark-like
    background artifacts
- at least one logo/text garment
- at least one patterned garment
- at least one short-sleeve garment
- at least one long-sleeve garment

If a candidate requires masks, parsing, or pose maps, the smoke must record
whether those inputs were manually provided, auto-generated, or unavailable.

If deterministic input conditioning is used, record both the original-input
result and the conditioned-input result. Conditioning can crop/recenter the
person foreground on a clean canvas, crop/center a garment, normalize
contrast/sharpness, and convert lossy web images to PNG, but it must not be
allowed to hide a weak model by destroying body alignment, logo, text, color, or
pattern fidelity.

Before scoring model quality, score the input quality. A blurry output is not a
model failure when the source capture is too small, too blurry, badly cropped,
or does not allocate enough pixels to the torso/garment print area.

- `make runpod-vton-input-quality`
- `make runpod-vton-input-quality PERSON_IMAGE=/path/to/selfie.png GARMENT_IMAGE=/path/to/garment.webp`
- `make runpod-vton-input-quality RUNPOD_VTON_INPUT_GARMENT_CATEGORY=tops`

Important report fields:

- `person.estimated_logo_width_px`: rough estimate of how many source pixels
  are available for a chest logo/text region.
- `person.torso_area_ratio_estimate`: rough torso area as a fraction of the
  image.
- `person.blur_variance` and `garment.blur_variance`: basic sharpness proxies.
- `issues`: input-quality blockers to fix before judging the VTON model.
- `critical_issues`: blockers that make a high-detail VTON judgment invalid
  even when the total score is high.
- `recommendation`: next action, usually closer capture, upper-body crop, or
  sharper garment image.

Category-aware critical checks:

| Garment category | Critical person checks |
| --- | --- |
| `tops` / `upper` / `shirt` / `t_shirt` | `torso_detail_enough` |
| `bottoms` / `lower` / `pants` / `shorts` | `lower_body_detail_enough`, `lower_body_visible` |
| `full_outfit` / `top_and_bottom` | `torso_detail_enough`, `lower_body_detail_enough`, `lower_body_visible` |
| `dress` | `torso_detail_enough`, `lower_body_detail_enough`, `lower_body_visible` |

All categories also require `garment_sharp_enough` and `garment_large_enough`.

## Score Scale

Use `1` to `5` for each visual category:

- `1`: unusable
- `2`: visibly wrong or heavily distorted
- `3`: acceptable for research, not production
- `4`: production candidate with minor issues
- `5`: strong production quality

## Required Gates

| Gate | Minimum | Hard Fail Condition |
| --- | ---: | --- |
| Garment fidelity | `4.3/5` avg | Logo/text/pattern unreadable or replaced |
| Input quality | `0.85` score and no `critical_issues` | Source capture too blurry/small for detail |
| Human preservation | `4.0/5` avg | Face/body/pose heavily changed |
| Arm/sleeve quality | `4.0/5` avg | Severe sleeve/arm artifacts |
| Web garment robustness | `4.0/5` avg | Fails on background/watermark/cropped garment |
| Runtime latency | `<90s` target, `<60s` preferred | `>180s` on target GPU |
| GPU memory | fits target GPU with headroom | repeated OOM |
| Integration complexity | smoke command works from Makefile | requires manual notebook-only steps |
| License | acceptable or reviewable | clearly incompatible with intended use |

The model passes the quality gate only when all hard fails are avoided and the
weighted score is at least `4.1/5`.

## Weighted Score

| Category | Weight |
| --- | ---: |
| Garment fidelity | `30%` |
| Web garment robustness | `20%` |
| Human preservation | `15%` |
| Arm/sleeve quality | `15%` |
| Runtime and VRAM | `10%` |
| Integration simplicity | `5%` |
| License/commercial path | `5%` |

## Evaluation Result Template

Record one row per model and fixture set:

| Model | GPU | Size | Steps | Latency | Peak VRAM | Fidelity | Robustness | Human | Sleeves | Weighted | Verdict |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Qwen-edit reference | remote/local | varies | varies | varies | varies | TBD | TBD | TBD | TBD | reference | reference only |
| CatVTON | RTX 4000 Ada | `768x1024` | `30` | `34-41s` | `<4GB` | soft | weak | TBD | TBD | fail | pause |
| Leffa conditioned | RTX 4000 Ada | `768x1024` | `30` | TBD | TBD | acceptable | acceptable | acceptable | acceptable | provisional pass | continue evaluation |
| Leffa web garments | RTX 4000 Ada | `768x1024` | `30` | TBD | TBD | soft | mixed | acceptable | acceptable | fail | tune or next candidate |
| Leffa API job | L4 | `768x1024` | `30` | `883s` | TBD | TBD | TBD | TBD | TBD | integration pass, latency fail | use only as minimum smoke |
| Leffa API job | RTX 3090 | `768x1024` effective | `30` | `258s total / 161s core`; `150s` warm follow-up | `5.8GB allocated` | acceptable | acceptable | acceptable | acceptable | provisional pass | viable baseline, optimize latency/input |
| OmniVTON | TBD | `384x512` smoke | `30` | TBD | TBD | TBD | TBD | TBD | TBD | pending | preflight first |

## Candidate ROI Order

### 1. Leffa

Test first.

Reasons:

- Public GitHub repository, model links, demo path, and MIT license.
- Purpose includes virtual try-on and pose transfer.
- The method explicitly targets fine-grained texture distortion, which maps to
  our garment fidelity problem.
- More mature than the other new candidates from an implementation standpoint.
- Likely fastest path to a meaningful RunPod smoke.

Main risk:

- Uses DensePose/SCHP-style preprocessing, so integration may be heavier than
  CatVTON.

Gate for continuing:

- Leffa conditioned smoke passed the first visual review on the fixed smoke
  fixture on June 11, 2026. Background artifacts were removed by deterministic
  person/garment conditioning, garment placement was acceptable, and
  logo/pattern fidelity was materially better than CatVTON.
- Web-style garment fixtures on June 11, 2026 showed good placement and human
  preservation, but garment logos/text/details were still soft. This is a
  current quality-gate failure for production web-downloaded garments.
- Do not build the production API adapter yet. Run one limited detail A/B pass
  first. If logo/text clarity remains soft, keep Leffa as research-only and move
  to the next candidate.

### 2. OmniVTON

Test second if Leffa does not pass.

Reasons:

- Training-free universal VTON direction is aligned with our messy production
  garment input problem.
- Public repository exists.
- Claims focus on garment detail preservation and pose consistency.

Main risks:

- Newer and less mature repository signal.
- Training-free pipelines may have more moving parts or slower runtime.
- The official inference path is not a simple person-image + garment-image
  call. Full VTON requires agnostic masks, garment masks, CLIP-interrogator
  condition JSON files, TAPPS parsing maps, and OpenPose keypoint JSON files.
  This is a major integration risk for a kiosk MVP unless we can automate the
  condition asset generator.

Gate for continuing:

- `make runpod-omnivton-import-check` must pass.
- `make runpod-omnivton-outpainting-smoke` should produce a stage-1 runtime
  output without CUDA/dependency failures.
- Full `vton` quality evaluation should not start until condition assets can be
  generated automatically from the same kiosk person/garment inputs.

### 3. Re-CatVTON

Track, but do not smoke first unless code and weights are clearly available.

Reasons:

- Directly addresses CatVTON weaknesses and claims a better
  efficiency-performance trade-off.
- If released, it could be the most natural successor to our failed CatVTON
  smoke.

Main risk:

- Current availability looks research-first, so implementation ROI is lower
  until code/weights are ready.

### 4. DiT-VTON

Research watchlist only for now.

Reasons:

- Direction is promising for robustness and multi-category product handling.
- Could be strategically important if VTON-specific pipelines remain too weak.

Main risk:

- Lower immediate ROI without a straightforward public local inference path.

## Stop Rules

Stop testing a candidate early when any of these happen:

- It cannot run from a single command after reasonable dependency setup.
- It cannot produce an output on one fixed fixture.
- It fails with repeated OOM on the target GPU class.
- The first quality output is obviously below CatVTON or far below Qwen-edit
  reference quality.
- License blocks expected use.

## Next Implementation Target

Build a Leffa smoke target before any API adapter:

- `make runpod-leffa-smoke-data`
- `make runpod-install-leffa-deps`
- `make runpod-leffa-smoke`

The smoke report should match the existing Qwen/CatVTON report shape:

- model name and version
- source repo path
- person image path
- garment image path
- output path
- latency
- peak VRAM
- preprocessing mode
- success/error
- manual quality score fields

For Leffa, also run the conditioned-input A/B target when the first output is
structurally good but soft:

- `make runpod-vton-condition-smoke-inputs`
- `make runpod-leffa-conditioned-smoke`

For web-style top fixtures, the current local baseline is Leffa with an
upper-body crop. Use the upper-body target before judging Leffa on garment
logo/text fidelity:

- `make runpod-vton-input-quality RUNPOD_VTON_INPUT_GARMENT_CATEGORY=tops`
- `make runpod-leffa-upper-body-web-garment-smoke RUNPOD_WEB_GARMENT_ID=2`
- `make runpod-leffa-upper-body-web-garment-smoke RUNPOD_WEB_GARMENT_ID=3`

The full-body Leffa web-style fixtures are not representative for top garments
when `torso_detail_enough=false`; use them only as a negative control.

If the upper-body crop is still blurry around garment text/logos, treat that as
a model limitation rather than a preprocessing issue.

Production-style API routing:

- Current local Swagger/worker baseline for `tops` is `local_leffa`.
- Enable with `KIOSK_VISUAL_PREVIEW_PROVIDER=local_leffa` after the Leffa repo
  and checkpoints are present on the GPU server.
- The API path applies category-aware input scoring and category-specific
  conditioning before invoking Leffa.
- Swagger/API can now route `bottoms`, `one_pieces`, and `full_outfit` for
  evaluation: `bottoms -> lower_body/full_body`, `one_pieces -> dresses/full_body`,
  `full_outfit -> dresses/full_body`.
- Treat `bottoms`, `one_pieces`, and `full_outfit` as experimental until they
  have their own quality-gate pass.
- RunPod L4 proved the async Swagger/worker/API path end-to-end, but one Leffa
  job took `883s`. Use L4 only as a minimum smoke GPU; use RTX 4000 Ada or
  stronger for practical evaluation.

For OmniVTON, run a cost-safe preflight before any quality run:

- `make runpod-install-omnivton-deps`
- `make runpod-omnivton-import-check`
- `make runpod-omnivton-outpainting-smoke`

Only proceed to `RUNPOD_OMNIVTON_STAGE=vton` after adding or providing TAPPS and
OpenPose condition assets.
