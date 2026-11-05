"""Related contract regressions with shared imports; original cases retained."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from fatebridge.core import almanac, solar_term_clock
from fatebridge.core.almanac import localize_datetime
from fatebridge.core.classical import (
    build_classical_overview,
    determine_monthly_structure,
    seasonal_climate_god,
    twelve_life_stage,
)
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.strength import DEFAULT_POLICY, evaluate_strength_policy
from fatebridge.services.bazi import calculate_bazi_birth
from fatebridge.services.knowledge import calculate_knowledge_read
from fatebridge.services.structured_snapshot import _KEY_LABELS, _label
from fatebridge.services.timing_uncertainty import analyze_birth_time_range
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.solar_time import normalize_birth_time
from tests.bazi.test_bazi_birth_seconds import BASE, SPECS
from tests.support.bazi_punishment_reference import GEOMETRIES, ORDER
from tests.support.transports import inputs


@pytest.mark.parametrize(
    "zone", ["Asia/Kolkata", "Europe/Amsterdam", "Europe/Paris", "Africa/Monrovia"]
)
def test_minute_grid_does_not_reparse_historical_second_offsets(zone):
    person = PersonInfo(
        birth_year=1900,
        birth_month=5,
        birth_day=15,
        birth_hour=10,
        birth_minute=20,
        birth_second=59,
        birth_timezone=zone,
        use_true_solar_time=False,
    )
    result = analyze_birth_time_range(person, 1, analysis_moment=datetime(2026, 1, 1))
    assert result["sample_count"] == 3
    assert sum(r["sample_count"] for r in result["pillars_candidates"]) == 3
    assert datetime.fromisoformat(result["birth_at_range"]["start"]).second == 59
    assert datetime.fromisoformat(result["birth_at_range"]["end"]).second == 59
    assert "未证明采样间秒级无变化" in result["interpretation_scope"]


def test_sampling_preserves_both_fold_occurrences_without_defaulting_to_one(
    monkeypatch,
):
    import fatebridge.services.timing_uncertainty as module

    original = module.normalize_birth_time
    observed = []

    def observe(person, **kwargs):
        value = original(person, **kwargs)
        observed.append(
            localize_datetime(value.input_datetime, value.timezone).astimezone(
                timezone.utc
            )
        )
        return value

    monkeypatch.setattr(module, "normalize_birth_time", observe)
    person = PersonInfo(
        birth_year=2015,
        birth_month=11,
        birth_day=1,
        birth_hour=2,
        birth_minute=10,
        birth_second=59,
        birth_timezone="America/New_York",
        use_true_solar_time=False,
    )
    result = module.analyze_birth_time_range(
        person, 120, analysis_moment=datetime(2026, 1, 1)
    )
    samples = observed[1:]
    assert len(samples) == len(set(samples)) == result["sample_count"] == 241
    assert all(b - a == timedelta(minutes=1) for a, b in zip(samples, samples[1:]))
    assert result["birth_at_range"] == {
        "start": "2015-11-01T01:10:59-04:00",
        "end": "2015-11-01T04:10:59-05:00",
    }


@pytest.mark.parametrize(
    "spec", [s for s in SPECS if s.key != "analyze_destiny"], ids=lambda s: s.key
)
def test_every_existing_snapshot_export_keeps_the_known_clock_receipt(spec):
    request = spec.request_model.model_validate(
        {**inputs(spec), **BASE, "birth_minute": 20, "birth_second": 59}
    )
    service, args, kwargs = spec.bind(request)
    result = service(*args, **kwargs)
    assert "error" not in result
    assert "1990-05-15T10:20:59+00:00" in result["snapshot_text"]
    assert "1990-05-15T10:20:59+00:00" in result["snapshot_export"]["export_text"]
    assert "不认证" in result["snapshot_export"]["export_text"]


@pytest.mark.parametrize(
    "key", ["燥湿与生发条件", "物理藏根与功能根", "隐显与制化", "众寡与日主符合"]
)
def test_public_semantic_cards_publish_named_source_and_unadjudicated_force(key):
    result = calculate_knowledge_read(
        domain="bazi", category="classical_force_semantics", key=key
    )
    assert "error" not in result
    curation = result["provenance"]["entry_curation"]
    assert (
        curation["validation_status"] == "text_semantics_not_model_force_adjudication"
    )
    source = curation["source_refs"][0]
    assert (
        source["source_sha256"]
        == "d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803"
    )
    assert source["source_pdf_pages"] and source["edition"] in result["snapshot_text"]
    assert source["source_url"] in result["citation"]


@pytest.mark.parametrize("solar", [False, True])
def test_rebase_keeps_a_fractional_actual_instant_on_both_sides_of_a_fold(solar):
    from fatebridge.utils.solar_time import rebase_birth_clock

    person = PersonInfo(
        birth_year=1991,
        birth_month=9,
        birth_day=15,
        birth_hour=1,
        birth_minute=59,
        birth_second=59,
        birth_timezone="Asia/Shanghai",
        birth_utc_offset="+09:00",
        birth_longitude=120,
        use_true_solar_time=solar,
    )
    template = normalize_birth_time(person)
    instant = datetime(1991, 9, 14, 17, 0, 0, 123456, tzinfo=timezone.utc)
    later = rebase_birth_clock(template, instant)
    assert later.input_datetime.astimezone(timezone.utc) == instant
    assert (
        later.input_datetime.fold == 1
        and later.input_datetime.tzinfo.key == "Asia/Shanghai"
    )
    # Compare the established normalization at exactly the same integer second.
    control = normalize_birth_time(
        person.model_copy(
            update={"birth_minute": 0, "birth_second": 0, "birth_utc_offset": "+08:00"}
        )
    )
    assert (
        later.corrected_datetime.replace(tzinfo=None)
        - control.corrected_datetime.replace(tzinfo=None)
    ).total_seconds() == pytest.approx(0.123456, abs=0.0001)
    assert (
        later.timezone == template.timezone
        and later.timezone_source == template.timezone_source
    )
    assert person.birth_utc_offset == "+09:00" and person.birth_second == 59
    assert template.input_datetime.fold == 0


def test_derived_instant_requires_a_physical_timezone_and_preserves_raw_precision():
    from fatebridge.utils.solar_time import rebase_birth_clock

    template = normalize_birth_time(
        PersonInfo(
            birth_year=2000,
            birth_month=1,
            birth_day=1,
            birth_hour=1,
            birth_minute=0,
            birth_second=0,
            birth_timezone="UTC",
            use_true_solar_time=False,
        )
    )
    with pytest.raises(ValueError):
        rebase_birth_clock(template, datetime(2000, 1, 1, 1))
    earlier = datetime(2000, 1, 1, 0, 59, 59, 999999, tzinfo=timezone.utc)
    later = rebase_birth_clock(template, earlier)
    assert later.corrected_datetime == earlier
    assert later.corrected_datetime.microsecond == 999999


def test_default_true_solar_fallback_does_not_acquire_a_made_up_longitude():
    from fatebridge.utils.solar_time import rebase_birth_clock

    template = normalize_birth_time(
        PersonInfo(
            birth_year=2000,
            birth_month=1,
            birth_day=1,
            birth_hour=1,
            birth_minute=0,
            birth_timezone="UTC",
            use_true_solar_time=True,
            true_solar_explicit=False,
        )
    )
    assert template.applied is False
    instant = datetime(2000, 1, 1, 1, 0, 0, 500000, tzinfo=timezone.utc)
    later = rebase_birth_clock(template, instant)
    assert later.applied is False and later.longitude is None
    assert later.corrected_datetime == instant
    assert later.resolution_advisory == template.resolution_advisory


def test_apparent_and_longitude_only_derived_clocks_keep_their_declared_strategy():
    from fatebridge.utils.solar_time import (
        SOLAR_TIME_STRATEGY_LONGITUDE_ONLY,
        rebase_birth_clock,
    )

    person = PersonInfo(
        birth_year=2000,
        birth_month=12,
        birth_day=10,
        birth_hour=9,
        birth_minute=55,
        birth_second=0,
        birth_timezone="Asia/Shanghai",
        birth_longitude=120.47,
        use_true_solar_time=True,
    )
    apparent = normalize_birth_time(person)
    longitude = normalize_birth_time(
        person, solar_time_strategy=SOLAR_TIME_STRATEGY_LONGITUDE_ONLY
    )
    actual = datetime(2000, 12, 10, 2, 55, 0, 654321, tzinfo=timezone.utc)
    a, b = rebase_birth_clock(apparent, actual), rebase_birth_clock(longitude, actual)
    assert a.corrected_datetime != b.corrected_datetime
    assert b.equation_of_time_minutes == 0
    assert a.solar_time_strategy == apparent.solar_time_strategy
    assert b.solar_time_strategy == SOLAR_TIME_STRATEGY_LONGITUDE_ONLY
    assert (
        a.input_datetime.astimezone(timezone.utc)
        == b.input_datetime.astimezone(timezone.utc)
        == actual
    )


@pytest.mark.parametrize(
    "error,reason",
    [
        (ValueError("private-label-and-path"), "solar_root_civil_unrepresentable"),
        (OverflowError("private-overflow"), "solar_root_civil_unrepresentable"),
        (ImportError("private-dependency-path"), "solar_root_clock_unavailable"),
        (RuntimeError("private-clock-failure"), "solar_root_clock_unavailable"),
    ],
)
def test_known_root_clock_failure_is_bounded_and_cannot_return_none(
    error, reason, monkeypatch
):
    def fail(*args):
        raise error

    monkeypatch.setattr(solar_term_clock, "datetime_from_tt_point", fail)
    with pytest.raises(solar_term_clock.SolarTermClockError) as caught:
        solar_term_clock.native_solar_root_datetime(2451545.0)
    result = caught.value.as_result()
    assert result["issues"] == [{"path": "runtime.solar_term_clock", "code": reason}]
    assert "private" not in json.dumps(result)
    assert result["retryable"] is False


def test_original_strict_source_error_is_preserved_not_wrapped(monkeypatch):
    error = EphemerisSourceError("solar_spk_changed")

    def fail(*args):
        raise error

    monkeypatch.setattr(solar_term_clock, "datetime_from_tt_point", fail)
    with pytest.raises(EphemerisSourceError) as caught:
        solar_term_clock.native_solar_root_datetime(2451545.0)
    assert caught.value is error


def test_no_native_engine_and_no_crossing_keep_their_original_unverified_fallback(
    monkeypatch,
):
    anchor = datetime(2000, 1, 1, tzinfo=timezone.utc)
    with monkeypatch.context() as context:
        context.setattr(almanac, "swe", None)
        assert almanac._solar_term_utc_via_swe(2000, 0, anchor) is None
    original = almanac.ephemeris_call

    def no_crossing(method, *args, **kwargs):
        if method == "calc":
            return ((120.0, 0, 1, 0, 0, 0), almanac.swe.FLG_MOSEPH)
        return original(method, *args, **kwargs)

    monkeypatch.setattr(almanac, "ephemeris_call", no_crossing)
    assert almanac._solar_term_utc_via_swe(2000, 0, anchor) is None


@pytest.mark.parametrize(
    "error", [ValueError("private-time"), ImportError("private-package")]
)
def test_known_native_root_clock_failure_never_becomes_a_linear_year(
    error, monkeypatch, tmp_path
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)

    def fail(*args):
        raise error

    monkeypatch.setattr(solar_term_clock, "datetime_from_tt_point", fail)
    with pytest.raises(solar_term_clock.SolarTermClockError):
        almanac._calculate_solar_terms_for_year(2000, "UTC")


@pytest.mark.parametrize("branches", GEOMETRIES)
def test_eight_first_patterns_cannot_resolve_punishment_with_contested_pairs(branches):
    chart = dict(zip(ORDER, (("甲", b) for b in branches)))
    value = evaluate_strength_policy(
        chart, ElementAnalysis.seasonal_phases(chart["month"][1]), DEFAULT_POLICY
    )
    punishment = next(e for e in value["relations"] if e["kind"] == "刑")
    assert punishment["status"] == "active"
    assert all(
        e["status"] == "contested_or_clashed"
        for e in value["relations"]
        if e["kind"] == "六合"
    )


def test_twelve_life_stage_yang_stem_forward():
    # 甲(阳木)顺行：长生亥 → 临官寅 → 帝旺卯
    assert twelve_life_stage("甲", "亥") == "长生"
    assert twelve_life_stage("甲", "寅") == "临官"
    assert twelve_life_stage("甲", "卯") == "帝旺"
    assert twelve_life_stage("甲", "午") == "死"


def test_twelve_life_stage_yin_stem_reverse():
    # 乙(阴木)逆行：长生午 → 帝旺寅
    assert twelve_life_stage("乙", "午") == "长生"
    assert twelve_life_stage("乙", "寅") == "帝旺"
    # 癸(阴水)逆行：长生卯
    assert twelve_life_stage("癸", "卯") == "长生"


def test_monthly_structure_benqi_when_not_transparent():
    # 辛日主、午月：本气丁为七杀，无透 → 七杀格（本气取格）
    pillars = {
        "year": ("庚", "午"),
        "month": ("壬", "午"),
        "day": ("辛", "酉"),
        "hour": ("戊", "子"),
    }
    structure = determine_monthly_structure(pillars, "辛")
    assert structure["label"] == "七杀格"
    assert structure["structure_god"]["role"] == "本气"
    assert structure["is_special"] is False


def test_monthly_structure_prefers_transparent_hidden_stem():
    # 甲日主、辰月（藏戊乙癸）：癸(余气,正印)透年干 → 取正印格而非本气偏财格
    pillars = {
        "year": ("癸", "卯"),
        "month": ("丙", "辰"),
        "day": ("甲", "子"),
        "hour": ("乙", "亥"),
    }
    structure = determine_monthly_structure(pillars, "甲")
    assert structure["label"] == "正印格"
    assert structure["structure_god"]["stem"] == "癸"
    assert structure["structure_god"]["transparent"] is True


def test_monthly_structure_lu_blade_special():
    # 甲日主、寅月：本气甲为比肩 → 建禄格，标记 is_special
    pillars = {
        "year": ("丙", "寅"),
        "month": ("庚", "寅"),
        "day": ("甲", "子"),
        "hour": ("乙", "亥"),
    }
    structure = determine_monthly_structure(pillars, "甲")
    assert structure["label"] == "建禄格"
    assert structure["is_special"] is True


def test_seasonal_climate_known_entry():
    # 甲木生午月：调候用神 癸（主），丁/庚（辅）
    climate = seasonal_climate_god("甲", "午")
    assert climate["available"] is True
    assert climate["primary"] == "癸"
    assert climate["secondary"] == ["丁", "庚"]


def test_seasonal_climate_table_complete():
    # 全 10 干 × 12 月支均有调候表项（120 格无缺漏）
    stems = list("甲乙丙丁戊己庚辛壬癸")
    branches = list("子丑寅卯辰巳午未申酉戌亥")
    for stem in stems:
        for branch in branches:
            assert seasonal_climate_god(stem, branch)["available"], (stem, branch)


def test_build_classical_overview_shape():
    pillars = {
        "year": ("庚", "午"),
        "month": ("壬", "午"),
        "day": ("甲", "子"),
        "hour": ("丙", "寅"),
    }
    overview = build_classical_overview(pillars)
    assert set(overview) == {
        "monthly_structure",
        "seasonal_climate",
        "life_stages",
        "root_profile",
    }
    assert overview["root_profile"]["global_strength_status"] == "not_adjudicated"
    assert overview["life_stages"]["per_pillar"]["时支"] == "临官"


def test_chart_exposes_classical_facts_and_snapshot_section():
    person = PersonInfo(
        name="测试",
        birth_year=1990,
        birth_month=6,
        birth_day=15,
        birth_hour=14,
        birth_minute=0,
        gender="男",
    )
    result = calculate_bazi_birth(person)
    assert "classical" in result["bazi_birth"]
    assert result["bazi_birth"]["classical"]["monthly_structure"]["label"].endswith(
        "格"
    )
    assert "[格局调候]" in result["snapshot_text"]


def test_dayun_age_label_is_unambiguous():
    label = _label("dayun_age")
    assert label == "累计行运年数(起运至今)"
    assert label != "dayun_age"  # 不再是原始英文键
    assert "当前运龄" not in label  # 不再用易误读的旧标签


def test_timing_keys_have_chinese_labels():
    for key in (
        "analysis_date",
        "start_age",
        "years_in_period",
        "dayun_pillar",
        "liunian_pillar",
    ):
        assert key in _KEY_LABELS
        assert _label(key) != key


def test_unknown_key_still_falls_back_to_raw():
    assert _label("some_unmapped_key") == "some_unmapped_key"
