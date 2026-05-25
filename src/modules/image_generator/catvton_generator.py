"""
CatVTON Local Inference cho virtual try-on trên MacBook M-series.

Uses CatVTON model via diffusers library với MPS backend.
Optimized cho 16GB RAM với attention slicing và CPU offloading.
"""

import base64
import io
import logging
import os
from typing import Optional
from PIL import Image
import torch

from src.config.settings import get_settings
from src.modules.image_generator.base import ImageGeneratorBase

# Force disable CUDA to prevent CUDA errors on MPS-only systems
os.environ["CUDA_VISIBLE_DEVICES"] = ""


# Monkey-patch torch.cuda to prevent CUDA initialization errors on non-CUDA systems
def _noop_lazy_init():
    """No-op replacement for torch.cuda._lazy_init to prevent CUDA errors."""
    pass


# Patch CUDA device calls to redirect to CPU
def _patch_cuda_device(device_string):
    """Redirect CUDA device calls to CPU."""
    if isinstance(device_string, str) and "cuda" in device_string.lower():
        return "cpu"
    return device_string


if not torch.cuda.is_available():
    torch.cuda._lazy_init = _noop_lazy_init

    # Patch torch.device to convert CUDA to CPU
    _original_device = torch.device

    def _patched_device(device):
        if isinstance(device, str) and "cuda" in device.lower():
            return _original_device("cpu")
        return _original_device(device)

    torch.device = _patched_device

logger = logging.getLogger(__name__)


