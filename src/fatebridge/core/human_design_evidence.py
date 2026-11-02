"""Source scope and field-grounded paraphrases, not licensed line readings."""

from typing import Any, Dict

from fatebridge.core.human_design_birth_clock import birth_clock_reading
from fatebridge.core.human_design_bridging import bridging_reading, definition_bridging
from fatebridge.core.human_design_circuit_topology import (
    audit_archival_channel_pages,
    topology_reading,
    topology_reference,
)
from fatebridge.core.human_design_circuitry import (
    audit_channel_circuits,
    audit_circuit_groups,
)
from fatebridge.core.human_design_classification import authority_structure_text
from fatebridge.core.human_design_cross_coverage import (
    expanded_cross_evidence,
    expanded_cross_reading,
)
from fatebridge.core.human_design_depth import depth_evidence, fixing_summary_reading
from fatebridge.core.human_design_gate_context import add_gate_context_evidence
from fatebridge.core.human_design_historical_polarity import (
    add_historical_polarity_evidence,
)
from fatebridge.core.human_design_interval_summary import interval_reading
from fatebridge.core.human_design_mechanics import (
    CENTER_GATES,
    CHANNELS,
    GATE_CENTER,
    GATE_ORDER,
    MOTORS,
    RULESET_ID,
    RULESET_VERSION,
)
from fatebridge.core.human_design_node_comparisons import (
    NODE_SOURCE,
    node_comparison_reading,
)
from fatebridge.core.human_design_personality_color import personality_color_reading
from fatebridge.core.human_design_primary_diagrams import (
    primary_diagram_evidence,
    primary_diagram_reading,
)
from fatebridge.core.human_design_profile import (
    profile_brief,
    profile_evidence,
    profile_reading,
)
from fatebridge.core.human_design_profile_partition import (
    add_profile_partition_evidence,
)
from fatebridge.core.human_design_references import reference_data
from fatebridge.core.human_design_source_variants import (
    cross_name_evidence,
    discrepancy_reading,
    line_variant_impact,
    source_variant_audit,
)

SOURCE_URLS = {
    "rave_2001": "https://www.myhumandesign.be/downloads/Rave-I%27Ching.pdf",
    "solar_arc": "https://jovianarchive.com/blogs/human-design-basics/introduction-to-the-human-design-system",
    "mandala": "https://jovianarchive.com/pages/the-mandala-and-the-bodygraph-in-human-design",
    "dictionary": "https://jovianarchive.com/pages/human-design-dictionary",
    "definition": "https://jovianarchive.com/pages/understanding-definition-in-human-design",
    "profile": "https://jovianarchive.com/pages/understanding-profile-in-human-design",
    "ego_manifested": "https://jovianarchive.com/pages/ego-manifested-authority-in-human-design-the-will-that-speaks",
    "ego_projected": "https://jovianarchive.com/pages/ego-projected-authority-in-human-design-willpower-and-invitations",
    "mental": "https://jovianarchive.com/pages/mental-authority-in-human-design-a-projector-process",
    "substructure": "https://jovianarchive.com/pages/the-basics-of-substructure-in-human-design",
    "ephemeris": "https://www.astro.com/swisseph/swephprg.htm",
    "node_mechanics": "https://www.astro.com/swisseph/swisseph.htm",
    "historical_utc": "https://hpiers.obspm.fr/eoppc/bul/bulc/UTC-TAI.history",
    "historical_utc_1960": "https://www.iausofa.org/2023-10-11c",
    "fixing": "https://jovianarchive.com/blogs/chart-interpretations-components/line-fixing-in-human-design-exaltation-detriment-and-juxtaposition",
    "ra_1997": "https://humandesignsystem.com/archive/newsletters/0402.pdf",
    "circuitry": "https://jovianarchive.com/pages/what-is-circuitry-in-human-design",
    "integration": "https://jovianarchive.com/blogs/chart-interpretations-components/keynoting-stephen-kings-design-part-2",
    "variable": "https://jovianarchive.com/blogs/deeper-mechanics-system-theory/a-simple-guide-to-variable",
}


def source_reference() -> Dict[str, Any]:
    return reference_data("rave-2001-reference.json")


