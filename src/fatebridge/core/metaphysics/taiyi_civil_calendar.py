"""Retain the exact civil-date lunar evidence already used by annual Taiyi."""

from copy import deepcopy
from datetime import date
from typing import Any


def civil_lunar_evidence(lunar: dict[str, Any], civil_date: date) -> dict[str, Any]:
    """Copy facts from the selected conversion, without another calendar lookup."""
    source = lunar.get("conversion_source")
    return {
        "civil_date": civil_date.isoformat(),
        **{key: lunar[key] for key in ("year", "month", "day", "is_leap_month")},
        "display": f"{lunar['year']}年{lunar['display']}",
        "clock_basis": "civil_date_before_true_solar_correction",
        "provider": "shared_offline_lunar_calendar",
        "conversion_source": deepcopy(source),
        "conversion_source_status": (
            "reported_by_calendar_provider"
            if source is not None
            else "not_reported_by_calendar_provider"
        ),
        "scope": (
            "太乙年计实际使用的输入钟表日期及农历，独立于校正钟面的时间上下文农历。"
            "provider表示共享离线换算管线，含已发布的校正与边界历表；"
            "conversion_source仅复制该次换算实际返回的来源，缺省不补造逐日权威认证。"
        ),
    }


def civil_lunar_text(evidence: dict[str, Any]) -> str:
    """Render only stored facts; supplementary calendar provenance stays intact."""
    text = f"年计所用农历：{evidence['display']}；输入日期：{evidence['civil_date']}。"
    source = evidence.get("conversion_source")
    if source:
        text += (
            f"换算来源：{source['publisher']}《{source['title']}》；{source['url']}。"
            + source.get("calendar_convention", "")
        )
    else:
        text += "换算来源：共享离线农历管线，本次未单列逐日历表来源。"
    return text
