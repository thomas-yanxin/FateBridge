"""Printed arithmetic, author terminology and complete current coverage."""

import gzip
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.fengshui.reading import build_natal_reading
from fatebridge.core.fengshui.xuankong import _chart, natal_rules
from fatebridge.services.fengshui import calculate_xuankong_natal
from fatebridge.services.replay_metadata import digest
from fatebridge.validation.fengshui_reading import verify_fengshui_reading
from fatebridge.validation.fengshui_structure import audit_printed_structures
from tests.test_fengshui_fixed_reading import executed, trusted

FOLDER = Path(__file__).parent / "data/fengshui_structure_reading_v1"
REFERENCE = json.loads((FOLDER / "printed-charts.json").read_text())
MOUNTAINS = natal_rules()["mountains"]


def request(example, offset=0):
    angle = next(
        m["center_degrees"] for m in MOUNTAINS if m["name"] == example["facing"]
    )
    return {
        "house": {
            "facing_degrees": (angle + offset) % 360,
            "north_reference": "magnetic",
        },
        "period": {
            "basis": "expert_confirmed",
            "period_number": example["period"],
            "evidence": "原典数字例，非真实住宅",
        },
        "interpretation": {
            "current_period_number": 9,
            "period_evidence": "独立评价九运",
        },
    }


def statements(result, kind):
    return [s for s in result["calculation_reading"]["statements"] if s["kind"] == kind]


def test_new_run_cannot_be_downgraded_using_a_valid_legacy_template_and_rehash():
    result = executed(request(REFERENCE["charts"][0]))
    anchor = trusted(result)
    result["calculation_reading"]["version"] = "1.0.0"
    result["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in result.items() if k != "run_metadata"}
    )
    report = verify_fengshui_reading(result, **anchor)
    assert report["status"] == "rejected"
    assert not report["numeric_structure_coverage_verified"]


def test_missing_natal_does_not_receive_numeric_structure_coverage_credit():
    result = executed(
        {
            "interpretation": {
                "current_period_number": 8,
                "period_evidence": "独立八运",
                "fixed_lingzheng": {},
            }
        }
    )
    report = verify_fengshui_reading(result, **trusted(result))
    assert report["status"] == "verified_served_fixed_reading"
    assert report["numeric_structure_chart_count"] == 0
    assert report["numeric_structure_coverage_verified"] is False


@pytest.mark.parametrize("part", ["pair", "palace", "role"])
def test_incomplete_raw_numeric_context_is_unsupported_rather_than_certified(part):
    result = calculate_xuankong_natal(**request(REFERENCE["charts"][0]))
    structure = result["layers"]["xuankong_natal"]["candidates"][0]["structure"]
    if part == "pair":
        structure["combination_of_ten"].pop()
    elif part == "palace":
        del structure["classical_patterns"]["parental_triples"]["palaces"]["NE"]
    else:
        del structure["classical_patterns"]["ground_comparison"]["roles"]["facing"]
    assert build_natal_reading(result)["status"] == "unsupported_context"


def test_six_independently_transcribed_charts_match162_cells_and_seven_scoped_headings():
    report = audit_printed_structures(REFERENCE)
    assert report["scoped_acceptance_passed"] and not report["differences"]
    assert (
        report["numeric_cells_checked"] == 162 and report["scoped_heading_checks"] == 7
    )
    assert not report["whole_book_conformity_established"]
    assert not report["real_world_prediction_established"]


@pytest.mark.parametrize("example", REFERENCE["charts"], ids=lambda e: e["id"])
def test_printed_charts_keep_full_pattern_reading_with_precise_bound_context(example):
    result = calculate_xuankong_natal(**request(example))
    reading = result["calculation_reading"]
    assert reading["status"] == "rendered" and reading["version"] == "1.2.0"
    assert len(statements(result, "numeric_sum_ten")) == 3
    assert len(statements(result, "parental_palace")) == 9
    assert len(statements(result, "numeric_refrain")) == 2
    assert len(statements(result, "named_refrain")) == 1
    for s in reading["statements"]:
        assert s["target_path"] in reading["basis"]
    chart = result["layers"]["xuankong_natal"]["chart"]
    for s in statements(result, "parental_palace"):
        row = reading["basis"][s["target_path"]]
        direction = s["target_path"].split(".")[-1]
        assert row["ordered_period_mountain_facing"] == [
            chart[role + "_chart"][direction]
            for role in ("period", "mountain", "facing")
        ]
        assert "历史" + str(example["period"]) + "运" in s["text"]


def test_full_ten_is_pair_specific_and_negative_global_does_not_erase_local_ten():
    result = calculate_xuankong_natal(**request(REFERENCE["charts"][0]))
    mountain, facing, _ = statements(result, "numeric_sum_ten")
    assert "历史运星与山星九宫全部同宫合十：符合" in mountain["text"]
    assert "历史运星与向星九宫全部同宫合十：不符合" in facing["text"]
    assert "N:3+7=10" in facing["text"]
    assert "不是异宫对角合十" in mountain["text"]


def test_wang_reverse_example_and_shen_finite_list_counterexample_coexist():
    result = calculate_xuankong_natal(**request(REFERENCE["charts"][3]))
    mountain = next(
        s
        for s in statements(result, "numeric_refrain")
        if s["target_path"].endswith(".mountain")
    )
    named = statements(result, "named_refrain")[0]
    assert "固定地盘全盘对数（反吟数式）：符合" in mountain["text"]
    assert "下卦反伏局名的有限数字对应：不符合" in named["text"]
    assert "名单不覆盖各作者全部反伏用语" in named["text"]


