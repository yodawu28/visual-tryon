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

For web-style garment fixtures, compare the baseline and detail pass without
overwriting outputs:

- `make runpod-leffa-web-garment-smoke RUNPOD_WEB_GARMENT_ID=2`
- `make runpod-leffa-web-garment-detail-smoke RUNPOD_WEB_GARMENT_ID=2`
- `make runpod-leffa-web-garment-smoke RUNPOD_WEB_GARMENT_ID=3`
- `make runpod-leffa-web-garment-detail-smoke RUNPOD_WEB_GARMENT_ID=3`

If the detail pass is still blurry around garment text/logos, treat that as a
model limitation rather than a preprocessing issue.
