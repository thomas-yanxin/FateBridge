"""Audit actual Guolao rates against the predeclared fixed-TT reference.

Uses the operator's configured ephemeris, never changes its model/path. Exit1
means an observed numerical failure; exit2 means missing/unresolved evidence
or a source error. Neither source consistency nor a pass proves prediction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fatebridge.core import guolao
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.time_scales import datetime_from_tt

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_SHA256 = "9c46e6590bbdd5cfb891d499b03f889fffa258e6294b6b7e87bb2eab74b877d5"
REFERENCE_SHA256 = "4fff4d0817aeb6e4514f6fbae75609357c52eb86c5acc228490470f6195758c3"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_reference(
    protocol_path: Path,
    reference_path: Path,
    *,
    protocol_sha256: str = PROTOCOL_SHA256,
    reference_sha256: str = REFERENCE_SHA256,
) -> tuple[dict, dict]:
    if digest(protocol_path) != protocol_sha256:
        raise ValueError("Frozen Guolao protocol identity changed")
    if digest(reference_path) != reference_sha256:
        raise ValueError("Frozen Guolao reference identity changed")
    protocol = json.loads(protocol_path.read_text())
    reference = json.loads(reference_path.read_text())
    if (
        reference["protocol_sha256"] != protocol_sha256
        or reference["versions"] != protocol["versions"]
        or reference["forbidden_implementation_imports"] != []
    ):
        raise ValueError("Independent collector provenance changed")
    for target in reference["references"]:
        expected = protocol["targets"][target["body"]]
        if target["target_id"] != expected:
            raise ValueError("Target reference point changed")
        if [row["date_tt"] for row in target["rows"]] != protocol["dates_tt"]:
            raise ValueError("Requested reference epochs changed")
        for batch in target["batches"]:
            if "error" in batch:
                continue  # Kept as incomplete/unresolved evidence below.
            raw = batch["raw_response_utf8"]
            if hashlib.sha256(raw.encode()).hexdigest() != batch["raw_response_sha256"]:
                raise ValueError("Raw NASA response identity changed")
            response = json.loads(raw)
            if response != batch["response"]:
                raise ValueError("Parsed NASA response differs from saved bytes")
            for key, value in protocol["reference_parameters"].items():
                if batch["parameters"][key] != value:
                    raise ValueError("Reference observer/time/frame request changed")
            if batch["parameters"]["COMMAND"] != f"'{expected}'":
                raise ValueError("Reference target request changed")
            header = response["result"].split("$$SOE", 1)[0]
            match = re.search(r"Target body name:.*\((\d+)\)", header)
            if (
                match is None
                or int(match[1]) not in protocol["target_id_aliases"][str(expected)]
            ):
                raise ValueError("Returned reference target changed")
            for label in (
                "Center body name: Earth (399)",
                "Date__(TT)__HR:MN:SC.fff",
                "RA_(ICRF-a-app)",
                "DEC_(ICRF-a-app)",
            ):
                if label not in header:
                    raise ValueError("Returned reference coordinate contract changed")
    if len(reference["references"]) != len(protocol["targets"]) or {
        r["body"] for r in reference["references"]
    } != set(protocol["targets"]):
        raise ValueError("Reference body coverage changed")
    return protocol, reference


def evaluate(protocol: dict, reference: dict) -> dict[str, Any]:
    indexed = {
        target["body"]: {row["date_tt"]: row for row in target["rows"]}
        for target in reference["references"]
    }
    rows = []
    for date in protocol["dates_tt"]:
        jd = indexed["Moon"][date]["jd_tt"]
        raw = None
        error = None
        try:
            moment = datetime_from_tt(jd)
            birth = build_astro_birth_info(
                birth_year=moment.year,
                birth_month=moment.month,
                birth_day=moment.day,
                birth_hour=moment.hour,
                birth_minute=moment.minute,
                birth_second=moment.second,
                birth_microsecond=moment.microsecond,
                birth_timezone="UTC",
                birth_longitude=0,
                birth_latitude=0,
            )
            raw = guolao.positions(birth, observer_geometry=False)
            if abs(raw["julian_day_tt"] - jd) >= 1e-9:
                raise ValueError("Civil inverse did not preserve the fixed TT epoch")
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
        for name in protocol["targets"]:
            ref = indexed[name][date]
            resolved = (
                ref["status"] == "available"
                and ref["stencil_difference_arcsec_per_day"]
                <= protocol["reference_stencil_uncertainty_line_arcsec_per_day"]
                and ref["frame_step_difference_arcsec_per_day"]
                <= protocol["frame_step_uncertainty_line_arcsec_per_day"]
            )
            row = {
                "body": name,
                "date_tt": date,
                "reference_resolved": resolved,
                "source_error": error,
                "passed": False,
            }
            if raw is not None and error is None:
                state = raw["states"][name]
                row.update(
                    state=state,
                    actual_model=raw["ephemeris_provenance"]["by_body"][name][
                        "ecliptic_model"
                    ],
                    future_leap_seconds_assumed_unchanged=raw[
                        "future_leap_seconds_assumed_unchanged"
                    ],
                )
                if ref["status"] == "available":
                    expected = ref["erfa_display_frame"][
                        "longitude_speed_degrees_per_day"
                    ]
                    residual = (state["longitude_speed"] - expected) * 3600
                    row.update(
                        reference_speed=expected,
                        signed_residual_arcsec_per_day=residual,
                        native_signed_residual_arcsec_per_day=(
                            state["longitude_speed_native"] - expected
                        )
                        * 3600,
                        passed=resolved
                        and math.isfinite(residual)
                        and abs(residual)
                        <= protocol["display_longitude_speed_tolerance_arcsec_per_day"],
                    )
            rows.append(row)
    return {
        "audit_version": "guolao_longitude_motion_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Actual Guolao positions at twelve predeclared TT epochs for seven physical bodies. Swiss and NASA may share DE441 dynamics; not independent trajectory, whole-domain, classical-rule or outcome validation.",
        "requested": len(protocol["dates_tt"]) * len(protocol["targets"]),
        "passed": sum(row["passed"] for row in rows),
        "source_errors": sum(row["source_error"] is not None for row in rows),
        "unresolved_reference": sum(not row["reference_resolved"] for row in rows),
        "numerical_subset_checks_passed": all(row["passed"] for row in rows),
        "rows": rows,
        "all_four_objectives_validated": False,
        "authority_certified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "tests/data/astro/guolao_motion/protocol.json",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=ROOT / "tests/data/astro/guolao_motion/reference.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        protocol, reference = load_reference(args.protocol, args.reference)
    except (OSError, ValueError, KeyError) as error:
        result = {
            "reference_validation_error": str(error),
            "numerical_subset_checks_passed": False,
            "all_four_objectives_validated": False,
            "authority_certified": False,
        }
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))
        return 2
    result = evaluate(protocol, reference)
    result["protocol_sha256"] = PROTOCOL_SHA256
    result["reference_sha256"] = REFERENCE_SHA256
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}))
    if result["source_errors"] or result["unresolved_reference"]:
        return 2
    return 0 if result["numerical_subset_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
