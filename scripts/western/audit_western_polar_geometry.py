"""Bounded common-axis/root evidence; preserve the earlier full audit failures."""

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from fatebridge.core.astro import runtime
from fatebridge.core.astro.house_axes import canonical_house_axes


def separation(a, b):
    return abs((a - b + 180) % 360 - 180) * 3600


def audit(reference, roots):
    if len(reference["cases"]) != len(roots["cases"]):
        raise ValueError("Root/reference case collections differ")
    rows = []
    root_rows = []
    for index, c in enumerate(reference["cases"]):
        p = c["input"]
        if roots["cases"][index]["input"] != p:
            raise ValueError("Root/reference geometry inputs differ")
        for code in reference["protocol"]["systems"]:
            row = {"case_index": index, "system": code}
            try:
                cusps, raw = runtime.ephemeris_call(
                    "houses_ex",
                    p["jd_ut1"],
                    p["latitude"],
                    p["longitude"],
                    code.encode(),
                )
            except runtime.swe.Error as error:
                row.update(
                    status="undefined_requested_method",
                    error=str(error),
                    expected=code in {"P", "K"} and abs(p["latitude"]) == 80,
                )
            else:
                if len(cusps) != 12 or not all(
                    math.isfinite(v) for v in (*cusps, *raw)
                ):
                    raise ValueError(
                        "Native geometry must contain twelve finite cusps and finite axes"
                    )
                physical, note = canonical_house_axes(
                    julian_day_ut1=p["jd_ut1"],
                    latitude=p["latitude"],
                    longitude=p["longitude"],
                    house_code=code.encode(),
                    native_angles=raw,
                )
                errors = {
                    key: separation(physical[i], c["erfa_vector_angles"][key])
                    for i, key in enumerate(["ascendant", "midheaven"])
                }
                row.update(
                    status="defined",
                    raw_axes=list(raw[:3]),
                    public_axes=list(physical[:3]),
                    axis_errors_arcseconds=errors,
                    matched=max(errors.values())
                    <= reference["protocol"]["angle_tolerance_arcseconds"],
                    house_axis_convention=note,
                )
                if code == "P":
                    root = roots["cases"][index]
                    if root["status"] != "solved":
                        raise ValueError("Unexpected root/method domain disagreement")
                    if len(root["cusps"]) != 12 or not all(
                        math.isfinite(v) for v in root["cusps"]
                    ):
                        raise ValueError(
                            "Independent roots must contain twelve finite cusps"
                        )
                    error = max(separation(a, b) for a, b in zip(cusps, root["cusps"]))
                    astrolog_error = max(
                        separation(a, b)
                        for a, b in zip(c["astrolog"]["P"]["cusps"], root["cusps"])
                    )
                    root_rows.append(
                        {
                            "case_index": index,
                            "native_maximum_cusp_error_arcseconds": error,
                            "native_matched": error
                            <= roots["protocol"]["cusp_tolerance_arcseconds"],
                            "astrolog_maximum_cusp_error_arcseconds": astrolog_error,
                            "astrolog_matched": astrolog_error
                            <= roots["protocol"]["cusp_tolerance_arcseconds"],
                        }
                    )
            rows.append(row)
    defined = [r for r in rows if r["status"] == "defined"]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Physical axes for all defined requested house methods; independent Placidus roots in the predeclared full-ecliptic rise/set domain",
        "case_count": len(reference["cases"]),
        "method_comparisons": len(rows),
        "defined_method_count": len(defined),
        "undefined_method_count": len(rows) - len(defined),
        "physical_axis_matched_count": sum(r["matched"] for r in defined),
        "maximum_public_axis_error_arcseconds": {
            key: max(r["axis_errors_arcseconds"][key] for r in defined)
            for key in ["ascendant", "midheaven"]
        },
        "placidus_defined_count": len(root_rows),
        "placidus_native_root_matches": sum(r["native_matched"] for r in root_rows),
        "placidus_astrolog_root_matches": sum(r["astrolog_matched"] for r in root_rows),
        "rows": rows,
        "placidus_roots": root_rows,
        "scoped_numerical_gate_passed": all(r["matched"] for r in defined)
        and all(r["native_matched"] for r in root_rows)
        and all(r.get("expected", True) for r in rows),
        "original_full_comparison_gate_replaced": False,
        "original_house_cusps_modified": False,
        "calendar_or_measured_EOP_independently_verified": False,
        "original_text_full_acceptance": False,
        "all_three_full_marks_established": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--roots", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    roots = json.loads(args.roots.read_text())
    if (
        roots["protocol"]["common_geometry_fixture_sha256"]
        != hashlib.sha256(args.reference.read_bytes()).hexdigest()
    ):
        raise ValueError("Reference differs from the frozen root protocol")
    result = audit(json.loads(args.reference.read_text()), roots)
    result["reference_sha256"] = hashlib.sha256(args.reference.read_bytes()).hexdigest()
    result["roots_sha256"] = hashlib.sha256(args.roots.read_bytes()).hexdigest()
    result["source_sha256"] = {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [
            Path(__file__),
            Path(__file__).parents[2] / "src/fatebridge/core/astro/house_axes.py",
        ]
    }
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print(
        {
            k: result[k]
            for k in [
                "physical_axis_matched_count",
                "defined_method_count",
                "placidus_native_root_matches",
                "placidus_astrolog_root_matches",
                "scoped_numerical_gate_passed",
            ]
        }
    )
    raise SystemExit(0 if result["scoped_numerical_gate_passed"] else 1)
