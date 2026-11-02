"""Named publisher uncertainty does not disappear behind exact table agreement."""

import asyncio
import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from fatebridge.core.meihua_calendar_precision import calendar_label_precision
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from fatebridge.validation.meihua_calendar_precision import audit_calendar_precision
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

REFERENCES = Path(__file__).parent / "fixtures/meihua_calendar_precision_v4"
REVIEW_CASES = json.loads((REFERENCES / "review-cases.json").read_text())["cases"]
CAST_CASES = json.loads((REFERENCES / "cases.json").read_text())["cases"]


@pytest.mark.parametrize("case", REVIEW_CASES, ids=lambda c: c["date"])
def test_published_month_review_scope_has_explicit_edges(case):
    result = calendar_label_precision(date.fromisoformat(case["date"]))
    assert bool(result["matched_events"]) is case["review_expected"]
    if case["review_expected"]:
        assert [e["id"] for e in result["matched_events"]] == [case["event_id"]]
        assert result["date_label_revision_may_change_month_day_and_cast"]
    policy = result["review_scope_policy"]
    assert policy["review_windows_are_not_published_hko_intervals"]
    assert policy["other_published_month_anchors_assumed_fixed_for_review_scope"]
    assert policy["no_shift_direction_probability_or_alternate_lunar_labels_inferred"]
    assert not result["exact_astronomical_accuracy_established"]
    assert not result["predictive_efficacy_established"]
    assert not result["absence_of_named_event_certifies_exactness"]


def test_frozen_official_caveat_and_three_manual_casts_are_not_authority():
    report = audit_calendar_precision(REFERENCES)
    assert report["selected_checks_passed"], report
    assert len(report["manual_mathematical_cases"]) == 3
    assert len(report["synthetic_review_window_cases"]) == 15
    assert not report["lunar_labels_or_cast_arithmetic_changed"]
    assert not report["full_astronomical_accuracy_established"]
    assert not report["real_world_predictive_efficacy_established"]
    assert report["actual_model_runs"] == 0
    assert not report["authority_certified"]


@pytest.mark.parametrize("topic", ["general", "weather"])
@pytest.mark.parametrize("case", CAST_CASES, ids=lambda c: c["date"])
def test_known_month_review_is_disclosed_in_both_interpretation_branches(case, topic):
    y, m, d = map(int, case["date"].split("-"))
    result = calculate_meihua_analysis(
        analysis_year=y,
        analysis_month=m,
        analysis_day=d,
        analysis_hour=12,
        analysis_timezone="UTC+08:00",
        interpretation_topic=topic,
    )
    assert "error" not in result
    precision = result["meihua"]["calendar_policy"]["label_precision"]
    assert precision["status"] == "named_month_start_review_required"
    assert precision["selected_civil_date"] == case["date"]
    assert "历表" in result["summary"] and "相差一日" in result["summary"]
    assert result["summary"] == result["interpretation"]["comprehensive_judgement"]
    scope = result["interpretation"]["evidence_scope"]
    assert (
        scope["calendar_label_precision_path"]
        == "meihua.calendar_policy.label_precision"
    )
    assert scope["calendar_label_precision_status"] == precision["status"]
    assert result["meihua"]["base_hexagram"]["binary_code"] == case["base_code"]
    assert result["meihua"]["seed"]["moving_line"] == case["moving_line"]
    if topic == "weather":
        assert result["interpretation"]["weather"]["single_forecast"] is None
        assert (
            result["interpretation"]["weather"]["time_scope_comparison"]["policy"][
                "target_calendar_date"
            ]
            is None
        )


def test_unlisted_day_and_non_hko_prefix_do_not_become_exactness_certificates():
    assert (
        calendar_label_precision(date(1900, 1, 1))["status"]
        == "outside_hko_annual_table_scope"
    )
    ordinary = calendar_label_precision(date(2026, 2, 19))
    assert ordinary["status"] == "no_named_boundary_in_review_window"
    assert not ordinary["absence_of_named_event_certifies_exactness"]
    # HKO also lists solar-term near-midnight cases. They must not silently
    # become new-moon label episodes in this lunar-seed-specific component.
    assert not calendar_label_precision(date(2083, 2, 4))["matched_events"]
    cast = calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": "001101", "moving_line": 1}
    )
    assert "label_precision" not in cast["meihua"]["calendar_policy"]


def test_returned_precision_metadata_cannot_poison_later_calls():
    a = calendar_label_precision(date(2057, 9, 28))
    a["source"]["url"] = "changed"
    a["matched_events"][0]["published_lunar_month"] = 1
    a["review_scope_policy"]["unlisted_boundaries_are_not_certified_exact"] = False
    b = calendar_label_precision(date(2057, 9, 28))
    assert b["source"]["url"].startswith("https://www.hko.gov.hk/")
    assert b["matched_events"][0]["published_lunar_month"] == 9
    assert b["review_scope_policy"]["unlisted_boundaries_are_not_certified_exact"]


def test_changed_reference_is_not_accepted_as_better_agreement(tmp_path):
    target = tmp_path / "refs"
    shutil.copytree(REFERENCES, target)
    path = target / "cases.json"
    path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError, match="Frozen calendar-precision reference changed"):
        audit_calendar_precision(target)


@pytest.mark.parametrize("topic", ["general", "weather"])
def test_publisher_review_remains_in_strict_projection_on_all_surfaces(
    topic, rest, tmp_path, capsys
):
    payload = {
        "analysis_year": 2057,
        "analysis_month": 9,
        "analysis_day": 28,
        "analysis_hour": 12,
        "analysis_timezone": "UTC+08:00",
        "interpretation_topic": topic,
    }
    fields = [
        "meihua.calendar_policy.label_precision.status",
        "meihua.calendar_policy.label_precision.matched_events",
        "interpretation.evidence_scope",
        "summary",
    ]
    spec = SPECS["meihua_analysis"]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [("strict_fields", "true"), ("response_char_limit", "0")],
    )
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(native(spec, payload, fields=fields, strict_fields=True))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(response.json())
        == business(cli)
        == business(protocol.structured_content)
    )
    for out in [response.json(), cli, protocol.structured_content]:
        assert (
            out["meihua"]["calendar_policy"]["label_precision"]["status"]
            == "named_month_start_review_required"
        )
        assert "相差一日" in out["summary"]
