"""Portable interpretation of timestamp text, before binding business facts."""

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
from tests.meihua_iso_clock_reference import load, load_supplement

CASES, PACKETS = load()
PACKETS += load_supplement()
SPEC = next(s for s in CATALOG if s.key == "meihua_analysis")


@pytest.mark.parametrize("row", CASES, ids=lambda r: r["id"])
def test_frozen_clock_label_semantics_or_explicit_rejection(row):
    if not row["valid"]:
        with pytest.raises(ValueError):
            _clock_datetime(row["text"], "frozen_clock_label", aware=row["aware"])
        return
    at = _clock_datetime(row["text"], "frozen_clock_label", aware=row["aware"])
    if "expected_wall" in row:
        assert at.replace(tzinfo=None).isoformat() == row["expected_wall"]
    if row["aware"]:
        assert at.astimezone(timezone.utc).isoformat() == row["expected_UTC"]
        assert at.utcoffset().total_seconds() * 1000000 == row["offset_microseconds"]
    else:
        assert at.utcoffset() is None


@pytest.mark.parametrize("row", PACKETS, ids=lambda r: r["id"])
def test_complete_controlled_packets_are_bound_before_public_execution(row):
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
        ("2000-01-06T09:17:43", True),
        ("2000-01-06T09:17:43Z", False),
        ("20000106T091743+0000", False),
        ("2000-W01-4T09:17:43+00:00", False),
    ],
)
def test_awareness_is_checked_after_portable_decoding(text, aware):
    with pytest.raises(ValueError, match="时区信息不符"):
        _clock_datetime(text, "awareness", aware=aware)
