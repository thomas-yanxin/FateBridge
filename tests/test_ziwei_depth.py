"""Independent sources, rule differences, palace identity and rejected guesses."""

import shutil
from dataclasses import replace

import pytest

from fatebridge.core.metaphysics.ziwei import (
    ZIWEI_SIHUA_RULES,
    _resolve_wuxing_ju,
    build_ziwei_chart,
    build_ziwei_horoscope,
    build_ziwei_rules,
)
from fatebridge.core.ziwei_rulesets import effective_lunar_month
from fatebridge.services.metaphysics import (
    _build_analysis_seed,
    calculate_ziwei_birth,
    calculate_ziwei_horoscope,
)
from fatebridge.utils.birth_input import create_person_info
from scripts.audit_ziwei import (
    FIXTURES,
    audit_calendar,
    audit_classical,
    hko_rows,
    report,
    synthetic_seed,
)

pytestmark = [
    pytest.mark.filterwarnings("ignore:fromSolarDate is deprecated:DeprecationWarning"),
    pytest.mark.filterwarnings("ignore:toSolarDate is deprecated:DeprecationWarning"),
    pytest.mark.filterwarnings("ignore:use is_leap_month:DeprecationWarning"),
]


def test_frozen_hko_cells_and_classical_vectors_have_separate_denominators():
    result = report()
    calendar = result["calendar"]
    assert calendar["status"] == "pass_in_frozen_corpus"
    assert calendar["day_and_year_cells"] == 73049
    assert calendar["full_date_cells"] == 73049
    assert calendar["outside_engine_support"] == 0
    assert calendar["source_prefix_cells_recovered_from_preceding_tam_table"] == 19
    assert (
        result["current_supported_civil_date_label_coverage"]["distinct_dates_compared"]
        == 73414
    )
    assert len(calendar["coverage"]) == 200
    classical = result["classical"]
    assert classical["checked_vectors"] == 47
    assert not classical["failed_vectors"]
    assert classical["unresolved_source_items"]
    assert classical["status"] == "partial"
    assert not classical["whole_book_acceptance_passed"]
    assert not result["full_acceptance_passed"]
    assert result["real_world_prediction"]["score"] is None
    assert result["real_world_prediction"]["independent_outcomes"] == 0


@pytest.mark.parametrize(
    "kind,name",
    [("calendar", "hko/T2026c.txt"), ("classical", "classical_excerpt.json")],
)
def test_source_edits_fail_without_silent_fixture_regeneration(tmp_path, kind, name):
    shutil.copytree(FIXTURES, tmp_path, dirs_exist_ok=True)
    path = tmp_path / name
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="checksum mismatch"):
        (audit_calendar if kind == "calendar" else audit_classical)(tmp_path)


def test_hko_parser_rejects_missing_or_reordered_days():
    text = (FIXTURES / "hko/T2026c.txt").read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    incomplete = "\n".join(
        line for line in lines if not line.startswith("2026年2月17日")
    )
    with pytest.raises(ValueError, match="missing, duplicate or unordered"):
        hko_rows(incomplete, 2026)


def test_audit_detects_a_wrong_engine_table_without_changing_expectations(monkeypatch):
    monkeypatch.setitem(ZIWEI_SIHUA_RULES["甲"], "化科", "太阴")
    result = audit_classical()
    assert result["status"] == "failed"
    failed = next(c for c in result["failed_vectors"] if c["case"] == "sihua/甲")
    assert failed["expected"] == ["廉贞", "破军", "武曲", "太阳"]
    assert failed["actual"] == ["廉贞", "破军", "太阴", "太阳"]


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_profile_changes_every_sihua_layer_and_actual_labels(profile):
    chart = build_ziwei_chart(synthetic_seed(1992), "男", rule_profile=profile)
    expected = "左辅" if profile == "iztro_2_5_8" else "天府"
    assert chart["sihua"]["化科"] == expected
    assert (
        sum(
            s["name"] == expected and s["mutagen"] == "化科"
            for p in chart["palaces"]
            for s in p["stars_detail"]
        )
        == 1
    )
    target = _build_analysis_seed(
        analysis_year=2032, analysis_month=6, analysis_day=15, analysis_hour=12
    )
    horoscope = build_ziwei_horoscope(
        nominal_age_basis="legacy_mixed_clock",
        chart=chart,
        gender="男",
        target_seed=target,
    )
    assert horoscope["ruleset"]["id"] == profile
    for scope in horoscope["scopes"]:
        if scope["stem"] == "壬":
            assert scope["mutagen"]["化科"] == expected
        assert (
            scope["mutagen"]
            == build_ziwei_rules(scope["stem"], rule_profile=profile)["focused_rules"][
                "sihua"
            ]
        )
    annual = next(s for s in horoscope["scopes"] if s["scope"] == "流年")
    link = next(
        x for x in annual["mutagen_natal_links"] if x["transformation"] == "化科"
    )
    assert link["star"] == expected
    assert link["status"] == "matched"


