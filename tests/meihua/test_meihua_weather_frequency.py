"""Uncertain count premises survive raw results, summaries and selected readings."""

import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.meihua_weather_frequency import qualify_weather_frequency
from fatebridge.services.meihua import calculate_meihua_cast
from fatebridge.validation.meihua_weather_frequency import audit_weather_frequency

REFERENCES = Path(__file__).parents[1] / "fixtures/meihua_weather_frequency_v2"
CASES = json.loads((REFERENCES / "cases.json").read_text())["cases"]


def test_frozen_frequency_oracles_and_source_quotes():
    report = audit_weather_frequency(REFERENCES)
    assert report["selected_frequency_checks_passed"], report["cases"]
    assert report["independent_mathematical_probe_count"] == 8
    assert len(report["quote_checks"]) == 8
    assert report["quote_only_rule_ids"] == [
        "many_dui_cloudy",
        "many_gen_long_rain_clear",
        "many_xun_all_seasons",
        "many_zhen_spring_summer",
    ]
    assert len(report["numerical_probe_rule_ids"]) == 4
    assert not report["raw_six_position_policy_changed"]
    assert not report["unique_classical_frequency_scope_established"]
    assert not report["authority_certified"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_actual_many_conditions_are_qualified_without_overwriting_raw_result(case):
    output = calculate_meihua_cast(
        casting=case["casting"],
        interpretation_topic="weather",
        weather_context=case["context"],
    )
    weather = output["interpretation"]["weather"]
    rows = {r["rule_id"]: r for r in weather["rule_trace"]}
    selected = {r["rule_id"]: r for r in weather["selected_readings"]}
    for key, expected in case["expected"]["rules"].items():
        row = rows[key]
        assert row["status"] == expected["status"]
        assert row["effective_status"] == expected["effective_status"]
        disputed = expected["effective_status"] == "conditional_on_unresolved_frequency"
        if disputed:
            assert row["conditional_tags"] == sorted(row["tags"])
            assert "unresolved_frequency_scope" in row["qualification_reasons"]
            assert "频数范围未裁定" in row["effective_reading"]
            assert selected[key]["reading"] == row["effective_reading"]
            assert selected[key]["frequency_assessment"] == row["frequency_assessment"]
            assert (
                "interpretation.weather.context.many_min_count"
                in selected[key]["fact_paths"]
            )
            assert "频数范围未裁定" in output["summary"]
        elif row["status"] != "matched":
            assert row["conditional_tags"] == []
            assert key not in selected
        else:
            assert row["qualification_reasons"] == []
        for variant in row["frequency_assessment"]["counting_variants"]:
            assert variant["count"] == len(variant["fact_paths"])
    assert rows["symbol_li"]["frequency_assessment"] is None
    assert weather["single_forecast"] is None


def test_frequency_qualification_retains_independent_control_and_pure_pair_readings():
    result = calculate_meihua_cast(
        casting=CASES[0]["casting"],
        interpretation_topic="weather",
        weather_context=CASES[0]["context"],
    )
    rows = {r["rule_id"]: r for r in result["interpretation"]["weather"]["rule_trace"]}
    assert rows["many_li"]["effective_status"] == "conditional_on_unresolved_frequency"
    assert rows["pure_li_summer_drought"]["effective_status"] == "matched"
    assert rows["pure_li_summer_drought"]["frequency_assessment"] is None
    # Fabricated overlapping conditions test composition only, not an original case.
    row = deepcopy(rows["many_li"])
    row.update(
        effective_status="qualified_by_source_control",
        qualification_reasons=["source_control"],
        controlled_tags=["clear"],
        conditional_tags=[],
        effective_reading="原有制约说明",
    )
    qualify_weather_frequency([row])
    assert row["effective_status"] == "multiple_qualifications"
    assert row["qualification_reasons"] == [
        "source_control",
        "unresolved_frequency_scope",
    ]
    assert row["controlled_tags"] == ["clear"] and row["conditional_tags"] == []
    assert row["effective_reading"].endswith("原有制约说明")


def test_rehashed_false_frequency_oracle_is_still_reported(tmp_path):
    directory = tmp_path / REFERENCES.name
    shutil.copytree(REFERENCES, directory)
    shutil.copytree(
        REFERENCES.parent / "meihua_v1/sources", tmp_path / "meihua_v1/sources"
    )
    shutil.copytree(REFERENCES.parent / "meihua_scan_v1", tmp_path / "meihua_scan_v1")
    path = directory / "cases.json"
    bundle = json.loads(path.read_text())
    bundle["cases"][0]["expected"]["counts"] = [3, 3]
    path.write_text(json.dumps(bundle, ensure_ascii=False))
    with pytest.raises(ValueError, match="frequency probes changed"):
        audit_weather_frequency(directory)
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["cases_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    report = audit_weather_frequency(directory)
    assert not report["selected_frequency_checks_passed"]
    assert report["cases"][0]["disagreements"][0]["field"] == "counts"
