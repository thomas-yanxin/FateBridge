"""Undefined local time never masquerades as a verified regional UTC offset."""

import gzip
import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.application.execution import (
    OutputContractError,
    execute_spec,
    execute_tool,
)
from fatebridge.core import meihua_clock_resolution as policy
from fatebridge.core.requests.divination import MeihuaAnalysisRequest
from fatebridge.services import divination as service
from fatebridge.services.tool_catalog import CATALOG
from tests.meihua_unspecified_clock_reference import digest, load

ROWS = load()
SPEC = next(spec for spec in CATALOG if spec.key == "meihua_analysis")
BAD = [
    row
    for row in ROWS
    if row["layers"]["service"].get("valid")
    and not row["case"]["expected_clock_resolvable"]
]


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row["case"]["id"])
def test_all355_frozen_undefined_defined_and_legacy_controls(row):
    args, case = row["arguments"], row["case"]
    for layer in ["service", "execution"]:
        value = (
            service.calculate_meihua_analysis(**args)
            if layer == "service"
            else execute_spec(SPEC, SPEC.request_model(**args))
        )
        assert ("error" not in value) is case["expected_clock_resolvable"], (
            case,
            value,
        )
        if case["expected_clock_resolvable"]:
            expected = row["layers"][layer]["result"]
            if case["id"] in {"zero-1", "zero-11"}:
                # The pre-repair code already preserved the requested GMT
                # label in six term receipts, rather than spelling it UTC.
                path = (
                    Path(__file__).parent
                    / "fixtures/architecture_refactor_v1/meihua-clock-before.json.gz"
                )
                raw = path.read_bytes()
                assert (
                    hashlib.sha256(raw).hexdigest()
                    == "52f002dc8b07aa0fd8b746ab34a38f49129e519cb8244c9832983c8a567f12f8"
                )
                frozen = json.loads(gzip.decompress(raw))[case["id"]]
                assert frozen["arguments"] == args
                assert frozen["original_sha256"][layer] == digest(expected)
                expected = frozen["before_repair"][layer]
            assert digest(value) == digest(expected)
            assert (
                value["meihua"]["calendar_policy"]["civil_clock_resolution"][
                    "instant_utc"
                ]
                == case["expected_utc"]
            )
        else:
            assert (
                value["error_code"] == "validation_error"
                and value["status_code"] == 422
            )
            assert value["retryable"] is False
            if case.get("status") == "selected_unspecified_type":
                assert value["issues"] == [
                    {"path": "analysis_timezone", "code": "unresolved_timezone_offset"}
                ]


@pytest.mark.parametrize("row", BAD, ids=lambda row: row["case"]["id"])
def test_every_original_false_acceptance_is_stopped_before_calendar_work(
    row, monkeypatch
):
    called = []

    def forbidden(*args, **kwargs):
        called.append(True)
        raise AssertionError("Undefined local time reached calendar computation")

    monkeypatch.setattr(service.BaZiCalendar, "get_four_pillars", forbidden)
    monkeypatch.setattr(service, "build_calendar_context", forbidden)
    value = service.calculate_meihua_analysis(**row["arguments"])
    assert value["status_code"] == 422 and not called


@pytest.mark.parametrize("row", BAD, ids=lambda row: row["case"]["id"])
def test_trusted_binding_rejects_original_self_consistent_bad_packets_before_projection(
    row,
):
    original = row["layers"]["execution"]["result"]
    saved = deepcopy(original)
    forged = replace(SPEC, bind=lambda request: (lambda: deepcopy(original), (), {}))
    request = MeihuaAnalysisRequest(**row["arguments"])
    with pytest.raises(OutputContractError):
        execute_spec(forged, request)
    result = execute_tool(forged, request, include_metadata=False)
    assert result["status_code"] == 500 and result["error_code"] == "internal_error"
    assert result["retryable"] is True
    assert original == saved


@pytest.mark.parametrize("seconds", [0, 3600, -3600, 68400, -68400])
def test_placeholder_designation_is_not_verified_by_any_numerical_offset(
    seconds, monkeypatch
):
    fake = datetime(
        2000, 1, 6, 12, tzinfo=timezone(timedelta(seconds=seconds), name="-00")
    )
    monkeypatch.setattr(policy, "resolve_civil_clock", lambda *args: fake)
    with pytest.raises(policy.MeihuaUnspecifiedClockError):
        policy.resolve_meihua_civil_clock(
            datetime(2000, 1, 6, 12), "synthetic_format_control", "+00:00"
        )
