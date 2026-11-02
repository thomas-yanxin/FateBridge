"""Require a separate trusted complete original and compare every packet field."""

from copy import deepcopy

from fatebridge.core.human_design_context_lines import METHOD
from fatebridge.core.human_design_line_catalogue import _canonical
from fatebridge.services.human_design_context_lines import (
    build_human_design_context_packet,
)
from fatebridge.services.human_design_line_reading import LineReadingInputError
from fatebridge.utils.errors import EphemerisSourceError


def verify_human_design_context_packet(
    packet: dict, trusted_source_result: dict, *, reference_category: str = "lines"
) -> dict:
    packet, source = deepcopy(packet), deepcopy(trusted_source_result)
    errors: list[dict[str, object]] = []
    matches, checked = False, 0
    try:
        expected = build_human_design_context_packet(
            source, reference_category=reference_category
        )
        matches = _canonical(
            packet.get("nominal_packet_v1", {}).get("original_result")
        ) == _canonical(source)
        if not matches:
            errors.append(
                {
                    "code": "external_original_run_mismatch",
                    "path": "nominal_packet_v1.original_result",
                }
            )
        for key in sorted(expected.keys() | packet.keys()):
            if key not in expected:
                errors.append({"code": "unbound_packet_field", "path": key})
            elif key not in packet or _canonical(packet[key]) != _canonical(
                expected[key]
            ):
                errors.append(
                    {"code": "source_bound_context_packet_mismatch", "path": key}
                )
        if not errors:
            checked = expected["coverage"]["retained_complete_chart_contexts"]
    except LineReadingInputError as exc:
        errors.append(
            {"code": "original_run_not_verified", "verification": exc.verification}
        )
    except EphemerisSourceError as exc:
        errors.append({"code": exc.reason})
    except (
        TypeError,
        ValueError,
        KeyError,
        AttributeError,
        RecursionError,
        IndexError,
    ):
        errors.append({"code": "incomplete_or_malformed_context_packet"})
    return {
        "method_id": (
            METHOD
            if reference_category == "lines"
            else {
                "lines_v3": "human_design_retained_context_line_reference_packet_v3",
                "lines_v4": "human_design_retained_context_line_reference_packet_v4",
                "lines_v5": "human_design_retained_context_line_reference_packet_v5",
                "lines_v6": "human_design_retained_context_line_reference_packet_v6",
                "lines_v7": "human_design_retained_context_line_reference_packet_v7",
            }.get(reference_category, "unsupported_reference_category")
        ),
        "status": (
            "rejected" if errors else "verified_original_bound_context_line_packet"
        ),
        "trusted_original_binding_matches": matches,
        "checked_complete_chart_contexts": checked,
        "checked_activation_context_bindings": 26 * checked,
        "complete384_line_semantics_accepted": False,
        "arbitrary_model_free_text_accepted": False,
        "real_world_prediction_validated": False,
        "errors": errors,
        "scope": "以外部可信原始回执重放原核验，逐字段重建所有实际完整盘上下文及解释绑定。不认证星历物理精度、原生执行、连续区间、完整原典语义或现实预测。",
    }