def reference_table_audit() -> Dict[str, Any]:
    """Compare implementation tables to independently transcribed source facts.

    Keep discrepancies, including printed internal inconsistencies, visible.
    An acknowledged discrepancy does not count as a passed source assertion.
    """
    reference = source_reference()
    center_names = {
        "Head": "head",
        "Ajna": "ajna",
        "Throat": "throat",
        "G": "g",
        "Heart": "ego",
        "Spleen": "spleen",
        "Sacral": "sacral",
        "Solar Plexus": "solar_plexus",
        "Root": "root",
    }
    gates_passed = centers_passed = lines_passed = 0
    discrepancies = []
    for row in reference["gates"]:
        gate = row["gate"]
        start = (302 + GATE_ORDER.index(gate) * 5.625) % 360
        end = (start + 5.625) % 360
        gates_passed += row["start_longitude"] == start and row["end_longitude"] == end
        centers_passed += GATE_CENTER[gate] == center_names[row["center"]]
        for line in row["lines"]:
            expected = {
                "start_longitude": (start + (line["line"] - 1) * 0.9375) % 360,
                "end_longitude": (start + line["line"] * 0.9375) % 360,
            }
            if all(
                abs((line[k] - v + 180) % 360 - 180) < 1e-10
                for k, v in expected.items()
            ):
                lines_passed += 1
            else:
                discrepancies.append(
                    {
                        "gate": gate,
                        "line": line["line"],
                        "printed_range": {k: line[k] for k in expected},
                        "implemented_uniform_range": expected,
                        "pdf_page_one_based": row["pdf_pages_one_based"][1],
                        "resolution": "unresolved_source_discrepancy_uniform_56m15s_rule_retained",
                    }
                )
    source_channels = {
        tuple(pair) for row in reference["gates"] for pair in row["channels"]
    }
    channels = {tuple(sorted((a, b))) for a, b, _ in CHANNELS}
    complete = sorted(row["gate"] for row in reference["gates"]) == list(range(1, 65))
    structural_match = (
        complete
        and gates_passed == centers_passed == 64
        and source_channels == channels
    )
    line_count = sum(len(row["lines"]) for row in reference["gates"])
    return {
        "status": (
            "numeric_table_mismatch"
            if not structural_match or line_count != 384
            else (
                "unresolved_source_discrepancies"
                if discrepancies
                else "bounded_numeric_table_match"
            )
        ),
        "gate_ranges_matched": gates_passed,
        "gate_ranges_checked": len(reference["gates"]),
        "centers_matched": centers_passed,
        "channel_pairs_matched": len(source_channels & channels),
        "channel_pair_sets_equal": source_channels == channels,
        "channel_classifications": audit_channel_circuits(CHANNELS, reference["gates"]),
        "archival_channel_pages": audit_archival_channel_pages(
            CHANNELS, reference["gates"], MOTORS
        ),
        "circuit_group_memberships": audit_circuit_groups(CHANNELS),
        "line_ranges_matched": lines_passed,
        "line_ranges_checked": line_count,
        "discrepancies": discrepancies,
        "source_pdf_sha256": reference["source"]["pdf_sha256"],
        "source_url": SOURCE_URLS["rave_2001"],
        "full_text_acceptance_passed": False,
        "numeric_table_acceptance_passed": structural_match
        and lines_passed == line_count == 384,
        "scope": "数值表局部核对；未核验384线全部义理、擢升落陷、所有交叉名称或现实效力。",
    }


TYPE_MEANINGS = {
    "generator": "在人类图体系中，生产者以回应具体机会作为策略；显示生产者仍归属于生产者。",
    "manifestor": "在人类图体系中，显示者采用行动前告知受影响者的策略。",
    "projector": "在人类图体系中，投射者重视被认可与适当邀请，尤其用于重要关系及角色选择。",
    "reflector": "在人类图体系中，反映者的重要决定采用观察一个月亮周期的策略。",
}
AUTHORITY_MEANINGS = {
    "emotional": "情绪权威在该体系中优先于其他已定义中心，强调等待情绪过程后再判断。",
    "sacral": "骶骨权威在该体系中指向当下对具体问题的回应。",
    "splenic": "脾权威在该体系中指向当下短促的直觉觉察。",
    "ego_manifested": "意志显现权威在该体系中通过意志至喉的连接表达想要与承诺。",
    "ego_projected": "意志投射权威由意志至G中心的连接支持，并遵守投射者的认可与邀请策略。",
    "self_projected": "自我投射权威在该体系中通过G中心至喉的表达听见自身方向。",
    "environment_no_inner_authority": "这是无内在权威的心理投射者过程；该体系强调环境与谈话中的自我听见，不能称为头脑内在权威。",
    "lunar_no_inner_authority": "反映者没有固定内在权威；该体系使用月亮周期观察过程。",
}


