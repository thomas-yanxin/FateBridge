"""Named line-position clauses, distinct from generic parity and full omens."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.heluo import judge
from fatebridge.core.heluo_lines import RULESET_ID, SOURCE_PATH, line_conditions
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.core.output_numerology import HeluoJudge
from tests.test_heluo_month_depth import chart_for
from tests.test_heluo_najia_depth import PILLARS

ROOT = Path(__file__).parent / "fixtures/heluo_line_rules_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text())


@pytest.mark.parametrize("case", REFERENCE["named_zhongzong_illustrations"])
def test_named_original_zhongzong_illustrations_use_the_actual_selected_line(case):
    chart = chart_for(case["gua"])
    assert chart["xian"]["lines"] == case["lines"]
    chart["xian"]["yuan"] = case["minority_pos"]
    chart["hou"]["yuan"] = next(p for p in range(1, 7) if p != case["minority_pos"])
    evidence = judge(chart, PILLARS, "卯")["line_conditions"]
    xian, hou = evidence["phases"]
    assert xian["zhongzong"]["match"] is True
    assert hou["zhongzong"]["match"] is False
    assert xian["zhongzong"]["minority_pos"] == case["minority_pos"]
    assert evidence["complete_assessment"] is False


@pytest.mark.parametrize("case", REFERENCE["derived_pattern_cases"])
def test_twelve_formula_arrangements_include_actual_line_selection(case):
    chart = chart_for(case["gua"])
    assert chart["xian"]["lines"] == case["lines"]
    for pos in range(1, 7):
        chart["xian"]["yuan"] = pos
        row = line_conditions(chart)["phases"][0]
        assert row["zhongzong"]["match"] is (pos == case["minority_pos"])
        assert row["zhongzong"]["minority_pos"] == case["minority_pos"]


@pytest.mark.parametrize(
    "pos,order", list(enumerate(REFERENCE["position_order"], start=1))
)
def test_literal_position_order_is_distinct_from_generic_parity(pos, order):
    chart = chart_for("坤為地")
    chart["xian"]["yuan"] = pos
    result = judge(chart, PILLARS, "卯")
    row = result["line_conditions"]["phases"][0]
    assert row["position_preference_order"] == order
    assert row["ruler_minister_seat"]["match"] is (pos in (2, 5))
    assert result["yuanTang"]["dangWei"] is (pos % 2 == 0)
    assert result["yuanTang"]["position_polarity_match"] is (pos % 2 == 0)
    assert result["yuanTang"]["dangWei_policy"].endswith("not_source_dangwei")


@pytest.mark.parametrize("gua", ["乾為天", "坤為地", "地天泰", "天地否", "風地觀"])
def test_pure_balanced_and_two_minority_lines_do_not_become_zhongzong(gua):
    evidence = line_conditions(chart_for(gua))
    for row in evidence["phases"]:
        assert row["zhongzong"]["minority_pos"] is None
        assert row["zhongzong"]["minority_polarity"] is None
        assert row["zhongzong"]["match"] is False
    assert evidence["ten_condition_score"] is None


def test_half_year_or_month_branch_cannot_supply_an_unverified_yinyue_definition():
    a = chart_for("地水師")
    a["xian"]["yuan"] = 2
    a["yangLing"] = True
    b = copy.deepcopy(a)
    b["yangLing"] = False
    positive = judge(a, PILLARS, "子")
    negative = judge(b, PILLARS, "午")
    assert positive["line_conditions"] == negative["line_conditions"]
    source = positive["line_conditions"]["source_dangwei"]
    assert source["match"] is source["month_polarity"] is None
    assert source["line_index_parity_substituted"] is False
    assert source["solstice_half_year_substituted"] is False


def test_loaded_source_hash_and_each_whole_page_witness_are_retained():
    for page in REFERENCE["images"]:
        assert (
            hashlib.sha256((ROOT / page["file"]).read_bytes()).hexdigest()
            == page["sha256"]
        )
    actual = line_conditions(chart_for("地雷復"))
    assert {
        k: actual["literal_clauses"][k] for k in REFERENCE["literal_clauses"]
    } == REFERENCE["literal_clauses"]
    assert (
        actual["collation_sha256"]
        == hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
    )
    assert actual["source_pdf_sha256"] == REFERENCE["source_pdf_sha256"]
    assert "independent_second_review_pending" in actual["review_status"]
    assert len(REFERENCE["derived_pattern_cases"]) == 12
    assert len(REFERENCE["named_zhongzong_illustrations"]) == 3
    assert REFERENCE["new_complete_classical_horoscopes"] == 0
    actual["literal_clauses"]["zhongzong"]["note"] = "changed"
    assert {
        k: line_conditions(chart_for("地雷復"))["literal_clauses"][k]
        for k in REFERENCE["literal_clauses"]
    } == REFERENCE["literal_clauses"]


def test_same_run_trace_snapshot_and_selected_phase_agree():
    result = build_heluo_result(
        date="1990-06-15",
        time="09:33",
        zone="Asia/Shanghai",
        gender="男",
        use_true_solar_time=False,
    )
    evidence = result["judge"]["line_conditions"]
    trace = next(
        r["facts"]
        for r in result["numerology_evidence"]["rule_trace"]
        if r["rule_id"] == RULESET_ID
    )
    assert evidence == trace
    for row in evidence["phases"]:
        phase = result["chart"][row["phase"]]
        assert (row["gua"], row["lines"], row["pos"]) == (
            phase["name"],
            phase["lines"],
            phase["yuan"],
        )
    HeluoJudge.model_validate(result["judge"])
    assert "[爻位条文条件]" in result["snapshot_text"]
    assert "元堂：当位" not in result["snapshot_text"]
    assert "元堂：不当位" not in result["snapshot_text"]
    assert "位序阴阳" in result["snapshot_text"]
    assert "不推出反面断语" in result["snapshot_text"]
    evidence["phases"][0]["pos"] = 6
    assert trace["phases"][0]["pos"] == result["chart"]["xian"]["yuan"]


@pytest.mark.parametrize(
    "invalid",
    [
        {"complete_assessment": True},
        {"ten_condition_score": 100},
        {"source_dangwei": {"match": True}},
        {"source_dangwei": {"month_polarity": "yin"}},
        {"source_dangwei": {"solstice_half_year_substituted": True}},
        {"phases": [{"pos": True}]},
        {"phases": [{"zhongzong": {"match": "false"}}]},
    ],
)
def test_contract_does_not_certify_unknown_conditions_or_coerce_facts(invalid):
    with pytest.raises(ValidationError):
        HeluoJudge.model_validate({"line_conditions": invalid})
