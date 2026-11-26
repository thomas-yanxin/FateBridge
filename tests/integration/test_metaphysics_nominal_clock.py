"""Eight fixed R33 controls with source-conditioned independent label targets.

Six services retain the actual BEFORE adjustment at its sole calculation
boundary and use the real seed/calendar/technique pipeline. Two library
controls supply the already-admitted original-C vectors at the native API
boundary. These regressions check label/UTC adapters, not live EOT accuracy,
internal backend identity, lunar dates, whole boards or predictive efficacy.
No expected value comes from AFTER output.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as runtime
from fatebridge.core.metaphysics import seed as seed_owner
from fatebridge.services import metaphysics as services
from fatebridge.utils.solar_time import calculate_equation_of_time_minutes

FIXTURE = (
    Path(__file__).parents[1]
    / "data/solar_clock_labels_v1/nominal-seed-boundaries-v1.json"
)


@pytest.fixture(scope="module")
def reference():
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "0f1efdc20517fb270bf7f81cc693d718c4af97c90fb141d595825beada339a27"
    )
    value = json.loads(raw)
    provenance = value["provenance"]
    assert provenance["source_target_sha256"] == (
        "916ad2c6a1da97654bafda66c3518d42cb17a7b97131d55e1e2f6a3bc36917a0"
    )
    assert provenance["AFTER_output_used"] is False
    assert provenance["fixed_denominators"] == {
        "original4": 4,
        "modern4": 4,
        "label6": 6,
        "library_EOT_only2": 2,
    }
    cases = {row["id"]: row for row in value["cases"]}
    assert len(cases) == len(value["cases"]) == 8
    for row in cases.values():
        qualification = row["source_qualification"]
        assert qualification["given_operator_admitted"] is True
        assert qualification["physical_accuracy_certified"] is False
        assert qualification["SDK_internal_backend_independently_certified"] is False
        if "original_C" in row:
            source = row["original_C"]
            assert source["time_equ_status"] == 0
            assert source["time_equ_message"] == ""
            assert source["days_finite"] is True
            assert source["paired_sun_returned_flags"] == 2050
            assert source["paired_sun_message"] == ""
            assert source["paired_call_is_internal_trace"] is False
        else:
            pass
    return cases


@pytest.mark.parametrize(
    "case_id",
    [
        "A1_qimen_lower_solar_label",
        "A2_qimen_upper_solar_label",
        "M1_qimen_previous_day",
        "M2_qimen_next_day",
        "M3_liureng_previous_day",
        "M4_jinkou_next_day",
    ],
)
def test_fixed_source_adjustments_keep_civil_instant_and_independent_label_facts(
    case_id: str, reference, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = reference[case_id]
    payload = case["payload"]
    expected = case["expected_solar_label"]
    cycle = case["expected_cycle"]
    adjustment_calls = []
    captured = []

    def given_adjustment(civil, timezone_name, longitude, *, strategy):
        # The fixed requests all explicitly use +00:00 and no DST. The
        # captured source operands remain conditional, not a new live oracle.
        assert civil.utcoffset() == timedelta(0)
        assert [
            civil.year,
            civil.month,
            civil.day,
            civil.hour,
            civil.minute,
            civil.second,
            civil.microsecond,
        ] == case["expected_utc_fields"]
        assert timezone_name == "+00:00" and strategy == "apparent"
        assert longitude == payload["analysis_longitude"]
        given = case["given_adjustment"]
        assert all(row["finite"] is True for row in given.values())
        assert all(row["value"].hex() == row["hex"] for row in given.values())
        adjustment_calls.append(civil)
        return {key: row["value"] for key, row in given.items()}

    actual_builder = services.build_analysis_seed

    def capture_seed(**kwargs):
        result = actual_builder(**kwargs)
        captured.append(result)
        return result

    monkeypatch.setattr(seed_owner, "calculate_solar_time_adjustment", given_adjustment)
    monkeypatch.setattr(services, "build_analysis_seed", capture_seed)
    # Calendar sources are real and retain their own acceptance boundaries.
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    result = getattr(services, case["service"])(**payload)

    assert "error" not in result, result
    assert len(captured) == len(adjustment_calls) == 1
    seed = captured[0]
    assert seed.input_datetime == adjustment_calls[0]
    assert seed.input_datetime.utcoffset() is not None
    assert seed.clock.ordinal == expected["ordinal"]
    assert seed.clock.microseconds_of_day == expected["day_time_us"]
    assert list(seed.clock.date_parts) == expected["parts"][:3]
    assert list(seed.clock.time_parts) == expected["parts"][3:]
    assert seed.solar_time_adjustment["physical_input_instant_shifted"] is False
    assert seed.solar_time_adjustment["equation_of_time_time_scale"] == "UTC_as_UT1"
    assert seed.solar_time_adjustment["subsecond_accuracy_certified"] is False
    assert result["four_pillars"]["day"] == {
        "stem": cycle["day_ganzhi"][0],
        "branch": cycle["day_ganzhi"][1],
    }
    assert result["four_pillars"]["hour"] == {
        "stem": cycle["hour_ganzhi"][0],
        "branch": cycle["hour_ganzhi"][1],
    }
    if case["service"] == "calculate_qimen_analysis":
        board = result["qimen"]
        assert board["day_ganzhi"] == cycle["day_ganzhi"]
        assert board["time_ganzhi"] == cycle["hour_ganzhi"]
        assert board["fu_tou"] == cycle["fu_tou"]
        assert board["yuan"] == cycle["yuan"]
        assert board["ju_decision"]["effective_date"] == cycle["effective_date_key"]
    else:
        pass


@pytest.mark.parametrize(
    "case_id", ["B1_eot_lower_utc_label", "B2_eot_upper_utc_label"]
)
def test_default_eot_adapter_reaches_given_original_C_vector_across_UTC_year_limits(
    case_id: str, reference, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = reference[case_id]
    source = case["original_C"]
    calls = []

    def given_source(operation, *args, **kwargs):
        assert not kwargs
        calls.append(operation)
        if operation == "julday":
            assert args[:3] == tuple(case["expected_utc_fields"][:3])
            assert args[3].hex() == source["hour_hex"]
            assert args[4] == 1  # Original source SE_GREG_CAL, not a new calendar.
            return float.fromhex(source["julday_hex"])
        else:
            pass
        assert operation == "time_equ"
        assert len(args) == 1 and args[0].hex() == source["julday_hex"]
        return float.fromhex(source["days_hex"])

    assert runtime.swe is not None  # Required SDK dependency; no skipped source gate.
    monkeypatch.setattr(runtime, "ephemeris_call", given_source)
    local = datetime(
        *case["local_fields"],
        tzinfo=timezone(timedelta(minutes=case["offset_minutes"])),
    )
    actual = calculate_equation_of_time_minutes(local)
    assert calls == ["julday", "time_equ"]
    assert actual.hex() == case["expected_eot_minutes_hex"]
    assert case["expected_solar_label"] is case["expected_cycle"] is None


@pytest.mark.parametrize(
    "anchor",
    ["0000-12-31T10:00:00+00:00", "+010000-01-01T11:00:00+00:00"],
)
def test_given_jiehou_context_accepts_auxiliary_UTC_labels(anchor: str) -> None:
    from fatebridge.core.heluo.heluo_jiehou import jiehou_evidence

    # Given R34 civil-offset labels and the already-selected winter term;
    # this does not calculate a Sun crossing or establish physical hou dates.
    result = jiehou_evidence(
        {
            "term": "冬至",
            "quarter": "坎",
            "anchor_utc": anchor,
            "precision": "birth_instant",
        }
    )
    assert result["anchor_utc"] == anchor
    assert result["upstream_term_label"] == "冬至"
    assert result["selected_hou"] is None
    assert result["historical_term_instants_established"] is False


@pytest.mark.parametrize(
    "change",
    [
        {"anchor_utc": "0000-12-31T10:00:00+08:00"},
        {"anchor_utc": "+010000-01-01T11:00:00-12:00"},
        {"anchor_utc": "0000-12-31T10:00:00"},
        {"quarter": "震"},
    ],
)
def test_auxiliary_jiehou_labels_keep_existing_context_rejections(change) -> None:
    from fatebridge.core.heluo.heluo_jiehou import jiehou_evidence
    from fatebridge.utils.errors import NumerologySourceError

    context = {
        "term": "冬至",
        "quarter": "坎",
        "anchor_utc": "0000-12-31T10:00:00+00:00",
        "precision": "birth_instant",
    }
    with pytest.raises(NumerologySourceError) as error:
        jiehou_evidence({**context, **change})
    assert error.value.reason == "runtime_heluo_jiehou_context_conflict"


def test_given_typed_jie_keeps_lower_civil_age_and_twelve_periods(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fractions import Fraction

    from fatebridge.core.almanac import SolarTerm
    from fatebridge.core.numerology.canping_timing import APPENDIX, luck_timeline
    from fatebridge.core.timing import DayunStartResolution, TimingAnalysis
    from fatebridge.utils.civil_time import ZonedCalendar

    # Targets were sealed before candidate outputs: R34 reference58adeab9…
    # Given label-only source fixture: localJan1 -> localJan5 is four civil
    # days. The nominal span is consistent with that supplied calendar label.
    birth = datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=14)))
    reference = ZonedCalendar.from_isoformat("0001-01-05T02:42:01.544629+14:00")
    term = SolarTerm(
        name="小寒", calendar=reference, resolution_provider="given_calendar"
    )
    resolution = DayunStartResolution(
        birth, term, True, "庚", Fraction(355_321_544_629, 86_400_000_000)
    )
    selections = []

    def given_resolution(actual_birth, gender, zone):
        assert actual_birth == birth and gender == "男" and zone == "+14:00"
        selections.append(actual_birth)
        return resolution

    monkeypatch.setattr(TimingAnalysis, "resolve_dayun_start", given_resolution)
    timeline = luck_timeline(birth, "男", ("戊", "子"), "+14:00", APPENDIX)
    assert selections == [birth]
    offset = timeline["calendar_offset"]
    assert (
        offset["civil_days_to_reference"],
        offset["whole_years"],
        offset["discarded_days"],
        offset["borrowed_days"],
    ) == (4, 1, 1, 0)
    assert timeline["start_details"]["reference_at"] == (
        "0001-01-05T02:42:01.544629+14:00"
    )
    assert timeline["start_at"] == "0002-01-01T00:00:00+14:00"
    assert len(timeline["periods"]) == 12
    assert [row["pillar"] for row in timeline["periods"]] == [
        "己丑",
        "庚寅",
        "辛卯",
        "壬辰",
        "癸巳",
        "甲午",
        "乙未",
        "丙申",
        "丁酉",
        "戊戌",
        "己亥",
        "庚子",
    ]
    assert [row["start_at"] for row in timeline["periods"]] == [
        "0002-01-01T00:00:00+14:00",
        "0012-01-01T00:00:00+14:00",
        "0022-01-01T00:00:00+14:00",
        "0032-01-01T00:00:00+14:00",
        "0042-01-01T00:00:00+14:00",
        "0052-01-01T00:00:00+14:00",
        "0062-01-01T00:00:00+14:00",
        "0072-01-01T00:00:00+14:00",
        "0082-01-01T00:00:00+14:00",
        "0092-01-01T00:00:00+14:00",
        "0102-01-01T00:00:00+14:00",
        "0112-01-01T00:00:00+14:00",
    ]
    assert [row["end_at"] for row in timeline["periods"][:-1]] == [
        row["start_at"] for row in timeline["periods"][1:]
    ]
    assert timeline["periods"][-1]["end_at"] == "0122-01-01T00:00:00+14:00"


@pytest.mark.parametrize(
    "year_offset,expected",
    [
        (0, "0002-05-14T12:03:05.355487+14:00"),
        (120, "0122-05-14T12:03:05.355487+14:00"),
    ],
)
def test_given_continuous_boundary_keeps_actual_UTC0_birth(
    year_offset: int, expected: str
) -> None:
    from fatebridge.core.timing import TimingAnalysis
    from fatebridge.utils.civil_time import utc_calendar

    # R35 given-source integer reference0d4de0cf…, sealed before candidate.
    # The exactquantizer/wall target is conditional on the original retained
    # Jie, not an independently observed ancientSolar or physicalUTC truth.
    birth = datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=14)))
    start_wall = datetime(2, 5, 14, 12, 3, 5, 355487)
    actual, fold_adjusted = TimingAnalysis._resolve_dayun_calendar_boundary(
        birth, start_wall, year_offset, "+14:00"
    )
    assert actual.isoformat() == expected
    assert actual.fold == 0 and fold_adjusted is False
    assert (
        utc_calendar(actual).julian_day_exact() > utc_calendar(birth).julian_day_exact()
    )
