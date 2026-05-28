"""
Prompt builders for avatar generation and avatar-based garment preview.
"""

from __future__ import annotations

from src.modules.avatar_preview.profile import DerivedAvatarProfile

AVATAR_PROMPT_VERSION = "avatar-body-profile-v1"
PREVIEW_CONTEXT_PROMPT_VERSION = "avatar-garment-preview-context-v1"


def build_avatar_generation_prompt(profile: DerivedAvatarProfile) -> str:
    body_phrase = _body_phrase(profile)
    skin_tone_phrase = (
        "unspecified skin tone"
        if profile.skin_tone == "not_specified"
        else f"{profile.skin_tone} skin tone"
    )
    age_phrase = "adult" if profile.age_band == "adult" else "middle-aged adult"

    return (
        f"Create a realistic {age_phrase} {profile.gender_presentation} "
        f"personalized avatar mannequin with {body_phrase}. "
        f"Use {skin_tone_phrase}. "
        "Use a neutral studio background, front relaxed pose, natural posture, "
        "and realistic but non-identifying body proportions. "
        "The face must be a neutral anonymized face area with a blurred or "
        "featureless face. "
        "Do not create a face resembling a real person. "
        "Do not include brand logos, text, accessories, or garment-specific "
        "graphics. "
        "Keep camera framing stable and suitable for upper-body garment preview."
    )


def build_avatar_preview_context_prompt(profile: DerivedAvatarProfile) -> str:
    return (
        "Use the first image as a personalized avatar mannequin, not as a real "
        "user photo. Use the second image only as the garment reference. "
        f"The avatar has {_body_phrase(profile)} and prefers a "
        f"{profile.fit_preference} clothing fit. "
        "Apply the garment to the avatar in a plausible creative outfit preview. "
        "Keep the avatar body proportions, pose, neutral non-identifying face, "
        "camera framing, and background stable. "
        "Preserve garment color, neckline, sleeve length, logos, text, stripes, "
        "panels, trims, and visible design details as much as the model allows."
    )


def _body_phrase(profile: DerivedAvatarProfile) -> str:
    shoulder_phrase = {
        "narrow": "narrow shoulders",
        "average": "average shoulder width",
        "broad": "broad shoulders",
    }[profile.shoulder_width]
    return (
        f"{profile.height_range} height range, {profile.body_build} build, "
        f"and {shoulder_phrase}"
    )
