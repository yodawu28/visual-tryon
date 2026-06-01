import pytest
from pydantic import ValidationError

from src.modules.avatar_preview.profile import (
    AvatarProfileInput,
    BasicBodyProfile,
    BodyInputMode,
    DetailedBodyProfile,
    FashnVtonCategory,
    GarmentRegion,
    GarmentSleeveLength,
    GarmentType,
    default_sleeve_length_for_garment_type,
    derive_avatar_profile,
    fashn_vton_category_for_garment,
    garment_region_for_garment_type,
    idm_vton_category_for_garment,
    report_safe_profile,
    resolve_garment_region,
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
        "avatar_style": "synthetic_person_photo",
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
    assert report_payload["derived_profile"]["avatar_style"] == "synthetic_person_photo"
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


def test_garment_type_maps_to_region():
    assert (
        garment_region_for_garment_type(GarmentType.JERSEY) == GarmentRegion.UPPER_BODY
    )
    assert (
        garment_region_for_garment_type(GarmentType.PANTS) == GarmentRegion.LOWER_BODY
    )
    assert garment_region_for_garment_type(GarmentType.DRESS) == GarmentRegion.FULL_BODY


def test_garment_type_overrides_fallback_region():
    assert (
        resolve_garment_region(
            garment_type=GarmentType.SHORTS,
            garment_region=GarmentRegion.UPPER_BODY,
        )
        == GarmentRegion.LOWER_BODY
    )
    assert (
        resolve_garment_region(
            garment_type=GarmentType.UNKNOWN,
            garment_region=GarmentRegion.FULL_BODY,
        )
        == GarmentRegion.FULL_BODY
    )


def test_idm_vton_category_maps_supported_garments():
    assert (
        idm_vton_category_for_garment(
            garment_type=GarmentType.JERSEY,
            garment_region=GarmentRegion.UPPER_BODY,
        )
        == "upper_body"
    )
    assert (
        idm_vton_category_for_garment(
            garment_type=GarmentType.SHORTS,
            garment_region=GarmentRegion.LOWER_BODY,
        )
        == "lower_body"
    )
    assert (
        idm_vton_category_for_garment(
            garment_type=GarmentType.DRESS,
            garment_region=GarmentRegion.FULL_BODY,
        )
        == "dresses"
    )


def test_fashn_vton_category_maps_supported_garments():
    assert (
        fashn_vton_category_for_garment(
            garment_type=GarmentType.JERSEY,
            garment_region=GarmentRegion.UPPER_BODY,
        )
        == FashnVtonCategory.TOPS
    )
    assert (
        fashn_vton_category_for_garment(
            garment_type=GarmentType.SHORTS,
            garment_region=GarmentRegion.LOWER_BODY,
        )
        == FashnVtonCategory.BOTTOMS
    )
    assert (
        fashn_vton_category_for_garment(
            garment_type=GarmentType.DRESS,
            garment_region=GarmentRegion.FULL_BODY,
        )
        == FashnVtonCategory.ONE_PIECES
    )


def test_default_sleeve_length_maps_upper_body_garments():
    assert (
        default_sleeve_length_for_garment_type(GarmentType.JERSEY)
        == GarmentSleeveLength.SHORT_SLEEVE
    )
    assert (
        default_sleeve_length_for_garment_type(GarmentType.JACKET)
        == GarmentSleeveLength.LONG_SLEEVE
    )
    assert (
        default_sleeve_length_for_garment_type(GarmentType.SHORTS)
        == GarmentSleeveLength.UNKNOWN
    )
