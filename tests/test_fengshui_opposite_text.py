"""Semantic checks use independently printed operands, not renderer output as an oracle."""

from copy import deepcopy

import pytest

from fatebridge.core.fengshui.opposite import opposite_star_comparison
from fatebridge.core.fengshui.reading import _opposite_statements
from fatebridge.core.fengshui.xuankong import _chart
from fatebridge.services.fengshui import calculate_xuankong_natal
from tests.test_fengshui_opposite import OPPOSITE_REFERENCE
from tests.test_fengshui_structure_reading import MOUNTAINS, request


@pytest.mark.parametrize(
    "case", OPPOSITE_REFERENCE["cases"], ids=lambda c: c["printed_example_id"]
)
def test_each_rendered_pair_names_the_independently_printed_roles_palaces_numbers_and_condition(
    case,
):
    result = calculate_xuankong_natal(**request(case))
    reading = result["calculation_reading"]
    by_target = {
        s["target_path"]: s
        for s in reading["statements"]
        if s["kind"] == "opposite_star_pair"
    }
    prefix = "layers.xuankong_natal.candidates.0.structure.classical_patterns.opposite_star_comparison.pairs."
    assert set(by_target) == {prefix + row[0] for row in case["pairs"]}
    for mountain_direction, facing_direction, mountain, facing, total, matched in case[
        "pairs"
    ]:
        text = by_target[prefix + mountain_direction]["text"]
        assert f"山星{mountain}在{mountain_direction}宫" in text
        assert f"向星{facing}在{facing_direction}宫" in text
        assert f"已算数和{total}，" in text
        assert "对宫合十条件" + ("符合" if matched else "不符合") in text
    summary = next(
        s["text"] for s in reading["statements"] if s["kind"] == "opposite_star_summary"
    )
    assert (
        "八个有向对宫条件：" + ("符合" if case["all_eight_match"] else "不符合")
        in summary
    )


def test_summary_reads_eight_pair_result_instead_of_substituting_a_matching_center():
    # A valid pair of permutations modified for this formatter check; no claim
    # that this is a printed or genuine traditional natal case.
    index = next(i for i, m in enumerate(MOUNTAINS) if m["name"] == "寅")
    chart = deepcopy(_chart(5, (index, "lower", "synthetic_text_counterexample")))
    chart["facing_chart"]["NW"], chart["facing_chart"]["E"] = (
        chart["facing_chart"]["E"],
        chart["facing_chart"]["NW"],
    )
    chart["structure"]["classical_patterns"]["opposite_star_comparison"] = (
        opposite_star_comparison(chart)
    )
    summary = _opposite_statements(chart)[0][2]
    assert "八个有向对宫条件：不符合" in summary
    assert "中宫仅作数字相加2+8=10，数和为十条件符合" in summary
    assert "不参与八宫合取" in summary
