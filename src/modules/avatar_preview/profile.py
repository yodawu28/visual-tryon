from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

GenderPresentation = Literal["male", "female", "neutral"]
BodyBuild = Literal["slim", "average", "athletic", "plus"]
HeightRange = Literal["short", "average", "tall"]
ShoulderWidth = Literal["narrow", "average", "broad"]
FitPreference = Literal["fitted", "regular", "oversized"]
AvatarPose = Literal["front_relaxed"]
SkinTone = Literal["light", "medium", "tan", "dark", "not_specified"]
AgeBand = Literal["adult", "middle_aged"]
AvatarStyle = Literal["synthetic_person_photo"]


class BodyInputMode(StrEnum):
    BASIC = "basic"
    DETAILED = "detailed"


class GarmentRegion(StrEnum):
    UPPER_BODY = "upper_body"
    LOWER_BODY = "lower_body"
    FULL_BODY = "full_body"


class GarmentType(StrEnum):
    SHIRT = "shirt"
    T_SHIRT = "t_shirt"
    JERSEY = "jersey"
    JACKET = "jacket"
    HOODIE = "hoodie"
    PANTS = "pants"
    SHORTS = "shorts"
    SKIRT = "skirt"
    DRESS = "dress"
    SET = "set"
    FULL_OUTFIT = "full_outfit"
    UNKNOWN = "unknown"


class FashnVtonCategory(StrEnum):
    TOPS = "tops"
    BOTTOMS = "bottoms"
    ONE_PIECES = "one-pieces"


class GarmentSleeveLength(StrEnum):
    SLEEVELESS = "sleeveless"
    SHORT_SLEEVE = "short_sleeve"
    LONG_SLEEVE = "long_sleeve"
    UNKNOWN = "unknown"


class AvatarFraming(StrEnum):
    UPPER_BODY = "upper_body"
    FULL_BODY = "full_body"


class AvatarPreviewQualityMode(StrEnum):
    CREATIVE_PREVIEW = "creative_preview"
    GARMENT_FIDELITY = "garment_fidelity"


class BasicBodyProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    avatar_style: AvatarStyle = "synthetic_person_photo"
    gender_presentation: GenderPresentation
    body_build: BodyBuild
    height_range: HeightRange
    shoulder_width: ShoulderWidth
    fit_preference: FitPreference
    pose: AvatarPose = "front_relaxed"
    skin_tone: SkinTone = "not_specified"
    age_band: AgeBand = "adult"


class DetailedBodyProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    avatar_style: AvatarStyle = "synthetic_person_photo"
    gender_presentation: GenderPresentation
    height_cm: int = Field(ge=120, le=230, strict=True)
    weight_kg: int = Field(ge=30, le=250, strict=True)
    shoulder_width_cm: int = Field(ge=30, le=70, strict=True)
    chest_or_bust_cm: int = Field(ge=60, le=180, strict=True)
    waist_cm: int = Field(ge=45, le=180, strict=True)
    hip_cm: int = Field(ge=60, le=190, strict=True)
    torso_length_cm: int | None = Field(default=None, ge=40, le=90, strict=True)
    sleeve_length_cm: int | None = Field(default=None, ge=40, le=100, strict=True)
    fit_preference: FitPreference
    pose: AvatarPose = "front_relaxed"
    skin_tone: SkinTone = "not_specified"
    age_band: AgeBand = "adult"


class DerivedAvatarProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    avatar_style: AvatarStyle
    gender_presentation: GenderPresentation
    body_build: BodyBuild
    height_range: HeightRange
    shoulder_width: ShoulderWidth
    fit_preference: FitPreference
    pose: AvatarPose
    skin_tone: SkinTone
    age_band: AgeBand


class AvatarProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_mode: BodyInputMode
    basic: BasicBodyProfile | None = None
    detailed: DetailedBodyProfile | None = None

    @model_validator(mode="after")
    def require_matching_input_payload(self) -> "AvatarProfileInput":
        if self.input_mode == BodyInputMode.BASIC:
            if self.basic is None:
                raise ValueError("basic profile is required when input_mode is basic")
            if self.detailed is not None:
                raise ValueError(
                    "detailed profile is not allowed when input_mode is basic"
                )
        if self.input_mode == BodyInputMode.DETAILED:
            if self.detailed is None:
                raise ValueError(
                    "detailed profile is required when input_mode is detailed"
                )
            if self.basic is not None:
                raise ValueError(
                    "basic profile is not allowed when input_mode is detailed"
                )
        return self


