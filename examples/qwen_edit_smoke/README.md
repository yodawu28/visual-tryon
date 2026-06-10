# Qwen Edit Smoke Fixtures

These images are deterministic inputs for local Qwen image-edit runtime smoke
tests on RunPod.

- `front.png`: front-facing person/reference image.
- `garment.webp`: garment reference image.

Use them to validate model loading, CUDA compatibility, and basic output
generation without running the full kiosk Swagger workflow first:

```bash
make runpod-qwen-edit-smoke-data
make runpod-qwen-edit-smoke
```

Only commit synthetic, licensed, or explicitly approved images here. Do not use
private user captures as repository fixtures.