def source_activation_impacts(chart: Dict[str, Any]) -> Dict[str, Any]:
    """Locate actual activations affected by the unchanged printed line table.

    This compares numerical interval membership only. An unaffected chart does
    not resolve the source discrepancy or certify the source's full contents.
    """
    return line_variant_impact(chart)


def evidence(
    chart: Dict[str, Any],
    *,
    include_gate_context: bool = True,
    include_profile_partition: bool = True,
    include_historical_polarity: bool = True,
) -> Dict[str, Any]:
    graph = chart["bodygraph"]
    bridges = definition_bridging(graph)
    profile = profile_evidence(chart)
    consistency = {
        **reference_table_audit(),
        "activation_impacts": source_activation_impacts(chart),
        "version_comparison": source_variant_audit(),
        "cross_name_comparison": cross_name_evidence(chart),
        "expanded_cross_name_comparison": expanded_cross_evidence(chart),
        "primary_transcript_diagrams": primary_diagram_evidence(chart),
    }
    chart = {
        **chart,
        "definition_bridging": bridges,
        "profile_evidence": profile,
        "source_consistency": consistency,
    }
    depth = depth_evidence(chart)
    source_summary = {
        "ruleset_id": RULESET_ID,
        "version": RULESET_VERSION,
        "author": "FateBridge implementation; source author Ra Uru Hu; publisher Jovian Archive Corporation",
        "source_kind": "primary_2001_numeric_tables_and_official_public_teaching",
        "primary_source_url": SOURCE_URLS["rave_2001"],
        "official_observations_url": "https://jovianarchive.com/pages/get-your-human-design-chart",
        "scope": "2001原典的门位、中心、通道、线界仅局部核对；29.1/29.2印刷界未决，保留等分。完整解释与官方整盘符合性未验收。",
        "full_source_acceptance_passed": False,
        "complete_source_list_path": "rulesets",
    }
    result = {
        "source_summary": source_summary,
        "definition_bridging": bridges,
        "depth_evidence": depth,
        "profile_evidence": profile,
        "source_consistency": consistency,
        "gate_evidence": [
            {
                "gate": row["gate"],
                "source_center": row["center"],
                "source_gate_circuit_label": row["gate_circuit_label"],
                "source_channel_pairs": [list(pair) for pair in row["channels"]],
                "source_pdf_pages_one_based": list(row["pdf_pages_one_based"]),
            }
            for row in source_reference()["gates"]
            if row["gate"] in graph["activated_gates"]
        ],
        "rulesets": [
            {
                "id": RULESET_ID,
                "author": "FateBridge implementation; source author Ra Uru Hu; publisher Jovian Archive Corporation",
                "version": RULESET_VERSION,
                "source_kind": "primary_2001_numeric_tables_and_official_public_teaching",
                "sources": dict(SOURCE_URLS),
                "scope": "2001原典的门位、中心、通道、线界仅局部核对；29.1/29.2印刷界未决，保留等分。完整解释与官方整盘符合性未验收。",
            }
        ],
        "rule_trace": [
            {
                "rule_id": "design_solar_arc",
                "ruleset_id": RULESET_ID,
                "inputs": {"birth_utc": chart["birth_utc"]},
                "result": {"design_utc": chart["design_utc"], **chart["design_solver"]},
                "source_url": SOURCE_URLS["solar_arc"],
            },
            {
                "rule_id": "definition_from_completed_channels",
                "ruleset_id": RULESET_ID,
                "inputs": {"activated_gates": graph["activated_gates"]},
                "result": {
                    "channels": [c["id"] for c in graph["channels"]],
                    "components": graph["definition"]["components"],
                },
                "source_url": SOURCE_URLS["definition"],
            },
            {
                "rule_id": "type_and_authority_priority",
                "ruleset_id": RULESET_ID,
                "inputs": {
                    "defined_centers": [
                        k
                        for k in CENTER_GATES
                        if k in graph["centers"]
                        and graph["centers"][k]["status"] == "defined"
                    ],
                    "motor_to_throat": graph["motor_to_throat"],
                    "complete_channel_ids": [c["id"] for c in graph["channels"]],
                },
                "result": {
                    "type": graph["type"],
                    "subtype": graph["subtype"],
                    "authority": graph["authority"],
                    "classification_evidence": graph["classification_evidence"],
                },
                "source_url": SOURCE_URLS["dictionary"],
            },
            {
                "rule_id": "profile_personality_then_design_sun_line",
                "ruleset_id": RULESET_ID,
                "inputs": {
                    side: next(a["line"] for a in values if a["body"] == "Sun")
                    for side, values in chart["activations"].items()
                },
                "result": {"profile": chart["profile"]},
                "source_url": SOURCE_URLS["profile"],
            },
            {
                "rule_id": "primary_2001_cross_identifier",
                "ruleset_id": RULESET_ID,
                "inputs": {
                    "personality_sun_gate": chart["incarnation_cross"]["gates"][0],
                    "angle": chart["incarnation_cross"]["angle"],
                },
                "result": {
                    key: chart["incarnation_cross"][key]
                    for key in ("name", "name_status", "source_pdf_page_one_based")
                },
                "source_url": SOURCE_URLS["rave_2001"],
            },
            {
                "rule_id": "natal_line_fixing_same_gate_and_harmonic",
                "ruleset_id": RULESET_ID,
                "inputs": {"activation_path": "activations"},
                "result": {
                    "evidence_path": "depth_evidence.line_fixings",
                    "activation_count": len(depth["line_fixings"]),
                    "fixing_summary": depth["fixing_summary"],
                    "fixing_policy": depth["fixing_policy"],
                    "status_counts": {
                        status: sum(
                            a["status"] == status for a in depth["line_fixings"]
                        )
                        for status in sorted(
                            {a["status"] for a in depth["line_fixings"]}
                        )
                    },
                },
                "source_url": SOURCE_URLS["fixing"],
            },
            {
                "rule_id": "four_variable_arrows_from_paired_activation_tones",
                "ruleset_id": RULESET_ID,
                "inputs": {"activation_path": "activations"},
                "result": {
                    "code": chart["variables"]["code"],
                    "status": chart["variables"]["status"],
                    "evidence_path": "variables.arrows",
                },
                "source_url": SOURCE_URLS["variable"],
            },
            {
                "rule_id": "completed_channel_circuitry_and_separate_integration",
                "ruleset_id": RULESET_ID,
                "inputs": {"channel_ids": [ch["id"] for ch in graph["channels"]]},
                "result": {
                    "group_channel_counts": graph["circuitry"]["group_channel_counts"],
                    "integration": graph["circuitry"]["integration"],
                },
                "source_url": SOURCE_URLS["dictionary"],
            },
            {
                "rule_id": "minimum_distinct_gate_bridge_sets",
                "ruleset_id": RULESET_ID,
                "inputs": {
                    "activated_gates": graph["activated_gates"],
                    "original_components": graph["definition"]["components"],
                },
                "result": {
                    "status": bridges["status"],
                    "minimum_added_gate_count": bridges["minimum_added_gate_count"],
                    "minimum_solution_count": bridges["minimum_solution_count"],
                    "evidence_path": "definition_bridging",
                },
                "source_url": SOURCE_URLS["definition"],
            },
        ],
        "interpretation": {
            **(
                {
                    "birth_interval_meaning": interval_reading(
                        chart["time_sensitivity"]["summary"]
                    )
                }
                if "time_sensitivity" in chart
                else {}
            ),
            **(
                {"node_comparison_meaning": node_comparison_reading(chart)}
                if "node_convention_comparison" in chart
                else {}
            ),
            **(
                {
                    "birth_clock_meaning": birth_clock_reading(
                        chart["birth_clock_evidence"]
                    )
                }
                if chart.get("birth_clock_evidence") is not None
                else {}
            ),
            "reading_policy": "human_design_source_bound_statements_v1",
            "time_scope": "盘面解释针对名义出生时刻；有生时范围时另读time_sensitivity的联合快照，桥接门集、线固定与四箭头须取自同一见证。同格多依赖变化会细查，未分开区间见joint_transition_refinement_summary。门数或方案数量相同不代表门集不变；不能扩为连续区间稳定，也不能跨样本拼接。",
            "ephemeris_scope": "先核对ephemeris_backend_comparison的整盘重排，再读node_backend_comparison同TT仅替换节点及交点约定差异。整盘参考重算自身设计时刻，桥接、线固定与四箭头取同一联合快照。不确定性不限于节点；所选结果不能称无条件确定，后端吻合不是独立认证，差值不是误差上界。",
            "variables_meaning": variable_reading(chart["variables"]),
            "personality_color_meaning": personality_color_reading(
                chart["variables"]["personality_colors"],
                chart.get("node_convention_comparison"),
            ),
            "design_time_precision_meaning": design_time_reading(chart),
            "line_fixing_meaning": fixing_summary_reading(depth),
            "source_discrepancy_meaning": discrepancy_reading(
                consistency["activation_impacts"], consistency["cross_name_comparison"]
            ),
            "expanded_cross_name_meaning": expanded_cross_reading(
                consistency["expanded_cross_name_comparison"]
            ),
            "statements": reading_statements(chart),
            "type_meaning": TYPE_MEANINGS[graph["type"]],
            "authority_meaning": AUTHORITY_MEANINGS[graph["authority"]],
            "authority_structure": authority_structure_text(
                graph["classification_evidence"]
            ),
            "definition_meaning": "定义描述完整通道连接的中心群；未定义或完全开放不等于心理缺陷，单门激活不构成中心定义。",
            "definition_structure": bridging_reading(bridges),
            "circuitry_meaning": circuitry_reading(graph),
            "circuit_topology_meaning": topology_reading(
                graph["circuitry"]["topology_completion"]
            ),
            "profile_meaning": profile_brief(profile),
            "basis": [
                "bodygraph.type",
                "bodygraph.subtype",
                "bodygraph.authority",
                "bodygraph.classification_evidence",
                "bodygraph.definition.components",
                "definition_bridging",
                "bodygraph.circuitry",
                "bodygraph.circuitry.topology_completion",
                "profile",
                "profile_evidence",
                "activations",
                "variables",
                "design_solver.numerical_precision",
                "depth_evidence.line_fixings",
                "depth_evidence.fixing_summary",
                "depth_evidence.fixing_policy",
                "source_consistency.expanded_cross_name_comparison",
            ],
            "reality_check": "可自愿记录具体决策、行动与外部结果作反思；重大决定仍结合事实、约束与专业意见。没有把门线或策略解释为已验证的神经、遗传或医学机制。",
        },
        "validation": {
            "calendar": "swiss_ephemeris_with_explicit_time_and_backend_conventions",
            "classical": "primary_2001_numeric_tables_partial_with_unresolved_discrepancy",
            "classical_acceptance_passed": False,
            "interpretation": "deterministic_field_grounded_paraphrases_not_free_text_semantic_certification",
            "prediction": "not_validated",
            "real_world_sample_size": 0,
            "authority_certified": False,
            "all_four_axes_full_marks": False,
            "all_three_axes_full_marks": False,
            "limitations": [
                "Swiss核对原19盘及新增193盘，含四分定义与192个门角组合；未认证全部生时和交点口径。原15项及新86项名称失败、Moshier细分超差、29.1/29.2印刷分界均保留。",
                "Color/Tone/Base 仅表示黄经细分，出生秒数和星历误差可改变结果；不据此给饮食、治疗或健康处方。",
                "交点是轨道数学要素；官方报告Moshier真交点与JPL推导值最大差异约70角秒，超过Base的18.75角秒宽度。这是发布者的近似后端差异，不是每盘误差上界；物理天体JPL对照不能替代节点细分认证。",
                "Moshier物理天体也可能跨线界，不能仅据节点比较认证其他激活；整盘后端比较重算自身设计TT。有限独立天文参考和当前差值均不提供全时域精度界。",
                "已提供384线极性星体、192个交叉名称和四箭头数值汇总；完整线义、PHS、DreamRave、合盘和流运尚未实现。",
                "回归测试与JPL天文对照不证明人格解释、量子/中微子机制或现实预测有效。",
            ],
        },
    }
    if include_gate_context:
        result = add_gate_context_evidence(chart, result)
    if include_profile_partition:
        result = add_profile_partition_evidence(chart, result)
    if include_historical_polarity:
        result = add_historical_polarity_evidence(chart, result)
    return result


