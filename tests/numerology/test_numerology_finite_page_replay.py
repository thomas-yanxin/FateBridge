"""Finite original-page readings without unpublished scan dependencies."""

import json
from collections import Counter
from pathlib import Path

import pytest

from fatebridge.core.canping import compute_number
from fatebridge.core.canping_texts import COLLATION_PATH, lookup_record
from fatebridge.core.heluo import calculate
from fatebridge.core.heluo_timing import daily_template, monthly_sequence
from fatebridge.core.heluo_yuantang import placement
from tests.support.transports import AS_OF, SPECS
from tests.support.transports import rest as shared_rest
from tests.support.transports import surface_calls

rest = shared_rest

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/canping_texts_v1/finite-page-replay.json"
    ).read_text(encoding="utf-8")
)


def test_reachable_columns_keep_the_original_missing_and_uncertain_denominators():
    statuses = Counter()
    for element in "水火木金土":
        numbers = {
            compute_number(day_branch, hour_branch, element)[direction]
            for day_branch in "子丑寅卯辰巳午未申酉戌亥"
            for hour_branch in "子丑寅卯辰巳午未申酉戌亥"
            for direction in ("numShun", "numNi")
        }
        assert len(numbers) == 108
        for number in numbers:
            for kind in ("male", "female", "luck"):
                record = lookup_record(element, number, kind)
                status = record["selection"]["cell_status"]
                statuses[status] += 1
                if status == "row_absent_in_local_corpus":
                    assert record["text"] == ""
                    assert "source_pdf_page" not in record["selection"]
                else:
                    pass
    assert sum(statuses.values()) == REFERENCE["reachable_cells"] == 1620
    assert statuses == REFERENCE["status_counts"]


def test_consecutive_water_pages_do_not_turn_unlisted_numbers_into_missing_pages():
    collation = json.loads(COLLATION_PATH.read_bytes())
    assert collation["source_pdf_sha256"] == REFERENCE["source_pdf_sha256"]
    water_rows = [row for row in collation["entries"] if row["element"] == "水"]
    assert len(water_rows) == 78
    for page in REFERENCE["water_pages"]:
        page_rows = [row for row in water_rows if row["pdf_page"] == page["pdf_page"]]
        assert len(page_rows) == page["row_count"]
        assert page_rows[0]["number"] == page["first_number"]
        assert page_rows[-1]["number"] == page["last_number"]
    for cell in REFERENCE["literal_cells"]:
        record = lookup_record(cell["element"], cell["number"], cell["kind"])
        assert record["text"] == cell["text"]
        assert record["selection"]["source_pdf_page"] == cell["pdf_page"]
    assert lookup_record("水", 3231, "luck")["selection"]["cell_status"] == (
        "row_absent_in_local_corpus"
    )


def test_xiaochu_borrows_after_repeating_its_only_yin_line():
    """NLC PDF 27, printed leaf 15: 午未四、申初、酉二、戌三、亥五."""
    positions = [
        placement([1, 1, 1, 0, 1, 1], hour_branch, True, None)["selected_pos"]
        for hour_branch in "午未申酉戌亥"
    ]
    assert positions == [4, 4, 1, 2, 3, 5]


@pytest.mark.parametrize(
    "yang_half,expected_positions",
    [(True, [6, 5, 4, 6, 5, 4]), (False, [1, 2, 3, 1, 2, 3])],
)
def test_qian_female_uses_the_printed_solstice_direction(
    yang_half: bool, expected_positions: list[int]
):
    """NLC PDF 30–31: 冬至後夏至前自上行下; 夏至後冬至前照男例."""
    assert [
        placement([1] * 6, hour_branch, False, yang_half)["selected_pos"]
        for hour_branch in "子丑寅卯辰巳"
    ] == expected_positions
    with pytest.raises(ValueError, match="至点阴阳令"):
        placement([1] * 6, "子", False, None)


@pytest.mark.parametrize(
    "pillars,cycle_year,yang_half,totals,xian_name,xian_position,hou_name,hou_position",
    [
        (
            ["庚午", "甲申", "丙申", "丁酉"],
            1990,
            False,
            (44, 28),
            "火山旅",
            1,
            "離為火",
            4,
        ),
        (
            ["乙亥", "乙酉", "戊寅", "庚申"],
            1995,
            False,
            (26, 26),
            "天水訟",
            1,
            "澤天夬",
            4,
        ),
        (
            ["丙寅", "庚子", "丙子", "己亥"],
            1986,
            False,
            (18, 42),
            "山地剝",
            6,
            "坤為地",
            3,
        ),
        (
            ["戊子", "甲子", "癸巳", "癸亥"],
            2008,
            True,
            (11, 30),
            "水雷屯",
            5,
            "雷地豫",
            2,
        ),
    ],
    ids=["gengwu_zhao", "yihai_bailu", "bingyin_kai_xi", "wuzi_dongzhi"],
)
def test_four_original_examples_keep_arithmetic_separate_from_historical_dates(
    pillars: list[str],
    cycle_year: int,
    yang_half: bool,
    totals: tuple[int, int],
    xian_name: str,
    xian_position: int,
    hou_name: str,
    hou_position: int,
) -> None:
    """NLC PDF 82–85; cycle representatives do not convert source birth dates."""
    result = calculate(
        four_pillars=dict(zip(("year", "month", "day", "hour"), pillars)),
        gender="男",
        birth_year=cycle_year,
        month_zhi=pillars[1][1],
        hour_zhi=pillars[3][1],
        month_yang_ling=yang_half,
    )
    assert (result["tian"], result["di"]) == totals
    assert (result["xian"]["name"], result["xian"]["yuan"]) == (
        xian_name,
        xian_position,
    )
    assert (result["hou"]["name"], result["hou"]["yuan"]) == (hou_name, hou_position)
    assert result["yangLingBasis"] == "explicit_half_year"
    if cycle_year == 2008:
        assert result["di"] != 33
    else:
        pass


