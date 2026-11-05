"""A verified offset selects an actual instant without replacing the calendar zone."""

import asyncio
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core.requests.divination import MeihuaAnalysisRequest
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.utils.civil_clock import utc_instant
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

FIXTURE = Path(__file__).parents[1] / "fixtures/meihua_civil_clock_v1"
CASES = json.loads((FIXTURE / "cases.json").read_text())
HISTORICAL = json.loads((FIXTURE / "historical-fold-supplement.json").read_text())


def parameters(case):
    wall = datetime.fromisoformat(case["wall"])
    out = {
        "analysis_year": wall.year,
        "analysis_month": wall.month,
        "analysis_day": wall.day,
        "analysis_hour": wall.hour,
        "analysis_minute": wall.minute,
        "analysis_timezone": case["zone"],
    }
    if case["offset"] is not None:
        out["analysis_utc_offset"] = case["offset"]
    return out


def test_original_zone_rules_and_expected_clocks_remain_frozen():
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    assert manifest["precedes_meihua_integration"]
    for name, digest in manifest["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    assert len(CASES["valid"]) == 8 and len(CASES["invalid"]) == 10


@pytest.mark.parametrize("zone", ["UTC", "GMT", "Z", "+00:00"])
def test_equivalent_utc_candidates_do_not_invent_a_repeated_clock(zone):
    from fatebridge.utils.civil_clock import resolve_civil_clock

    at = resolve_civil_clock(datetime(2026, 10, 22, 12), zone, "+00:00")
    assert at.fold == 0
    assert utc_instant(at).isoformat() == "2026-10-22T12:00:00+00:00"


@pytest.mark.parametrize("case", HISTORICAL["cases"], ids=lambda c: c["id"])
def test_historical_subminute_offset_fold_preserves_each_actual_instant(case):
    lock = json.loads((FIXTURE / "historical-fold-supplement-lock.json").read_text())
    assert (
        hashlib.sha256((FIXTURE / lock["file"]).read_bytes()).hexdigest()
        == lock["sha256"]
    )
    out = calculate_meihua_analysis(**parameters(case))
    assert "error" not in out
    clock = out["meihua"]["calendar_policy"]["civil_clock_resolution"]
    assert clock["fold"] == case["fold"] and clock["instant_utc"] == case["utc"]


def test_historical_repeated_clock_uses_343_seconds_not_a_rounded_hour():
    rows = [calculate_meihua_analysis(**parameters(c)) for c in HISTORICAL["cases"]]
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


@pytest.mark.parametrize("case", CASES["valid"], ids=lambda c: c["id"])
def test_explicit_offset_preserves_zone_and_hand_derived_utc(case):
    payload = parameters(case)
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
        assert clock["timezone_rules"]["iana_version"] == "2026e"
        assert len(clock["timezone_rules"]["tzif_sha256"]) == 64


@pytest.mark.parametrize("case", CASES["valid"][:4], ids=lambda c: c["id"])
def test_verified_fold_is_passed_to_both_real_calendar_consumers(case, monkeypatch):
    import fatebridge.services.divination as service

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
    out = service.calculate_meihua_analysis(**parameters(case))
    assert "error" not in out
    assert [label for label, _, _ in moments] == ["four", "context"]
    for _, moment, zone in moments:
        assert zone == case["zone"]
        assert moment.fold == case["fold"]
        assert utc_instant(moment).isoformat() == case["utc"]


@pytest.mark.parametrize("start,count,seconds", [(0, 2, 3600), (2, 2, 1800)])
def test_fold_choices_change_real_elapsed_time_without_inventing_a_different_cast(
    start, count, seconds
):
    rows = [
        calculate_meihua_analysis(**parameters(c))
        for c in CASES["valid"][start : start + count]
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


@pytest.mark.parametrize("case", CASES["invalid"], ids=lambda c: c["id"])
def test_gaps_or_incompatible_offsets_never_reach_the_calendar_engine(
    case, monkeypatch
):
    import fatebridge.services.divination as service

    called = []

    def forbidden(*args, **kwargs):
        called.append(True)
        raise AssertionError("Invalid civil clock reached calendar calculation")

    monkeypatch.setattr(service.BaZiCalendar, "get_four_pillars", forbidden)
    out = service.calculate_meihua_analysis(**parameters(case))
    assert out["error_code"] == "validation_error" and out["retryable"] is False
    assert not called


@pytest.mark.parametrize("offset", ["5.5", "+05:60", "+16:00", "", 8])
def test_malformed_explicit_offsets_are_rejected(offset):
    payload = {**parameters(CASES["valid"][5]), "analysis_utc_offset": offset}
    out = calculate_meihua_analysis(**payload)
    assert out["error_code"] == "validation_error" and out["retryable"] is False


@pytest.mark.parametrize(
    "case",
    [CASES["valid"][0], CASES["valid"][1], CASES["valid"][3], CASES["valid"][4]],
    ids=lambda c: c["id"],
)
def test_clock_resolution_is_projectable_on_rest_mcp_cli(case, rest, tmp_path, capsys):
    spec = SPECS["meihua_analysis"]
    payload = parameters(case)
    fields = [
        "analysis_context",
        "meihua.seed",
        "meihua.calendar_policy.civil_clock_resolution",
        "meihua.rule_trace",
        "calendar_context.bazi_month_boundary",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[
            *(("fields", f) for f in fields),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
        ],
    )
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
        ],
    )
    mcp = asyncio.run(native(spec, payload, fields=fields, strict_fields=True))
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    assert (
        cli["meihua"]["calendar_policy"]["civil_clock_resolution"]["instant_utc"]
        == case["utc"]
    )


@pytest.mark.parametrize(
    "case",
    [CASES["invalid"][0], CASES["invalid"][1], CASES["invalid"][3]],
    ids=lambda c: c["id"],
)
def test_invalid_clocks_keep_the_same_nonretryable_error_on_all_surfaces(
    case, rest, tmp_path, capsys
):
    spec = SPECS["meihua_analysis"]
    payload = parameters(case)
    response = rest.post(spec.rest_path, json=payload)
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    mcp = asyncio.run(native(spec, payload))
    assert response.status_code == 422 and code != 0 and mcp.is_error
    for out in [response.json(), cli, mcp.structured_content]:
        assert out["error_code"] == "validation_error" and out["retryable"] is False
