"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

from typing import Any

from fatebridge.core.canping_schedule_basis import (
    APPLIED,
    LEGACY,
    POLICY_ID,
    build_schedule_basis,
    schedule_basis_snapshot,
)
from fatebridge.utils.errors import NumerologySourceError


def _registered_facts_match(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _registered_facts_match(actual[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(_registered_facts_match(a, e) for a, e in zip(actual, expected))
        )
    return type(actual) is type(expected) and actual == expected


def require_schedule_binding(result: dict) -> None:
    """Validate present receipts before transport projection can hide a conflict.

    Missing context in a partial library result remains unknown. Where the
    actual timing and birth clock are present, compare against those facts;
    internal agreement of a forged source map is insufficient.
    """
    from pydantic import ValidationError

    from fatebridge.core.output_canping_schedule import CanpingScheduleBasis

    timing = result.get("canping_timing")
    if not isinstance(timing, dict) or timing.get("schedule_basis") is None:
        return
    basis = timing["schedule_basis"]
    try:
        CanpingScheduleBasis.model_validate(basis)
        if not isinstance(basis, dict):
            raise ValueError("配运回执必须为对象。")
        profile = timing.get("profile_id")
        if (
            profile is not None
            and basis.get("profile_id") is not None
            and profile != basis["profile_id"]
        ):
            raise ValueError("配运回执的方法与同次计算不符。")
        rows = result.get("dayun")
        if (
            isinstance(rows, list)
            and not rows
            and any(
                timing.get(key) is not None for key in ("first_row", "first_period")
            )
        ):
            raise ValueError("实际配运序为空，不能保留非空首行或首运摘要。")
        if isinstance(rows, list) and rows:
            # Compare against the actual calculation, not just two internally
            # agreeing summaries. This also checks text, column, numbers, ages
            # and both boundaries before projection can remove the full rows.
            for key in ("first_row", "first_period"):
                if key not in timing:
                    continue
                expected_row = (
                    None if key == "first_period" and profile == LEGACY else rows[0]
                )
                if not (
                    _registered_facts_match(timing[key], expected_row)
                    and _registered_facts_match(expected_row, timing[key])
                ):
                    raise ValueError("首行或首运摘要与同次实际配运行不一致。")
        evidence = result.get("numerology_evidence")
        clock = evidence.get("birth_clock") if isinstance(evidence, dict) else None
        mapping_keys = (
            {"calendar_scope"}
            if profile == LEGACY
            else {
                "calendar_policy",
                "reference_policy",
                "boundary_policy",
                "dst_policy",
            }
        )
        expected = None
        if (
            profile in APPLIED
            and isinstance(clock, dict)
            and mapping_keys <= timing.keys()
        ):
            expected = build_schedule_basis(profile, timing, clock)
            if not _registered_facts_match(basis, expected):
                raise ValueError("配运回执与同次实际政策或钟面不符。")
        trace = evidence.get("rule_trace") if isinstance(evidence, dict) else None
        if trace is not None:
            if not isinstance(trace, list) or any(
                not isinstance(r, dict) for r in trace
            ):
                raise ValueError("配运来源轨迹必须为记录列表。")
            copies = [r for r in trace if r.get("rule_id") == POLICY_ID]
            registered = (
                expected
                if expected is not None
                else {
                    k: v
                    for k, v in basis.items()
                    if k in CanpingScheduleBasis.model_fields
                }
            )
            if len(copies) != 1 or not _registered_facts_match(
                copies[0].get("facts"), registered
            ):
                raise ValueError("配运来源轨迹与同次回执不符。")
        snapshot = result.get("snapshot_text")
        if snapshot is not None:
            marker = "[配运原典与日期映射]"
            if not isinstance(snapshot, str) or snapshot.count(marker) != 1:
                raise ValueError("配运释文段缺失或重复。")
            section = snapshot[snapshot.index(marker) :].split("\n\n[", 1)[0]
            if section.strip() != schedule_basis_snapshot(basis).strip():
                raise ValueError("配运释文与同次回执不符。")
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise NumerologySourceError(
            "runtime_canping_schedule_binding_conflict"
        ) from exc
