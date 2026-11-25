import json
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from fatebridge.core.astro.angle_definitions import is_ascendant_resolved
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant
from fatebridge.core.predictive import western_timing as astrology_predictive
from fatebridge.core.predictive._common import build_predictive_birth_info
from fatebridge.core.predictive.decennials import (
    _DecennialInterval,
    build_decennials_payload,
)
from fatebridge.core.predictive.native_chart import NativePoint, NativeSubject
from fatebridge.services.western_timing import calculate_western_timing_analysis
from fatebridge.services.western_timing_tools import calculate_timing_tool
from fatebridge.utils.civil_time import utc_calendar
from fatebridge.utils.timezones import parse_timezone_name
from tests.fixtures.surface_payloads import J2000_UNRESOLVED_ASC_SITE, western_payload
from tests.support.ephemeris_context import empty_ephemeris_path

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
        ut1=UT1Instant.from_float(2451545.0),
        tt=TTInstant.from_float(2451545.0),
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
    else:
        pass
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
def test_decennial_exact_subdivision_matches_flint(case, calendar_scale) -> None:
    parent = _DecennialInterval(
        "reference",
        case["level"] - 1,
        case["parent_lord"],
        Fraction(*case["parent_start"]),
        Fraction(*case["parent_end"]),
    )
    birth = datetime(2000, 1, 1, tzinfo=timezone.utc)
    utc_birth = utc_calendar(birth)
    children = parent.children(case["order"])
    for index, child in enumerate(children):
        assert child.start_minutes == Fraction(*case["bounds"][index])
        assert child.end_minutes == Fraction(*case["bounds"][index + 1])
        output = child.payload(utc_birth, timezone.utc, utc_birth, calendar_scale)
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
def test_decennial_clock_and_current_path_match_temporal(case) -> None:
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
    else:
        pass


def test_decennials_target_in_utc_year_zero_preserves_the_preview() -> None:
    zone_name = "Asia/Tokyo"
    zone = parse_timezone_name(zone_name)
    birth = build_predictive_birth_info(
        birth_year=1900,
        birth_month=1,
        birth_day=1,
        birth_hour=9,
        birth_minute=18,
        birth_timezone=zone_name,
        birth_longitude=139.6917,
        birth_latitude=35.6895,
    )
    subject = _decennial_subject(
        {"day": True, "positions": [0, 30, 60, 90, 120, 150, 180]}
    )
    target = datetime(1, 1, 1, 9, 18, tzinfo=zone)
    result = build_decennials_payload(birth, subject, analysis_datetime=target)
    assert result == build_decennials_payload(
        birth, subject, analysis_datetime=target + timedelta(minutes=1)
    )
    assert len(result["timeline"]) == 7
    assert result["timeline"][0]["end"] == "1910-08-07T09:18:00+09:00"
    assert result["current_level_1"] is None
    assert result["current_level_2"] is None
    assert result["current_level_3"] is None


def test_decennials_utc_and_local_delivery_have_distinct_upper_bounds() -> None:
    zone_name = "Etc/GMT+5"
    zone = parse_timezone_name(zone_name)
    birth_inputs = {
        "birth_year": 1904,
        "birth_month": 11,
        "birth_hour": 20,
        "birth_timezone": zone_name,
        "birth_longitude": -75,
        "birth_latitude": 40,
    }
    birth = build_predictive_birth_info(birth_day=19, **birth_inputs)
    subject = _decennial_subject(
        {"day": True, "positions": [0, 30, 60, 90, 120, 150, 180]}
    )
    before = datetime(9999, 12, 31, 18, 59, tzinfo=zone)
    after = datetime(9999, 12, 31, 19, 0, tzinfo=zone)
    result = build_decennials_payload(birth, subject, analysis_datetime=after)
    assert result == build_decennials_payload(birth, subject, analysis_datetime=before)
    current = result["current_level_1"]
    assert current is not None
    assert current["key"] == "l1_763"
    assert current["end"] == "9999-12-31T20:00:00-05:00"

    next_day_birth = build_predictive_birth_info(birth_day=20, **birth_inputs)
    with pytest.raises(ValueError, match="Civil calendar label is outside"):
        build_decennials_payload(next_day_birth, subject, analysis_datetime=before)


def test_decennial_unverified_candidate_cannot_execute() -> None:
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


def test_western_return_and_direction_tools_generate_snapshots() -> None:
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


def test_solarreturn_skips_unrelated_predictive_modules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_primary_direction_and_time_lord_tools_support_selected_sections() -> None:
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


