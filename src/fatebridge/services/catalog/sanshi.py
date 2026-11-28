"""SanShi (Liuren, Qimen, Taiyi) and Jinkou tool declarations."""

from __future__ import annotations

from fatebridge.application.bindings import (
    bind_kwargs,
    bind_person,
    request_model_ref,
    service_ref,
)
from fatebridge.application.domain_validators import validate_ren_output
from fatebridge.application.tool_spec import ToolSpec

_SANSHI_REQ = "fatebridge.core.requests.sanshi"

calculate_jinkou_analysis = service_ref(
    "fatebridge.services.sanshi", "calculate_jinkou_analysis"
)
calculate_liureng_gods = service_ref(
    "fatebridge.services.sanshi", "calculate_liureng_gods"
)
calculate_liureng_runyear = service_ref(
    "fatebridge.services.sanshi", "calculate_liureng_runyear"
)
calculate_qimen_analysis = service_ref(
    "fatebridge.services.sanshi", "calculate_qimen_analysis"
)
calculate_taiyi_analysis = service_ref(
    "fatebridge.services.sanshi", "calculate_taiyi_analysis"
)

_LIUREN_DEFAULT_OMIT = (
    "calendar_context",
    "liuren.twelve_board",
    "liuren.life_stages",
    "liuren.auxiliary_stars",
    "liuren.month_building_element",
    "liuren.transmission_relations",
    "liuren.branch_relations",
    "liuren.emptiness_evidence",
    "liuren.god_yin",
    "liuren.seasonal_evidence",
    "liuren.day_placement_patterns",
    "liuren.cross_harmony",
    "liuren.transmission_progression",
    "liuren.calendar_policy.solar_term_dependencies",
    "liuren.meta.diurnal_evidence",
)


SPECS: list[ToolSpec] = [
    ToolSpec(
        name="liuren_chart",
        bind=bind_kwargs(calculate_liureng_gods),
        request_model_loader=request_model_ref(_SANSHI_REQ, "LiuRengGodsRequest"),
        summary="六壬起课：输出四课、九宗门三传、天将、旬遁与细课名；金口诀用 jinkou。",
        operation_label_zh="六壬课",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/liuren/chart",
        default_omit=_LIUREN_DEFAULT_OMIT,
        output_validators=(validate_ren_output,),
    ),
    ToolSpec(
        name="liuren_yearly_timing",
        bind=bind_person(
            calculate_liureng_runyear,
            also_pass=("use_true_solar_time", "birth_utc_offset"),
        ),
        request_model_loader=request_model_ref(_SANSHI_REQ, "LiuRengRunyearRequest"),
        summary="六壬行年：按农历虚岁推男女行年并起课；问具体单事用 liuren_chart。",
        operation_label_zh="六壬流年",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/liuren/timing/yearly",
        default_omit=_LIUREN_DEFAULT_OMIT,
        output_validators=(validate_ren_output,),
    ),
    ToolSpec(
        name="qimen",
        bind=bind_kwargs(calculate_qimen_analysis),
        request_model_loader=request_model_ref(_SANSHI_REQ, "QimenAnalysisRequest"),
        summary="奇门遁甲：方位选择、行动时机与谋略布局；单事成败用 liuyao，大势用 taiyi。",
        operation_label_zh="奇门遁甲",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/qimen",
        default_omit=(
            "calendar_context",
            "qimen.calendar_policy",
            "qimen.assessment",
            "qimen.fushi_hexagram",
            "qimen.hidden_stems_palace_map",
            "qimen.ju_decision",
            "qimen.palaces.*.door_hexagram",
            "qimen.palaces.*.content_palace",
            "qimen.palaces.*.content_trigram",
            "qimen.palaces.*.heaven_origin_trigram",
            "qimen.palaces.*.god_sequence_index",
        ),
    ),
    ToolSpec(
        name="taiyi",
        bind=bind_kwargs(calculate_taiyi_analysis),
        request_model_loader=request_model_ref(_SANSHI_REQ, "TaiyiAnalysisRequest"),
        summary="太乙神数：年/月/日/时四计，返回二目、主客算、四将与规则路径；日计用金钥匙积日。",
        operation_label_zh="太乙",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/taiyi",
        default_omit=(
            "calendar_context",
            "taiyi.calendar_rules",
            "taiyi.gates",
            "taiyi.long_cycles",
            "taiyi.condition_assessment",
            "taiyi.patterns",
            "taiyi.counter_cycles",
            "taiyi.shiji_derivation",
            "taiyi.determinate_calculation",
            "taiyi.solar_anchors",
            "taiyi.solar_anchor_scope",
            "taiyi.interpretation_scope",
        ),
    ),
    ToolSpec(
        name="jinkou",
        bind=bind_kwargs(calculate_jinkou_analysis),
        request_model_loader=request_model_ref(_SANSHI_REQ, "JinkouAnalysisRequest"),
        summary="金口诀：按日干、月将、占时与地分起四位，含五动三动、六十四课钤及本命另课。",
        operation_label_zh="金口诀",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/jinkou",
        default_omit=(
            "calendar_context",
            "jinkou.qi_evidence",
            "jinkou.position_interactions",
            "jinkou.branch_breaks",
            "jinkou.stem_relations",
            "jinkou.definition_evidence",
            "jinkou.combinations",
            "jinkou.relations",
            "jinkou.branch_stars",
            "jinkou.patterns.evaluations",
            "jinkou.internal_strength.relations",
            "jinkou.overview.power_basis",
            "jinkou.natal_course.course",
            "jinkou.year_fate.course",
        ),
        output_validators=(validate_ren_output,),
    ),
]