def test_real_leap_month_early_half_and_late_half_have_explicit_conventions():
    # HKO: 2025-07-25 is leap sixth month day 1; day 16 is 2025-08-09.
    for day, expected in [(25, [6, 7])]:
        seed = _build_analysis_seed(
            analysis_year=2025, analysis_month=7, analysis_day=day, analysis_hour=0
        )
        charts = [
            build_ziwei_chart(seed, "男", rule_profile=p)
            for p in ("iztro_2_5_8", "quanshu_v2_excerpt")
        ]
        assert [
            c["calendar_rules"]["effective_birth_month"] for c in charts
        ] == expected
        assert charts[0]["ming_gong"]["branch"] != charts[1]["ming_gong"]["branch"]
        assert (
            charts[0]["lunar_date"]
            == charts[1]["lunar_date"]
            == dict(year=2025, month=6, day=1, is_leap_month=True)
        )
    seed = _build_analysis_seed(
        analysis_year=2025, analysis_month=8, analysis_day=9, analysis_hour=0
    )
    assert [
        build_ziwei_chart(seed, "男", rule_profile=p)["calendar_rules"][
            "effective_birth_month"
        ]
        for p in ("iztro_2_5_8", "quanshu_v2_excerpt")
    ] == [7, 7]


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_leap_twelfth_month_ordinal_is_preserved_for_ten_period_stems(profile):
    assert effective_lunar_month(12, 16, True, profile) == 13
    chart = build_ziwei_chart(
        synthetic_seed(1984, month=12, day=16, leap=True), "男", rule_profile=profile
    )
    assert chart["calendar_rules"]["effective_birth_month"] == 13
    assert chart["ming_gong"]["branch"] == "寅"


def test_unknown_gender_keeps_natal_stars_but_does_not_guess_direction():
    seed = synthetic_seed(1984)
    unknown = build_ziwei_chart(seed, "未知")
    male = build_ziwei_chart(seed, "男")
    assert "未定" in unknown["daxian_direction"]
    assert all(
        p["daxian"] is None and p["daxian_period"] is None for p in unknown["palaces"]
    )
    assert [p["stars_detail"] for p in unknown["palaces"]] == [
        p["stars_detail"] for p in male["palaces"]
    ]
    with pytest.raises(ValueError, match="需要明确性别"):
        build_ziwei_horoscope(
            nominal_age_basis="legacy_mixed_clock",
            chart=unknown,
            gender="未知",
            target_seed=synthetic_seed(2026),
        )


def test_natal_leap_excerpt_is_not_silently_extended_to_target_months():
    # Natal is an ordinary month: profiles share geometry. Only the target is
    # leap-sixth-month day 1. The natal 安身命 excerpt is not a 流月 rule.
    target = _build_analysis_seed(
        analysis_year=2025, analysis_month=7, analysis_day=25, analysis_hour=12
    )
    results = []
    for profile in ("iztro_2_5_8", "quanshu_v2_excerpt"):
        chart = build_ziwei_chart(synthetic_seed(1984), "男", rule_profile=profile)
        result = build_ziwei_horoscope(
            nominal_age_basis="legacy_mixed_clock",
            chart=chart,
            gender="男",
            target_seed=target,
        )
        results.append(next(s for s in result["scopes"] if s["scope"] == "流月"))
        assert (
            result["ruleset"]["target_leap_month_rule"]
            == "iztro_split_at_day_15_not_classically_verified"
        )
    assert results[0]["branch"] == results[1]["branch"]
    assert results[0]["stem"] == results[1]["stem"]


