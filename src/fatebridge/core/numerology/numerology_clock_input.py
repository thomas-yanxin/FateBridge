"""Lexical birth-clock provenance; displayed digits do not certify accuracy."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any

from fatebridge.core.numerology.numerology_inputs import (
    CLOCK_INPUT_POLICY_ID,
    CLOCK_INPUT_SCOPE,
    CLOCK_POLICY_ID,
    DISPLAY_SCOPE,
    ParsedBirthClock,
    birth_clock_input_record,
    parse_birth_clock,
)
from fatebridge.utils.errors import NumerologySourceError


def preserve_birth_clock_text(value: object) -> str:
    """Validate the local clock while retaining the supplied components."""
    return parse_birth_clock(value).supplied_text


def clock_input_representation(value: object) -> dict[str, Any]:
    """Build a receipt for the validated text of a birth clock."""
    return birth_clock_input_record(parse_birth_clock(value))


def require_clock_input_binding(
    result: dict[str, Any], *, requested_time: str | None = None
) -> None:
    """Bind full current results before projection to the actual request text.

    An old receipt without a supplied-text record remains unknown when no
    request is available. Never reconstruct its original components from a
    canonical output. This guard does not reapply today's regional time rules.
    """

    try:
        evidence = result["numerology_evidence"]
        clock = evidence["birth_clock"]
        receipt = clock.get("input_representation")
        if requested_time is None and receipt is None:
            return
        original = (
            requested_time if requested_time is not None else receipt["supplied_text"]
        )
        expected = clock_input_representation(original)
        if not isinstance(receipt, dict):
            raise ValueError("Missing original clock provenance")
        if any(
            k not in receipt or type(receipt[k]) is not type(v) or receipt[k] != v
            for k, v in expected.items()
        ):
            raise ValueError("Clock provenance differs from request")
        if any(type(v) is not int for v in receipt["calculation_defaults"].values()):
            raise ValueError("Defaults must be integer reference components")
        if result["input_normalized"]["time"] != expected["normalized_clock"]:
            raise ValueError("Normalized calculation clock differs from input")
        civil = datetime.fromisoformat(clock["civil_datetime"])
        if civil.time() != time.fromisoformat(expected["normalized_clock"]):
            raise ValueError("Civil clock differs from supplied calculation reference")
        traces = [
            r["facts"]
            for r in evidence["rule_trace"]
            if r.get("rule_id") == CLOCK_POLICY_ID
        ]
        if len(traces) != 1 or traces[0] != clock:
            raise ValueError("Clock trace differs from output")
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise NumerologySourceError("runtime_numerology_clock_input_conflict") from exc
