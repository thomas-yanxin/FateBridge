"""Verify every field against a separately supplied trusted original run."""

from __future__ import annotations

from copy import deepcopy

from fatebridge.core.human_design_line_catalogue import _canonical
from fatebridge.core.human_design_line_reading import METHOD
from fatebridge.services.human_design_line_reading import (
    LineReadingInputError,
    build_human_design_line_packet,
)
from fatebridge.utils.errors import EphemerisSourceError


def verify_human_design_line_packet(packet: dict, trusted_source_result: dict) -> dict:
    packet = deepcopy(packet)
    trusted_source_result = deepcopy(trusted_source_result)
    errors: list[dict[str, object]] = []
    original_matches = False
    try:
        expected = build_human_design_line_packet(trusted_source_result)
        original_matches = _canonical(packet.get("original_result")) == _canonical(
            trusted_source_result
        )
        if not original_matches:
            errors.append(
                {"code": "external_original_run_mismatch", "path": "original_result"}
            )
        for key in sorted(expected.keys() | packet.keys()):
            if key not in expected:
                errors.append({"code": "unbound_packet_field", "path": key})
            elif key not in packet or _canonical(packet[key]) != _canonical(
                expected[key]
            ):
                errors.append({"code": "source_bound_packet_mismatch", "path": key})
    except LineReadingInputError as exc:
        errors.append(
            {"code": "original_run_not_verified", "verification": exc.verification}
        )
    except EphemerisSourceError as exc:
        errors.append({"code": exc.reason})
    except (TypeError, ValueError, KeyError, AttributeError, RecursionError):
        errors.append({"code": "incomplete_or_malformed_line_packet"})
    return {
        "method_id": METHOD,
        "status": (
            "rejected" if errors else "verified_original_bound_line_reference_packet"
        ),
        "trusted_original_binding_matches": original_matches,
        "checked_activation_count": 0 if errors else 26,
        "complete384_line_semantics_accepted": False,
        "arbitrary_model_free_text_accepted": False,
        "real_world_prediction_validated": False,
        "errors": errors,
        "scope": "对外部可信完整回执重放原核验，并逐字段重建整个解释包。只验证已声明的固定组装与计算绑定，不认证出生记录、完整爻义、任意模型文字、物理精度或现实预测。",
    }
