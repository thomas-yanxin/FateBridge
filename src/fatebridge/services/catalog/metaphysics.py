"""Metaphysics tool declarations and domain binding helpers."""

from __future__ import annotations

from fatebridge.application.bindings import bind_kwargs, bind_person, service_ref
from fatebridge.application.domain_validators import validate_ren_output
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.core.requests.metaphysics import (
    JinkouAnalysisRequest,
    LiuRengGodsRequest,
    LiuRengRunyearRequest,
    QimenAnalysisRequest,
    TaiyiAnalysisRequest,
    ZiweiBirthRequest,
    ZiweiHoroscopeRequest,
    ZiweiRulesRequest,
)

calculate_jinkou_analysis = service_ref(
    "fatebridge.services.metaphysics", "calculate_jinkou_analysis"
)


calculate_liureng_gods = service_ref(
    "fatebridge.services.metaphysics", "calculate_liureng_gods"
)


calculate_liureng_runyear = service_ref(
    "fatebridge.services.metaphysics", "calculate_liureng_runyear"
)


calculate_qimen_analysis = service_ref(
    "fatebridge.services.metaphysics", "calculate_qimen_analysis"
)


calculate_taiyi_analysis = service_ref(
    "fatebridge.services.metaphysics", "calculate_taiyi_analysis"
)


calculate_ziwei_birth = service_ref(
    "fatebridge.services.metaphysics", "calculate_ziwei_birth"
)


calculate_ziwei_horoscope = service_ref(
    "fatebridge.services.metaphysics", "calculate_ziwei_horoscope"
)


calculate_ziwei_rules = service_ref(
    "fatebridge.services.metaphysics", "calculate_ziwei_rules"
)


def _compact_qimen(result: ServiceResult) -> ServiceResult:
    board = result["qimen"]
    return {
        **result,
        "qimen": {
            **board,
            "palaces": [
                {key: value for key, value in palace.items() if key != "evidence"}
                for palace in board["palaces"]
            ],
        },
    }


def _compact_ziwei_horoscope(result: ServiceResult) -> ServiceResult:
    horoscope = result["ziwei_horoscope"]
    fields = {
        "scope",
        "status",
        "unavailable_reason",
        "first_age",
        "palace_name",
        "scope_palace_role",
        "branch",
        "stem",
        "stem_origin",
        "mutagen",
    }
    return {
        **result,
        "ziwei_horoscope": {
            **{
                key: value for key, value in horoscope.items() if key != "annual_cycles"
            },
            "scopes": [
                {key: value for key, value in scope.items() if key in fields}
                for scope in horoscope["scopes"]
            ],
        },
    }


def _compact_ziwei_rules(result: ServiceResult) -> ServiceResult:
    return {
        **result,
        "rule_catalogue": {
            key: value
            for key, value in result["rule_catalogue"].items()
            if key != "named_patterns"
        },
    }


SPECS: list[ToolSpec] = [
    ToolSpec(
        name="ziwei_birth_chart",
        bind=bind_person(calculate_ziwei_birth, also_pass=("birth_utc_offset",)),
        request_model=ZiweiBirthRequest,
        summary="紫微斗数本命盘（星位、结构与循环来源；四化可显式选明刊原表，未知性别保留可确定标记）。",
        operation_label_zh="紫微命盘",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/ziwei/birth-chart",
    ),
    ToolSpec(
        name="ziwei_timing",
        bind=bind_person(calculate_ziwei_horoscope, also_pass=("birth_utc_offset",)),
        request_model=ZiweiHoroscopeRequest,
        summary="紫微斗数运限（六层索引与童限）；沿用所选四化表，未知性别仅大限/小限标不可定。",
        operation_label_zh="紫微运限",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/ziwei/timing",
        compact_view=_compact_ziwei_horoscope,
    ),
    ToolSpec(
        name="ziwei_rules",
        bind=bind_kwargs(calculate_ziwei_rules),
        request_model=ZiweiRulesRequest,
        summary="紫微斗数规则查表：按年干返回四化参照；排盘用 ziwei_birth_chart/ziwei_timing。",
        operation_label_zh="紫微规则",
        family="metaphysics",
        rest_path="/api/ziwei/rules",
        compact_view=_compact_ziwei_rules,
    ),
    ToolSpec(
        name="liuren_chart",
        bind=bind_kwargs(calculate_liureng_gods),
        request_model=LiuRengGodsRequest,
        summary="六壬起课：输出四课、九宗门三传、天将、旬遁与细课名；金口诀用 jinkou。",
        operation_label_zh="六壬课",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/liuren/chart",
        output_validators=(validate_ren_output,),
    ),
    ToolSpec(
        name="liuren_yearly_timing",
        bind=bind_person(
            calculate_liureng_runyear,
            also_pass=("use_true_solar_time", "birth_utc_offset"),
        ),
        request_model=LiuRengRunyearRequest,
        summary="六壬行年：按农历虚岁推男女行年并起课；问具体单事用 liuren_chart。",
        operation_label_zh="六壬流年",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/liuren/timing/yearly",
        output_validators=(validate_ren_output,),
    ),
    ToolSpec(
        name="qimen",
        bind=bind_kwargs(calculate_qimen_analysis),
        request_model=QimenAnalysisRequest,
        summary="奇门遁甲：方位选择、行动时机与谋略布局；单事成败用 liuyao，大势用 taiyi。",
        operation_label_zh="奇门遁甲",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/qimen",
        compact_view=_compact_qimen,
    ),
    ToolSpec(
        name="taiyi",
        bind=bind_kwargs(calculate_taiyi_analysis),
        request_model=TaiyiAnalysisRequest,
        summary="太乙神数：年/月/日/时四计，返回二目、主客算、四将与规则路径；日计用金钥匙积日。",
        operation_label_zh="太乙",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/taiyi",
    ),
    ToolSpec(
        name="jinkou",
        bind=bind_kwargs(calculate_jinkou_analysis),
        request_model=JinkouAnalysisRequest,
        summary="金口诀：按日干、月将、占时与地分起四位，含五动三动、六十四课钤及本命另课。",
        operation_label_zh="金口诀",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/jinkou",
        output_validators=(validate_ren_output,),
    ),
]
