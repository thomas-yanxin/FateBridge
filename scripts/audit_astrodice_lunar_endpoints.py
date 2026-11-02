"""Verify the frozen endpoint reference, then use the unchanged lunar audit.

The collector's linear solve is checked independently: exact polynomial
moments and polynomial weights uniquely certify the minimum-norm stencil.
No old symmetric-template failure or incomplete row is replaced.
"""

import argparse
import csv
import hashlib
import io
import json
import math
import re
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path

from scripts.audit_astrodice_lunar_precision import audit
from scripts.audit_astrodice_position_motion import parse_date

PROTOCOL_SHA256 = "6f4a367e72f2cca3902d618d03abde92d4c28a5e3f8031125d12828509441498"
FROZEN_PROTOCOLS = {
    PROTOCOL_SHA256: (25, 10),
    "a4e996ef442872794e55cc9c32c2989f959a535806d15cb6d2ca94a005bb6077": (49, 12),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_reference(protocol, reference):
    if reference["candidate_imported"] or reference["candidate_compared"]:
        raise ValueError("Reference collection separation changed")
    geometry = FROZEN_PROTOCOLS.get(reference["protocol_sha256"])
    if geometry is None:
        raise ValueError("Endpoint protocol changed")
    count, order = geometry
    if (
        (protocol["node_count"], protocol["polynomial_degree"]) != geometry
        or protocol["direction_derivative_tolerance_arcsec_per_day"] != 0.002
        or protocol["position_tolerance_arcsec"] != 0.02
    ):
        raise ValueError("Endpoint geometry or fixed error line changed")
    weights = [Fraction(*pair) for pair in protocol["rational_weights"]]
    if len(weights) != count:
        raise ValueError("Endpoint node count changed")
    for degree in range(order + 1):
        if sum(w * k**degree for k, w in enumerate(weights)) != int(degree == 1):
            raise ValueError("Endpoint polynomial moment changed")
    differences = weights
    for _ in range(order + 1):
        differences = [b - a for a, b in zip(differences, differences[1:])]
    if any(differences):
        raise ValueError("Endpoint minimum-norm polynomial changed")
    dates = protocol["development_dates_tt"] + protocol["holdout_dates_tt"]
    if len(dates) != 10 or len(set(dates)) != 10:
        raise ValueError("Endpoint cohort changed")

    def probes(date):
        center = datetime.fromisoformat(date)
        return {
            (
                center + timedelta(seconds=protocol["directions"][date] * k * h)
            ).isoformat()
            for h in protocol["steps_seconds"]
            for k in range(count)
        }

    wanted = set().union(*(probes(d) for d in dates))
    missing = {r["date_tt"] for r in reference["missing_probe_epochs"]}
    points = {}
    for batch in reference["batches"]:
        response = json.loads(batch["raw_response_utf8"])
        text = response.get("result", "")
        if (
            hashlib.sha256(batch["raw_response_utf8"].encode()).hexdigest()
            != batch["raw_response_sha256"]
            or response != batch["response"]
            or hashlib.sha256(text.encode()).hexdigest() != batch["result_sha256"]
        ):
            raise ValueError("Endpoint raw response changed")
        if any(
            batch["parameters"].get(k) != v
            for k, v in protocol["reference_parameters"].items()
        ):
            raise ValueError("Endpoint target/frame/time changed")
        requested = {
            parse_date(v, True)
            for v in re.findall(r"'([^']+)'", batch["parameters"]["TLIST"])
        }
        if not requested <= wanted:
            raise ValueError("Endpoint requested cohort changed")
        if "error" in batch:
            if "No ephemeris" not in batch["error"]:
                raise ValueError("Unexplained endpoint error")
            continue
        if not all(
            v in text
            for v in [
                "Target body name: Moon (301)",
                "Center body name: Earth (399)",
                "ICRF",
                "Date__(TT)",
            ]
        ):
            raise ValueError("Endpoint reference header changed")
        table = list(
            csv.reader(io.StringIO(text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]))
        )
        if len(table) != len(batch["rows"]):
            raise ValueError("Endpoint raw row count changed")
        returned = set()
        for row, columns in zip(batch["rows"], table):
            date = parse_date(columns[0])
            ra, dec = map(float, columns[3:5])
            alpha, delta = map(math.radians, (ra, dec))
            unit = [
                math.cos(delta) * math.cos(alpha),
                math.cos(delta) * math.sin(alpha),
                math.sin(delta),
            ]
            if (
                date != row["date_tt"]
                or date in points
                or [ra, dec] != [row["ra_degrees"], row["dec_degrees"]]
                or [v.strip() for v in columns[3:5]] != row["printed_values"]
                or max(abs(a - b) for a, b in zip(unit, row["icrf_unit_direction"]))
                > 1e-15
            ):
                raise ValueError("Endpoint raw angle/date changed")
            points[date] = row["icrf_unit_direction"]
            returned.add(date)
        if returned != requested:
            raise ValueError("Endpoint returned coverage changed")
    if set(points) & missing or set(points) | missing != wanted:
        raise ValueError("Endpoint full coverage changed")
    if [r["date_tt"] for r in reference["rows"]] != dates:
        raise ValueError("Endpoint center order changed")
    for row in reference["rows"]:
        date = row["date_tt"]
        center = datetime.fromisoformat(date)
        absent = sorted(probes(date) - points.keys())
        jd = (
            center.toordinal()
            + 1721424.5
            + (center.hour * 3600 + center.minute * 60 + center.second) / 86400
        )
        if (
            row["jd_tt"] != jd
            or row["cohort"]
            != ("holdout" if date in protocol["holdout_dates_tt"] else "development")
            or row["missing_probes"] != absent
            or row["status"] != ("incomplete" if absent else "available")
        ):
            raise ValueError("Endpoint center evidence changed")
        if absent:
            continue
        direction = protocol["directions"][date]
        rates = {
            str(h): [
                math.fsum(
                    float(w)
                    * (
                        points[
                            (center + timedelta(seconds=direction * k * h)).isoformat()
                        ][axis]
                        - points[date][axis]
                    )
                    for k, w in enumerate(weights)
                )
                * 86400
                / (direction * h)
                for axis in range(3)
            ]
            for h in protocol["steps_seconds"]
        }
        if (
            rates != row["derivatives"]
            or row["icrf_direction_derivative_per_day"]
            != rates[str(protocol["chosen_step_seconds"])]
            or row["icrf_unit_direction"] != points[date]
            or abs(
                row["step_difference_arcsec_per_day"]
                - math.degrees(math.dist(*rates.values())) * 3600
            )
            > 1e-12
        ):
            raise ValueError("Endpoint derivative changed")
    available = [r for r in reference["rows"] if r["status"] == "available"]
    return {
        "centers": len(dates),
        "position_probes": len(points),
        "available": len(available),
        "incomplete": [
            r["date_tt"] for r in reference["rows"] if r["status"] != "available"
        ],
        "template_failures": [
            r["date_tt"]
            for r in available
            if r["step_difference_arcsec_per_day"] > 0.002
        ],
        "max_template_step_difference_arcsec_per_day": max(
            (r["step_difference_arcsec_per_day"] for r in available), default=None
        ),
        "exact_polynomial_moments_and_minimum_norm_verified": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ["protocol", "reference", "output"]:
        parser.add_argument("--" + field, required=True, type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if digest(args.protocol) not in FROZEN_PROTOCOLS:
        raise ValueError("Frozen endpoint protocol changed")
    protocol, reference = [
        json.loads(f.read_text()) for f in [args.protocol, args.reference]
    ]
    validation = validate_reference(protocol, reference)
    unresolved = bool(validation["incomplete"] or validation["template_failures"])
    result = (
        {
            "validation": validation,
            "candidate_compared": False,
            "status": (
                "reference_evidence_unresolved"
                if unresolved
                else "reference_quality_lines_satisfied"
            ),
            "exit_code": 2 if unresolved else 0,
        }
        if args.validate_only
        else audit(protocol, reference, production_order=True)
    )
    result["inputs"] = {
        "protocol_sha256": digest(args.protocol),
        "reference_sha256": digest(args.reference),
    }
    result["scope"] = (
        "Separate fixed one-sided endpoint study. Original symmetric failures remain unchanged; no universal/calendar/original-text/prediction certification."
    )
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
