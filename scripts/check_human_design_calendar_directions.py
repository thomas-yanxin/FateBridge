"""All original48,000 longitude rows plus independent ICRF direction checks.

The original rows/false acceptances are retained separately. A closer axis or
frame never substitutes for a failed full direction or the original gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.check_human_design_icrf_horizons import mv, rotation, validate_rotation
from scripts.gen_human_design_calendar_directions import ROOT, inputs, read, write

BASE = ROOT / "docs/validation/human-design-calendar-directions-v1"
E = BASE / "evidence"
REFERENCE = E / "icrf-reference-exact-inverse.json.gz"
REFERENCE_SHA256 = "980fe8901a4783e78d0404121e70da75b9de45d0c4f0ca55050b9f4bc6433860"
LEGACY = (
    ROOT
    / "docs/validation/human-design-calendar-retention-v1/evidence/final-full.json.gz"
)


def reference() -> tuple[dict, dict]:
    declared, old_plan, original = inputs()
    if hashlib.sha256(REFERENCE.read_bytes()).hexdigest() != REFERENCE_SHA256:
        raise ValueError("Frozen independent ICRF directions changed")
    value = read(REFERENCE)
    expected = [
        (p["label"], side, p[side])
        for p in original["pairs"]
        for side in ("personality", "design")
    ]
    if (
        value["epoch_count"] != 2400
        or value["physical_direction_count"] != 24000
        or len(value["rows"]) != len(expected)
    ):
        raise ValueError("Incomplete original reference cohort")
    for row, (label, side, epoch) in zip(value["rows"], expected, strict=True):
        if (row["label"], row["side"], row["jd_tt"]) != (
            label,
            side,
            epoch["jd_tt"],
        ) or set(row["directions"]) != set(old_plan["bodies"]):
            raise ValueError("Independent epoch/side/body rebound")
        for body, fact in row["directions"].items():
            if fact["original_fact"] != epoch["positions"][body]:
                raise ValueError("Original independent LBR fact replaced")
    return old_plan, value


def _error(exc: Exception) -> dict[str, str]:
    return {"type": type(exc).__name__, "message": str(exc)}


def _finite(values: list | tuple, length: int) -> bool:
    return len(values) == length and all(
        type(v) in (int, float) and math.isfinite(v) for v in values
    )


def direction(lon: float, lat: float) -> list[float]:
    a, b = math.radians(lon), math.radians(lat)
    return [math.cos(b) * math.cos(a), math.cos(b) * math.sin(a), math.sin(b)]


def angle(a: list | tuple, b: list | tuple) -> float:
    if (
        not _finite(a, 3)
        or not _finite(b, 3)
        or any(abs(math.hypot(*v) - 1) > 1e-12 for v in (a, b))
    ):
        raise ValueError("Invalid independent/native direction vector")
    cross = [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]
    return (
        math.degrees(
            math.atan2(math.hypot(*cross), math.fsum(x * y for x, y in zip(a, b)))
        )
        * 3600
    )


def capture() -> dict:
    from fatebridge.core import human_design_apparent_positions as batches
    from fatebridge.core import human_design_natal_sources as sources
    from fatebridge.core.astro import runtime
    from fatebridge.core.human_design import BODY_IDS, positions_at_tt

    old_plan, independent = reference()
    swe = runtime.swe
    if swe is None:
        raise RuntimeError("Swiss Ephemeris unavailable")
    trace = sources.NatalSourceTrace()
    trace_token = sources._ACTIVE.set(trace)
    backends = {}
    try:
        for label, backend, bit in (
            ("selected", "swieph", 2),
            ("moshier_diagnostic", "moshier", 4),
        ):
            rows = []
            for index, epoch in enumerate(independent["rows"]):
                observed = batches.PositionTrace()
                token = batches._ACTIVE.set(observed)
                failure = None
                positions = None
                try:
                    positions = positions_at_tt(epoch["jd_tt"], "true", backend=backend)
                except Exception as exc:
                    failure = _error(exc)
                finally:
                    batches._ACTIVE.reset(token)
                raw = {
                    r["body"]: r for batch in observed.batches for r in batch["bodies"]
                }
                try:
                    epsilon, epsilon_flags = runtime.ephemeris_call(
                        "calc", epoch["jd_tt"], swe.ECL_NUT, 0
                    )
                    if not _finite(epsilon, 6):
                        raise ValueError("Nonfinite native frame observation")
                    matrix = rotation(epoch["jd_tt"], epsilon[1], epsilon[2])
                    frame = {
                        "matrix": matrix,
                        "epsilon": list(epsilon),
                        "return_flags": epsilon_flags,
                        "error": None,
                    }
                except Exception as exc:
                    frame = {
                        "matrix": None,
                        "epsilon": None,
                        "return_flags": None,
                        "error": _error(exc),
                    }
                for body in old_plan["bodies"]:
                    row: dict[str, Any] = {
                        "label": epoch["label"],
                        "side": epoch["side"],
                        "body": body,
                        "jd_tt": epoch["jd_tt"],
                        "requested_backend": backend,
                        "default_batch_completed": failure is None,
                        "default_batch_error": failure,
                        "default_position": positions.get(body) if positions else None,
                        "default_raw": raw.get(body),
                        "icrf_requested_flags": bit | 256 | 32 | 131072 | 2048,
                        "icrf_native_coordinates": None,
                        "icrf_return_flags": None,
                        "icrf_error": None,
                        "diagnostic_post_call_file_contexts": [],
                        "icrf_to_default_frame": frame,
                    }
                    try:
                        coordinates, flags = runtime.ephemeris_call(
                            "calc",
                            epoch["jd_tt"],
                            BODY_IDS[body],
                            row["icrf_requested_flags"],
                        )
                        # JSON-safe raw observations, including explicit nonfinite labels.
                        row["icrf_native_coordinates"] = [
                            float(v) if math.isfinite(v) else str(v)
                            for v in coordinates
                        ]
                        row["icrf_return_flags"] = int(flags)
                        if flags & 7 in (1, 2):
                            row["diagnostic_post_call_file_contexts"] = [
                                {
                                    "slot": slot,
                                    "filename": Path(m[0]).name if m[0] else None,
                                    "native_start": m[1],
                                    "native_end": m[2],
                                    "native_de_number": m[3],
                                }
                                for slot in (0, 1)
                                for m in [swe.get_current_file_data(slot)]
                            ]
                    except Exception as exc:
                        row["icrf_error"] = _error(exc)
                    rows.append(row)
                if (index + 1) % 200 == 0:
                    print(
                        label, "epochs", index + 1, "positions", len(rows), flush=True
                    )
            backends[label] = {"requested_backend": backend, "rows": rows}
        try:
            source = trace.finish()
            source_error = None
        except Exception as exc:
            source = None
            source_error = _error(exc)
    finally:
        sources._ACTIVE.reset(trace_token)
    return {
        "method_id": "human_design_original_calendar_direction_capture_v2",
        "native_version": str(swe.version),
        "backends": backends,
        "default_source_evidence": source,
        "default_source_error": source_error,
        "default_LBR_from_existing_position_batches": True,
        "native_execution_authenticated": False,
        "scope": "Existing default positions_at_tt values and their actual raw LBR captured without another default call; separate ICRS/J2000 diagnostic calls at each same TT. Default source trace covers original calls; extra diagnostics retain flags and post-call native contexts only. No atomic read-set, original execution or physical accuracy certificate.",
    }


def compare_row(actual: dict, epoch: dict, legacy: dict, bit: int) -> dict:
    fact = epoch["directions"][actual["body"]]
    result = {
        k: actual[k] for k in ("label", "side", "body", "jd_tt", "requested_backend")
    }
    result.update(
        original_longitude_row=legacy,
        current_longitude_error_arcseconds=None,
        current_longitude_within_original2arcseconds=False,
        current_computed_longitude_equals_original=None,
        icrf_angular_error_arcseconds=None,
        icrf_angular_within2arcseconds=False,
        distance_difference_au=None,
        latitude_difference_in_separate_of_date_frames_arcseconds=None,
        default_and_icrf_backend_accepted=False,
        evaluation_status="not_assessed",
        accepted=False,
        default_icrf_direction_closure_arcseconds=None,
        default_icrf_direction_closure_accepted=False,
    )
    try:
        raw = actual["default_raw"]
        default = actual["default_position"]
        values = raw["native_coordinates"]
        icrf = actual["icrf_native_coordinates"]
        if (
            actual["default_batch_error"] is not None
            or not actual["default_batch_completed"]
            or not _finite(values, 4)
            or not _finite(icrf, 6)
        ):
            raise ValueError("Incomplete or nonfinite default/ICRF state")
        if not (
            0 <= values[0] < 360
            and -90 <= values[1] <= 90
            and values[2] > 0
            and 0 <= icrf[0] < 360
            and -90 <= icrf[1] <= 90
            and icrf[2] > 0
        ):
            raise ValueError("Out-of-range default/ICRF LBR")
        if (values[0], values[3], raw["return_flags"]) != (
            default["longitude"],
            default["longitude_speed"],
            default["return_flags"],
        ):
            raise ValueError("Default raw batch detached from actual producer")
        expected_icrf = bit | 256 | 32 | 64 | 131072 | 2048
        result["default_and_icrf_backend_accepted"] = (
            raw["return_flags"] == bit | 256
            and default["ephemeris_model"] == actual["requested_backend"]
            and raw["ephemeris_model"] == actual["requested_backend"]
            and actual["icrf_requested_flags"] == expected_icrf & ~64
            and actual["icrf_return_flags"] == expected_icrf
        )
        error = (
            abs((values[0] - fact["original_fact"]["longitude"] + 180) % 360 - 180)
            * 3600
        )
        angular = angle(direction(icrf[0], icrf[1]), fact["icrf_unit_vector"])
        matrix = actual["icrf_to_default_frame"]["matrix"]
        validate_rotation(matrix)
        closure = angle(
            direction(values[0], values[1]), mv(matrix, direction(icrf[0], icrf[1]))
        )
        result.update(
            current_longitude_error_arcseconds=error,
            current_longitude_within_original2arcseconds=error <= 2,
            current_computed_longitude_equals_original=values[0]
            == legacy["computed_longitude"],
            icrf_angular_error_arcseconds=angular,
            icrf_angular_within2arcseconds=angular <= 2,
            distance_difference_au=values[2] - fact["original_fact"]["distance_au"],
            latitude_difference_in_separate_of_date_frames_arcseconds=(
                values[1] - fact["original_fact"]["latitude"]
            )
            * 3600,
            evaluation_status="observed",
            default_icrf_direction_closure_arcseconds=closure,
            default_icrf_direction_closure_accepted=closure <= 0.0001,
        )
        result["accepted"] = bool(
            result["default_and_icrf_backend_accepted"]
            and result["current_longitude_within_original2arcseconds"]
            and result["icrf_angular_within2arcseconds"]
            and legacy["accepted"]
            and result["default_icrf_direction_closure_accepted"]
        )
    except (TypeError, ValueError, KeyError, IndexError, OverflowError) as exc:
        result["error"] = _error(exc)
    return result


def compare(production: dict, independent: dict, old_plan: dict) -> dict:
    legacy = read(LEGACY)
    identities = [
        (e["label"], e["side"], body, e["jd_tt"])
        for e in independent["rows"]
        for body in old_plan["bodies"]
    ]
    if (
        len(identities) != 24000
        or len(set(identities)) != 24000
        or set(production["backends"]) != {"selected", "moshier_diagnostic"}
    ):
        raise ValueError("Incomplete original reference/backend cohort")
    epoch_by_key = {(e["label"], e["side"]): e for e in independent["rows"]}
    output = {}
    for label, backend, bit in (
        ("selected", "swieph", 2),
        ("moshier_diagnostic", "moshier", 4),
    ):
        actual = production["backends"][label]
        if (
            actual["requested_backend"] != backend
            or [(r["label"], r["side"], r["body"], r["jd_tt"]) for r in actual["rows"]]
            != identities
        ):
            raise ValueError("Native rows lost, duplicated, reordered or rebound")
        before = legacy["backends"][label]["position_rows"]
        if [
            (r["label"], r["side"], r["body"], r["jd_tt"]) for r in before
        ] != identities:
            raise ValueError("Original longitude acceptance detached")
        rows = [
            compare_row(row, epoch_by_key[row["label"], row["side"]], old, bit)
            for row, old in zip(actual["rows"], before, strict=True)
        ]
        observed = [r for r in rows if r["evaluation_status"] == "observed"]
        failures = [r for r in rows if not r["icrf_angular_within2arcseconds"]]
        newly_exposed = [r for r in failures if r["original_longitude_row"]["accepted"]]
        output[label] = {
            "rows": rows,
            "position_count": len(rows),
            "not_assessed": len(rows) - len(observed),
            "original_longitude_failure_count": sum(not r["accepted"] for r in before),
            "current_longitude_failure_count": sum(
                not r["current_longitude_within_original2arcseconds"] for r in rows
            ),
            "icrf_angular_failure_count": len(failures),
            "new_full_direction_failures_previously_longitude_accepted": newly_exposed,
            "angular_failures_by_body": dict(Counter(r["body"] for r in failures)),
            "old_computed_longitude_difference_count": sum(
                r["current_computed_longitude_equals_original"] is not True
                for r in rows
            ),
            "default_or_icrf_backend_unaccepted_count": sum(
                not r["default_and_icrf_backend_accepted"] for r in rows
            ),
            "maximum_angular_error_arcseconds": max(
                (r["icrf_angular_error_arcseconds"] for r in observed), default=None
            ),
            "accepted_count": sum(r["accepted"] for r in rows),
            "default_icrf_closure_unaccepted_count": sum(
                not r["default_icrf_direction_closure_accepted"] for r in rows
            ),
            "maximum_default_icrf_direction_closure_arcseconds": max(
                (r["default_icrf_direction_closure_arcseconds"] for r in observed),
                default=None,
            ),
        }
    return {
        "method_id": "human_design_all_original_calendar_full_direction_comparison_v3",
        "independent_direction_reference_version": 2,
        "backends": output,
        "status": (
            "bounded_agreement_only"
            if production["default_source_error"] is None
            and all(v["accepted_count"] == 24000 for v in output.values())
            else "disagreements_remain"
        ),
        "all_original_rows_and_longitude_failures_retained": True,
        "original_numeric_thresholds_changed": False,
        "design_roots_recomputed_or_regraded": False,
        "full_calendar_certified": False,
        "native_execution_authenticated": False,
        "physical_accuracy_certified": False,
        "scope": "All48,000 original physical rows: original separate-frame longitude criterion remains, full ICRF direction adds a joint condition. Distance and separate-frame latitude are diagnostics without invented pass limits. No new root computation, continuous-calendar, original-software, full-semantics or prediction certification.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.production.exists() or args.output.exists():
        raise FileExistsError("Never overwrite an investigation")
    old_plan, independent = reference()
    production = capture()
    write(args.production, production)
    value = compare(production, independent, old_plan)
    write(args.output, value)
    print(
        json.dumps(
            {
                "status": value["status"],
                "backends": {
                    k: {
                        n: r[n]
                        for n in (
                            "position_count",
                            "not_assessed",
                            "original_longitude_failure_count",
                            "current_longitude_failure_count",
                            "icrf_angular_failure_count",
                            "angular_failures_by_body",
                            "old_computed_longitude_difference_count",
                            "maximum_angular_error_arcseconds",
                        )
                    }
                    for k, r in value["backends"].items()
                },
            }
        )
    )
    return int(value["status"] == "disagreements_remain")


if __name__ == "__main__":
    raise SystemExit(main())
