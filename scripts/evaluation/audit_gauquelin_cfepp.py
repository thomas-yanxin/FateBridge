"""Reproduce a pinned historical cohort without scoring predictive authority.

No network access, row selection, clock fitting, or predictive significance test.
Supply the decompressed final3 file from the version recorded in the protocol.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from collections import Counter
from pathlib import Path

from fatebridge.core.astro import runtime
from fatebridge.validation.gauquelin import (
    clock_coherence,
    decode_final3,
    method_profile,
    sector12,
    semiarc_sector,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/fixtures/gauquelin-cfepp-protocol.json"
PROTOCOL_SHA256 = "55b57ee32d54f5fb53d07d324d38b47f1c37dd31e586036fd4c07c299400640f"
POLICY = ROOT / "tests/fixtures/gauquelin-cfepp-native-policy.json"
POLICY_SHA256 = "e0fe6f30ac13d1a311a70ceeb1fb8626aabad24b902d19b053e2fbfbfca97071"


def geometry_comparison(native: float, independent: float) -> dict:
    raw_error = abs((native - independent + 18) % 36 - 18)
    expected = 1 + ((independent - 1 - 1 / 36_000_000) % 36)
    policy_error = abs((native - expected + 18) % 36 - 18)
    return {
        "raw_error_sector_units": raw_error,
        "raw_numeric_agreement": raw_error <= 1e-8,
        "documented_policy_expected_sector36": expected,
        "policy_error_sector_units": policy_error,
        "documented_policy_agreement": policy_error <= 1e-8,
    }


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def geometry_grid() -> dict:
    rows = []
    for ra, dec, lat, hour in itertools.product(
        range(0, 360, 30),
        [-60, -23.4, 0, 23.4, 60],
        [-89, -66.5, -45, 0, 45, 66.5, 89],
        range(0, 360, 30),
    ):
        armc = (ra + hour) % 360
        independent = semiarc_sector(armc, lat, ra, dec)
        row = {
            "ra": ra,
            "declination": dec,
            "latitude": lat,
            "hour_angle": hour,
            "independent": independent,
        }
        try:
            native = float(
                runtime.ephemeris_call("house_pos", armc, lat, 0.0, (ra, dec), b"G")
            )
            row["native_sector36"] = native
            if independent["status"] == "computed":
                error = abs((native - independent["sector36"] + 18) % 36 - 18)
                boundary = (
                    min(
                        abs(native - round(native)),
                        abs(independent["sector36"] - round(independent["sector36"])),
                    )
                    <= 1e-7
                )
                row.update(
                    error_sector_units=error,
                    numeric_agreement=error <= 1e-8,
                    integer_comparison=(
                        "boundary_unresolved" if boundary else "compared"
                    ),
                    integer_agreement=(
                        None
                        if boundary
                        else math.floor(native) == math.floor(independent["sector36"])
                    ),
                )
                row.update(geometry_comparison(native, independent["sector36"]))
        except (ValueError, runtime.swe.Error) as exc:
            row["native_error"] = str(exc)
        rows.append(row)
    compared = [r for r in rows if r["independent"]["status"] == "computed"]
    return {
        "rows": rows,
        "count": len(rows),
        "computed_count": len(compared),
        "independent_undefined_count": len(rows) - len(compared),
        "numeric_mismatch_count": sum(
            r.get("numeric_agreement") is not True for r in compared
        ),
        "integer_mismatch_count": sum(
            r.get("integer_agreement") is False for r in compared
        ),
        "boundary_unresolved_count": sum(
            r.get("integer_comparison") == "boundary_unresolved" for r in compared
        ),
        "max_error_sector_units": max(
            (r.get("error_sector_units", 36) for r in compared), default=None
        ),
        "documented_policy_mismatch_count": sum(
            r.get("documented_policy_agreement") is not True for r in compared
        ),
    }


def native_sector(
    jd: float,
    lon: float,
    lat: float,
    method: int,
    *,
    observer_height_m: float = 0.0,
    pressure_hpa: float = 0.0,
    temperature_c: float = 0.0,
) -> dict:
    try:
        position = float(
            runtime.ephemeris_call(
                "gauquelin_sector",
                jd,
                runtime.swe.MARS,
                method,
                (lon, lat, observer_height_m),
                pressure_hpa,
                temperature_c,
                runtime.swe.FLG_MOSEPH,
            )
        )
        return {
            "status": "computed",
            "sector36": position,
            "sector12": sector12(position),
            "distance_to_12_sector_boundary": min(
                (position - 1) % 3, 3 - (position - 1) % 3
            ),
        }
    except (ValueError, runtime.swe.Error) as exc:
        return {"status": "unresolved", "error": str(exc)}


def audit(data: bytes) -> dict:
    if runtime.swe is None:
        raise RuntimeError("Swiss Ephemeris is required; no approximate substitute")
    if sha(PROTOCOL.read_bytes()) != PROTOCOL_SHA256:
        raise ValueError("frozen_protocol_hash_mismatch")
    if sha(POLICY.read_bytes()) != POLICY_SHA256:
        raise ValueError("native_policy_hash_mismatch")
    policy = json.loads(POLICY.read_text())
    if policy["primary_protocol_sha256"] != PROTOCOL_SHA256:
        raise ValueError("native_policy_protocol_mismatch")
    source = decode_final3(data)
    grid = geometry_grid()
    rows, seen = [], {}
    for row in source:
        record = {
            k: row[k] for k in ("case_id", "cohort", "source_line_sha256", "issues")
        }
        record["clock_coherence"] = clock_coherence(row)
        if row["issues"]:
            rows.append(record)
            continue
        identity = tuple(row["raw"][k] for k in ("name", "local_date", "local_time"))
        record["duplicate_source_identity_of"] = seen.get(identity)
        seen.setdefault(identity, row["case_id"])
        record.update(
            source_mars12=row["mars12"],
            source_time_regime=row["raw"]["regime"],
            local_24_hour_rollover=row["local_24_hour_rollover"],
            universal_24_hour_rollover=row["universal_24_hour_rollover"],
        )
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
        lon, lat = row["longitude_east"], row["latitude"]
        record["methods"] = {str(m): native_sector(jd, lon, lat, m) for m in (0, 1, 2)}
        tt = jd + float(runtime.ephemeris_call("deltat_ex", jd, runtime.swe.FLG_MOSEPH))
        coordinates, flags = runtime.ephemeris_call(
            "calc",
            tt,
            runtime.swe.MARS,
            runtime.swe.FLG_MOSEPH | runtime.swe.FLG_EQUATORIAL,
        )
        if flags & runtime.swe.FLG_MOSEPH != runtime.swe.FLG_MOSEPH:
            raise RuntimeError("requested Moshier backend not returned")
        eps, _ = runtime.ephemeris_call(
            "calc", tt, runtime.swe.ECL_NUT, runtime.swe.FLG_MOSEPH
        )
        armc = (
            float(runtime.ephemeris_call("sidtime0", jd, eps[0], eps[2])) * 15 + lon
        ) % 360
        independent = semiarc_sector(armc, lat, coordinates[0], coordinates[1])
        record["independent_semiarc"] = independent
        primary = record["methods"]["0"]
        if independent["status"] == primary["status"] == "computed":
            error = abs((independent["sector36"] - primary["sector36"] + 18) % 36 - 18)
            record["independent_geometry_error_sector_units"] = error
            record["independent_geometry_agreement"] = error <= 1e-8
            record["native_geometry_comparison"] = geometry_comparison(
                primary["sector36"], independent["sector36"]
            )
        samples = []
        for seconds, dlon, dlat in itertools.product(
            (-60, 0, 60), (-0.01, 0.0, 0.01), (-0.01, 0.0, 0.01)
        ):
            result = native_sector(jd + seconds / 86400, lon + dlon, lat + dlat, 0)
            samples.append(
                {
                    "time_shift_seconds": seconds,
                    "longitude_shift_degrees": dlon,
                    "latitude_shift_degrees": dlat,
                    **result,
                }
            )
        record["resolution_samples"] = samples
        record["sampled_sector12_values"] = sorted(
            {s["sector12"] for s in samples if s["status"] == "computed"}
        )
        record["unresolved_sample_count"] = sum(
            s["status"] != "computed" for s in samples
        )
        for result in record["methods"].values():
            result["source_agreement"] = result.get("sector12") == row["mars12"]
        rows.append(record)
    groups = {}
    for group in ("published_1066", "supplementary_54"):
        selected = [r for r in rows if r["cohort"] == group]
        groups[group] = {
            "rows": len(selected),
            "invalid_rows": sum(bool(r["issues"]) for r in selected),
            "methods": {
                str(m): {
                    "computed": sum(
                        r.get("methods", {}).get(str(m), {}).get("status") == "computed"
                        for r in selected
                    ),
                    "source_agreement": sum(
                        r.get("methods", {}).get(str(m), {}).get("source_agreement")
                        is True
                        for r in selected
                    ),
                    "mismatch_ids": [
                        r["case_id"]
                        for r in selected
                        if r.get("methods", {}).get(str(m), {}).get("source_agreement")
                        is False
                    ],
                }
                for m in (0, 1, 2)
            },
            "clock_status_counts": dict(
                Counter(r["clock_coherence"]["status"] for r in selected)
            ),
            "sampled_sector_varies_count": sum(
                len(r.get("sampled_sector12_values", [])) > 1 for r in selected
            ),
        }
    numerical_pass = grid["numeric_mismatch_count"] == grid[
        "integer_mismatch_count"
    ] == 0 and all(r.get("independent_geometry_agreement") is True for r in rows)
    source_pass = all(
        r.get("methods", {}).get("0", {}).get("source_agreement") is True for r in rows
    )
    return {
        "audit_id": "other-schools-v25-cfepp",
        "output_revision": "method_provenance_v2",
        "design": "historical_calculation_audit",
        "protocol_sha256": PROTOCOL_SHA256,
        "native_policy_supplement_sha256": sha(POLICY.read_bytes()),
        "source_sha256": sha(data),
        "runtime": {
            "swiss_version": runtime.swe.version,
            "requested_ephemeris": "Moshier",
            "requested_topocentric_flag": False,
            "observer_scope": "per_method",
            "method_profiles": {str(m): method_profile(m) for m in (0, 1, 2)},
            "observer_height_m": 0.0,
            "observer_height_source": "fixed_convention_not_birth_record",
            "pressure_input_hpa": 0.0,
            "temperature_input_c": 0.0,
        },
        "geometry_grid": grid,
        "cohorts": groups,
        "rows": rows,
        "numerical_geometry_pass": numerical_pass,
        "documented_native_policy_pass": grid["documented_policy_mismatch_count"] == 0
        and all(
            r.get("native_geometry_comparison", {}).get("documented_policy_agreement")
            is True
            for r in rows
        ),
        "primary_source_sector_reproduction_pass": source_pass,
        "historical_clock_accepted": False,
        "real_world_predictive_validation": "not_established",
        "prospective_sample_count": 0,
        "authority_certified": False,
        "all_four_perfect": False,
        "passed": numerical_pass and source_pass,
        "limits": [
            "Original method and rounding conventions have not been certified from the 1996 booklet.",
            "Partial clock coherence is not complete historical civil-time validation.",
            "27 resolution samples are sensitivity scenarios, not independent persons or an interval proof.",
            "Native coordinate backend is shared; independent semiarc geometry is not independent planetary dynamics.",
            "Known-outcome selected athletes without matched controls cannot establish occupational prediction.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Reserve the output before running. Never replace earlier negative evidence.
    with args.output.open("x", encoding="utf-8") as stream:
        report = audit(args.source.read_bytes())
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "numerical_geometry_pass",
                    "primary_source_sector_reproduction_pass",
                    "cohorts",
                    "passed",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
