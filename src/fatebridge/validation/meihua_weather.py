"""Frozen mathematical weather-rule probes, never observed forecasting results."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.meihua_weather import weather_ruleset
from fatebridge.core.meihua_weather_controls import weather_control_profile
from fatebridge.services.meihua import calculate_meihua_cast


def audit_weather_rules(directory: Path) -> dict[str, Any]:
    package = Path(__file__).resolve().parents[1]
    files = [
        "core/divination.py",
        "core/meihua.py",
        "core/meihua_casting.py",
        "core/meihua_weather.py",
        "core/meihua_weather_attributions.py",
        "core/meihua_weather_time_scope.py",
        "core/meihua_weather_cast_variants.py",
        "core/meihua_weather_controls.py",
        "core/meihua_weather_frequency.py",
        "core/requests/meihua.py",
        "services/meihua.py",
        "validation/meihua_weather.py",
        "data/meihua/weather-v1.json",
        "data/meihua/weather-attributions-nlc1925-v1.json",
        "data/meihua/weather-controls-v1.json",
        "data/meihua/weather-research-validation-v1.json",
    ]
    hashes = {
        name: hashlib.sha256((package / name).read_bytes()).hexdigest()
        for name in files
    }
    manifest_bytes = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    case_bytes = (directory / "cases.json").read_bytes()
    if hashlib.sha256(case_bytes).hexdigest() != manifest["cases_sha256"]:
        raise ValueError("Frozen weather condition probes changed")
    reference = manifest["reference"]
    source_path = (directory / reference["file"]).resolve()
    if not source_path.is_relative_to(directory.parent.resolve()):
        raise ValueError("Weather source escapes fixture collection")
    source_bytes = source_path.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != reference["sha256"]:
        raise ValueError("Frozen weather source changed")
    source = source_bytes.decode("utf-8")
    cases = json.loads(case_bytes)["cases"]
    if len(cases) != 8 or manifest["case_count"] != 8:
        raise ValueError("Weather v1 requires all eight condition probes")
    profile = weather_ruleset()
    quotes = [
        {"rule_id": rule["id"], "matched": rule["quote"] in source}
        for rule in [dict(profile["entry_rule"], id="weather_entry"), *profile["rules"]]
    ]
    reports = []
    for case in cases:
        output = calculate_meihua_cast(
            casting=case["casting"],
            interpretation_topic="weather",
            weather_context=case["context"],
        )
        weather = output["interpretation"]["weather"]
        statuses = {r["rule_id"]: r["status"] for r in weather["rule_trace"]}
        actual = {
            "counts": weather["trigram_counts"],
            "rule_status": {key: statuses[key] for key in case["rule_status"]},
        }
        reports.append(
            {
                "id": case["id"],
                "disagreements": [
                    {"field": field, "expected": case[field], "actual": actual[field]}
                    for field in ["counts", "rule_status"]
                    if case[field] != actual[field]
                ],
            }
        )
    if any(
        hashlib.sha256((package / name).read_bytes()).hexdigest() != digest
        for name, digest in hashes.items()
    ):
        raise ValueError("Weather implementation changed during audit")
    return {
        "audit_id": "meihua_weather_v1",
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "implementation_sha256": hashes,
        "selected_rule_checks_passed": all(q["matched"] for q in quotes)
        and all(not r["disagreements"] for r in reports),
        "independent_mathematical_probe_count": 8,
        "source_clause_count": len(profile["rules"]),
        "source_clause_count_scope": "legacy_runtime_reading_count_not_distinct_source_clauses_or_observations",
        "runtime_reading_count": len(profile["rules"]),
        "unique_fixed_quote_count": len({r["quote"] for r in profile["rules"]}),
        "numerical_probe_rule_ids": sorted(
            {name for case in cases for name in case["rule_status"]}
        ),
        "quote_only_rule_ids": sorted(
            {rule["id"] for rule in profile["rules"]}
            - {name for case in cases for name in case["rule_status"]}
        ),
        "quote_checks": quotes,
        "cases": reports,
        "unresolved": profile["unresolved"],
        "full_classical_conformance_established": False,
        "real_model_semantic_acceptance": "not_tested",
        "real_world_efficacy": "not_tested",
        "real_world_prospective_sample_count": 0,
        "authority_certified": False,
    }


def audit_weather_controls(directory: Path) -> dict[str, Any]:
    """Check the separate direct-control probes and the borrowed-item frequency example."""
    package = Path(__file__).resolve().parents[1]
    files = [
        "core/divination.py",
        "core/meihua_casting.py",
        "core/meihua_weather.py",
        "core/meihua_weather_time_scope.py",
        "core/meihua_weather_cast_variants.py",
        "core/meihua_weather_controls.py",
        "core/meihua_weather_frequency.py",
        "services/meihua.py",
        "validation/meihua_weather.py",
        "data/meihua/weather-v1.json",
        "data/meihua/weather-controls-v1.json",
        "data/meihua/weather-research-validation-v1.json",
    ]
    hashes = {
        name: hashlib.sha256((package / name).read_bytes()).hexdigest()
        for name in files
    }
    manifest_bytes = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    case_bytes = (directory / "cases.json").read_bytes()
    if hashlib.sha256(case_bytes).hexdigest() != manifest["cases_sha256"]:
        raise ValueError("Frozen weather-control probes changed")
    materials = {}
    for reference in manifest["references"]:
        path = (directory / reference["file"]).resolve()
        if not path.is_relative_to(directory.parent.resolve()):
            raise ValueError("Weather-control source escapes fixture collection")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != reference["sha256"]:
            raise ValueError("Frozen weather-control source changed")
        materials[reference["id"]] = raw.decode("utf-8")
    cases = json.loads(case_bytes)["cases"]
    if len(cases) != 9 or manifest["case_count"] != 9:
        raise ValueError("Control v1 requires all nine probes")
    profile = weather_control_profile()
    quotes = [
        {
            "rule_id": r.get("id", "frequency_reference"),
            "matched": r["quote"] in materials[r["source_id"]],
        }
        for r in [*profile["rules"], profile["frequency_reference"]]
    ]
    reports = []
    for case in cases:
        result = calculate_meihua_cast(
            casting=case["casting"],
            interpretation_topic="weather",
            weather_context=case["context"],
        )
        weather = result["interpretation"]["weather"]
        frequencies = {r["scope"]: r for r in weather["frequency_views"]}
        readings = {r["rule_id"]: r for r in weather["rule_trace"]}
        rule_id = case["expected"]["effective_rule"]["rule_id"]
        actual = {
            "six_counts": frequencies["six_positions"]["trigram_counts"],
            "five_counts": frequencies["five_roles_static_once"]["trigram_counts"],
            "control_statuses": {
                r["rule_id"]: r["status"] for r in weather["controls"]
            },
            "effective_rule": {
                "rule_id": rule_id,
                "status": readings[rule_id]["effective_status"],
            },
        }
        if set(actual) != set(case["expected"]):
            raise ValueError("Incomplete weather-control oracle")
        reports.append(
            {
                "id": case["id"],
                "disagreements": [
                    {"field": field, "expected": expected, "actual": actual[field]}
                    for field, expected in case["expected"].items()
                    if actual[field] != expected
                ],
            }
        )
    if any(
        hashlib.sha256((package / name).read_bytes()).hexdigest() != value
        for name, value in hashes.items()
    ):
        raise ValueError("Weather-control implementation changed during audit")
    return {
        "audit_id": "meihua_weather_controls_v1",
        "implementation_sha256": hashes,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "selected_control_checks_passed": all(q["matched"] for q in quotes)
        and all(not r["disagreements"] for r in reports),
        "existing_classical_frequency_example_count": 1,
        "additional_mathematical_probe_count": 8,
        "quote_checks": quotes,
        "cases": reports,
        "unresolved": profile["unresolved"],
        "unique_classical_frequency_scope_established": False,
        "full_classical_conformance_established": False,
        "real_world_efficacy": "not_established",
        "real_world_prospective_sample_count": 0,
        "authority_certified": False,
    }


def audit_weather_gen_rain(directory: Path) -> dict[str, Any]:
    """Keep the conditional clear-sky clause distinct from generic rain stopping."""
    package = Path(__file__).resolve().parents[1]
    names = [
        "core/meihua_weather.py",
        "core/meihua_weather_time_scope.py",
        "core/meihua_weather_cast_variants.py",
        "core/meihua_weather_controls.py",
        "core/meihua_weather_frequency.py",
        "services/meihua.py",
        "data/meihua/weather-v1.json",
        "validation/meihua_weather.py",
    ]
    hashes = {n: hashlib.sha256((package / n).read_bytes()).hexdigest() for n in names}
    manifest_raw = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    for name, expected in manifest["files_sha256"].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError("Gen-rain reference escapes its frozen bundle")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Frozen Gen-rain reference changed")
    ref = manifest["fixed_transcription"]
    path = (directory / ref["file"]).resolve()
    if not path.is_relative_to(directory.parent.resolve()):
        raise ValueError("Gen-rain transcription escapes fixture collection")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise ValueError("Frozen Gen-rain transcription changed")
    collation = json.loads((directory / "collation.json").read_text())
    readings = {r["id"]: r for r in collation["readings"]}
    rule = next(
        r for r in weather_ruleset()["rules"] if r["id"] == "many_gen_long_rain_clear"
    )
    quote_passed = (
        rule["quote"] == readings["gen_many_long_rain_clear"]["span"]
        and rule["quote"] in raw.decode()
    )
    cases = json.loads((directory / "cases.json").read_text())["cases"]
    if len(cases) != 7 or manifest["case_count"] != 7:
        raise ValueError("Retain all seven Gen-rain probes")
    reports = []
    for case in cases:
        weather = calculate_meihua_cast(
            casting=case["casting"],
            interpretation_topic="weather",
            weather_context=case["context"],
        )["interpretation"]["weather"]
        rows = {r["rule_id"]: r for r in weather["rule_trace"]}
        selected = rows["many_gen_long_rain_clear"]
        actual = {
            "six_slots": [r["trigram"] for r in weather["trigram_slots"]],
            "gen_counts": [
                v["trigram_counts"]["艮"] for v in weather["frequency_views"]
            ],
            "many_gen_status": selected["status"],
            "many_gen_effective_status": selected["effective_status"],
            "rain_stopping_status": rows["long_rain_gen_stops"]["status"],
        }
        reports.append(
            {
                "id": case["id"],
                "disagreements": [
                    {"field": k, "expected": v, "actual": actual[k]}
                    for k, v in case["expected"].items()
                    if actual[k] != v
                ],
            }
        )
    if any(
        hashlib.sha256((package / n).read_bytes()).hexdigest() != h
        for n, h in hashes.items()
    ):
        raise ValueError("Gen-rain implementation changed during audit")
    return {
        "audit_id": "meihua_weather_gen_v4",
        "profile": "meihua_weather_v1@" + weather_ruleset()["version"],
        "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "implementation_sha256": hashes,
        "selected_checks_passed": quote_passed
        and all(not r["disagreements"] for r in reports),
        "selected_manual_facsimile_readings": 2,
        "manual_mathematical_probe_count": 7,
        "quote_matched_frozen_reading_and_transcription": quote_passed,
        "cases": reports,
        "long_clear_anaphor_uniquely_adjudicated": False,
        "full_chapter_conformance_established": False,
        "manual_transcription_truth_automatically_proved": False,
        "real_weather_observation_count": 0,
        "real_model_semantic_acceptance": "not_tested",
        "predictive_efficacy_established": False,
        "authority_certified": False,
    }
