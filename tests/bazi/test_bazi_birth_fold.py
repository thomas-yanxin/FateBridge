"""Fictional known-offset records retain physical time and the civil zone."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.requests.bazi import BaziBirthRequest
from fatebridge.core.timing import TimingAnalysis
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.birth_clock import birth_clock_input_receipt
from fatebridge.utils.birth_input import PersonInfo, create_person_info
from fatebridge.utils.solar_time import normalize_birth_time
from tests.bazi.test_bazi_birth_seconds import SPECS
from tests.evaluation.test_agentic_nested_outputs import inputs

SHANGHAI = dict(
    birth_year=1991,
    birth_month=9,
    birth_day=15,
    birth_hour=1,
    birth_minute=30,
    birth_second=0,
    birth_timezone="Asia/Shanghai",
    use_true_solar_time=False,
)


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.key)
@pytest.mark.parametrize("offset,hour,fold", [("+09:00", 16, 0), ("+08:00", 17, 1)])
def test_all_actual_bindings_preserve_selected_instant_and_original_zone(
    spec, offset, hour, fold
):
    req = spec.request_model.model_validate(
        {**inputs(spec), **SHANGHAI, "birth_utc_offset": offset}
    )
    _, args, kwargs = spec.bind(req)
    person = args[0]
    assert person.birth_utc_offset == offset
    assert "birth_utc_offset" not in kwargs
    normalized = normalize_birth_time(person)
    assert normalized.input_datetime.astimezone(timezone.utc) == datetime(
        1991, 9, 14, hour, 30, tzinfo=timezone.utc
    )
    assert normalized.input_datetime.fold == fold
    assert normalized.input_datetime.tzinfo.key == "Asia/Shanghai"


@pytest.mark.parametrize("bad", [True, 8, 8.0])
def test_offset_has_no_numeric_or_boolean_coercion(bad):
    with pytest.raises(ValidationError):
        BaziBirthRequest(**SHANGHAI, birth_utc_offset=bad)
    with pytest.raises(ValidationError):
        PersonInfo(**SHANGHAI, birth_utc_offset=bad)


@pytest.mark.parametrize(
    "bad", ["", "+8:00", "+08:60", "+15:00:01", "+07:00", "UTC+08:00"]
)
def test_wrong_or_malformed_selector_cannot_create_a_birth_instant(bad):
    with pytest.raises(ValueError, match="birth_utc_offset"):
        normalize_birth_time(PersonInfo(**SHANGHAI, birth_utc_offset=bad))


def test_omitted_offset_does_not_choose_a_fold_and_no_offset_fills_a_gap():
    with pytest.raises(ValueError):
        normalize_birth_time(PersonInfo(**SHANGHAI))
    gap = {**SHANGHAI, "birth_month": 4, "birth_day": 14, "birth_hour": 2}
    for offset in [None, "+08:00", "+09:00"]:
        with pytest.raises(ValueError):
            normalize_birth_time(PersonInfo(**gap, birth_utc_offset=offset))


def test_conflicting_direct_and_recorded_offsets_are_rejected_by_actual_instant():
    person = PersonInfo(**SHANGHAI, birth_utc_offset="+09:00")
    first = normalize_birth_time(person, birth_utc_offset="+09:00:00")
    assert first.input_datetime.fold == 0
    with pytest.raises(ValueError, match="birth_utc_offset"):
        normalize_birth_time(person, birth_utc_offset="+08:00")
    helper = create_person_info(
        1991,
        9,
        15,
        1,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        birth_utc_offset="+08:00",
    )
    assert normalize_birth_time(helper).input_datetime.fold == 1


def test_opt_in_receipt_states_actual_instant_rules_and_unverified_source_precision():
    person = PersonInfo(**SHANGHAI, birth_utc_offset="+08:00")
    receipt = birth_clock_input_receipt(person, normalize_birth_time(person))
    assert receipt["requested_utc_offset"] == "+08:00"
    assert receipt["civil_utc_offset"] == "+08:00"
    assert receipt["civil_instant_utc"] == "1991-09-14T17:30:00+00:00"
    assert receipt["civil_fold"] == 1 and receipt["civil_time_ambiguous"] is True
    assert receipt["timezone_source"] == "birth_timezone"
    assert receipt["timezone_rules"]["provider"]
    assert receipt["observed_precision_certified"] is False
    ordinary = person.model_copy(update={"birth_day": 16, "birth_utc_offset": None})
    old = birth_clock_input_receipt(ordinary, normalize_birth_time(ordinary))
    assert "civil_fold" not in old and "requested_utc_offset" not in old


def test_selected_timezone_is_kept_for_future_dayun_boundaries():
    a = PersonInfo(**SHANGHAI, birth_utc_offset="+09:00", gender="男")
    aa = normalize_birth_time(a)
    b = a.model_copy(update={"birth_timezone": "+09:00"})
    bb = normalize_birth_time(b)
    fixed, named = [
        TimingAnalysis.calculate_dayun_timeline(
            n.input_datetime, "男", ("丁", "酉"), timezone_name=n.timezone, periods=2
        )
        for n in (bb, aa)
    ]
    assert (
        fixed["start_details"]["elapsed_seconds"]
        == named["start_details"]["elapsed_seconds"]
    )
    # Same instant and nominal calendar offset, but future Shanghai is +08.
    assert fixed["calendar_offset"] == named["calendar_offset"]
    assert datetime.fromisoformat(named["start_at"]).astimezone(
        timezone.utc
    ) - datetime.fromisoformat(fixed["start_at"]).astimezone(timezone.utc) == timedelta(
        hours=1
    )


def test_same_wall_cache_does_not_reuse_the_other_side_of_havana_jie():
    base = dict(
        birth_year=2021,
        birth_month=11,
        birth_day=7,
        birth_hour=0,
        birth_minute=30,
        birth_second=0,
        birth_timezone="America/Havana",
        use_true_solar_time=False,
    )
    expected = {"-04:00": ("戊", "戌"), "-05:00": ("己", "亥")}
    for order in [list(expected), list(reversed(expected))]:
        BaZiCalendar._get_four_pillars_cached.cache_clear()
        for offset in order:
            n = normalize_birth_time(PersonInfo(**base, birth_utc_offset=offset))
            p = BaZiCalendar.get_four_pillars(
                n.corrected_datetime,
                timezone_name=n.timezone,
                civil_datetime=n.input_datetime,
            )
            assert p == {
                "year": ("辛", "丑"),
                "month": expected[offset],
                "day": ("己", "未"),
                "hour": ("甲", "子"),
            }


def test_minute_grid_uses_each_derived_instant_offset_across_clock_rollback(
    monkeypatch,
):
    import fatebridge.services.timing_uncertainty as module

    person = PersonInfo(**{**SHANGHAI, "birth_minute": 59}, birth_utc_offset="+09:00")
    seen = []
    original = module.normalize_birth_time

    def observe(sample, **kwargs):
        result = original(sample, **kwargs)
        seen.append(
            (sample.birth_utc_offset, result.input_datetime.astimezone(timezone.utc))
        )
        return result

    monkeypatch.setattr(module, "normalize_birth_time", observe)
    result = module.analyze_birth_time_range(
        person, 1, analysis_moment=datetime(2026, 1, 1)
    )
    assert result["sample_count"] == 3
    assert [x[0] for x in seen] == ["+09:00", "+09:00", "+09:00", "+08:00"]
    assert [x[1] for x in seen[1:]] == [
        datetime(1991, 9, 14, 16, 58, tzinfo=timezone.utc) + timedelta(minutes=k)
        for k in range(3)
    ]


@pytest.mark.parametrize("key", ["ziwei_birth", "ziwei_horoscope", "liureng_runyear"])
def test_existing_public_offset_consumers_keep_their_explicit_keyword(key):
    spec = next(s for s in CATALOG if s.key == key)
    values = {**inputs(spec), **SHANGHAI, "birth_utc_offset": "+09:00"}
    values.pop("birth_second")
    _, args, kwargs = spec.bind(spec.request_model.model_validate(values))
    assert args[0].birth_utc_offset == "+09:00"
    assert kwargs["birth_utc_offset"] == "+09:00"


def test_ren_birth_clock_direct_record_and_keyword_cannot_disagree():
    from fatebridge.core.metaphysics.ren_calendar import resolve_runyear_birth_clock

    wall = datetime(1991, 9, 15, 1, 30, 59)
    actual, receipt = resolve_runyear_birth_clock(
        wall, "Asia/Shanghai", recorded_offset="+08:00"
    )
    assert actual.astimezone(timezone.utc) == datetime(
        1991, 9, 14, 17, 30, 59, tzinfo=timezone.utc
    )
    assert receipt["input_utc_offset"] == "+08:00"
    with pytest.raises(ValueError, match="birth_utc_offset"):
        resolve_runyear_birth_clock(
            wall, "Asia/Shanghai", "+09:00", recorded_offset="+08:00"
        )


def test_ren_direct_known_second_is_used_before_chronology_comparison():
    from fatebridge.services.metaphysics import calculate_liureng_runyear

    person = PersonInfo(**{**SHANGHAI, "birth_second": 59}, birth_utc_offset="+08:00")
    result = calculate_liureng_runyear(
        person,
        analysis_year=1991,
        analysis_month=9,
        analysis_day=15,
        analysis_hour=1,
        analysis_minute=30,
        analysis_second=30,
        analysis_timezone="Asia/Shanghai",
        analysis_utc_offset="+08:00",
        use_true_solar_time=False,
    )
    assert "分析日期不能早于出生日期" in result["error"]
    assert "runyear" not in result


@pytest.mark.parametrize(
    "zone,wall,longitude,offsets",
    [
        ("Asia/Shanghai", "1991-09-15T01:30:00", 120, ["+09:00", "+08:00"]),
        ("America/New_York", "2015-11-01T01:30:00", -74, ["-04:00", "-05:00"]),
        ("Australia/Lord_Howe", "2020-04-05T01:45:00", 159.08, ["+11:00", "+10:30"]),
        ("America/Havana", "2021-11-07T00:30:00", -82.3667, ["-04:00", "-05:00"]),
    ],
)
def test_apparent_clock_uses_the_selected_instant_in_named_and_fixed_zone_controls(
    zone, wall, longitude, offsets, monkeypatch
):
    import fatebridge.utils.solar_time as module

    observed = []
    original = module.calculate_equation_of_time_minutes

    def observe(moment):
        observed.append(moment.astimezone(timezone.utc))
        return original(moment)

    monkeypatch.setattr(module, "calculate_equation_of_time_minutes", observe)
    local = datetime.fromisoformat(wall)
    for offset in offsets:
        person = PersonInfo(
            birth_year=local.year,
            birth_month=local.month,
            birth_day=local.day,
            birth_hour=local.hour,
            birth_minute=local.minute,
            birth_second=local.second,
            birth_timezone=zone,
            birth_utc_offset=offset,
            birth_longitude=longitude,
            use_true_solar_time=True,
        )
        named = normalize_birth_time(person)
        fixed = normalize_birth_time(
            person.model_copy(update={"birth_timezone": offset})
        )
        assert observed[-2] == observed[-1]
        assert named.input_datetime.astimezone(timezone.utc) == observed[-1]
        assert named.corrected_datetime == fixed.corrected_datetime
        assert named.timezone == zone
