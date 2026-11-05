"""Anchor strength, qi and use conditions to the same four positions.

All deterministic rules remain in the domain services. Sparse views validate
only facts whose anchors are present; complete service output must retain them.
"""

from __future__ import annotations

from typing import Any

from fatebridge.core.output_jinkou_comparison import TEXT_FIELDS, compare_present

from .metaphysics.common import branch_element_text, stem_element_text
from .metaphysics.jinkou_patterns import use_evidence
from .metaphysics.jinkou_qi import build_jinkou_qi
from .metaphysics.jinkou_seasonal import seasonal_power, seasonal_power_basis
from .metaphysics.jinkou_strength import internal_strength

POSITIONS = ("人元", "贵神", "将神", "地分")
TRACES = {
    "internal_strength": "jinkou.internal_strength",
    "use_evidence": "jinkou.use_conditions",
    "qi_evidence": "jinkou.month_day_qi",
}
ROW_FIELDS = (
    "label",
    "content",
    "element",
    "polarity",
    "seasonal_power",
    "internal_power",
    "xun_kong",
    "si_da_kong",
    "month_break",
    "is_use",
)


def expected_facts(board: dict[str, Any]) -> dict[str, Any]:
    """Use present raw phases as anchors; never insert an omitted view field."""
    rows = board.get("rows")
    if not isinstance(rows, list) or len(rows) != 4:
        return {}
    if [r.get("label") for r in rows] != list(POSITIONS):
        return {}
    canonical = []
    for index, row in enumerate(rows):
        phase = row.get("element")
        content = row.get("content")
        if content is not None:
            try:
                anchored = (stem_element_text if index == 0 else branch_element_text)(
                    content
                )
            except (KeyError, TypeError) as exc:
                raise ValueError("旺衰输入须为人元干及其余三位的地支") from exc
            if "element" in row and phase != anchored:
                raise ValueError("旺衰须使用四位实际干支的五行")
            phase = anchored
        if phase is None:
            return {}
        canonical.append(dict(row, element=phase))
    strength = internal_strength(canonical)
    result = {"internal_strength": strength}
    for row in canonical:
        row["internal_power"] = strength["powers"][row["label"]]
    needed = ("content", "seasonal_power", "xun_kong", "si_da_kong", "month_break")
    if all(all(k in r and r[k] is not None for k in needed) for r in canonical):
        from ..utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS
        from .metaphysics.jinkou import _jinkou_pick_use_position

        for i, row in enumerate(canonical):
            sequence = HEAVENLY_STEMS if i == 0 else EARTHLY_BRANCHES
            row["polarity"] = "阳" if sequence.index(row["content"]) % 2 == 0 else "阴"
        position, _, _ = _jinkou_pick_use_position(canonical)
        result["use_evidence"] = use_evidence(
            canonical, strength, polarity_position=position
        )
    qi = board.get("qi_evidence")
    if (
        isinstance(qi, dict)
        and qi.get("month_building_branch") is not None
        and qi.get("day_branch") is not None
        and all(r.get("content") is not None for r in canonical)
    ):
        result["qi_evidence"] = build_jinkou_qi(
            canonical,
            month_branch=qi["month_building_branch"],
            day_branch=qi["day_branch"],
        )
    return result


def validate_seasonal_evidence(board: dict[str, Any]) -> None:
    """Bind available facts without manufacturing a projected-out month."""
    months = [
        obj[key]
        for name, key in (
            ("qi_evidence", "month_building_branch"),
            ("combinations", "month_branch"),
        )
        if isinstance(obj := board.get(name), dict) and obj.get(key) is not None
    ]
    if not months:
        return
    month = months[0]
    basis = seasonal_power_basis(month)
    if any(other != month for other in months):
        raise ValueError("同课四季旺衰的月建依据不一致")
    overview = board.get("overview")
    if isinstance(overview, dict) and overview.get("power_basis") is not None:
        compare_present(overview["power_basis"], basis)
    rows = board.get("rows")
    if not isinstance(rows, list):
        return
    for index, row in enumerate(rows):
        phase = row.get("element")
        content = row.get("content")
        position = row.get("label") or (POSITIONS[index] if len(rows) == 4 else None)
        if content is not None and position in POSITIONS:
            try:
                anchored = (
                    stem_element_text if position == "人元" else branch_element_text
                )(content)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("四季旺衰须使用四位实际干支") from exc
            if phase is not None:
                compare_present(phase, anchored)
            phase = anchored
        if phase is None:
            continue
        power = seasonal_power(month, phase)
        if row.get("seasonal_power") is not None:
            compare_present(row["seasonal_power"], power)


