"""
Download required ML models.
"""

import insightface
from insightface.app import FaceAnalysis
from pathlib import Path
import sys


def download_models():
    print("📥 Downloading InsightFace models...")

    try:
        # This will auto-download buffalo_l model
        print("   Downloading buffalo_l model...")
        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=-1, det_size=(640, 640))
        print("   ✅ buffalo_l model downloaded")
    except Exception as e:
        print(f"   ❌ Failed to download buffalo_l: {e}")
        return False

    try:
        # Download inswapper model
        print("   Downloading inswapper model...")
        insightface.model_zoo.get_model(
            "inswapper_128.onnx", download=True, download_zip=True
        )
        print("   ✅ inswapper_128 model downloaded")
    except Exception as e:
        print(f"   ⚠️  Failed to download inswapper: {e}")
        print("   Fallback anonymization (blur) will be used.")

    model_dir = Path.home() / ".insightface" / "models"
    print(f"\n📁 Models saved to: {model_dir}")
    return True


if __name__ == "__main__":
    success = download_models()
    sys.exit(0 if success else 1)
