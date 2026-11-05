"""The full source exception and unobserved conditions cannot disappear."""

import hashlib
import json
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_senmyo_phase import (
    SOURCE,
    goryeosa_phase_annotation,
    phase_annotation_lines,
    phase_annotation_reading,
    phase_annotation_reference,
    validate_selected_rule,
)
from fatebridge.core.sukuyo_sources import load_source

FIXTURE = Path(__file__).parents[1] / "data/sukuyo-senmyo-phase-oracle-v1.json"


def test_complete_before_code_possible_world_oracle_including_rejected_rows():
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "2b4b0cbcbf1bc1bd034b95b5c574a77ed334aa8a2435482eb5b2a0e186cd773a"
    )
    protocol = json.loads(raw)
    assert protocol["rows_count"] == len(protocol["rows"]) == 100
    assert protocol["expected_rejections"] == 10
    for row in protocol["rows"]:
        args = (
            row["phase"],
            Fraction(**row["phase_remainder"]),
            Fraction(**row["twilight_remainder"]),
        )
        flags = {k: row[k] for k in ("has_lunar_eclipse", "initial_before_chenchu")}
        if "expected_rejection" in row:
            with pytest.raises(ValueError, match=row["expected_rejection"]):
                goryeosa_phase_annotation(*args, **flags)
        else:
            result = goryeosa_phase_annotation(*args, **flags)
            assert (
                result["candidate_annotation_day_shifts"] == row["expected_candidates"]
            )
            assert result["status"] == row["expected_status"]
            assert not result["applied_to_current_input_or_host_calendar"]


def test_above_threshold_cannot_hide_missing_eclipse_exception_predicate():
    result = goryeosa_phase_annotation("full", 2557, 2193, has_lunar_eclipse=True)
    assert not result["phase_before_twilight"]
    assert result["full_moon_eclipse_exception_applies"] is None
    assert result["annotation_day_shift"] is None
    assert result["candidate_annotation_day_shifts"] == [-1, 0]
    assert "合取条件未知" in result["reading_text"]
    assert "退一日／不退两候选" in result["reading_text"]


def test_known_eclipse_exception_changes_phase_designation_without_changing_clock():
    result = goryeosa_phase_annotation(
        "full", 2557, 2193, has_lunar_eclipse=True, initial_before_chenchu=True
    )
    assert result["annotation_day_shift"] == -1
    assert not result["chenchu_equal_to_twilight_inferred"]
    assert not result["physical_eclipse_or_visibility_evaluated"]
    assert "记日结果为退一日" in result["reading_text"]


def test_false_morning_answer_covers_requested_contrasts_and_declaration_provenance():
    variants = [
        goryeosa_phase_annotation(
            "full", 2557, 2193, has_lunar_eclipse=True, initial_before_chenchu=flag
        )
        for flag in (None, True, False)
    ]
    assert [r["candidate_annotation_day_shifts"] for r in variants] == [
        [-1, 0],
        [-1],
        [0],
    ]
    text = variants[-1]["reading_text"]
    assert "晨初条件若未知，保留退一日／不退" in text
    assert "若成立，望食例外使记日退一日；若不成立，则不退" in text
    assert "本函数未取得独立核定者身份" in text
    assert variants[-1]["independent_adjudicator_identity"] is None


def test_strict_equality_and_exact_subunits_are_not_rounded_into_same_case():
    for point, expected in [(Fraction(4385, 2), -1), (2193, 0), (Fraction(4387, 2), 0)]:
        result = goryeosa_phase_annotation("full", point, 2193, has_lunar_eclipse=False)
        assert result["annotation_day_shift"] == expected
        assert (
            result["named_print_variant"]["inferred_comparison"] == "less_than_or_equal"
        )
        assert "两版本未合并" in result["reading_text"]
        assert "相等处有差异" in result["reading_text"]


