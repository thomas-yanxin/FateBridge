"""Bounded structural facts under an explicit Zengshan Buyi rule profile.

Flags describe relations, not automatic judgments of success or failure.
In particular, 旬空 does not by itself imply 真空 and 日冲 is not automatically 暗动.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from .liuyao_relations import (
    _SOURCE_MANIFEST,
    ADVANCES,
)
from .liuyao_relations import BRANCHES as BRANCHES
from .liuyao_relations import COMBINES as COMBINES
from .liuyao_relations import CONTROLS as CONTROLS
from .liuyao_relations import ELEMENTS
from .liuyao_relations import GENERATES as GENERATES
from .liuyao_relations import SOURCES
from .liuyao_relations import STEMS as STEMS
from .liuyao_relations import branch_facts, element_relation, xunkong


def build_liuyao_evidence(
    *,
    day_ganzhi: str,
    month_branch: str,
    current_code: str,
    changed_code: str,
    lines: list[dict[str, Any]],
    hidden: list[dict[str, Any]],
    palace_element: str,
    moment: datetime,
    focus_line: int | None = None,
    focus_kinship: str | None = None,
    focus_kind: str | None = None,
    timing_days: int = 0,
    event_horizon: str | None = None,
) -> dict[str, Any]:
    # Kept lazy because the conditional layer reuses this module's pure
    # relation primitives; no conditional work runs during catalog loading.
    from .liuyao_judgment import build_conditional_analysis

    void = xunkong(day_ganzhi)
    day = day_ganzhi[1]
    rows = []
    trace = [
        {
            "rule_id": "palace_shiying_nazhi_kinship_six_gods",
            "fact_path": "lines",
            "inputs": {
                "current_code": current_code,
                "changed_code": changed_code,
                "day_ganzhi": day_ganzhi,
            },
            "sources": [SOURCES[n] for n in (3, 4, 5, 6, 7, 18)],
        }
    ]
    for line in lines:
        row = {
            "position": line["position"],
            "branch": line["branch"],
            **branch_facts(line["branch"], month_branch, day, void),
        }
        if line["change"]:
            old, new = line["branch"], line["changed_branch"]
            relation = element_relation(ELEMENTS[new], ELEMENTS[old])
            row["transformation"] = {
                "branch": new,
                "back_relation": {"生爻": "回头生", "克爻": "回头克"}.get(
                    relation, relation
                ),
                "advance": ADVANCES.get(old) == new,
                "retreat": ADVANCES.get(new) == old,
                **branch_facts(new, month_branch, day, void),
            }
            trace.append(
                {
                    "rule_id": "moving_line_back_relation_advance_retreat",
                    "fact_path": f"liuyao_evidence.lines.{line['position'] - 1}.transformation",
                    "inputs": {"original_branch": old, "changed_branch": new},
                    "sources": [SOURCES[7], SOURCES[29]],
                }
            )
        rows.append(row)
        trace.append(
            {
                "rule_id": "day_month_branch_relations",
                "fact_path": f"liuyao_evidence.lines.{line['position'] - 1}",
                "inputs": {
                    "branch": line["branch"],
                    "month_branch": month_branch,
                    "day_ganzhi": day_ganzhi,
                    "xunkong": void,
                },
                "sources": [
                    SOURCES[16],
                    SOURCES[17],
                    SOURCES[19],
                    SOURCES[20],
                    SOURCES[26],
                    SOURCES[27],
                ],
            }
        )
    for candidate in hidden:
        candidate["calendar_relations"] = branch_facts(
            candidate["branch"], month_branch, day, void
        )
        candidate["flying_to_hidden_relation"] = element_relation(
            ELEMENTS[candidate["flying_branch"]], ELEMENTS[candidate["branch"]]
        )
    trace.append(
        {
            "rule_id": "missing_kinship_hidden_candidates",
            "fact_path": "liuyao_evidence.hidden_spirits",
            "inputs": {
                "current_code": current_code,
                "visible_kinships": sorted({line["liuqin"] for line in lines}),
                "changed_kinships": sorted(
                    {line["changed_liuqin"] for line in lines if line["change"]}
                ),
            },
            "sources": [SOURCES[5], SOURCES[28]],
        }
    )
    conditional = build_conditional_analysis(
        lines=lines,
        hidden=hidden,
        month=month_branch,
        day_ganzhi=day_ganzhi,
        palace=palace_element,
        moment=moment,
        focus_line=focus_line,
        focus_kinship=focus_kinship,
        focus_kind=focus_kind,
        timing_days=timing_days,
        event_horizon=event_horizon,
    )
    trace.append(
        {
            "rule_id": "progression_four_clauses_and_explicit_horizon",
            "fact_path": "liuyao_evidence.conditional_analysis.lines",
            "inputs": {"event_horizon": event_horizon},
            "sources": sorted(
                {
                    row["progress_conditions"]["source_url"]
                    for row in conditional["lines"]
                    if row.get("progress_conditions")
                }
            ),
            "scope": "进退结构配对与当下条件分开；近事久远未指定不推断；季节无扶不等于无向外作用。",
        }
    )
    trace.append(
        {
            "rule_id": "activity_control_targets_and_injured_static_control",
            "fact_path": "liuyao_evidence.conditional_analysis.control_conditions",
            "inputs": {"month_branch": month_branch, "day_ganzhi": day_ganzhi},
            "sources": [conditional["control_conditions"]["source_url"]],
            "scope": "动静克制按对象及作用前提核对，受克静爻的向外克另审；不把同向关系或未决暗动读成实际控制。",
        }
    )
    trace.append(
        {
            "rule_id": "day_clash_break_fill_and_moving_scatter",
            "fact_path": "liuyao_evidence.conditional_analysis.clash_conditions",
            "inputs": {"month_branch": month_branch, "day_ganzhi": day_ganzhi},
            "sources": [conditional["clash_conditions"]["source_url"]],
            "scope": "静爻日破、暗动、冲空填实与明动散分别核对；日冲几何事实不直接当伤害。",
        }
    )
    trace.append(
        {
            "rule_id": "outgoing_generation_and_target_reception",
            "fact_path": "liuyao_evidence.conditional_analysis.generation_conditions",
            "inputs": {"month_branch": month_branch, "day_ganzhi": day_ganzhi},
            "sources": [conditional["generation_conditions"]["source_url"]],
            "scope": "本位回头生的向外生扶资格与受生爻空破无根另审，不以生源受日月克即删除生扶，也不以有生即删受伤。",
        }
    )
    trace.append(
        {
            "rule_id": "back_generation_support_for_original_actions",
            "fact_path": "liuyao_evidence.conditional_analysis.back_generation_conditions",
            "inputs": {"month_branch": month_branch, "day_ganzhi": day_ganzhi},
            "sources": [conditional["back_generation_conditions"]["source_url"]],
            "scope": "回头生及变爻空破门槛同次共用，原爻空破合绊与多动相克另审，日月反制事实不抹除。",
        }
    )
    trace.append(
        {
            "rule_id": "successive_generation_path_conditions",
            "fact_path": "liuyao_evidence.conditional_analysis.routing_conditions",
            "inputs": {"month_branch": month_branch, "day_ganzhi": day_ganzhi},
            "sources": [conditional["routing_conditions"]["source_url"]],
            "scope": "路径逐段与受生门槛合取，多条按或合并；资格匹配不代表直接克制消失或现实成败。",
        }
    )
    trace.append(
        {
            "rule_id": "current_void_fill_directed_control",
            "fact_path": "liuyao_evidence.conditional_analysis.control_conditions.void_fill_qualification",
            "inputs": {"month_branch": month_branch, "day_ganzhi": day_ganzhi},
            "sources": conditional["control_conditions"]["void_fill_qualification"][
                "source_urls"
            ],
            "scope": conditional["control_conditions"]["void_fill_qualification"][
                "scope"
            ],
        }
    )
    trace.append(
        {
            "rule_id": "partial_stage_query_knowledge",
            "fact_path": "liuyao_evidence.conditional_analysis.stage_knowledge",
            "inputs": {"month_branch": month_branch, "day_ganzhi": day_ganzhi},
            "sources": [
                conditional["stage_knowledge"]["source_url"].split("#")[0]
                + f"#page={p}"
                for p in (97, 99, 101)
            ],
            "scope": "本次阶段查询的已知、排除与缺表分别追踪；火表仍缺帝旺与绝，不把位置当效力。",
        }
    )
    trace.append(
        {
            "rule_id": "earth_cessation_independent_support_exception",
            "fact_path": "liuyao_evidence.conditional_analysis.cessation_conditions",
            "inputs": {"month_branch": month_branch, "day_ganzhi": day_ganzhi},
            "sources": [conditional["cessation_conditions"]["source_url"]],
            "scope": "绝位与土逢巳生扶例外分开；本项不循环证明巳已生土，不解除另有化克化破或宣称全局真绝。",
        }
    )
    trace.append(
        {
            "rule_id": "metal_si_day_growth_month_support",
            "fact_path": "liuyao_evidence.conditional_analysis.growth_conditions",
            "inputs": {"month_branch": month_branch, "day_ganzhi": day_ganzhi},
            "sources": [conditional["growth_conditions"]["source_url"]],
            "scope": "金逢巳日按独立月令生扶核对长生，原五行克关系保留；其他扶源及反制不据本项自动裁决。",
        }
    )
    moving_growth_contexts = [
        r["moving_support"]
        for r in conditional["growth_conditions"]["lines"]
        if "moving_support" in r
    ] + [
        r["reception"]["moving_support"]
        for r in conditional["hidden_conditions"]
        if "moving_support" in r.get("reception", {})
    ]
    if moving_growth_contexts:
        trace.append(
            dict(
                rule_id="metal_si_day_growth_moving_support",
                fact_path="liuyao_evidence.conditional_analysis.growth_conditions",
                inputs={"month_branch": month_branch, "day_ganzhi": day_ganzhi},
                sources=sorted(
                    {c["source_url"] for c in moving_growth_contexts}
                    | {
                        c["application_source_url"]
                        for c in moving_growth_contexts
                        if "application_source_url" in c
                    }
                ),
                source_sha256=moving_growth_contexts[0]["source_sha256"],
                proof_paths=[c["source_path"] for c in moving_growth_contexts],
                scope="分别核实际动土来源资格、排除被判断金爻的独立根与受方门槛；不由长生资格解除空破回头克或裁定现实成败。",
            )
        )
    moving_si_contexts = [
        r["moving_si"]
        for r in conditional["growth_conditions"]["lines"]
        if "moving_si" in r
    ]
    if moving_si_contexts:
        trace.append(
            dict(
                rule_id="metal_actual_moving_si_growth_qualification",
                fact_path="liuyao_evidence.conditional_analysis.growth_conditions.lines",
                inputs={"month_branch": month_branch, "day_ganzhi": day_ganzhi},
                sources=sorted({c["source_url"] for c in moving_si_contexts}),
                source_sha256=moving_si_contexts[0]["source_sha256"],
                proof_paths=[c["source_path"] for c in moving_si_contexts],
                scope="独立生扶、每一动巳来源及原克制许可分别核对；同版第85、97页合并效力未裁定，不以遇长生自动取消克制或断现实成败。",
            )
        )
    own_si_contexts = [
        r["own_changed_si"]
        for r in conditional["growth_conditions"]["lines"]
        if "own_changed_si" in r
    ]
    if own_si_contexts:
        trace.append(
            dict(
                rule_id="metal_actual_own_si_growth_qualification",
                fact_path="liuyao_evidence.conditional_analysis.growth_conditions.lines",
                inputs={"month_branch": month_branch, "day_ganzhi": day_ganzhi},
                sources=sorted(
                    {c["source_url"] for c in own_si_contexts}
                    | {c["admission_source_url"] for c in own_si_contexts}
                ),
                source_sha256=own_si_contexts[0]["source_sha256"],
                proof_paths=[c["source_path"] for c in own_si_contexts],
                scope="实际本位金化巳另核独立生扶与变支门槛；原生克关系保留，未核不写成已克或已生，不跨位使用变巳。",
            )
        )
    trace.append(
        {
            "rule_id": "si_yin_shen_scoped_growth_exclusion",
            "fact_path": "liuyao_evidence.conditional_analysis.penalty_conditions",
            "inputs": {"month_branch": month_branch, "day_ganzhi": day_ganzhi},
            "sources": [conditional["penalty_conditions"]["source_url"]],
            "scope": "同版三支条件与寅日生扶排除；刑的总作用未裁定，变支只按本位，不据三刑断现实结果。",
        }
    )
    trace.append(
        {
            "rule_id": "day_value_month_only_opposition_exception",
            "fact_path": "liuyao_evidence.conditional_analysis.month_break_conditions",
            "inputs": {"month_branch": month_branch, "day_ganzhi": day_ganzhi},
            "sources": [conditional["month_break_conditions"]["source_url"]],
            "scope": "原月破标记保留；当前同支日建只排除本项月令反制，其他明暗动克及回头克仍须独立核对。",
        }
    )
    for rule, path, chapters in (
        (
            "seasonal_activity_conditions",
            "conditional_analysis.lines",
            ("15又", "19", "22", "23", "26又1", "26又3", "29"),
        ),
        (
            "parent_only_transformation",
            "conditional_analysis.interaction_edges",
            ("14", "15"),
        ),
        ("explicit_focus_roles", "conditional_analysis.focus", ("8", "9", "28")),
        ("day_condition_windows", "conditional_analysis.timing_candidates", ("26又3",)),
    ):
        trace.append(
            {
                "rule_id": rule,
                "fact_path": "liuyao_evidence." + path,
                "inputs": {
                    "month_branch": month_branch,
                    "day_ganzhi": day_ganzhi,
                    "focus_line": focus_line,
                    "focus_kinship": focus_kinship,
                    "focus_kind": focus_kind,
                    "timing_days": timing_days,
                },
                "sources": [
                    conditional["source_revisions"][chapter]["source_url"]
                    for chapter in chapters
                ],
            }
        )
    trace.extend(
        [
            {
                "rule_id": "three_harmony_conditions",
                "fact_path": "liuyao_evidence.conditional_analysis.three_harmony",
                "inputs": {
                    "current_code": current_code,
                    "changed_code": changed_code,
                    "month_branch": month_branch,
                    "day_ganzhi": day_ganzhi,
                },
                "sources": [conditional["three_harmony"]["source_url"]],
            },
            {
                "rule_id": "hidden_support_conditions",
                "fact_path": "liuyao_evidence.conditional_analysis.hidden_conditions",
                "inputs": {"focus_kind": focus_kind, "focus_line": focus_line},
                "sources": [
                    conditional["classical_scan"]["source"]["url"] + "#page=110",
                    conditional["classical_scan"]["source"]["url"] + "#page=111",
                ],
            },
            {
                "rule_id": "role_condition_effects",
                "fact_path": "liuyao_evidence.conditional_analysis.role_effects",
                "inputs": {
                    "focus_kind": focus_kind,
                    "focus_line": focus_line,
                    "focus_kinship": focus_kinship,
                },
                "sources": [conditional["role_effects"]["source_url"]],
            },
            {
                "rule_id": "grounded_strength_and_tombs",
                "fact_path": "liuyao_evidence.conditional_analysis.classical_assessment",
                "inputs": {"month_branch": month_branch, "day_ganzhi": day_ganzhi},
                "sources": [conditional["classical_assessment"]["source_url"]],
            },
            {
                "rule_id": "void_conditions_and_outgoing_obstructions",
                "fact_path": "liuyao_evidence.conditional_analysis.void_conditions",
                "inputs": {"month_branch": month_branch, "day_ganzhi": day_ganzhi},
                "sources": [conditional["void_conditions"]["source_url"]],
            },
        ]
    )
    return {
        "ruleset_id": "zengshan_structural_v1",
        "ruleset_version": "1.18.0",
        "source_kind": "classical_transcription_with_selected_scan_collation_and_explicit_engine_conventions",
        "conformance_scope": "装卦、世应、六亲、六神、动变及日月支关系的结构层；非全书断法认证",
        "calendar_conventions": {
            "cast_at": moment.isoformat(),
            "year_boundary": "立春",
            "month_boundary": "十二节交接瞬间，非农历初一或中气",
            "day_boundary": "当地时钟23:00换干支日，沿用共享历法约定",
            "clock": "输入时区的民用时间；不作真太阳时修正",
            "month_branch": month_branch,
            "day_ganzhi": day_ganzhi,
            "xunkong": void,
        },
        "lines": rows,
        "conditional_analysis": conditional,
        "hidden_spirits": hidden,
        "hidden_policy": "仅在本卦及实际变爻均未现该六亲时列本宫纯卦同位的伏神候选；取用位置须区分本爻、变爻、日月及伏神",
        "rule_trace": trace,
        "sources": list(
            dict.fromkeys(
                [*SOURCES.values(), conditional["classical_scan"]["source"]["url"]]
            )
        ),
        "source_revisions": deepcopy(_SOURCE_MANIFEST["sources_by_chapter"]),
        "textual_corrections": list(_SOURCE_MANIFEST["corrections"]),
        "pattern_detection_scope": "六冲六合为静态卦表；fanfu分列底本明示卦体例、内外卦盘纳支与实际动爻的反伏。卦盘比较不使静爻成为变爻，未列卦体不视为已经排除反伏，效力须另审旺衰回头冲克",
        "pending_judgments": [
            "用神须结合所问对象及一事一问确认，不能只靠关键词强选",
            "月令、暗动、合绊、墓绝、进退及空不空的分支已有条件证据；旬内旬外、破而不破及最终有效性仍须综合裁定",
            "三合路径及伏神支持阻碍已逐项取证；用神总旺衰、出伏与应期的完整裁定尚未完成",
            "有根生扶与三墓的明确分支已有裁定；扶克并见、日墓冲开作用域及总旺衰仍须保留未知，不能扩成全局吉凶",
            "本卦与变卦格局不能直接当成现实事件成败",
        ],
        "prediction_validation": {
            "status": "not_established",
            "real_world_sample_count": 0,
            "scope": "本规则集未登记独立前瞻样本；原典例证和软件测试不计为现实验证",
        },
    }
