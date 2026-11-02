"""Required full-service BaZi facts; projected/historical models stay partial.

These checks follow the current domain producers. They compare presence only,
never supply a birth fact, recompute a chart or adjudicate classical force.
"""

from __future__ import annotations

from typing import Any

from fatebridge.utils.data import TenGod

TOPICS = (
    "career",
    "wealth",
    "health",
    "children",
    "education",
    "personality",
    "relatives",
    "marriage",
    "romance",
)
BAZI_ANCHOR_TOOLS = frozenset(
    ("analyze_destiny", "bazi_birth", *("bazi_" + t for t in TOPICS))
)
POSITIONS = ("year", "month", "day", "hour")

# Every named block is emitted by its corresponding analysis producer. Text
# extensions remain open; the listed leaves are its stable computational basis.
TOPIC_BLOCKS: dict[str, dict[str, str]] = {
    "career": {
        "dominant_ten_gods": "top_gods mapping_scope weighted_counts counting_basis tied_primary_gods primary_selection primary_career_type",
        "industry_analysis": "favorable_elements conditional_elements reference_scope mapping_status recommended_industries avoid_industries element_distribution",
        "career_structure": "score score_kind scope formation_status rule_signals unverified_conditions interpretation_scope score_basis level legacy_level notes",
        "entrepreneurship": "score weighted_counts partial_star_weight normal_star_weight score_kind scope formation_status rule_signals unverified_conditions score_basis tendency legacy_tendency notes",
        "career_timing": "timing_signals",
        "noble_direction": "favorable_directions conditional_elements reference_scope mapping_status",
    },
    "wealth": {
        "wealth_stars": "positions zheng_wealth_weight pian_wealth_weight total_weight visibility",
        "wealth_structure": "day_master_strength wealth_strength pattern legacy_pattern formation_status score_kind score_basis wealth_strength_kind score level notes",
        "wealth_storage": "has_storage storage_hits summary effect_status source_ref",
        "wealth_style": "primary_style recommendations",
        "wealth_direction": "wealth_element direction note",
        "wealth_risk": "bijie_weight risks relations assessment_status",
        "wealth_timing": "timing_signals storage_events assessment_status",
    },
    "health": {
        "constitution": "day_master_strength climate warm_strength cold_strength notes reference_scope",
        "organ_analysis": "element_distribution findings summary reference_scope",
        "health_timing": "timing_signals reference_scope",
    },
    "children": {
        "child_star": "star positions weight status",
        "child_palace": "hour_pillar hour_ten_god palace_relations trait",
        "affinity": "score tendency notes",
        "relationship": "hour_ten_god trait achievement",
        "children_timing": "timing_signals",
    },
    "education": {
        "study_stars": "seal_weight food_hurt_weight officer_weight wealth_weight",
        "education_level": "score score_kind assessment_status score_basis tier notes",
        "wenchang": "wenchang_branch hit_pillars has_wenchang note",
        "subject_orientation": "inclination favorable_fields conditional_elements reference_scope assessment_status",
        "exam_timing": "timing_signals assessment_status",
    },
    "personality": {
        "core_nature": "element virtue traits shortcoming reference_scope",
        "dominant_traits": "top_gods primary tied_primary_gods primary_selection",
        "disposition": "strength polarity notes",
    },
    "relatives": {
        "parents": "father_star_weight mother_star_weight notes",
        "siblings": "sibling_star_weight notes",
        "palaces": "year_pillar month_pillar relations",
        "support": "seal_weight peer_weight notes",
    },
    "marriage": {
        "spouse_palace": "day_branch day_branch_element day_branch_polarity hidden_stems relationship_to_day_master stability stability_notes spouse_personality_hint",
        "marriage_quality": "score quality_level notes",
        "marriage_timing": "timing_signals marriage_tendency tendency_notes",
    },
    "romance": {
        "peach_blossom": "peach_branches hit_pillars count note",
        "hongluan_tianxi": "hongluan_branch tianxi_branch hongluan_hits tianxi_hits notes",
        "opposite_sex_star": "basis weight status",
        "peach_quality": "notes relations assessment_status",
        "romance_timing": "timing_signals assessment_status",
    },
}
TOPIC_FIELDS = {
    "career": "interpretation_scope suggestions",
    "wealth": "counting_basis classical_context wealth_element suggestions",
    "health": "scope is_medical_assessment disclaimer",
    "children": "interpretation_scope gender_basis",
    "education": "counting_basis suggestions",
    "personality": "interpretation_scope counting_basis day_master strengths weaknesses advice",
    "relatives": "counting_basis",
    "marriage": "gender_basis marriage_shensha risk_factors suggestions spouse_star",
    "romance": "counting_basis gender_basis",
}
NULLABLE_BLOCK_FIELDS = {
    ("career", "dominant_ten_gods"): {"primary_career_type"},
    ("wealth", "wealth_structure"): {"score"},
    ("children", "affinity"): {"score"},
    ("education", "education_level"): {"score"},
    ("personality", "dominant_traits"): {"primary"},
    ("marriage", "marriage_quality"): {"score"},
    ("romance", "opposite_sex_star"): {"weight"},
}


