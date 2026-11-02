"""Each counting candidate has its own actual weather evidence and fact paths."""

import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.meihua_weather import build_weather_interpretation
from fatebridge.services.meihua import calculate_meihua_cast
from fatebridge.validation.meihua_weather_cast_variants import (
    audit_weather_cast_variants,
)

REFERENCES = Path(__file__).parent / "fixtures/meihua_weather_cast_variants_v3"
CASES = json.loads((REFERENCES / "cases.json").read_text())["cases"]


def calculate(case):
    return calculate_meihua_cast(
        casting=case["casting"],
        interpretation_topic="weather",
        weather_context=case["context"],
    )


def resolve(output, path):
    value = output
    for key in path.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def normalize_paths(value, prefix):
    if isinstance(value, str) and value.startswith(prefix):
        return "meihua" + value.removeprefix(prefix)
    if isinstance(value, dict):
        return {k: normalize_paths(v, prefix) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize_paths(v, prefix) for v in value]
    return value


def test_frozen_manual_candidate_geometry_and_conditions():
    report = audit_weather_cast_variants(REFERENCES)
    assert report["selected_checks_passed"], report["cases"]
    assert report["independent_manual_probe_count"] == 7
    assert report["original_worked_example_count_added"] == 0
    assert report["real_weather_observation_count"] == 0
    assert report["real_model_semantic_acceptance"] == "not_tested"
    assert not report["unique_classical_count_convention_established"]
    assert not report["authority_certified"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_every_candidate_uses_own_facts_and_same_context_without_new_cast(case):
    output = calculate(case)
    weather = output["interpretation"]["weather"]
    compact = weather["casting_variants"]
    details = weather["casting_variant_traces"]
    assert len(compact) == len(details) == len(output["meihua"]["counting_variants"])
    assert (
        weather["casting_comparison"]["status"] == case["expected"]["comparison_status"]
    )
    assert weather["single_forecast"] is None
    if not compact:
        assert weather["casting_comparison"]["candidate_count"] == 0
        return
    assert sum(v["selected"] for v in compact) == 1
    selected = next(v for v in compact if v["selected"])
    assert selected["line_sum_basis"] == output["meihua"]["seed"]["line_sum_basis"]
    assert selected["trigram_counts"] == weather["trigram_counts"]
    assert (
        normalize_paths(selected["selected_readings"], selected["fact_prefix"])
        == weather["selected_readings"]
    )
    for compact_row, detail in zip(compact, details):
        prefix = compact_row["fact_prefix"]
        assert compact_row["single_forecast"] is None
        assert (
            compact_row["base_code"] == output["meihua"]["base_hexagram"]["binary_code"]
        )
        assert sum(compact_row["trigram_counts"].values()) == 6
        assert [v["slot_count"] for v in detail["frequency_views"]] == [6, 5]
        expected_static = "upper" if compact_row["moving_line"] <= 3 else "lower"
        assert (
            detail["frequency_views"][1]["excluded_repeated_static_path"]
            == prefix + ".changed_hexagram." + expected_static
        )
        for slot in detail["trigram_slots"]:
            assert slot["path"].startswith(prefix + ".")
            assert resolve(output, slot["path"])["name"] == slot["trigram"]
        for reading in compact_row["selected_readings"]:
            for path in reading["fact_paths"]:
                assert path.startswith(prefix + ".") or path.startswith(
                    "interpretation.weather.context."
                )
                resolve(output, path)
    assert "各候选分列" in output["summary"]


@pytest.mark.parametrize("case", CASES[:5], ids=lambda c: c["id"])
def test_candidate_evaluation_matches_standalone_given_cast_integration(case):
    # Integration equivalence is not counted as an independent mathematical oracle.
    output = calculate(case)
    weather = output["interpretation"]["weather"]
    for detail, compact in zip(
        weather["casting_variant_traces"], weather["casting_variants"]
    ):
        standalone = calculate_meihua_cast(
            casting={
                "method": "existing",
                "hexagram_code": compact["base_code"],
                "moving_line": compact["moving_line"],
            },
            interpretation_topic="weather",
            weather_context=case["context"],
        )["interpretation"]["weather"]
        prefix = compact["fact_prefix"]
        for key in ["rule_trace", "controls", "frequency_views"]:
            assert normalize_paths(detail[key], prefix) == standalone[key]
        assert (
            normalize_paths(compact["selected_readings"], prefix)
            == standalone["selected_readings"]
        )


def test_context_agreement_is_not_universal_cast_or_forecast_agreement():
    summer, winter = (calculate(c)["interpretation"]["weather"] for c in CASES[3:5])
    assert (
        summer["casting_comparison"]["status"]
        == "same_rule_results_for_supplied_context"
    )
    assert summer["casting_comparison"]["trigram_counts_differ"]
    assert winter["casting_comparison"]["status"] == "different_rule_results"
    assert "zhongfu_daguo_winter" in winter["casting_comparison"]["changed_rule_ids"]
    assert summer["single_forecast"] is winter["single_forecast"] is None


def test_missing_season_keeps_the_affected_candidate_pending():
    case = deepcopy(CASES[3])
    case["context"]["season"] = None
    weather = calculate(case)["interpretation"]["weather"]
    rows = {r["line_sum_basis"]: r for r in weather["casting_variant_traces"]}
    statuses = {
        basis: next(
            r["status"]
            for r in row["rule_trace"]
            if r["rule_id"] == "zhongfu_daguo_winter"
        )
        for basis, row in rows.items()
    }
    assert statuses == {"raw_counts": "not_met", "trigram_numbers": "pending_context"}
    assert weather["casting_comparison"]["status"] == "different_rule_results"


def test_source_control_difference_is_not_hidden_by_same_symbol_presence():
    output = calculate(CASES[2])
    weather = output["interpretation"]["weather"]
    assert (
        "metal_controls_wood_weather"
        in weather["casting_comparison"]["changed_control_ids"]
    )
    rows = {v["line_sum_basis"]: v for v in weather["casting_variants"]}
    raw = next(
        r
        for r in rows["raw_counts"]["selected_readings"]
        if r["rule_id"] == "symbol_xun"
    )
    reduced = next(
        r
        for r in rows["trigram_numbers"]["selected_readings"]
        if r["rule_id"] == "symbol_xun"
    )
    assert raw["controlled_tags"] == ["wind"] and raw["conditional_tags"] == []
    assert reduced["controlled_tags"] == [] and reduced["conditional_tags"] == ["wind"]


def test_candidate_weather_does_not_use_body_use_or_editorial_meanings():
    output = calculate(CASES[0])
    altered = deepcopy(output["meihua"])
    for row in altered["counting_variants"]:
        row["body_trigram"] = row["use_trigram"] = row["stage_relations"] = "unused"
        for key in ["base_hexagram", "changed_hexagram", "mutual_hexagram"]:
            row[key]["meaning"] = "not weather evidence"
    assert build_weather_interpretation(
        altered, CASES[0]["context"]
    ) == build_weather_interpretation(output["meihua"], CASES[0]["context"])


def test_rehashed_false_expected_candidate_is_still_reported(tmp_path):
    directory = tmp_path / REFERENCES.name
    shutil.copytree(REFERENCES, directory)
    shutil.copytree(
        REFERENCES.parent / "meihua_v1/sources", tmp_path / "meihua_v1/sources"
    )
    (tmp_path / "meihua_scan_v1").mkdir()
    shutil.copy2(
        REFERENCES.parent / "meihua_scan_v1/manifest.json",
        tmp_path / "meihua_scan_v1/manifest.json",
    )
    path = directory / "cases.json"
    data = json.loads(path.read_text())
    data["cases"][0]["expected"]["variants"]["raw_counts"]["changed_code"] = "110101"
    path.write_text(json.dumps(data, ensure_ascii=False))
    with pytest.raises(ValueError, match="probes changed"):
        audit_weather_cast_variants(directory)
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["cases_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    report = audit_weather_cast_variants(directory)
    assert not report["selected_checks_passed"]
    assert report["cases"][0]["disagreements"][0]["field"] == "variants"
