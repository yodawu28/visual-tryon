# Visual Fitting Room UI

Static user-facing kiosk app for the FastAPI kiosk workflow.

Run the backend first:

```bash
API_PROFILE=kiosk make run
```

Serve the UI:

```bash
make ui-kiosk
```

Open `http://127.0.0.1:5173`.

Shopper capture supports both file upload and browser camera capture. Camera
capture requires a secure browser context, so use `localhost`, HTTPS, or a
trusted tunnel/proxy when testing from a phone.

The app calls the current Swagger API surface:

- `GET /api/v1/readiness`
- `GET /api/v1/kiosk/size-charts`
- `POST /api/v1/kiosk/garments`
- `POST /api/v1/kiosk/sessions`
- `POST /api/v1/kiosk/sessions/{session_id}/captures`
- `POST /api/v1/kiosk/sessions/{session_id}/captures/analyze`
- `POST /api/v1/kiosk/sessions/{session_id}/fit/analyze`
- Optional: `POST /api/v1/kiosk/sessions/{session_id}/visual-preview/jobs`
- Optional: `GET /api/v1/kiosk/jobs/{job_id}`

The UI automatically runs capture quality analysis after shopper photos are uploaded. The separate capture analysis endpoint remains visible for Swagger/debug workflows and the UI keeps a recheck action for retakes.

When photos are captured through the browser camera, the UI runs a guided
capture sequence:

- One `Guided Capture` action takes front and side photos in order. Separate
  front/side buttons remain available for retakes.
- 5-second countdown so the shopper can hold still.
- Scan overlay while the browser captures a short burst.
- Lightweight frame selection using brightness, edge/sharpness, and resolution
  signals.

The upload includes `capture_source=guided_mobile_web` and optional
`capture_metadata_json` keyed by `front`/`side`. The backend stores the selected
frame score and burst metadata in the session and echoes it in capture
analysis/fit debug signals.

This is input-quality provenance only; it does not convert MediaPipe landmarks
into calibrated measurements. Fit Intelligence still keeps overall confidence
conservative and reports target-confidence blockers until measurements and
capture quality are strong enough.

Fit results display `Size match` separately from `Data confidence`. Size match
reflects deterministic chart fit, while data confidence reflects measurement
basis, capture quality, garment input quality, and size-chart availability.

Capture analysis is category-aware. For `tops`, the API focuses on upper-body
readiness and does not fail the shopper capture only because feet are missing.
For `bottoms`, `one_pieces`, and `full_outfit`, lower-body/full-body visibility
still matters.

Visual preview responses now include `output_quality_gate` metadata for Leffa
outputs. The gate warns on decode, size, sharpness, or brightness issues but
does not block the preview job during the demo baseline.
