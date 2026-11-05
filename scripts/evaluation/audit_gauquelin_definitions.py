"""Compare all six native definitions without selecting a historical winner.

This post-result diagnostic cannot identify CFEPP's original algorithm or test
occupational prediction. Its zero exit means complete fixed-input replay with
the previous methods0..2 numerically unchanged, not source agreement.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

from fatebridge.core.astro import runtime
from fatebridge.validation.gauquelin import decode_final3, method_profile
from scripts.evaluation.audit_gauquelin_cfepp import native_sector

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/fixtures/gauquelin-definitions-protocol.json"
PROTOCOL_SHA256 = "60bf73cd6264352b4c717fe07c36dfb26a612b3f479d083ebd68df323f02fdb8"
BASELINE_POLICY = ROOT / "tests/fixtures/gauquelin-definitions-platform-baselines.json"
BASELINE_POLICY_SHA256 = (
    "8fc34591bf5c2f29cc4b2a80ad84a405916605cf82b781ae64e7a205e116010d"
)


def read_baseline(data: bytes) -> tuple[dict, str]:
    policy_bytes = BASELINE_POLICY.read_bytes()
    if hashlib.sha256(policy_bytes).hexdigest() != BASELINE_POLICY_SHA256:
        raise ValueError("frozen_platform_baseline_policy_hash_mismatch")
    approved = json.loads(policy_bytes)["baselines"]
    if data.startswith(b"\x1f\x8b"):
        data = gzip.decompress(data)
    digest = hashlib.sha256(data).hexdigest()
    if digest not in approved.values():
        raise ValueError("frozen_baseline_hash_mismatch")
    return json.loads(data), digest


def compare(data: bytes, baseline: dict, baseline_sha256: str) -> dict:
    if runtime.swe is None:
        raise RuntimeError("Swiss Ephemeris required; no approximate substitute")
    protocol_bytes = PROTOCOL.read_bytes()
    if hashlib.sha256(protocol_bytes).hexdigest() != PROTOCOL_SHA256:
        raise ValueError("frozen_definitions_protocol_hash_mismatch")
    protocol = json.loads(protocol_bytes)
    parameters = protocol["request_parameters"]
    source = decode_final3(data)
    old = {row["case_id"]: row for row in baseline["rows"]}
    if list(old) != [row["case_id"] for row in source]:
        raise ValueError("baseline_source_identity_mismatch")
    rows = []
    for row in source:
        result = {
            key: row[key]
            for key in ("case_id", "cohort", "source_line_sha256", "issues")
        }
        if row["issues"]:
            rows.append(result)
            continue
        if old[row["case_id"]]["source_line_sha256"] != row["source_line_sha256"]:
            raise ValueError("baseline_source_line_mismatch")
        dt = row["universal"]
        jd = float(
            runtime.ephemeris_call(
                "julday",
                dt.year,
                dt.month,
                dt.day,
                dt.hour + dt.minute / 60,
                runtime.swe.GREG_CAL,
            )
        )
        # The published answer is only compared after calculating every method.
        methods = {
            str(method): native_sector(
                jd,
                row["longitude_east"],
                row["latitude"],
                method,
                observer_height_m=parameters["observer_height_m"],
                pressure_hpa=parameters["pressure_hpa"],
                temperature_c=parameters["temperature_c"],
            )
            for method in protocol["methods"]
        }
        result["source_mars12"] = row["mars12"]
        result["methods"] = methods
        for method, value in methods.items():
            value["source_agreement"] = value.get("sector12") == row["mars12"]
            if method in ("0", "1", "2"):
                previous = old[row["case_id"]]["methods"][method]
                value["previous_numerical_values_unchanged"] = all(
                    value.get(key) == previous.get(key)
                    for key in (
                        "status",
                        "sector36",
                        "sector12",
                        "distance_to_12_sector_boundary",
                    )
                )
        rows.append(result)
    cohorts = {}
    for cohort in ("published_1066", "supplementary_54"):
        selected = [row for row in rows if row["cohort"] == cohort]
        cohorts[cohort] = {
            "rows": len(selected),
            "invalid_rows": sum(bool(row["issues"]) for row in selected),
            "methods": {
                str(method): {
                    "status_counts": dict(
                        Counter(
                            row.get("methods", {})
                            .get(str(method), {})
                            .get("status", "invalid_input")
                            for row in selected
                        )
                    ),
                    "source_agreement": sum(
                        row.get("methods", {})
                        .get(str(method), {})
                        .get("source_agreement")
                        is True
                        for row in selected
                    ),
                    "mismatch_ids": [
                        row["case_id"]
                        for row in selected
                        if row.get("methods", {})
                        .get(str(method), {})
                        .get("source_agreement")
                        is False
                    ],
                }
                for method in protocol["methods"]
            },
        }
    complete = all(
        not row["issues"]
        and all(value["status"] == "computed" for value in row["methods"].values())
        for row in rows
    )
    unchanged = complete and all(
        row["methods"][str(method)]["previous_numerical_values_unchanged"]
        for row in rows
        for method in (0, 1, 2)
    )
    return {
        "audit_id": "other-schools-v28-gauquelin-definitions",
        "design": protocol["design"],
        "protocol_sha256": PROTOCOL_SHA256,
        "baseline_sha256": baseline_sha256,
        "baseline_policy_sha256": BASELINE_POLICY_SHA256,
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "runtime": {
            "swiss_version": runtime.swe.version,
            "requested_ephemeris": "Moshier",
            "parameters": parameters,
            "parameter_truth": protocol["parameter_truth"],
            "method_profiles": {str(m): method_profile(m) for m in protocol["methods"]},
        },
        "rows": rows,
        "cohorts": cohorts,
        "diagnostic_complete": complete,
        "previous_numerical_values_unchanged": unchanged,
        "primary_source_sector_reproduction_pass": complete
        and all(row["methods"]["0"]["source_agreement"] for row in rows),
        "historical_cfepp_method_identified": False,
        "real_world_predictive_validation": "not_established",
        "prospective_sample_count": 0,
        "all_four_perfect": False,
        "authority_certified": False,
        "diagnostic_exit_zero_meaning": "Complete replay and unchanged previous numbers only; no historical or predictive acceptance.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Output must not exist; preserve earlier diagnostics")
    baseline, baseline_sha256 = read_baseline(args.baseline.read_bytes())
    result = compare(args.source.read_bytes(), baseline, baseline_sha256)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "diagnostic_complete",
                    "previous_numerical_values_unchanged",
                    "primary_source_sector_reproduction_pass",
                    "historical_cfepp_method_identified",
                )
            }
        )
    )
    return (
        0
        if result["diagnostic_complete"]
        and result["previous_numerical_values_unchanged"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
