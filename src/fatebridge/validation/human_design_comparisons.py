"""Rebuild complete node diagnostic reports from their supplied witnesses."""

from typing import Any

from fatebridge.core.human_design_node_comparisons import (
    node_convention_report,
    reconstruct_node_reference,
)
from fatebridge.core.human_design_precision import (
    node_backend_base,
    node_backend_report,
)
from fatebridge.validation.claims import _same_value


def verify_node_comparison_reports(payload: dict[str, Any]) -> dict[str, Any]:
    errors = []
    checked = 0
    for path in ("node_convention_comparison", "node_backend_comparison"):
        try:
            policy = payload["calculation_policy"]
            node_mode = policy["node_mode"]
            required = policy["require_swiss_files"]
            if type(required) is not bool or node_mode not in {"true", "mean"}:
                raise ValueError("Invalid selected convention or Swiss policy")
            report = payload[path]
            expected: dict[str, Any]
            if path == "node_convention_comparison":
                other = "mean" if node_mode == "true" else "true"
                reference = reconstruct_node_reference(
                    payload,
                    report["reference_node_positions"],
                    other,
                    require_swiss_files=required,
                )
                expected = node_convention_report(payload, reference, node_mode)
            else:
                base = node_backend_base(payload, node_mode)
                status = report["status"]
                if node_mode == "mean":
                    expected = {
                        **base,
                        "status": "analytic_mean_node_not_cross_validated",
                        "reference_backend": None,
                        "mechanical_comparison": None,
                    }
                elif policy["physical_backend_policy"] == "strict_jpl":
                    expected = {
                        **base,
                        "status": "reference_disabled_by_strict_jpl_policy",
                        "reference_computation_performed": False,
                        "unavailable_reason": "jpl_mixed_request",
                        "mechanical_comparison": None,
                    }
                elif status == "reference_unavailable":
                    expected = {
                        **base,
                        "status": "reference_unavailable",
                        "mechanical_comparison": None,
                    }
                    if "unavailable_side" in report:
                        if report["unavailable_side"] not in {"personality", "design"}:
                            raise ValueError("Invalid unavailable side")
                        expected["unavailable_side"] = report["unavailable_side"]
                elif status in {
                    "cross_backend_compared",
                    "same_backend_not_independent",
                }:
                    reference = reconstruct_node_reference(
                        payload,
                        report["reference_node_positions"],
                        node_mode,
                        required_model="moshier",
                    )
                    expected = node_backend_report(payload, reference, node_mode)
                else:
                    raise ValueError("Invalid node backend outcome")
            if not _same_value(report, expected):
                raise ValueError(
                    "Node report contradicts its selected chart or reference"
                )
            checked += 1
        except (
            KeyError,
            TypeError,
            ValueError,
            StopIteration,
            IndexError,
            AttributeError,
            OverflowError,
        ):
            errors.append({"code": "node_comparison_witness_mismatch", "path": path})
    return {
        "errors": errors,
        "checked_node_report_count": checked,
        "astronomical_witness_certified": False,
        "scope": "Only local deterministic reconstruction of complete node comparison reports from supplied coordinates/flags and selected TT; does not authenticate native execution, unavailable outcomes, ephemeris truth, source doctrine or external predictions.",
    }