def reading_statements(chart: Dict[str, Any]) -> list[Dict[str, Any]]:
    """Bound each returned interpretation to exact calculation fields.

    Fixed templates are explicitly scoped; this is not a free-text LLM grader.
    """
    graph = chart["bodygraph"]
    type_names = {
        "generator": "生产者",
        "manifestor": "显示者",
        "projector": "投射者",
        "reflector": "反映者",
    }
    type_name = (
        "显示生产者（生产者子型）"
        if graph["subtype"] == "manifesting_generator"
        else type_names[graph["type"]]
    )
    authority_names = {
        "emotional": "情绪权威",
        "sacral": "骶骨权威",
        "splenic": "脾权威",
        "ego_manifested": "意志显现权威",
        "ego_projected": "意志投射权威",
        "self_projected": "自我投射权威",
        "environment_no_inner_authority": "环境／讨论过程，无内在权威",
        "lunar_no_inner_authority": "月亮过程，无内在权威",
    }
    profile = chart.get("profile_evidence") or profile_evidence(chart)
    source_impacts = source_activation_impacts(chart)
    source_names = cross_name_evidence(chart)
    definitions = {
        "none": "无定义",
        "single": "单一定义",
        "split": "二分定义",
        "triple_split": "三分定义",
        "quadruple_split": "四分定义",
    }

    def statement(
        key: str, text: str, facts: Dict[str, Any], sources: list[str]
    ) -> Dict[str, Any]:
        return {
            "id": key,
            "text": text,
            "basis": [{"path": path, "value": value} for path, value in facts.items()],
            "source_urls": sources,
        }

    node_statements = []
    if "node_convention_comparison" in chart:
        convention = chart["node_convention_comparison"]
        backend = chart["node_backend_comparison"]
        node_statements.append(
            statement(
                "node_comparisons",
                node_comparison_reading(chart),
                {
                    "node_convention_comparison.selected": convention["selected"],
                    "node_convention_comparison.alternative": convention["alternative"],
                    "node_convention_comparison.changed_activations": convention[
                        "changed_activations"
                    ],
                    "node_backend_comparison.status": backend["status"],
                    "node_backend_comparison.rows": backend["rows"],
                },
                [NODE_SOURCE],
            )
        )
    interval_statements = []
    if "time_sensitivity" in chart:
        summary = chart["time_sensitivity"]["summary"]
        interval_statements.append(
            statement(
                "birth_interval",
                interval_reading(summary),
                {"time_sensitivity.summary": summary},
                [],
            )
        )
    return (
        (
            [
                statement(
                    "birth_clock",
                    birth_clock_reading(chart["birth_clock_evidence"]),
                    {
                        "birth_clock_evidence": chart["birth_clock_evidence"],
                        "birth_utc": chart["birth_utc"],
                        "time_scales.personality.jd_tt": chart["time_scales"][
                            "personality"
                        ]["jd_tt"],
                    },
                    [chart["birth_clock_evidence"]["source_url"]],
                )
            ]
            if chart.get("birth_clock_evidence") is not None
            else []
        )
        + [
            statement(
                "type",
                f"本次类型为{type_name}。{TYPE_MEANINGS[graph['type']]}",
                {
                    "bodygraph.type": graph["type"],
                    "bodygraph.subtype": graph["subtype"],
                },
                [SOURCE_URLS["dictionary"]],
            ),
            statement(
                "authority",
                f"本次为{authority_names[graph['authority']]}。{AUTHORITY_MEANINGS[graph['authority']]}"
                + authority_structure_text(graph["classification_evidence"]),
                {
                    "bodygraph.authority": graph["authority"],
                    "bodygraph.classification_evidence": graph[
                        "classification_evidence"
                    ],
                },
                [SOURCE_URLS["dictionary"]]
                + (
                    [SOURCE_URLS[graph["authority"]]]
                    if graph["authority"] in {"ego_manifested", "ego_projected"}
                    else (
                        [SOURCE_URLS["mental"]]
                        if graph["authority"] == "environment_no_inner_authority"
                        else []
                    )
                ),
            ),
            statement(
                "definition",
                f"本次为{definitions[graph['definition']['kind']]}，共有{len(graph['definition']['components'])}组由完整通道连接的中心。分组不表示人的完整程度或能力高低。"
                + bridging_reading(chart["definition_bridging"]),
                {
                    "bodygraph.definition.kind": graph["definition"]["kind"],
                    "bodygraph.definition.components": [
                        list(group) for group in graph["definition"]["components"]
                    ],
                    **{
                        "definition_bridging." + key: chart["definition_bridging"][key]
                        for key in (
                            "status",
                            "original_component_count",
                            "minimum_added_gate_count",
                            "minimum_solution_count",
                        )
                    },
                },
                [SOURCE_URLS["definition"]],
            ),
            statement(
                "circuitry",
                circuitry_reading(graph),
                {
                    "bodygraph.channels": graph["channels"],
                    "bodygraph.circuitry": graph["circuitry"],
                },
                [
                    SOURCE_URLS["circuitry"],
                    SOURCE_URLS["integration"],
                    SOURCE_URLS["dictionary"],
                    topology_reference()["source"]["url"],
                ],
            ),
            statement(
                "profile",
                profile_reading(profile),
                {"profile": chart["profile"], "profile_evidence": profile},
                profile["source_urls"],
            ),
            statement(
                "variables",
                variable_reading(chart["variables"]),
                {
                    "variables.code": chart["variables"]["code"],
                    "variables.status": chart["variables"]["status"],
                    "variables.arrows": chart["variables"]["arrows"],
                },
                [SOURCE_URLS["variable"], SOURCE_URLS["substructure"]],
            ),
            statement(
                "cross",
                f"本次轮回交叉原典名称为 {chart['incarnation_cross']['name']}，四门按人格日地、设计日地排列为 {'/'.join(map(str, chart['incarnation_cross']['gates']))}。名称索引不构成事件预言。",
                {
                    "incarnation_cross.name": chart["incarnation_cross"]["name"],
                    "incarnation_cross.angle": chart["incarnation_cross"]["angle"],
                    "incarnation_cross.gates": list(
                        chart["incarnation_cross"]["gates"]
                    ),
                },
                [SOURCE_URLS["rave_2001"]],
            ),
            statement(
                "source_discrepancies",
                discrepancy_reading(source_impacts, source_names),
                {
                    "source_consistency.activation_impacts": source_impacts,
                    "source_consistency.cross_name_comparison": source_names,
                },
                [SOURCE_URLS["rave_2001"], SOURCE_URLS["dictionary"]],
            ),
        ]
        + node_statements
        + interval_statements
        + (
            [
                statement(
                    "primary_transcript_diagram",
                    primary_diagram_reading(
                        chart["source_consistency"]["primary_transcript_diagrams"]
                    ),
                    {
                        "source_consistency.primary_transcript_diagrams": chart[
                            "source_consistency"
                        ]["primary_transcript_diagrams"],
                        "incarnation_cross.gates": chart["incarnation_cross"]["gates"],
                        "incarnation_cross.angle": chart["incarnation_cross"]["angle"],
                    },
                    [
                        row["source_url"]
                        for row in chart["source_consistency"][
                            "primary_transcript_diagrams"
                        ]["observations"]
                    ],
                )
            ]
            if chart["source_consistency"]["primary_transcript_diagrams"][
                "observations"
            ]
            else []
        )
    )


