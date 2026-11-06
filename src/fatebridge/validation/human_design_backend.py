"""Local mathematics of the full backend report, not a celestial signature."""

import math
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.profiles import ANALYTICAL_MEAN_NODE_MODEL
from fatebridge.core.human_design_backend import (
    backend_report_base,
    full_backend_report,
)
from fatebridge.core.human_design_joint import JointSnapshotCache
from fatebridge.core.human_design_mechanics import (
    bodygraph,
    longitude_activation,
    opposite_activation,
)
from fatebridge.core.human_design_solar_root_validation import verify_solar_root_context
from fatebridge.core.human_design_variables import variables_from_activations
from fatebridge.core.public_output import same_public_value as _same_value
from fatebridge.validation.human_design_joint import verify_joint_snapshot
from fatebridge.validation.human_design_provenance import verify_activation_provenance


def verify_full_backend_report(payload: dict[str, Any]) -> dict[str, Any]:
    errors = []
    checked = 0
    checked_roots = 0
    try:
        report = payload["ephemeris_backend_comparison"]
        node_mode = payload["calculation_policy"]["node_mode"]
        base = backend_report_base(payload, node_mode)
        status = report["status"]
        if base["selected_physical_models"] == ["moshier"]:
            expected = {**base, "status": "same_backend_not_independent"}
        elif status == "reference_unavailable":
            expected = {
                **base,
                "status": "reference_unavailable",
                "unavailable_reason": "native_reference_unavailable",
            }
        elif status == "reference_disabled_by_strict_jpl_policy":
            if payload["calculation_policy"].get(
                "physical_backend_policy"
            ) != "strict_jpl" or base["selected_physical_models"] != ["jpl"]:
                raise ValueError(
                    "Disabled reference does not match selected strict JPL policy"
                )
            expected = {
                **base,
                "status": status,
                "reference_computation_performed": False,
                "unavailable_reason": "jpl_mixed_request",
            }
        elif status == "full_backend_compared":
            reference = report["reference_chart"]
            if verify_solar_root_context(reference)["errors"]:
                raise ValueError("Inconsistent reference solar root witness")
            checked_roots = 1
            if verify_activation_provenance(reference["activations"], node_mode)[
                "errors"
            ]:
                raise ValueError("Inconsistent reference position provenance")
            if set(reference) != {
                "birth_utc",
                "design_utc",
                "design_solver",
                "time_scales",
                "activations",
                "variables",
                "bodygraph",
                "profile",
                "incarnation_cross",
            }:
                raise ValueError("Unexpected reference-chart fields")
            for side, rows in reference["activations"].items():
                if [a["body"] for a in rows] != [
                    a["body"] for a in payload["activations"][side]
                ]:
                    raise ValueError("Missing or reordered reference bodies")
                by_body = {a["body"]: a for a in rows}
                for row in rows:
                    source = {"Earth": "Sun", "SouthNode": "NorthNode"}.get(row["body"])
                    projected = (
                        opposite_activation(by_body[source]["longitude"])
                        if source
                        else longitude_activation(row["longitude"])
                    )
                    expected_row = {
                        "body": row["body"],
                        "longitude_speed": (
                            by_body[source]["longitude_speed"]
                            if source
                            else row["longitude_speed"]
                        ),
                        "ephemeris_model": (
                            ANALYTICAL_MEAN_NODE_MODEL
                            if node_mode == "mean"
                            and row["body"] in {"NorthNode", "SouthNode"}
                            else "moshier"
                        ),
                        "return_flags": runtime.swe.FLG_MOSEPH | runtime.swe.FLG_SPEED,
                        **(
                            {"native_return_flag_model": "moshier"}
                            if row["body"] in {"NorthNode", "SouthNode"}
                            else {}
                        ),
                        **projected,
                    }
                    if source:
                        expected_row["derived_from"] = source
                    if not math.isfinite(row["longitude_speed"]) or not _same_value(
                        row, expected_row
                    ):
                        raise ValueError(
                            "Reference activation arithmetic/model mismatch"
                        )
            graph = bodygraph(
                (a["gate"] for a in reference["activations"]["personality"]),
                (a["gate"] for a in reference["activations"]["design"]),
            )
            if not _same_value(reference["bodygraph"], graph) or not _same_value(
                reference["variables"],
                variables_from_activations(reference["activations"]),
            ):
                raise ValueError("Reference graph or Variable mismatch")
            if (
                verify_joint_snapshot(JointSnapshotCache().snapshot(reference))[
                    "status"
                ]
                != "verified_local_snapshot_mechanics"
            ):
                raise ValueError("Reference joint structure mismatch")
            birth = reference["time_scales"]["personality"]["jd_tt"]
            design = reference["time_scales"]["design"]["jd_tt"]
            solver = reference["design_solver"]
            suns = {
                side: next(a for a in rows if a["body"] == "Sun")
                for side, rows in reference["activations"].items()
            }
            residual = (
                suns["personality"]["longitude"] - suns["design"]["longitude"]
            ) % 360 - 88
            if (
                birth != payload["time_scales"]["personality"]["jd_tt"]
                or not 70 < birth - design < 110
                or solver["birth_jd_tt"] != birth
                or solver["design_jd_tt"] != design
                or solver["target_solar_arc_degrees"] != 88.0
                or abs(residual) > 1e-7
                or not math.isclose(residual, solver["residual_degrees"], abs_tol=1e-10)
                or not 0 <= solver["bracket_width_seconds"] <= 0.0002
            ):
                raise ValueError("Reference solar-arc context mismatch")
            expected = full_backend_report(payload, reference, node_mode)
            checked = 2
        else:
            raise ValueError("Invalid full-backend status")
        if not _same_value(report, expected):
            errors.append(
                {
                    "code": "full_backend_report_derivation_mismatch",
                    "path": "ephemeris_backend_comparison",
                }
            )
    except (
        KeyError,
        TypeError,
        ValueError,
        StopIteration,
        IndexError,
        AttributeError,
        OverflowError,
    ):
        errors.append(
            {
                "code": "invalid_full_backend_report",
                "path": "ephemeris_backend_comparison",
            }
        )
    return {
        "checked_snapshot_count": checked,
        "checked_adjacent_solar_root_count": checked_roots,
        "errors": errors,
        "astronomical_witness_certified": False,
    }
