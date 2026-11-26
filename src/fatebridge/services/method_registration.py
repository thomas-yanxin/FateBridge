"""Register executable domain methods, keeping conventions and sources separate."""

from dataclasses import replace

from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.astro.opaque_solar import METHOD_ID as OPAQUE_SOLAR_METHOD_ID
from fatebridge.core.human_design.human_design_point_mass import (
    METHOD_ID as HUMAN_DESIGN_POINT_MASS_METHOD_ID,
)
from fatebridge.core.method_contracts import MethodContract
from fatebridge.services.method_registration_groups import (
    GROUPS,
    WESTERN_EVENTS,
    WESTERN_LIFESPAN,
    WESTERN_TIMING,
    MethodGroup,
)


def register_methods(spec: ToolSpec) -> tuple[MethodContract, ...]:
    records = list(spec.methods)
    groups = list(GROUPS)
    for tool_name in WESTERN_TIMING:
        groups.append(
            MethodGroup(
                method_name=f"western_{tool_name}",
                consuming_tools=f"{tool_name} western_timing_analysis",
                implementation_path="core/predictive/western_timing.py",
                source_path="docs/western-astrology.md",
                quantity_kind="astronomy_and_rule_result",
                measurement_unit="per_field",
                error_sources=(
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
    for tool_name in WESTERN_LIFESPAN:
        groups.append(
            MethodGroup(
                method_name=f"western_{tool_name}",
                consuming_tools=f"astro_{tool_name}",
                implementation_path="core/astro/astrology_lifespan.py",
                source_path="docs/western-astrology.md",
                quantity_kind="astronomy_and_rule_result",
                measurement_unit="per_field",
                error_sources=(
                    "civil_clock",
                    "earth_rotation",
                    "ephemeris_model",
                    "display_quantization",
                    "rule_adjudication",
                ),
            )
        )
    for tool_name in WESTERN_EVENTS:
        groups.append(
            MethodGroup(
                method_name=f"western_{tool_name}",
                consuming_tools=f"astro_{tool_name}",
                implementation_path="services/western_events.py",
                source_path="docs/western-astrology.md",
                quantity_kind="astronomy_and_rule_result",
                measurement_unit="per_field",
                error_sources=(
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
    for group in groups:
        if spec.key not in group.consuming_tools.split():
            continue
        implementation_refs: tuple[str, ...] = (
            f"src/fatebridge/{group.implementation_path}",
        )
        source_refs: tuple[str, ...] = (group.source_path,)
        error_sources = group.error_sources
        if group.method_name == "western_lunation_phase":
            implementation_refs += (
                "src/fatebridge/core/lunar_phase_events.py",
                "src/fatebridge/core/predictive/progressions.py",
            )
            source_refs += (
                "https://www.khaldea.com/rudhyar/astroarticles/progressedlunationcharts.php",
                "https://khaldea.com/rudhyar/pofa/pofa_11.shtml",
                "https://khaldea.com/rudhyar/astroarticles/lunationbirthday_2.php",
                "https://www.khaldea.com/rudhyar/astroarticles/lunationbirthday_4.php",
                "https://www.astro.com/swisseph/swephprg.htm",
            )
            error_sources += ("numerical_solver",)
        records.append(
            MethodContract(
                method_id=f"fatebridge.{group.method_name}.contract_v1",
                output_paths=spec.required_output_fields,
                quantity_kind=group.quantity_kind,
                unit=group.measurement_unit,
                prerequisites=(
                    "请求Schema及领域前提必须成立；条件分支以本次实际回执为准",
                ),
                dependencies=("validated_request",),
                comparison_requirements=(
                    "相同方法合同、实现与数据版本、选项及实际计算层",
                ),
                limitations=(
                    "contract_v1是登记合同版本，不冒充上游原典或数值算法版本；实际版本另列runtime_method_ids",
                    "登记不认证全书、全部历史范围、连续区间稳定或现实预测",
                ),
                implementation_refs=implementation_refs,
                source_refs=source_refs,
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
                        "sihua_source",
                        "brightness_source",
                        "day_divide",
                        "node_mode",
                        "apparent_model",
                    }
                ),
                error_sources=error_sources,
                role=(
                    "reference"
                    if group.quantity_kind == "reference_text"
                    else "calculation"
                ),
            )
        )
    if spec.key == "otherbu":
        records.append(
            MethodContract(
                method_id="fatebridge.astrodice_symbolic_rules.contract_v1",
                output_paths=("planet", "sign", "house", "diceChart"),
                quantity_kind="symbolic_rule_result",
                unit="categorical",
                prerequisites=("已提供实际行星、星座和宫位骰面。",),
                dependencies=("planet", "sign", "house"),
                comparison_requirements=("相同规范化骰面、符号规则与词典版本。",),
                limitations=(
                    "整宫示意仅表示符号位置；实际规则版本及逐条来源随结果交付。",
                    "天象选项仅作用于独立天象背景。",
                ),
                implementation_refs=(
                    "src/fatebridge/core/astrodice.py",
                    "src/fatebridge/core/local_techniques/otherbu.py",
                ),
                source_refs=("docs/astrodice.md",),
                error_sources=("rule_adjudication",),
            )
        )
        records.append(
            MethodContract(
                method_id="fatebridge.astrodice_astronomical_context.contract_v1",
                output_paths=("chart",),
                quantity_kind="astronomy_and_rule_result",
                unit="per_field",
                prerequisites=("提供完整天象背景资料且本次交付chart。",),
                dependencies=(
                    "date",
                    "time",
                    "zone",
                    "lat",
                    "lon",
                    "gps_lat",
                    "gps_lon",
                ),
                comparison_requirements=(
                    "相同观测时刻和地点、星历、黄道和宫制、福点公式及实际参考系。",
                ),
                limitations=(
                    "天象背景与骰面及其整宫示意独立；运行版本见chart内实际回执。",
                    "声明误差分量不构成物理位置或事件时刻的误差上界。",
                ),
                implementation_refs=(
                    "src/fatebridge/core/local_techniques/chart.py",
                    "src/fatebridge/core/local_techniques/otherbu.py",
                ),
                source_refs=(
                    "docs/astrodice.md",
                    "https://www.astro.com/swisseph/swephprg.htm",
                ),
                selector_fields=("tradition", "hsys", "zodiacal", "fortune_method"),
                error_sources=(
                    "civil_clock",
                    "observer_location",
                    "earth_rotation",
                    "ephemeris_model",
                    "numerical_solver",
                    "display_quantization",
                    "rule_adjudication",
                ),
                requires_non_null_output="chart",
            )
        )
    if spec.key == "human_design":
        records.append(
            MethodContract(
                method_id=HUMAN_DESIGN_POINT_MASS_METHOD_ID,
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
                implementation_refs=(
                    "src/fatebridge/core/human_design/human_design_point_mass.py",
                ),
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
        records.append(
            MethodContract(
                method_id=OPAQUE_SOLAR_METHOD_ID,
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
    # note (methods): Preserve the published method IDs of the two numerical indices.
    return tuple(
        (
            replace(r, error_sources=r.error_sources or ("rule_adjudication",))
            if r.quantity_kind == "uncalibrated_rule_index"
            else r
        )
        for r in records
    )