@pytest.mark.parametrize("bad", [True, 0.0, "2193", None, -1, 8400, Fraction(-1, 2)])
def test_remainders_reject_inferred_units_floats_and_implicit_day_carry(bad):
    with pytest.raises(ValueError):
        goryeosa_phase_annotation("full", bad, 2193)
    with pytest.raises(ValueError):
        goryeosa_phase_annotation("full", 2557, bad)


@pytest.mark.parametrize("bad", [0, 1, "unknown", "false"])
def test_truth_values_cannot_silently_coerce_unknown_or_flags(bad):
    with pytest.raises(ValueError, match="布尔或未知"):
        goryeosa_phase_annotation("full", 2557, 2193, has_lunar_eclipse=bad)


@pytest.mark.parametrize(
    "mutation",
    [
        "exception",
        "operator",
        "phase_scope",
        "units",
        "morning",
        "report",
        "sources",
        "variant_operator",
        "variant_merge",
        "variant_identity",
    ],
)
def test_source_context_and_missing_terms_cannot_be_reduced_to_passing_rule(mutation):
    data = deepcopy(load_source(SOURCE).data)
    if mutation == "exception":
        data["rules"].pop("full_moon_eclipse_exception")
    elif mutation == "operator":
        data["rules"]["quarter_or_full_before_twilight"]["comparison"] = "less_or_equal"
    elif mutation == "phase_scope":
        data["rules"]["full_moon_eclipse_exception"]["phase_scope"].append("quarter")
    elif mutation == "units":
        data["units"]["koku_units"] = 100
    elif mutation == "morning":
        data["terminology"]["all_three_established_identical"] = True
    elif mutation == "report":
        data["reported_1117_case"]["reported_1117_phase_remainder"] = 2550
    elif mutation == "sources":
        data["source_reference"]["electronic_sources"].pop()
    elif mutation == "variant_operator":
        data["named_print_variant"]["inferred_comparison"] = "strict_less_than"
    elif mutation == "variant_merge":
        data["named_print_variant"]["selected_goryeosa_rule_changed"] = True
    else:
        data["named_print_variant"]["kyoto_equals_cited_waseda_physical_copy"] = True
    with pytest.raises(ValueError):
        validate_selected_rule(data)


def test_current_civil_time_does_not_set_phase_predicates_or_rewrite_hinoo_candidates():
    calendar = calendar_mansion(
        "0814-09-21",
        "11:59:00",
        "+09:00",
        calendar_basis="japanese_naoj_historical_utc09",
        calendar_profile="hinoo_t1299_host27",
    )
    result = day_evidence(calendar)
    assert calendar["natal_su27"] is None
    assert calendar["candidate_su27s"] == ["轸", "角"]
    named = result["calendar_day"]["clock_doctrine"][
        "senmyo_phase_annotation_reference"
    ]
    assert named["current_input_phase_annotation_status"] == "not_evaluated"
    assert named["reported_case_full_rule_evaluation"][
        "candidate_annotation_day_shifts"
    ] == [-1, 0]
    assert "不是本次输入日期的月相或退日计算" in result["reading_text"]
    assert not named["historical_report_or_research_error_certified"]
    assert named["named_print_variant"]["equality_conflict_preserved"]
    assert "相等处有差异" in result["reading_text"]


def test_returned_source_cannot_mutate_later_calls_or_hardcode_rendered_candidates():
    first = phase_annotation_reference()
    first["rules"].clear()
    assert phase_annotation_reference()["rules"]
    result = goryeosa_phase_annotation(
        "full", 2557, 2193, has_lunar_eclipse=True, initial_before_chenchu=True
    )
    assert "退一日／不退两候选" not in phase_annotation_reading(result)
    ref = phase_annotation_reference()
    ref["reported_case_full_rule_evaluation"] = result
    assert "条件结果为退" in "".join(phase_annotation_lines(ref))
    assert "保留退／不退两候选" not in "".join(phase_annotation_lines(ref))
