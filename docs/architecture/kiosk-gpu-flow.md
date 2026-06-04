# Kiosk GPU Try-On Flow

This branch introduces the first production boundary for a kiosk-style try-on
deployment. The flow stays sequential, but avatar and generated visual preview
steps are optional. The fit path must not call image generation unless the user
explicitly asks for a visual preview.

## Flow

```mermaid
flowchart LR
    A[Upload or select garment] --> B[Create kiosk session]
    A --> C{User wants avatar preview?}
    C -- Yes --> D[Avatar preview flow]
    C -- No --> B
    D --> B
    B --> E[Capture front webcam image]
    E --> F[Optional side capture]
    F --> G[Pose and quality analysis]
    G --> H[Fit Intelligence]
    H --> I[Size and fit recommendation]
    I --> J{User wants visual preview?}
    J -- Yes --> K[Qwen visual preview]
    J -- No --> L[Result review]
    K --> L
```

## Current API Boundary

The current implementation covers garment registration, direct or avatar-assisted
session creation, capture analysis, Fit Intelligence, and optional visual
preview:

- `POST /api/v1/kiosk/garments`
  Uploads a garment image and stores its local path in the garment registry.
- `POST /api/v1/kiosk/sessions`
  Creates a session. Avatar cache fields are optional.
- `GET /api/v1/kiosk/sessions/{session_id}`
  Loads the current kiosk session state.
- `POST /api/v1/kiosk/sessions/{session_id}/captures`
  Stores front and optional side webcam captures for the next try-on stage.
- `POST /api/v1/kiosk/sessions/{session_id}/captures/analyze`
  Runs MediaPipe-based capture quality and pose checks.
- `POST /api/v1/kiosk/sessions/{session_id}/fit/analyze`
  Runs Fit Intelligence. This endpoint does not call Qwen or generate images.
- `POST /api/v1/kiosk/sessions/{session_id}/visual-preview`
  Runs optional Qwen-style visual preview only when the user requests it.
- `POST /api/v1/kiosk/sessions/{session_id}/try-on`
  Deprecated compatibility alias for `visual-preview`.

## Deployment Shape

```mermaid
flowchart TB
    subgraph Kiosk[Physical kiosk]
        UI[Touch screen UI]
        CAM[Webcam]
    end

    subgraph GPU[GPU server package]
        API[FastAPI service]
        CACHE[File/KV cache]
        FIT[Fit Intelligence]
        QWEN[Optional multimodal analyzer]
        GEN[Optional image generation provider]
    end

    UI --> API
    CAM --> API
    API --> CACHE
    API --> FIT
    API --> QWEN
    API --> GEN
```

## Intentional Scope

Fit Intelligence is the primary sizing path. Visual preview is a separate,
optional UX path and must not be treated as measurement truth. The current fit
implementation is still a skeleton and should be extended with real measurement
estimation and size-chart scoring before production size recommendations.
