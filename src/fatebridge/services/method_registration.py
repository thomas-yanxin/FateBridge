"""Register executable domain methods, keeping conventions and sources separate."""

from dataclasses import replace

from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.method_contracts import MethodContract

REGISTRY_VERSION = "domain_methods_2026_11_v1"
EXCLUDED_TOOLS = frozenset({"bazi_personality"})

# Explicit membership fails closed when a new tool has not been classified.
# A shared method has one ID across consumers; these are domain computations,
# not one generated method label per transport entry.
GROUPS = (
    (
        "bazi_natal",
        "analyze_destiny bazi_birth bazi_marriage bazi_career bazi_wealth bazi_health bazi_children bazi_education bazi_relatives bazi_romance bazi_source_compare two_person_compatibility timing_analysis dayun_analysis liunian_analysis liuyue_analysis liuri_analysis liushi_analysis",
        "services/birth_context.py",
        "docs/bazi-assessment.md",
        "traditional_rule_result",
        "per_field",
        ("civil_clock", "solar_clock", "calendar_model", "rule_adjudication"),
    ),
    (
        "bazi_source_collation",
        "bazi_source_compare",
        "core/source_annotations.py",
        "docs/bazi-assessment.md",
        "source_comparison",
        "categorical",
        ("calendar_model", "rule_adjudication"),
    ),
    (
        "bazi_timing_layers",
        "timing_analysis dayun_analysis liunian_analysis liuyue_analysis liuri_analysis liushi_analysis",
        "services/timing_state.py",
        "docs/bazi-timing.md",
        "traditional_rule_result",
        "per_field",
        ("civil_clock", "solar_clock", "calendar_model", "rule_adjudication"),
    ),
    (
        "solar_term_crossings",
        "jieqi_timeline_analysis jieqi_year",
        "services/calendar_tools.py",
        "docs/solar-backends.md",
        "event_time",
        "seconds",
        (
            "civil_clock",
            "earth_rotation",
            "ephemeris_model",
            "numerical_solver",
            "display_quantization",
        ),
    ),
    (
        "chinese_calendar_conversion",
        "nongli_time",
        "services/calendar_tools.py",
        "docs/solar-backends.md",
        "calendar_conversion",
        "per_field",
        ("civil_clock", "calendar_model"),
    ),
    (
        "hexagram_lookup",
        "gua_lookup gua_meiyi",
        "services/divination.py",
        "docs/numerology-audit.md",
        "reference_text",
        "categorical",
        ("rule_adjudication",),
    ),
    (
        "meihua_cast_and_rules",
        "meihua_analysis meihua_cast",
        "services/divination.py",
        "docs/meihua.md",
        "traditional_rule_result",
        "categorical",
        ("civil_clock", "calendar_model", "rule_adjudication"),
    ),
    (
        "tongshefa_symbolic_rules",
        "tongshefa",
        "services/divination.py",
        "docs/numerology-audit.md",
        "symbolic_rule_result",
        "categorical",
        ("rule_adjudication",),
    ),
    (
        "sixyao_cast_and_yao_relations",
        "sixyao",
        "core/local_techniques/sixyao.py",
        "docs/liuyao-depth-audit.md",
        "traditional_rule_result",
        "categorical",
        ("civil_clock", "solar_clock", "calendar_model", "rule_adjudication"),
    ),
    (
        "canping_number_and_timing",
        "canping",
        "core/local_techniques/canping.py",
        "docs/numerology-audit.md",
        "integer_and_rule_result",
        "per_field",
        ("civil_clock", "calendar_model", "rule_adjudication"),
    ),
    (
        "heluo_number_and_month_rules",
        "heluo",
        "core/heluo.py",
        "docs/numerology-audit.md",
        "integer_and_rule_result",
        "per_field",
        ("civil_clock", "calendar_model", "rule_adjudication"),
    ),
    (
        "sukuyo_calendar_and_relations",
        "suzhan sukuyo_compatibility",
        "core/local_techniques/suzhan.py",
        "docs/algorithm-coverage.md",
        "calendar_and_symbolic_result",
        "per_field",
        ("civil_clock", "calendar_model", "rule_adjudication"),
    ),
    (
        "astrodice_symbolic_rules",
        "otherbu",
        "services/divination.py",
        "docs/algorithm-coverage.md",
        "symbolic_rule_result",
        "categorical",
        ("rule_adjudication",),
    ),
    (
        "sanshi_correspondence",
        "sanshiunited",
        "services/divination.py",
        "docs/taiyi-sanshi-audit.md",
        "spatial_symbolic_correspondence",
        "categorical",
        ("civil_clock", "solar_clock", "calendar_model", "rule_adjudication"),
    ),
    (
        "ziwei_natal_and_temporal_rules",
        "ziwei_birth ziwei_horoscope ziwei_rules",
        "services/metaphysics.py",
        "docs/algorithm-coverage.md",
        "traditional_rule_result",
        "categorical",
        ("civil_clock", "solar_clock", "calendar_model", "rule_adjudication"),
    ),
    (
        "liuren_course_and_transmissions",
        "liureng_gods liureng_runyear sanshiunited",
        "services/metaphysics.py",
        "docs/liuren-jinkou-audit.md",
        "traditional_rule_result",
        "categorical",
        ("civil_clock", "solar_clock", "calendar_model", "rule_adjudication"),
    ),
    (
        "qimen_rotating_board",
        "qimen sanshiunited",
        "services/metaphysics.py",
        "docs/qimen-depth-audit.md",
        "traditional_rule_result",
        "categorical",
        ("civil_clock", "solar_clock", "calendar_model", "rule_adjudication"),
    ),
    (
        "taiyi_four_counts",
        "taiyi sanshiunited",
        "services/metaphysics.py",
        "docs/taiyi-sanshi-audit.md",
        "integer_and_rule_result",
        "per_field",
        ("civil_clock", "solar_clock", "calendar_model", "rule_adjudication"),
    ),
    (
        "jinkou_four_positions",
        "jinkou",
        "services/metaphysics.py",
        "docs/liuren-jinkou-audit.md",
        "traditional_rule_result",
        "categorical",
        ("civil_clock", "solar_clock", "calendar_model", "rule_adjudication"),
    ),
    (
        "export_sections",
        "export_registry export_parse",
        "services/export_tools.py",
        "docs/api-reference.md",
        "reference_text",
        "categorical",
        (),
    ),
    (
        "knowledge_source_lookup",
        "knowledge_registry knowledge_read",
        "services/knowledge.py",
        "docs/api-reference.md",
        "reference_text",
        "categorical",
        ("rule_adjudication",),
    ),
    (
        "human_design_solar_arc_and_mechanics",
        "human_design",
        "core/human_design.py",
        "docs/human-design.md",
        "astronomy_and_rule_result",
        "per_field",
        (
            "civil_clock",
            "earth_rotation",
            "ephemeris_model",
            "numerical_solver",
            "display_quantization",
            "rule_adjudication",
        ),
    ),
    (
        "western_natal_geometry",
        "astro_chart astro_chart13 astro_hellen astro_guolao astro_india astro_vimshottari astro_germany astro_relative astro_relative_chart",
        "core/astro/chart.py",
        "docs/western-astrology.md",
        "astronomy_and_rule_result",
        "per_field",
        (
            "civil_clock",
            "observer_location",
            "earth_rotation",
            "ephemeris_model",
            "numerical_solver",
            "display_quantization",
            "rule_adjudication",
        ),
    ),
    (
        "jyotish_vargas_strength_and_dasha",
        "astro_chart astro_india astro_vimshottari",
        "core/jyotish.py",
        "docs/jyotish.md",
        "astronomy_and_rule_result",
        "per_field",
        (
            "civil_clock",
            "earth_rotation",
            "ephemeris_model",
            "display_quantization",
            "rule_adjudication",
        ),
    ),
    (
        "guolao_mansions_and_rules",
        "astro_chart astro_guolao",
        "core/astro/chart.py",
        "docs/algorithm-coverage.md",
        "astronomy_and_rule_result",
        "per_field",
        ("civil_clock", "earth_rotation", "ephemeris_model", "rule_adjudication"),
    ),
    (
        "germany_midpoint_geometry",
        "astro_chart astro_germany",
        "services/astrology.py",
        "docs/western-astrology.md",
        "astronomy_and_rule_result",
        "per_field",
        (
            "civil_clock",
            "earth_rotation",
            "ephemeris_model",
            "display_quantization",
            "rule_adjudication",
        ),
    ),
    (
        "western_relationship_geometry",
        "astro_relative astro_relative_chart",
        "core/astro/relationship.py",
        "docs/western-astrology.md",
        "astronomy_and_rule_result",
        "per_field",
        (
            "civil_clock",
            "observer_location",
            "earth_rotation",
            "ephemeris_model",
            "display_quantization",
            "rule_adjudication",
        ),
    ),
    (
        "fengshui_directions",
        "fengshui_directions",
        "services/fengshui.py",
        "docs/fengshui.md",
        "direction_sector",
        "degrees",
        (
            "observer_location",
            "north_reference",
            "display_quantization",
            "rule_adjudication",
        ),
    ),
    (
        "fengshui_minggua_bazhai",
        "fengshui_minggua fengshui_bazhai fengshui_assess",
        "services/fengshui.py",
        "docs/fengshui.md",
        "traditional_rule_result",
        "categorical",
        ("civil_clock", "calendar_model", "north_reference", "rule_adjudication"),
    ),
    (
        "fengshui_jinsuo",
        "fengshui_jinsuo fengshui_assess",
        "services/fengshui.py",
        "docs/fengshui.md",
        "traditional_rule_result",
        "categorical",
        ("north_reference", "rule_adjudication"),
    ),
    (
        "fengshui_annual_monthly_stars",
        "fengshui_annual_stars fengshui_monthly_stars fengshui_assess",
        "services/fengshui.py",
        "docs/fengshui.md",
        "traditional_rule_result",
        "categorical",
        ("civil_clock", "calendar_model", "north_reference", "rule_adjudication"),
    ),
    (
        "fengshui_xuankong_natal",
        "fengshui_xuankong_natal fengshui_assess",
        "services/fengshui.py",
        "docs/fengshui-xuankong.md",
        "traditional_rule_result",
        "categorical",
        ("civil_clock", "calendar_model", "north_reference", "rule_adjudication"),
    ),
)

