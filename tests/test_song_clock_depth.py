"""Source clock captions, exact branch windows and uncertainty at a qi boundary."""

import hashlib
import json
from fractions import Fraction
from pathlib import Path

import pytest

import fatebridge.core.song_clock as clock

ROOT = Path(__file__).parent / "fixtures/song_clock_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text())
PROFILES = [p["profile"] for p in REFERENCE["literal_clock_rules"]]


@pytest.mark.parametrize("row", REFERENCE["literal_clock_rules"])
def test_printed_multipliers_and_divisors_normalize_to_twelve_chen_and_hundred_ke(row):
    r = clock.source_clock_from_fraction(
        profile_id=row["profile"], numerator=0, denominator=1
    )
    for key, value in r["source_clock_constants"].items():
        assert value == row[key]
    assert r["chen_per_day"] == {"numerator": 12, "denominator": 1}
    assert r["ke_per_day"] == {"numerator": 100, "denominator": 1}
    assert r["normalized_chu_zheng"]["label"] == "子正初刻"
    assert r["actual_historical_birth_clock_established"] is False
    assert "no_modern_minutes_or_UTC" in r["time_frame"]


@pytest.mark.parametrize("row", REFERENCE["printed_clock_captions"])
def test_two_reused_mei_calculations_match_their_printed_clock_captions(row):
    r = clock.source_term_clock(
        profile_id=row["profile"],
        accumulated_years=row["prior_worked_accumulated"],
        term_index=0,
    )
    c = r["source_clock"]
    assert c["source_day_fraction"] == row["source_fraction"]
    expected = (
        row["branch"],
        row["phase"],
        row["whole_ke_after_phase"],
        row["ke_fraction_after_phase"],
    )
    actual = c["normalized_chu_zheng"]
    assert (
        actual["branch"],
        actual["phase"],
        actual["whole_ke"],
        actual["remaining_ke_fraction"],
    ) == expected
    assert r["source_term"]["ganzhi_day"] == row["same_source_day_name"]
    assert c["source_day_name_advanced_at_zi_chu"] is False


@pytest.mark.parametrize("row", REFERENCE["derived_term_clock_probes"])
def test_three_derived_clock_probes_keep_exact_remainders(row):
    r = clock.source_term_clock(
        profile_id=row["profile"],
        accumulated_years=row["accumulated"],
        term_index=row["term_index"],
    )
    assert r["source_clock"]["source_day_fraction"] == row["fraction"]
    c = r["source_clock"]["normalized_chu_zheng"]
    assert (c["branch"], c["phase"], c["whole_ke"], c["remaining_ke_fraction"]) == (
        row["branch"],
        row["phase"],
        row["whole_ke_after_phase"],
        row["ke_fraction_after_phase"],
    )


@pytest.mark.parametrize("profile", PROFILES)
def test_half_chen_boundaries_do_not_round_early_or_advance_the_day_at_zi_chu(profile):
    labels = [
        "子正",
        "丑初",
        "丑正",
        "寅初",
        "寅正",
        "卯初",
        "卯正",
        "辰初",
        "辰正",
        "巳初",
        "巳正",
        "午初",
        "午正",
        "未初",
        "未正",
        "申初",
        "申正",
        "酉初",
        "酉正",
        "戌初",
        "戌正",
        "亥初",
        "亥正",
        "子初",
    ]
    for k, label in enumerate(labels):
        at = clock.source_clock_from_fraction(
            profile_id=profile, numerator=k, denominator=24
        )
        assert at["normalized_chu_zheng"]["label"] == label + "初刻"
        assert not at["source_day_name_advanced_at_zi_chu"]
        if k:
            before = clock.source_clock_from_fraction(
                profile_id=profile, numerator=k * 1000 - 1, denominator=24000
            )
            c = before["normalized_chu_zheng"]
            assert c["branch"] + c["phase"] == labels[k - 1]
            assert c["whole_ke"] == 4
            assert c["remaining_ke_fraction"] != {"numerator": 0, "denominator": 1}


def test_kai_xi_whole_hai_branch_straddles_daxue_without_an_imputed_birth_minute():
    r = clock.compare_branch_window_to_term(
        profile_id="songshi_tongtian_mei_v1",
        accumulated_years=3842,
        term_index=23,
        birth_day_offset_from_term_day=0,
        birth_branch="亥",
    )
    assert r["source_clock"]["normalized_chu_zheng"]["label"] == "亥初一刻"
    assert r["possible_before_term"] and r["possible_at_or_after_term"]
    assert r["boundary_inside_birth_window"]
    assert r["relation_under_assumption"] == "before_and_at_or_after_possible"
    assert not r["single_side_determined_under_assumption"]
    assert not r["birth_instant_imputed"]
    assert not r["public_month_pillar_changed"]
    assert "identity_not_established" in r["comparison_assumption"]
    assert "no_Bazi_ZiChu_day_rollover" in r["day_offset_basis"]


