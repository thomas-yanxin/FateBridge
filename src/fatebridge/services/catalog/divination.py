"""Divination tool declarations and domain binding helpers."""

from __future__ import annotations

from functools import partial

from fatebridge.application.bindings import bind_kwargs, service_ref
from fatebridge.application.domain_validators import (
    validate_canping_schedule,
    validate_meihua_clock,
    validate_numerology_clock,
    validate_ren_output,
    validate_suzhan_clock,
)
from fatebridge.application.meihua_clock_binding import meihua_time_invoke
from fatebridge.application.tool_spec import EvidenceViews, ServiceInput, ToolSpec
from fatebridge.core.contracts.output_meihua_cast import MeihuaCastOutput
from fatebridge.core.liuyao.liuyao_casting import needs_random_coin_cast
from fatebridge.core.requests.compatibility import SukuyoCompatibilityRequest
from fatebridge.core.requests.divination import (
    CanpingRequest,
    GuaLookupRequest,
    HeluoRequest,
    MeihuaAnalysisRequest,
    OtherBuRequest,
    SanShiUnitedRequest,
    SixYaoRequest,
    SuZhanRequest,
    TongSheFaRequest,
)
from fatebridge.core.requests.meihua import MeihuaCastRequest
from fatebridge.services.catalog.detail_views import traditional_detail_view

MEIHUA_DETAIL_VIEW = partial(traditional_detail_view, keep_lunar_meihua=True)

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


calculate_sukuyo_compatibility = service_ref(
    "fatebridge.services.divination", "calculate_sukuyo_compatibility"
)


calculate_suzhan_analysis = service_ref(
    "fatebridge.services.divination", "calculate_suzhan_analysis"
)


calculate_tongshefa_analysis = service_ref(
    "fatebridge.services.divination", "calculate_tongshefa_analysis"
)


def _sixyao_needs_seed(data: dict[str, ServiceInput]) -> bool:
    return needs_random_coin_cast(data)


def _meihua_evidence_views(
    views: EvidenceViews | None, *, include_casting: bool
) -> EvidenceViews | None:
    views = views or {}
    fields = [
        "meihua.body_trigram",
        "meihua.use_trigram",
        "interpretation.topic_reading.chapter_qualifications.qualitative_motion",
        "summary",
    ]
    if include_casting:
        fields.append("interpretation.casting_readings")
    views["chapter_qualitative_motion"] = {
        "fields": fields,
        "scope": "Requires interpretation_topic=travel or traveler. A declared NLC1925 grammatical reading selects the candidate's initial body for travel and initial use for traveler. Preserve 多 as an unquantified qualifier; distinguish it from inner-role motion and field observations. Existing occurrence-count readings remain unresolved. No probability, route, location, safety or return-time certificate.",
    }
    return views


def _meihua_analysis_views(
    views: EvidenceViews | None,
) -> EvidenceViews | None:
    return _meihua_evidence_views(views, include_casting=False)


def _meihua_cast_views(views: EvidenceViews | None) -> EvidenceViews | None:
    return _meihua_evidence_views(views, include_casting=True)


