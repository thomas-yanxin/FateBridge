"""Named primary Youyuan clause, actual phase facts and source coherence."""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.core.heluo_lines as lines
from fatebridge.core.heluo import _ying, judge
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.core.output_numerology import HeluoLineConditionRow, HeluoSourceYouyuan
from fatebridge.utils.errors import NumerologySourceError
from tests.numerology.test_heluo_month_depth import chart_for
from tests.numerology.test_heluo_najia_depth import PILLARS

ROOT = Path(__file__).parents[1] / "fixtures/heluo_support_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text())


@pytest.mark.parametrize("case", REFERENCE["derived_probes"])
def test_named_yin_to_yang_clause_is_distinct_from_generic_opposition(case):
    chart = chart_for(case["gua"])
    assert chart["xian"]["lines"] == case["lines"]
    chart["xian"]["yuan"] = case["pos"]
    chart["hou"]["yuan"] = case["responding_pos"]
    result = judge(chart, PILLARS, "卯")
    first, second = result["line_conditions"]["phases"]
    aid = first["source_youyuan"]
    assert aid["selected_pos"] == case["pos"]
    assert aid["corresponding_pos"] == case["responding_pos"] == _ying(case["pos"])
    assert (
        aid["selected_yang"],
        aid["corresponding_yang"],
        aid["polarity_opposed"],
        aid["clause_match"],
    ) == (
        case["selected_yang"],
        case["responding_yang"],
        case["opposed"],
        case["clause_match"],
    )
    assert result["yuanTang"]["youYing"] is case["opposed"]
    assert "xian_selected" in result["yuanTang"]["youYing_policy"]
    assert second["source_youyuan"]["selected_pos"] == case["responding_pos"]
    assert second["source_youyuan"]["selected_yang"] is case["responding_yang"]
    assert second["source_youyuan"]["clause_match"] is (
        case["responding_yang"] is False and case["selected_yang"] is True
    )
    HeluoLineConditionRow.model_validate(first)


@pytest.mark.parametrize("pair", REFERENCE["source_correspondence_pairs"])
def test_all_six_existing_response_positions_preserve_direction_and_actual_bits(pair):
    for selected, other in [pair, pair[::-1]]:
        for a, b in [(0, 0), (0, 1), (1, 0), (1, 1)]:
            chart = chart_for("坤為地")
            chart["xian"]["lines"][selected - 1] = a
            chart["xian"]["lines"][other - 1] = b
            chart["xian"]["yuan"] = selected
            aid = lines.line_conditions(chart)["phases"][0]["source_youyuan"]
            assert aid["corresponding_pos"] == other
            assert aid["clause_match"] is (a == 0 and b == 1)
            assert aid["polarity_opposed"] is (a != b)


def test_yin_line_reading_is_not_replaced_with_even_seat_or_other_phase():
    chart = chart_for("雷地豫")
    chart["xian"]["yuan"] = 1  # odd seat, actual yin, corresponding yang
    chart["hou"]["lines"] = [1, 1, 1, 1, 1, 1]
    chart["hou"]["name"] = "乾為天"
    chart["hou"]["yuan"] = 2  # even seat, actual yang, corresponding yang
    first, second = lines.line_conditions(chart)["phases"]
    assert first["source_youyuan"]["clause_match"] is True
    assert second["source_youyuan"]["clause_match"] is False
    chart["yangLing"] = not chart["yangLing"]
    assert lines.line_conditions(chart)["phases"] == [first, second]


def test_public_evidence_trace_and_snapshot_keep_the_same_phase_without_negative_omen():
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
        if r["rule_id"] == lines.RULESET_ID
    )
    assert evidence == trace
    assert [r["source_youyuan"]["clause_match"] for r in evidence["phases"]] == [
        True,
        False,
    ]
    assert (
        "先天有援原句（主本阴爻读法）：元堂5位阴，应爻2位阳；阴元堂、阳应爻式匹配。"
        in result["snapshot_text"]
    )
    assert (
        "后天有援原句（主本阴爻读法）：元堂2位阳，应爻5位阳；阴元堂、阳应爻式未匹配。"
        in result["snapshot_text"]
    )
    assert "先天元堂与应爻阴阳相异（非十体有援总判）" in result["snapshot_text"]
    assert (
        "无援"
        not in result["snapshot_text"]
        .split("[爻位条文条件]", 1)[1]
        .split("[卦属月", 1)[0]
    )
    assert (
        evidence["complete_assessment"] is False
        and evidence["ten_condition_score"] is None
    )
    evidence["phases"][0]["source_youyuan"]["clause_match"] = False
    assert trace["phases"][0]["source_youyuan"]["clause_match"] is True


@pytest.mark.parametrize(
    "change",
    [
        {"corresponding_pos": 6},
        {"corresponding_yang": False},
        {"selected_pos": 4},
        {"selected_yang": True},
        {"clause_match": False},
        {"polarity_opposed": False},
        {"required_selected_yang": True},
        {"required_corresponding_yang": False},
        {"clause_match": "true"},
    ],
)
def test_contract_rejects_wrong_response_wrong_bits_and_wrong_clause(change):
    chart = chart_for("水地比")
    chart["xian"]["yuan"] = 2
    row = lines.line_conditions(chart)["phases"][0]
    row["source_youyuan"].update(change)
    with pytest.raises(ValidationError):
        HeluoLineConditionRow.model_validate(row)


def test_projected_known_fields_are_valid_without_inventing_missing_facts():
    r = HeluoSourceYouyuan.model_validate(
        {"corresponding_pos": 5, "clause_match": True}
    )
    assert r.selected_yang is None and r.corresponding_yang is None
    assert r.clause_match is True


@pytest.mark.parametrize(
    "change",
    [
        {"required_selected_yang": True},
        {"required_corresponding_yang": False},
        {"required_selected_yang": 0},
        {"note": "元堂阳爻亦有援"},
    ],
)
def test_conflicting_source_conditions_are_source_failures_not_birth_input_errors(
    tmp_path, monkeypatch, change
):
    data = json.loads(lines.SOURCE_PATH.read_text())
    data["clauses"]["support"].update(change)
    path = tmp_path / "source.json"
    path.write_text(json.dumps(data, ensure_ascii=False))
    lines._source.cache_clear()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(lines, "SOURCE_PATH", path)
            with pytest.raises(NumerologySourceError):
                lines.line_conditions(chart_for("水地比"))
    finally:
        lines._source.cache_clear()


def test_source_witnesses_original_references_and_variant_wording_remain_separate():
    for w in REFERENCE["witnesses"]:
        assert (
            hashlib.sha256((ROOT / w["file"]).read_bytes()).hexdigest() == w["sha256"]
        )
    for path, digest in REFERENCE["prior_fixture_hashes"].items():
        assert (
            hashlib.sha256((ROOT.parents[2] / path).read_bytes()).hexdigest() == digest
        )
    source = lines.line_conditions(chart_for("水地比"))
    clause = source["literal_clauses"]["support"]
    assert clause["note"] == REFERENCE["readings"]["primary_note"]
    assert clause["counterpart_note"] == REFERENCE["readings"]["counterpart_note"]
    assert source["version"] == "1.1.0"
    assert REFERENCE["new_literal_clauses"] == 1
    assert (
        REFERENCE["new_source_pages"]
        == REFERENCE["new_original_births"]
        == REFERENCE["independent_second_reviews"]
        == 0
    )