def validate_strength_evidence(board: dict[str, Any]) -> None:
    from fatebridge.core.output_jinkou_course_qi import validate_course_qi

    validate_course_qi(board)
    validate_seasonal_evidence(board)
    expected = expected_facts(board)
    strength = expected.get("internal_strength")
    if strength is not None:
        for row in board["rows"]:
            if "internal_power" in row:
                compare_present(row["internal_power"], strength["powers"][row["label"]])
    for key, value in expected.items():
        if key in board:
            compare_present(board[key], value, key)
    for key, rule_id in TRACES.items():
        traces = [
            t for t in board.get("rule_trace") or [] if t.get("rule_id") == rule_id
        ]
        if len(traces) > 1:
            raise ValueError("金口诀同一旺衰或取用规则轨迹不可重复")
        if key in expected and traces and "result" in traces[0]:
            compare_present(traces[0]["result"], expected[key], key)


def require_present(actual: Any, expected: Any) -> None:
    """Full output retains nullable facts; views are not passed through this gate."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(expected) - set(actual):
            raise ValueError("完整金口诀缺少旺衰或用位依据字段")
        for key, value in expected.items():
            require_present(actual[key], value)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError("完整金口诀缺少旺衰或用位依据条目")
        for a, b in zip(actual, expected):
            require_present(a, b)
    elif expected is not None and actual is None:
        raise ValueError("完整金口诀不可将已知旺衰或取用依据置空")
    elif isinstance(expected, str) and (
        not isinstance(actual, str) or not actual.strip()
    ):
        raise ValueError("完整金口诀不可将旺衰或取用说明置空")


def require_complete_strength_evidence(board: dict[str, Any]) -> None:
    rows = board.get("rows")
    if not isinstance(rows, list) or len(rows) != 4:
        raise ValueError("完整金口诀须保留四位旺衰的输入依据")
    for position, row in zip(POSITIONS, rows):
        if (
            not isinstance(row, dict)
            or row.get("label") != position
            or any(k not in row for k in ROW_FIELDS)
            or any(row[k] is None for k in ROW_FIELDS if k != "internal_power")
        ):
            raise ValueError("完整金口诀须保留四位旺衰的输入依据")
    expected = expected_facts(board)
    if set(expected) != set(TRACES):
        raise ValueError("完整金口诀须保留月建日辰与阴阳用位依据")
    basis = seasonal_power_basis(expected["qi_evidence"]["month_building_branch"])
    overview = board.get("overview")
    if not isinstance(overview, dict) or overview.get("power_basis") != basis:
        raise ValueError("完整金口诀须保留与实际月建一致的四季旺衰说明")
    for key, value in expected.items():
        require_present(board.get(key), value)
        traces = [
            t for t in board.get("rule_trace") or [] if t.get("rule_id") == TRACES[key]
        ]
        if len(traces) != 1:
            raise ValueError("完整金口诀须保留唯一的旺衰与用位规则轨迹")
        require_present(traces[0].get("result"), value)
        if key == "internal_strength":
            source = value["source_evidence"]
            if (
                board[key].get("source_evidence") != source
                or traces[0]["result"].get("source_evidence") != source
                or traces[0].get("source_url") != source["source_url"]
                or traces[0].get("source_section") != source["source_section"]
            ):
                raise ValueError("完整旺衰须保留相同且真实的原书来源与异文")
    validate_strength_evidence(board)
