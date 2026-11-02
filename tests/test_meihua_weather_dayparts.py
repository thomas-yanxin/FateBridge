"""Original dayparts stay separate, date-free and tied to actual cast geometry."""

import asyncio
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from fatebridge.core.meihua_weather import weather_ruleset
from fatebridge.core.meihua_weather_time_scope import compare_weather_time_scopes
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from fatebridge.validation.meihua_weather_dayparts import (
    NEW_RULES,
    audit_weather_dayparts,
    synthetic_scope_traces,
)
from tests.test_agentic_nested_outputs import rest  # noqa: F401

REFERENCES = Path(__file__).parent / "fixtures/meihua_weather_dayparts_v7"
CASES = json.loads((REFERENCES / "cases.json").read_text())["cases"]
SCOPE_CASES = json.loads((REFERENCES / "scope-cases.json").read_text())["cases"]
TIME_CASE = json.loads((REFERENCES / "time-case.json").read_text())


@pytest.fixture(scope="module")
def audited():
    return audit_weather_dayparts(REFERENCES)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_original_clause_uses_the_actual_ordered_hexagram_pair(case, audited):
    row = next(r for r in audited["cases"] if r["id"] == case["id"])
    assert not row["disagreements"], row


@pytest.mark.parametrize("case", SCOPE_CASES, ids=lambda c: c["id"])
def test_declared_time_scope_comparisons_remain_separate(case, audited):
    row = next(r for r in audited["scope_cases"] if r["id"] == case["id"])
    assert not row["disagreements"], row


def test_diagram_constraint_does_not_adjudicate_the_ambiguous_following_clause(audited):
    assert audited["selected_checks_passed"]
    assert audited["mutual_diagram_check_passed"]
    assert (
        len(audited["mutual_codes"]) == 16 and "001101" not in audited["mutual_codes"]
    )
    assert not audited["following_clause_parse_adjudicated"]
    assert not audited["source_clock_bounds_or_target_dates_defined"]
    assert not audited["complete_classical_conformance_established"]
    assert not audited["predictive_efficacy_established"]
    assert not audited["authority_certified"]


def test_previous_38_rule_bodies_and_first_16_oracles_remain_frozen():
    baseline = json.loads((REFERENCES / "baseline-profile.json").read_text())
    current = weather_ruleset()
    assert current["rules"][:38] == baseline["rules"]
    assert current["version"] == "1.7.0" and len(current["rules"]) == 40
    manifest = json.loads((REFERENCES / "manifest.json").read_text())
    assert (
        hashlib.sha256((REFERENCES / "cases.json").read_bytes()).hexdigest()
        == manifest["files"]["cases.json"]
    )
    assert manifest["implementation_changed_before_freeze"] is False


def test_unknown_daypart_cannot_silently_become_an_all_day_scope():
    traces = synthetic_scope_traces(SCOPE_CASES[0]["rows"])
    traces[0]["time_scope"] = "every_hour"
    with pytest.raises(ValueError, match="Unknown weather source time scope"):
        compare_weather_time_scopes(traces)


def test_known_analysis_date_is_not_an_invented_daypart_target_date():
    manifest = json.loads((REFERENCES / "time-case-manifest.json").read_text())
    assert (
        hashlib.sha256((REFERENCES / "time-case.json").read_bytes()).hexdigest()
        == manifest["file_sha256"]
    )
    ref = REFERENCES / manifest["reference"]["file"]
    assert (
        hashlib.sha256(ref.read_bytes()).hexdigest() == manifest["reference"]["sha256"]
    )
    text = ref.read_text(encoding="utf-8-sig")
    assert "初三" in next(
        line for line in text.splitlines() if line.startswith("2026年2月19日")
    )
    result = calculate_meihua_analysis(**TIME_CASE["input"])
    cast = result["meihua"]
    lunar = result["calendar_context"]["lunar_calendar"]
    expected = TIME_CASE["expected"]
    for key in ["year", "month", "day"]:
        assert lunar[key] == expected["lunar_" + key]
    for key in ["year_branch", "hour_branch", "moving_line"]:
        assert cast["seed"][key] == expected[key]
    for key in ["base", "changed", "mutual"]:
        assert cast[key + "_hexagram"]["binary_code"] == expected[key + "_code"]
    assert result["analysis_context"]["analysis_datetime"] == "2026-02-19 06:00:00"
    comparison = result["interpretation"]["weather"]["time_scope_comparison"]
    assert comparison["policy"]["target_calendar_date"] is None
    assert comparison["policy"]["local_clock_intervals"] is None
    assert comparison["policy"]["dawn_or_sunset_mapping"] is None
    assert comparison["policy"]["display_order_is_event_chronology"] is False
    assert comparison["has_explicit_daypart_readings"]


def test_morning_and_evening_are_not_added_to_legacy_unscoped_conflicts():
    result = calculate_meihua_cast(
        casting=CASES[0]["casting"], interpretation_topic="weather"
    )
    weather = result["interpretation"]["weather"]
    assert not any(row["tags"] == ["clear", "rain"] for row in weather["conflicts"])
    comp = weather["time_scope_comparison"]
    assert len(comp["separated_daypart_pairs"]) == 1
    assert not comp["same_daypart_conflicts"]
    assert comp["unresolved_time_relations"]
    assert all(
        row["relationship"] == "unspecified_scope_not_all_day"
        for row in comp["unresolved_time_relations"]
    )
    assert weather["single_forecast"] is None