def test_local_period_overlap_retained_separately_from_fixed_ground():
    result = calculate_xuankong_natal(**request({"period": 7, "facing": "酉"}))
    s = next(
        s
        for s in statements(result, "numeric_refrain")
        if s["target_path"].endswith(".facing")
    )
    assert "固定洛书地盘全盘同数（伏吟数式）：不符合" in s["text"]
    assert "历史运盘全盘同数：不符合，同数宫位['NW']" in s["text"]


def test_parental_group_does_not_override_other_negative_relations_or_imply_robbery():
    result = calculate_xuankong_natal(**request(REFERENCE["charts"][4]))
    assert (
        "全局父母三般卦数字条件：符合"
        in statements(result, "parental_summary")[0]["text"]
    )
    assert all(
        "全盘同数（伏吟数式）：不符合" in s["text"]
        and "全盘对数（反吟数式）：不符合" in s["text"]
        for s in statements(result, "numeric_refrain")
    )
    assert "seven_star_robbery" in result["calculation_reading"]["uncovered_topics"]
    replacement = calculate_xuankong_natal(**request(REFERENCE["charts"][4], offset=6))
    assert (
        replacement["layers"]["xuankong_natal"]["chart"]["chart_mode"] == "replacement"
    )
    assert (
        "替卦不适用此段下卦局名名单"
        in statements(replacement, "named_refrain")[0]["text"]
    )
    assert "对应状态未判定" in statements(replacement, "named_refrain")[0]["text"]


def test_complete432_chart_domain_retains_every_pair_palace_role_and_applicability():
    payload = calculate_xuankong_natal(**request(REFERENCE["charts"][0]))
    layer = payload["layers"]["xuankong_natal"]
    layer["interpretation"] = None
    for period in range(1, 10):
        for index in range(24):
            for mode in ("lower", "replacement"):
                chart = _chart(period, (index, mode, "coverage_only_not_source_oracle"))
                layer["candidates"] = [chart]
                layer["chart"] = chart
                original = deepcopy(chart)
                reading = build_natal_reading(payload)
                assert reading["status"] == "rendered"
                counts = {
                    k: sum(s["kind"] == k for s in reading["statements"])
                    for k in (
                        "numeric_sum_ten",
                        "parental_summary",
                        "parental_palace",
                        "numeric_refrain",
                        "named_refrain",
                    )
                }
                assert counts == dict(
                    numeric_sum_ten=3,
                    parental_summary=1,
                    parental_palace=9,
                    numeric_refrain=2,
                    named_refrain=1,
                )
                assert chart == original


@pytest.mark.parametrize(
    "change",
    [
        "omit_negative_ten",
        "omit_parental_palace",
        "swap_ground_target",
        "replace_scope",
        "unknown_version",
    ],
)
def test_forged_complete_receipt_does_not_hide_new_structure_omissions(change):
    result = executed(request(REFERENCE["charts"][0]))
    reading = result["calculation_reading"]
    if change == "omit_negative_ten":
        reading["statements"] = [
            s
            for s in reading["statements"]
            if not (
                s["kind"] == "numeric_sum_ten"
                and "九宫全部同宫合十：不符合" in s["text"]
            )
        ]
    elif change == "omit_parental_palace":
        reading["statements"] = [
            s
            for s in reading["statements"]
            if not (s["kind"] == "parental_palace" and s["target_path"].endswith(".NE"))
        ]
    elif change == "swap_ground_target":
        next(s for s in reading["statements"] if s["kind"] == "numeric_refrain")[
            "target_path"
        ] = "layers.xuankong_natal.candidates.0.period_chart"
    elif change == "replace_scope":
        reading["uncovered_topics"].remove("seven_star_robbery")
    else:
        reading["version"] = "999.0.0"
    reading["text"] = "\n".join(s["text"] for s in reading["statements"])
    result["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in result.items() if k != "run_metadata"}
    )
    report = verify_fengshui_reading(result, **trusted(result))
    assert (
        report["status"] == "rejected"
        and not report["numeric_structure_coverage_verified"]
    )


@pytest.mark.parametrize(
    "corruption",
    [
        "drop_example",
        "drop_heading",
        "drop_row",
        "duplicate_case",
        "valid_wrong_number",
    ],
)
def test_source_audit_preserves_complete_scope_and_reports_real_numeric_disagreement(
    corruption,
):
    reference = deepcopy(REFERENCE)
    if corruption == "drop_example":
        reference["charts"].pop()
    elif corruption == "drop_heading":
        del reference["charts"][0]["expected_sum_ten_pair"]
    elif corruption == "drop_row":
        reference["charts"][0]["rows"].pop()
    elif corruption == "duplicate_case":
        reference["charts"][0].update(
            {k: reference["charts"][1][k] for k in ("period", "facing")}
        )
    else:
        rows = reference["charts"][0]["rows"]
        rows[0][0], rows[1][0] = rows[1][0], rows[0][0]
        report = audit_printed_structures(reference)
        assert (
            not report["scoped_acceptance_passed"] and len(report["differences"]) == 2
        )
        return
    with pytest.raises(ValueError):
        audit_printed_structures(reference)
