"""Frozen frequency-premise probes; no observational forecast acceptance."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.meihua_weather import weather_ruleset
from fatebridge.services.meihua import calculate_meihua_cast


def audit_weather_frequency(directory: Path) -> dict[str, Any]:
    package = Path(__file__).resolve().parents[1]
    names = [
        "core/meihua_weather.py",
        "core/meihua_weather_time_scope.py",
        "core/meihua_weather_cast_variants.py",
        "core/meihua_weather_controls.py",
        "core/meihua_weather_frequency.py",
        "core/requests/meihua.py",
        "data/meihua/weather-v1.json",
        "validation/meihua_weather_frequency.py",
    ]
    hashes = {
        name: hashlib.sha256((package / name).read_bytes()).hexdigest()
        for name in names
    }
    manifest_raw = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    case_raw = (directory / "cases.json").read_bytes()
    if hashlib.sha256(case_raw).hexdigest() != manifest["cases_sha256"]:
        raise ValueError("Frozen weather-frequency probes changed")
    materials = {}
    for ref in manifest["references"]:
        path = (directory / ref["file"]).resolve()
        if not path.is_relative_to(directory.parent.resolve()):
            raise ValueError("Weather-frequency source escapes fixture collection")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
            raise ValueError("Frozen weather-frequency source changed")
        materials[ref["id"]] = raw.decode("utf-8")
    scan = manifest["facsimile_collation_manifest"]
    scan_path = (directory / scan["file"]).resolve()
    if not scan_path.is_relative_to(directory.parent.resolve()):
        raise ValueError("Weather-frequency scan manifest escapes fixture collection")
    if hashlib.sha256(scan_path.read_bytes()).hexdigest() != scan["sha256"]:
        raise ValueError("Frozen supporting facsimile manifest changed")
    scan_manifest = json.loads(scan_path.read_bytes())
    collation_ref = next(
        r for r in scan_manifest["artifacts"] if r["file"] == "collation.json"
    )
    collation_raw = (scan_path.parent / "collation.json").read_bytes()
    if hashlib.sha256(collation_raw).hexdigest() != collation_ref["sha256"]:
        raise ValueError("Frozen supporting facsimile collation changed")
    collation = json.loads(collation_raw)
    count_reading = next(
        r for r in collation["readings"] if r["id"] == scan["used_reading"]
    )
    cases = json.loads(case_raw)["cases"]
    if len(cases) != 8 or manifest["case_count"] != 8:
        raise ValueError("Weather-frequency v2 requires all eight probes")
    reports = []
    for case in cases:
        weather = calculate_meihua_cast(
            casting=case["casting"],
            interpretation_topic="weather",
            weather_context=case["context"],
        )["interpretation"]["weather"]
        expected = case["expected"]
        rows = {r["rule_id"]: r for r in weather["rule_trace"]}
        assessment = rows[next(iter(expected["rules"]))]["frequency_assessment"]
        actual = {
            "slots": [s["trigram"] for s in weather["trigram_slots"]],
            "many_trigram": assessment["trigram"],
            "counts": [v["count"] for v in assessment["counting_variants"]],
            "condition_met": [
                v["condition_met"] for v in assessment["counting_variants"]
            ],
            "frequency_status": assessment["status"],
            "rules": {
                key: {
                    "status": rows[key]["status"],
                    "effective_status": rows[key]["effective_status"],
                }
                for key in expected["rules"]
            },
        }
        reports.append(
            {
                "id": case["id"],
                "disagreements": [
                    {"field": key, "expected": value, "actual": actual[key]}
                    for key, value in expected.items()
                    if actual[key] != value
                ],
            }
        )
    profile = weather_ruleset()
    quote_checks = [
        {
            "rule_id": rule["id"],
            "matched": rule["quote"] in materials[rule["source_id"]],
        }
        for rule in profile["rules"]
        if "many" in rule["conditions"]
    ]
    numerical_probe_rule_ids = sorted(
        {key for case in cases for key in case["expected"]["rules"]}
    )
    if any(
        hashlib.sha256((package / name).read_bytes()).hexdigest() != digest
        for name, digest in hashes.items()
    ):
        raise ValueError("Weather-frequency implementation changed during audit")
    return {
        "audit_id": "meihua_weather_frequency_v2",
        "ruleset": f"{profile['id']}@{profile['version']}",
        "implementation_sha256": hashes,
        "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "selected_frequency_checks_passed": all(q["matched"] for q in quote_checks)
        and all(not r["disagreements"] for r in reports),
        "independent_mathematical_probe_count": len(cases),
        "quote_checks": quote_checks,
        "numerical_probe_rule_ids": numerical_probe_rule_ids,
        "quote_only_rule_ids": sorted(
            {row["rule_id"] for row in quote_checks} - set(numerical_probe_rule_ids)
        ),
        "supporting_manual_facsimile_reading": count_reading,
        "cases": reports,
        "raw_six_position_policy_changed": False,
        "unique_classical_frequency_scope_established": False,
        "full_classical_conformance_established": False,
        "real_model_semantic_acceptance": "not_tested",
        "real_world_prospective_sample_count": 0,
        "real_world_efficacy": "not_established",
        "authority_certified": False,
    }
