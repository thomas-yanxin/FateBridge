"""Diagnose Placidus convergence using its published defining equation.

This is a post-discrepancy diagnostic, with raw residuals and no retrospective
acceptance threshold. It neither replaces the frozen oracle nor certifies an
original-text edition. Common ERFA geometry does not validate UTC or EOP.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

from fatebridge.core.astro import runtime


def semiarc_residual(longitude, latitude, obliquity, armc, fraction):
    """H = -fraction * acos(-tan(phi)*tan(delta)), in degrees.

    Cusp 11 has completed 2/3 of its semidiurnal arc: H=-H0/3.
    Cusp 12 has completed 1/3: H=-2H0/3. RA/Dec are independently
    computed from a zero-latitude ecliptic point, without Swiss transforms.
    """
    lam, phi, eps = map(math.radians, (longitude, latitude, obliquity))
    ra = math.degrees(math.atan2(math.sin(lam) * math.cos(eps), math.cos(lam)))
    dec = math.asin(math.sin(lam) * math.sin(eps))
    cosine = -math.tan(phi) * math.tan(dec)
    if abs(cosine) > 1:
        return {"defined": False, "reason": "ecliptic_point_has_no_rise_set"}
    hour_angle = (armc - ra + 180) % 360 - 180
    semiarc = math.degrees(math.acos(cosine))
    return {
        "defined": True,
        "hour_angle_degrees": hour_angle,
        "semidiurnal_arc_degrees": semiarc,
        "signed_equation_residual_arcseconds": (hour_angle + fraction * semiarc) * 3600,
    }


def audit(path):
    reference = json.loads(path.read_text())
    rows = []
    for index, case in enumerate(reference["cases"]):
        p = case["input"]
        row = {"case_index": index, "input": p, "native": [], "astrolog": []}
        oracle = case["astrolog"]["P"]
        row["oracle_effective_system"] = oracle["effective_system"]
        try:
            cusps, _ = runtime.ephemeris_call(
                "houses_ex", p["jd_ut1"], p["latitude"], p["longitude"], b"P"
            )
        except runtime.swe.Error as error:
            row["native_error"] = str(error)
        else:
            for name, values in [("native", cusps), ("astrolog", oracle["cusps"])]:
                if (
                    name == "astrolog"
                    and oracle["effective_system"]
                    != reference["protocol"]["systems"]["P"]
                ):
                    continue
                row[name] = [
                    {
                        "cusp": i + 1,
                        "longitude": values[i],
                        **semiarc_residual(
                            values[i],
                            p["latitude"],
                            case["true_obliquity"],
                            case["armc"],
                            fraction,
                        ),
                    }
                    for i, fraction in [(10, 1 / 3), (11, 2 / 3)]
                ]
        rows.append(row)
    return {
        "scope": "Post-discrepancy diagnostic; common ERFA ARMC/obliquity, raw defining-equation residuals only",
        "source_url": "https://www.astro.com/swisseph/swisseph.htm",
        "source_section": "6.2.1",
        "reference_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "case_count": len(rows),
        "native_undefined_count": sum("native_error" in row for row in rows),
        "maximum_absolute_equation_residual_arcseconds": {
            name: max(
                abs(v["signed_equation_residual_arcseconds"])
                for row in rows
                for v in row[name]
                if v["defined"]
            )
            for name in ["native", "astrolog"]
        },
        "rows": rows,
        "frozen_full_audit_status_changed": False,
        "original_text_acceptance_established": False,
        "observational_accuracy_established": False,
        "new_acceptance_threshold": None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.reference)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print(result["maximum_absolute_equation_residual_arcseconds"])
