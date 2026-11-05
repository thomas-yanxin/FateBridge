"""Printed spatial operands and full-domain current arithmetic."""

import asyncio
import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.cli import run
from fatebridge.core.fengshui.opposite import opposite_star_comparison
from fatebridge.core.fengshui.reading import build_natal_reading
from fatebridge.core.fengshui.xuankong import _chart
from fatebridge.services.fengshui import calculate_xuankong_natal
from fatebridge.services.replay_metadata import digest
from fatebridge.validation.fengshui_opposite import audit_opposite_reference
from fatebridge.validation.fengshui_reading import verify_fengshui_reading
from tests.fengshui.test_fengshui_fixed_reading import executed, trusted
from tests.fengshui.test_fengshui_structure_reading import MOUNTAINS, REFERENCE, request
from tests.fengshui.test_fengshui_surfaces import (
    mcp_call,
    rest_client,
    without_transport,
)

FIXTURES = Path(__file__).parents[1] / "data"
OPPOSITE_REFERENCE = json.loads(
    (FIXTURES / "fengshui_opposite_v1/reference.json").read_text()
)


def comparison(result):
    return result["layers"]["xuankong_natal"]["chart"]["structure"][
        "classical_patterns"
    ]["opposite_star_comparison"]


def test_printed_operands_match_sixteen_directed_pairs_and_two_independent_centers():
    report = audit_opposite_reference(OPPOSITE_REFERENCE, REFERENCE)
    assert report["scoped_acceptance_passed"] and not report["differences"]
    assert report["directed_pair_checks"] == 16 and report["center_numeric_checks"] == 2
    assert report["all_eight_checks"] == 2
    assert (
        not report["whole_book_conformity_established"]
        and not report["real_world_prediction_established"]
    )


def test_printed_five_example_is_opposite_not_same_palace_sum_ten():
    result = calculate_xuankong_natal(**request(REFERENCE["charts"][4]))
    c = comparison(result)
    assert c["all_eight_sum_to_ten"] is True
    assert c["pairs"]["N"]["mountain_star_number"] == 7
    assert c["pairs"]["N"]["facing_star_number"] == 3
    assert c["pairs"]["S"]["mountain_star_number"] == 6
    assert c["pairs"]["S"]["facing_star_number"] == 4
    same = next(
        p
        for p in result["layers"]["xuankong_natal"]["chart"]["structure"][
            "combination_of_ten"
        ]
        if (p["left_role"], p["right_role"]) == ("mountain", "facing")
    )
    assert same["all_nine_sum_to_ten"] is False
    assert (
        "C" not in c["pairs"]
        and not c["center_numeric_pair"]["spatial_opposite_exists"]
    )
    assert "八个有向对宫条件：符合" in result["calculation_reading"]["text"]


def test_author_reverse_heading_can_coexist_with_false_opposite_star_condition():
    result = calculate_xuankong_natal(**request(REFERENCE["charts"][3]))
    assert not comparison(result)["all_eight_sum_to_ten"]
    assert result["layers"]["xuankong_natal"]["chart"]["structure"][
        "classical_patterns"
    ]["ground_comparison"]["roles"]["mountain"]["whole_ground_reverse"]
    assert "本条数式不等于所有反吟定义" in result["calculation_reading"]["text"]


def test_all432_charts_match_independent_coordinate_reflection_and_raw_operands():
    coordinates = {
        "N": (0, 1),
        "NE": (1, 1),
        "E": (1, 0),
        "SE": (1, -1),
        "S": (0, -1),
        "SW": (-1, -1),
        "W": (-1, 0),
        "NW": (-1, 1),
    }
    for period in range(1, 10):
        for index in range(24):
            for mode in ("lower", "replacement"):
                chart = _chart(
                    period, (index, mode, "arithmetic_domain_not_source_oracle")
                )
                result = chart["structure"]["classical_patterns"][
                    "opposite_star_comparison"
                ]
                matches = []
                assert set(result["pairs"]) == set(coordinates)
                for direction, (x, y) in coordinates.items():
                    opposite = next(
                        k for k, xy in coordinates.items() if xy == (-x, -y)
                    )
                    row = result["pairs"][direction]
                    total = (
                        chart["mountain_chart"][direction]
                        + chart["facing_chart"][opposite]
                    )
                    assert row == dict(
                        mountain_direction=direction,
                        facing_direction=opposite,
                        mountain_star_number=chart["mountain_chart"][direction],
                        facing_star_number=chart["facing_chart"][opposite],
                        sum=total,
                        matches_sum_to_ten=total == 10,
                    )
                    matches.append(total == 10)
                assert result["all_eight_sum_to_ten"] is all(matches)
                assert result["spatial_pair_count"] == 8
                assert (
                    result["center_numeric_pair"]["included_in_spatial_conjunction"]
                    is False
                )


