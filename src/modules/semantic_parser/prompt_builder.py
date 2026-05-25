"""
Advanced prompt engineering strategies cho different use cases.
"""

from typing import Dict, Optional
from enum import Enum


class PromptStrategy(str, Enum):
    """Different prompting strategies"""

    DETAILED = "detailed"  # Maximum detail
    BALANCED = "balanced"  # Balance detail vs speed
    FAST = "fast"  # Minimal prompt for speed
    EDIT_SAFE = "edit_safe"  # Preserve image 1, edit clothing only


class PromptBuilder:
    """
    Builder pattern cho flexible prompt engineering.
    """

    PROMPT_VERSIONS = {
        PromptStrategy.DETAILED: "semantic-detailed-v1",
        PromptStrategy.BALANCED: "semantic-balanced-v1",
        PromptStrategy.FAST: "semantic-fast-v1",
        PromptStrategy.EDIT_SAFE: "semantic-edit-safe-v1",
    }

    @classmethod
    def get_prompt_version(cls, strategy: PromptStrategy) -> str:
        try:
            normalized_strategy = PromptStrategy(strategy)
        except ValueError as exc:
            raise ValueError(f"Unsupported prompt strategy: {strategy}") from exc

        return cls.PROMPT_VERSIONS[normalized_strategy]

    @staticmethod
    def build_vto_prompt(
        strategy: PromptStrategy = PromptStrategy.BALANCED,
        focus_areas: Optional[Dict[str, bool]] = None,
    ) -> str:
        """
        Build prompt based on strategy và focus areas.

        Args:
            strategy: Prompting strategy
            focus_areas: Dict như {"fabric": True, "fit": True, "color": False}

        Returns:
            Engineered prompt string
        """

        base_prompt = "Analyze these images for virtual try-on:\n\n"

        if strategy == PromptStrategy.DETAILED:
            # Full detailed analysis
            base_prompt += """
IMAGE 1 (User):
- Body pose: Head angle, shoulder position, torso orientation, arm placement, weight distribution
- Body measurements visible: Shoulder width, torso length, proportions
- Current clothing: Style, fit, material visible
- Background and lighting: Type, direction, intensity

IMAGE 2 (Product):
- Material analysis: Fabric weight, stretch, drape, texture, sheen
- Construction: Seam placement, stitching, structure
- Fit characteristics: How it should sit on shoulders, torso, waist
- Design details: Every visible element
- Color analysis: Primary, secondary, pattern details

Generate inpainting_prompt optimized for photorealistic rendering with:
- Exact lighting replication
- Fabric physics simulation instructions
- Pose-aware clothing placement
- Wrinkle and fold placement
- Shadow and highlight preservation
"""
        elif strategy == PromptStrategy.FAST:
            base_prompt += """
IMAGE 1: Describe body pose briefly.
IMAGE 2: Describe clothing item concisely.
Generate short inpainting_prompt for clothing overlay.
"""
        elif strategy == PromptStrategy.EDIT_SAFE:
            base_prompt += """
IMAGE 1 (Anonymized User Photo):
- Identify the stable details that must remain unchanged: anonymized face area, body shape, pose, hands/arms, camera framing, background, and lighting conditions
- Describe the body pose clearly enough for clothing placement

IMAGE 2 (Garment Reference):
- Describe the garment type and target clothing region (upper body, lower body, or full outfit)
- Describe the garment's silhouette, collar/neckline, sleeve style, colors, logos, stripes, and other visible design details
- Focus on details that should transfer from the product image to the person in IMAGE 1

Generate output for image-editing, not text-to-image generation:
1. clothing_description: Concise garment description grounded in IMAGE 2
2. body_pose: Concise pose description grounded in IMAGE 1
3. inpainting_prompt: An edit-safe instruction that:
   - treats IMAGE 1 as the base photo
   - uses IMAGE 2 only as the garment reference
   - preserves the anonymized face area, person identity, body shape, pose, framing, background, and lighting from IMAGE 1
   - changes only the relevant clothing region
   - preserves garment type, colors, silhouette, and visible design details from IMAGE 2
   - avoids text-to-image phrasing such as "photorealistic rendering", "new image", or pose restatement
"""
        else:  # BALANCED
            base_prompt += """
IMAGE 1 (User): Body pose, proportions, current clothing fit
IMAGE 2 (Product): Fabric type, form, collar/sleeve details, color, key design elements

Generate inpainting_prompt for realistic clothing overlay including lighting, draping, and fit.
"""

        return base_prompt

    @staticmethod
    def build_edit_safe_inpainting_prompt(
        *,
        clothing_description: str,
        body_pose: str,
    ) -> str:
        """
        Compose deterministic edit-safe prompt from VLM analysis.

        VLMs should describe the garment and pose. Backend owns the safety and
        image-preservation constraints so generation behavior stays predictable.
        """
        clothing_description = clothing_description.strip()
        body_pose = body_pose.strip()

        return (
            "Use IMAGE 1 as the base photo. "
            "Use IMAGE 2 only as the garment reference. "
            "Replace only the current upper body clothing with the garment from IMAGE 2: "
            f"{clothing_description}. "
            f"Keep the IMAGE 1 pose unchanged: {body_pose}. "
            "Maintain the anonymized face area, body shape, pose, hands and arms, "
            "camera framing, background, and lighting from IMAGE 1. "
            "Preserve the garment type, colors, neckline or collar, sleeve length, "
            "panels, logos, patches, fabric appearance, silhouette, and visible design "
            "details from IMAGE 2. "
            "Do not create a new person, do not change the pose, do not change the "
            "background, and do not restyle the image. "
            "If uncertain, keep IMAGE 1 unchanged except for the clothing swap."
        )
