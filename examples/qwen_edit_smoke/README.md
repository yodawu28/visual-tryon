# Qwen Edit Smoke Fixtures

These images are deterministic inputs for local Qwen image-edit runtime smoke
tests on RunPod.

- `front.png`: front-facing person/reference image.
- `garment.webp`: upper-body garment reference image.

Use them to validate model loading, CUDA compatibility, and basic output
generation without running the full kiosk Swagger workflow first:

```bash
make runpod-qwen-edit-smoke-data
make runpod-qwen-edit-smoke
```

The same prepared files are also used by CatVTON smoke tests. The fixture
garment category is `upper`, so the default CatVTON `cloth_type` is `upper`.
Use `RUNPOD_SMOKE_GARMENT_CATEGORY=lower` only when replacing `garment.webp`
with a lower-body fixture.

Only commit synthetic, licensed, or explicitly approved images here. Do not use
private user captures as repository fixtures.
