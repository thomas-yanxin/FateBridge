"""Undefined local time never masquerades as a verified regional UTC offset."""

from datetime import datetime, timedelta, timezone

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
from tests.support.meihua_unspecified_clock_reference import load

ROWS = load()
SPEC = next(spec for spec in CATALOG if spec.key == "meihua_analysis")
BAD = [row for row in ROWS if row["previous_false_acceptance"]]


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
