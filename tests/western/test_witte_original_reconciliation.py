"""Original-page operations, retained residuals and a non-fitting source audit."""

import copy
import hashlib
import json
import sys

import pytest
from pydantic import ValidationError

from fatebridge.application.examples import call_guidance, evidence_views
from fatebridge.core.output_midpoints import MidpointAnalysis
from fatebridge.services.tool_catalog import CATALOG
from scripts.western import replay_witte_meridian_sources as replayer
from scripts.western.audit_other_chart_schools import day_meridian_check


def source():
    data = replayer.FIXTURE.read_bytes()
    assert hashlib.sha256(data).hexdigest() == replayer.FIXTURE_SHA256
    return json.loads(data)


def test_printed_operations_explain_184_minutes_and_retain_separate_four_minutes():
    report = replayer.replay(source())
    assert report["printed_arithmetic_checks_passed"]
    assert report["table_rows"] == 13
    assert report["consecutive_phase_steps_arcminutes"] == [1795] * 12
    assert all(
        row["residual_arcminutes"] == 0 for row in report["printed_cusp_oppositions"]
    )
    assert (
        report["meridian_difference_arcminutes"]
        == report["cusp_offset_arcminutes"]
        == 184
    )
    assert report["operations"][0]["result_arcminutes"] == 236 * 60 + 34
    assert report["operations"][0]["opposite_result_arcminutes"] == 56 * 60 + 34
    assert report["operations"][1]["result_arcminutes"] == 166 * 60 + 49
    assert report["operations"][1]["signed_comparison_residual_arcminutes"] == 4
    assert not report["all_reported_sensitive_points_exact"]
    assert not report["original_variants_fully_reconciled"]
    assert not report["original_progression_time_key_accepted"]
    assert not report["table_dates_independently_verified"]
    assert report["empirical_outcomes"] == 0


def test_equalizing_the_1923_cusp_is_a_failed_source_replay():
    fixture = copy.deepcopy(source())
    fixture["table"][4]["natal_cusp"] = [7, 7, 15]
    report = replayer.replay(fixture)
    assert not report["difference_explained_by_printed_cusp_offset"]
    assert not report["printed_arithmetic_checks_passed"]
    assert (
        report["source_disagreement_status"]
        == "printed_arithmetic_difference_not_reproduced"
    )


def test_monthly_phase_typo_is_retained_as_a_failure():
    fixture = copy.deepcopy(source())
    fixture["table"][0]["solar_phase"][2] = 47
    assert not replayer.replay(fixture)["printed_arithmetic_checks_passed"]


def test_modified_transcription_is_rejected_before_receipt_is_created(
    monkeypatch, tmp_path
):
    fixture = tmp_path / "changed.json"
    fixture.write_bytes(replayer.FIXTURE.read_bytes() + b"\n")
    destination = tmp_path / "receipt.json"
    monkeypatch.setattr(replayer, "FIXTURE", fixture)
    monkeypatch.setattr(sys, "argv", ["replay", "--output", str(destination)])
    with pytest.raises(ValueError, match="checksum"):
        replayer.main()
    assert not destination.exists()


def test_public_comparison_rejects_invalid_historical_angle():
    with pytest.raises(ValidationError):
        MidpointAnalysis.model_validate(
            {
                "solar_arc_analysis": {
                    "daily_meridian": {
                        "source_comparison": {
                            "historical_example_difference_arcminutes": "wrong"
                        }
                    }
                }
            }
        )


def test_aggregate_audit_retains_historical_status_and_does_not_accept_full_original():
    report = day_meridian_check()
    assert report["selected_1924_equation_replay_matches"]
    assert report["source_reconciliation"]["printed_arithmetic_checks_passed"]
    assert report["original_author_printed_arithmetic_cases"] == 3
    assert report["distinct_historical_examples"] == 1
    assert (
        report["earlier_source_disagreement_status_at_capture"]
        == "variant_or_print_error_unresolved"
    )
    assert report["printed_variant_difference_explained"]
    assert not report["original_variants_reconciled"]
    assert report["full_original_numerical_horoscopes_accepted"] == 0


def test_published_day_meridian_card_reads_the_comparison_and_retained_residual():
    spec = next(row for row in CATALOG if row.key == "astro_germany")
    guidance = call_guidance(spec)["daily_meridian"]
    card = evidence_views(spec)["daily_meridian"]
    assert "source_comparison" in guidance
    assert "184 arcminute correction" in guidance
    assert "4 arcminute" in guidance
    assert "computed_for_current_chart=false" in card["purpose"]
    assert "unresolved 1923/1924" not in card["purpose"]
    assert "midpoint_analysis.solar_arc_analysis.daily_meridian" in card["fields"]
