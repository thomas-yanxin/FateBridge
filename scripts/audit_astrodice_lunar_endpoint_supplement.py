"""Validate new endpoint evidence, then separately grade the selected source.

Original wide-reference missing records stay untouched. A hard NASA boundary
cannot become a passing single-sided or candidate-generated reference.
"""

import argparse
import csv
import hashlib
import io
import json
import math
from fractions import Fraction
from pathlib import Path

from scripts.gen_astrodice_lunar_endpoint_supplement import calendar_label

ROOT = Path(__file__).resolve().parents[1]


def validate(directory):
    protocol = json.loads((directory / "protocol.json").read_text())
    reference = json.loads((directory / "reference.json").read_text())
    original = ROOT / "tests/data/astrodice" / protocol["original_reference"]
    original_protocol = original.with_name("lunar-wide-protocol.json")
    if (
        hashlib.sha256(original.read_bytes()).hexdigest()
        != protocol["original_reference_sha256"]
        or hashlib.sha256(original_protocol.read_bytes()).hexdigest()
        != protocol["original_protocol_sha256"]
        or hashlib.sha256((directory / "protocol.json").read_bytes()).hexdigest()
        != reference["protocol_sha256"]
        or reference["candidate_imported"]
        or reference["candidate_compared"]
    ):
        raise ValueError("Original or supplemental source identity changed")
    previous = json.loads(original_protocol.read_text())
    for key in (
        "reference_parameters",
        "steps_seconds",
        "chosen_step_seconds",
        "offsets_seconds",
    ):
        if protocol[key] != previous[key]:
            raise ValueError("Supplement changed the original reference semantics")
    original_missing = [
        row
        for row in json.loads(original.read_text())["rows"]
        if row["status"] == "incomplete"
    ]
    if protocol["centers"] != original_missing:
        raise ValueError("Supplement detached from the two original missing centers")
    points = {}
    for request in reference["requests"]:
        raw = (directory / request["raw_path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != request["sha256"]:
            raise ValueError("Independent raw response changed")
        epochs = list(map(Fraction, request["numeric_jd_tt"]))
        labels = list(map(calendar_label, epochs))
        if request["calendar_labels"] != labels or request["parameters"] != {
            **protocol["reference_parameters"],
            "TLIST": " ".join(f"'{label}'" for label in labels),
        }:
            raise ValueError("Request epoch or target/frame changed")
        response = json.loads(raw)
        text = response.get("result", "")
        if "$$SOE\n" not in text:
            if request.get("error") != response.get("error", text) or request["rows"]:
                raise ValueError("Unavailable NASA source became available")
            continue
        if not all(
            value in text
            for value in ("Moon (301)", "Earth (399)", "ICRF", "Date__(TT)")
        ):
            raise ValueError("Returned NASA target/frame/time changed")
        rows = list(
            csv.reader(io.StringIO(text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]))
        )
        if len(rows) != len(request["rows"]) or len(rows) != len(epochs):
            raise ValueError("Incomplete independent raw table")
        for epoch, row, saved in zip(epochs, rows, request["rows"]):
            ra, dec = map(float, row[3:5])
            a, d = map(math.radians, (ra, dec))
            direction = [
                math.cos(d) * math.cos(a),
                math.cos(d) * math.sin(a),
                math.sin(d),
            ]
            if saved != {
                "jd_tt": str(epoch),
                "calendar_label": calendar_label(epoch),
                "returned_calendar_label": row[0],
                "ra_degrees": ra,
                "dec_degrees": dec,
                "printed_values": [v.strip() for v in row[3:5]],
                "icrf_unit_direction": direction,
            }:
                raise ValueError("Saved reference differs from original NASA row")
            points[str(epoch)] = direction
    weights = {
        k: float(
            Fraction((-1) ** (k + 1), k)
            * Fraction(
                math.factorial(6) ** 2, math.factorial(6 - k) * math.factorial(6 + k)
            )
        )
        for k in range(1, 7)
    }
    if len(reference["rows"]) != 2:
        raise ValueError("The complete original missing cohort was not retained")
    for center, row in zip(protocol["centers"], reference["rows"]):
        epoch = Fraction(center["jd_tt"])
        missing = [
            {
                "offset_seconds": offset,
                "jd_tt": str(epoch + Fraction(offset, 86400)),
                "calendar_label": calendar_label(epoch + Fraction(offset, 86400)),
            }
            for offset in [0, *protocol["offsets_seconds"]]
            if str(epoch + Fraction(offset, 86400)) not in points
        ]
        if (
            any(row[key] != center[key] for key in ("date_tt", "jd_tt", "cohort"))
            or row["missing_probes"] != missing
            or row["status"] != ("incomplete" if missing else "available")
        ):
            raise ValueError("Missing probes were removed or relabeled")
        if missing:
            continue
        derivatives = {
            str(step): [
                math.fsum(
                    weights[k]
                    * (
                        points[str(epoch + Fraction(k * step, 86400))][axis]
                        - points[str(epoch - Fraction(k * step, 86400))][axis]
                    )
                    for k in range(1, 7)
                )
                * 86400
                / step
                for axis in range(3)
            ]
            for step in protocol["steps_seconds"]
        }
        if (
            row["derivatives"] != derivatives
            or row["icrf_direction_derivative_per_day"]
            != derivatives[str(protocol["chosen_step_seconds"])]
            or row["icrf_unit_direction"] != points[str(epoch)]
            or row["step_difference_arcsec_per_day"]
            != math.degrees(math.dist(*derivatives.values())) * 3600
        ):
            raise ValueError("Original complete stencil or quality check changed")
    return (
        protocol,
        reference,
        {
            "centers": 2,
            "available": sum(row["status"] == "available" for row in reference["rows"]),
            "incomplete": [
                row for row in reference["rows"] if row["status"] != "available"
            ],
            "available_position_probes": len(points),
            "original_reference_bytes_unchanged": True,
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    protocol, reference, validation = validate(args.directory)
    if args.validate_only:
        result = {"validation": validation, "candidate_compared": False}
    else:
        from scripts.audit_astrodice_lunar_precision import audit

        result = audit(protocol, reference, production_order=True)
        result["validation"] = validation
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key not in {"cases", "physical_sources"}
            },
            indent=2,
        )
    )
    return result.get("exit_code", 0)


if __name__ == "__main__":
    raise SystemExit(main())
