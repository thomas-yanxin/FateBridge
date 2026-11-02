"""Frozen seasonal diagrams and per-source readings, not prediction outcomes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.meihua_weather import weather_ruleset
from fatebridge.services.meihua import calculate_meihua_cast


def audit_weather_seasonal(directory: Path) -> dict[str, Any]:
    directory = directory.resolve()
    package = Path(__file__).resolve().parents[1]
    names = [
        "core/divination.py",
        "core/meihua_casting.py",
        "core/meihua_weather.py",
        "core/meihua_weather_time_scope.py",
        "core/meihua_weather_controls.py",
        "core/meihua_weather_frequency.py",
        "core/meihua_weather_cast_variants.py",
        "core/requests/meihua.py",
        "services/meihua.py",
        "data/meihua/weather-v1.json",
        "data/meihua/weather-controls-v1.json",
        "validation/meihua_weather_seasonal.py",
    ]
    implementation = {
        name: hashlib.sha256((package / name).read_bytes()).hexdigest()
        for name in names
    }
    manifest_raw = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    for name, digest in manifest["files"].items():
        path = (directory / name).resolve()
        if (
            not path.is_relative_to(directory)
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise ValueError("Frozen seasonal diagrams or source readings changed")
    materials = {}
    for reference in manifest["references"]:
        path = (directory / reference["file"]).resolve()
        if (
            not path.is_relative_to(directory.parent)
            or hashlib.sha256(path.read_bytes()).hexdigest() != reference["sha256"]
        ):
            raise ValueError("Frozen seasonal source changed")
        materials[reference["id"]] = path.read_bytes()
    cases = json.loads((directory / "cases.json").read_text())["cases"]
    collation = json.loads((directory / "collation.json").read_text())
    if len(cases) != 16 or manifest["case_count"] != 16:
        raise ValueError("Retain all sixteen declared seasonal probes")
    profile = weather_ruleset()
    rules = {r["id"]: r for r in profile["rules"]}
    fixed_source = materials["fixed-volume-2"].decode()
    source_checks = []
    for reading in collation["readings"]:
        rule = rules[reading["rule_id"]]
        witness = next(
            w
            for w in rule["source_witnesses"]
            if w["source_id"] == "meihua-gen-nlc-1925"
        )
        source_checks.append(
            {
                "rule_id": rule["id"],
                "fixed_quote_matches": rule["quote"] == reading["fixed_quote"]
                and rule["quote"] in fixed_source,
                "runtime_source_is_fixed_transcription": rule["source_id"]
                == "meihua-volume-2",
                "selected_witness_matches_frozen_assistant_reading": witness[
                    "selected_span"
                ]
                == reading["nlc_selected_span"]
                and witness["original_pdf_index"] == 63,
                "textual_status_matches": rule["textual_status"]
                == reading.get(
                    "subject_status",
                    reading.get(
                        "graph_status",
                        "fixed_transcription_wei_vs_selected_facsimile_zhi",
                    ),
                ),
            }
        )
    rows = []
    for case in cases:
        result = calculate_meihua_cast(
            casting=case["casting"],
            interpretation_topic="weather",
            weather_context=case["context"],
        )
        cast = result["meihua"]
        weather = result["interpretation"]["weather"]
        traces = {r["rule_id"]: r for r in weather["rule_trace"]}
        expected = case["expected"]
        actual = {
            "base_code": cast["base_hexagram"]["binary_code"],
            "moving_line": cast["seed"]["moving_line"],
            "changed_code": cast["changed_hexagram"]["binary_code"],
            "mutual_code": cast["mutual_hexagram"]["binary_code"],
            "six_slots": [
                r["trigram"].translate(str.maketrans({"兑": "兌", "离": "離"}))
                for r in weather["trigram_slots"]
            ],
            "rule_status": {
                name: traces[name]["status"] for name in expected["rule_status"]
            },
        }
        if probe := expected.get("qualified_control_probe"):
            actual["qualified_control_probe"] = {
                "controlled_rule": probe["controlled_rule"],
                "controlled_tags": traces[probe["controlled_rule"]]["controlled_tags"],
                "uncontrolled_rule": probe["uncontrolled_rule"],
                "effective_tags": traces[probe["uncontrolled_rule"]]["effective_tags"],
            }
        rows.append(
            {
                "id": case["id"],
                "actual": actual,
                "disagreements": [
                    {"field": key, "expected": value, "actual": actual[key]}
                    for key, value in expected.items()
                    if actual[key] != value
                ],
            }
        )
    if any(
        hashlib.sha256((package / name).read_bytes()).hexdigest() != digest
        for name, digest in implementation.items()
    ):
        raise ValueError("Seasonal implementation changed during audit")
    return {
        "audit_id": "meihua_weather_seasonal_v6",
        "ruleset": profile["id"] + "@" + profile["version"],
        "implementation_sha256": implementation,
        "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "selected_checks_passed": not any(row["disagreements"] for row in rows)
        and all(
            all(v for k, v in row.items() if k != "rule_id") for row in source_checks
        ),
        "literal_mathematical_probe_count": 16,
        "new_seasonal_rule_count": 3,
        "diagram_label_normalization": "兑/兌 and 离/離 aliases only; no line or trigram transformation",
        "runtime_basis": collation["runtime_basis"],
        "source_checks": source_checks,
        "cases": rows,
        "unresolved_in_this_increment": collation["unresolved_in_this_increment"],
        "selected_facsimile_reading_truth_independently_proved": False,
        "independent_human_expert_review": "not_performed",
        "complete_chapter_semantic_conformance_established": False,
        "actual_model_runs": 0,
        "prospective_weather_observations_added": 0,
        "predictive_efficacy_established": False,
        "authority_certified": False,
    }