def test_guan_months_and_jiji_days_remain_nominal_sequences():
    """NLC PDF 39–40: twelve printed months; last twelve days rule-derived."""
    months = monthly_sequence([0, 0, 0, 0, 1, 1], 6)
    assert [row["gua"] for row in months] == [
        "風雷益",
        "天雷無妄",
        "風澤中孚",
        "山澤損",
        "風天小畜",
        "水天需",
        "乾為天",
        "天風姤",
        "火天大有",
        "離為火",
        "雷天大壯",
        "雷澤歸妹",
    ]
    assert [row["pos"] for row in months] == [1, 4, 2, 5, 3, 6, 4, 1, 5, 2, 6, 3]
    days = daily_template([1, 0, 1, 0, 1, 0], 2)
    assert [row["gua"] for row in days] == [
        name
        for name in ("水雷屯", "澤火革", "地火明夷", "風火家人", "水山蹇")
        for _ in range(6)
    ]
    assert [row["pos"] for row in days] == [1, 2, 3, 4, 5, 6] * 5
    assert all("start_at" not in row and "end_at" not in row for row in months + days)


@pytest.mark.parametrize("tool_name", ["canping", "heluo"])
def test_finite_page_facts_survive_actual_three_surface_projection(
    tool_name, surface_calls
):
    payload = dict(
        date="1990-06-15",
        time="09:33:00",
        zone="Asia/Shanghai",
        gender="男",
        use_true_solar_time=False,
    )
    if tool_name == "heluo":
        payload.update(analysis_year=2028, month_index=3, day_index=10)
        fields = [
            "chart.yuantang_derivation",
            "chart.xian",
            "chart.hou",
            "heluo_timing.selected_annual",
            "heluo_timing.selected_month",
            "heluo_timing.selected_day",
            "heluo_timing.calendar_policy",
        ]
    else:
        payload.update(date="1983-06-17", time="00:30:00")
        fields = ["benming", "numerology_evidence.selected_texts"]
    response, protocol, code, local = surface_calls(
        SPECS[tool_name],
        payload,
        rest_as_of=AS_OF,
        projection=dict(
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
            response_char_limit=0,
        ),
    )
    assert response.status_code == 200, response.text
    assert not protocol.is_error, protocol.content
    assert code == 0, local
    bodies = [response.json(), protocol.structured_content, local]
    for body in bodies:
        body.pop("run_metadata")
    assert bodies[0] == bodies[1] == bodies[2]
    if tool_name == "heluo":
        chart = bodies[0]["chart"]
        derivation = chart["yuantang_derivation"]
        assert derivation["ruleset_id"] == "heluo_yuantang_nlc_v1"
        assert derivation["placement"]["selected_pos"] == chart["xian"]["yuan"] == 5
        assert derivation["placement"]["slot_positions"] == [2, 3, 4, 6, 1, 5]
        assert derivation["placement"]["source_pdf_pages"] == [29]
        assert (
            derivation["houtian_transform"]["resulting_yuan"]
            == chart["hou"]["yuan"]
            == 2
        )
        assert (
            derivation["half_year"]["birth_instant_utc"] == "1990-06-15T00:33:00+00:00"
        )
        assert derivation["half_year"]["basis"] == "solstice_instant"
        timing = bodies[0]["heluo_timing"]
        assert timing["selected_month"]["month_index"] == 3
        assert timing["selected_day"]["day_index"] == 10
        assert (
            timing["calendar_policy"]["month"]
            == "ordinal_classical_month_1_to_12; not_Gregorian_month"
        )
        assert (
            timing["calendar_policy"]["day"]
            == "ordinal_30_slot_template; not_Gregorian_or_lunar_day"
        )
        assert "start_at" not in timing["selected_day"]
    else:
        selected = bodies[0]["benming"]["verses"]
        for direction in ("Shun", "Ni"):
            selection = selected[f"selection{direction}"]
            assert selection["number"] == selected[f"num{direction}"] == 3330
            assert selection["kind"] == "male"
            assert selection["column"] == "upper_male"
            assert selection["source_pdf_page"] == 65
            assert selected[f"text{direction}"] == REFERENCE["literal_cells"][0]["text"]
        evidence = bodies[0]["numerology_evidence"]["selected_texts"]
        assert len(evidence) == 1
        assert evidence[0]["phase"] == "benming"
        assert evidence[0]["element"] == "水"
        assert evidence[0]["kind"] == "male"
        assert evidence[0]["verses"] == selected
