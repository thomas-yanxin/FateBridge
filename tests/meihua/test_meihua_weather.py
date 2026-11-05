"""Weather follows its own sourced conditions, not a generic body/use verdict."""

import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.meihua_weather import build_weather_interpretation
from fatebridge.core.requests.meihua import MeihuaCastRequest, MeihuaWeatherContext
from fatebridge.services.meihua import calculate_meihua_cast
from fatebridge.validation.meihua_weather import audit_weather_rules

REFERENCES = Path(__file__).parents[1] / "fixtures/meihua_weather_v1"
CASES = json.loads((REFERENCES / "cases.json").read_text())["cases"]


def test_frozen_weather_probes_and_primary_quotes():
    report = audit_weather_rules(REFERENCES)
    assert report["selected_rule_checks_passed"], report["cases"]
    assert report["source_clause_count"] == 40
    assert report["runtime_reading_count"] == 40
    assert report["unique_fixed_quote_count"] < report["runtime_reading_count"]
    assert "spring_earth_rain" in report["quote_only_rule_ids"]
    assert "spring_earth_rain" not in report["numerical_probe_rule_ids"]
    assert report["independent_mathematical_probe_count"] == 8
    assert report["real_world_prospective_sample_count"] == 0
    assert not report["authority_certified"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_confirmed_context_and_rule_status_are_preserved(case):
    output = calculate_meihua_cast(
        casting=case["casting"],
        interpretation_topic="weather",
        weather_context=case["context"],
    )
    reading = output["interpretation"]
    weather = reading["weather"]
    assert weather["trigram_counts"] == case["counts"]
    statuses = {r["rule_id"]: r["status"] for r in weather["rule_trace"]}
    for rule, status in case["rule_status"].items():
        assert statuses[rule] == status
    assert reading["evidence_scope"]["body_use_applied"] is False
    assert "body_use_reading" not in reading
    assert reading["action_hint"] is None
    assert weather["single_forecast"] is None
    assert sum(weather["trigram_counts"].values()) == 6
    for slot in weather["trigram_slots"]:
        assert "cuo" not in slot["path"] and "zong" not in slot["path"]


def test_weather_is_invariant_to_unrelated_body_use_and_editorial_templates():
    cast = calculate_meihua_cast(casting=CASES[0]["casting"])["meihua"]
    before = build_weather_interpretation(cast, CASES[0]["context"])
    changed = deepcopy(cast)
    for key in ["body_trigram", "use_trigram", "stage_relations", "body_use_relation"]:
        changed[key] = "unrelated-to-weather"
    changed["cuo_hexagram"] = changed["zong_hexagram"] = "unused"
    assert build_weather_interpretation(changed, CASES[0]["context"]) == before


def test_no_implicit_many_threshold_or_season_from_month_strength():
    a = calculate_meihua_cast(
        casting=CASES[0]["casting"],
        season_month_branch="午",
        interpretation_topic="weather",
    )
    b = calculate_meihua_cast(
        casting=CASES[0]["casting"],
        season_month_branch="子",
        interpretation_topic="weather",
    )
    assert a["interpretation"] == b["interpretation"]
    weather = a["interpretation"]["weather"]
    assert weather["context"]["season"] is None
    statuses = {r["rule_id"]: r["status"] for r in weather["rule_trace"]}
    assert statuses["many_li"] == "pending_context"
    assert statuses["many_kan"] == "not_met"
    assert statuses["pure_li_summer_drought"] == "pending_context"


def test_conflicting_rain_and_rain_stop_remain_visible():
    case = CASES[3]
    output = calculate_meihua_cast(
        casting=case["casting"],
        interpretation_topic="weather",
        weather_context=case["context"],
    )
    weather = output["interpretation"]["weather"]
    assert any(c["tags"] == ["rain", "rain_stopping"] for c in weather["conflicts"])
    assert "全部保留" in output["summary"]
    assert weather["single_forecast"] is None


@pytest.mark.parametrize("threshold", [True, 1, 7, "2"])
def test_threshold_must_be_declared_strict_count(threshold):
    with pytest.raises(ValidationError):
        MeihuaWeatherContext(many_min_count=threshold)


def test_context_requires_explicit_weather_branch():
    with pytest.raises(ValidationError, match="weather_context"):
        MeihuaCastRequest(
            casting=CASES[0]["casting"], weather_context={"season": "summer"}
        )
    general = calculate_meihua_cast(casting=CASES[0]["casting"], question="天气如何")
    assert general["interpretation"]["interpretation_topic"] == "general"
    assert general["interpretation"]["weather"] is None


def test_corrupt_expected_weather_count_cannot_pass(tmp_path):
    directory = tmp_path / "meihua_weather_v1"
    shutil.copytree(REFERENCES, directory)
    shutil.copytree(
        REFERENCES.parent / "meihua_v1/sources", tmp_path / "meihua_v1/sources"
    )
    path = directory / "cases.json"
    cases = json.loads(path.read_text())
    cases["cases"][0]["counts"]["离"] = 6
    path.write_text(json.dumps(cases, ensure_ascii=False))
    with pytest.raises(ValueError, match="probes changed"):
        audit_weather_rules(directory)
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["cases_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False))
    report = audit_weather_rules(directory)
    assert not report["selected_rule_checks_passed"]
    assert report["cases"][0]["disagreements"][0]["field"] == "counts"
