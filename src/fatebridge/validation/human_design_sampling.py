"""Re-execute the finite interval algorithm using supplied native scalars."""

from typing import Any

from fatebridge.core.human_design_interval_summary import unassessed_interval
from fatebridge.core.human_design_sample_witness import unpack_sample_witnesses
from fatebridge.core.human_design_sensitivity import (
    METHOD,
    assess_birth_interval,
)
from fatebridge.validation.claims import _same_value


def verify_sampled_interval(payload: dict[str, Any]) -> dict[str, Any]:
    checked = 0
    errors = []
    try:
        report = payload["time_sensitivity"]
        policy = payload["calculation_policy"]
        radius = policy["birth_time_uncertainty_minutes"]
        if type(radius) is not int or not 0 <= radius <= 60:
            raise ValueError("Invalid declared interval radius")
        if radius == 0:
            expected = unassessed_interval()
        else:
            if report.get("method_id") != METHOD:
                raise ValueError("Unknown interval method")
            raw = unpack_sample_witnesses(
                report["evaluation_witnesses"],
                policy["node_mode"],
                require_swiss_files=policy["require_swiss_files"],
                physical_backend_policy=policy["physical_backend_policy"],
            )
            center = payload["time_scales"]["personality"]["jd_tt"]
            if center not in raw:
                raise ValueError("Missing nominal native witness")
            for key in (
                "birth_utc",
                "design_utc",
                "time_scales",
                "design_solver",
                "activations",
                "bodygraph",
                "variables",
                "profile",
                "incarnation_cross",
            ):
                if not _same_value(raw[center][key], payload[key]):
                    raise ValueError("Nominal sample detached from selected chart")
            used = {center}

            def lookup(tt: float) -> dict[str, Any]:
                if tt not in raw:
                    raise ValueError("A consumed interval evaluation was omitted")
                used.add(tt)
                return raw[tt]

            expected = assess_birth_interval(
                payload,
                radius,
                policy["node_mode"],
                require_swiss_files=policy["require_swiss_files"],
                _chart_reader=lookup,
            )
            if used != set(raw):
                raise ValueError("Unused or invented native sample witness")
            checked = len(used)
        if not _same_value(report, expected):
            raise ValueError(
                "Interval report contradicts its complete scalar witnesses"
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
                "code": "sampled_interval_witness_or_summary_mismatch",
                "path": "time_sensitivity",
            }
        )
    return {
        "errors": errors,
        "checked_interval_evaluation_count": checked,
        "native_execution_authenticated": False,
        "scope": "Finite supplied native scalars, actual evaluation set, station/refinement replay and complete report consistency only. Modern UTC labels use the unchanged0.2ms frozen-table tolerance; historical UT1/UTC realization, actual native execution, physical positions and continuous completeness remain uncertified.",
    }