def _object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("完整八字结果缺少计算依据对象")
    return value


def _keys(
    value: Any, names: str, *, nullable: set[str] | None = None
) -> dict[str, Any]:
    obj = _object(value)
    for key in names.split():
        if key not in obj or (obj[key] is None and key not in (nullable or set())):
            raise ValueError("完整八字结果缺少计算依据字段：" + key)
        if isinstance(obj[key], str) and not obj[key].strip():
            raise ValueError("完整八字计算依据不能为空字符串：" + key)
    return obj


def _rows(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError("完整八字结果缺少计算依据列表")
    return value


def _calendar(value: Any) -> None:
    c = _keys(
        value,
        "timezone solar_datetime current_solar_term next_solar_term solar_term_delta bazi_month_boundary lunar_calendar lunar_calendar_support",
        nullable={"lunar_calendar"},
    )
    support = _keys(c["lunar_calendar_support"], "supported supported_range")
    _keys(support["supported_range"], "start end")
    if support["supported"] is True:
        _keys(
            c["lunar_calendar"],
            "year month day is_leap_month day_ganzhi",
        )
    elif support["supported"] is False:
        _keys(support, "reason")
        if c["lunar_calendar"] is not None:
            raise ValueError("表外农历不能以完整计算结果交付")
    else:
        raise ValueError("完整八字结果须明示农历支持状态")
    month = _keys(
        c["bazi_month_boundary"],
        "branch month_index comparison_datetime elapsed_basis elapsed_seconds_since_start elapsed_seconds_until_next days_since_start days_until_next start_term next_term",
    )
    for term in (
        c["current_solar_term"],
        c["next_solar_term"],
        month["start_term"],
        month["next_term"],
    ):
        _keys(
            term,
            "name datetime datetime_with_offset utc_offset_seconds fold timezone resolution_provider ephemeris_model",
        )
    _keys(c["solar_term_delta"], "days_since_current days_until_next description")


def _force(value: Any) -> None:
    f = _keys(
        value,
        "method_id source components source_root_observations engineering_composition classical_adjudication scope limitations",
    )
    _keys(f["source"], "id title url")
    _keys(f["classical_adjudication"], "body_strength seal_weight body_seal_relation")
    composition = _keys(
        f["engineering_composition"],
        "status ratio_basis strength_method_id strength_level support_share body_within_support_share body_seal_energy_relation quantity_kind",
        nullable={
            "strength_method_id",
            "strength_level",
            "support_share",
            "body_within_support_share",
        },
    )
    components = _keys(f["components"], "body seal output wealth officer_killer")
    for name in ("body", "seal", "output", "wealth", "officer_killer"):
        component = _keys(
            components[name],
            "element ten_gods physical_hidden_roots revealed_positions source_star_refs engineering_energy engineering_energy_unrounded remaining_hidden_roots",
            nullable={
                "engineering_energy",
                "engineering_energy_unrounded",
                "remaining_hidden_roots",
            },
        )
        if composition["status"] == "supplied_calculation":
            _keys(
                component,
                (
                    "engineering_energy_unrounded"
                    if composition["ratio_basis"] == "unrounded_same_assessment"
                    else "engineering_energy"
                ),
            )
    _keys(f["source_root_observations"], "method_id source stems scope")


def _passage(value: Any) -> None:
    p = _keys(
        value,
        "method_id source nodes visible_paths principal_hidden_paths all_hidden_paths mixed_paths summary scope",
    )
    _keys(p["source"], "id title url source_sha256")
    planes: dict[str, set[str]] = {"stem": set(), "hidden": set()}
    for node in _rows(p["nodes"]):
        row = _keys(
            node,
            "id pillar plane stem branch hidden_rank element remaining_root_state binding_state",
            nullable={"branch", "hidden_rank"},
        )
        planes[row["plane"]].add(row["pillar"])
    if any(positions != set(POSITIONS) for positions in planes.values()):
        raise ValueError("完整八字通关依据须保留四柱实际干藏节点")
    for name in (
        "visible_paths",
        "principal_hidden_paths",
        "all_hidden_paths",
        "mixed_paths",
    ):
        for path in _rows(p[name]):
            _keys(
                path,
                "from_node via_node to_node plane elements positions principal_hidden_only position_status all_nodes_have_remaining_roots binding_states effective_passage",
                nullable={"all_nodes_have_remaining_roots"},
            )
    _keys(
        p["summary"],
        "visible_path_count principal_hidden_path_count all_hidden_path_count mixed_path_count effective_passage calculation_effect",
    )


def _evidence(value: Any, *, topic: str | None) -> None:
    e = _keys(
        value,
        "method_id rulesets ten_gods visible_stems star_occurrences element_presence bureau_season_reference relations group_relations month_command seasonal_reference classical_root_profile classical_routes candidate_selection from_child_reference natal_hidden_carriers force_components classical_passage financial_seal_positions structure_checks strength_context limitations",
    )
    if not _rows(e["rulesets"]):
        raise ValueError("完整八字结果缺少来源规则")
    _keys(e["ten_gods"], " ".join(g.value for g in TenGod))
    visible = _rows(e["visible_stems"])
    for row in visible:
        _keys(
            row,
            "pillar stem ten_god is_day_master roots life_stages growth_phase_roots",
        )
    if len(visible) != 4 or {r["pillar"] for r in visible} != set(POSITIONS):
        raise ValueError("完整八字结果须保留四柱透干依据")
    for name in (
        "star_occurrences",
        "element_presence",
        "bureau_season_reference",
        "classical_root_profile",
        "classical_routes",
        "candidate_selection",
        "from_child_reference",
        "natal_hidden_carriers",
    ):
        _keys(e[name], "method_id scope")
    _keys(
        e["star_occurrences"], "quantity_kind status gods day_stem_counted_as_support"
    )
    _keys(e["star_occurrences"]["gods"], " ".join(g.value for g in TenGod))
    for name in ("visible_stems", "principal_hidden_stems", "all_hidden_stems"):
        _keys(
            e["element_presence"].get(name),
            "occurrences present_elements absent_elements",
        )
    _keys(e["classical_root_profile"], "day_stem roots global_strength_status source")
    _keys(
        e["classical_routes"], "source selected_month_role routes wealth_seal_positions"
    )
    _keys(
        e["candidate_selection"],
        "source selected_month paths chosen_path_id adjudication_status selection_status",
        nullable={"chosen_path_id"},
    )
    _keys(
        e["from_child_reference"],
        "status formation_status ordinary_fuyi_requires_review source observed_conditions pending_conditions",
    )
    _keys(e["natal_hidden_carriers"], "pillars effective_force_status source")
    month = _keys(
        e["month_command"],
        "month_branch label selection_rule selection_method candidates selected_god selection_status intra_month_duty scope",
    )
    duty = _keys(
        month["intra_month_duty"],
        "status selected_stem rule_profile source_reference scope",
        nullable={"selected_stem", "rule_profile"},
    )
    _keys(
        duty["source_reference"],
        "method_id month_branch conventional_month_hidden_stems sources duration_source_layers effective_command_status scope calculation_effect",
    )
    _keys(
        e["strength_context"],
        "strength_level method_id status root_effect_policy root_qualifications stem_energy_accounting clash_comparison storage_movement_effects",
    )
    _force(e["force_components"])
    _passage(e["classical_passage"])
    if e["method_id"] == "bazi_position_prerequisites_v2":
        context = _keys(
            e.get("classical_passage_relations"),
            "method_id passage_source_id relations_status source_relation_count events unclassified_event_refs nodes effective_passage calculation_effect scope",
            nullable={"source_relation_count", "events", "unclassified_event_refs"},
        )
        source_ids = {n["id"] for n in e["classical_passage"]["nodes"]}
        nodes = _rows(context["nodes"])
        for node in nodes:
            _keys(
                node,
                "node_id visible_relation_refs root_carrier_scope root_carrier_positions root_relation_refs",
                nullable={
                    "visible_relation_refs",
                    "root_carrier_positions",
                    "root_relation_refs",
                },
            )
        if {n["node_id"] for n in nodes} != source_ids:
            raise ValueError("通关关系上下文必须保留同次全部实际节点")
        if context["passage_source_id"] != e["classical_passage"]["source"]["id"]:
            raise ValueError("通关关系上下文不能替换同次原典来源")
        if context["relations_status"] == "supplied":
            _keys(context, "source_relation_count events unclassified_event_refs")
            for event in _rows(context["events"]):
                _keys(event, "id plane receipt")
                _keys(event["receipt"], "kind positions status")
    if topic is not None:
        t = _keys(
            e.get("topic"),
            "topic first_view scope selection_basis selection_alternatives stars palaces timing source_ref limitations",
        )
        if t["topic"] != topic:
            raise ValueError("完整专题依据须对应实际专题")
        _keys(
            t["timing"],
            "scope pillar_carriers carrier_source carrier_scope hidden_target_reference hidden_target_carriers layers between_layers combined_groups",
        )


def _timing(value: Any) -> None:
    t = _keys(
        value,
        "source dayun_pillar liunian_pillar overridden",
        nullable={"dayun_pillar"},
    )
    _keys(t["overridden"], "dayun_pillar liunian_pillar")
    if t["source"] == "explicit_pillar_overrides":
        _keys(t, "dayun_pillar")
    else:
        _keys(
            t,
            "analysis_date analysis_datetime timezone input_granularity anchor_policy year_boundary_policy boundary_status boundaries_on_date boundary_scope hourly_evidence dayun_age dayun_selection_basis dayun_start_at dayun_end_at",
            nullable={
                "dayun_age",
                "dayun_selection_basis",
                "dayun_start_at",
                "dayun_end_at",
            },
        )


def require_complete_bazi_anchors(key: str, result: dict[str, Any]) -> None:
    """Only called on full successful results, before any transport projection."""
    if key not in BAZI_ANCHOR_TOOLS:
        return
    if key in {"analyze_destiny", "bazi_birth"}:
        root = result if key == "analyze_destiny" else result.get("bazi_birth")
        r = _keys(
            root,
            "person_info four_pillars day_master element_distribution favorable_elements ten_gods patterns calendar_context structure_profile",
        )
        _keys(
            r["person_info"],
            "name gender birth_datetime normalized_birth_datetime birth_timezone",
        )
        pillars = _keys(r["four_pillars"], "year month day hour")
        for name in POSITIONS:
            _keys(pillars[name], "stem branch")
        dm = _keys(r["day_master"], "stem element polarity strength assessment")
        _keys(
            dm["assessment"],
            "method_id status strength_level hidden_stem_ledger effective_elements_unrounded stem_energy_accounting relations month_command",
        )
        profile = _keys(
            r["structure_profile"],
            "resolution_policy dominant_structure candidate_selection from_child_reference evidence_chain",
        )
        _evidence(profile["evidence_chain"], topic=None)
    else:
        topic = key.removeprefix("bazi_")
        r = _keys(
            result.get(topic + "_analysis"),
            "calendar_context timing_context evidence_chain " + TOPIC_FIELDS[topic],
        )
        for block, fields in TOPIC_BLOCKS[topic].items():
            _keys(
                r.get(block), fields, nullable=NULLABLE_BLOCK_FIELDS.get((topic, block))
            )
        if topic == "marriage":
            if r["gender_basis"] == "unselected_gender_alternatives":
                star = _keys(
                    r["spouse_star"],
                    "spouse_star_type spouse_star_strength alternatives",
                )
                for gender in ("male", "female"):
                    _keys(
                        _object(star["alternatives"]).get(gender),
                        "spouse_star_type spouse_star_alt spouse_star_positions spouse_star_strength counting_scope spouse_element predicted_appearance",
                    )
            else:
                _keys(
                    r["spouse_star"],
                    "spouse_star_type spouse_star_alt spouse_star_positions spouse_star_strength counting_scope spouse_element predicted_appearance",
                )
                _keys(
                    r["marriage_quality"], "score score_kind score_basis counting_scope"
                )
                _keys(r, "interpretation_scope")
        _timing(r["timing_context"])
        _evidence(r["evidence_chain"], topic=topic)
    _calendar(r["calendar_context"])
