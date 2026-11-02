"""Original empty/nonempty conditions, distinct from permanent outcome claims."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any

from .liuyao_activity import activity_condition
from .liuyao_month_break import month_opposition_applies
from .liuyao_relations import ELEMENTS, branch_facts, element_relation, xunkong

PROFILE: dict[str, Any] = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-void-v7.json")
    .read_text(encoding="utf-8")
)


def build_void_conditions(
    *,
    lines: list[dict[str, Any]],
    hidden: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
    assessment: dict[str, Any],
    month: str,
    day_ganzhi: str,
    focus: dict[str, Any],
) -> dict[str, Any]:
    void, day = xunkong(day_ganzhi), day_ganzhi[1]
    source = PROFILE["source"]["url"]

    def rule(
        name: str, condition: str, matched: bool | None, page: int = 93
    ) -> dict[str, Any]:
        return {
            "rule_id": name,
            "condition": condition,
            "matched": matched,
            "status": (
                "unresolved"
                if matched is None
                else ("matched" if matched else "not_matched")
            ),
            "source_url": source + f"#page={page}",
        }

    rows = []
    for line in lines:
        p, branch = line["position"], line["branch"]
        c, a = conditions[p - 1], assessment["lines"][p - 1]["strength"]
        active = activity_condition(line, c)
        facts = branch_facts(branch, month, day, void)
        changed_void = line["changed_branch"] in void if line["change"] else None
        moving_positions = {
            r["position"]
            for r in lines
            if r["change"]
            or conditions[r["position"] - 1]["activity"]
            in ("暗动条件匹配", "冲空条件匹配")
        }
        support = any(
            s["location"] == "visible" and s["position"] in moving_positions
            for s in a["supports"]
        )
        pending = any(
            s["location"] == "visible" and s["position"] in moving_positions
            for s in a["pending_supports"]
        )
        positive = [
            rule(
                "supported", "旺不为空；仅使用同次明确有根生扶裁定", a["is_supported"]
            ),
            rule("active", "动不为空；活动资格未决不能当已动", active),
            rule(
                "day_void_fill",
                "日辰冲空则实；只解除当日所列空亡门槛",
                facts["is_xunkong"] and facts["is_day_clash"],
                67,
            ),
            rule(
                "day_generate",
                "日建生扶不为空",
                element_relation(ELEMENTS[day], line["element"]) in ("生爻", "比和"),
            ),
            rule(
                "moving_generate",
                "有实际可用动爻生扶不为空；回头克来源不能算普通生扶",
                True if support else (None if pending else False),
            ),
            rule(
                "moving_to_void",
                "动而化空不作到底全空",
                bool(line["change"] and changed_void),
            ),
        ]
        seasonal = (
            (month in "寅卯辰" and line["element"] == "土")
            or (month in "巳午未" and line["element"] == "金")
            or (month in "申酉戌" and line["element"] == "木")
            or (month in "亥子丑" and line["element"] == "火")
        )
        negative = [
            rule(
                "month_break",
                "月破为空的条件；不据此推到底全空",
                facts["is_month_clash"],
            ),
            rule(
                "qi_static",
                "有气不动亦为空；与旺不为空并见时须保留原章疑义及时间层",
                (
                    (None if active is None else not active)
                    if bool(
                        c["monthly_strength"]["monthly_supported"]
                        or c["monthly_strength"]["residual_qi"]
                    )
                    else False
                ),
            ),
            rule(
                "seasonal_true_void_label",
                "春土夏金秋木三冬火的原文季令真空标签；不是全局旺衰裁定",
                seasonal,
                94,
            ),
        ]
        negative[0]["qualified_matched"] = month_opposition_applies(branch, month, day)
        positives = any(r["matched"] is True for r in positive)
        negatives = any(
            r.get("qualified_matched", r["matched"]) is True for r in negative
        )
        if not facts["is_xunkong"]:
            status, truth = "not_in_xunkong", False
        elif positives and not negatives:
            status, truth = "not_final_void_pending_use", False
        else:
            status, truth = "conflicting_or_unresolved_conditions", None
        rows.append(
            {
                "location": "visible",
                "position": p,
                "branch": branch,
                "is_xunkong": facts["is_xunkong"],
                "changed_is_xunkong": changed_void,
                "day_void_fill_condition": facts["is_xunkong"]
                and facts["is_day_clash"],
                "not_empty_conditions": positive,
                "empty_conditions": negative,
                "classification": status,
                "is_true_void": truth,
                "is_permanently_void": None,
                "permanent_void_status": "not_adjudicated",
                "requires_horizon_review": facts["is_xunkong"] or bool(changed_void),
                "source_url": source + "#page=93",
            }
        )
    hidden_rows = [
        {
            "location": "hidden",
            "position": r["position"],
            "branch": r["branch"],
            "is_xunkong": r["branch"] in void,
            "changed_is_xunkong": None,
            "flying_branch": lines[r["position"] - 1]["branch"],
            "not_empty_conditions": [
                rule("hidden_supported", "伏而旺相不为空；伏神总旺衰仍待裁定", None)
            ],
            "empty_conditions": [
                rule(
                    "flying_controls_hidden",
                    "伏而被克的原文空条件",
                    element_relation(
                        ELEMENTS[lines[r["position"] - 1]["branch"]],
                        ELEMENTS[r["branch"]],
                    )
                    == "克爻",
                )
            ],
            "classification": "requires_hidden_strength_and_horizon",
            "is_true_void": None,
            "is_permanently_void": None,
            "permanent_void_status": "not_adjudicated",
            "requires_horizon_review": r["branch"] in void,
            "source_url": source + "#page=94",
        }
        for r in hidden
    ]
    selected = focus["selected"]
    focus_row = next(
        (
            r
            for r in [*rows, *hidden_rows]
            if selected
            and r["location"] == selected["location"]
            and r["position"] == selected["position"]
        ),
        None,
    )
    return {
        "ruleset_id": PROFILE["ruleset_id"],
        "ruleset_version": PROFILE["ruleset_version"],
        "source_url": source + "#page=93",
        "source_sha256": PROFILE["source"]["sha256"],
        "lines": rows,
        "hidden": hidden_rows,
        "focus": deepcopy(focus_row),
        "textual_issues": deepcopy(PROFILE["textual_issues"]),
        "horizon_status": "requires_question_horizon_and_total_judgment",
        "scope": "旬空是原旬缺支；不为空条件、原文空条件和季令标签分别保留。原章近远、总旺衰及疑义未决时不推到底全空，也不将不作真空读成此刻已经可用。变爻及日月取用不套明爻空亡判定，不代用户再占，不输出事件成败。",
    }