def test_decennials_payload_is_bounded_for_agent_consumption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The decennial tree is 4 levels deep (7^4 ≈ 2400 leaves). Serialising it
    whole produced a ~14 MB response that no agent context (or MCP/HTTP
    transport) can hold. The active drill-down is exposed via
    current_level_1/2/3, so the timeline only needs the decade overview and each
    current_level only its immediate children. Guard the bound with the
    Moshier source, whose natal motion diagnostics are larger."""
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    with empty_ephemeris_path():
        result = calculate_timing_tool("decennials", **western_payload())
    basis = result["natal_reference"]["calculation_basis"]
    assert basis["ephemeris_model"] == "moshier"
    assert basis["physical_ephemeris_source"]
    payload = result["decennials"]

    # Whole tool response must stay comfortably agent-readable.
    serialized = json.dumps(result, ensure_ascii=False, default=str)
    assert (
        len(serialized) < 200_000
    ), f"decennials response too large: {len(serialized)}"
    period_section = next(
        section
        for section in result["snapshot_export"]["sections"]
        if section["title"] == "基于X起运"
    )
    assert json.loads(period_section["content"].partition("\n")[2]) == payload

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


def test_is_ascendant_resolved_reads_all_chart_and_reference_shapes() -> None:
    assert is_ascendant_resolved(None) is True
    assert is_ascendant_resolved({"geometric_ascendant_resolved": True}) is True
    assert is_ascendant_resolved({"geometric_ascendant_resolved": False}) is False
    assert (
        is_ascendant_resolved({"status": "geographic_pole_meridian_convention"}) is True
    )
    assert (
        is_ascendant_resolved(
            {
                "calculation_basis": {
                    "angle_definition": {"geometric_ascendant_resolved": False}
                }
            }
        )
        is False
    )
    assert (
        is_ascendant_resolved(
            {
                "chart_profile": {
                    "angle_definition": {"geometric_ascendant_resolved": False}
                }
            }
        )
        is False
    )
    assert (
        is_ascendant_resolved({"angles": {"ascendant": {"longitude": None}}}) is False
    )


def test_singular_ascendant_blocks_profection_givenyear_and_zr_while_keeping_facts() -> (
    None
):
    singular_inputs = dict(
        name="奇点样本",
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="UTC",
        **J2000_UNRESOLVED_ASC_SITE,
        house_system="W",
        analysis_year=2026,
        analysis_month=5,
        analysis_day=20,
    )

    prof_res = calculate_timing_tool("profection", **singular_inputs)
    prof = prof_res["profection"]
    assert (
        prof_res["natal_reference"]["calculation_basis"]["angle_definition"][
            "geometric_ascendant_resolved"
        ]
        is False
    )
    assert prof["status"] == "underdetermined_ascendant"
    assert prof["ascendant_resolved"] is False
    assert prof["age_years"] == 26
    assert prof["year_start"] == "2026-01-01T12:00:00+00:00"
    assert prof["year_end"] == "2027-01-01T12:00:00+00:00"
    assert prof["activated_house"] == 3
    assert prof["monthly_house"] == 7
    for key in (
        "activated_sign",
        "activated_sign_label",
        "lord",
        "lord_label",
        "monthly_sign",
        "monthly_sign_label",
    ):
        assert prof[key] is None
    assert "None" not in prof_res["summary"]

    gy_res = calculate_timing_tool("givenyear", **singular_inputs)
    gy = gy_res["givenyear"]
    assert gy["status"] == "underdetermined_ascendant"
    assert gy["natal_ascendant_resolved"] is False
    assert gy["ascendant_resolved"] is True
    assert gy["annual_profection"]["activated_house"] == 3
    assert gy["annual_profection"]["activated_sign"] is None
    assert len(gy["monthly_profections"]) == 12
    assert all(
        m["sign"] is None
        and m["sign_label"] is None
        and m["lord"] is None
        and m["lord_label"] is None
        and m["status"] == "underdetermined_ascendant"
        and m["start"]
        and m["end"]
        for m in gy["monthly_profections"]
    )
    assert [m["house"] for m in gy["monthly_profections"] if m["active"]] == [7]
    assert gy["sun"]["sign"] and gy["moon"]["sign"] and gy["medium_coeli"]["sign"]
    assert all(
        hit["source"] != "Ascendant" and hit["target"] != "Ascendant"
        for hit in gy["hits"]
    )
    assert "None" not in gy_res["summary"]

    gy_both_res = calculate_timing_tool(
        "givenyear",
        **{
            **singular_inputs,
            "analysis_year": 2000,
            "analysis_month": 1,
            "analysis_day": 1,
            "analysis_hour": 12,
            "analysis_minute": 0,
        },
    )
    gy_both = gy_both_res["givenyear"]
    assert gy_both["ascendant_resolved"] is False
    assert gy_both["ascendant"]["longitude"] is None
    assert gy_both["ascendant"]["status"] == "underdetermined_ascendant"
    assert gy_both["sun"]["house"] is None

    zr_res = calculate_timing_tool("zr", **singular_inputs)
    zr = zr_res["zr"]
    assert zr["status"] == "underdetermined_ascendant"
    assert zr["ascendant_resolved"] is False
    assert zr["calculation_basis"]["angular_reference_sign"] is None
    for track_key in ("spirit", "fortune"):
        track = zr[track_key]
        assert track["status"] == "underdetermined_ascendant"
        assert track["lot"]["sign"] is None
        assert track["lot"]["longitude"] is None
        assert track["release_start_sign"] is None
        assert track["current_level_1"] is None
        assert track["level_1_timeline"] == []
        assert track["peak_signs"] == []
    for lot_key in ("lot_of_fortune", "lot_of_spirit"):
        lot = zr_res["natal_reference"]["lots"][lot_key]
        assert lot["status"] == "underdetermined_ascendant"
        assert lot["sign"] is None
        assert lot["longitude"] is None
    assert zr_res["natal_reference"]["sun"]["sign"]
    assert zr_res["natal_reference"]["sect"]["key"] in {"day", "night"}

    combined = calculate_western_timing_analysis(**singular_inputs)
    assert "error" not in combined
    assert (
        combined["time_lords"]["annual_profection"]["status"]
        == "underdetermined_ascendant"
    )
    assert (
        combined["time_lords"]["zodiacal_releasing"]["status"]
        == "underdetermined_ascendant"
    )
    assert "None" not in combined["summary"]
