"""Compare frozen native arithmetic with an independently frozen TDB model.

The native API is given the same nominal epoch as one rounded Julian date;
the reader retains two parts. Swiss documents TT approximately TDB. This diagnoses the
source/motion implementation and explicitly does not certify a TT instant.
"""

import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path

from scripts.astrodice.audit_astrodice_lunar_precision import audit
from scripts.astrodice.audit_astrodice_split_reference import (
    PROTOCOL_SHA256,
    REFERENCE_SHA256,
    validate,
)


def compare(protocol, reference, expected_model):
    validation = validate(protocol, reference)
    adapted = {
        "rows": [
            {
                "date_tt": row["date_tdb"],
                "cohort": row["cohort"],
                "status": "available",
                "missing_probes": [],
                "jd_tt": row["jd0_tdb"] + row["fraction_tdb"],
                "icrf_unit_direction": row["samples"]["0"]["selected_direction"],
                "icrf_direction_derivative_per_day": row[
                    "selected_direction_derivative_per_tdb_day"
                ],
                "step_difference_arcsec_per_day": row["step_difference_arcsec_per_day"],
            }
            for row in reference["rows"]
        ]
    }
    result = audit(protocol, adapted, production_order=True)
    if result["model"] != expected_model:
        raise ValueError("Expected physical source was not used")
    for row in result["cases"]:
        row["source_date_tdb"] = row.pop("date_tt")
        row["native_argument_as_tt_jd"] = next(
            r["jd_tt"]
            for r in adapted["rows"]
            if r["date_tt"] == row["source_date_tdb"]
        )
        split = next(
            r for r in reference["rows"] if r["date_tdb"] == row["source_date_tdb"]
        )
        row["native_single_jd_rounding_seconds"] = float(
            (
                Fraction(row["native_argument_as_tt_jd"])
                - Fraction(split["jd0_tdb"])
                - Fraction(split["fraction_tdb"])
            )
            * 86400
        )
    result["status"] = {
        0: "nominal_argument_lines_satisfied_not_TT_acceptance",
        1: "nominal_argument_numeric_failure",
        2: "reference_quality_unresolved",
    }[result["exit_code"]]
    result["independent_reference_validation"] = validation
    result["native_api_time_scale"] = "TT"
    result["reference_time_scale"] = "TDB"
    result["tt_tdb_conversion_applied"] = False
    result["tt_calendar_acceptance"] = False
    result["scope"] = (
        "Same nominal epoch through a rounded single-JD native TT API and the independent split-TDB model. Single-JD rounding is reported separately from the native TT/TDB approximation. Reception/deflection model differences remain explicit. Not a TT clock alignment test,not a regrading of any earlier failure,and not observation/original-text/authority certification."
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["protocol", "reference", "output"]:
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--model", required=True, choices=["swieph", "jpl"])
    args = parser.parse_args()
    digest = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()
    if digest(args.protocol) != PROTOCOL_SHA256:
        raise ValueError("Frozen split protocol changed")
    if digest(args.reference) != REFERENCE_SHA256:
        raise ValueError("Frozen split reference changed")
    result = compare(
        json.loads(args.protocol.read_text()),
        json.loads(args.reference.read_text()),
        args.model,
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
    raise SystemExit(result["exit_code"])
