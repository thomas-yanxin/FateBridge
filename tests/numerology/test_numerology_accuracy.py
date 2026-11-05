"""Independent original-text examples and external calendar references.

Neither snapshots from the port nor self-generated expected values establish
accuracy. These checks cover named rules only, not universal prediction.
"""

import json
from datetime import datetime, timedelta, timezone
from itertools import product
from pathlib import Path

import pytest

from fatebridge.core.almanac import get_solar_terms_for_year
from fatebridge.core.canping import (
    BRANCHES,
)
from fatebridge.core.canping import calculate as canping
from fatebridge.core.canping import compute_number, liunian_series
from fatebridge.core.heluo import (
    _reduce_di,
    _reduce_tian,
    _wu_ji_gong,
)
from fatebridge.core.heluo import calculate as heluo
from fatebridge.core.heluo import (
    four_pillar_number_totals,
    gua_lines,
    judge,
    solar_term,
    solar_term_huagong,
    transform_houtian,
    yao_text,
)
from fatebridge.core.heluo_hexagrams import _gua_tables
from fatebridge.core.heluo_yuantang import placement
from fatebridge.core.zhouyi import classical_hexagram
from fatebridge.services.divination import (
    calculate_canping_analysis,
    calculate_heluo_analysis,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"
REFERENCE = json.loads((FIXTURES / "numerology-classical-reference.json").read_text())
NAOJ = json.loads((FIXTURES / "numerology-naoj-2026.json").read_text())


@pytest.mark.parametrize("case", REFERENCE["heluo"])
def test_volume_one_original_examples(case):
    pillars = dict(zip(("year", "month", "day", "hour"), case["pillars"]))
    # Both source printings literally retain this arithmetic illustration.
    # Its Geng-year/Wuxu-month conflict must not become a realizable birth chart.
    # Keep the old fixture and all its numeric assertions rather than changing
    # the source pillars or dropping a nonconforming case from the sample.
    if case["pillars"] == ["庚午", "戊戌", "己酉", "乙亥"]:
        with pytest.raises(ValueError, match="月柱与年干"):
            heluo(
                four_pillars=pillars,
                gender=case["gender"],
                birth_year=case["year"],
                month_zhi="戌",
                hour_zhi="亥",
            )
        actual = four_pillar_number_totals(pillars)
    else:
        actual = heluo(
            four_pillars=pillars,
            gender=case["gender"],
            birth_year=case["year"],
            month_zhi=pillars["month"][1],
            hour_zhi=pillars["hour"][1],
        )
    for key, expected_key in [
        ("tian", "tian"),
        ("di", "di"),
        ("tianNum", "tian_num"),
        ("diNum", "di_num"),
    ]:
        assert actual[key] == case[expected_key]
    for phase in ("xian", "hou"):
        if phase in case:
            assert actual[phase]["name"] == case[phase]
    if "yuan" in case:
        assert actual["xian"]["yuan"] == case["yuan"]
        assert actual["hou"]["yuan"] == case["hou_yuan"]


@pytest.mark.parametrize("case", REFERENCE["canping"])
def test_volume_six_five_element_examples(case):
    number = compute_number(case["day"], case["hour"], case["element"])
    assert number == {
        "shun": case["shun"],
        "ni": case["ni"],
        "ziRound": BRANCHES.index(case["day"]) + BRANCHES.index(case["hour"]) + 2,
        "numShun": case["num_shun"],
        "numNi": case["num_ni"],
    }
    for month in BRANCHES:
        result = canping(
            year_gz=case["year_gz"],
            month_branch=month,
            day_branch=case["day"],
            hour_branch=case["hour"],
        )
        assert result["method"] == "gu"
        assert result["benming"]["numShun"] == case["num_shun"]
        assert result["benming"]["numNi"] == case["num_ni"]


def test_all_branch_pairs_use_inclusive_walk_with_full_circle_for_equal_branches():
    # Independent literal ring walk, including all 12 same-branch cases.
    for day, hour in product(BRANCHES, repeat=2):
        for direction, field in [(1, "shun"), (-1, "ni")]:
            position, count = BRANCHES.index(day), 1
            while True:
                position = (position + direction) % 12
                count += 1
                if BRANCHES[position] == hour:
                    break
            assert compute_number(day, hour, "金")[field] == count


@pytest.mark.parametrize(
    "number,expected",
    [(20, 2), (25, 5), (31, 6), (35, 1), (44, 9), (50, 5), (55, 3), (60, 5), (65, 4)],
)
def test_heaven_number_subtracts_25_once_then_discards_tens(number, expected):
    assert _reduce_tian(number) == expected


@pytest.mark.parametrize(
    "number,expected", [(24, 4), (30, 3), (40, 1), (50, 2), (60, 3), (70, 4)]
)
def test_earth_number_subtracts_30_once_then_discards_tens(number, expected):
    assert _reduce_di(number) == expected


@pytest.mark.parametrize(
    "year,male,female",
    [
        (1504, "艮", "坤"),
        (1564, "艮", "坤"),
        (1624, "離", "兌"),
        (1864, "艮", "坤"),
        (1924, "艮", "坤"),
        (1984, "離", "兌"),
        (2044, "艮", "坤"),
    ],
)
def test_three_yuan_cycles_follow_hongzhi_jiazi_anchor(year, male, female):
    assert _wu_ji_gong(year - 1911, True, True) == male
    assert _wu_ji_gong(year - 1911, True, False) == female
    for offset in (-360, -180, 180, 360):
        assert _wu_ji_gong(year + offset - 1911, True, True) == male


def test_middle_yuan_yin_male_yang_female_and_pre_lichun_cycle_year():
    assert _wu_ji_gong(1924 - 1911, False, True) == "坤"
    assert _wu_ji_gong(1924 - 1911, True, False) == "坤"
    result = calculate_heluo_analysis(
        date="2044-01-15", time="12:00:00", gender="男", use_true_solar_time=False
    )
    assert result["chart"]["cycleYear"] == 2043
    assert result["chart"]["yuanCycle"] == "下元"
    later = calculate_heluo_analysis(
        date="2044-03-15", time="12:00:00", gender="男", use_true_solar_time=False
    )
    assert later["chart"]["yuanCycle"] == "上元"


@pytest.mark.parametrize(
    "up,low,hours,expected",
    [
        ("坤", "坎", "子丑寅卯辰巳", [2, 2, 1, 3, 4, 5]),
        ("巽", "乾", "午未申酉戌亥", [4, 4, 1, 2, 3, 5]),
        ("兌", "坤", "子丑寅卯辰巳", [4, 5, 4, 5, 1, 2]),
        ("乾", "震", "午未申酉戌亥", [2, 3, 2, 3, 1, 4]),
        ("乾", "離", "子丑寅卯辰巳", [1, 3, 4, 5, 6, 2]),
        ("震", "坤", "午未申酉戌亥", [1, 2, 3, 5, 6, 4]),
    ],
)
def test_yuantang_explicit_tables_from_volume_one(up, low, hours, expected):
    lines = gua_lines(up, low)
    assert [placement(lines, h, True, True)["selected_pos"] for h in hours] == expected


@pytest.mark.parametrize(
    "up,male,yang,expected",
    [
        ("乾", True, True, [1, 2, 3, 1, 2, 3, 4, 5, 6, 4, 5, 6]),
        ("乾", False, True, [6, 5, 4, 6, 5, 4, 3, 2, 1, 3, 2, 1]),
        ("乾", False, False, [1, 2, 3, 1, 2, 3, 4, 5, 6, 4, 5, 6]),
        ("坤", False, False, [1, 2, 3, 1, 2, 3, 4, 5, 6, 4, 5, 6]),
        ("坤", True, False, [6, 5, 4, 6, 5, 4, 3, 2, 1, 3, 2, 1]),
        ("坤", True, True, [1, 2, 3, 1, 2, 3, 4, 5, 6, 4, 5, 6]),
    ],
)
def test_pure_hexagrams_have_separate_sex_and_solstice_tables(up, male, yang, expected):
    lines = gua_lines(up, up)
    assert [
        placement(lines, h, male, yang)["selected_pos"] for h in BRANCHES
    ] == expected


@pytest.mark.parametrize(
    "name,low", [("坎為水", "坎"), ("水雷屯", "震"), ("水山蹇", "艮")]
)
def test_three_supreme_hexagrams_both_exception_branches(name, low):
    lines = gua_lines("坎", low)
    for pos, yang in [(5, False), (6, True)]:
        special = transform_houtian(name, lines, pos, yang)
        assert special["yuan"] == pos
        assert [
            i for i, (a, b) in enumerate(zip(lines, special["lines"]), 1) if a != b
        ] == [pos]
        assert transform_houtian(name, lines, pos, not yang)["yuan"] == pos - 3


@pytest.mark.parametrize("name,instant", NAOJ["cases"])
def test_24_solar_terms_against_naoj_and_external_boundary_bracketing(name, instant):
    reference = datetime.fromisoformat(instant)
    terms = get_solar_terms_for_year(2026, "Asia/Shanghai")
    actual = next(t.moment for t in terms if t.name == name)
    assert abs((actual - reference).total_seconds()) <= NAOJ["tolerance_seconds"]
    before = reference - timedelta(seconds=90)
    after = reference + timedelta(seconds=90)
    assert (
        solar_term(
            2026, reference.month, reference.day, "Asia/Tokyo", birth_datetime=before
        )["term"]
        != name
    )
    assert (
        solar_term(
            2026, reference.month, reference.day, "Asia/Tokyo", birth_datetime=after
        )["term"]
        == name
    )


@pytest.mark.parametrize(
    "term,new_yang,quarter",
    [
        ("夏至", False, "離"),
        ("冬至", True, "坎"),
        ("春分", True, "震"),
        ("秋分", False, "兌"),
    ],
)
def test_exact_instant_changes_both_solstice_and_huagong(term, new_yang, quarter):
    at = next(
        t.moment
        for t in get_solar_terms_for_year(2026, "Asia/Shanghai")
        if t.name == term
    )
    before = solar_term(
        2026,
        at.month,
        at.day,
        "Asia/Shanghai",
        birth_datetime=at - timedelta(microseconds=1),
    )
    after = solar_term(2026, at.month, at.day, "Asia/Shanghai", birth_datetime=at)
    assert before["quarter"] != after["quarter"] == quarter
    assert after["yang_ling"] is new_yang
    if term in {"夏至", "冬至"}:
        assert before["yang_ling"] is not new_yang
    same = solar_term(2026, 1, 1, "+00:00", birth_datetime=at.astimezone(timezone.utc))
    # The new source receipt preserves the requested civil labels. Equal UTC
    # instants keep all prior numerical facts, while their local dates can differ.
    a, b = same.copy(), after.copy()
    ca, cb = a.pop("boundary_context"), b.pop("boundary_context")
    assert a == b
    assert (
        ca["context_timezone"] == "+00:00" and cb["context_timezone"] == "Asia/Shanghai"
    )
    da, db = ca.pop("dependencies"), cb.pop("dependencies")
    ca.pop("context_timezone")
    cb.pop("context_timezone")
    assert ca == cb
    from fatebridge.core.almanac import get_day_ganzhi

    local_fields = {
        "datetime",
        "datetime_with_offset",
        "date_key",
        "day_ganzhi",
        "utc_offset_seconds",
        "fold",
        "timezone",
    }
    for x, y in zip(da, db):
        rx, ry = x.pop("record"), y.pop("record")
        assert x == y
        assert {k: v for k, v in rx.items() if k not in local_fields} == {
            k: v for k, v in ry.items() if k not in local_fields
        }
        for record, label in [(rx, "UTC"), (ry, "Asia/Shanghai")]:
            civil = datetime.fromisoformat(record["datetime_with_offset"])
            assert civil == datetime.fromisoformat(x["instant_utc"])
            assert record["datetime"] == civil.replace(tzinfo=None).isoformat(sep=" ")
            assert record["date_key"] == civil.strftime("%Y%m%d")
            assert record["day_ganzhi"] == get_day_ganzhi(
                civil.year, civil.month, civil.day
            )
            assert record["utc_offset_seconds"] == civil.utcoffset().total_seconds()
            assert record["fold"] == 0 and record["timezone"] == label


def test_service_uses_civil_instant_for_terms_despite_solar_clock_correction():
    args = dict(date="2026-06-21", time="16:30:00", zone="+08:00", gender="女")
    civil = calculate_heluo_analysis(**args, use_true_solar_time=False)
    solar = calculate_heluo_analysis(**args, use_true_solar_time=True, lon="0")
    assert civil["solar_term"] == solar["solar_term"]
    assert civil["solar_term"]["term"] == "夏至"
    assert solar["chart"]["yangLing"] is False
    assert solar["chart"]["yangLingBasis"] == "solstice_instant"


@pytest.mark.parametrize("name", ["立春", "立夏", "立秋", "立冬"])
def test_tuyong_is_half_open_18_elapsed_days(name):
    end = next(
        t.moment
        for t in get_solar_terms_for_year(2026, "Asia/Shanghai")
        if t.name == name
    )
    start = end - timedelta(days=18)
    for at, expected in [
        (start - timedelta(microseconds=1), False),
        (start, True),
        (end - timedelta(microseconds=1), True),
        (end, False),
    ]:
        assert (
            solar_term(at.year, at.month, at.day, "Asia/Shanghai", birth_datetime=at)[
                "tuyong"
            ]
            is expected
        )


def test_canping_late_ages_have_real_periods_instead_of_clamping_to_age_90():
    series = liunian_series(
        year_gz="庚午",
        month_branch="寅",
        day_branch="巳",
        hour_branch="午",
        birth_year=1990,
    )
    assert len(series["dayun"]) == 12
    assert series["rows"][90]["dayunRange"] == "91-100"
    assert series["rows"][110]["dayunRange"] == "111-120"
    assert series["rows"][110]["dayunBranch"] != series["rows"][89]["dayunBranch"]


def test_najia_policy_includes_houtian_direct_trigrams_and_is_partial():
    p = dict(zip(("year", "month", "day", "hour"), REFERENCE["heluo"][0]["pillars"]))
    chart = heluo(
        four_pillars=p, gender="男", hour_zhi="辰", birth_year=1924, month_zhi="卯"
    )
    # Isolate the matching operation: 丁巳纳兑，兑仅见于后天中孚，先天姤无兑。
    actual = judge(
        chart, {**p, "year": "丁巳"}, "卯", solar_term_huagong("清明", False)
    )
    assert actual["deSheng"] is True
    assert actual["assessment_status"] == "partial"


def test_invalid_four_pillars_cannot_silently_drop_branch_contributions():
    p = dict(zip(("year", "month", "day", "hour"), REFERENCE["heluo"][0]["pillars"]))
    with pytest.raises(ValueError):
        heluo(
            four_pillars={**p, "hour": "庚丑"},
            gender="男",
            hour_zhi="丑",
            birth_year=1924,
            month_zhi="卯",
        )
    with pytest.raises(ValueError):
        heluo(
            four_pillars=p, gender="男", hour_zhi="巳", birth_year=1924, month_zhi="卯"
        )


def test_same_run_text_selection_and_partial_assessment_are_explicit():
    r = calculate_heluo_analysis(
        date="2000-05-15", time="09:33:00", gender="男", use_true_solar_time=False
    )
    e = r["numerology_evidence"]
    for text in e["selected_texts"]:
        phase = text["phase"]
        assert text["hexagram"] == r["chart"][phase]["name"]
        assert text["text"] == yao_text(text["hexagram"], text["line"])
        assert text["zhouyi_reference"]["verse"]["position"] == text["line"]
        assert text["zhouyi_reference"]["source_wikitext_sha256"]
        assert text["text"]["detail"] in r["snapshot_text"]
    assert r["judge"]["assessment_status"] == "partial"
    assert e["validation_status"]["prediction"] == "not_validated"
    assert "未定" in r["snapshot_text"]
    # Returned quotations cannot mutate the process-wide cached corpus.
    e["selected_texts"][0]["text"]["detail"] = "changed by host"
    again = calculate_heluo_analysis(
        date="2000-05-15", time="09:33:00", gender="男", use_true_solar_time=False
    )
    assert (
        again["numerology_evidence"]["selected_texts"][0]["text"]["detail"]
        != "changed by host"
    )


def test_all_64_heluo_names_and_line_positions_match_the_separate_zhouyi_corpus():
    names = _gua_tables()[0]
    assert len(names) == 64
    for name, trigrams in names.items():
        lines = gua_lines(trigrams["up"], trigrams["low"])
        reference = classical_hexagram("".join(str(bit) for bit in lines))
        assert reference["number"] == _gua_tables()[2][name]
        assert [v["position"] for v in reference["yaoci"]] == [1, 2, 3, 4, 5, 6]
        for pos in range(1, 7):
            assert yao_text(name, pos) is not None


def test_invalid_method_and_unknown_element_do_not_silently_choose_a_school():
    with pytest.raises(ValueError):
        canping(
            year_gz="庚午",
            month_branch="寅",
            day_branch="巳",
            hour_branch="午",
            method="typo",
        )
    with pytest.raises(ValueError):
        compute_number("子", "丑", "unknown")


def test_canping_variants_have_different_traceable_rulesets_and_corpus_statuses():
    args = dict(
        date="1990-06-15", time="09:33:00", gender="男", use_true_solar_time=False
    )
    gu = calculate_canping_analysis(**args)
    ming = calculate_canping_analysis(**args, method="ming")
    assert gu["input_normalized"]["method"] == "gu"
    assert (
        gu["numerology_evidence"]["rulesets"][0]["ruleset_id"]
        != ming["numerology_evidence"]["rulesets"][0]["ruleset_id"]
    )
    # Both selected earth cells now have primary-page witnesses (PDF 99/102).
    assert gu["benming"]["numShun"] == 2773
    assert gu["benming"]["verses"]["textShun"] == "松筠侵日月，星斗見長天。"
    assert ming["benming"]["numShun"] == 3169
    assert ming["benming"]["verses"]["textShun"] == "眾逐虎負嵎，攘臂下車搏。"
    for result in (gu, ming):
        assert (
            result["benming"]["verses"]["statusShun"] == "source_cell_visually_collated"
        )
    assert (
        gu["numerology_evidence"]["validation_status"]["prediction"] == "not_validated"
    )
