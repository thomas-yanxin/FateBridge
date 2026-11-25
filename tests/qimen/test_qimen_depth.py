"""Independent classical examples, clock boundaries and conservation tests."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from fatebridge.core.almanac import get_solar_terms_for_year, localize_datetime
from fatebridge.core.local_techniques.qimen import build_qimen_with_options
from fatebridge.core.metaphysics import qimen as engine
from fatebridge.core.qimen import qimen_evidence as evidence
from fatebridge.services.metaphysics import calculate_qimen_analysis
from tests.unit_test.fixtures.qimen import fixed_board, seed

FIXTURE = json.loads(
    (Path(__file__).parents[1] / "fixtures/qimen-classical-excerpts.json").read_text()
)


@pytest.mark.parametrize("case", FIXTURE["leader_examples"])
def test_leader_identities_from_explicit_classical_examples(
    monkeypatch: pytest.MonkeyPatch, case
) -> None:
    board = fixed_board(monkeypatch, case)
    assert board["zhifu"]["star"] == case["star"]
    assert board["zhishi"]["door"] == case["door"]
    assert board["rule_trace"][0]["outputs"]["source_gong"] == case["source"]
    at = next(p for p in board["palaces"] if p["name"] == board["zhifu"]["palace"])
    assert case["star"] in [at["star"], *at["hosted_stars"]]
    assert board["structure"]["stars_fuyin"]
    # When a centre leader is hosted in 坤, the other doors still remain native.
    if case["source"] != "中":
        assert board["structure"]["doors_fuyin"]
    else:
        pass


@pytest.mark.parametrize("case", FIXTURE["moving_examples"])
def test_moving_examples_are_transcribed_from_book_not_engine(
    monkeypatch: pytest.MonkeyPatch, case
) -> None:
    board = fixed_board(monkeypatch, case)
    assert board["zhifu"]["star"] == case["star"]
    assert board["zhifu"]["trigram"] == case["star_at"]
    assert board["zhishi"]["trigram"] == case["door_at"]
    by_gua = {p["trigram"]: p for p in board["palaces"]}
    for gua, stem in case["sky_stems"].items():
        assert stem in by_gua[gua]["heaven_stems"]


@pytest.mark.parametrize("case", FIXTURE["pattern_examples"])
def test_book_pattern_examples_include_hosted_heaven_stem(
    monkeypatch: pytest.MonkeyPatch, case
) -> None:
    board = fixed_board(monkeypatch, case)
    at = next(p for p in board["palaces"] if p["name"] == case["palace"])
    assert case["sky"] in at["heaven_stems"]
    assert case["earth"] in at["earth_stems"]
    assert any(
        p["name"] == case["name"] and p["palace"] == case["palace"]
        for p in board["patterns"]
    )


def call(at, **extra):
    return calculate_qimen_analysis(
        analysis_year=at.year,
        analysis_month=at.month,
        analysis_day=at.day,
        analysis_hour=at.hour,
        analysis_minute=at.minute,
        analysis_timezone="Asia/Hong_Kong",
        use_true_solar_time=False,
        **extra,
    )


def test_hko_published_day_anchors_and_late_zi_do_not_double_roll() -> None:
    # Independently read from HKO January 2026 calendar PDF, p1.
    for date, expected in [
        ("2026-01-01", "乙亥"),
        ("2026-01-20", "甲午"),
        ("2026-01-31", "乙巳"),
    ]:
        board = call(datetime.fromisoformat(date).replace(hour=12))["qimen"]
        assert board["day_ganzhi"] == expected
    moments = [
        datetime(2026, 1, 19, 22, 59),
        datetime(2026, 1, 19, 23),
        datetime(2026, 1, 20),
        datetime(2026, 1, 20, 0, 59),
    ]
    boards = [call(t)["qimen"] for t in moments]
    assert [b["day_ganzhi"] for b in boards] == ["癸巳", "甲午", "甲午", "甲午"]
    assert [b["time_ganzhi"] for b in boards[1:]] == ["甲子"] * 3
    assert boards[1]["palaces"] == boards[2]["palaces"] == boards[3]["palaces"]


def test_term_instant_uses_civil_time_while_hour_uses_apparent_solar() -> None:

    for year in [2026, 2027]:
        for term in get_solar_terms_for_year(year, "Asia/Hong_Kong"):
            if term.name not in {"夏至", "冬至", "立春"}:
                continue
            else:
                pass
            for offset in [-2, 2]:
                at = term.moment.replace(tzinfo=None) + timedelta(minutes=offset)
                civil = call(at, qimen_options={"ju_method": "chaibu"})
                solar = calculate_qimen_analysis(
                    analysis_year=at.year,
                    analysis_month=at.month,
                    analysis_day=at.day,
                    analysis_hour=at.hour,
                    analysis_minute=at.minute,
                    analysis_timezone="Asia/Hong_Kong",
                    analysis_longitude=75.0,
                    use_true_solar_time=True,
                    qimen_options={"ju_method": "chaibu"},
                )
                assert civil["qimen"]["ju_term"] == solar["qimen"]["ju_term"]
                assert (civil["qimen"]["ju_term"] == term.name) == (offset > 0)


def test_hko_major_terms_match_independent_published_minute() -> None:

    fixture = json.loads(
        (
            Path(__file__).parents[1] / "fixtures/qimen-calendar-hko-2026.json"
        ).read_text()
    )
    terms = {t.name: t for t in get_solar_terms_for_year(2026, fixture["timezone"])}
    for case in fixture["cases"]:
        assert (
            abs(
                (
                    terms[case["term"]].moment - datetime.fromisoformat(case["at"])
                ).total_seconds()
            )
            <= fixture["tolerance_seconds"]
        )


@pytest.mark.parametrize(
    "options",
    [
        {"layout": "fly"},
        {"layout": "mirror"},
        {"palaceShift": 1},
        {"ju_method": "unknown"},
        {"typo": True},
    ],
)
def test_no_silent_fake_school_or_ignored_option(options) -> None:
    with pytest.raises(ValueError):
        build_qimen_with_options(seed(), options)


def test_wangshuai_is_qimen_star_rule_and_not_bazi() -> None:
    assert [
        evidence.star_season_state("水", month)
        for month in ["水", "木", "金", "火", "土"]
    ] == ["相", "旺", "废", "休", "囚"]


def test_day_and_hour_xun_are_separate_not_inconsistent() -> None:
    board = call(datetime(2028, 4, 6, 9, 33))["qimen"]
    assert (board["xun_head"], board["kongwang"]) == ("甲申", "午未空")
    assert (board["day_xun_head"], board["day_kongwang"]) == ("甲寅", "子丑空")
    assert board["rule_trace"][0]["outputs"]["xun_head"] == board["xun_head"]
    assert board["assessment"]["interpretation_status"] == "rule_evidence_only"


def test_zhirun_schedule_is_continuous_across_year_and_cache_anchors() -> None:
    # Regression: the old >=9 initializer disagreed with the >9 continuation
    # for January 2019, so yearly cache rollover silently moved ju by 15 days.
    for year in range(1901, 2100):
        current = engine._qimen_build_yinyangdun_map(year, "Asia/Shanghai")
        following = engine._qimen_build_yinyangdun_map(year + 1, "Asia/Shanghai")
        overlap = sorted(
            k for k in current.keys() & following.keys() if k.startswith(str(year + 1))
        )
        assert overlap
        for key in overlap:
            assert current[key] == following[key], (key, current[key], following[key])


def test_five_not_meet_requires_same_polarity_and_reports_the_two_stems(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = {"dun": "阳遁", "ju": 1, "hour": "庚午"}
    assert fixed_board(monkeypatch, case, day="甲子")["structure"]["five_not_meet"]
    # 辛 also controls 甲, but it is the opposite polarity and not 五不遇.
    case["hour"] = "辛未"
    assert not fixed_board(monkeypatch, case, day="甲子")["structure"]["five_not_meet"]


def test_nine_day_zhirun_boundary_from_hko_calendar_and_declared_profile() -> None:
    fixture = json.loads(
        (
            Path(__file__).parents[1] / "fixtures/qimen-zhirun-boundary-2018.json"
        ).read_text()
    )
    for case in fixture["cases"]:
        board = call(datetime.fromisoformat(case["at"]))["qimen"]
        assert board["day_ganzhi"] == case["day"]
        assert board["ju_term"] == case["ju_term"]
        assert board["ju_text"] == case["ju_text"]


@pytest.mark.parametrize(
    "at,expected",
    [
        ("2010-06-13T12:00:00", ("甲午", "芒种", "阳遁六局上元")),
        ("2012-12-14T12:00:00", ("己酉", "大雪", "阴遁四局上元")),
        ("2013-01-01T12:00:00", ("丁卯", "冬至", "阳遁一局上元")),
    ],
    ids=["mangzhong-repeat", "daxue-repeat", "next-year-seed"],
)
def test_zhirun_nine_dates_including_both_ends(
    monkeypatch: pytest.MonkeyPatch, at: str, expected
) -> None:
    # Siku vol. 1, p. 13 counts 初一 through 初九. The DE441 reference
    # dates give that same eight-day separation for these two anchors.
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    result = call(datetime.fromisoformat(at), qimen_options={"ju_method": "zhirun"})
    board = result["qimen"]
    assert (board["day_ganzhi"], board["ju_term"], board["ju_text"]) == expected


def test_missing_or_inconsistent_zhirun_calendar_never_guesses_ju(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(engine, "_qimen_build_yinyangdun_map", lambda *args: {})
    with pytest.raises(ValueError, match="无法确定置闰局"):
        engine.build_qimen_board(seed())
    monkeypatch.setattr(
        engine,
        "_qimen_build_yinyangdun_map",
        lambda *args: {"20260101": ("冬至", "甲子")},
    )
    # The synthetic seed says 乙亥, so the injected 甲子 row must fail closed.
    with pytest.raises(ValueError, match="有效日柱不一致"):
        engine.build_qimen_board(seed(day="乙亥"))