@pytest.mark.parametrize(
    "birth_branch,offset,relation",
    [
        ("戌", 0, "entirely_before"),
        ("子", 0, "before_and_at_or_after_possible"),
        ("亥", -1, "entirely_before"),
        ("亥", 1, "entirely_at_or_after"),
    ],
)
def test_resolvable_order_is_reported_without_extending_the_uncertainty(
    birth_branch, offset, relation
):
    r = clock.compare_branch_window_to_term(
        profile_id="songshi_tongtian_mei_v1",
        accumulated_years=3842,
        term_index=23,
        birth_day_offset_from_term_day=offset,
        birth_branch=birth_branch,
    )
    assert r["relation_under_assumption"] == relation
    assert r["single_side_determined_under_assumption"] is (
        relation != "before_and_at_or_after_possible"
    )
    if birth_branch == "子":
        assert len(r["birth_windows_relative_to_term_day"]) == 2
        assert not r["boundary_inside_birth_window"]


@pytest.mark.parametrize(
    "n,relation", [(21, "entirely_at_or_after"), (23, "entirely_before")]
)
def test_exact_branch_edges_use_inclusive_start_and_exclusive_end(
    monkeypatch, n, relation
):
    monkeypatch.setattr(
        clock,
        "source_term_clock",
        lambda **kwargs: {
            "source_term": {"source_day_fraction": {"numerator": n, "denominator": 24}}
        },
    )
    r = clock.compare_branch_window_to_term(
        profile_id="songshi_tongtian_mei_v1",
        accumulated_years=3842,
        term_index=23,
        birth_day_offset_from_term_day=0,
        birth_branch="亥",
    )
    assert r["relation_under_assumption"] == relation


@pytest.mark.parametrize(
    "n,d",
    [
        (True, 24),
        (1, True),
        (1.0, 24),
        ("1", 24),
        (0, 0),
        (1, -24),
        (-1, 24),
        (24, 24),
        (25, 24),
        (None, 24),
    ],
)
def test_day_fraction_cannot_be_guessed_rounded_or_carried_to_another_date(n, d):
    with pytest.raises(ValueError):
        clock.source_clock_from_fraction(
            profile_id="songshi_tongtian_mei_v1", numerator=n, denominator=d
        )


@pytest.mark.parametrize("bad", [True, 0.0, "0", None])
def test_signed_day_offset_is_explicit_not_inferred_from_a_cyclic_day_name(bad):
    with pytest.raises(ValueError):
        clock.compare_branch_window_to_term(
            profile_id="songshi_tongtian_mei_v1",
            accumulated_years=3842,
            term_index=23,
            birth_day_offset_from_term_day=bad,
            birth_branch="亥",
        )


@pytest.mark.parametrize("bad", ["", "亥時", "auto", None])
def test_unknown_branch_never_receives_a_default(bad):
    with pytest.raises(ValueError):
        clock.compare_branch_window_to_term(
            profile_id="songshi_tongtian_mei_v1",
            accumulated_years=3842,
            term_index=23,
            birth_day_offset_from_term_day=0,
            birth_branch=bad,
        )


@pytest.mark.parametrize("bad", ["", "auto", "tongtian", None])
def test_clock_profile_requires_an_explicit_verified_rule_name(bad):
    with pytest.raises(ValueError):
        clock.source_clock_from_fraction(profile_id=bad, numerator=0, denominator=1)


def test_sources_are_reused_without_claiming_new_original_examples():
    for item in REFERENCE["witnesses"]:
        assert (
            hashlib.sha256((ROOT / item["file"]).read_bytes()).hexdigest()
            == item["sha256"]
        )
    for name, digest in REFERENCE["prior_fixture_hashes"].items():
        assert (
            hashlib.sha256((ROOT.parents[2] / name).read_bytes()).hexdigest() == digest
        )
    assert sum(i["new_image"] for i in REFERENCE["witnesses"]) == 2
    assert (
        REFERENCE["new_original_births"]
        == REFERENCE["new_printed_calculation_cases"]
        == 0
    )
    assert REFERENCE["reused_prior_calculation_clock_captions"] == 2
    assert (
        REFERENCE["validated_historical_utc_instants"]
        == REFERENCE["independent_second_reviews"]
        == 0
    )


def test_audit_rejects_a_modern_ninety_six_ke_substitution(monkeypatch):
    from dataclasses import replace

    from scripts.audit_numerology import song_clock_source_checks

    valid = song_clock_source_checks()
    assert valid["checks_passed"]
    assert not valid["kai_xi_unique_month_boundary_side_determined"]
    rules = dict(clock._RULES)
    rules["songshi_tongtian_mei_v1"] = replace(
        rules["songshi_tongtian_mei_v1"], ke_divisor=Fraction(125)
    )
    monkeypatch.setattr(clock, "_RULES", rules)
    rejected = song_clock_source_checks()
    assert not rejected["checks_passed"]
    assert any(f["kind"] == "song_clock_ke_per_day" for f in rejected["failures"])
