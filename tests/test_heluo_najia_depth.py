"""Independent scanned assignments, positional counterexamples and fidelity."""

import copy
import hashlib
import itertools
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.heluo import calculate, hexagram_najia, judge, solar_term
from fatebridge.core.heluo_timing import selected_timing_snapshot
from fatebridge.core.output_numerology import HeluoJudge
from fatebridge.services.divination import calculate_heluo_analysis

ROOT = Path(__file__).parent / "fixtures/numerology_nlc_v1"
REFERENCE = json.loads((ROOT / "najia-reference.json").read_text())
PILLARS = dict(year="甲子", month="丁卯", day="庚申", hour="庚辰")


def example_chart():
    return calculate(
        four_pillars=PILLARS,
        gender="男",
        hour_zhi="辰",
        birth_year=1924,
        month_zhi="卯",
    )


def test_source_witnesses_have_the_declared_identity():
    manifest = json.loads((ROOT / "najia-manifest.json").read_text())
    assert REFERENCE["source_pdf_sha256"] == manifest["pdf_sha256"]
    assert {i["pdf_page"] for i in manifest["images"]} == {119, 122, 124, 136, 139}
    for item in manifest["images"]:
        assert (
            hashlib.sha256((ROOT / item["file"]).read_bytes()).hexdigest()
            == item["sha256"]
        )


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: c["gua"])
def test_original_direct_and_borrowed_najia(case):
    rows = hexagram_najia(case["lines"])
    assert [r["pos"] for r in rows] == [1, 2, 3, 4, 5, 6]
    assert [r["direct"] for r in rows] == case["direct"]
    assert [r["borrowed"] for r in rows] == case["borrowed"]


def test_jiazi_is_not_in_gou_or_zhongfu_just_because_qian_is_present():
    # 姤只有外乾的壬午申戌/借甲午申戌，不能混入内乾甲子寅辰。
    chart = example_chart()
    actual = judge(chart, PILLARS, "卯")
    assert (chart["xian"]["name"], chart["hou"]["name"]) == ("天風姤", "風澤中孚")
    assert actual["deSheng"] is False
    assert all(not phase["matches"] for phase in actual["najia"])


def test_borrowed_renzi_is_seen_only_in_inner_qian():
    # 借用壬子在内乾初爻；旧乾表只有外乾的壬午申戌，原会漏判。
    chart = example_chart()
    chart["xian"].update(name="風天小畜", lines=[1, 1, 1, 0, 1, 1], up="巽", low="乾")
    actual = judge(chart, {**PILLARS, "year": "壬子"}, "卯")
    assert actual["deSheng"] is True
    assert actual["najia"][0]["matches"] == [{"pos": 1, "kind": "borrowed"}]
    assert not actual["najia"][1]["matches"]


def test_outer_xun_does_not_receive_inner_xun_xinyou():
    chart = example_chart()
    chart["xian"].update(name="風天小畜", lines=[1, 1, 1, 0, 1, 1], up="巽", low="乾")
    actual = judge(chart, {**PILLARS, "year": "辛酉"}, "卯")
    assert actual["deSheng"] is False


def test_houtian_receives_a_real_lower_dui_assignment():
    actual = judge(example_chart(), {**PILLARS, "year": "丁巳"}, "卯")
    assert not actual["najia"][0]["matches"]
    assert actual["najia"][1]["matches"] == [{"pos": 1, "kind": "direct"}]
    assert actual["deSheng"] is True


def test_six_actual_positions_and_no_input_mutation_for_all_hexagrams():
    # Structural invariants only, not 64 independent original examples.
    for bits in itertools.product((0, 1), repeat=6):
        lines = list(bits)
        before = copy.deepcopy(lines)
        rows = hexagram_najia(lines)
        assert len(rows) == 6 and lines == before
        for row in rows:
            assert len(row["borrowed"]) == (1 if row["trigram"] in {"乾", "坤"} else 0)
            for borrowed in row["borrowed"]:
                assert borrowed[1] == row["direct"][1]


@pytest.mark.parametrize("lines", [[True] * 6, [1] * 5, [0, 1, 0, 2, 1, 0]])
def test_invalid_lines_are_rejected(lines):
    with pytest.raises(ValueError):
        hexagram_najia(lines)


@pytest.mark.parametrize(
    "payload",
    [
        {"deSheng": "true"},
        {"najia": [{"present": "false"}]},
        {"najia": [{"lines": [{"pos": True}]}]},
    ],
)
def test_corrupt_najia_facts_are_rejected_by_output_contract(payload):
    with pytest.raises(ValidationError):
        HeluoJudge.model_validate(payload)


def test_selected_sequence_snapshot_uses_day_position_instead_of_changed_position():
    result = calculate_heluo_analysis(
        date="1990-06-15",
        time="09:33:00",
        zone="Asia/Shanghai",
        gender="男",
        use_true_solar_time=False,
        analysis_year=2028,
        month_index=3,
        day_index=10,
    )
    timing = result["heluo_timing"]
    day = timing["selected_day"]
    assert day["pos"] == 4 and day["changed_pos"] == 1
    selected = selected_timing_snapshot(timing)
    assert "年标签2028" in selected and "月序3" in selected
    assert "日定式序10：火山旅，用爻九四" in selected
    assert "日定式序10：火山旅，用爻初六" not in selected
    assert selected in result["snapshot_text"]
    assert "尚未桥接实际日期" in selected


def test_hko_three_year_solstices_agree_in_different_timezones():
    reference = json.loads((ROOT.parent / "calendar_hko_v1/reference.json").read_text())
    for case in reference["cases"]:
        if case["term"] not in {"冬至", "夏至", "春分", "秋分"}:
            continue
        instant = datetime.fromisoformat(case["at"])
        before = instant - timedelta(minutes=2)
        after = instant + timedelta(minutes=2)
        # These are external minute brackets, not program-generated crossings.
        for zone in ("Asia/Shanghai", "America/New_York", "+00:00"):
            a = solar_term(
                before.year, before.month, before.day, zone, birth_datetime=before
            )
            b = solar_term(
                after.year, after.month, after.day, zone, birth_datetime=after
            )
            assert a["term"] != case["term"] and b["term"] == case["term"]
            if case["term"] in {"冬至", "夏至"}:
                assert a["yang_ling"] is not b["yang_ling"]
                assert b["yang_ling"] == (case["term"] == "冬至")
            else:
                assert a["yang_ling"] is b["yang_ling"]
            assert (
                b["quarter"]
                == {"冬至": "坎", "春分": "震", "夏至": "離", "秋分": "兌"}[
                    case["term"]
                ]
            )
