"""Offset magnitude and sign must survive before binding the actual instant."""

from copy import deepcopy
from dataclasses import replace
from datetime import timezone

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.application.meihua_clock_binding import (
    _clock_datetime,
    require_meihua_clock_binding,
)
from fatebridge.core.requests.divination import MeihuaAnalysisRequest
from fatebridge.services.tool_catalog import CATALOG
from tests.meihua_fractional_binding_reference import load

PACKETS, PARSER = load()
SPEC = next(s for s in CATALOG if s.key == "meihua_analysis")


@pytest.mark.parametrize("row", PARSER, ids=lambda r: r["text"])
def test_parsed_offset_and_instant_match_independent_literals(row):
    at = _clock_datetime(row["text"], "frozen_parser", aware=row["aware"])
    if row["aware"]:
        assert at.astimezone(timezone.utc).isoformat() == row["expected_UTC"]
        assert at.utcoffset().total_seconds() * 1000000 == row["offset_microseconds"]
    else:
        assert at.isoformat() == row["expected_wall"] and at.utcoffset() is None


@pytest.mark.parametrize("row", PACKETS, ids=lambda r: r["id"])
def test_original_and_expanded_full_packets_keep_their_declared_meaning(row):
    req = MeihuaAnalysisRequest(**row["request"])
    if row["should_succeed"]:
        require_meihua_clock_binding(deepcopy(row["packet"]), req)
    else:
        with pytest.raises(ValueError):
            require_meihua_clock_binding(deepcopy(row["packet"]), req)
    forged = replace(SPEC, bind=lambda _: (lambda: deepcopy(row["packet"]), (), {}))
    result = execute_tool(forged, req)
    assert ("error" not in result) is row["should_succeed"]
    if not row["should_succeed"]:
        assert result["error_code"] == "internal_error" and result["retryable"] is True


@pytest.mark.parametrize(
    "text,aware",
    [
        (None, True),
        (123, True),
        ("not-a-time", True),
        ("2020-06-15T12:34:56", True),
        ("2020-06-15T12:34:56Z", False),
    ],
)
def test_parser_retains_type_and_awareness_rejections(text, aware):
    with pytest.raises((ValueError, TypeError)):
        _clock_datetime(text, "invalid", aware=aware)
