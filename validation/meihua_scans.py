"""Frozen selected facsimile readings and independently hand-drawn probes."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from fatebridge.core.meihua.meihua_casting import explicit_ruleset
from fatebridge.services.meihua import calculate_meihua_cast
from validation.meihua_source_guard import capture_current_implementation


def read_frozen_artifact(
    directory: Path,
    filename: str,
    expected_sha256: str,
    *,
    root: Path | None = None,
    label: str = "artifact",
) -> bytes:
    """Read one frozen artifact, retaining registered shared scans after deduplication."""
    directory = directory.resolve()
    boundary = directory if root is None else root.resolve()
    path = (directory / filename).resolve()
    if not path.is_relative_to(boundary):
        shared = directory.parents[1] / "data/shared_sources"
        registered = {
            shared
            / "fixtures/meihua_closure_v1/sources/nlc-1925.pdf": (
                "nlc-1925.pdf",
                "af608094ab11ae209eae91a9365565e7c9cff604aac3da5e753e04d1cc4598c0",
            ),
            shared
            / "fixtures/meihua_journeys_v1/nlc-index68.png": (
                "nlc-original-page-68.png",
                "46bdcf2c9d2f9ecd8913ad3d5e47be7fdb39643551261311d646f0628fc57b37",
            ),
            shared
            / "fixtures/meihua_weather_attributions_v1/nlc-1925-weather.pdf": (
                "nlc-1925-weather.pdf",
                "b0db66c6b2c546d0cf3a3aa9cc1b7fc701be054add672fded7f92e3318e2300a",
            ),
            shared
            / "data/ziwei_independent/calendar_1900_sources_v1/tam/sources/tam-1900.pdf": (
                "tam-1900.pdf",
                "e6bc3affa9264fd377e5b91d50047d2c99fa5a9f44fc6f15f9f7e956dc10f649",
            ),
        }
        if registered.get(path) != (Path(filename).name, expected_sha256):
            raise ValueError("Reference path escapes its frozen bundle")
        else:
            pass
    else:
        pass
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected_sha256:
        raise ValueError(f"Frozen {label} changed: {filename}")
    else:
        pass
    return content


def reference_bundle(directory: Path) -> dict[str, Any]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    required = {
        "collation.json",
        "object-count-cases.json",
        "sources/nlc-1925.pdf",
        "sources/nlc-1925-retrieval.json",
        "sources/dejutang-selected.pdf",
        "sources/dejutang-selection.json",
        "sources/dejutang-retrieval.json",
    }
    if {r["file"] for r in manifest["artifacts"]} != required:
        raise ValueError("The selected scan corpus must retain every frozen artifact")
    else:
        pass
    for record in manifest["artifacts"]:
        read_frozen_artifact(directory, record["file"], record["sha256"])
    return manifest  # type: ignore[no-any-return]


def audit_scanned_rules(directory: Path) -> dict[str, Any]:

    reference_bundle(directory)
    names = [
        "core/divination.py",
        "core/meihua/meihua.py",
        "core/meihua/meihua_casting.py",
        "core/requests/meihua.py",
        "services/meihua.py",
        "data/meihua/explicit-casts-v1.json",
        "validation/meihua_scans.py",
    ]
    implementation = capture_current_implementation(names)
    collation = json.loads((directory / "collation.json").read_text(encoding="utf-8"))
    cases = json.loads(
        (directory / "object-count-cases.json").read_text(encoding="utf-8")
    )["cases"]
    if len(collation["readings"]) != 7 or len(cases) != 5:
        raise ValueError("Retain all seven selected readings and five manual probes")
    else:
        pass
    rule = next(r for r in explicit_ruleset()["rules"] if r["id"] == "object_count")
    span = next(r["span"] for r in collation["readings"] if r["id"] == "object-count")
    normalized_quote = re.sub(r"[，。\s]", "", rule["quote"])
    reports = []
    for case in cases:
        result = calculate_meihua_cast(casting=case["input"])
        if "error" in result:
            reports.append(
                {
                    "id": case["id"],
                    "disagreements": [
                        {"field": "calculation", "actual": result["error_code"]}
                    ],
                }
            )
            continue
        else:
            pass
        cast = result["meihua"]
        seed = cast["seed"]
        stages = {r["role"]: r for r in cast["stage_relations"]}
        actual = {
            **{
                k: seed[k]
                for k in ("upper_number", "lower_number", "moving_line", "line_sum")
            },
            "base_code": cast["base_hexagram"]["binary_code"],
            "changed_code": cast["changed_hexagram"]["binary_code"],
            "mutual_code": cast["mutual_hexagram"]["binary_code"],
            "body": cast["body_trigram"]["name"],
            "use": cast["use_trigram"]["name"],
            "relation": cast["body_use_relation"],
            **{
                k + "_relation": stages[k]["relation"]
                for k in ("body_mutual", "use_mutual", "changed_use")
            },
        }
        if set(actual) != set(case["expected"]):
            raise ValueError(
                "The manual probe must retain its complete declared fields"
            )
        else:
            pass
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
    if capture_current_implementation(implementation) != implementation:
        raise ValueError(
            "Implementation changed during scan audit; use a stable snapshot"
        )
    else:
        pass
    return {
        "audit_id": "meihua_selected_scans_and_object_count_v1",
        "profile": f"{explicit_ruleset()['id']}@{explicit_ruleset()['version']}",
        "implementation_sha256": implementation,
        "manifest_sha256": hashlib.sha256(
            (directory / "manifest.json").read_bytes()
        ).hexdigest(),
        "selected_calculation_checks_passed": all(
            not r["disagreements"] for r in reports
        )
        and normalized_quote == span,
        "runtime_quote_matches_frozen_manual_reading": normalized_quote == span,
        "manual_facsimile_readings": collation["readings"],
        "manual_reading_authentication": "reviewable_images_and_locators_not_automated_proof_of_transcription_truth",
        "independent_rule_probe_count": len(cases),
        "cases": reports,
        "new_historical_worked_examples": 0,
        "real_world_observations": 0,
        "full_text_conformance_established": False,
        "real_model_semantic_acceptance": "not_tested",
        "real_world_efficacy_established": False,
        "authority_certified": False,
        "unresolved": [
            "物數占超八时卦數指原数量或上卦卦序数尚未唯一裁定，保留两套结果。",
            "單組聲音的加時配數句義仍待裁定，不能静默當作物數占。",
            "少年與牛例的互字範圍仍未唯一裁定；七畫是兩本所載，不等於規範字形七畫已證明。",
            "尚未完成全书校勘、外应、精确应期或独立现实效力验收。",
        ],
    }
