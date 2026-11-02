"""Phase-specific, positional Yuanqi and Huagong facts from the named printing."""

from typing import Any

from fatebridge.core.heluo_opposition import opposition_evidence, opposition_snapshot
from fatebridge.core.heluo_seasonal import SOURCE_SHA256, SOURCE_URL

RULESET_ID = "heluo_wenming_phase_qi_v1"
LABELS = {
    "yuan_tian": "天元气",
    "yuan_di": "地元气",
    "fan_yuan_tian": "反天元气候选",
    "fan_yuan_di": "反地元气候选",
    "huagong": "化工",
    "fanhua": "反化工",
}


def phase_qi_evidence(
    bodies: list[dict[str, Any]],
    yuan: dict[str, str],
    fan_yuan: dict[str, str],
    hg: list[str],
    fh: list[str],
    solar: dict[str, Any] | None,
    *,
    year_ganzhi: str,
) -> dict[str, Any]:
    """Consume the actual eight bodies, never copy the phase union to each phase.

    Presence includes direct and nuclear bodies, with both classes separately
    identified. It is not the final judgment after counteraction or restraint.
    """
    opposition = opposition_evidence(year_ganzhi, bodies, yuan, fan_yuan)
    targets = {
        "yuan_tian": [yuan["tian"]],
        "yuan_di": [yuan["di"]],
        "fan_yuan_tian": [fan_yuan["tian"]],
        "fan_yuan_di": [fan_yuan["di"]],
        "huagong": hg[:],
        "fanhua": fh[:],
    }
    phases = []
    for phase in ("xian", "hou"):
        rows = [
            {
                **{key: row[key] for key in ("body_id", "gua", "kind", "trigram")},
                "line_positions": row["line_positions"][:],
            }
            for row in bodies
            if row["phase"] == phase
        ]
        facts = {}
        for kind, trigrams in targets.items():
            direct = [
                r["body_id"]
                for r in rows
                if r["kind"] in {"lower", "upper"} and r["trigram"] in trigrams
            ]
            nuclear = [
                r["body_id"]
                for r in rows
                if r["kind"] in {"lower_nuclear", "upper_nuclear"}
                and r["trigram"] in trigrams
            ]
            facts[kind] = {
                "trigrams": trigrams[:],
                "direct_body_ids": direct,
                "nuclear_body_ids": nuclear,
                "present": bool(direct or nuclear) if trigrams else None,
            }
        phases.append(
            {"phase": phase, "gua": rows[0]["gua"], "bodies": rows, "matches": facts}
        )
    transitions = []
    for kind in targets:
        a, b = (row["matches"][kind]["present"] for row in phases)
        status = (
            "not_evaluated"
            if a is None or b is None
            else "retained" if a and b else "lost" if a else "gained" if b else "absent"
        )
        transitions.append(
            {"kind": kind, "xian_present": a, "hou_present": b, "change": status}
        )
    return {
        "ruleset_id": RULESET_ID,
        "version": "1.0.0",
        "source_url": SOURCE_URL + "#page=34",
        "source_pdf_sha256": SOURCE_SHA256,
        "source_pdf_pages": [32, 33, 34, 35, 50, 51, 63],
        "candidate_basis": (
            solar.get("precision", "explicit_candidates_without_birth_instant")
            if solar is not None
            else "month_branch_approximation"
        ),
        "birth_instant_utc": (
            solar.get("anchor_utc")
            if solar is not None and solar.get("precision") == "birth_instant"
            else None
        ),
        "fanhua_rule_ids": (
            list(solar.get("fanhua_rule_ids", [])) if solar is not None else []
        ),
        "phases": phases,
        "transitions": transitions,
        "yuanqi_opposition": opposition,
        "complete_assessment": False,
        "scope": "先后天分别核对实际上下体及两互体，正逢与互体位置另列；聚合命中不替代单阶段事实。反化工成立不自动等于现实凶断。",
        "unresolved": [
            "土用的原典季月十八日与当前四立前连续十八日约定尚未完成版本裁定。",
            "第83页乙亥命例称乾为化工，与第34页按该例白露时节应取离的定义冲突；未用命例反改定义。",
            "未按气虚、制化、轻重及元堂等条件完成综合葉否；不得自动选定条文分支。",
        ],
    }


def phase_qi_snapshot(evidence: dict[str, Any]) -> str:
    lines = ["[先后天·元气化工分列]"]
    body_labels = {
        "lower": "下体",
        "upper": "上体",
        "lower_nuclear": "下互",
        "upper_nuclear": "上互",
    }
    for row in evidence["phases"]:
        phase = "先天" if row["phase"] == "xian" else "后天"
        bodies = {b["body_id"]: b for b in row["bodies"]}
        clauses = []
        for kind, match in row["matches"].items():
            ids = match["direct_body_ids"] + match["nuclear_body_ids"]
            detail = "、".join(
                f"{body_labels[bodies[i]['kind']]}{bodies[i]['trigram']}" for i in ids
            )
            status = (
                detail if ids else "无" if match["present"] is False else "候选未定"
            )
            clauses.append(f"{LABELS[kind]}{''.join(match['trigrams'])}：{status}")
        lines.append(f"{phase}·{row['gua']}：" + "；".join(clauses))
    lines.append("各项为实际卦体命中；先后天分开，综合葉否未定。")
    lines.extend(["", opposition_snapshot(evidence["yuanqi_opposition"])])
    return "\n".join(lines)
