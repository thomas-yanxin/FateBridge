"""Fengshui tool declarations and domain binding helpers."""

from __future__ import annotations

from typing import List

from fatebridge.application.bindings import lazy_service, raw_invoke
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.fengshui.models import (
    AnnualRequest,
    AssessRequest,
    BazhaiRequest,
    DirectionsRequest,
    JinsuoRequest,
    MingguaRequest,
    MonthlyRequest,
    XuankongRequest,
)
from fatebridge.core.fengshui.output import FengshuiOutput

SPECS: List[ToolSpec] = []

for _name, _service, _model, _summary in (
    (
        "directions",
        "calculate_directions",
        DirectionsRequest,
        "后天八卦固定方位、宫数与角区索引；可显式提供geomagnetic_reference计算WMM2025地磁与真北/磁北换算候选，保留原始方位，不自动应用宅盘。",
    ),
    (
        "minggua",
        "calculate_minggua",
        MingguaRequest,
        "住户命卦及个人八方关系（独立于宅卦）：支持公历 birth_date，非立春当日不需要出生小时；布局问题优先 fengshui_assess 的 analyze_layout。",
    ),
    (
        "bazhai",
        "calculate_bazhai",
        BazhaiRequest,
        "八宅坐山宅盘、逐人命盘与用途判定；不是完整阳宅三要门主灶结构法",
    ),
    (
        "jinsuo",
        "calculate_jinsuo",
        JinsuoRequest,
        "金锁玉关八宫基础砂水偏好（已确认分类）",
    ),
    (
        "annual_stars",
        "calculate_annual_stars",
        AnnualRequest,
        "立春换年的年度九宫紫白飞星（非山向宅盘）",
    ),
    (
        "monthly_stars",
        "calculate_monthly_stars",
        MonthlyRequest,
        "十二节交节时刻换月的九宫月紫白；可传含时区query_at或已确认的effective_solar_year/solar_month_number，不以公历月/农历月补值，不替代年盘或宅盘，不生成布局处方。",
    ),
    (
        "xuankong_natal",
        "calculate_xuankong_natal",
        XuankongRequest,
        "中州派玄空运山向宅盘、历史定运、兼向替星与边界候选（独立于年星）；interpretation 显式启用 xuankong_conditioned_v1 有限解释，current_period_number/period_evidence 成对，外局分宫独立确认山形/水形，不复用金锁或室内靠背。",
    ),
    (
        "assess",
        "assess",
        AssessRequest,
        "工位、合租和家居风水布局主入口；布局设 analyze_layout=true。"
        "只传确认事实，照片保留候选；位置、朝向、使用人与行动许可分开。"
        "解释已有依据与条件，不等待动作 ready；保留 rulesets/rule_trace 与来源。"
        "具体分支按参数说明及 Onda 风水技能读取，不把个人八字喜忌当环境规则。",
    ),
):
    SPECS.append(
        ToolSpec(
            key=f"fengshui_{_name}",
            bind=raw_invoke(lazy_service("fatebridge.services.fengshui", _service)),
            request_model=_model,
            summary=_summary,
            operation_label_zh=_summary,
            family="fengshui",
            rest_path=f"/api/fengshui/{_name}",
            mcp_name=f"fengshui_{_name}",
            output_model=FengshuiOutput,
            cli_request_file=True,
        )
    )