def test_scope_information_is_computed_for_each_retained_cast():
    result = calculate_meihua_cast(
        casting=CASES[14]["casting"],
        interpretation_topic="weather",
        weather_context=CASES[14]["context"],
    )
    weather = result["interpretation"]["weather"]
    rows = {v["line_sum_basis"]: v for v in weather["casting_variants"]}
    assert not rows["raw_counts"]["time_scope_comparison"][
        "has_explicit_daypart_readings"
    ]
    assert rows["trigram_numbers"]["time_scope_comparison"][
        "has_explicit_daypart_readings"
    ]
    assert weather["casting_comparison"]["changed_rule_ids"] == list(NEW_RULES)
    assert weather["casting_comparison"]["changed_control_ids"] == []


def test_changed_expected_scope_is_not_accepted_merely_by_rehashing(tmp_path):
    target = tmp_path / "fixtures/meihua_weather_dayparts_v7"
    shutil.copytree(REFERENCES, target)
    for name in ["meihua_v1", "meihua_weather_gen_v4"]:
        shutil.copytree(REFERENCES.parent / name, target.parent / name)
    path = target / "scope-cases.json"
    cases = json.loads(path.read_text())
    cases["cases"][0]["expected"]["legacy_conflicts"] = 1
    path.write_text(json.dumps(cases))
    with pytest.raises(ValueError, match="Frozen daypart"):
        audit_weather_dayparts(target)
    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"]["scope-cases.json"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    assert not audit_weather_dayparts(target)["selected_checks_passed"]


@pytest.mark.parametrize(
    "audit_name,reference_name",
    [
        ("rules", "meihua_weather_v1"),
        ("controls", "meihua_weather_controls_v1"),
        ("frequency", "meihua_weather_frequency_v2"),
        ("casts", "meihua_weather_cast_variants_v3"),
        ("gen", "meihua_weather_gen_v4"),
        ("chapter", "meihua_weather_chapter_v5"),
        ("seasonal", "meihua_weather_seasonal_v6"),
        ("dayparts", "meihua_weather_dayparts_v7"),
    ],
)
def test_each_weather_auditor_rejects_time_scope_source_drift(
    audit_name, reference_name, monkeypatch
):
    from fatebridge.core import meihua_weather_time_scope
    from fatebridge.validation.meihua_weather import (
        audit_weather_controls,
        audit_weather_gen_rain,
        audit_weather_rules,
    )
    from fatebridge.validation.meihua_weather_cast_variants import (
        audit_weather_cast_variants,
    )
    from fatebridge.validation.meihua_weather_chapter import audit_weather_chapter
    from fatebridge.validation.meihua_weather_frequency import audit_weather_frequency
    from fatebridge.validation.meihua_weather_seasonal import audit_weather_seasonal

    auditors = {
        "rules": audit_weather_rules,
        "controls": audit_weather_controls,
        "frequency": audit_weather_frequency,
        "casts": audit_weather_cast_variants,
        "gen": audit_weather_gen_rain,
        "chapter": audit_weather_chapter,
        "seasonal": audit_weather_seasonal,
        "dayparts": audit_weather_dayparts,
    }
    target = Path(meihua_weather_time_scope.__file__).resolve()
    original = Path.read_bytes
    reads = 0

    def changed_after_initial_fingerprint(path):
        nonlocal reads
        data = original(path)
        if path.resolve() == target:
            reads += 1
            if reads > 1:
                return data + b"\n# simulated source drift, without changing the file\n"
        return data

    monkeypatch.setattr(Path, "read_bytes", changed_after_initial_fingerprint)
    with pytest.raises(ValueError, match="changed during audit"):
        auditors[audit_name](REFERENCES.parent / reference_name)
    assert reads >= 2


@pytest.mark.parametrize("tool", ["meihua_analysis", "meihua_cast"])
def test_dayparts_and_unresolved_time_relations_agree_across_surfaces(
    tool, rest, tmp_path, capsys
):
    from fatebridge.application.examples import suggested_fields
    from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native

    spec = SPECS[tool]
    payload = (
        dict(TIME_CASE["input"])
        if tool == "meihua_analysis"
        else {"casting": CASES[0]["casting"], "interpretation_topic": "weather"}
    )
    fields = [
        *suggested_fields(spec, view="weather"),
        "interpretation.weather.single_forecast",
    ]
    http = rest.post(
        spec.rest_path,
        json=payload,
        params=[
            *(("fields", f) for f in fields),
            ("strict_fields", "true"),
            ("response_char_limit", 0),
        ],
    )
    code, local = call_cli(
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
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [http.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        w = output["interpretation"]["weather"]
        assert w["version"] == "1.7.0"
        comparison = w["time_scope_comparison"]
        assert (
            comparison["has_explicit_daypart_readings"]
            and comparison["separated_daypart_pairs"]
        )
        assert comparison["policy"]["target_calendar_date"] is None
        readings = {r["rule_id"]: r for r in w["selected_readings"]}
        assert readings[NEW_RULES[0]]["time_scope"] == "morning"
        assert readings[NEW_RULES[1]]["time_scope"] == "evening"
        for name in NEW_RULES:
            assert readings[name]["quote"] == "離在艮上，暮雨朝晴"
            assert (
                readings[name]["source_witnesses"][0]["selected_span"]
                == "離在艮上暮雨朝晴"
            )
        assert w["single_forecast"] is None
