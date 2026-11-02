"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

from typing import Any

from fatebridge.core.output_jinkou_qi import compare

from .metaphysics.jinkou_qi import qi_metadata


def validate_course_qi(board: dict[str, Any]) -> None:
    # Runtime import avoids a schema import cycle. The child validator calls only
    # validate_qi_fields, so trace-only views do not recurse through the course.
    from fatebridge.core.output_jinkou_qi_models import JinkouQiEvidence

    block = board.get("qi_evidence")
    if isinstance(block, dict):
        JinkouQiEvidence.model_validate(block)
    traces = [
        t
        for t in board.get("rule_trace") or []
        if t.get("rule_id") == "jinkou.month_day_qi"
    ]
    if len(traces) > 1:
        raise ValueError("月建日辰得气轨迹不可重复")
    for trace in traces:
        metadata = qi_metadata()
        compare(trace, {k: metadata[k] for k in ("source_url", "source_section")})
        result = trace.get("result")
        if isinstance(result, dict):
            JinkouQiEvidence.model_validate(result)
            if isinstance(block, dict):
                compare(result, block)
