"""Metaphysics tool declarations and domain binding helpers."""

from __future__ import annotations

from typing import List

from fatebridge.application.bindings import lazy_service, person_invoke, raw_invoke
from fatebridge.application.tool_spec import ToolSpec
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

calculate_jinkou_analysis = lazy_service(
    "fatebridge.services.metaphysics", "calculate_jinkou_analysis"
)


calculate_liureng_gods = lazy_service(
    "fatebridge.services.metaphysics", "calculate_liureng_gods"
)


calculate_liureng_runyear = lazy_service(
    "fatebridge.services.metaphysics", "calculate_liureng_runyear"
)


calculate_qimen_analysis = lazy_service(
    "fatebridge.services.metaphysics", "calculate_qimen_analysis"
)


calculate_taiyi_analysis = lazy_service(
    "fatebridge.services.metaphysics", "calculate_taiyi_analysis"
)


calculate_ziwei_birth = lazy_service(
    "fatebridge.services.metaphysics", "calculate_ziwei_birth"
)


calculate_ziwei_horoscope = lazy_service(
    "fatebridge.services.metaphysics", "calculate_ziwei_horoscope"
)


calculate_ziwei_rules = lazy_service(
    "fatebridge.services.metaphysics", "calculate_ziwei_rules"
)

SPECS: List[ToolSpec] = [
    # --- Metaphysics -------------------------------------------------------
    ToolSpec(
        key="ziwei_birth",
        bind=person_invoke(calculate_ziwei_birth, also_pass=("birth_utc_offset",)),
        request_model=ZiweiBirthRequest,
        summary="紫微斗数本命盘（星位、结构与循环来源；四化可显式选明刊原表，未知性别保留可确定标记）。",
        operation_label_zh="紫微命盘",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/cn/ziwei/birth",
        mcp_name="ziwei_birth",
    ),
    ToolSpec(
        key="ziwei_horoscope",
        bind=person_invoke(calculate_ziwei_horoscope, also_pass=("birth_utc_offset",)),
        request_model=ZiweiHoroscopeRequest,
        summary="紫微斗数运限（六层索引与独立童限；四化继承所选表，未起大限时该层为空，未含全部流曜飞宫）。",
        operation_label_zh="紫微运限",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/cn/ziwei/horoscope",
        mcp_name="ziwei_horoscope",
    ),
    ToolSpec(
        key="ziwei_rules",
        bind=raw_invoke(calculate_ziwei_rules),
        request_model=ZiweiRulesRequest,
        summary=(
            "紫微斗数规则查表：按年干返回四化等规则参照，供解读时查证；"
            "起命盘用 ziwei_birth，看运限用 ziwei_horoscope。"
        ),
        operation_label_zh="紫微规则",
        family="metaphysics",
        rest_path="/api/cn/ziwei/rules",
        mcp_name="ziwei_rules",
    ),
    ToolSpec(
        key="liureng_gods",
        bind=raw_invoke(calculate_liureng_gods),
        request_model=LiuRengGodsRequest,
        summary=(
            "六壬起课：输出四课、九宗门三传、天将、旬遁与从实际计算推导的细课名；"
            "规则匹配不代表现实预测已验证。金口诀四位用 jinkou。"
        ),
        operation_label_zh="六壬课",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/cn/liureng/gods",
        mcp_name="liureng_gods",
    ),
    ToolSpec(
        key="liureng_runyear",
        bind=person_invoke(
            calculate_liureng_runyear,
            also_pass=("use_true_solar_time", "birth_utc_offset"),
        ),
        request_model=LiuRengRunyearRequest,
        summary=(
            "六壬行年：按农历虚岁推男女行年，并以分析时刻起六壬课；"
            "没有逐流月预测。问具体单事用 liureng_gods。"
        ),
        operation_label_zh="六壬流年",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/cn/liureng/runyear",
        mcp_name="liureng_runyear",
    ),
    ToolSpec(
        key="qimen",
        bind=raw_invoke(calculate_qimen_analysis),
        request_model=QimenAnalysisRequest,
        summary=(
            "奇门遁甲：问方位选择 / 行动时机 / 谋略布局（含趋吉避凶方位）；"
            "问单事成败用 sixyao，看大势国运用 taiyi。"
        ),
        operation_label_zh="奇门遁甲",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/cn/qimen",
        mcp_name="qimen",
    ),
    ToolSpec(
        key="taiyi",
        bind=raw_invoke(calculate_taiyi_analysis),
        request_model=TaiyiAnalysisRequest,
        summary=(
            "太乙神数：年计、节月月计、金钥匙积日日计、冬夏至换遁时计，返回二目、主客算、四将及规则路径；年计另附卷五年度十神。"
            "日计附定计、直门与分源十精，天时周期及多处正文/课式异数保留。"
            "时计可明选金钥匙冬至前甲子完整积时、定计和阴阳四门；定计原数及三门课语仍有未决。"
            "月/日/时计为明确约定的现代天文适配；原典表文分歧、古历及完整命法仍待验收。"
        ),
        operation_label_zh="太乙",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/cn/taiyi",
        mcp_name="taiyi",
    ),
    ToolSpec(
        key="jinkou",
        bind=raw_invoke(calculate_jinkou_analysis),
        request_model=JinkouAnalysisRequest,
        summary=(
            "金口诀：按日干、月将、占时和地分起四位，分列旺衰、得气、阴阳用位条件、五动三动、六十四课钤与三合空破条件；"
            "地分省略按时支回退；已确认natal_branch或birth_year_ganzhi可算将命大绝及独立本命另课，派生地分不替换主课；未知不补造。原典仅局部核对，现实预测未经验证。"
        ),
        operation_label_zh="金口诀",
        family="metaphysics",
        cpu_bound=True,
        rest_path="/api/cn/jinkou",
        mcp_name="jinkou",
    ),
]
