"""Source conflicts stay failed and propagate into the complete served reading."""

import json
import math
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.human_design import longitude_activation, opposite_activation
from fatebridge.core.human_design_evidence import source_activation_impacts
from fatebridge.core.human_design_source_variants import (
    cross_name_evidence,
    line_variant_impact,
    source_variant_audit,
    variant_reference,
)
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[1]
SPEC = next(s for s in CATALOG if s.key == "human_design")
# Engine-selected regression in the already declared 29.1/29.2 angular gap;
# not an independent astronomy reference or a real birth record.
INPUT = dict(
    birth_year=2000,
    birth_month=8,
    birth_day=18,
    birth_hour=0,
    birth_minute=0,
    birth_timezone="UTC",
)


def test_all_384_exact_arcs_and_all_19_names_retain_the_original_failures():
    report = source_variant_audit()
    assert report["printed_line_count"] == 384
    assert [
        (r["gate"], r["line"], r["printed_width_arcseconds"])
        for r in report["line_width_disagreements"]
    ] == [(29, 1, 2775), (29, 2, 3975)]
    assert report["observed_label_count"] == 19
    assert report["literal_name_matches"] == 4
    differences = [r for r in report["name_comparisons"] if not r["literal_match"]]
    assert len(differences) == 15
    assert (
        sum(
            r["difference_kind"] == "observed_label_omits_variant_number"
            for r in differences
        )
        == 12
    )
    assert (
        sum(r["difference_kind"] == "different_literal_label" for r in differences) == 3
    )
    assert not any(r["alias_accepted"] for r in report["name_comparisons"])
    assert report["publisher_erratum_obtained"] is False
    assert report["all_disagreements_resolved"] is False


