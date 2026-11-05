"""Directed Nayin relations and source qualifiers, independent of port parity."""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.heluo import judge
from fatebridge.core.heluo_body import ELEMENTS, body_evidence, element_relation
from fatebridge.core.output_numerology import HeluoJudge
from tests.numerology.test_heluo_month_depth import chart_for
from tests.numerology.test_heluo_najia_depth import PILLARS

ROOT = Path(__file__).parents[1] / "fixtures/numerology_nlc_v1"
REFERENCE = json.loads((ROOT / "body-reference.json").read_text())


def test_two_edition_witnesses_keep_identity_and_do_not_claim_second_reviewer():
    manifest = json.loads((ROOT / "body-manifest.json").read_text())
    assert len(manifest["images"]) == 8
    assert "independent_second_review_pending" in manifest["review_status"]
    for item in manifest["images"]:
        assert (
            hashlib.sha256((ROOT / item["file"]).read_bytes()).hexdigest()
            == item["sha256"]
        )


@pytest.mark.parametrize(
    "natal,trigram,expected",
    [
        (e, t, r)
        for e, rs in REFERENCE["rule_derived_relation_grid"].items()
        for t, r in zip(REFERENCE["trigram_order"], rs)
    ],
)
def test_independent_forty_cell_directed_grid(natal, trigram, expected):
    assert element_relation(ELEMENTS[trigram], natal) == expected


@pytest.mark.parametrize("case", REFERENCE["generating_clause_combinations"])
def test_four_derived_combinations_from_one_water_nayin_clause(case):
    chart = chart_for(
        case["trigram"] + "為" + ("天" if case["trigram"] == "乾" else "澤")
    )
    result = judge(chart, {**PILLARS, "year": case["year"]}, "卯")["deTi"]
    assert result["nayin"] == "大溪水"
    main_bodies = [r for r in result["bodies"] if r["kind"] in {"lower", "upper"}]
    assert len(main_bodies) == 4
    assert {r["relation"] for r in main_bodies} == {case["relation"]}
    assert result["present"] is None and result["complete_assessment"] is False


def test_existing_yuanqi_cannot_be_ignored_to_activate_page_51():
    chart = chart_for("乾為天")
    jia = judge(chart, {**PILLARS, "year": "甲寅"}, "卯")["deTi"]
    yi = judge(chart, {**PILLARS, "year": "乙卯"}, "卯")["deTi"]
    assert jia["generating_qi"]["relation_present"] is True
    assert jia["yuanqi_absent"] is False
    assert jia["generating_qi"]["condition_match"] is False
    assert yi["yuanqi_absent"] is True
    assert yi["generating_qi"]["condition_match"] is True


def test_reverse_generation_does_not_satisfy_the_directed_page_51_rule():
    # 丙寅火纳音，纯坤土；火生土是第87页方向，不能倒称土生火。
    actual = judge(chart_for("坤為地"), {**PILLARS, "year": "丙寅"}, "卯")["deTi"]
    assert actual["nayin_element"] == "火" and actual["yuanqi_absent"] is True
    assert actual["generating_qi"]["relation_present"] is False
    assert actual["generating_qi"]["condition_match"] is False
    assert actual["mutual_generation"]["relation_present"] is True
    assert len(actual["mutual_generation"]["nayin_generates_body_ids"]) == 8


def test_dingyou_xiaoguo_original_nuclear_example_and_actual_positions():
    case = REFERENCE["direct_nuclear_reading"]
    actual = judge(chart_for(case["gua"]), {**PILLARS, "year": case["year"]}, "卯")[
        "deTi"
    ]
    rows = actual["bodies"][:4]
    assert [r["line_positions"] for r in rows] == [
        [1, 2, 3],
        [2, 3, 4],
        [3, 4, 5],
        [4, 5, 6],
    ]
    assert [r["trigram"] for r in rows[1:3]] == case["nuclear_trigrams"]
    assert not rows[0]["yuanqi_kinds"] and not rows[3]["yuanqi_kinds"]
    assert rows[2]["yuanqi_kinds"] == ["tian", "di"]
    assert actual["yuanqi_absent"] is False


def test_day_stem_changes_do_not_change_year_nayin_body_relations():
    chart = chart_for("坎為水")
    a = judge(chart, {**PILLARS, "year": "丙寅", "day": "戊子"}, "卯")
    b = judge(chart, {**PILLARS, "year": "丙寅", "day": "己丑"}, "卯")
    assert a["deTi"] == b["deTi"]
    assert [r["relation"] for r in a["deTi"]["bodies"][:4]] == [
        "body_controls_nayin",
        "body_generates_nayin",
        "nayin_generates_body",
        "body_controls_nayin",
    ]
    assert a["deTi"]["present"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {"deTi": {"present": True}},
        {"deTi": {"complete_assessment": True}},
        {"deTi": {"yuanqi_absent": "false"}},
        {"deTi": {"generating_qi": {"condition_match": "true"}}},
        {"deTi": {"generating_qi": {"direction": "nayin_generates_body"}}},
        {"deTi": {"bodies": [{"line_positions": [True]}]}},
    ],
)
def test_output_contract_rejects_changed_meanings_and_wrong_fact_types(payload):
    with pytest.raises(ValidationError):
        HeluoJudge.model_validate(payload)


@pytest.mark.parametrize("year", [None, "", "甲", "甲丑", False])
def test_nayin_input_is_never_guessed(year):
    with pytest.raises(ValueError):
        body_evidence(year, {}, {"tian": "乾", "di": "坤"})
