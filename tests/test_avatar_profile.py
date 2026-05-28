import pytest
from pydantic import ValidationError

from src.modules.avatar_preview.profile import (
    AvatarProfileInput,
    BasicBodyProfile,
    BodyInputMode,
    DetailedBodyProfile,
    derive_avatar_profile,
    report_safe_profile,
)


def _basic_profile() -> BasicBodyProfile:
    return BasicBodyProfile(
        gender_presentation="male",
        body_build="athletic",
        height_range="tall",
        shoulder_width="broad",
        fit_preference="regular",
        pose="front_relaxed",
        skin_tone="tan",
        age_band="adult",
    )


def _detailed_profile() -> DetailedBodyProfile:
    return DetailedBodyProfile(
        gender_presentation="male",
        height_cm=182,
        weight_kg=84,
        shoulder_width_cm=49,
        chest_or_bust_cm=104,
        waist_cm=86,
        hip_cm=98,
        fit_preference="regular",
        pose="front_relaxed",
        skin_tone="medium",
        age_band="adult",
    )


def test_basic_body_profile_derives_report_safe_profile():
    profile = AvatarProfileInput(
        input_mode=BodyInputMode.BASIC,
        basic=_basic_profile(),
    )

    derived = derive_avatar_profile(profile)

    assert derived.model_dump(mode="json") == {
        "gender_presentation": "male",
        "body_build": "athletic",
        "height_range": "tall",
        "shoulder_width": "broad",
        "fit_preference": "regular",
        "pose": "front_relaxed",
        "skin_tone": "tan",
        "age_band": "adult",
    }
    assert report_safe_profile(profile) == {
        "input_mode": "basic",
        "derived_profile": derived.model_dump(mode="json"),
    }


def test_detailed_measurements_are_not_returned_in_report_safe_profile():
    profile = AvatarProfileInput(
        input_mode=BodyInputMode.DETAILED,
        detailed=_detailed_profile(),
    )

    report_payload = report_safe_profile(profile)
    serialized = str(report_payload)

    assert report_payload["input_mode"] == "detailed"
    assert report_payload["derived_profile"]["height_range"] == "tall"
    assert report_payload["derived_profile"]["shoulder_width"] == "broad"
    assert "182" not in serialized
    assert "84" not in serialized
    assert "104" not in serialized
    assert "86" not in serialized
    assert "height_cm" not in serialized
    assert "weight_kg" not in serialized
    assert "shoulder_width_cm" not in serialized
    assert "chest_or_bust_cm" not in serialized
    assert "waist_cm" not in serialized
    assert "hip_cm" not in serialized


def test_profile_requires_matching_input_payload():
    with pytest.raises(ValidationError, match="basic profile is required"):
        AvatarProfileInput(input_mode=BodyInputMode.BASIC)

    with pytest.raises(ValidationError, match="detailed profile is required"):
        AvatarProfileInput(input_mode=BodyInputMode.DETAILED)


def test_basic_profile_rejects_detailed_payload():
    with pytest.raises(ValidationError, match="detailed profile is not allowed"):
        AvatarProfileInput(
            input_mode=BodyInputMode.BASIC,
            basic=_basic_profile(),
            detailed=_detailed_profile(),
        )


def test_detailed_profile_rejects_basic_payload():
    with pytest.raises(ValidationError, match="basic profile is not allowed"):
        AvatarProfileInput(
            input_mode=BodyInputMode.DETAILED,
            basic=_basic_profile(),
            detailed=_detailed_profile(),
        )


def test_detailed_measurements_validate_reasonable_ranges():
    with pytest.raises(ValidationError):
        DetailedBodyProfile(
            gender_presentation="male",
            height_cm=80,
            weight_kg=84,
            shoulder_width_cm=49,
            chest_or_bust_cm=104,
            waist_cm=86,
            hip_cm=98,
            fit_preference="regular",
            pose="front_relaxed",
        )


def test_detailed_measurements_do_not_coerce_strings():
    with pytest.raises(ValidationError):
        DetailedBodyProfile(
            gender_presentation="male",
            height_cm="182",
            weight_kg=84,
            shoulder_width_cm=49,
            chest_or_bust_cm=104,
            waist_cm=86,
            hip_cm=98,
            fit_preference="regular",
            pose="front_relaxed",
        )
