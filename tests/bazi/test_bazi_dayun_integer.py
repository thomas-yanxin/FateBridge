"""Integer displays use raw intervals; real calendar selection stays unchanged."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

import pytest

import fatebridge.core.timing as timing
from fatebridge.analysis.timing_effects import TimingEffectsAnalysis
from fatebridge.application.execution import execute_tool
from fatebridge.core.almanac import SolarTerm, get_solar_terms_for_year
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.utils.civil_time import CivilPoint, ZonedCalendar, utc_calendar
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
    integer, micros, forward: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Controlled boundary oracle; not a new astronomical or historical source.
    # Given calendar-grid source -> None: an actual solar root need not equal moment.
    term = SolarTerm(
        "立夏",
        ZonedCalendar.from_datetime(datetime(2026, 5, 5, 12, tzinfo=timezone.utc)),
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


@pytest.mark.parametrize("integer", range(1, 11))
@pytest.mark.parametrize("ticks", [-2, -1, 0, 1, 2])
def test_integer_ceiling_keeps_submicrosecond_source_remainders(integer, ticks) -> None:
    # Independent integer-neighbor classification, not a solar-accuracy claim.
    span = 3 * integer + Fraction(ticks, 16384 * 86400 * 1_000_000)
    birth = datetime(2000, 1, 1, tzinfo=timezone.utc)
    point = CivilPoint(utc_calendar(birth).julian_day_exact() + span)
    calendar = point.as_calendar().as_datetime()
    assert calendar is not None
    term = SolarTerm("小寒", ZonedCalendar.from_datetime(calendar), civil_point=point)
    details = timing.DayunStartResolution(birth, term, True, "庚", span).to_details()
    assert details["start_age_rounded"] == integer + (ticks > 0)


def test_explicit_age_uses_retained_span_at_all_three_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Fixed R28 N03_K+1 source point. It is just after three nominal years.
    # Integer ages 3, 13 and 123 fall before start, in period 1 and in period 12.
    birth = datetime(2000, 1, 1, tzinfo=timezone.utc)
    span = 9 + Fraction(1, 16384 * 86400 * 1_000_000)
    point = CivilPoint(utc_calendar(birth).julian_day_exact() + span)
    calendar = point.as_calendar().as_datetime()
    assert calendar is not None
    term = SolarTerm("小寒", ZonedCalendar.from_datetime(calendar), civil_point=point)
    resolution = timing.DayunStartResolution(birth, term, True, "庚", span)
    monkeypatch.setattr(
        timing.TimingAnalysis, "resolve_dayun_start", lambda *args: resolution
    )
    pillars = {
        "year": ("庚", "辰"),
        "month": ("戊", "寅"),
        "day": ("甲", "子"),
        "hour": ("甲", "子"),
    }
    for age, expected in ((3, "before_dayun"), (13, 1), (123, 12)):
        value = TimingEffectsAnalysis.analyze_dayun_effects(
            pillars, birth, "男", age, timezone_name="UTC"
        )
        actual = (
            value["dayun_info"]["period"] if "dayun_info" in value else value["status"]
        )
        assert actual == expected


def test_actual_public_minute_counterexample_and_display_collision() -> None:
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


def test_minimum_one_is_only_display_and_does_not_delay_an_exact_zero_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Exact given source point; a real solar root's datetime is only a display.
    term = SolarTerm(
        "立夏",
        ZonedCalendar.from_datetime(datetime(2026, 5, 5, 12, tzinfo=timezone.utc)),
    )
    monkeypatch.setattr(timing, "get_bazi_year", lambda *args: 2026)
    monkeypatch.setattr(
        timing, "get_bazi_month_boundaries", lambda *args: (term, term, "巳", 3)
    )
    details = timing.TimingAnalysis.calculate_dayun_start_details(
        term.moment, "女", "Asia/Shanghai"
    )
    assert details["start_age_unrounded"] == 0
    assert details["start_age_rounded"] == 1
    value = timing.TimingAnalysis.calculate_dayun_timeline(
        term.moment, "女", ("癸", "巳"), "Asia/Shanghai"
    )
    assert datetime.fromisoformat(value["start_at"]).astimezone(
        timezone.utc
    ) == term.moment.astimezone(timezone.utc)


@pytest.mark.parametrize("tool", TOOLS)
def test_current_actual_surfaces_keep_complete_business_and_legal_projection(
    tool, rest, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
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
    tool: str, root: str, zone: str
) -> None:
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
    else:
        pass


def test_dayun_resolution_retains_source_point_without_a_json_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    term = next(t for t in get_solar_terms_for_year(2024, "UTC") if t.name == "立秋")
    row = next(
        r
        for r in json.loads(
            (ROOT / "tests/data/retained_civil_points_v1.json").read_bytes()
        )["rows"]
        if r["name"] == "立秋"
    )
    expected = Fraction(int(row["civil_numerator"]), int(row["civil_denominator"]))
    birth = datetime(2024, 8, 6, 18, 9, 16, 454006, tzinfo=timezone.utc)
    monkeypatch.setattr(timing, "get_bazi_year", lambda *args: 2024)
    monkeypatch.setattr(
        timing, "get_bazi_month_boundaries", lambda *args: (term, term, "申", 6)
    )

    def no_serialization(self):
        raise AssertionError("resolution must retain the actual SolarTerm")

    monkeypatch.setattr(type(term), "as_dict", no_serialization)
    resolved = timing.TimingAnalysis.resolve_dayun_start(birth, "男", "UTC")
    assert resolved.target_term is term
    assert resolved.target_term.point.day == expected
    assert resolved.nominal_days == expected - utc_calendar(birth).julian_day_exact()
    assert resolved.birth == birth
    assert resolved.forward_direction is True and resolved.year_stem == "甲"


@pytest.mark.parametrize(
    "micros,age_hex,elapsed_hex,wall,offset",
    [
        (
            454005,
            "0x1.55555555b41edp-4",
            "0x1.518000005db90p+14",
            "2024-09-06T18:09:16.454173",
            {"years": 0, "months": 1, "days": 0, "microseconds": 168},
        ),
        (
            454006,
            "0x1.55555555703fdp-4",
            "0x1.518000001a9d2p+14",
            "2024-09-06T18:09:16.454054",
            {"years": 0, "months": 1, "days": 0, "microseconds": 48},
        ),
        (
            454007,
            "0x1.555555552c60dp-4",
            "0x1.517fffffd7814p+14",
            "2024-09-05T18:09:16.453935",
            {"years": 0, "months": 0, "days": 29, "microseconds": 86399999928},
        ),
    ],
)
def test_retained_resolution_keeps_original_float_and_wall_guard_values(
    micros: int,
    age_hex: str,
    elapsed_hex: str,
    wall: str,
    offset,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Frozen before extraction from the original three LiQiu carry guards;
    # compatibility values, not an independent actual-wall threshold oracle.
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    birth = datetime(2024, 8, 6, 18, 9, 16, micros, tzinfo=timezone.utc)
    _, details, actual_wall, actual_offset = (
        timing.TimingAnalysis._dayun_calendar_wall_context(birth, "男", "UTC")
    )
    assert details["start_age_unrounded"].hex() == age_hex
    assert details["elapsed_seconds"].hex() == elapsed_hex
    assert actual_wall.isoformat() == wall
    assert actual_offset == offset


@pytest.mark.parametrize(
    "birth_label,gender,age_hex,elapsed_hex,wall,offset",
    [
        (
            "2024-06-06T14:20:03.398557+00:00",
            "男",
            "0x1.400000000068bp+3",
            "0x1.3c68000000678p+21",
            "2034-06-06T14:20:03.398650",
            {"years": 10, "months": 0, "days": 0, "microseconds": 93},
        ),
        (
            "2024-06-06T14:20:03.398558+00:00",
            "男",
            "0x1.3fffffffffe0fp+3",
            "0x1.3c67ffffffe14p+21",
            "2034-06-05T14:20:03.398531",
            {"years": 9, "months": 11, "days": 29, "microseconds": 86399999973},
        ),
        (
            "2024-08-05T14:20:03.398557+00:00",
            "女",
            "0x1.3fffffffff975p+3",
            "0x1.3c67ffffff988p+21",
            "2034-08-04T14:20:03.398464",
            {"years": 9, "months": 11, "days": 29, "microseconds": 86399999907},
        ),
        (
            "2024-08-05T14:20:03.398558+00:00",
            "女",
            "0x1.40000000001f1p+3",
            "0x1.3c680000001ecp+21",
            "2034-08-05T14:20:03.398585",
            {"years": 10, "months": 0, "days": 0, "microseconds": 27},
        ),
    ],
)
def test_actual_wall_quantizes_the_original_span_without_float_ties(
    birth_label: str,
    gender: str,
    age_hex: str,
    elapsed_hex: str,
    wall: str,
    offset,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Frozen original small-summer DE440 source. Expected offsets use an
    # independent integer divmod/nearest-even oracle; expected Gregorian walls
    # use stdlib monthrange/clamp plus integer timedelta, not relativedelta.
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    birth = datetime.fromisoformat(birth_label)
    resolution = timing.TimingAnalysis.resolve_dayun_start(birth, gender, "UTC")
    assert resolution.target_term.name == "小暑"
    assert resolution.target_term.point.day == Fraction(
        116870958780183607306200733, 47498902319923200000
    )
    _, details, actual_wall, actual_offset = (
        timing.TimingAnalysis._dayun_calendar_wall_context(birth, gender, "UTC")
    )
    assert details["start_age_unrounded"].hex() == age_hex
    assert details["elapsed_seconds"].hex() == elapsed_hex
    assert actual_wall.isoformat() == wall
    assert actual_offset == offset


@pytest.mark.parametrize("forward", [False, True])
@pytest.mark.parametrize("parity", [0, 1])
def test_actual_wall_half_even_offset_preserves_integer_grid_translation(
    forward: bool, parity: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Pure quantizer controls, with no astronomical precision claim. The same
    # source is retained at each adjacent birth label, including exact ties.
    day_us = 86400 * 1_000_000
    birth = datetime(2024, 6, 6, 12, tzinfo=timezone.utc)
    lower_integer = 120 * day_us + parity
    span = Fraction(2 * lower_integer + 1, 2 * day_us * 120)
    point = CivilPoint(
        utc_calendar(birth).julian_day_exact() + (span if forward else -span)
    )
    term = SolarTerm(
        "synthetic_quantizer_control",
        ZonedCalendar(point.as_calendar(), timezone.utc),
        civil_point=point,
    )
    for delta in (-1, 0, 1):
        sample = birth + timedelta(microseconds=delta)
        resolution = timing.DayunStartResolution(
            sample,
            term,
            forward,
            "甲",
            abs(point.day - utc_calendar(sample).julian_day_exact()),
        )
        monkeypatch.setattr(
            timing.TimingAnalysis,
            "resolve_dayun_start",
            staticmethod(lambda *args, resolved=resolution: resolved),
        )
        _, _, _, offset = timing.TimingAnalysis._dayun_calendar_wall_context(
            sample, "男" if forward else "女", "UTC"
        )
        actual = (
            offset["years"] * 360 + offset["months"] * 30 + offset["days"]
        ) * day_us + offset["microseconds"]
        expected = lower_integer + parity + (-120 if forward else 120) * delta
        assert actual == expected
