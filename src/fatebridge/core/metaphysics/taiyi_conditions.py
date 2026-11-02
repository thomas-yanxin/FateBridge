"""Volume-four conjunctions over the same board's evaluated relations.

The three 五將發 clauses are not a license to assert 三門具 or a real event.
In particular, a failed conjunction must keep every actual blocking relation,
and a passing conjunction must not turn an unevaluated gate rule into True.
"""

from __future__ import annotations

from typing import Any

from .taiyi_eye_relations import ANNOTATIONS, PROFILE, SCOPE

SOURCE = "https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷04#推五將發不發"
CLAUSES = (
    ("shiji_clear", "始击无掩击", {"始击"}, {"掩", "击"}),
    ("wenchang_clear", "文昌无囚迫", {"文昌"}, {"囚", "迫"}),
    (
        "generals_unconnected",
        "主客大小将无相关",
        {"主大将", "主参将", "客大将", "客参将"},
        {"关"},
    ),
)


def conjunction(*values: bool | None) -> bool | None:
    """A known blocker is decisive; missing evidence is never a positive."""
    if not values or any(v is not None and type(v) is not bool for v in values):
        raise ValueError("条件合取需要非空的布尔或未知值")
    if any(v is False for v in values):
        return False
    return None if any(v is None for v in values) else True


def update_conjunction(assessment: dict[str, Any]) -> None:
    """Keep each layer's status when composing gates and generals."""
    five = assessment["five_generals"]["conditions_satisfied"]
    gates = assessment["three_gates"].get("conditions_satisfied")
    combined = conjunction(five, gates)
    assessment["menju_jiangfa"] = combined
    words = {True: "满足", False: "不满足", None: "未定"}
    assessment["summary"] = (
        f"本盘所选五将三项{words[five]}，三门条件{words[gates]}；"
        f"两层合取{words[combined]}。未决事实与实际阻断分别保留，不推出实际成败。"
    )


def _unassessed_same_camp(core: dict[str, Any]) -> list[dict[str, Any]]:
    pending = []
    for camp, label in (("main", "主"), ("guest", "客")):
        fields = [camp + "_general", camp + "_vice_general"]
        if core[fields[0]] == core[fields[1]]:
            pending.append(
                {
                    "id": "same_camp_guan_scope_unadjudicated",
                    "subjects": [label + "大将", label + "参将"],
                    "basis": [
                        {"field": "core_board." + field, "value": core[field]}
                        for field in fields
                    ],
                    "reason": "同阵两将数齐；是否属于卷三关及卷四相关尚未裁定，不把未列关当作无关。",
                }
            )
    return pending


def five_general_conditions(
    patterns: list[dict[str, Any]], *, core: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Use same-core coverage and supplied relations; never recast positions.

    The old relation-list conjunction remains available as assessed_conditions.
    It cannot prove a negative about unadjudicated same-camp co-location.
    """
    fields = {
        "main_general",
        "main_vice_general",
        "guest_general",
        "guest_vice_general",
        "taiyi_palace",
        "wenchang_palace",
        "shiji",
    }
    has_core = (
        core is not None
        and fields.issubset(core)
        and all(core[field] is not None for field in fields)
    )
    missing = [
        {
            "id": "same_core_not_supplied",
            "subjects": [],
            "basis": [],
            "reason": "缺少同盘完整位置，只有已列关系不能证明未列关系均不存在。",
        }
    ]
    pending = _unassessed_same_camp(core) if has_core and core is not None else []
    clauses: list[dict[str, Any]] = []
    for key, label, subjects, names in CLAUSES:
        blockers = [
            {
                "source_path": f"taiyi.patterns.{i}",
                "name": p["name"],
                "subject": p["subject"],
                "variant": p["variant"],
            }
            for i, p in enumerate(patterns)
            if p["subject"] in subjects and p["name"] in names
        ]
        unknowns = (
            missing
            if not has_core
            else (pending if key == "generals_unconnected" else [])
        )
        clauses.append(
            {
                "id": key,
                "label": label,
                "assessed_satisfied": not blockers,
                "satisfied": False if blockers else (None if unknowns else True),
                "blockers": blockers,
                "unassessed": unknowns,
            }
        )
    satisfied = conjunction(*(c["satisfied"] for c in clauses))
    result = {
        "ruleset": {
            "id": "jinjing_vol4_five_general_conditions_v1",
            "version": "1.2.0",
            "author": "FateBridge contributors",
            "classical_author": "唐·王希明",
            "source": SOURCE,
            "conformance": "three_source_scoped_clauses_with_explicit_unknowns",
            "relation_profile": PROFILE,
            "relation_sources": list(ANNOTATIONS),
            "relation_scope": SCOPE,
            "coverage_policy": "same_core_co_location_checked_unknown_is_not_absence_v1",
        },
        "five_generals": {
            "assessed_conditions_satisfied": all(
                c["assessed_satisfied"] for c in clauses
            ),
            "conditions_satisfied": satisfied,
            "same_core_coverage_checked": has_core,
            "clauses": clauses,
        },
        "three_gates": {
            "status": "not_assessed",
            "conditions_satisfied": None,
            "reason": "本步骤只核对五将三项条件；三门由对应计法另行附门盘后评估，不借用奇门八门替代。",
        },
        "menju_jiangfa": None,
        "scope": "只核卷四三条所选空间读法，关含将目补证，掩含始击掩将；同阵数齐的关称名未决不算无关。已实现关系合取另存assessed_conditions_satisfied；完整结论三值合取，已知阻断优先。未决版本和主客算表异文仍适用，不推出实际成败。",
    }
    update_conjunction(result)
    return result


def conditions_text(assessment: dict[str, Any]) -> str:
    lines = [assessment["summary"]]
    for clause in assessment["five_generals"]["clauses"]:
        references = "、".join(
            f"{p['subject']}{p['variant']}（{p['source_path']}）"
            for p in clause["blockers"]
        )
        state = {True: "满足", False: "不满足", None: "未定"}[clause["satisfied"]]
        unresolved = "；".join(
            f"{'与'.join(p['subjects']) or '同盘位置'}：{p['reason']}"
            + (
                "（"
                + "、".join(f"{f['field']}={f['value']}" for f in p["basis"])
                + "）"
                if p["basis"]
                else ""
            )
            for p in clause["unassessed"]
        )
        lines.append(
            f"{clause['label']}：{state}"
            + (f"；实际阻断：{references}" if references else "")
            + (f"；未决：{unresolved}" if unresolved else "")
            + "。"
        )
    lines.append(assessment["scope"])
    return "\n".join(lines)
