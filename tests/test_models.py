from backeer.models import (
    STEM_PROFILES,
    WorkflowConfig,
)


def test_htdemucs_6s_has_six_stems() -> None:
    profile = STEM_PROFILES["htdemucs_6s"]
    assert len(profile.stems) == 6
    assert "vocals.wav" in profile.stems
    assert "guitar.wav" in profile.stems
    assert "piano.wav" in profile.stems


def test_htdemucs_has_four_stems() -> None:
    profile = STEM_PROFILES["htdemucs"]
    assert len(profile.stems) == 4
    assert set(profile.stems) == {"bass.wav", "drums.wav", "other.wav", "vocals.wav"}


def test_htdemucs_ft_has_four_stems() -> None:
    profile = STEM_PROFILES["htdemucs_ft"]
    assert len(profile.stems) == 4


def test_mdx_extra_has_four_stems() -> None:
    profile = STEM_PROFILES["mdx_extra"]
    assert len(profile.stems) == 4


def test_import_order_matches_stems() -> None:
    for name, profile in STEM_PROFILES.items():
        assert set(profile.import_order) == set(profile.stems), (
            f"{name}: import_order {profile.import_order} != stems {profile.stems}"
        )


def test_import_order_is_correct_length() -> None:
    for name, profile in STEM_PROFILES.items():
        assert len(profile.import_order) == len(profile.stems), (
            f"{name}: import_order length mismatch"
        )


def test_config_get_profile_returns_correct_profile() -> None:
    config = WorkflowConfig(url="x", model="htdemucs")
    profile = config.get_profile()
    assert profile.name == "htdemucs"
    assert profile.stems == ("bass.wav", "drums.wav", "other.wav", "vocals.wav")


def test_config_get_profile_fallback_for_unknown_model() -> None:
    config = WorkflowConfig(url="x", model="my_custom_model")
    profile = config.get_profile()
    assert profile.name == "my_custom_model"
    assert profile.stems == config.expected_stems
    assert profile.import_order == config.expected_stems


def test_stem_profile_display_names() -> None:
    assert STEM_PROFILES["htdemucs_6s"].display_name == "Demucs HT 6-Stem"
    assert STEM_PROFILES["htdemucs"].display_name == "Demucs HT 4-Stem"
    assert STEM_PROFILES["htdemucs_ft"].display_name == "Demucs HT Fine-Tuned 4-Stem"
    assert STEM_PROFILES["mdx_extra"].display_name == "MDX Extra 4-Stem"