def design_time_reading(chart: Dict[str, Any]) -> str:
    from fatebridge.core.human_design_root_interpretations import (
        root_interpretation_reading,
    )

    solver = chart["design_solver"]
    precision = solver["numerical_precision"]
    changes = precision["observed_solar_changed_levels"]
    status = (
        "求根太阳及地球对点的端点细分出现" + "/".join(changes) + "差异"
        if changes
        else "求根太阳及地球对点在所评估端点的细分相同"
    )
    bodies = precision["design_body_endpoint_assessment"]
    changes = bodies["observed_activation_changes"]
    body_text = (
        "实际设计端点中"
        + "；".join(row["body"] + "的" + "/".join(row["levels"]) for row in changes)
        + "细分存在差异。"
        if changes
        else "全部13项实际设计激活在本次所评估端点的门至Base细分相同。"
    )
    labels = {
        "type": "类型",
        "subtype": "子型",
        "authority": "权威",
        "strategy": "策略",
        "definition": "定义",
        "channels": "通道及其激活来源",
        "center_statuses": "中心状态",
        "profile": "角色",
        "profile_in_declared_pairs": "角色对照状态",
        "cross_gates": "交叉门序",
        "variable_code": "四箭头",
    }
    mechanical = bodies["observed_structure_changed_fields"]
    body_text += (
        "分别推导的整盘" + "/".join(labels[k] for k in mechanical) + "有变化。"
        if mechanical
        else "分别推导的整盘结构字段在这些端点相同。"
    )
    lattice = precision["local_solar_lattice"]
    if lattice["observed_decreasing_step_indices"]:
        body_text += "所检查的相邻TT太阳函数存在低位数值反向；这不是物理逆行，不能认证唯一数值根。"
    family = precision["local_root_family"]
    if family is not None:
        body_text += (
            f"有限邻点中的其他符号括区／零值候选共保留{family['actual_epoch_count']}个实际设计TT，均各自计算完整激活与解释。"
            + (
                "至少一个候选的门至Base细分与主盘不同，须逐候选读取。"
                if family["any_activation_subdivision_change"]
                else "这些候选的门至Base细分与主盘相同。"
            )
            + "原选根保持；这些数值候选不是物理误差区间或多个真实时刻。"
        )
    return (
        f"设计时刻从最终数值端点中选择太阳弧绝对残差最小者；本次TT区间宽度{solver['bracket_width_seconds']:.9f}秒。"
        + status
        + "。"
        + body_text
        + root_interpretation_reading(bodies["endpoint_interpretations"])
        + "当前主盘保留原选根规则；候选整盘各自读取，不拼接端点。观测到函数零值也不等于物理时刻误差为零，端点一致不证明连续区间稳定、出生记录或天文精度。"
    )


