"""Local flag/model/policy consistency; not an astronomical witness signature."""

import math
from typing import Any

from fatebridge.core.astro.profiles import ANALYTICAL_MEAN_NODE_MODEL
from fatebridge.core.human_design_mechanics import BODY_IDS
from fatebridge.core.human_design_provenance import position_flag_model
from fatebridge.validation.claims import _same_value

SIDES = ("personality", "design")
NODES = {"NorthNode", "SouthNode"}
EXPECTED_BODIES = set(BODY_IDS) | NODES | {"Earth"}


def verify_activation_provenance(
    activations: dict[str, Any], node_mode: str, *, require_swiss_files: bool = False
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    checked = 0
    try:
        if node_mode not in {"true", "mean"} or set(activations) != set(SIDES):
            raise ValueError("Invalid node mode or activation sides")
        for side in SIDES:
            rows = activations[side]
            if len(rows) != 13 or {row["body"] for row in rows} != EXPECTED_BODIES:
                raise ValueError("Incomplete activation provenance")
            by_body = {row["body"]: row for row in rows}
            for index, row in enumerate(rows):
                path = f"activations.{side}.{index}"
                checked += 1
                try:
                    native = position_flag_model(row["return_flags"])
                except (KeyError, ValueError, TypeError):
                    errors.append(
                        {"code": "invalid_position_return_flags", "path": path}
                    )
                    continue
                expected_model = (
                    ANALYTICAL_MEAN_NODE_MODEL
                    if node_mode == "mean" and row["body"] in NODES
                    else native
                )
                if row.get("ephemeris_model") != expected_model:
                    errors.append(
                        {"code": "activation_model_flag_mismatch", "path": path}
                    )
                if (
                    row["body"] in NODES
                    or row.get("native_return_flag_model") is not None
                ) and row.get("native_return_flag_model") != native:
                    errors.append({"code": "native_flag_label_mismatch", "path": path})
                if require_swiss_files and native != "swieph":
                    errors.append(
                        {"code": "required_swiss_backend_mismatch", "path": path}
                    )
                speed = row["longitude_speed"]
                if type(speed) not in {int, float} or not math.isfinite(speed):
                    errors.append({"code": "invalid_longitude_speed", "path": path})
            for source, derived in (("Sun", "Earth"), ("NorthNode", "SouthNode")):
                for key in (
                    "return_flags",
                    "ephemeris_model",
                    "longitude_speed",
                    "native_return_flag_model",
                ):
                    if not _same_value(
                        by_body[source].get(key), by_body[derived].get(key)
                    ):
                        errors.append(
                            {
                                "code": "opposition_provenance_mismatch",
                                "path": f"activations.{side}.{derived}.{key}",
                            }
                        )
    except (KeyError, ValueError, TypeError, OverflowError, AttributeError):
        errors.append(
            {
                "code": "incomplete_or_invalid_activation_provenance",
                "path": "activations",
            }
        )
    return {"errors": errors, "checked_activation_count": checked}


def verify_selected_provenance(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    checked = 0
    try:
        policy = payload["calculation_policy"]
        required = policy["require_swiss_files"]
        if type(required) is not bool:
            raise ValueError("Swiss-files policy must be a boolean")
        activations = payload["activations"]
        check = verify_activation_provenance(
            activations, policy["node_mode"], require_swiss_files=required
        )
        errors.extend(check["errors"])
        checked = check["checked_activation_count"]
        physical = sorted(
            {
                row["ephemeris_model"]
                for rows in activations.values()
                for row in rows
                if row["body"] in BODY_IDS
            }
        )
        expected = {
            "ephemeris_model": "+".join(physical),
            "ephemeris_model_scope": "physical_bodies",
            "position_frame": "geocentric_apparent_tropical_ecliptic_of_date",
            "position_frame_scope": "physical_bodies",
            "lunar_node_frame": "geocentric_tropical_ecliptic_of_date_mathematical_point",
            "nonphysical_factor_models": {
                side: {
                    row["body"]: row["ephemeris_model"]
                    for row in rows
                    if row["body"] not in BODY_IDS
                }
                for side, rows in activations.items()
            },
        }
        for key, value in expected.items():
            if not _same_value(policy.get(key), value):
                errors.append(
                    {
                        "code": "calculation_provenance_policy_mismatch",
                        "path": "calculation_policy." + key,
                    }
                )
        backend_policy = policy["physical_backend_policy"]
        if backend_policy not in {"auto", "strict_jpl"} or (
            backend_policy == "strict_jpl" and physical != ["jpl"]
        ):
            errors.append(
                {
                    "code": "physical_backend_policy_mismatch",
                    "path": "calculation_policy.physical_backend_policy",
                }
            )
    except (KeyError, ValueError, TypeError, AttributeError):
        errors.append(
            {
                "code": "incomplete_or_invalid_provenance_policy",
                "path": "calculation_policy",
            }
        )
    return {
        "errors": errors,
        "checked_activation_count": checked,
        "astronomical_witness_certified": False,
    }