def test_valid_synthetic_permutation_cannot_hide_last_pairs_behind_four_axes_or_center():
    # This deliberately modified pair of valid permutations is not a real natal example.
    chart = _chart(
        5,
        (
            next(i for i, m in enumerate(MOUNTAINS) if m["name"] == "寅"),
            "lower",
            "synthetic_counterexample",
        ),
    )
    chart["facing_chart"]["NW"], chart["facing_chart"]["E"] = (
        chart["facing_chart"]["E"],
        chart["facing_chart"]["NW"],
    )
    c = opposite_star_comparison(chart)
    assert c["center_numeric_pair"]["matches_sum_to_ten"]
    assert sum(p["matches_sum_to_ten"] for p in c["pairs"].values()) == 6
    assert c["all_eight_sum_to_ten"] is False


@pytest.mark.parametrize(
    "corruption", ["missing", "boolean", "duplicate_star", "duplicate_flight"]
)
def test_incomplete_plates_are_rejected_instead_of_looking_like_complete_negative(
    corruption,
):
    chart = _chart(5, (0, "lower", "invalid_input_test"))
    if corruption == "missing":
        del chart["facing_chart"]["NW"]
    elif corruption == "boolean":
        chart["facing_chart"]["C"] = True
    elif corruption == "duplicate_star":
        chart["facing_chart"]["NW"] = chart["facing_chart"]["N"]
    else:
        chart["flight_path"][0] = chart["flight_path"][1]
    with pytest.raises(ValueError):
        opposite_star_comparison(chart)


def test_current_period_does_not_rewrite_historical_spatial_numbers_and_replacement_is_numeric_only():
    req = request(REFERENCE["charts"][4])
    a = calculate_xuankong_natal(**req)
    req["interpretation"]["current_period_number"] = 2
    req["interpretation"]["period_evidence"] = "独立二运"
    assert comparison(a) == comparison(calculate_xuankong_natal(**req))
    replacement = calculate_xuankong_natal(**request(REFERENCE["charts"][4], offset=6))
    assert (
        replacement["layers"]["xuankong_natal"]["chart"]["chart_mode"] == "replacement"
    )
    assert "numeric_relation_only" in comparison(replacement)["replacement_scope"]
    assert "不继承原书下卦例盘或应期裁决" in replacement["calculation_reading"]["text"]


def test_new_version_covers_every_bearing_candidate_and_does_not_credit_missing_natal():
    req = request(REFERENCE["charts"][4])
    req["house"]["facing_degrees"] = 7.5
    result = executed(req)
    reading = result["calculation_reading"]
    count = len(result["layers"]["xuankong_natal"]["candidates"])
    assert count > 1 and reading["version"] == "1.2.0"
    assert (
        sum(s["kind"] == "opposite_star_pair" for s in reading["statements"])
        == 8 * count
    )
    assert (
        verify_fengshui_reading(result, **trusted(result))[
            "opposite_palace_chart_count"
        ]
        == count
    )
    missing = executed(
        {
            "interpretation": {
                "current_period_number": 8,
                "period_evidence": "独立八运",
                "fixed_lingzheng": {},
            }
        }
    )
    report = verify_fengshui_reading(missing, **trusted(missing))
    assert (
        report["status"] == "verified_served_fixed_reading"
        and not report["opposite_palace_coverage_verified"]
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "omit_negative_pair",
        "wrong_target",
        "false_direction",
        "center_opposite",
        "four_axes",
        "invent_fortune",
    ],
)
def test_new_semantic_or_context_corruption_is_rejected_even_with_synthetic_trusted_receipt(
    mutation,
):
    result = executed(request(REFERENCE["charts"][3]))
    reading = result["calculation_reading"]
    c = result["layers"]["xuankong_natal"]["candidates"][0]["structure"][
        "classical_patterns"
    ]["opposite_star_comparison"]
    if mutation == "omit_negative_pair":
        reading["statements"] = [
            s
            for s in reading["statements"]
            if not (
                s["kind"] == "opposite_star_pair" and s["target_path"].endswith(".N")
            )
        ]
    elif mutation == "wrong_target":
        next(s for s in reading["statements"] if s["kind"] == "opposite_star_pair")[
            "target_path"
        ] = "layers.xuankong_natal.candidates.0.facing_chart.NE"
    elif mutation == "false_direction":
        c["pairs"]["N"]["facing_direction"] = "NE"
    elif mutation == "center_opposite":
        c["center_numeric_pair"]["spatial_opposite_exists"] = True
    elif mutation == "four_axes":
        c["pairs"] = dict(list(c["pairs"].items())[:4])
        c["spatial_pair_count"] = 4
    else:
        next(s for s in reading["statements"] if s["kind"] == "opposite_star_summary")[
            "text"
        ] += "保证现实旺财"
    reading["text"] = "\n".join(s["text"] for s in reading["statements"])
    result["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in result.items() if k != "run_metadata"}
    )
    assert verify_fengshui_reading(result, **trusted(result))["status"] == "rejected"


