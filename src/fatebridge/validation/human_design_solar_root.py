"""Check the local numerical witness; never authenticate the ephemeris producer."""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

from fatebridge.core.astro.profiles import ANALYTICAL_MEAN_NODE_MODEL
from fatebridge.core.human_design import solar_root_subdivisions
from fatebridge.core.human_design_root_bodies import (
    derive_root_body_assessment,
    root_body_summary,
)
from fatebridge.core.human_design_root_family import derive_family, family_summary
from fatebridge.core.human_design_solar_lattice import derive_lattice, lattice_summary
from fatebridge.core.human_design_solar_root import (
    ROOT_POLICY,
    ROOT_SCOPE,
    SOLAR_COORDINATE_POLICY,
)
from fatebridge.validation.claims import _same_value


def verify_solar_root_context(chart: dict[str, Any]) -> dict[str, Any]:
    errors = []
    try:
        s = chart["design_solver"]
        w = s["numerical_precision"]
        birth = chart["time_scales"]["personality"]["jd_tt"]
        design = chart["time_scales"]["design"]["jd_tt"]
        if (
            any(
                type(s[k]) not in (float, int) or not math.isfinite(s[k])
                for k in (
                    "birth_jd_tt",
                    "design_jd_tt",
                    "days_before_birth",
                    "residual_degrees",
                    "bracket_width_seconds",
                )
            )
            or type(s["iterations"]) is not int
            or not 0 < s["iterations"] < 128
        ):
            raise ValueError("Malformed solar solver numbers")
        if (
            s["birth_jd_tt"] != birth
            or s["design_jd_tt"] != design
            or not 70 < birth - design < 110
            or s["days_before_birth"] != birth - design
            or type(s["target_solar_arc_degrees"]) is not float
            or s["target_solar_arc_degrees"] != 88.0
        ):
            raise ValueError("Detached solar epoch")
        p = w["birth_sun_longitude"]
        if type(p) is not float or not math.isfinite(p) or not 0 <= p < 360:
            raise ValueError("Malformed natal solar function value")
        residuals = []
        for key in ("lower", "upper", "selected"):
            row = w[key]
            if set(row) != {
                "jd_tt",
                "sun_longitude",
                "residual_degrees",
                "exact_residual",
            }:
                raise ValueError("Unexpected endpoint fields")
            if any(
                type(row[k]) is not float or not math.isfinite(row[k])
                for k in ("jd_tt", "sun_longitude", "residual_degrees")
            ):
                raise ValueError("Malformed endpoint values")
            if not 0 <= row["sun_longitude"] < 360:
                raise ValueError("Malformed endpoint angle")
            residual = (Fraction(p) - Fraction(row["sun_longitude"])) % 360 - 88
            if not _same_value(
                row["exact_residual"],
                {
                    "numerator": str(residual.numerator),
                    "denominator": str(residual.denominator),
                },
            ) or row["residual_degrees"] != float(residual):
                raise ValueError("Incorrect exact residual")
            residuals.append(residual)
        # The root and activations now request the identical native flags.
        # Even an ULP shift contradicts this internal binding. Exact equality
        # does not authenticate either native coordinates or physical timing.
        for side, observed in (
            ("personality", p),
            ("design", w["selected"]["sun_longitude"]),
        ):
            actual = next(
                a["longitude"] for a in chart["activations"][side] if a["body"] == "Sun"
            )
            if not _same_value(actual, observed):
                raise ValueError("Solar function detached from the assembled Sun")
        for key in ("lower", "upper"):
            endpoint = next(
                row
                for row in w["design_body_endpoint_assessment"]["evaluations"]
                if row["jd_tt"] == w[key]["jd_tt"]
            )
            if not _same_value(
                endpoint["native_positions"][0][0], w[key]["sun_longitude"]
            ):
                raise ValueError("Endpoint solar function detached from actual Sun")
        lo, hi = w["lower"]["jd_tt"], w["upper"]["jd_tt"]
        exact = lo == hi
        if exact:
            if residuals[0] != 0 or not _same_value(w["lower"], w["upper"]):
                raise ValueError("Not an observed function zero")
        elif not (
            lo < hi
            and math.nextafter(lo, math.inf) == hi
            and residuals[0] > 0 > residuals[1]
        ):
            raise ValueError("Not a final adjacent bracket")
        expected = min(
            (w["lower"], w["upper"]),
            key=lambda row: (
                abs(
                    Fraction(row["exact_residual"]["numerator"])
                    / Fraction(row["exact_residual"]["denominator"])
                ),
                row["jd_tt"],
            ),
        )
        if (
            not _same_value(w["selected"], expected)
            or design != expected["jd_tt"]
            or s["residual_degrees"] != expected["residual_degrees"]
            or abs(s["residual_degrees"]) > 1e-7
            or s["bracket_width_seconds"] != (hi - lo) * 86400
            or not 0 <= s["bracket_width_seconds"] <= 0.0002
        ):
            raise ValueError("Wrong selected root")
        fixed = {
            "sun_coordinate_policy": SOLAR_COORDINATE_POLICY,
            "local_solar_lattice": derive_lattice(
                p,
                lo,
                hi,
                [
                    {k: row[k] for k in ("jd_tt", "sun_longitude")}
                    for row in w["local_solar_lattice"]["samples"]
                ],
            ),
            "local_root_family": derive_family(
                s,
                chart["activations"]["personality"],
                chart["activations"]["design"],
                chart.get("calculation_policy", {}).get(
                    "node_mode",
                    (
                        "mean"
                        if next(
                            a
                            for a in chart["activations"]["design"]
                            if a["body"] == "NorthNode"
                        )["ephemeris_model"]
                        == ANALYTICAL_MEAN_NODE_MODEL
                        else "true"
                    ),
                ),
                (
                    [
                        {
                            k: row[k]
                            for k in ("jd_tt", "native_positions", "source_role")
                        }
                        for row in w["local_root_family"]["candidates"]
                    ]
                    if w["local_root_family"] is not None
                    else []
                ),
                require_swiss_files=chart.get("calculation_policy", {}).get(
                    "require_swiss_files", False
                ),
                physical_backend_policy=chart.get("calculation_policy", {}).get(
                    "physical_backend_policy", "auto"
                ),
            ),
            "method_id": "human_design_adjacent_float_solar_root_v1",
            "selection_policy": ROOT_POLICY,
            "termination": (
                "observed_exact_function_zero"
                if exact
                else "adjacent_float_TT_endpoints"
            ),
            "physical_time_accuracy_certified": False,
            "other_bodies_bracket_sensitivity_assessed": True,
            "design_body_endpoint_assessment": derive_root_body_assessment(
                s,
                chart["activations"]["personality"],
                chart["activations"]["design"],
                chart.get("calculation_policy", {}).get(
                    "node_mode",
                    (
                        "mean"
                        if next(
                            a
                            for a in chart["activations"]["design"]
                            if a["body"] == "NorthNode"
                        )["ephemeris_model"]
                        == ANALYTICAL_MEAN_NODE_MODEL
                        else "true"
                    ),
                ),
                w["design_body_endpoint_assessment"]["evaluations"],
                require_swiss_files=chart.get("calculation_policy", {}).get(
                    "require_swiss_files", False
                ),
                physical_backend_policy=chart.get("calculation_policy", {}).get(
                    "physical_backend_policy", "auto"
                ),
            ),
            "scope": ROOT_SCOPE,
            **solar_root_subdivisions(s),
        }
        fixed["design_body_endpoint_summary"] = root_body_summary(
            fixed["design_body_endpoint_assessment"]
        )
        fixed["local_solar_lattice_summary"] = lattice_summary(
            fixed["local_solar_lattice"]
        )
        fixed["local_root_family_summary"] = family_summary(fixed["local_root_family"])
        if set(w) != set(fixed) | {
            "birth_sun_longitude",
            "lower",
            "upper",
            "selected",
        } or any(not _same_value(w[k], v) for k, v in fixed.items()):
            raise ValueError("Wrong solar witness or invented precision certificate")
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        ZeroDivisionError,
        IndexError,
        StopIteration,
        AttributeError,
    ):
        errors.append(
            {"code": "solar_root_numerical_witness_mismatch", "path": "design_solver"}
        )
    return {
        "errors": errors,
        "checked_root_count": 0 if errors else 1,
        "scope": "Local adjacent-TT and exact-residual consistency only, not a physical error bound or proof of TT-to-coordinate truth.",
    }
