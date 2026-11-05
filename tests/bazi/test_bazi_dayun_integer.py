"""Integer displays use raw intervals; real calendar selection stays unchanged."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import pytest

import fatebridge.core.timing as timing
from fatebridge.application.execution import execute_tool
from fatebridge.core.almanac import get_solar_terms_for_year
from fatebridge.core.execution_context import ExecutionOptions
from tests.support.transports import SPECS, business, call_cli, native
from tests.support.transports import rest as _rest_fixture


def exact_age_ceiling(birth, boundary):
    delta = abs(boundary.astimezone(timezone.utc) - birth.astimezone(timezone.utc))
    micros = (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
    divisor = 3 * 86400 * 1_000_000
    return max(1, (micros + divisor - 1) // divisor)


rest = _rest_fixture
ROOT = Path(__file__).resolve().parents[2]
AS_OF = "2038-10-23T04:00:00Z"
TOOLS = (
    "analyze_destiny",
    "bazi_birth",
    *(
        "bazi_" + t
        for t in (
            "career",
            "wealth",
            "health",
            "children",
            "education",
            "personality",
            "relatives",
            "marriage",
            "romance",
        )
    ),
    "timing_analysis",
    "dayun_analysis",
    "liunian_analysis",
    "liuyue_analysis",
    "liuri_analysis",
    "liushi_analysis",
    "jieqi_timeline_analysis",
)


@lru_cache(maxsize=1)
def baseline():
    return {
        "rows": json.loads(
            (ROOT / "tests/data/bazi/dayun-integer-inputs.json").read_bytes()
        )
    }


def base(tool, zone="Asia/Shanghai", solar=False):
    return next(
        r
        for r in baseline()["rows"]
        if r["tool"] == tool and r["zone"] == zone and r["solar"] == solar
    )


@pytest.mark.parametrize("integer", range(1, 11))
@pytest.mark.parametrize("micros", [-1, 0, 1])
@pytest.mark.parametrize("forward", [False, True])
def test_integer_ceiling_at_each_unrounded_boundary(
    integer, micros, forward, monkeypatch
):
    # Controlled boundary oracle; not a new astronomical or historical source.
    term = next(
        t for t in get_solar_terms_for_year(2026, "Asia/Shanghai") if t.name == "立夏"
    )
    delta = timedelta(days=3 * integer, microseconds=micros)
    birth = term.moment.astimezone(timezone.utc) + (-delta if forward else delta)
    monkeypatch.setattr(timing, "get_bazi_year", lambda *args: 2026)
    monkeypatch.setattr(
        timing, "get_bazi_month_boundaries", lambda *args: (term, term, "巳", 3)
    )
    result = timing.TimingAnalysis.calculate_dayun_start_details(
        birth, "男" if forward else "女", "Asia/Shanghai"
    )
    expected = max(1, integer + (micros > 0))
    assert result["start_age_rounded"] == expected
    assert result["start_age_rounded"] == exact_age_ceiling(birth, term.moment)


def test_actual_public_minute_counterexample_and_display_collision():
    row = base("dayun_analysis")
    args = row["arguments"]
    birth = datetime(
        *(args["birth_" + key] for key in ("year", "month", "day", "hour", "minute"))
    )
    info = timing.TimingAnalysis.calculate_dayun_start_details(
        birth, args["gender"], row["zone"]
    )
    assert info["start_age_precise"] == 3.0
    assert 3 < info["start_age_unrounded"] < 3.005
    assert info["start_age_rounded"] == 4


def test_minimum_one_is_only_display_and_does_not_delay_an_exact_zero_start():
    term = next(
        t for t in get_solar_terms_for_year(2026, "Asia/Shanghai") if t.name == "立夏"
    )
    details = timing.TimingAnalysis.calculate_dayun_start_details(
        term.moment, "女", "Asia/Shanghai"
    )
    assert details["start_age_unrounded"] == 0
    assert details["start_age_rounded"] == 1
    from fatebridge.core.calendar import BaZiCalendar

    month = BaZiCalendar.get_four_pillars(term.moment, "Asia/Shanghai")["month"]
    value = timing.TimingAnalysis.calculate_dayun_timeline(
        term.moment, "女", month, "Asia/Shanghai"
    )
    assert datetime.fromisoformat(value["start_at"]).astimezone(
        timezone.utc
    ) == term.moment.astimezone(timezone.utc)


@pytest.mark.parametrize("tool", TOOLS)
def test_current_actual_surfaces_keep_complete_business_and_legal_projection(
    tool, rest, tmp_path, capsys
):
    spec = SPECS[tool]
    payload = base(tool)["arguments"]
    protocol = asyncio.run(
        native(
            spec,
            payload,
            as_of=AS_OF,
            include_snapshot_text=False,
            response_char_limit=0,
        )
    )
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--as-of",
            AS_OF,
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    assert not protocol.is_error and code == 0
    assert business(protocol.structured_content) == business(cli)
    if spec.rest_path is not None:
        http = rest.post(
            spec.rest_path,
            json=payload,
            params={
                "as_of": AS_OF,
                "include_snapshot_text": False,
                "response_char_limit": 0,
            },
        )
        assert http.status_code == 200 and business(http.json()) == business(cli)
    else:
        assert tool == "analyze_destiny"
    spec.output_model.model_validate(cli)


@pytest.mark.parametrize(
    "tool,root",
    [
        ("dayun_analysis", "dayun_info"),
        ("timing_analysis", "dayun_analysis"),
        ("bazi_birth", "bazi_birth.timing_overview.dayun"),
    ],
)
@pytest.mark.parametrize("zone", ["Asia/Shanghai", "America/New_York"])
def test_raw_age_and_integer_label_explain_the_same_calculation_and_snapshot(
    tool, root, zone
):
    spec = SPECS[tool]
    args = base(tool, zone)["arguments"]
    value = execute_tool(
        spec,
        spec.request_model.model_validate(args),
        options=ExecutionOptions(as_of=AS_OF),
        include_metadata=False,
    )
    assert "error" not in value
    info = value
    for part in root.split("."):
        info = info[part]
    assert info["start_age"] == 4 and info["start_age_precise"] == 3.0
    assert 3 < info["start_age_unrounded"] < 3.005
    if tool != "bazi_birth":
        assert "向上取整" in value["snapshot_text"]
        assert str(info["start_age_unrounded"]) in value["snapshot_text"]
