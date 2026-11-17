import json
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from fatebridge.core.predictive import western_timing as astrology_predictive
from fatebridge.core.predictive._common import build_predictive_birth_info
from fatebridge.core.predictive.decennials import (
    _DecennialInterval,
    build_decennials_payload,
)
from fatebridge.core.predictive.native_chart import NativePoint, NativeSubject
from fatebridge.services.western_timing_tools import calculate_timing_tool
from tests.fixtures.surface_payloads import western_payload

DECENNIAL_REFERENCE = json.loads(
    (Path(__file__).parents[1] / "fixtures/decennials-reference.json").read_text()
)


def _decennial_subject(profile) -> NativeSubject:
    names = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]
    return NativeSubject(
        name="explicit-synthetic-decennial-operand",
        lng=0,
        lat=40,
        tz_str="UTC",
        iso_formatted_utc_datetime=None,
        iso_formatted_local_datetime=None,
        julian_day=2451545.0,
        julian_day_tt=2451545.0,
        houses_system_identifier="P",
        zodiac_type="Tropic",
        sidereal_mode=None,
        is_diurnal=profile["day"],
        calculation_basis={},
        points={
            name.lower(): NativePoint(
                name=name,
                abs_pos=position,
                position=position % 30,
                sign="Ari",
                sign_num=int(position // 30),
                house="First_House",
            )
            for name, position in zip(names, profile["positions"])
        },
    )


def _assert_decennial_reference(actual, expected):
    if expected is None:
        assert actual is None
        return
    assert actual is not None
    for key, value in expected.items():
        if key in {"start", "end"}:
            moment = datetime.fromisoformat(actual[key])
            assert moment.astimezone(timezone.utc) == datetime.fromisoformat(
                value["UTC"]
            )
            assert (
                moment.replace(tzinfo=None).isoformat(timespec="microseconds")
                == value["local_plain"]
            )
            assert moment.utcoffset().total_seconds() == value["offset_seconds"]
        elif key == "sublevel":
            assert len(actual[key]) == len(value)
            for child, reference in zip(actual[key], value):
                _assert_decennial_reference(child, reference)
        else:
            assert actual[key] == value


@pytest.mark.parametrize(
    "case", DECENNIAL_REFERENCE["coefficients"], ids=lambda c: c["id"]
)
@pytest.mark.parametrize("calendar_scale", [Fraction(1), Fraction(487, 480)])
def test_decennial_exact_subdivision_matches_flint(case, calendar_scale):
    parent = _DecennialInterval(
        "reference",
        case["level"] - 1,
        case["parent_lord"],
        Fraction(*case["parent_start"]),
        Fraction(*case["parent_end"]),
    )
    birth = datetime(2000, 1, 1, tzinfo=timezone.utc)
    children = parent.children(case["order"])
    for index, child in enumerate(children):
        assert child.start_minutes == Fraction(*case["bounds"][index])
        assert child.end_minutes == Fraction(*case["bounds"][index + 1])
        output = child.payload(birth, timezone.utc, birth, calendar_scale)
        expected_offsets = case[
            "UTC_microseconds" if calendar_scale == 1 else "UTC_microseconds_365_25"
        ]
        for key, offset in (("start", index), ("end", index + 1)):
            assert datetime.fromisoformat(output[key]) == birth + timedelta(
                microseconds=expected_offsets[offset]
            )
    assert children[-1].end_minutes == parent.end_minutes


@pytest.mark.parametrize(
    "case",
    DECENNIAL_REFERENCE["clocks"] + DECENNIAL_REFERENCE["boundaries"],
    ids=lambda c: c["id"],
)
def test_decennial_clock_and_current_path_match_temporal(case):
    local = datetime.fromisoformat(case["local"])
    birth = build_predictive_birth_info(
        birth_year=local.year,
        birth_month=local.month,
        birth_day=local.day,
        birth_hour=local.hour,
        birth_minute=local.minute,
        birth_timezone=case["zone"],
        birth_longitude=0,
        birth_latitude=40,
    )
    subject = _decennial_subject(case["profile"])
    target = datetime.fromisoformat(case["analysis_UTC"])
    output = build_decennials_payload(birth, subject, analysis_datetime=target)
    assert output == build_decennials_payload(
        birth,
        subject,
        analysis_datetime=target.astimezone(ZoneInfo("America/New_York")),
    )
    assert output["base_order"] == case["base_order"]
    assert output["calculation_options"]["time_basis"] == "UTC_nominal_elapsed_days"
    for key in ("current_level_1", "current_level_2", "current_level_3"):
        _assert_decennial_reference(output[key], case[key])
    if "timeline" in case:
        for actual, expected in zip(output["timeline"], case["timeline"]):
            _assert_decennial_reference(actual, expected)


def test_decennial_unverified_candidate_cannot_execute():
    birth = build_predictive_birth_info(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=40,
    )
    subject = _decennial_subject(
        {"day": True, "positions": [0, 30, 60, 90, 120, 150, 180]}
    )
    with pytest.raises(ValueError, match="Unverified decennial day method"):
        build_decennials_payload(
            birth,
            subject,
            analysis_datetime=birth.require_utc_datetime,
            day_method="hephaistio",
        )


def test_western_return_and_direction_tools_generate_snapshots():
    solarreturn_result = calculate_timing_tool(
        "solarreturn",
        **western_payload(),
        selected_sections=["起盘信息", "星盘信息"],
    )
    lunarreturn_result = calculate_timing_tool("lunarreturn", **western_payload())
    transit_result = calculate_timing_tool(
        "transit",
        **western_payload(),
        selected_sections=["起盘信息", "相位"],
    )
    solararc_result = calculate_timing_tool("solararc", **western_payload())
    givenyear_result = calculate_timing_tool("givenyear", **western_payload())
    profection_result = calculate_timing_tool("profection", **western_payload())

    assert solarreturn_result["analysis_type"] == "西占太阳返照"
    assert solarreturn_result["solarreturn"]["return_datetime"].startswith(
        "2025-05-17T01:47:"
    )
    assert solarreturn_result["snapshot_export"]["technique"]["key"] == "solarreturn"
    assert solarreturn_result["snapshot_export"]["selected_sections"] == [
        "起盘信息",
        "星盘信息",
    ]
    assert "[起盘信息]" in solarreturn_result["snapshot_export"]["export_text"]
    assert "[星盘信息]" in solarreturn_result["snapshot_export"]["export_text"]
    assert "[相位]" not in solarreturn_result["snapshot_export"]["export_text"]

    assert lunarreturn_result["analysis_type"] == "西占月亮返照"
    assert lunarreturn_result["lunarreturn"]["return_datetime"].startswith(
        "2025-05-20T01:30:"
    )
    assert lunarreturn_result["snapshot_export"]["technique"]["key"] == "lunarreturn"

    assert transit_result["analysis_type"] == "西占行运盘"
    assert transit_result["transit"]["analysis_datetime"].startswith(
        "2025-05-20T15:30:00+08:00"
    )
    assert transit_result["transit"]["location"]["timezone"] == "Asia/Shanghai"
    assert (
        transit_result["transit"]["transit_reference"]["uranus"]["point_label"]
        == "天王星"
    )
    assert transit_result["snapshot_export"]["technique"]["key"] == "transit"
    assert transit_result["snapshot_export"]["selected_sections"] == [
        "起盘信息",
        "相位",
    ]
    assert "[起盘信息]" in transit_result["snapshot_export"]["export_text"]
    assert "[相位]" in transit_result["snapshot_export"]["export_text"]
    assert "[星盘信息]" not in transit_result["snapshot_export"]["export_text"]

    assert solararc_result["analysis_type"] == "西占太阳弧"
    assert solararc_result["solararc"]["arc_degrees"] == pytest.approx(
        33.5458, abs=0.01
    )
    assert solararc_result["snapshot_export"]["technique"]["key"] == "solararc"

    assert givenyear_result["analysis_type"] == "西占指定年盘"
    assert givenyear_result["givenyear"]["ascendant"]["sign"] == "Libra"
    assert len(givenyear_result["givenyear"]["monthly_profections"]) == 12
    assert givenyear_result["snapshot_export"]["technique"]["key"] == "givenyear"

    assert profection_result["analysis_type"] == "西占年小限"
    assert profection_result["profection"]["activated_house"] == 12
    assert profection_result["profection"]["activated_sign"] == "Virgo"
    assert profection_result["snapshot_export"]["technique"]["key"] == "profection"


def test_solarreturn_skips_unrelated_predictive_modules(monkeypatch):
    def _unexpected_transit(*args, **kwargs):
        raise AssertionError("build_transit_payload should not run for solarreturn")

    def _unexpected_primary_directions(*args, **kwargs):
        raise AssertionError(
            "build_primary_directions_payload should not run for solarreturn"
        )

    monkeypatch.setattr(
        astrology_predictive,
        "build_transit_payload",
        _unexpected_transit,
    )
    monkeypatch.setattr(
        astrology_predictive,
        "build_primary_directions_payload",
        _unexpected_primary_directions,
    )

    result = calculate_timing_tool("solarreturn", **western_payload())

    assert "error" not in result
    assert result["analysis_type"] == "西占太阳返照"
    assert result["solarreturn"]["return_datetime"].startswith("2025-05-17T01:47:")


def test_primary_direction_and_time_lord_tools_support_selected_sections():
    pd_result = calculate_timing_tool(
        "pd",
        **western_payload(),
        selected_sections=["出生时间", "主/界限法设置", "主/界限法表格"],
    )
    pdchart_result = calculate_timing_tool("pdchart", **western_payload())
    zr_result = calculate_timing_tool(
        "zr",
        **western_payload(),
        selected_sections=["起盘信息", "基于X点推运"],
    )
    firdaria_result = calculate_timing_tool("firdaria", **western_payload())
    decennials_result = calculate_timing_tool("decennials", **western_payload())

    assert pd_result["analysis_type"] == "西占主限"
    assert pd_result["pd"]["method"] == "astroapp_alchabitius"
    assert pd_result["pd"]["time_key"] == "Naibod"
    assert pd_result["snapshot_export"]["technique"]["key"] == "primarydirect"
    assert pd_result["snapshot_export"]["selected_sections"] == [
        "出生时间",
        "主/界限法设置",
        "主/界限法表格",
    ]
    assert "[出生时间]" in pd_result["snapshot_export"]["export_text"]
    assert "[主/界限法设置]" in pd_result["snapshot_export"]["export_text"]
    assert "[主/界限法表格]" in pd_result["snapshot_export"]["export_text"]
    assert "[星盘信息]" not in pd_result["snapshot_export"]["export_text"]

    assert pdchart_result["analysis_type"] == "西占主限法盘"
    assert pdchart_result["pdchart"]["show_pd_bounds"] is True
    assert pdchart_result["snapshot_export"]["technique"]["key"] == "primarydirchart"

    assert zr_result["analysis_type"] == "西占黄道释放"
    assert zr_result["zr"]["spirit"]["current_level_1"]["sign"] == "Aquarius"
    assert zr_result["snapshot_export"]["technique"]["key"] == "zodialrelease"
    assert zr_result["snapshot_export"]["selected_sections"] == [
        "起盘信息",
        "基于X点推运",
    ]
    assert "[星盘信息]" not in zr_result["snapshot_export"]["export_text"]

    assert firdaria_result["analysis_type"] == "西占法达星限"
    assert firdaria_result["firdaria"]["current_major"]["planet"] == "Moon"
    assert firdaria_result["snapshot_export"]["technique"]["key"] == "firdaria"

    assert decennials_result["analysis_type"] == "西占十年星限"
    assert decennials_result["decennials"]["current_level_1"]["planet"] == "Moon"
    assert decennials_result["snapshot_export"]["technique"]["key"] == "decennials"


def test_decennials_payload_is_bounded_for_agent_consumption():
    """The decennial tree is 4 levels deep (7^4 ≈ 2400 leaves). Serialising it
    whole produced a ~14 MB response that no agent context (or MCP/HTTP
    transport) can hold. The active drill-down is exposed via
    current_level_1/2/3, so the timeline only needs the decade overview and each
    current_level only its immediate children. Guard the bound."""
    import json

    result = calculate_timing_tool("decennials", **western_payload())
    payload = result["decennials"]

    # Whole tool response must stay comfortably agent-readable.
    serialized = json.dumps(result, ensure_ascii=False, default=str)
    assert (
        len(serialized) < 200_000
    ), f"decennials response too large: {len(serialized)}"

    # Timeline is a decade overview: 7 level-1 nodes, no deep subtree.
    timeline = payload["timeline"]
    assert len(timeline) == 7
    for node in timeline:
        assert node["level"] == 1
        assert node.get("sublevel", []) == []

    # The active path is preserved: each current_level carries its immediate
    # children only (one level deep), not the full tree.
    cl1 = payload["current_level_1"]
    cl2 = payload["current_level_2"]
    cl3 = payload["current_level_3"]
    assert cl1 and cl1["level"] == 1
    assert cl2 and cl2["level"] == 2
    assert cl3 and cl3["level"] == 3
    # Immediate children present, but no grandchildren (bounded depth).
    for cur, child_level in ((cl1, 2), (cl2, 3), (cl3, 4)):
        children = cur.get("sublevel", [])
        assert children, "active level should expose its immediate children"
        for child in children:
            assert child["level"] == child_level
            assert child.get("sublevel", []) == []
