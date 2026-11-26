"""A verified offset selects an actual instant without replacing the calendar zone."""

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from fractions import Fraction

import pytest
import pytz

import fatebridge.services.divination as service
from fatebridge.application.meihua_clock_binding import (
    require_meihua_instant_binding,
)
from fatebridge.core.requests.divination import MeihuaAnalysisRequest
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.utils.civil_clock import resolve_civil_clock, utc_instant
from fatebridge.utils.civil_time import ZonedCalendar
from tests.support.transports import SPECS, business, rest, surface_calls
from tests.unit_test.fixtures.meihua_civil_clock import (
    CIVIL_CLOCK_CASES,
    CIVIL_CLOCK_FIXTURE,
    civil_clock_parameters,
)

HISTORICAL = json.loads(
    (CIVIL_CLOCK_FIXTURE / "historical-fold-supplement.json").read_text()
)


def test_original_zone_rules_and_expected_clocks_remain_frozen() -> None:
    manifest = json.loads((CIVIL_CLOCK_FIXTURE / "manifest.json").read_text())
    assert manifest["precedes_meihua_integration"]
    for name, digest in manifest["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        else:
            pass
        assert (
            hashlib.sha256((CIVIL_CLOCK_FIXTURE / name).read_bytes()).hexdigest()
            == digest
        )
    assert (
        len(CIVIL_CLOCK_CASES["valid"]) == 8 and len(CIVIL_CLOCK_CASES["invalid"]) == 10
    )


@pytest.mark.parametrize("zone", ["UTC", "GMT", "Z", "+00:00"])
def test_equivalent_utc_candidates_do_not_invent_a_repeated_clock(zone: str) -> None:

    at = resolve_civil_clock(datetime(2026, 10, 22, 12), zone, "+00:00")
    assert at.fold == 0
    assert utc_instant(at).isoformat() == "2026-10-22T12:00:00+00:00"


@pytest.mark.parametrize("case", HISTORICAL["cases"], ids=lambda c: c["id"])
def test_historical_subminute_offset_fold_preserves_each_actual_instant(case) -> None:
    lock = json.loads(
        (CIVIL_CLOCK_FIXTURE / "historical-fold-supplement-lock.json").read_text()
    )
    assert (
        hashlib.sha256((CIVIL_CLOCK_FIXTURE / lock["file"]).read_bytes()).hexdigest()
        == lock["sha256"]
    )
    out = calculate_meihua_analysis(**civil_clock_parameters(case))
    assert "error" not in out
    clock = out["meihua"]["calendar_policy"]["civil_clock_resolution"]
    assert clock["fold"] == case["fold"] and clock["instant_utc"] == case["utc"]


def test_historical_repeated_clock_uses_343_seconds_not_a_rounded_hour() -> None:
    rows = [
        calculate_meihua_analysis(**civil_clock_parameters(c))
        for c in HISTORICAL["cases"]
    ]
    assert rows[0]["meihua"]["seed"] == rows[1]["meihua"]["seed"]
    elapsed = [
        r["calendar_context"]["bazi_month_boundary"]["elapsed_seconds_since_start"]
        for r in rows
    ]
    assert (
        elapsed[1] - elapsed[0]
        == HISTORICAL["expected_elapsed_seconds_between_instants"]
        == 343
    )


@pytest.mark.parametrize("case", CIVIL_CLOCK_CASES["valid"], ids=lambda c: c["id"])
def test_explicit_offset_preserves_zone_and_hand_derived_utc(case) -> None:
    payload = civil_clock_parameters(case)
    assert MeihuaAnalysisRequest(**payload).analysis_utc_offset == case["offset"]
    out = calculate_meihua_analysis(**payload)
    assert "error" not in out
    clock = out["meihua"]["calendar_policy"]["civil_clock_resolution"]
    assert clock["timezone"] == case["zone"]
    assert clock["input_utc_offset"] == case["offset"]
    assert clock["resolved_utc_offset"] == case["offset"]
    assert clock["instant_utc"] == case["utc"]
    assert clock["fold"] == case["fold"]
    assert clock["rule_kind"] == "software_convention"
    assert out["analysis_context"]["timezone"] == case["zone"]
    assert out["analysis_context"]["civil_instant_utc"] == case["utc"]
    assert out["analysis_context"]["civil_utc_offset"] == case["offset"]
    assert out["calendar_context"]["timezone"] == case["zone"]
    assert (
        out["calendar_context"]["bazi_month_boundary"]["comparison_datetime"]
        == clock["local_datetime"]
    )
    assert out["meihua"]["rule_trace"][-1]["result"] == clock
    if "/" in case["zone"]:
        assert clock["timezone_rules"]["iana_version"] == pytz.OLSON_VERSION
        assert clock["timezone_rules"]["package_version"] == pytz.__version__
        with pytz.open_resource(case["zone"]) as resource:
            assert (
                clock["timezone_rules"]["tzif_sha256"]
                == hashlib.sha256(resource.read()).hexdigest()
            )
    else:
        pass


@pytest.mark.parametrize("case", CIVIL_CLOCK_CASES["valid"][:4], ids=lambda c: c["id"])
def test_verified_fold_is_passed_to_both_real_calendar_consumers(
    case, monkeypatch: pytest.MonkeyPatch
) -> None:

    four = service.BaZiCalendar.get_four_pillars
    calendar = service.build_calendar_context
    moments = []

    def capture_four(moment, **kw):
        moments.append(("four", moment, kw["timezone_name"]))
        return four(moment, **kw)

    def capture_calendar(moment, **kw):
        moments.append(("context", moment, kw["timezone_name"]))
        return calendar(moment, **kw)

    monkeypatch.setattr(service.BaZiCalendar, "get_four_pillars", capture_four)
    monkeypatch.setattr(service, "build_calendar_context", capture_calendar)
    out = service.calculate_meihua_analysis(**civil_clock_parameters(case))
    assert "error" not in out
    assert [label for label, _, _ in moments] == ["four", "context"]
    for _, moment, zone in moments:
        assert zone == case["zone"]
        assert moment.fold == case["fold"]
        assert utc_instant(moment).isoformat() == case["utc"]


@pytest.mark.parametrize("start,count,seconds", [(0, 2, 3600), (2, 2, 1800)])
def test_fold_choices_change_real_elapsed_time_without_inventing_a_different_cast(
    start: int, count: int, seconds: int
) -> None:
    rows = [
        calculate_meihua_analysis(**civil_clock_parameters(c))
        for c in CIVIL_CLOCK_CASES["valid"][start : start + count]
    ]
    assert rows[0]["meihua"]["seed"] == rows[1]["meihua"]["seed"]
    boundaries = [r["calendar_context"]["bazi_month_boundary"] for r in rows]
    assert (
        boundaries[1]["elapsed_seconds_since_start"]
        - boundaries[0]["elapsed_seconds_since_start"]
        == seconds
    )
    assert (
        boundaries[0]["elapsed_seconds_until_next"]
        - boundaries[1]["elapsed_seconds_until_next"]
        == seconds
    )


@pytest.mark.parametrize("case", CIVIL_CLOCK_CASES["invalid"], ids=lambda c: c["id"])
def test_gaps_or_incompatible_offsets_never_reach_the_calendar_engine(
    case, monkeypatch: pytest.MonkeyPatch
) -> None:

    called = []

    def forbidden(*args, **kwargs):
        called.append(True)
        raise AssertionError("Invalid civil clock reached calendar calculation")

    monkeypatch.setattr(service.BaZiCalendar, "get_four_pillars", forbidden)
    out = service.calculate_meihua_analysis(**civil_clock_parameters(case))
    assert out["error_code"] == "validation_error" and out["retryable"] is False
    assert not called


@pytest.mark.parametrize("offset", ["5.5", "+05:60", "+16:00", "", 8])
def test_malformed_explicit_offsets_are_rejected(offset: int | str) -> None:
    payload = {
        **civil_clock_parameters(CIVIL_CLOCK_CASES["valid"][5]),
        "analysis_utc_offset": offset,
    }
    out = calculate_meihua_analysis(**payload)
    assert out["error_code"] == "validation_error" and out["retryable"] is False


@pytest.mark.parametrize(
    "case",
    [
        CIVIL_CLOCK_CASES["valid"][0],
        CIVIL_CLOCK_CASES["valid"][1],
        CIVIL_CLOCK_CASES["valid"][3],
        CIVIL_CLOCK_CASES["valid"][4],
    ],
    ids=lambda c: c["id"],
)
def test_clock_resolution_is_projectable_on_rest_mcp_cli(case, surface_calls) -> None:
    spec = SPECS["meihua_analysis"]
    payload = civil_clock_parameters(case)
    fields = [
        "analysis_context",
        "meihua.seed",
        "meihua.calendar_policy.civil_clock_resolution",
        "meihua.rule_trace",
        "calendar_context.bazi_month_boundary",
    ]
    response, mcp, code, cli = surface_calls(
        spec,
        payload,
        projection={
            **{"fields": fields, "strict_fields": True},
            "response_char_limit": 0,
        },
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    assert (
        cli["meihua"]["calendar_policy"]["civil_clock_resolution"]["instant_utc"]
        == case["utc"]
    )


@pytest.mark.parametrize(
    "case,expected_issue",
    [
        pytest.param(
            CIVIL_CLOCK_CASES["invalid"][0],
            {
                "path": "analysis_utc_offset",
                "code": "ambiguous_local_time",
                "constraints": {"expected": ["-04:00", "-05:00"]},
            },
            id="fold-needs-offset",
        ),
        pytest.param(
            CIVIL_CLOCK_CASES["invalid"][1],
            {"path": "analysis_hour", "code": "nonexistent_local_time"},
            id="gap-needs-valid-clock",
        ),
        pytest.param(
            CIVIL_CLOCK_CASES["invalid"][3],
            {
                "path": "analysis_utc_offset",
                "code": "utc_offset_mismatch",
                "constraints": {"expected": ["-04:00", "-05:00"]},
            },
            id="wrong-offset",
        ),
        pytest.param(
            {**CIVIL_CLOCK_CASES["invalid"][0], "zone": "invalid/test-zone"},
            {"path": "analysis_timezone", "code": "invalid_timezone"},
            id="unknown-timezone",
        ),
    ],
)
def test_invalid_clocks_keep_the_same_nonretryable_error_on_all_surfaces(
    case, expected_issue, surface_calls
) -> None:
    spec = SPECS["meihua_analysis"]
    payload = civil_clock_parameters(case)
    response, mcp, code, cli = surface_calls(spec, payload)
    assert response.status_code == 422 and code != 0 and mcp.is_error
    for out in [response.json(), cli, mcp.structured_content]:
        assert out["error_code"] == "validation_error" and out["retryable"] is False
        assert out["issues"] == [expected_issue]
    if expected_issue["code"] == "ambiguous_local_time":
        payload[expected_issue["path"]] = expected_issue["constraints"]["expected"][0]
        response, mcp, code, _ = surface_calls(spec, payload)
        assert response.status_code == 200 and code == 0 and not mcp.is_error
    else:
        pass


def test_integral_second_binding_uses_complete_retained_solar_point(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    payload = {
        "analysis_year": 2024,
        "analysis_month": 8,
        "analysis_day": 7,
        "analysis_hour": 0,
        "analysis_minute": 9,
        "analysis_second": 16,
        "analysis_timezone": "UTC",
    }
    request = MeihuaAnalysisRequest(**payload)
    result = calculate_meihua_analysis(**payload)
    require_meihua_instant_binding(result, request)
    boundary = result["calendar_context"]["bazi_month_boundary"]["start_term"]
    point = boundary["civil_point"]
    retained = Fraction(int(point["numerator"]), int(point["denominator"]))
    display = ZonedCalendar.from_isoformat(boundary["datetime_with_offset"])
    assert retained != display.utc.julian_day_exact()

    missing_cap = deepcopy(result)
    del missing_cap["calendar_context"]["bazi_month_boundary"]["start_term"][
        "civil_point"
    ]["excluded_before"]
    with pytest.raises(ValueError, match="excluded_before"):
        require_meihua_instant_binding(missing_cap, request)

    missing_point = deepcopy(result)
    del missing_point["calendar_context"]["bazi_month_boundary"]["start_term"][
        "civil_point"
    ]
    with pytest.raises(ValueError, match="精确民用主点"):
        require_meihua_instant_binding(missing_point, request)

    del missing_point["calendar_context"]["bazi_month_boundary"]["start_term"][
        "comparison_policy"
    ]
    with pytest.raises(ValueError, match="精确民用主点"):
        require_meihua_instant_binding(missing_point, request)