def derive_avatar_profile(profile: AvatarProfileInput) -> DerivedAvatarProfile:
    if profile.input_mode == BodyInputMode.BASIC:
        if profile.basic is None:
            raise ValueError("basic profile is required when input_mode is basic")
        return DerivedAvatarProfile(**profile.basic.model_dump())

    if profile.detailed is None:
        raise ValueError("detailed profile is required when input_mode is detailed")

    detailed = profile.detailed
    return DerivedAvatarProfile(
        avatar_style=detailed.avatar_style,
        gender_presentation=detailed.gender_presentation,
        body_build=_derive_body_build(detailed),
        height_range=_derive_height_range(detailed.height_cm),
        shoulder_width=_derive_shoulder_width(detailed.shoulder_width_cm),
        fit_preference=detailed.fit_preference,
        pose=detailed.pose,
        skin_tone=detailed.skin_tone,
        age_band=detailed.age_band,
    )


def report_safe_profile(profile: AvatarProfileInput) -> dict[str, Any]:
    derived_profile = derive_avatar_profile(profile)
    return {
        "input_mode": profile.input_mode.value,
        "derived_profile": derived_profile.model_dump(mode="json"),
    }


def avatar_framing_for_garment_region(
    garment_region: GarmentRegion,
) -> AvatarFraming:
    if garment_region == GarmentRegion.UPPER_BODY:
        return AvatarFraming.UPPER_BODY
    return AvatarFraming.FULL_BODY


def garment_region_for_garment_type(garment_type: GarmentType) -> GarmentRegion:
    if garment_type in {
        GarmentType.SHIRT,
        GarmentType.T_SHIRT,
        GarmentType.JERSEY,
        GarmentType.JACKET,
        GarmentType.HOODIE,
    }:
        return GarmentRegion.UPPER_BODY
    if garment_type in {
        GarmentType.PANTS,
        GarmentType.SHORTS,
        GarmentType.SKIRT,
    }:
        return GarmentRegion.LOWER_BODY
    if garment_type in {
        GarmentType.DRESS,
        GarmentType.SET,
        GarmentType.FULL_OUTFIT,
    }:
        return GarmentRegion.FULL_BODY
    return GarmentRegion.UPPER_BODY


def resolve_garment_region(
    *,
    garment_type: GarmentType | None,
    garment_region: GarmentRegion | None,
) -> GarmentRegion:
    if garment_type is not None and garment_type != GarmentType.UNKNOWN:
        return garment_region_for_garment_type(garment_type)
    return garment_region or GarmentRegion.UPPER_BODY


def idm_vton_category_for_garment(
    *,
    garment_type: GarmentType | None,
    garment_region: GarmentRegion,
) -> str:
    if garment_type == GarmentType.DRESS:
        return "dresses"
    if garment_region == GarmentRegion.LOWER_BODY:
        return "lower_body"
    if garment_region == GarmentRegion.FULL_BODY:
        return "dresses"
    return "upper_body"


def fashn_vton_category_for_garment(
    *,
    garment_type: GarmentType | None,
    garment_region: GarmentRegion,
) -> FashnVtonCategory:
    if garment_type in {GarmentType.DRESS, GarmentType.SET, GarmentType.FULL_OUTFIT}:
        return FashnVtonCategory.ONE_PIECES
    if garment_region == GarmentRegion.LOWER_BODY:
        return FashnVtonCategory.BOTTOMS
    if garment_region == GarmentRegion.FULL_BODY:
        return FashnVtonCategory.ONE_PIECES
    return FashnVtonCategory.TOPS


def default_sleeve_length_for_garment_type(
    garment_type: GarmentType | None,
) -> GarmentSleeveLength:
    if garment_type in {GarmentType.T_SHIRT, GarmentType.JERSEY, GarmentType.SHIRT}:
        return GarmentSleeveLength.SHORT_SLEEVE
    if garment_type in {GarmentType.HOODIE, GarmentType.JACKET}:
        return GarmentSleeveLength.LONG_SLEEVE
    return GarmentSleeveLength.UNKNOWN


def _derive_height_range(height_cm: int) -> HeightRange:
    if height_cm < 165:
        return "short"
    if height_cm >= 180:
        return "tall"
    return "average"


def _derive_shoulder_width(shoulder_width_cm: int) -> ShoulderWidth:
    if shoulder_width_cm < 40:
        return "narrow"
    if shoulder_width_cm >= 47:
        return "broad"
    return "average"


def _derive_body_build(profile: DetailedBodyProfile) -> BodyBuild:
    height_m = profile.height_cm / 100
    bmi = profile.weight_kg / (height_m * height_m)
    shoulder_to_waist = profile.shoulder_width_cm / profile.waist_cm

    if bmi < 19:
        return "slim"
    if bmi >= 30:
        return "plus"
    if shoulder_to_waist >= 0.54 and bmi < 27:
        return "athletic"
    return "average"
