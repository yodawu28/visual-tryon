"""
Backward-compatible import path for the Qwen fast preview generator.
"""

from src.modules.image_generator.replicate_preview_generator import QwenFastGenerator

__all__ = ["QwenFastGenerator"]
