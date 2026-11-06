"""Independent printed operands and directed pairs, separate from full fan-yin claims."""

from typing import Any

from fatebridge.core.fengshui.xuankong import _chart, natal_rules
from fatebridge.utils.json_values import same_value as _same_value


def audit_opposite_reference(
    reference: dict[str, Any], printed: dict[str, Any]
) -> dict[str, Any]:
    mapping = reference["opposite_directions"]
    expected_mapping = {
        "N": "S",
        "NE": "SW",
        "E": "W",
        "SE": "NW",
        "S": "N",
        "SW": "NE",
        "W": "E",
        "NW": "SE",
    }
    cases = reference["cases"]
    if (
        mapping != expected_mapping
        or len(cases) != 2
        or len({c["printed_example_id"] for c in cases}) != 2
    ):
        raise ValueError("保留两个原书例及八个有向对宫参照")
    if reference["source"]["sha256"] != printed["source"]["sha256"]:
        raise ValueError("两份独立转录须指向同一印刷文件")
    printed_cases = {c["id"]: c for c in printed["charts"]}
    mountains = [m["name"] for m in natal_rules()["mountains"]]
    differences = []
    for case in cases:
        source = printed_cases[case["printed_example_id"]]
        if source["period"] != case["period"] or source["facing"] != case["facing"]:
            raise ValueError("不能换用其他运或山向替代原例")
        rows = dict(zip(printed["row_order"], source["rows"]))
        pairs = case["pairs"]
        if len(pairs) != 8 or {r[0] for r in pairs} != set(mapping):
            raise ValueError("八个有向配对不能删成四轴或选择部分正例")
        for direction, opposite, mountain, facing, total, matched in pairs:
            if (
                any(type(n) is not int for n in (mountain, facing, total))
                or opposite != mapping[direction]
                or [mountain, facing] != [rows[direction][0], rows[opposite][1]]
                or type(matched) is not bool
                or total != mountain + facing
                or matched != (total == 10)
            ):
                raise ValueError("配对转录与既有独立印刷数字或空间参照不一致")
        center = case["center"]
        if (
            any(type(n) is not int for n in center[:3])
            or center[:2] != rows["C"][:2]
            or center[2] != sum(center[:2])
            or type(center[3]) is not bool
            or center[3] != (center[2] == 10)
        ):
            raise ValueError("中宫数字独立留证，不成为空间对宫")
        if type(case["all_eight_match"]) is not bool or case["all_eight_match"] != all(
            r[5] for r in pairs
        ):
            raise ValueError("保留全部八宫合取的原例状态")
        actual = _chart(
            case["period"],
            (mountains.index(case["facing"]), "lower", "opposite_printed_reference"),
        )["structure"]["classical_patterns"]["opposite_star_comparison"]
        for direction, opposite, mountain, facing, total, matched in pairs:
            wanted = {
                "mountain_direction": direction,
                "facing_direction": opposite,
                "mountain_star_number": mountain,
                "facing_star_number": facing,
                "sum": total,
                "matches_sum_to_ten": matched,
            }
            if not _same_value(actual["pairs"].get(direction), wanted):
                differences.append(
                    {
                        "example": case["printed_example_id"],
                        "direction": direction,
                        "expected": wanted,
                        "actual": actual["pairs"].get(direction),
                    }
                )
        wanted_center = {
            "mountain_star_number": center[0],
            "facing_star_number": center[1],
            "sum": center[2],
            "matches_sum_to_ten": center[3],
            "spatial_opposite_exists": False,
            "included_in_spatial_conjunction": False,
        }
        if (
            not _same_value(actual["center_numeric_pair"], wanted_center)
            or actual["all_eight_sum_to_ten"] is not case["all_eight_match"]
        ):
            differences.append(
                {
                    "example": case["printed_example_id"],
                    "finding": "center_or_eight_pair_conjunction_mismatch",
                }
            )
    return {
        "printed_examples": 2,
        "directed_pair_checks": 16,
        "center_numeric_checks": 2,
        "all_eight_checks": 2,
        "differences": differences,
        "scoped_acceptance_passed": not differences,
        "source": reference["source"],
        "scope": "opposite_star_arithmetic_using_previously_transcribed_printed_operands_not_new_real_world_cases",
        "whole_book_conformity_established": False,
        "real_world_prediction_established": False,
    }
