"""Chapter-selected timing roles and literal named day-branch membership.

This atom is distinct from seasonal strength, month labels and a forecast date.
"""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.meihua_roles import LABELS

from ..utils.data import EARTHLY_BRANCHES
from .meihua import meihua_stage_relations


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    profile: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/meihua/qi-day-atoms-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if (
        profile["id"] != "meihua_qi_day_atoms_nlc1925_v1"
        or profile["version"] != "1.0.0"
        or set(profile["literal_day_branch_atoms"]) != set("乾坤震巽坎离艮兑")
        or len(profile["chapter_selectors"]) != 5
    ):
        raise ValueError("Unknown selected qi day-atom profile")
    for row in profile["literal_day_branch_atoms"].values():
        if not row["day_branches"] or any(
            b not in EARTHLY_BRANCHES for b in row["day_branches"]
        ):
            raise ValueError("Qi day atoms require explicit original branch labels")
    return profile


def qi_day_atom_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


def chapter_timing_targets(
    cast: dict[str, Any],
    layer: dict[str, Any],
    topic: str,
    *,
    fact_prefix: str,
    clause_path: str,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Keep the same actual chapter-selected roles for every time unit."""
    profile = _profile()
    stages = meihua_stage_relations(cast, fact_prefix=fact_prefix)
    nodes: list[dict[str, Any]] = [
        {
            "role": "body",
            "trigram": cast["body_trigram"]["name"],
            "relation": "body_self",
            "fact_path": fact_prefix + ".body_trigram",
        },
        *stages,
    ]
    by_role = {row["role"]: row for row in nodes}
    selectors = profile["chapter_selectors"]
    targets: list[dict[str, Any]] = []
    if topic == "wealth":
        for key in ("wealth_gain", "wealth_loss"):
            rule = selectors[key]
            for row in stages:
                if row["relation"] == rule["relation"]:
                    index = next(
                        i for i, r in enumerate(stages) if r["role"] == row["role"]
                    )
                    targets.append(
                        {
                            "selector_id": key,
                            "node": row,
                            "selected_source_context_condition": True,
                            "condition_fact_path": f"{fact_prefix}.stage_relations.{index}.relation",
                            "full_source_context_authenticated": False,
                        }
                    )
    elif topic == "reputation":
        q = (
            layer["topic_reading"]["chapter_qualifications"]
            if "topic_reading" in layer
            else layer["topic_clause"]["chapter_qualifications"]
        )
        for key, collection in [
            ("reputation_completion", "support_time_references"),
            ("reputation_office", "attacker_time_references"),
        ]:
            if [r["role"] for r in q[collection]] != [
                r["role"] for r in stages if r["relation"] == selectors[key]["relation"]
            ]:
                raise ValueError(
                    "Qi timing must retain every chapter-selected actual role"
                )
            for row in q[collection]:
                actual = by_role[row["role"]]
                if (row["trigram"], row["relation"], row["trigram_fact_path"]) != (
                    actual["trigram"],
                    selectors[key]["relation"],
                    actual["fact_path"] + ".name",
                ):
                    raise ValueError(
                        "Qi timing cannot borrow another role's source selector"
                    )
                condition = (
                    True
                    if key == "reputation_completion"
                    else row["selected_office_clause_applies"]
                )
                if condition is not None and type(condition) is not bool:
                    raise ValueError(
                        "Qi timing source context must be boolean or unknown"
                    )
                targets.append(
                    {
                        "selector_id": key,
                        "node": actual,
                        "selected_source_context_condition": condition,
                        "condition_fact_path": clause_path
                        + ".chapter_qualifications."
                        + (
                            "support_time_references"
                            if key == "reputation_completion"
                            else "office_qualification"
                        ),
                        "full_source_context_authenticated": False,
                    }
                )
        no_attacker = q["no_attacker_qualification"]
        has_attacker = any(r["relation"] == "用克体" for r in stages)
        if (
            no_attacker["body_time_reference"] is not None
        ) == has_attacker or no_attacker["full_source_clause_applies"] is not (
            False if has_attacker else None
        ):
            raise ValueError(
                "Qi body timing cannot borrow another cast's absence condition"
            )
        if no_attacker["body_time_reference"] is not None:
            targets.append(
                {
                    "selector_id": "reputation_body_without_attacker",
                    "node": by_role["body"],
                    "selected_source_context_condition": no_attacker[
                        "full_source_clause_applies"
                    ],
                    "condition_fact_path": clause_path
                    + ".chapter_qualifications.no_attacker_qualification",
                    "full_source_context_authenticated": False,
                }
            )
    else:
        raise ValueError(
            "Qi day timing selectors require the explicit wealth or reputation chapter"
        )
    return by_role, targets


def _reading(
    cast: dict[str, Any],
    layer: dict[str, Any],
    topic: str,
    *,
    fact_prefix: str,
    layer_path: str,
    clause_path: str,
) -> dict[str, Any] | None:
    day = layer.get("day_qi")
    if day is None:
        return None
    profile = _profile()
    by_role, targets = chapter_timing_targets(
        cast,
        layer,
        topic,
        fact_prefix=fact_prefix,
        clause_path=clause_path,
    )
    labels = []
    for index, candidate in enumerate(day["calendar_candidates"]):
        calendar = candidate["calendar"]
        if calendar["day_branch"] not in EARTHLY_BRANCHES or [
            r["role"] for r in candidate["roles"]
        ] != list(by_role):
            raise ValueError("Qi timing requires complete input-day role records")
        for row in candidate["roles"]:
            actual = by_role[row["role"]]
            if (row["trigram"], row["fact_path"]) != (
                actual["trigram"],
                actual["fact_path"],
            ):
                raise ValueError("Qi day roles must remain bound to their own cast")
        labels.append(
            {
                **deepcopy(calendar),
                "selected_input_day_label": calendar["id"]
                == day["selected_candidate_id"],
                "day_branch_fact_path": candidate["day_branch_fact_path"],
                "calendar_record_fact_path": f"{layer_path}.day_qi.calendar_candidates.{index}.calendar",
            }
        )
    if not labels or sum(row["selected_input_day_label"] for row in labels) != 1:
        raise ValueError("Qi timing requires the original selected input-day label")
    selectors = profile["chapter_selectors"]
    rows = []
    for target in targets:
        node = target["node"]
        atom = profile["literal_day_branch_atoms"][node["trigram"]]
        matches = [
            {
                "calendar_id": label["id"],
                "queried_date": label["date"],
                "day_branch": label["day_branch"],
                "day_boundary": label["day_boundary"],
                "day_branch_fact_path": label["day_branch_fact_path"],
                "selected_input_day_label": label["selected_input_day_label"],
                "literal_named_day_branch_atom_met": label["day_branch"]
                in atom["day_branches"],
                "full_source_timing_condition": None,
                "real_outcome": None,
            }
            for label in labels
        ]
        rows.append(
            {
                "selector_id": target["selector_id"],
                "source_rule": deepcopy(selectors[target["selector_id"]]),
                "role": node["role"],
                "trigram": node["trigram"],
                "relation_to_original_body": node["relation"],
                "trigram_fact_path": node["fact_path"] + ".name",
                "selected_source_context_condition": target[
                    "selected_source_context_condition"
                ],
                "condition_fact_path": target["condition_fact_path"],
                "full_source_context_authenticated": False,
                "literal_day_branch_atom": deepcopy(atom),
                "input_day_matches": matches,
                "boundary_changes_literal_atom_match": len(
                    {r["literal_named_day_branch_atom_met"] for r in matches}
                )
                > 1,
                "countercontrol_and_strength_combined_into_timing": False,
                "event_time": None,
            }
        )
    details = []
    for row in rows:
        states = "、".join(
            r["calendar_id"]
            + ("相符" if r["literal_named_day_branch_atom_met"] else "不符")
            for r in row["input_day_matches"]
        )
        condition_label = (
            "所列角色条件满足"
            if row["selected_source_context_condition"] is True
            else (
                "所列前提不成立"
                if row["selected_source_context_condition"] is False
                else "所列前提未定"
            )
        )
        details.append(
            f"{LABELS[row['role']]}{row['trigram']}明列日支{''.join(row['literal_day_branch_atom']['day_branches'])}（{states}；{condition_label}）"
        )
    summary = (
        "章句卦气日支另核："
        + ("；".join(details) if details else "所列范围没有这两类生体或克体目标角色")
        + "。仅核时序中明列的日支原子，不把月份、五行旺衰或其他数字类目代入；原文在任及完整无克体等前提另列，原子不符也不否定其他未解析条文。输入日界候选不是未来应期，不生成最近日期、成败、收支、处分或预测窗口。"
    )
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "ruleset": qi_day_atom_ruleset(),
        "topic": topic,
        "day_qi_fact_path": layer_path + ".day_qi",
        "input_calendar_labels": labels,
        "input_label_scope": "same_input_clock_or_caller_reported_day_not_future_date_search",
        "source_selected_role_references": rows,
        "literal_branch_membership_is_element_strength": False,
        "nonmembership_negates_full_source_condition": False,
        "other_time_atoms_and_full_source_synthesis": "not_adjudicated",
        "role_occurrences_are_independent_observations": False,
        "next_or_nearest_matching_day_selected": False,
        "candidate_event_dates": None,
        "event_time": None,
        "real_world_observation_window": None,
        "real_outcome": None,
        "independent_verified_observations": 0,
        "summary": summary,
    }


def apply_qi_day_timing_references(
    cast: dict[str, Any], interpretation: dict[str, Any]
) -> None:
    topic = interpretation["interpretation_topic"]
    if topic not in {"wealth", "reputation"} or interpretation.get("day_qi") is None:
        return
    main = _reading(
        cast,
        interpretation,
        topic,
        fact_prefix="meihua",
        layer_path="interpretation",
        clause_path="interpretation.topic_reading",
    )
    if main is None:
        return
    interpretation["topic_reading"]["qi_day_timing_reference"] = main
    interpretation["traditional_judgement"] += main["summary"]
    suffix = main["summary"]
    for index, row in enumerate(interpretation.get("casting_readings") or []):
        item = _reading(
            cast["counting_variants"][index],
            row,
            topic,
            fact_prefix=f"meihua.counting_variants.{index}",
            layer_path=f"interpretation.casting_readings.{index}",
            clause_path=f"interpretation.casting_readings.{index}.topic_clause",
        )
        if item is None:
            raise ValueError("Count candidate lost its own input day labels")
        row["topic_clause"]["qi_day_timing_reference"] = item
        row["traditional_judgement"] += item["summary"]
        suffix += (
            ("原数" if row["line_sum_basis"] == "raw_counts" else "卦序数")
            + "候选卦气日支另核："
            + item["summary"]
        )
    interpretation["comprehensive_judgement"] += suffix
