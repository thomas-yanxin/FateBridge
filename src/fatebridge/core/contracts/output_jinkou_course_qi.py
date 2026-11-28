"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

from typing import Any

from fatebridge.core.contracts.output_jinkou_qi_models import JinkouQiEvidence


def validate_course_qi(board: dict[str, Any]) -> None:
    block = board.get("qi_evidence")
    if isinstance(block, dict):
        JinkouQiEvidence.model_validate(block)