def variable_reading(variables: Dict[str, Any]) -> str:
    if variables["status"] != "computed":
        return "四组日地／交点的Tone缺失或对点不一致，本次不生成Variable编码；未确定的箭头不可自行补齐。"
    return (
        f"本次Variable编码为 {variables['code']}。P为人格、D为设计，每组先日地后交点；L、R对应Tone的1至3与4至6。"
        "这只汇总所选时刻和后端的四箭头，不等于现实认知、学习能力、饮食或健康评估；不同样本的箭头不能拼接。"
    )


def circuitry_reading(graph: Dict[str, Any]) -> str:
    summary = graph["circuitry"]
    if not summary["defined_channel_count"]:
        return "本次没有完整定义通道，故没有固定通道回路可解读；已激活的单门仍保留，不能据此说缺少能力或人生主题。"
    parts = [
        f"{','.join(row['channel_ids'])}：{row['meaning']}"
        for row in summary["circuits"]
    ]
    return (
        f"本次有{summary['defined_channel_count']}条完整定义通道。"
        + "；".join(parts)
        + f" 三群完整通道数为个体{summary['group_channel_counts']['individual']}、集体{summary['group_channel_counts']['collective']}、部落{summary['group_channel_counts']['tribal']}。"
        + "整合四通道已计入个体群，同时与相邻的10-34、20-57分开列出，整合小计不能再次相加。回路说明只描述本次通道结构，不从通道数量判断主导人格、能力高低或现实结果。"
    )
