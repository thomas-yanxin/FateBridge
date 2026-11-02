"""Day/hour stem rules with unresolved day-Jia identities kept as candidates.

Literal day stems can be read directly. The selected excerpts do not establish
one universal substitution for day Jia, so candidate policies are compared but
never selected by a desired pattern or a known outcome.
"""

from __future__ import annotations

from typing import Any


def build_stem_context(
    board: dict[str, Any], *, leader: dict[str, str], source: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from fatebridge.core.metaphysics.qimen_calendar_tables import (
        QIMEN_FUHEAD_HEAVEN_STEM,
    )

    day_ganzhi, hour_ganzhi = board["day_ganzhi"], board["time_ganzhi"]
    day, hour = day_ganzhi[0], hour_ganzhi[0]
    palaces = [p for p in board["palaces"] if p["trigram"] != "中"]

    def comparisons(stem: str) -> dict[str, list[str]]:
        return {
            "hidden_day_stem": [
                p["name"]
                for p in palaces
                if "庚" in p["heaven_stems"] and stem in p["earth_stems"]
            ],
            "flying_day_stem": [
                p["name"]
                for p in palaces
                if stem in p["heaven_stems"] and "庚" in p["earth_stems"]
            ],
        }

    if day == "甲":
        candidates = [
            {
                "policy": "day_jia_own_six_instrument",
                "xun_head": day_ganzhi,
                "effective_stem": QIMEN_FUHEAD_HEAVEN_STEM[day_ganzhi],
            },
            {
                "policy": "current_hour_xun_six_instrument",
                "xun_head": leader["xun_head"],
                "effective_stem": leader["zhifu_heaven_stem"],
            },
        ]
        for candidate in candidates:
            candidate["candidate_matches"] = comparisons(candidate["effective_stem"])
            candidate["adopted"] = False
        day_context: dict[str, Any] = {
            "ganzhi": day_ganzhi,
            "literal_stem": day,
            "status": "unresolved_jia_identity",
            "effective_stem": None,
            "candidates": candidates,
            "adopted_candidate": None,
            "note": "所核原例对日甲及宫数有差异；仅比较日甲本身藏仪与时旬藏仪候选，不据匹配结果自动选法，也不据未正式输出格局判定不存在。",
        }
    else:
        day_context = {
            "ganzhi": day_ganzhi,
            "literal_stem": day,
            "status": "literal_stem_resolved",
            "effective_stem": day,
            "resolution_policy": "literal_day_stem",
            "evaluations": comparisons(day),
        }
    hour_stem = leader["zhifu_heaven_stem"] if hour == "甲" else hour
    context: dict[str, Any] = {
        "day": day_context,
        "hour": {
            "ganzhi": hour_ganzhi,
            "literal_stem": hour,
            "effective_stem": hour_stem,
            "resolution_policy": (
                "current_hour_xun_six_instrument"
                if hour == "甲"
                else "literal_hour_stem"
            ),
            "xun_head": leader["xun_head"],
        },
        "source": source,
        "sections": ["卷二·伏干格", "卷二·飞干格", "卷二·小隔并岁隔月隔日隔时隔"],
        "source_scan_pages": [29, 31],
        "day_jia_policy_automatically_selected": False,
        "real_world_efficacy": "not_tested",
    }
    result: list[dict[str, Any]] = []
    for index, palace in enumerate(board["palaces"]):
        if palace["trigram"] == "中":
            continue
        for rule_id, name, sky, earth, matched, section, pages, aliases in [
            (
                "hidden_day_stem",
                "伏干格",
                "庚",
                day,
                day != "甲"
                and "庚" in palace["heaven_stems"]
                and day in palace["earth_stems"],
                "卷二·伏干格／小隔并岁隔月隔日隔时隔·日格",
                [29, 31],
                ["日格", "日干格"],
            ),
            (
                "flying_day_stem",
                "飞干格",
                day,
                "庚",
                day != "甲"
                and day in palace["heaven_stems"]
                and "庚" in palace["earth_stems"],
                "卷二·飞干格",
                [31],
                [],
            ),
            (
                "hour_stem_block",
                "时格",
                "庚",
                hour_stem,
                "庚" in palace["heaven_stems"] and hour_stem in palace["earth_stems"],
                "卷二·小隔并岁隔月隔日隔时隔·时格",
                [29],
                ["伏吟格"],
            ),
        ]:
            if not matched:
                continue
            is_hour = rule_id == "hour_stem_block"
            identity = context["hour"] if is_hour else day_context
            result.append(
                {
                    "rule_id": rule_id,
                    "name": name,
                    "palace": palace["name"],
                    "facts": {
                        "heaven_stem": sky,
                        "earth_stem": earth,
                        "day_ganzhi": day_ganzhi,
                        "hour_ganzhi": hour_ganzhi,
                    },
                    "source": source,
                    "section": section,
                    "source_scan_pages": pages,
                    "evidence_paths": [
                        f"qimen.palaces.{index}",
                        (
                            "qimen.stem_context.hour"
                            if is_hour
                            else "qimen.stem_context.day"
                        ),
                    ],
                    "layer": "traditional_rule_match",
                    "traditional_meaning": "原文用于主客受制、推进受阻的传统象义；格局名称不证明现实阻碍、损失或人身后果。",
                    "qualification": {
                        "condition": (
                            "按本时干（甲按已声明时旬藏仪）核对庚加时干"
                            if is_hour
                            else "按实际非甲日干核对天地盘先后，不以时旬或日旬其他干替代"
                        ),
                        "condition_observed": True,
                        "blocking_rule_names": [],
                        "same_palace_conflicts": [],
                        "source_disagreements": list(
                            board.get("source_disagreements", [])
                        ),
                        "source_aliases": aliases,
                        "alias_scope": (
                            "本段时格的伏吟别称不改星伏吟或门伏吟字段"
                            if is_hour
                            else "同一干对的日格别称不计作额外证据"
                        ),
                        "stem_identity": dict(identity),
                        "shared_evidence_group": f"heaven:{sky}|earth:{earth}|palace:{palace['trigram']}",
                        "independent_outcome_evidence": False,
                        "overall_judgment": "requires_whole_board",
                        "outcome_inference_allowed": False,
                    },
                }
            )
    return context, result