def test_new_run_downgrade_to_previous_valid_renderer_cannot_replace_original_receipt():
    result = executed(request(REFERENCE["charts"][4]))
    anchor = trusted(result)
    result["calculation_reading"]["version"] = "1.1.0"
    assert result["calculation_reading"]["status"] == "rendered"
    result["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in result.items() if k != "run_metadata"}
    )
    assert verify_fengshui_reading(result, **anchor)["status"] == "rejected"


@pytest.mark.parametrize("tool", ["xuankong_natal", "assess"])
def test_opposite_comparison_and_fixed_text_match_rest_mcp_cli(
    monkeypatch, tmp_path, capsys, tool
):
    data = request(REFERENCE["charts"][4])
    if tool == "assess":
        data = {"methods": ["xuankong_natal"], "xuankong": data}
    http = rest_client(monkeypatch).post("/api/fengshui/" + tool, json=data)
    mcp = asyncio.run(mcp_call(tool, data))
    path = tmp_path / "opposite.json"
    path.write_text(json.dumps(data))
    assert run(["fengshui_" + tool, "--request-file", str(path)]) == 0
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 200 and not mcp.is_error
    assert (
        without_transport(http.json())
        == without_transport(mcp.structured_content)
        == without_transport(cli)
    )
    assert (
        comparison(cli)["all_eight_sum_to_ten"]
        and cli["rulesets"][0]["version"] == "1.4.0"
    )
    assert verify_fengshui_reading(cli, **trusted(cli))[
        "opposite_palace_coverage_verified"
    ]


def test_strict_projection_keeps_full_directed_relation_and_source_but_is_not_a_complete_receipt():
    data = request(REFERENCE["charts"][4])
    result = asyncio.run(
        mcp_call(
            "xuankong_natal",
            {
                **data,
                "fields": [
                    "layers.xuankong_natal.chart.structure.classical_patterns.opposite_star_comparison",
                    "rulesets",
                    "rule_trace",
                ],
                "strict_fields": True,
                "include_snapshot_text": False,
            },
        )
    )
    assert not result.is_error
    assert len(comparison(result.structured_content)["pairs"]) == 8
    assert "X12" in result.structured_content["rulesets"][0]["source_ids"]


@pytest.mark.parametrize(
    "mutation",
    [
        "drop_case",
        "four_axes",
        "wrong_opposite",
        "wrong_operand",
        "wrong_center",
        "boolean_operand",
        "float_total",
    ],
)
def test_independent_reference_cannot_be_narrowed_or_repaired_from_production(mutation):
    ref = deepcopy(OPPOSITE_REFERENCE)
    if mutation == "drop_case":
        ref["cases"].pop()
    elif mutation == "four_axes":
        ref["cases"][0]["pairs"] = ref["cases"][0]["pairs"][:4]
    elif mutation == "wrong_opposite":
        ref["cases"][0]["pairs"][0][1] = "NE"
    elif mutation == "wrong_operand":
        ref["cases"][0]["pairs"][0][2] += 1
    elif mutation == "boolean_operand":
        ref["cases"][0]["pairs"][3][2] = True
    elif mutation == "float_total":
        ref["cases"][0]["pairs"][0][4] = 10.0
    else:
        ref["cases"][0]["center"][2] += 1
    with pytest.raises(ValueError):
        audit_opposite_reference(ref, REFERENCE)


@pytest.mark.parametrize("mutation", ["number", "boolean_type"])
def test_independent_reference_reports_a_corrupted_engine_value_as_disagreement(
    monkeypatch,
    mutation,
):
    from fatebridge.validation import fengshui_opposite as module

    original = module._chart

    def altered(*args):
        result = original(*args)
        row = result["structure"]["classical_patterns"]["opposite_star_comparison"][
            "pairs"
        ]["N"]
        if mutation == "number":
            row["sum"] += 1
        else:
            row["matches_sum_to_ten"] = int(row["matches_sum_to_ten"])
        return result

    monkeypatch.setattr(module, "_chart", altered)
    report = audit_opposite_reference(OPPOSITE_REFERENCE, REFERENCE)
    assert not report["scoped_acceptance_passed"] and len(report["differences"]) == 2
