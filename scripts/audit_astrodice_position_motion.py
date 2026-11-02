"""Independently validate the sealed reference, then audit a frozen candidate.

Exit 1: candidate above the unchanged .002 arcsec/day line. Exit 2: reference
not converged. No case is removed and no old audit is overwritten.
"""

import argparse
import csv
import hashlib
import io
import json
import math
import platform
import re
from datetime import datetime, timedelta
from pathlib import Path

PROTOCOL_SHA256 = "19a157ac1dfd837fe9922818185bb0de8b4459e855bd6fee69889d1be5ed6f87"
REFERENCE_SHA256 = "46aa302f5c40e056aa535f5e979d77b4c27499bb6f35ec1068a56ccc4e518bb9"
FROZEN_COHORTS = {
    PROTOCOL_SHA256: (REFERENCE_SHA256, 40),
    "a93a69736e003de3f0a3c788a3849d079ff06360f92b8b168448b05a7977eb56": (
        "5e0fe1b89e575e1d7c21eda548095cc609365a6128d44ec72f2d073b8cb92cf7",
        20,
    ),
}
MONTHS = dict(
    zip("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), range(1, 13))
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_date(label, request=False):
    pattern = (
        r"(\d+)ad-(\w{3})-(\d{2}) (\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?"
        if request
        else r"\s*(\d{1,4})-(\w{3})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d+)\s*"
    )
    match = re.fullmatch(pattern, label)
    if match is None:
        raise ValueError("Reference TT calendar label changed")
    y, m, d, h, mi, s, fraction = match.groups()
    fraction = fraction or ""
    if len(fraction) > 6 and any(c != "0" for c in fraction[6:]):
        raise ValueError("Reference time exceeds microsecond representation")
    microsecond = int(fraction[:6].ljust(6, "0"))
    return datetime(
        int(y), MONTHS[m], int(d), int(h), int(mi), int(s), microsecond
    ).isoformat()


def stencil(points, date, seconds):
    t = datetime.fromisoformat(date)
    values = [
        points[(t + timedelta(seconds=k * seconds)).isoformat()]
        for k in [-3, -2, -1, 1, 2, 3]
    ]
    # Deliberately reproduce the *frozen* reference operation order.
    return [
        (-a + 9 * b - 45 * c + 45 * d - 9 * e + f) * 86400 / (60 * seconds)
        for a, b, c, d, e, f in zip(*values)
    ]


def validate_reference(protocol, reference):
    cohort = FROZEN_COHORTS.get(reference["protocol_sha256"])
    if cohort is None or reference["forbidden_candidate_imports"]:
        raise ValueError("Reference collection separation changed")
    if (
        len(protocol["dates_tt"]) != cohort[1]
        or len(set(protocol["dates_tt"])) != cohort[1]
    ):
        raise ValueError("Frozen cohort changed")
    wanted = {
        (datetime.fromisoformat(d) + timedelta(seconds=o)).isoformat()
        for d in protocol["dates_tt"]
        for o in [0, *protocol["offsets_seconds"]]
    }
    if [t["body"] for t in reference["references"]] != list(protocol["targets"]):
        raise ValueError("Target coverage changed")
    counts = {
        "target_epochs": 0,
        "position_probes": 0,
        "raw_batches": 0,
        "reference_stencil_failures": [],
    }
    for target in reference["references"]:
        body = target["body"]
        ident = protocol["targets"][body]
        if target["target_id"] != ident:
            raise ValueError("Target reference point changed")
        points = {}
        for batch in target["batches"]:
            raw = batch["raw_response_utf8"]
            response = json.loads(raw)
            text = response.get("result", "")
            if (
                hashlib.sha256(raw.encode()).hexdigest() != batch["raw_response_sha256"]
                or response != batch["response"]
                or hashlib.sha256(text.encode()).hexdigest() != batch["result_sha256"]
            ):
                raise ValueError("Reference raw response identity changed")
            params = batch["parameters"]
            expected = {**protocol["reference_parameters"], "COMMAND": f"'{ident}'"}
            if any(params.get(k) != v for k, v in expected.items()):
                raise ValueError("Reference frame/time/target contract changed")
            if not all(
                s in text
                for s in [
                    f"Target body name: {body}",
                    f"({ident})",
                    "Center body name: Earth (399)",
                    "ICRF",
                    "Date__(TT)",
                    "$$SOE\n",
                ]
            ):
                raise ValueError("Returned reference headers changed")
            labels = re.findall(r"'([^']+)'", params["TLIST"])
            requested = {parse_date(label, True) for label in labels}
            if len(requested) != len(labels) or not requested <= wanted:
                raise ValueError("Requested probe coverage changed")
            table = list(
                csv.reader(
                    io.StringIO(text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0])
                )
            )
            if len(table) != len(batch["rows"]):
                raise ValueError("Reference parsed count changed")
            returned = set()
            for row, columns in zip(batch["rows"], table):
                date = parse_date(columns[0])
                if date != row["date_tt"] or date in points:
                    raise ValueError("Reference date duplicated or changed")
                angles = list(map(float, columns[3:5]))
                if angles != [row["ra_degrees"], row["dec_degrees"]] or row[
                    "printed_values"
                ] != [v.strip() for v in columns[3:5]]:
                    raise ValueError("Reference angles changed")
                ra, dec = map(math.radians, angles)
                unit = [
                    math.cos(dec) * math.cos(ra),
                    math.cos(dec) * math.sin(ra),
                    math.sin(dec),
                ]
                frozen = row["icrf_unit_direction"]
                if (
                    len(frozen) != 3
                    or max(abs(a - b) for a, b in zip(unit, frozen)) > 1e-15
                ):
                    raise ValueError("Reference direction changed")
                points[date] = frozen
                returned.add(date)
            if returned != requested:
                raise ValueError("Reference missing probes")
            counts["raw_batches"] += 1
        if (
            set(points) != wanted
            or [r["date_tt"] for r in target["rows"]] != protocol["dates_tt"]
        ):
            raise ValueError("Reference full coverage changed")
        counts["position_probes"] += len(points)
        for row in target["rows"]:
            date = row["date_tt"]
            t = datetime.fromisoformat(date)
            jd = (
                t.toordinal()
                + 1721424.5
                + (t.hour * 3600 + t.minute * 60 + t.second) / 86400
            )
            rates = {
                str(h): stencil(points, date, h)
                for h in protocol["seven_point_steps_seconds"]
            }
            chosen = rates[str(protocol["chosen_step_seconds"])]
            difference = math.degrees(math.dist(*rates.values())) * 3600
            if (
                row["jd_tt"] != jd
                or row["icrf_unit_direction"] != points[date]
                or row["seven_point_derivatives"] != rates
                or row["icrf_direction_derivative_per_day"] != chosen
                or abs(row["stencil_difference_arcsec_per_day"] - difference) > 1e-12
            ):
                raise ValueError("Frozen reference stencil changed")
            if difference > protocol["direction_derivative_tolerance_arcsec_per_day"]:
                counts["reference_stencil_failures"].append(
                    {
                        "body": body,
                        "date_tt": date,
                        "difference_arcsec_per_day": difference,
                    }
                )
            counts["target_epochs"] += 1
    return counts


def audit(protocol, reference):
    from fatebridge.core.astro import ephemeris, runtime
    from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
    from fatebridge.core.astro.position_motion import OFFSETS, STEPS_DAYS, WEIGHTS
    from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
    from fatebridge.core.astro.zodiac import native_lahiri_positions

    swe = runtime.swe
    trace = PhysicalEphemerisTrace()
    rows = []
    flags = (
        swe.FLG_SWIEPH
        | swe.FLG_SPEED
        | swe.FLG_ICRS
        | swe.FLG_J2000
        | swe.FLG_EQUATORIAL
        | swe.FLG_XYZ
    )
    for target in reference["references"]:
        body = target["body"]
        for row in target["rows"]:
            jd = row["jd_tt"]
            metadata = {}
            state, model = ephemeris._swisseph_planet_state(
                body, jd, julian_day_tt=jd, source_trace=trace, motion_metadata=metadata
            )
            lahiri = native_lahiri_positions(
                [body],
                julian_day_ut1=jd,
                julian_day_tt=jd,
                motion_metadata=metadata,
                source_trace=trace,
            )[body]
            # ICRF direction derivative of the same complete apparent position;
            # this diagnostic is distinct from the production longitude output.
            h = STEPS_DAYS[-1]
            vectors = []
            for k in OFFSETS:
                values, returned = runtime.ephemeris_call(
                    "calc", jd + k * h, PLANET_SWISSEPH_IDS[body], flags
                )
                if (
                    returned < 0
                    or runtime.ephemeris_model_from_retflag(returned) != model
                ):
                    raise ValueError("Diagnostic physical model changed")
                radius = math.hypot(*values[:3])
                vectors.append([v / radius for v in values[:3]])
                trace.observe(f"{body}_holdout_icrf_{k}", model, record_factor=False)
            derivative = [
                math.fsum(w * v for w, v in zip(WEIGHTS, axis)) / (60 * h)
                for axis in zip(*vectors)
            ]
            expected = row["erfa_display_frame"]["longitude_speed_degrees_per_day"]
            rows.append(
                {
                    "body": body,
                    "date_tt": row["date_tt"],
                    "model": model,
                    "native_display_error_arcsec_per_day": abs(
                        state["longitude_speed_native"] - expected
                    )
                    * 3600,
                    "corrected_display_error_arcsec_per_day": abs(
                        state["longitude_speed"] - expected
                    )
                    * 3600,
                    "complete_position_icrf_error_arcsec_per_day": math.degrees(
                        math.dist(derivative, row["icrf_direction_derivative_per_day"])
                    )
                    * 3600,
                    "reference_step_difference_arcsec_per_day": row[
                        "stencil_difference_arcsec_per_day"
                    ],
                    "state": state,
                    "lahiri_state": lahiri,
                    "correction_metadata": metadata,
                }
            )
    metrics = [
        "native_display_error_arcsec_per_day",
        "corrected_display_error_arcsec_per_day",
        "complete_position_icrf_error_arcsec_per_day",
        "reference_step_difference_arcsec_per_day",
    ]
    summary = {
        body: {
            m: {
                "count": len(rs),
                "max": max(r[m] for r in rs),
                "above_fixed_line": sum(r[m] > 0.002 for r in rs),
            }
            for m in metrics
        }
        for body in protocol["targets"]
        for rs in [[r for r in rows if r["body"] == body]]
    }
    failed = any(r[m] > 0.002 for r in rows for m in metrics[1:3])
    unresolved = any(r[metrics[-1]] > 0.002 for r in rows)
    return {
        "status": (
            "numeric_acceptance_failed"
            if failed
            else (
                "reference_evidence_unresolved"
                if unresolved
                else "frozen_holdout_lines_satisfied"
            )
        ),
        "exit_code": 1 if failed else 2 if unresolved else 0,
        "platform": platform.platform(),
        "summary": summary,
        "cases": rows,
        "physical_sources": trace.finish(),
        "fixed_line_arcsec_per_day": 0.002,
        "scope": "Prospectively frozen inner-planet target epochs only. Original failures remain. No universal accuracy or real-world prediction certification.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    for key in ["protocol", "reference", "output"]:
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--validate-reference-only", action="store_true")
    args = parser.parse_args()
    cohort = FROZEN_COHORTS.get(digest(args.protocol))
    if cohort is None or digest(args.reference) != cohort[0]:
        raise ValueError("Frozen input bytes changed")
    protocol = json.loads(args.protocol.read_text())
    reference = json.loads(args.reference.read_text())
    validation = validate_reference(protocol, reference)
    result = (
        {"validation": validation, "candidate_compared": False}
        if args.validate_reference_only
        else audit(protocol, reference)
    )
    result["inputs"] = {
        "protocol_sha256": digest(args.protocol),
        "reference_sha256": digest(args.reference),
    }
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in ["cases", "physical_sources"]},
            indent=2,
        )
    )
    raise SystemExit(result.get("exit_code", 0))