SPECS: list[ToolSpec] = [
    ToolSpec(
        name="gua_lookup",
        bind=bind_kwargs(calculate_gua_lookup),
        request_model=GuaLookupRequest,
        summary="卦象查询：按八卦或六十四卦名、卦码批量查结构，六十四卦附《周易》经文与出处。",
        operation_label_zh="卦象查询",
        family="divination",
        rest_path="/api/divination/gua",
        uses_astronomy_runtime=False,
    ),
    ToolSpec(
        name="meihua_time_cast",
        bind=meihua_time_invoke(calculate_meihua_analysis),
        request_model=MeihuaAnalysisRequest,
        summary="梅花时间起卦：按公历钟时与时区查农历取数，返回本变互卦、初中终生克与原文来源；weather选天时条款。",
        operation_label_zh="梅花易数",
        family="divination",
        rest_path="/api/divination/meihua/time-cast",
        cli_request_file=True,
        evidence_views_builder=_meihua_analysis_views,
        output_validators=(validate_meihua_clock,),
        detail_view=MEIHUA_DETAIL_VIEW,
    ),
    ToolSpec(
        name="meihua_cast",
        bind=bind_kwargs(calculate_meihua_cast),
        request_model=MeihuaCastRequest,
        output_model=MeihuaCastOutput,
        required_output_fields=(
            "analysis_type",
            "input_normalized",
            "meihua",
            "interpretation",
            "summary",
        ),
        summary="梅花显式起卦与解卦：支持物数、声音、尺寸、字形笔画/字数、农历加数或已有卦码；公历换算用 meihua_time_cast。",
        operation_label_zh="梅花显式起卦",
        family="divination",
        rest_path="/api/divination/meihua/cast",
        cli_request_file=True,
        evidence_views_builder=_meihua_cast_views,
        detail_view=MEIHUA_DETAIL_VIEW,
    ),
    ToolSpec(
        name="combine_four_gua",
        bind=bind_kwargs(calculate_tongshefa_analysis),
        request_model=TongSheFaRequest,
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
        request_model=SixYaoRequest,
        summary="六爻纳甲：支持摇钱(coin/coins/seed)、已有卦码(gua_code/lines)或时间起卦；可指定用神与日级候选。",
        operation_label_zh="六爻",
        family="divination",
        cpu_bound=True,
        rest_path="/api/divination/liuyao",
        needs_random_seed=_sixyao_needs_seed,
    ),
    ToolSpec(
        name="canping",
        bind=bind_kwargs(calculate_canping_analysis),
        request_model=CanpingRequest,
        summary="邵子参评数：需明确性别，默认卷六日支起数并配子平大运，支持时刻分段查询；日常命格用 bazi_overview。",
        operation_label_zh="邵子参评数",
        family="divination",
        cpu_bound=True,
        rest_path="/api/divination/canping",
        output_validators=(validate_numerology_clock, validate_canping_schedule),
    ),
    ToolSpec(
        name="heluo",
        bind=bind_kwargs(calculate_heluo_analysis),
        request_model=HeluoRequest,
        summary="河洛理数：须明确性别，生成天地数、元堂、先后天卦、大限与流年月日卦序；日常命格用 bazi_overview。",
        operation_label_zh="河洛理数",
        family="divination",
        cpu_bound=True,
        rest_path="/api/divination/heluo",
        output_validators=(validate_numerology_clock,),
    ),
    ToolSpec(
        name="suzhan",
        bind=bind_kwargs(calculate_suzhan_analysis),
        request_model=SuZhanRequest,
        summary="宿占：按日期定农历二十七宿、七曜与T1299事项条文；提供钟时和经纬度可排星图与现代天文28宿。",
        operation_label_zh="宿占",
        family="divination",
        cpu_bound=True,
        rest_path="/api/divination/suzhan",
        output_validators=(validate_suzhan_clock,),
    ),
    ToolSpec(
        name="sukuyo_compatibility",
        bind=bind_kwargs(calculate_sukuyo_compatibility),
        request_model=SukuyoCompatibilityRequest,
        summary="宿曜双人相性：农历月日定二十七宿，T1299三九法双向关系；闰月保留候选。",
        operation_label_zh="宿曜合盘",
        family="compatibility",
        rest_path="/api/compatibility/sukuyo",
    ),
    ToolSpec(
        name="interpret_astrology_dice",
        bind=bind_kwargs(calculate_otherbu_analysis),
        request_model=OtherBuRequest,
        summary="占星骰解读：解读已掷出的 planet/sign/house(0..11) 符号与喜乐关系；可选时间地点仅作独立天象背景。",
        operation_label_zh="占星骰解读",
        family="divination",
        rest_path="/api/divination/astrology-dice/interpret",
    ),
    ToolSpec(
        name="sanshi_combined_chart",
        bind=bind_kwargs(calculate_sanshiunited_analysis),
        request_model=SanShiUnitedRequest,
        summary="三式合参：同盘排太乙、六壬与奇门并列五将星门神对应及异文范围；未作联合胜率或吉凶投票。",
        operation_label_zh="三式合参",
        family="divination",
        cpu_bound=True,
        rest_path="/api/divination/sanshi",
        output_validators=(validate_ren_output,),
    ),
]