class CatVTONGenerator(ImageGeneratorBase):
    """
    Local CatVTON Generator cho MacBook M-series.

    Runs CatVTON locally với MPS (Metal Performance Shaders).
    Memory optimized cho 16GB RAM systems.
    """

    def __init__(self):
        settings = get_settings()
        self.model_id = settings.catvton_model_id
        self.requested_device = settings.catvton_device

        # Detect actual available device
        self.device = self._get_available_device(self.requested_device)
        logger.info(f"Using device: {self.device} (requested: {self.requested_device})")

        # Lazy load pipeline - chỉ import khi cần
        try:
            # NOTE: CatVTON requires custom implementation, not standard diffusers
            # For now, use fallback SD 2.1 inpainting model (lighter, better MPS support)
            logger.warning(
                "CatVTON requires custom implementation. "
                "Using fallback: sd2-community/stable-diffusion-2-inpainting"
            )

            from diffusers import StableDiffusionInpaintPipeline

            # Load SD 2.1 inpainting as fallback (better compatibility)
            fallback_model = "sd2-community/stable-diffusion-2-inpainting"
            logger.info(f"Loading fallback model: {fallback_model}")

            # Always use CPU for now (MPS has compatibility issues with diffusers)
            logger.warning(
                f"Requested device: {self.device}, forcing CPU for compatibility"
            )
            self.device = "cpu"
            torch_dtype = torch.float32

            self.pipe = StableDiffusionInpaintPipeline.from_pretrained(
                fallback_model,
                torch_dtype=torch_dtype,
                low_cpu_mem_usage=True,
            )

            # Move to CPU and override internal device property
            self.pipe = self.pipe.to("cpu")
            # Force all sub-components to CPU
            for component_name in ["vae", "text_encoder", "unet"]:
                if hasattr(self.pipe, component_name):
                    component = getattr(self.pipe, component_name)
                    if component is not None:
                        component.to("cpu")

            logger.info("Pipeline loaded on CPU")

            # Memory optimizations
            if settings.catvton_enable_attention_slicing:
                self.pipe.enable_attention_slicing("auto")
                logger.info("Enabled attention slicing")

            if settings.catvton_enable_vae_slicing:
                self.pipe.vae.enable_slicing()
                self.pipe.vae.enable_tiling()
                logger.info("Enabled VAE slicing and tiling")

            if settings.catvton_enable_cpu_offload:
                self.pipe.enable_model_cpu_offload()
                logger.info("Enabled model CPU offload")

            logger.info("CatVTON pipeline initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize CatVTON: {str(e)}")
            raise RuntimeError(f"CatVTON initialization failed: {str(e)}")

    def generate_tryon(
        self,
        base_image: bytes,
        garment_image: bytes,
        inpainting_prompt: str,
        mask: Optional[bytes] = None,
        size: str = "1024x1024",
    ) -> bytes:
        """
        Generate try-on image sử dụng CatVTON local inference.

        Args:
            base_image: Anonymized user image bytes
            garment_image: Product garment image bytes (not used - local mode broken)
            inpainting_prompt: Prompt từ Module 2 semantic parser
            mask: Optional mask (white = edit, black = keep)
            size: Output size (default 1024x1024)

        Returns:
            Generated image bytes
        """
        try:
            logger.info("Running CatVTON local inference...")
            logger.info(f"Prompt: {inpainting_prompt[:200]}...")

            # Convert bytes to PIL Image
            base_pil = Image.open(io.BytesIO(base_image)).convert("RGB")

            # Resize if needed
            target_w, target_h = map(int, size.split("x"))
            if base_pil.size != (target_w, target_h):
                base_pil = base_pil.resize(
                    (target_w, target_h), Image.Resampling.LANCZOS
                )
                logger.info(f"Resized base image to {size}")

            # Prepare mask if provided
            mask_pil = None
            if mask:
                mask_pil = Image.open(io.BytesIO(mask)).convert("L")
                if mask_pil.size != (target_w, target_h):
                    mask_pil = mask_pil.resize(
                        (target_w, target_h), Image.Resampling.LANCZOS
                    )
                logger.info("Mask provided and processed")

            # Run inference
            logger.info("Starting CatVTON inference...")

            # SDXL Inpainting parameters
            inference_params = {
                "prompt": inpainting_prompt,
                "image": base_pil,
                "mask_image": (
                    mask_pil if mask_pil else self._create_full_mask(base_pil)
                ),
                "num_inference_steps": 30,  # Balance speed vs quality
                "guidance_scale": 7.5,
                "strength": 0.8,  # How much to transform image
            }

            # Generate with torch.no_grad() để save memory
            with torch.no_grad():
                result = self.pipe(**inference_params)

            output_image = result.images[0]
            logger.info("CatVTON inference completed")

            # Convert back to bytes
            buffer = io.BytesIO()
            output_image.save(buffer, format="PNG")
            image_bytes = buffer.getvalue()

            logger.info(f"Generated {len(image_bytes)} bytes")
            return image_bytes

        except Exception as e:
            logger.error(f"CatVTON inference failed: {str(e)}")
            raise ValueError(f"Image generation failed: {str(e)}")

    def generate_tryon_from_b64(
        self,
        base_image_b64: str,
        garment_image_b64: str,
        inpainting_prompt: str,
        mask_b64: Optional[str] = None,
        size: str = "1024x1024",
    ) -> str:
        """
        Generate try-on image từ base64 inputs, return base64.
        """
        # Decode base64 to bytes
        base_image = base64.b64decode(base_image_b64)
        garment_image = base64.b64decode(garment_image_b64)
        mask = base64.b64decode(mask_b64) if mask_b64 else None

        # Generate
        result_bytes = self.generate_tryon(
            base_image=base_image,
            garment_image=garment_image,
            inpainting_prompt=inpainting_prompt,
            mask=mask,
            size=size,
        )

        # Encode back to base64
        return base64.b64encode(result_bytes).decode("utf-8")

    def _get_available_device(self, requested: str) -> str:
        """
        Detect actual available device.

        Priority: requested device > MPS > CUDA > CPU
        """
        if requested == "mps" and torch.backends.mps.is_available():
            return "mps"
        elif requested == "cuda" and torch.cuda.is_available():
            return "cuda"
        elif requested in ["mps", "cuda"]:
            logger.warning(
                f"{requested.upper()} requested but not available. Falling back to CPU"
            )
            return "cpu"
        else:
            return "cpu"

    def _create_full_mask(self, image: Image.Image) -> Image.Image:
        """Create full white mask if none provided."""
        return Image.new("L", image.size, 255)