def test_each_observed_name_is_bound_to_an_unchanged_official_case_and_pdf():
    import hashlib

    reference = variant_reference()
    cases = {}
    for source in reference["observed_cross_label_sources"]:
        raw = (ROOT / "tests/fixtures" / source["fixture"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == source["sha256"]
        cases.update({r["id"]: r for r in json.loads(raw)["cases"]})
    for row in reference["observed_cross_labels"]:
        case = cases[row["case_id"]]
        assert row["pdf_sha256"] == case["pdf_sha256"]
        assert row["display_name"] in case["properties"]["Incarnation Cross"]
    assert len(cases) == len(reference["observed_cross_labels"]) == 19


def test_an_observed_name_is_not_a_fuzzy_alias_or_an_unobserved_general_rule():
    cross = {"angle": "right", "gates": [38, 39, 48, 21], "name": "TENSION (4)"}
    report = cross_name_evidence({"incarnation_cross": cross})
    assert len(report["observations"]) == 9
    assert report["observed_labels"][0]["literal_match"] is False
    assert report["disagreement_resolved"] is False
    cross["gates"] = [38, 39, 45, 26]
    absent = cross_name_evidence({"incarnation_cross": cross})
    assert absent["status"] == "not_observed_in_frozen_cohort"
    assert absent["observed_labels"] == []
    assert absent["disagreement_resolved"] is False


def test_printed_source_candidates_at_every_boundary_and_adjacent_float():
    # Independent integer interval oracle; does not call the production classifier.
    rows = variant_reference()["printed_line_arcs"]
    for row in rows:
        for raw in (row["start_arcseconds"], row["end_arcseconds"]):
            bound = float(Fraction(raw, 3600))
            for lon in (
                math.nextafter(bound, -math.inf),
                bound,
                math.nextafter(bound, math.inf),
            ):
                activation = {"body": "Moon", **longitude_activation(lon)}
                coordinate = Fraction(lon) % 360 * 3600
                expected = [
                    r["line"]
                    for r in rows
                    if r["gate"] == activation["gate"]
                    and (coordinate - r["start_arcseconds"]) % 1296000
                    < (r["end_arcseconds"] - r["start_arcseconds"]) % 1296000
                ]
                report = line_variant_impact(
                    {"activations": {"personality": [activation]}}
                )
                if expected == [activation["line"]]:
                    assert report["differences"] == []
                else:
                    assert (
                        report["differences"][0]["printed_line_candidates"] == expected
                    )


def test_literal_29_table_breaks_the_paired_solar_rule_without_inventing_a_profile():
    p = [
        {"body": "Sun", **longitude_activation(145.3)},
        {"body": "Earth", "derived_from": "Sun", **opposite_activation(145.3)},
    ]
    d = [
        {"body": "Sun", **longitude_activation(57.3)},
        {"body": "Earth", "derived_from": "Sun", **opposite_activation(57.3)},
    ]
    chart = {"activations": {"personality": p, "design": d}}
    report = source_activation_impacts(chart)
    effects = report["conditional_printed_line_effects"]
    assert effects["status"] == "inconsistent_printed_sun_earth_lines"
    assert effects["sun_earth_pairs"][0] == {
        "side": "personality",
        "printed_sun_line": 2,
        "printed_earth_line": 1,
        "same_line": False,
    }
    assert effects["candidate_profile"] is None
    assert effects["full_alternative_chart_computed"] is False
    assert effects["color_tone_base_alternative"] is None
    changed = effects["changed_fixing_records"]
    assert changed[0]["implemented_uniform"]["line"] == 1
    assert changed[0]["conditional_printed"]["line"] == 2
    assert p[0]["line"] == 1  # Input is not rewritten.


@pytest.fixture(scope="module")
def complete():
    return execute_tool(SPEC, SPEC.request_model(**INPUT))


def test_complete_served_reading_explains_actual_conflict_and_retains_all_prior_statements(
    complete,
):
    source = complete["source_consistency"]
    assert source["activation_impacts"]["status"] == "affected"
    assert source["version_comparison"]["literal_name_matches"] == 4
    statements = complete["interpretation"]["statements"]
    assert {s["id"] for s in statements} == {
        "type",
        "authority",
        "definition",
        "circuitry",
        "profile",
        "variables",
        "cross",
        "source_discrepancies",
        "node_comparisons",
        "birth_interval",
    }
    statement = next(s for s in statements if s["id"] == "source_discrepancies")
    assert "日地不同线" in statement["text"]
    assert "不能据此生成" in statement["text"]
    assert statement["basis"][0]["value"] == source["activation_impacts"]
    check = verify_human_design_reading(complete)
    assert check["status"] == "verified_fixed_template_reading", check
    assert check["checked_statement_count"] == 10
    assert complete["validation"]["classical_acceptance_passed"] is False


def test_initial_august_17_clock_is_retained_as_an_outside_gap_negative_control():
    # The initial harness used this clock with an incorrect affected expectation.
    # Keep the original input: its Sun is before the disputed source interval.
    value = execute_tool(
        SPEC, SPEC.request_model(**{**INPUT, "birth_day": 17, "birth_hour": 12})
    )
    sun = next(a for a in value["activations"]["personality"] if a["body"] == "Sun")
    assert sun["gate"] == 29 and sun["line"] == 1
    assert sun["longitude"] < 145 + 16 / 60 + 15 / 3600
    assert value["source_consistency"]["activation_impacts"]["status"] == (
        "no_line_discrepancy_at_returned_longitudes"
    )
    assert (
        verify_human_design_reading(value)["status"]
        == "verified_fixed_template_reading"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "delete_conflict",
        "alt_profile",
        "printed_fixing",
        "alias",
        "name",
        "text",
        "drop_statement",
    ],
)
def test_rehashed_forged_dispute_or_incomplete_reading_is_rejected(complete, mutation):
    value = deepcopy(complete)
    source = value["source_consistency"]
    effects = source["activation_impacts"]["conditional_printed_line_effects"]
    if mutation == "delete_conflict":
        source["activation_impacts"]["differences"].clear()
    elif mutation == "alt_profile":
        effects["candidate_profile"] = "2/3"
    elif mutation == "printed_fixing":
        effects["changed_fixing_records"].clear()
    elif mutation == "alias":
        source["version_comparison"]["name_comparisons"][0]["alias_accepted"] = True
    elif mutation == "name":
        source["cross_name_comparison"]["primary"]["name"] = "Modern invented name"
    elif mutation == "text":
        value["interpretation"]["statements"][-1]["text"] = "原典完全一致，线义已认证。"
    else:
        value["interpretation"]["statements"].pop()
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )
    assert verify_human_design_reading(value)["status"] == "rejected"
