"""Source wording, seasonal 多 and actual pair scope remain explicit."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from fatebridge.services.meihua import calculate_meihua_cast
from fatebridge.validation.meihua_weather_chapter import audit_weather_chapter
from tests.support.transports import rest, surface_calls

REFERENCES = Path(__file__).parents[1] / "fixtures/meihua_weather_chapter_v5"
CASES = json.loads((REFERENCES / "cases.json").read_text())["cases"]


def calculate(case):
    return calculate_meihua_cast(
        casting=case["casting"],
        interpretation_topic="weather",
        weather_context=case["context"],
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_frozen_season_many_and_pair_probes(case):
    output = calculate(case)
    cast = output["meihua"]
    weather = output["interpretation"]["weather"]
    expected = case["expected"]
    assert cast["base_hexagram"]["binary_code"] == expected["base_code"]
    assert cast["changed_hexagram"]["binary_code"] == expected["changed_code"]
    assert cast["mutual_hexagram"]["binary_code"] == expected["mutual_code"]
    assert [row["trigram"] for row in weather["trigram_slots"]] == expected["six_slots"]
    trace = next(
        row for row in weather["rule_trace"] if row["rule_id"] == expected["rule_id"]
    )
    assert [trace["status"], trace["effective_status"]] == [
        expected["status"],
        expected["effective_status"],
    ]
    if expected["counts"] is not None:
        assert [
            v["count"] for v in trace["frequency_assessment"]["counting_variants"]
        ] == expected["counts"]


def test_fixed_quote_and_primary_wording_are_both_retained():
    output = calculate(CASES[13])
    row = next(
        r
        for r in output["interpretation"]["weather"]["selected_readings"]
        if r["rule_id"] == "pure_kan_rain"
    )
    assert "四時必雨" in row["quote"]
    assert {r["selected_span"] for r in row["source_witnesses"]} == {"冬必寒四時多雨"}
    assert row["textual_status"] == "fixed_transcription_with_facsimile_variants"


def test_source_subject_is_not_reconstructed_to_match_familiar_text():
    from fatebridge.core.meihua_weather import weather_ruleset

    rule = next(
        r for r in weather_ruleset()["rules"] if r["id"] == "long_rain_qian_clears"
    )
    assert "乾為老陽之極" in rule["quote"]
    assert rule["source_witnesses"][0]["selected_span"] == "久雨必晴"
    assert (
        rule["textual_status"]
        == "fixed_transcription_subject_not_confirmed_in_selected_facsimile"
    )


def test_frozen_witness_integration_does_not_become_textual_truth():
    report = audit_weather_chapter(REFERENCES)
    assert report["selected_checks_passed"], report
    assert report["literal_mathematical_probe_count"] == 16
    assert report["rule_linked_selected_reading_count"] == 35
    assert report["current_profile_rule_count"] == 40
    assert report["current_rules_not_reviewed_by_this_v5_corpus"] == [
        "autumn_metal_clear",
        "li_above_gen_evening_rain",
        "li_above_gen_morning_clear",
        "spring_earth_rain",
        "winter_kan_snow",
    ]
    assert report["unique_nlc_selected_spans"] < 35
    assert len(report["chapter_inventory"]["units"]) == 36
    assert any(
        row["status"].startswith("not_implemented")
        for row in report["chapter_inventory"]["units"]
    )
    assert report["independent_human_expert_review"] == "not_performed"
    assert not report["primary_transcription_truth_automatically_proved"]
    assert not report["complete_chapter_semantic_conformance_established"]
    assert (
        report["actual_model_runs"]
        == report["prospective_weather_observations_added"]
        == 0
    )


def test_weather_oracle_disagreement_stays_a_failure_after_rehash(tmp_path):
    reference = tmp_path / "fixtures/meihua_weather_chapter_v5"
    shutil.copytree(REFERENCES, reference)
    for name in ["meihua_weather_gen_v4", "meihua_v1"]:
        shutil.copytree(REFERENCES.parent / name, reference.parent / name)
    path = reference / "cases.json"
    data = json.loads(path.read_text())
    data["cases"][0]["expected"]["status"] = "not_met"
    path.write_text(json.dumps(data, ensure_ascii=False))
    with pytest.raises(ValueError, match="oracle or collation changed"):
        audit_weather_chapter(reference)
    path = reference / "manifest.json"
    data = json.loads(path.read_text())
    data["files"]["cases.json"] = hashlib.sha256(
        (reference / "cases.json").read_bytes()
    ).hexdigest()
    path.write_text(json.dumps(data, ensure_ascii=False))
    report = audit_weather_chapter(reference)
    assert not report["selected_checks_passed"]
    assert report["cases"][0]["disagreements"][0]["field"] == "status"


def test_cloudy_is_not_a_dry_label_and_autumn_is_not_extraordinary_thunder():
    output = calculate(CASES[10])
    weather = output["interpretation"]["weather"]
    row = next(r for r in weather["rule_trace"] if r["rule_id"] == "many_dui_cloudy")
    assert row["tags"] == ["cloudy"]
    assert "symbol_kan" in weather["matched_rule_ids"]
    assert weather["single_forecast"] is None
    for case in CASES[3:5]:
        output = calculate(case)
        row = next(
            r
            for r in output["interpretation"]["weather"]["rule_trace"]
            if r["rule_id"] == "many_zhen_spring_summer"
        )
        assert row["status"] == "not_met"
        assert not any(
            "非常之雷" in r["reading"]
            for r in output["interpretation"]["weather"]["selected_readings"]
        )


@pytest.mark.parametrize(
    "index", [0, 5, 7, 9, 13, 14, 15], ids=lambda i: CASES[i]["id"]
)
def test_weather_selected_witnesses_and_conditions_agree_on_three_transports(
    index, surface_calls
):
    from fatebridge.application.examples import suggested_fields
    from tests.support.transports import SPECS, business, call_cli, native

    spec = SPECS["meihua_cast"]
    case = CASES[index]
    fields = suggested_fields(spec, view="weather")
    payload = {
        "casting": case["casting"],
        "interpretation_topic": "weather",
        "weather_context": case["context"],
    }
    response, protocol, code, local = surface_calls(
        spec,
        payload,
        projection={
            **{"fields": fields, "strict_fields": True},
            "response_char_limit": 0,
        },
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        weather = output["interpretation"]["weather"]
        assert weather["version"] == "1.7.0"
        assert (
            "meihua_weather_v1@1.7.0" in output["run_metadata"]["provenance"]["ruleset"]
        )
        selected = {r["rule_id"]: r for r in weather["selected_readings"]}
        if case["expected"]["status"] == "matched":
            row = selected[case["expected"]["rule_id"]]
            assert row["source_witnesses"]
            assert row["effective_status"] == case["expected"]["effective_status"]
        elif case["expected"]["status"] == "pending_context":
            assert case["expected"]["rule_id"] in weather["pending_rule_ids"]
