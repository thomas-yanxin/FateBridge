"""Divination tool declarations and domain binding helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fatebridge.application.bindings import bind_kwargs, request_model_ref, service_ref
from fatebridge.application.tool_spec import (
    BatchInputPolicy,
    OutputContractError,
    ServiceInput,
    ServiceResult,
    ToolSpec,
)
from fatebridge.core.reproducibility import ReproducibilityPolicy
from fatebridge.services.catalog.sanshi import validate_ren_anchors

if TYPE_CHECKING:
    from pydantic import BaseModel

_DIV_REQ = "fatebridge.core.requests.divination"


def _validate_suzhan_clock(
    _spec: ToolSpec,
    result: ServiceResult,
    request: BaseModel | None,
    _validated: BaseModel | None,
) -> None:
    from fatebridge.core.requests.divination import SuZhanRequest
    from fatebridge.core.sukuyo.suzhan_clock_input import require_clock_input_binding

    assert request is None or isinstance(request, SuZhanRequest)
    try:
        require_clock_input_binding(result, request=request)
    except ValueError as exc:
        raise OutputContractError("宿占输出与钟时计算层不符") from exc


calculate_canping_analysis = service_ref(
    "fatebridge.services.divination", "calculate_canping_analysis"
)


calculate_gua_lookup = service_ref(
    "fatebridge.services.divination", "calculate_gua_lookup"
)


calculate_heluo_analysis = service_ref(
    "fatebridge.services.divination", "calculate_heluo_analysis"
)


calculate_meihua_analysis = service_ref(
    "fatebridge.services.divination", "calculate_meihua_analysis"
)
calculate_meihua_cast = service_ref(
    "fatebridge.services.meihua", "calculate_meihua_cast"
)


calculate_otherbu_analysis = service_ref(
    "fatebridge.services.divination", "calculate_otherbu_analysis"
)


calculate_sanshiunited_analysis = service_ref(
    "fatebridge.services.divination", "calculate_sanshiunited_analysis"
)


calculate_sixyao_analysis = service_ref(
    "fatebridge.services.divination", "calculate_sixyao_analysis"
)


calculate_suzhan_analysis = service_ref(
    "fatebridge.services.divination", "calculate_suzhan_analysis"
)


calculate_tongshefa_analysis = service_ref(
    "fatebridge.services.divination", "calculate_tongshefa_analysis"
)


def _sixyao_needs_seed(data: dict[str, ServiceInput]) -> bool:
    from fatebridge.core.liuyao.casting import needs_random_coin_cast

    return needs_random_coin_cast(data)


SPECS: list[ToolSpec] = [
    ToolSpec(
        name="gua_lookup",
        bind=bind_kwargs(calculate_gua_lookup),
        request_model_loader=request_model_ref(_DIV_REQ, "GuaLookupRequest"),
        required_output_fields=("results",),
        summary="卦象查询：按八卦或六十四卦名、卦码批量查结构，六十四卦附《周易》经文与出处。",
        operation_label_zh="卦象查询",
        family="divination",
        rest_path="/api/divination/gua",
        uses_astronomy_runtime=False,
    ),
    ToolSpec(
        name="meihua_time_cast",
        bind=bind_kwargs(calculate_meihua_analysis),
        request_model_loader=request_model_ref(_DIV_REQ, "MeihuaAnalysisRequest"),
        required_output_fields=("meihua",),
        summary="梅花时间起卦：按公历钟时与时区查农历取数，返回本变互卦、初中终生克与原文来源；weather选天时条款。",
        operation_label_zh="梅花易数",
        family="divination",
        rest_path="/api/divination/meihua/time-cast",
        default_omit=(
            "calendar_context",
            "meihua.base_hexagram.classical",
            "meihua.changed_hexagram.classical",
            "meihua.calendar_policy.solar_term_date_reference",
            "meihua.calendar_policy.civil_clock_resolution",
            "meihua.calendar_policy.label_precision.matched_events",
            "interpretation.line_oracles",
            "interpretation.traditional_stage_readings",
            "interpretation.traditional_judgement",
            "interpretation.moving_line_oracle",
        ),
        cli_request_file=True,
    ),
    ToolSpec(
        name="meihua_cast",
        bind=bind_kwargs(calculate_meihua_cast),
        request_model_loader=request_model_ref(
            "fatebridge.core.requests.meihua", "MeihuaCastRequest"
        ),
        required_output_fields=(
            "analysis_type",
            "analysis_context",
            "meihua",
            "interpretation",
            "summary",
        ),
        summary="梅花显式起卦与解卦：支持物数、声音、尺寸、字形笔画/字数、农历加数或已有卦码；公历换算用 meihua_time_cast。",
        operation_label_zh="梅花显式起卦",
        family="divination",
        rest_path="/api/divination/meihua/cast",
        default_omit=(
            "meihua.base_hexagram.classical",
            "meihua.changed_hexagram.classical",
            "interpretation.line_oracles",
            "interpretation.traditional_stage_readings",
            "interpretation.traditional_judgement",
            "interpretation.moving_line_oracle",
        ),
        cli_request_file=True,
    ),
    ToolSpec(
        name="combine_four_gua",
        bind=bind_kwargs(calculate_tongshefa_analysis),
        request_model_loader=request_model_ref(_DIV_REQ, "TongSheFaRequest"),
        required_output_fields=("tongshefa",),
        summary=(
            "统摄四卦组合：按实际给定的 taiyin/taiyang/shaoyang/shaoyin "
            "组合左右卦、潜藏与亲和；不实现蓍草十八变或大衍随机起卦，固定默认不是用户起卦。"
        ),
        operation_label_zh="统摄法",
        family="divination",
        rest_path="/api/divination/combine-four-gua",
        uses_astronomy_runtime=False,
    ),
    ToolSpec(
        name="liuyao",
        bind=bind_kwargs(calculate_sixyao_analysis),
        request_model_loader=request_model_ref(_DIV_REQ, "SixYaoRequest"),
        required_output_fields=("cast", "current_code", "current_hexagram"),
        summary="六爻纳甲：支持摇钱(coin/coins/seed)、已有卦码(gua_code/lines)或时间起卦；可指定用神与日级候选。",
        operation_label_zh="六爻",
        family="divination",
        cpu_bound=True,
        rest_path="/api/divination/liuyao",
        default_omit=(
            "calendar_context",
            "descriptions",
            "current_hexagram.classical",
            "changed_hexagram.classical",
            "liuyao_evidence.lines",
            "liuyao_evidence.fanfu",
            "liuyao_evidence.hidden_spirits",
            "liuyao_evidence.three_harmony",
            "liuyao_evidence.month_model_comparison",
            "liuyao_evidence.timing_candidates",
        ),
        reproducibility=ReproducibilityPolicy(
            random_seed_field="seed",
            seed_condition="method=coin without coins/lines/binary hexagram codes",
        ),
        needs_random_seed=_sixyao_needs_seed,
        batch_policy=BatchInputPolicy(subject_mode="date_clock"),
    ),
    ToolSpec(
        name="canping",
        bind=bind_kwargs(calculate_canping_analysis),
        request_model_loader=request_model_ref(_DIV_REQ, "CanpingRequest"),
        required_output_fields=("benming", "numerology_evidence", "canping_timing"),
        summary="邵子参评数：需明确性别，默认卷六日支起数并配子平大运，支持时刻分段查询；日常命格用 bazi_overview。",
        operation_label_zh="邵子参评数",
        family="divination",
        cpu_bound=True,
        rest_path="/api/divination/canping",
        default_omit=(
            "dayun",
            "liunian_series",
            "numerology_evidence.birth_clock",
            "numerology_evidence.pillar_links",
            "canping_timing.schedule_basis",
            "canping_timing.solar_year_context",
        ),
        batch_policy=BatchInputPolicy(subject_mode="date_clock"),
    ),
    ToolSpec(
        name="heluo",
        bind=bind_kwargs(calculate_heluo_analysis),
        request_model_loader=request_model_ref(_DIV_REQ, "HeluoRequest"),
        required_output_fields=("chart", "numerology_evidence"),
        summary="河洛理数：须明确性别，生成天地数、元堂、先后天卦、大限与流年月日卦序；日常命格用 bazi_overview。",
        operation_label_zh="河洛理数",
        family="divination",
        cpu_bound=True,
        rest_path="/api/divination/heluo",
        default_omit=(
            "dayun",
            "heluo_timing.annual_rows",
            "numerology_evidence.birth_clock",
            "numerology_evidence.pillar_links",
            "solar_term.boundary_context",
            "jiehou_evidence",
            "judge.month_affinity",
            "judge.najia",
            "judge.line_conditions",
            "judge.nayin_fortune",
            "judge.deTi",
            "judge.qi_phases",
            "judge.seasonal_numbers",
            "judge.body_structure",
            "judge.deSheng",
            "judge.deTime",
        ),
        reproducibility=ReproducibilityPolicy(),
        batch_policy=BatchInputPolicy(subject_mode="date_clock"),
    ),
    ToolSpec(
        name="suzhan",
        bind=bind_kwargs(calculate_suzhan_analysis),
        request_model_loader=request_model_ref(_DIV_REQ, "SuZhanRequest"),
        required_output_fields=(
            "analysis_context",
            "analysis_type",
            "params",
            "sukuyo",
            "summary",
            "validation",
        ),
        summary="宿占：按日期定农历二十七宿、七曜与T1299事项条文；提供钟时和经纬度可排星图与现代天文28宿。",
        operation_label_zh="宿占",
        family="divination",
        cpu_bound=True,
        rest_path="/api/divination/suzhan",
        default_omit=(
            "chart",
            "astronomy",
            "params",
            "sukuyo.activity_assessment",
            "sukuyo.calendar",
            "sukuyo.palace_reference",
            "sukuyo.directional_travel",
            "sukuyo.six_palace_reference",
            "sukuyo.conjunction_doctrine",
            "sukuyo.special_day_evidence",
            "sukuyo.lower_methods",
            "sukuyo.taibai_direction_reference",
            "sukuyo.lower_mansion_day",
            "sukuyo.calendar_day",
        ),
        output_validators=(_validate_suzhan_clock,),
        batch_policy=BatchInputPolicy(subject_mode="date_clock"),
    ),
    ToolSpec(
        name="interpret_astrology_dice",
        bind=bind_kwargs(calculate_otherbu_analysis),
        request_model_loader=request_model_ref(_DIV_REQ, "OtherBuRequest"),
        required_output_fields=("planet", "sign", "house"),
        summary="占星骰解读：解读已掷出的 planet/sign/house(0..11) 符号与喜乐关系；可选时间地点仅作独立天象背景。",
        operation_label_zh="占星骰解读",
        family="divination",
        rest_path="/api/divination/astrology-dice/interpret",
        default_omit=(
            "chart",
            "dice_chart",
            "symbolic_details.symbolic_house_ring",
        ),
        batch_policy=BatchInputPolicy(subject_mode="date_clock"),
    ),
    ToolSpec(
        name="sanshi_combined_chart",
        bind=bind_kwargs(calculate_sanshiunited_analysis),
        request_model_loader=request_model_ref(_DIV_REQ, "SanShiUnitedRequest"),
        required_output_fields=(
            "qimen",
            "taiyi",
            "liuren",
            "subresults",
            "synthesis",
        ),
        summary="三式合参：同盘排太乙、六壬与奇门并列五将星门神对应及异文范围；未作联合胜率或吉凶投票。",
        operation_label_zh="三式合参",
        family="divination",
        cpu_bound=True,
        rest_path="/api/divination/sanshi",
        default_omit=(
            "subresults",
            "taiyi.calendar_rules",
            "taiyi.gates",
            "taiyi.long_cycles",
            "taiyi.condition_assessment",
            "taiyi.patterns",
            "taiyi.counter_cycles",
            "taiyi.shiji_derivation",
            "taiyi.determinate_calculation",
            "taiyi.palace_marks",
            "taiyi.center_marks",
            "taiyi.extra_palace_marks",
            "qimen.palaces",
            "qimen.calendar_policy",
            "qimen.assessment",
            "qimen.structure",
            "qimen.fushi_hexagram",
            "qimen.hidden_stems_palace_map",
            "qimen.ju_decision",
            "liuren.twelve_board",
            "liuren.four_lessons",
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
            "liuren.calendar_policy",
            "liuren.meta",
            "liuren.classification",
            "liuren.overview",
            "synthesis.palace_correspondences",
            "synthesis.noble_source_assessment",
        ),
        output_validators=(validate_ren_anchors,),
        batch_policy=BatchInputPolicy(subject_mode="date_clock"),
    ),
]