WESTERN_TIMING = "solarreturn lunarreturn transit solararc givenyear profection pd pdchart zr firdaria decennials".split()
WESTERN_LIFESPAN = "harmonic planetary_ages triplicity_rulers lunation_phase distributions balbillus keypoints yearsystem129 planetaryarc persiandirected agepoint vedicprog jaynesprog".split()
WESTERN_EVENTS = "mundane extrareturns horary election".split()


def register_methods(spec: ToolSpec) -> tuple[MethodContract, ...]:
    if spec.key in EXCLUDED_TOOLS:
        return spec.methods
    records = list(spec.methods)
    groups = list(GROUPS)
    for key in WESTERN_TIMING:
        groups.append(
            (
                f"western_{key}",
                f"{key} western_timing_analysis",
                "core/predictive/western_timing.py",
                "docs/western-astrology.md",
                "astronomy_and_rule_result",
                "per_field",
                (
                    "civil_clock",
                    "observer_location",
                    "earth_rotation",
                    "ephemeris_model",
                    "numerical_solver",
                    "display_quantization",
                    "rule_adjudication",
                ),
            )
        )
    for key in WESTERN_LIFESPAN:
        groups.append(
            (
                f"western_{key}",
                f"astro_{key}",
                "core/astrology_lifespan.py",
                "docs/western-astrology.md",
                "astronomy_and_rule_result",
                "per_field",
                (
                    "civil_clock",
                    "earth_rotation",
                    "ephemeris_model",
                    "display_quantization",
                    "rule_adjudication",
                ),
            )
        )
    for key in WESTERN_EVENTS:
        groups.append(
            (
                f"western_{key}",
                f"astro_{key}",
                "services/western_events.py",
                "docs/western-astrology.md",
                "astronomy_and_rule_result",
                "per_field",
                (
                    "civil_clock",
                    "observer_location",
                    "earth_rotation",
                    "ephemeris_model",
                    "numerical_solver",
                    "display_quantization",
                    "rule_adjudication",
                ),
            )
        )
    for name, consumers, implementation, source, quantity, unit, errors in groups:
        if spec.key not in consumers.split():
            continue
        records.append(
            MethodContract(
                method_id=f"fatebridge.{name}.contract_v1",
                output_paths=spec.required_output_fields,
                quantity_kind=quantity,
                unit=unit,
                prerequisites=(
                    "请求Schema及领域前提必须成立；条件分支以本次实际回执为准",
                ),
                dependencies=("validated_request",),
                comparison_requirements=(
                    "相同方法合同、实现/数据指纹、选项与实际计算层",
                ),
                limitations=(
                    "contract_v1是登记合同版本，不冒充上游原典或数值算法版本；实际版本另列runtime_method_ids",
                    "登记不认证全书、全部历史范围、连续区间稳定或现实预测",
                ),
                implementation_refs=(f"src/fatebridge/{implementation}",),
                source_refs=(source,),
                selector_fields=tuple(
                    n
                    for n in spec.request_model.model_fields
                    if n.endswith(
                        ("method", "profile", "policy", "basis", "mode", "ruleset_id")
                    )
                    or n
                    in {
                        "qimen_options",
                        "methods",
                        "modules",
                        "options",
                        "house_system",
                        "node_mode",
                        "apparent_model",
                    }
                ),
                error_sources=errors,
                role="reference" if quantity == "reference_text" else "calculation",
            )
        )
    if spec.key == "human_design":
        from fatebridge.core.human_design_point_mass import METHOD_ID

        records.append(
            MethodContract(
                method_id=METHOD_ID,
                output_paths=("apparent_model_comparison",),
                quantity_kind="astronomy_model_comparison",
                unit="degrees",
                prerequisites=(
                    "compare_apparent_models=true；pyerfa与实际重心星历文件可用",
                ),
                dependencies=(
                    "time_scales.personality.jd_tt",
                    "time_scales.design.jd_tt",
                ),
                comparison_requirements=(
                    "同TT、同重心状态来源、相同有限源偏折/光行差/真黄道约定",
                ),
                limitations=(
                    "不改变原生激活；固定TT位置与候选自有设计根分别比较；太阳盘内为数学延拓",
                    "固定队列误差不是全域物理误差界；未认证原版软件来源优先级",
                ),
                implementation_refs=("src/fatebridge/core/human_design_point_mass.py",),
                source_refs=("docs/human-design.md",),
                selector_fields=("compare_apparent_models",),
                error_sources=(
                    "ephemeris_model",
                    "numerical_solver",
                    "display_quantization",
                    "rule_adjudication",
                ),
            )
        )
        records.append(
            replace(
                records[-1],
                method_id="human_design_point_mass_design_root_v1",
                output_paths=("apparent_model_comparison.candidate_design_root",),
                quantity_kind="event_time",
                unit="per_field",
                dependencies=("time_scales.personality.jd_tt",),
                limitations=(
                    "88度根仅使用同一候选坐标模型的太阳；数值相邻端点不是物理时刻误差界",
                    "不替换原生设计根；数值队列通过不认证原版软件模型或现实效度",
                ),
            )
        )
    if spec.key == "astro_chart":
        from fatebridge.core.astro.opaque_solar import METHOD_ID

        records.append(
            MethodContract(
                method_id=METHOD_ID,
                output_paths=("apparent_model_positions",),
                quantity_kind="astronomical_position",
                unit="degrees",
                prerequisites=(
                    "chart分支且apparent_model=opaque_solar；pyerfa与实际重心星历来源可用",
                ),
                dependencies=(
                    "chart_profile.julian_day_tt",
                    "physical_ephemeris_source",
                ),
                comparison_requirements=(
                    "同TT、同天体中心、同有限光路日盘遮蔽约定、光行差与真黄道参考系",
                ),
                limitations=(
                    "standalone_positions_only；natal_chart_recomputed=false，原planets、日速、宫位及相位不重算",
                    "太阳盘内坐标为具名数学约定；有限队列不认证完整物理范围或现实预测",
                ),
                implementation_refs=("src/fatebridge/core/astro/opaque_solar.py",),
                source_refs=("docs/western-astrology.md",),
                selector_fields=("apparent_model",),
                error_sources=(
                    "ephemeris_model",
                    "numerical_solver",
                    "display_quantization",
                ),
            )
        )
    if not records:
        raise ValueError(f"未登记领域方法：{spec.key}")
    # The two existing numerical indices retain their published method IDs.
    return tuple(
        (
            replace(r, error_sources=r.error_sources or ("rule_adjudication",))
            if r.quantity_kind == "uncalibrated_rule_index"
            else r
        )
        for r in records
    )
