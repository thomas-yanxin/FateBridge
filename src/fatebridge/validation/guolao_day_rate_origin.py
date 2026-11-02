"""Strict comparison of the declared day-rate source-value schema correction.

All prior cases and all other JSON values must survive. This verifier only
recognizes the documented source/effective-value and audit-count changes;
arithmetic differences, dropped cases and unrelated metadata changes fail.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA = "gujin45-day-rate-source-values-v2"
POLICY = "printed_empty_day_rate_at_index0_interpreted_as_lookup_zero_only"
COMPONENT_ADDITIONS = {
    "day_rate_output_schema_version",
    "selected_effective_day_rate_days",
    "selected_day_rate_source_mark",
    "empty_day_rate_origin_interpreted_as_zero",
    "day_rate_origin_policy",
}


def _require(condition: bool, path: str, reason: str) -> None:
    if not condition:
        raise ValueError(f"{path}: {reason}")


def _project_previous(
    before: Any, after: Any, path: str, changes: list[dict[str, Any]]
) -> Any:
    _require(type(before) is type(after), path, "输出类型改变")
    if isinstance(before, dict):
        projected = dict(after)
        if "selected_printed_day_rate_days" in before:
            _require(
                set(after) == set(before) | COMPONENT_ADDITIONS,
                path,
                "日率组件含未声明的增删字段",
            )
            index = before["whole_limit_index"]
            origin = index == 0
            effective = after["selected_effective_day_rate_days"]
            _require(
                effective == before["selected_printed_day_rate_days"],
                path,
                "有效日率或取限计算值改变",
            )
            _require(
                after["day_rate_output_schema_version"] == SCHEMA
                and after["day_rate_origin_policy"] == POLICY
                and after["empty_day_rate_origin_interpreted_as_zero"] is origin,
                path,
                "输出版本或原刊空格政策不符",
            )
            _require(
                after["selected_day_rate_source_mark"]
                == ("空" if origin else "numeric" if index is not None else None),
                path,
                "原字状态与取限不符",
            )
            if origin:
                _require(
                    effective == "0.0000"
                    and after["selected_printed_day_rate_days"] is None,
                    path,
                    "初限须保留原刊空格，仅有效日率解释为零",
                )
                projected["selected_printed_day_rate_days"] = effective
                if before["status"] == "unique_literal_rate_bracket":
                    _require(
                        after["status"] == "origin_zero_interpretation_bracket",
                        path,
                        "初限查询状态未表明解释政策",
                    )
                    projected["status"] = before["status"]
            for key in COMPONENT_ADDITIONS:
                projected.pop(key)
            changes.append(
                {
                    "path": path,
                    "kind": "day_rate_source_value_component",
                    "origin_empty_now_explicit": origin,
                }
            )
        elif before.get("model_id") == "gujin_literal_day_rate_table_audit_v1":
            expected = {
                "day_rate_output_schema_version": SCHEMA,
                "rate_position_count": 169,
                "printed_numeric_rate_count": 168,
                "printed_empty_rate_indices": [0],
                "effective_lookup_rate_count": 169,
                "day_rate_origin_policy": POLICY,
                "equal_step_diagnostic_numeric_compared_count": 168,
            }
            _require(
                before["literal_rate_count"] == 169
                and "literal_rate_count" not in after
                and after.get("model_id") == "gujin_literal_day_rate_table_audit_v2",
                path,
                "表内审计须显式迁移位置、数值与空格计数",
            )
            for key, value in expected.items():
                _project_previous(value, projected.pop(key, None), f"{path}.{key}", [])
            projected["literal_rate_count"] = 169
            projected["model_id"] = before["model_id"]
            changes.append({"path": path, "kind": "numeric_and_empty_rate_counts"})
        elif before.get("model_id") == "gujin_literal_cumulative_increment_audit_v1":
            expected = {
                "day_rate_output_schema_version": SCHEMA,
                "day_rate_origin_policy": POLICY,
                "empty_day_rate_origin_interpreted_as_zero_at_boundary1": True,
            }
            for key, value in expected.items():
                actual = projected.pop(key, None)
                _require(
                    type(actual) is type(value) and actual == value,
                    path,
                    f"积度边界的日率解释政策不符:{key}",
                )
            changes.append({"path": path, "kind": "cumulative_boundary_rate_policy"})
        _require(set(before) == set(projected), path, "存在未声明的增删字段")
        return {
            key: _project_previous(value, projected[key], f"{path}.{key}", changes)
            for key, value in before.items()
        }
    if isinstance(before, list):
        _require(len(before) == len(after), path, "列表长度改变，不能省略失败或缺失项")
        return [
            _project_previous(old, new, f"{path}[{i}]", changes)
            for i, (old, new) in enumerate(zip(before, after, strict=True))
        ]
    _require(before == after, path, "存在未声明的数值、状态或元数据变化")
    return after


def compare_origin_schema_outputs(
    before: dict[str, str], after: dict[str, str]
) -> dict[str, Any]:
    """Require every prior case and every value outside the stated migration."""
    _require(
        isinstance(before, dict)
        and isinstance(after, dict)
        and all(isinstance(k, str) and isinstance(v, str) for k, v in before.items())
        and all(isinstance(k, str) and isinstance(v, str) for k, v in after.items()),
        "$",
        "输入须为命令名到完整stdout字符串的JSON对象",
    )
    _require(bool(before), "$", "旧基线不能为空")
    _require(set(before) <= set(after), "$", "旧命令案例被删除")
    rows = []
    changed_cases = 0
    origin_nodes = 0
    for key, old_stdout in before.items():
        changes: list[dict[str, Any]] = []
        old = json.loads(old_stdout)
        new = json.loads(after[key])
        projected = _project_previous(old, new, "$", changes)
        _require(projected == old, key, "迁移核对未能保留旧结果")
        exact = old_stdout == after[key]
        _require(bool(changes) or exact, key, "无声明变更的案例必须保持完整stdout字节")
        changed_cases += not exact
        origin_nodes += sum(c.get("origin_empty_now_explicit", False) for c in changes)
        rows.append({"case": key, "stdout_byte_identical": exact, "changes": changes})
    return {
        "comparison": "strict_gujin45_day_rate_source_value_schema_v1_to_v2",
        "prior_cases": len(before),
        "prior_cases_dropped": 0,
        "prior_cases_with_changed_stdout": changed_cases,
        "prior_cases_with_byte_identical_stdout": len(before) - changed_cases,
        "origin_empty_components_now_explicit": origin_nodes,
        "additional_cases_without_prior_baseline": sorted(set(after) - set(before)),
        "all_previous_calculation_values_and_undeclared_fields_equal": True,
        "original_source_data_or_prior_stdout_rewritten": False,
        "rows": rows,
        "complete_calendar_accuracy_demonstrated": False,
        "real_world_prediction_demonstrated": False,
    }
