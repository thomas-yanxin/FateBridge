"""Re-execute the finite interval algorithm using supplied native scalars."""

from typing import Any

from fatebridge.core.human_design_interval_summary import unassessed_interval
from fatebridge.core.human_design_sample_witness import unpack_sample_witnesses
from fatebridge.core.human_design_sensitivity import (
    LEGACY_METHOD,
    METHOD,
    assess_birth_interval,
)
from fatebridge.validation.claims import _same_value

# Known complete output schemas from before coordinate interval probes. These
# identify historical contracts, never privileged input dates or passing rows.
PRE_COORDINATE_INTERVAL_CONTRACTS = frozenset(
    {
        "9635e75d1b51f21e1b473f773f4b226447f940d60b5070e709bf63fd8665b74d",
        "89c717f00c649ed5373e3a803fb1c6b3190c68b63c1c55dd8f4fdd54aa71927d",
        "5b8d14718cf5015eb9b4f89740da82ca63c9a0af12c5c2169df87ebb0563e04e",
        "fa56c62beed008e190217f69fc8eb89f7abe858c5a4c46fb0d0ac0e77c6c93d4",
        "f66b042abb0a9b04261477989e147609fc9b011cea0e4613fb4183e6c483ae7e",
        "30e391eb24c92dc5b61f9f27b296536cc5891c34367b73e7cc33daee91b8f765",
        "168d79463454686ee3e8afb731ea2ee8d29ae906f0d9ca88c5cf364ea7daba30",
        "570410131790378bf9a4e34e1f7031d5767e6dd9103c88426746099d870400b2",
        "56806b2004d57149ad0067f1e7cb090d4fd3325413a6f21b04b4dc91dd02d4aa",
    }
)


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
            method = report.get("method_id")
            legacy = method == LEGACY_METHOD
            if method not in (LEGACY_METHOD, METHOD) or (
                legacy
                and payload.get("run_metadata", {}).get("contract_sha256")
                not in PRE_COORDINATE_INTERVAL_CONTRACTS
            ):
                raise ValueError("Unknown interval method or legacy contract downgrade")
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
                _coordinate_extrema=not legacy,
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