def test_unknown_nayin_and_invalid_profiles_or_dates_cannot_produce_plausible_charts():
    with pytest.raises(ValueError, match="无法确定五行局"):
        _resolve_wuxing_ju("甲", "丑")
    with pytest.raises(ValueError, match="不支持的紫微规则"):
        build_ziwei_chart(synthetic_seed(1984), "男", rule_profile="perfect_predictor")
    with pytest.raises(ValueError, match="有效范围"):
        build_ziwei_chart(synthetic_seed(1984, month=13), "男")
    with pytest.raises(ValueError, match="年干必须"):
        build_ziwei_rules("not_a_stem")
    seed = synthetic_seed(2026)
    invalid = replace(seed, calendar_context={"lunar_calendar": {"month": 1, "day": 1}})
    with pytest.raises(ValueError, match="目标农历年缺失"):
        build_ziwei_horoscope(
            nominal_age_basis="legacy_mixed_clock",
            chart=build_ziwei_chart(synthetic_seed(1984), "男"),
            gender="男",
            target_seed=invalid,
        )


def test_ming_sanfang_contains_career_wealth_and_opposite_without_borrowing_stars():
    chart = build_ziwei_chart(synthetic_seed(1984), "男")
    ming = chart["palaces"][0]["structural_evidence"]
    assert [p["natal_palace_name"] for p in ming["sanfang_sizheng"]] == [
        "命宫",
        "官禄宫",
        "财帛宫",
        "迁移宫",
    ]
    by_name = {p["name"]: p for p in chart["palaces"]}
    assert (
        sum(len(p["structural_evidence"]["major_stars"]) for p in chart["palaces"])
        == 14
    )
    for palace in chart["palaces"]:
        evidence = palace["structural_evidence"]
        assert not evidence["opposite_stars_relocated"]
        assert evidence["is_empty_main_palace"] == (len(evidence["major_stars"]) == 0)
        assert len({p["branch"] for p in evidence["sanfang_sizheng"]}) == 4
        for related in evidence["sanfang_sizheng"]:
            assert (
                related["stars_detail"]
                == by_name[related["natal_palace_name"]]["stars_detail"]
            )


def test_childhood_palace_is_not_silently_labelled_as_an_actual_decade():
    chart = build_ziwei_chart(synthetic_seed(2025), "女")
    result = build_ziwei_horoscope(
        nominal_age_basis="legacy_mixed_clock",
        chart=chart,
        gender="女",
        target_seed=synthetic_seed(2025),
    )
    daxian = result["scopes"][0]
    assert daxian["status"] == "not_started"
    assert daxian["is_childhood_limit"] is False
    assert daxian["natal_palace_name"] is None
    assert daxian["mutagen"] is None
    assert result["childhood_limit"]["natal_palace_name"] == "命宫"


def test_same_year_target_before_birth_is_rejected_using_actual_instants():
    person = create_person_info(
        birth_year=2025,
        birth_month=7,
        birth_day=25,
        birth_hour=12,
        gender="男",
        birth_timezone="Asia/Shanghai",
        use_true_solar_time=False,
    )
    rejected = calculate_ziwei_horoscope(
        person, target_year=2025, target_month=7, target_day=25, target_hour=11
    )
    assert rejected["status_code"] == 400
    assert "早于出生" in rejected["error"]
    # 04:01 UTC is after 12:00 Shanghai despite its smaller clock hour.
    accepted = calculate_ziwei_horoscope(
        person,
        target_year=2025,
        target_month=7,
        target_day=25,
        target_hour=4,
        target_minute=1,
        target_timezone="UTC",
    )
    assert "error" not in accepted, accepted
    assert accepted["analysis_context"]["analysis_minute"] == 1


def test_rule_trace_exposes_inputs_and_snapshots_preserve_selected_convention():
    person = create_person_info(
        birth_year=1992,
        birth_month=8,
        birth_day=15,
        birth_hour=14,
        gender="男",
        use_true_solar_time=False,
    )
    result = calculate_ziwei_birth(person, rule_profile="quanshu_v2_excerpt")
    chart = result["ziwei_birth"]
    trace = {r["rule_id"]: r for r in chart["rule_trace"]}
    assert (
        trace["wuhu_dun_nayin_ju"]["outputs"]["ju_number"]
        == chart["wuxing_ju"]["number"]
    )
    assert (
        trace["ming_shen_month_hour"]["outputs"]["ming_branch"]
        == chart["ming_gong"]["branch"]
    )
    assert "quanshu_v2_excerpt" in result["snapshot_text"]
    assert chart["ruleset"]["classical_conformance"] == "partial_excerpt"
