"""
Prompt builders for avatar generation and avatar-based garment preview.
"""

from __future__ import annotations

from src.modules.avatar_preview.profile import (
    AvatarFraming,
    DerivedAvatarProfile,
    GarmentRegion,
    GarmentSleeveLength,
    GarmentType,
)

AVATAR_PROMPT_VERSION = "avatar-body-profile-v4"
PREVIEW_CONTEXT_PROMPT_VERSION = "avatar-garment-preview-context-v4"


def build_avatar_generation_prompt(
    profile: DerivedAvatarProfile,
    *,
    avatar_framing: AvatarFraming = AvatarFraming.UPPER_BODY,
    garment_region: GarmentRegion = GarmentRegion.UPPER_BODY,
    garment_sleeve_length: GarmentSleeveLength = GarmentSleeveLength.UNKNOWN,
) -> str:
    body_phrase = _body_phrase(profile)
    skin_tone_phrase = (
        "unspecified skin tone"
        if profile.skin_tone == "not_specified"
        else f"{profile.skin_tone} skin tone"
    )
    age_phrase = "adult" if profile.age_band == "adult" else "middle-aged adult"

    return (
        f"Create a photorealistic synthetic human model of an {age_phrase} "
        f"{profile.gender_presentation} person with {body_phrase}. "
        f"Use {skin_tone_phrase}. "
        "Use a clean neutral studio background, front relaxed pose, natural "
        "posture, and realistic but non-identifying body proportions. "
        "The result must look like a real camera photo of a fictional synthetic "
        "human model with natural skin texture, not a plastic mannequin, not a "
        "cartoon, not an illustration, not a sketch, and not a stick figure. "
        "The face must be softly blurred and non-identifying, with no "
        "recognizable facial details. "
        "Do not create a face resembling a real person or the user. "
        "Do not include brand logos, text, accessories, or garment-specific "
        "graphics. "
        f"{_generation_framing_phrase(avatar_framing, garment_region, garment_sleeve_length)}"
    )


def build_avatar_preview_context_prompt(
    profile: DerivedAvatarProfile,
    *,
    avatar_framing: AvatarFraming = AvatarFraming.UPPER_BODY,
    garment_region: GarmentRegion = GarmentRegion.UPPER_BODY,
    garment_type: GarmentType | None = None,
) -> str:
    return (
        "Edit only the first image. Return only the edited first image, not a "
        "side-by-side comparison, not a collage, and not both input images. "
        f"Use the first image as a {_preview_avatar_phrase(avatar_framing)}, "
        "not as a real user photo, not a mannequin, not a stick figure, not a "
        "cartoon, and not an illustration. Use the second image only as the "
        "garment reference. "
        f"The avatar has {_body_phrase(profile)} and prefers a "
        f"{profile.fit_preference} clothing fit. "
        f"{_preview_framing_phrase(avatar_framing, garment_region, garment_type)}"
        "Keep the avatar body proportions, pose, neutral non-identifying face, "
        "camera framing, and background stable. "
        "Preserve garment color, neckline, sleeve length, logos, text, stripes, "
        "panels, trims, and visible design details as much as the model allows."
    )


def _generation_framing_phrase(
    avatar_framing: AvatarFraming,
    garment_region: GarmentRegion,
    garment_sleeve_length: GarmentSleeveLength,
) -> str:
    if avatar_framing == AvatarFraming.FULL_BODY:
        if garment_region == GarmentRegion.UPPER_BODY:
            return (
                "Use simple plain fitted base clothing with no graphics: "
                f"{_base_top_phrase(garment_sleeve_length)} and plain neutral "
                "shorts. Frame the avatar as a full-body photo from head to "
                "shoes with hips visible, legs fully visible, and feet fully "
                "visible. Keep arms relaxed and slightly away from the torso, "
                "with hands not covering the shirt area. "
            )
        return (
            "Use simple plain fitted base clothing with no graphics: a plain "
            "neutral fitted top and plain neutral shorts. Frame the avatar as a "
            "full-body photo from head to shoes with hips visible, legs fully "
            "visible, and feet fully visible. Keep arms slightly away from the "
            "torso so pants, shorts, or full outfits are not blocked. "
        )
    return (
        "Use simple plain fitted base clothing with no graphics. Frame the "
        "avatar as an upper-body photo suitable for shirt and jacket preview. "
    )


def _base_top_phrase(garment_sleeve_length: GarmentSleeveLength) -> str:
    if garment_sleeve_length == GarmentSleeveLength.SLEEVELESS:
        return (
            "a plain neutral sleeveless fitted top with bare shoulders and arms "
            "visible"
        )
    if garment_sleeve_length == GarmentSleeveLength.SHORT_SLEEVE:
        return (
            "a plain neutral short-sleeve fitted t-shirt with bare forearms "
            "visible, no long sleeves, no layered undershirt, and no jacket"
        )
    if garment_sleeve_length == GarmentSleeveLength.LONG_SLEEVE:
        return "a plain neutral long-sleeve fitted top"
    return "a plain neutral fitted top"


def _preview_avatar_phrase(avatar_framing: AvatarFraming) -> str:
    if avatar_framing == AvatarFraming.FULL_BODY:
        return "full-body synthetic human avatar"
    return "photorealistic synthetic human avatar"


def _preview_framing_phrase(
    avatar_framing: AvatarFraming,
    garment_region: GarmentRegion,
    garment_type: GarmentType | None,
) -> str:
    garment_label = _garment_type_label(garment_type, garment_region)
    if garment_region == GarmentRegion.UPPER_BODY:
        if avatar_framing == AvatarFraming.FULL_BODY:
            return (
                f"Apply the {garment_label} to the upper body of the full-body "
                "avatar only. Keep "
                "the legs and lower-body clothing visible and stable. "
            )
        return (
            f"Apply the {garment_label} to the avatar's upper body only. "
            "Keep pants, shorts, skirt, legs, and shoes unchanged. "
        )
    if garment_region == GarmentRegion.LOWER_BODY:
        return (
            f"Apply the {garment_label} to the avatar's lower body only, with "
            "legs and hips visible. Keep shirt, torso, arms, and shoes "
            "unchanged unless the garment naturally covers them. "
        )
    return (
        f"Apply the {garment_label} to the avatar in a plausible full outfit "
        "preview, with torso, hips, and legs visible. Replace only the outfit "
        "areas needed by the garment reference. "
    )


def _garment_type_label(
    garment_type: GarmentType | None,
    garment_region: GarmentRegion,
) -> str:
    labels = {
        GarmentType.SHIRT: "shirt",
        GarmentType.T_SHIRT: "t-shirt",
        GarmentType.JERSEY: "sports jersey",
        GarmentType.JACKET: "jacket",
        GarmentType.HOODIE: "hoodie",
        GarmentType.PANTS: "pants",
        GarmentType.SHORTS: "shorts",
        GarmentType.SKIRT: "skirt",
        GarmentType.DRESS: "dress",
        GarmentType.SET: "matching top and bottom set",
        GarmentType.FULL_OUTFIT: "full outfit",
    }
    if garment_type in labels:
        return labels[garment_type]
    if garment_region == GarmentRegion.LOWER_BODY:
        return "lower-body garment"
    if garment_region == GarmentRegion.FULL_BODY:
        return "full outfit garment"
    return "upper-body garment"


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
