"""Original direct controls qualify dependent symbols; scope disagreement survives."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from fatebridge.core.meihua_weather_controls import qualify_weather_rules
from fatebridge.services.meihua import calculate_meihua_cast
from fatebridge.validation.meihua_weather import audit_weather_controls

REFERENCES = Path(__file__).parents[1] / "fixtures/meihua_weather_controls_v1"
CASES = json.loads((REFERENCES / "cases.json").read_text())["cases"]


def test_fixed_source_counts_and_all_control_probes():
    report = audit_weather_controls(REFERENCES)
    assert report["selected_control_checks_passed"], report["cases"]
    assert report["existing_classical_frequency_example_count"] == 1
    assert report["additional_mathematical_probe_count"] == 8
    assert len(report["quote_checks"]) == 4
    assert not report["unique_classical_frequency_scope_established"]
    assert not report["authority_certified"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_frequency_paths_scope_variants_and_actual_reading(case):
    output = calculate_meihua_cast(
        casting=case["casting"],
        interpretation_topic="weather",
        weather_context=case["context"],
    )
    weather = output["interpretation"]["weather"]
    views = {r["scope"]: r for r in weather["frequency_views"]}
    assert views["six_positions"]["trigram_counts"] == case["expected"]["six_counts"]
    assert (
        views["five_roles_static_once"]["trigram_counts"]
        == case["expected"]["five_counts"]
    )
    assert sum(views["six_positions"]["trigram_counts"].values()) == 6
    assert sum(views["five_roles_static_once"]["trigram_counts"].values()) == 5
    assert not views["five_roles_static_once"]["selected_for_main_frequency_rules"]
    assert all(
        r["path"] != views["five_roles_static_once"]["excluded_repeated_static_path"]
        for r in views["five_roles_static_once"]["trigram_slots"]
    )
    rows = {r["rule_id"]: r for r in weather["rule_trace"]}
    expected = case["expected"]["effective_rule"]
    assert rows[expected["rule_id"]]["effective_status"] == expected["status"]
    assert weather["single_forecast"] is None


def test_controlled_weather_is_not_still_presented_as_unqualified():
    case = CASES[0]
    output = calculate_meihua_cast(
        casting=case["casting"],
        interpretation_topic="weather",
        weather_context=case["context"],
    )
    row = next(
        r
        for r in output["interpretation"]["weather"]["rule_trace"]
        if r["rule_id"] == "symbol_xun"
    )
    assert row["status"] == "matched"  # Keep the literal source association.
    assert row["controlled_tags"] == ["wind"] and row["effective_tags"] == []
    assert "风象" in row["effective_reading"] and "受制" in output["summary"]


def test_selected_readings_keep_actual_conditions_and_source_paths():
    case = CASES[0]
    output = calculate_meihua_cast(
        casting=case["casting"],
        interpretation_topic="weather",
        weather_context=case["context"],
    )
    weather = output["interpretation"]["weather"]
    selected = weather["selected_readings"]
    assert [row["rule_id"] for row in selected] == weather["matched_rule_ids"]
    row = next(r for r in selected if r["rule_id"] == "symbol_xun")
    assert row["controlled_tags"] == ["wind"] and "受制" in row["reading"]
    assert row["source_id"] == "meihua-volume-2" and row["quote"] == "巽為風"
    assert row["fact_paths"] == [
        "meihua.base_hexagram.lower",
        "meihua.changed_hexagram.lower",
        "meihua.changed_hexagram.upper",
    ]


def test_grouping_and_static_deduplication_disagreement_are_not_voted():
    case = CASES[2]
    output = calculate_meihua_cast(
        casting=case["casting"],
        interpretation_topic="weather",
        weather_context=case["context"],
    )
    control = output["interpretation"]["weather"]["controls"][0]
    assert [v["condition_met"] for v in control["counting_variants"]] == [
        True,
        True,
        True,
        False,
    ]
    assert control["status"] == "scope_unresolved"
    assert "尚未确定" in output["summary"]


def test_water_controls_li_does_not_cancel_qian_clear_symbol():
    case = CASES[6]
    output = calculate_meihua_cast(
        casting=case["casting"],
        interpretation_topic="weather",
        weather_context=case["context"],
    )
    rows = {r["rule_id"]: r for r in output["interpretation"]["weather"]["rule_trace"]}
    assert rows["symbol_li"]["controlled_tags"] == ["clear"]
    assert rows["symbol_qian"]["controlled_tags"] == []
    assert rows["symbol_qian"]["effective_tags"] == ["clear"]


def test_earth_control_is_not_a_blanket_veto_of_every_rain_clause():
    # The source control is 坎雨. A different rain clause with 巽/兑 dependencies
    # must retain its own conditions, even if a separate 坎 symbol is controlled.
    traces = [
        {
            "rule_id": "winter_pair",
            "status": "matched",
            "tags": ["rain", "snow"],
            "traditional_reading": "冬季中孚雨雪象",
        }
    ]
    rules = [{"id": "winter_pair", "conditions": {"pairs": [["巽", "兑"]]}}]
    controls = [
        {
            "rule_id": "earth_controls_water_weather",
            "status": "met_under_declared_threshold_and_scope_probes",
            "affected_targets": {"坎": ["rain"]},
        }
    ]
    qualify_weather_rules(traces, rules, controls)
    assert traces[0]["effective_tags"] == ["rain", "snow"]
    assert traces[0]["control_checks"] == []


def test_old_negative_research_evidence_is_not_current_prediction_certification():
    result = calculate_meihua_cast(
        casting=CASES[0]["casting"], interpretation_topic="weather"
    )
    weather = result["interpretation"]["weather"]
    evidence = weather["research_validation"]
    assert evidence["correct"] == 128 and evidence["evaluable_days"] == 209
    assert evidence["same_dates_always_dry_correct"] == 134
    assert not evidence["beats_both_fixed_baselines"]
    assert evidence["evaluated_base_ruleset"].endswith("@1.0.0")
    assert weather["version"] == "1.7.0"
    assert not evidence["weather_controls_included"]
    assert not evidence["current_ruleset_efficacy_established"]


def test_control_oracle_corruption_and_false_expected_status_cannot_pass(tmp_path):
    directory = tmp_path / "meihua_weather_controls_v1"
    shutil.copytree(REFERENCES, directory)
    shutil.copytree(
        REFERENCES.parent / "meihua_v1/sources", tmp_path / "meihua_v1/sources"
    )
    path = directory / "cases.json"
    bundle = json.loads(path.read_text())
    bundle["cases"][0]["expected"]["five_counts"]["巽"] = 3
    path.write_text(json.dumps(bundle, ensure_ascii=False))
    with pytest.raises(ValueError, match="control probes changed"):
        audit_weather_controls(directory)
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["cases_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    report = audit_weather_controls(directory)
    assert not report["selected_control_checks_passed"]
    assert report["cases"][0]["disagreements"][0]["field"] == "five_counts"
