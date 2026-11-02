"""Audit day-label transcription and supplied offsets, not astronomical truth."""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import date
from importlib.resources import files
from pathlib import Path
from typing import Any

from fatebridge.core.meihua_solar_reference import compare_solar_term_date
from fatebridge.validation.meihua_source_guard import (
    capture_package_sources,
    verify_package_sources,
)


def audit_solar_date_reference(directory: Path) -> dict[str, Any]:
    package = Path(__file__).resolve().parents[1]
    source_guard = capture_package_sources(package)
    manifest_bytes = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    for name, expected in manifest["files"].items():
        p = (directory / name).resolve()
        if not p.is_relative_to(directory.resolve()):
            raise ValueError("Solar-date reference path escapes its frozen bundle")
        if hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen solar-date reference changed: {name}")
    profile_bytes = (
        files("fatebridge.data").joinpath("meihua/solar-dates-hko-v1.json").read_bytes()
    )
    if json.loads(profile_bytes) != json.loads(
        (directory / "source-reading.json").read_bytes()
    ):
        raise ValueError(
            "Runtime solar-date transcription differs from frozen source reading"
        )
    normalizer = str.maketrans(
        {"驚": "惊", "蟄": "蛰", "穀": "谷", "滿": "满", "種": "种", "處": "处"}
    )
    events = 0
    failures = []
    for source in json.loads((directory / "extraction.json").read_bytes()):
        if source["fixture_file"] not in manifest["files"]:
            raise ValueError("Source row locator must refer to a fingerprinted file")
        p = directory / source["fixture_file"]
        content = (
            gzip.decompress(p.read_bytes()) if p.suffix == ".gz" else p.read_bytes()
        )
        if hashlib.sha256(content).hexdigest() != source["raw_content_sha256"]:
            raise ValueError("Frozen solar-date source content fingerprint differs")
        lines = content.decode("utf-8-sig").splitlines()
        for row in source["rows"]:
            fields = lines[row["source_line"] - 1].split()
            y, m, d = (
                fields[0].replace("年", "-").replace("月", "-").rstrip("日").split("-")
            )
            published = date(int(y), int(m), int(d)).isoformat()
            if (
                fields[-1].translate(normalizer) != row["term"]
                or published != row["published_date"]
            ):
                raise ValueError(
                    "Frozen line locator no longer identifies its published label"
                )
            event = compare_solar_term_date(
                {
                    "name": row["term"],
                    "datetime_with_offset": published + "T12:00:00+08:00",
                },
                fact_path="synthetic_supplied_term",
            )
            if (
                event["published_date"] != published
                or event["comparison_status"] != "published_date_match"
                or event["source"]["raw_sha256"] != source["raw_content_sha256"]
            ):
                failures.append(
                    {"source": source["fixture_file"], "row": row, "actual": event}
                )
            events += 1
    case_results = []
    for case in json.loads((directory / "cases.json").read_bytes())["cases"]:
        actual = compare_solar_term_date(case["term"], fact_path="supplied_term")
        passed = (
            actual["comparison_status"] == case["expected_status"]
            and actual["computed_date"] == case["expected_computed_date"]
            and actual["published_date"] == case["expected_published_date"]
            and actual["publisher_named_near_midnight"] is case["publisher_named_event"]
        )
        case_results.append(
            {
                "id": case["id"],
                "kind": case["kind"],
                "passed": passed,
                "expected_status": case["expected_status"],
                "actual_status": actual["comparison_status"],
            }
        )
    if (directory / "manifest.json").read_bytes() != manifest_bytes:
        raise ValueError("Solar-date reference manifest changed during audit")
    for name, expected in manifest["files"].items():
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != expected:
            raise ValueError(
                f"Frozen solar-date reference changed during audit: {name}"
            )
    verify_package_sources(package, source_guard)
    return {
        "audit_version": "meihua_solar_date_reference_audit_v1",
        "selected_checks_passed": events == 4800
        and not failures
        and all(c["passed"] for c in case_results),
        "source_bundle_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "runtime_transcription_sha256": hashlib.sha256(profile_bytes).hexdigest(),
        "source_years": 200,
        "published_date_labels_checked": events,
        "synthetic_noon_instants_are_not_actual_event_times": True,
        "case_results": case_results,
        "failures": failures,
        "all_disagreements_in_supplied_cases_retained": all(
            c["actual_status"] == "published_date_disagreement"
            for c in case_results
            if c["expected_status"] == "published_date_disagreement"
        ),
        "production_calculator_generated_expected_published_dates": False,
        "actual_independent_astronomical_event_observations": 0,
        "actual_model_semantic_evaluations": 0,
        "new_prospective_real_outcomes": 0,
        "lunar_seed_or_month_branch_recomputed": False,
        "physical_calendar_accuracy_established": False,
        "real_predictive_efficacy_established": False,
        "authority_certified": False,
        "package_source_guard": source_guard,
    }
