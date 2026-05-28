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


class BodyInputMode(StrEnum):
    BASIC = "basic"
    DETAILED = "detailed"


class BasicBodyProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
