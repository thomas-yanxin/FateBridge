"""Rain stopping, conditional clear sky, and an unresolved anaphor stay distinct."""

import asyncio
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from fatebridge.application.examples import suggested_fields
from fatebridge.services.meihua import calculate_meihua_cast
from fatebridge.validation.meihua_weather import audit_weather_gen_rain
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

REFERENCES = Path(__file__).parents[1] / "fixtures/meihua_weather_gen_v4"
CASES = json.loads((REFERENCES / "cases.json").read_text())["cases"]


def test_source_readings_and_all_frozen_manual_probes():
    report = audit_weather_gen_rain(REFERENCES)
    assert report["selected_checks_passed"], report["cases"]
    assert report["selected_manual_facsimile_readings"] == 2
    assert report["manual_mathematical_probe_count"] == 7
    assert not report["long_clear_anaphor_uniquely_adjudicated"]
    assert not report["full_chapter_conformance_established"]
    assert report["real_weather_observation_count"] == 0
    assert not report["authority_certified"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_many_gen_clear_is_not_the_generic_single_gen_rain_stop(case):
    result = calculate_meihua_cast(
        casting=case["casting"],
        interpretation_topic="weather",
        weather_context=case["context"],
    )
    weather = result["interpretation"]["weather"]
    trace = {r["rule_id"]: r for r in weather["rule_trace"]}
    clear = trace["many_gen_long_rain_clear"]
    stop = trace["long_rain_gen_stops"]
    assert stop["tags"] == ["rain_stopping"] and clear["tags"] == ["clear"]
    assert clear["status"] == case["expected"]["many_gen_status"]
    assert clear["effective_status"] == case["expected"]["many_gen_effective_status"]
    readings = {r["rule_id"]: r for r in weather["selected_readings"]}
    if clear["status"] == "matched":
        assert readings[clear["rule_id"]]["quote"] == "艮多則久雨必晴"
        assert (
            "interpretation.weather.context.prior_condition"
            in readings[clear["rule_id"]]["fact_paths"]
        )
        if clear["effective_status"] == "conditional_on_unresolved_frequency":
            assert clear["conditional_tags"] == ["clear"]
            assert "频数范围未裁定" in readings[clear["rule_id"]]["reading"]
    else:
        assert clear["rule_id"] not in readings
    if case["id"] == "one_gen_rain_stop_is_not_clear_clause":
        assert stop["status"] == "matched"
        assert not any("clear" in r["effective_tags"] for r in trace.values())
    assert weather["single_forecast"] is None
    assert any("久晴不雨得此亦然" in text for text in weather["ruleset"]["unresolved"])


def test_gen_clear_clause_is_not_cancelled_as_if_it_were_li_fire_clear():
    result = calculate_meihua_cast(
        casting=CASES[0]["casting"],
        interpretation_topic="weather",
        weather_context=CASES[0]["context"],
    )
    rows = {r["rule_id"]: r for r in result["interpretation"]["weather"]["rule_trace"]}
    # Control targets must follow their source dependencies, not all clear tags.
    assert rows["many_gen_long_rain_clear"]["control_checks"] == []
    assert rows["many_gen_long_rain_clear"]["controlled_tags"] == []


def test_corrupt_gen_oracle_cannot_pass_even_after_rehash(tmp_path):
    directory = tmp_path / REFERENCES.name
    shutil.copytree(REFERENCES, directory)
    shutil.copytree(
        REFERENCES.parent / "meihua_v1/sources", tmp_path / "meihua_v1/sources"
    )
    path = directory / "cases.json"
    data = json.loads(path.read_text())
    data["cases"][3]["expected"]["many_gen_status"] = "matched"
    path.write_text(json.dumps(data, ensure_ascii=False))
    with pytest.raises(ValueError, match="reference changed"):
        audit_weather_gen_rain(directory)
    mp = directory / "manifest.json"
    manifest = json.loads(mp.read_text())
    manifest["files_sha256"]["cases.json"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    mp.write_text(json.dumps(manifest))
    report = audit_weather_gen_rain(directory)
    assert not report["selected_checks_passed"]
    assert report["cases"][3]["disagreements"][0]["field"] == "many_gen_status"


@pytest.mark.parametrize(
    "case", [CASES[i] for i in [0, 1, 3, 5]], ids=lambda c: c["id"]
)
def test_gen_clause_conditions_survive_all_three_surfaces(case, rest, tmp_path, capsys):
    spec = SPECS["meihua_cast"]
    payload = {
        "casting": case["casting"],
        "interpretation_topic": "weather",
        "weather_context": case["context"],
    }
    fields = suggested_fields(spec, view="weather")
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[
            *(("fields", f) for f in fields),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
        ],
    )
    exit_code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--weather-context",
            json.dumps(case["context"]),
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(native(spec, payload, fields=fields, strict_fields=True))
    assert response.status_code == 200 and exit_code == 0 and not protocol.is_error
    assert (
        business(response.json())
        == business(local)
        == business(protocol.structured_content)
    )
    for output in [response.json(), local, protocol.structured_content]:
        weather = output["interpretation"]["weather"]
        assert weather["version"] == "1.7.0"
        selected = {r["rule_id"]: r for r in weather["selected_readings"]}
        key = "many_gen_long_rain_clear"
        if case["expected"]["many_gen_status"] == "matched":
            assert (
                selected[key]["effective_status"]
                == case["expected"]["many_gen_effective_status"]
            )
            assert selected[key]["quote"] == "艮多則久雨必晴"
        else:
            assert key not in selected
        if case["expected"]["many_gen_status"] == "pending_context":
            assert key in weather["pending_rule_ids"]
