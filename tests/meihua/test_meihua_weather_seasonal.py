"""Seasonal conditions use actual graphs and an explicitly named text witness."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from fatebridge.core.meihua_weather import weather_ruleset
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from fatebridge.validation.meihua_weather_policy_v2 import (
    canonical_sha256,
    qualified_weather_label,
)
from fatebridge.validation.meihua_weather_seasonal import audit_weather_seasonal
from tests.support.transports import rest, surface_calls

REFERENCES = Path(__file__).parents[1] / "fixtures/meihua_weather_seasonal_v6"
CASES = json.loads((REFERENCES / "cases.json").read_text())["cases"]


@pytest.fixture(scope="module")
def audited():
    return audit_weather_seasonal(REFERENCES)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_frozen_seasonal_diagrams_and_conditions(case, audited):
    row = next(r for r in audited["cases"] if r["id"] == case["id"])
    assert not row["disagreements"], row


def test_source_integration_is_not_independent_text_or_prediction_acceptance(audited):
    assert audited["selected_checks_passed"]
    assert audited["literal_mathematical_probe_count"] == 16
    assert audited["new_seasonal_rule_count"] == 3
    assert not audited["selected_facsimile_reading_truth_independently_proved"]
    assert not audited["complete_chapter_semantic_conformance_established"]
    assert not audited["predictive_efficacy_established"]
    assert not audited["authority_certified"]
    assert (
        audited["actual_model_runs"]
        == audited["prospective_weather_observations_added"]
        == 0
    )


def test_previous_35_rule_bodies_and_case_oracles_are_preserved():
    old = json.loads(
        (REFERENCES.parent / "meihua_weather_policy_v2/profile.json").read_text()
    )
    current = weather_ruleset()
    assert current["rules"][:35] == old["rules"]
    assert len(current["rules"]) == 40 and current["version"] == "1.7.0"
    manifest = json.loads(
        (REFERENCES.parent / "meihua_weather_chapter_v5/manifest.json").read_text()
    )
    assert (
        hashlib.sha256(
            (REFERENCES.parent / "meihua_weather_chapter_v5/cases.json").read_bytes()
        ).hexdigest()
        == manifest["files"]["cases.json"]
    )


def test_facsimile_subject_and_graph_cannot_be_repaired_using_element_knowledge():
    rules = {r["id"]: r for r in weather_ruleset()["rules"]}
    winter = rules["winter_kan_snow"]
    assert winter["quote"] == "坎之水，冬雪凜冽"
    assert "坎之水" not in winter["source_witnesses"][0]["selected_span"]
    assert (
        winter["textual_status"]
        == "fixed_transcription_subject_not_present_in_selected_facsimile"
    )
    spring = rules["spring_earth_rain"]
    assert spring["conditions"]["present_any"] == ["坤", "艮"]
    assert spring["source_witnesses"][0]["selected_span"] == "坤兌之土春雨澤"
    assert (
        spring["textual_status"] == "fixed_transcription_gen_vs_selected_facsimile_dui"
    )
    assert all(
        rules[name]["source_id"] == "meihua-volume-2"
        for name in ["winter_kan_snow", "spring_earth_rain"]
    )


def test_calendar_month_is_not_an_unreported_weather_season():
    output = calculate_meihua_analysis(
        analysis_year=2026,
        analysis_month=2,
        analysis_day=5,
        analysis_hour=12,
        analysis_timezone="Asia/Hong_Kong",
        interpretation_topic="weather",
    )
    weather = output["interpretation"]["weather"]
    assert weather["context"]["season"] is None
    assert "spring_earth_rain" in weather["pending_rule_ids"]
    assert weather["single_forecast"] is None


def test_old_2024_policy_cannot_silently_label_the_new_profile():
    output = calculate_meihua_cast(
        casting=CASES[6]["casting"],
        interpretation_topic="weather",
        weather_context=CASES[6]["context"],
    )
    old = json.loads(
        (REFERENCES.parent / "meihua_weather_policy_v2/profile.json").read_text()
    )
    with pytest.raises(ValueError, match="pinned1.5.0"):
        qualified_weather_label(
            output["interpretation"]["weather"],
            expected_profile_sha256=canonical_sha256(old),
        )


def test_retained_casts_use_their_own_winter_kan_not_the_selected_casts():
    # 9 -> 乾, 酉10 -> 兑: raw19 moves1; ordinal11 moves5.
    # Base110111, mutual101011; changed010111 versus110101.
    result = calculate_meihua_cast(
        casting={"method": "object_count", "count": 9, "hour_branch": "酉"},
        interpretation_topic="weather",
        weather_context={"season": "winter"},
    )
    weather = result["interpretation"]["weather"]
    variants = {v["line_sum_basis"]: v for v in weather["casting_variants"]}
    raw, ordinal = variants["raw_counts"], variants["trigram_numbers"]
    assert [raw["moving_line"], ordinal["moving_line"]] == [1, 5]
    assert [raw["changed_code"], ordinal["changed_code"]] == ["010111", "110101"]
    assert raw["trigram_counts"]["坎"] == 1 and ordinal["trigram_counts"]["坎"] == 0
    assert "winter_kan_snow" in raw["matched_rule_ids"]
    assert "winter_kan_snow" not in ordinal["matched_rule_ids"]
    assert "winter_kan_snow" in weather["casting_comparison"]["changed_rule_ids"]
    row = next(r for r in raw["selected_readings"] if r["rule_id"] == "winter_kan_snow")
    assert row["quote"] == "坎之水，冬雪凜冽"
    assert row["fact_paths"] == [
        "interpretation.weather.context.season",
        raw["fact_prefix"] + ".changed_hexagram.lower",
    ]
    assert raw["single_forecast"] is ordinal["single_forecast"] is None


def test_a_wrong_predeclared_result_remains_a_disagreement_after_rehash(tmp_path):
    target = tmp_path / "fixtures/meihua_weather_seasonal_v6"
    shutil.copytree(REFERENCES, target)
    for name in ["meihua_weather_gen_v4", "meihua_v1"]:
        shutil.copytree(REFERENCES.parent / name, target.parent / name)
    path = target / "cases.json"
    data = json.loads(path.read_text())
    data["cases"][0]["expected"]["rule_status"]["autumn_metal_clear"] = "not_met"
    path.write_text(json.dumps(data, ensure_ascii=False))
    with pytest.raises(ValueError, match="Frozen seasonal"):
        audit_weather_seasonal(target)
    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"]["cases.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    report = audit_weather_seasonal(target)
    assert not report["selected_checks_passed"]
    assert report["cases"][0]["disagreements"]


@pytest.mark.parametrize("tool", ["meihua_analysis", "meihua_cast"])
def test_seasonal_source_and_actual_qualification_survive_all_transports(
    tool, surface_calls
):
    from fatebridge.application.examples import suggested_fields
    from tests.support.transports import SPECS, business, call_cli, native

    spec = SPECS[tool]
    payload = (
        {
            "analysis_year": 2026,
            "analysis_month": 2,
            "analysis_day": 5,
            "analysis_hour": 12,
            "analysis_timezone": "Asia/Hong_Kong",
        }
        if tool == "meihua_analysis"
        else {"casting": CASES[15]["casting"]}
    )
    context = {"season": "spring", "many_min_count": 2}
    payload.update(interpretation_topic="weather", weather_context=context)
    fields = [
        *suggested_fields(spec, view="weather"),
        "interpretation.weather.single_forecast",
    ]
    http, protocol, code, local = surface_calls(
        spec,
        payload,
        projection={
            **{"fields": fields, "strict_fields": True},
            "response_char_limit": 0,
        },
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [http.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        weather = output["interpretation"]["weather"]
        assert weather["version"] == "1.7.0"
        assert (
            "meihua_weather_v1@1.7.0" in output["run_metadata"]["provenance"]["ruleset"]
        )
        row = next(
            r
            for r in weather["selected_readings"]
            if r["rule_id"] == "spring_earth_rain"
        )
        assert row["effective_status"] == "matched" and not row["controlled_tags"]
        assert row["quote"] == "坤、艮之土，春雨澤"
        assert row["source_witnesses"][0]["selected_span"] == "坤兌之土春雨澤"
        assert (
            row["textual_status"] == "fixed_transcription_gen_vs_selected_facsimile_dui"
        )
        assert (
            row["fact_paths"]
            and "interpretation.weather.context.season" in row["fact_paths"]
        )
        assert weather["single_forecast"] is None
