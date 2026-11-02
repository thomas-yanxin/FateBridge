"""Birth-clock component provenance, separate from measurement accuracy."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.civil_clock import format_utc_offset, utc_instant
from fatebridge.utils.timezones import parse_timezone_name, timezone_rules_metadata

if TYPE_CHECKING:
    from fatebridge.utils.solar_time import NormalizedBirthTime


def birth_clock_input_receipt(
    person: PersonInfo, normalized: NormalizedBirthTime
) -> Dict[str, Any]:
    """Declare old nominal defaults without inventing a recording interval."""
    supplied = ["year", "month", "day", "hour"]
    if "birth_minute" in person.model_fields_set:
        supplied.append("minute")
    if person.birth_second is not None:
        supplied.append("second")
    omitted = [part for part in ("minute", "second") if part not in supplied]
    civil = normalized.input_datetime
    zone = parse_timezone_name(normalized.timezone)
    civil = (
        civil.replace(tzinfo=zone) if civil.tzinfo is None else civil.astimezone(zone)
    )
    receipt: Dict[str, Any] = {
        "method_id": "birth_clock_components_v1",
        "supplied_components": supplied,
        "omitted_components": omitted,
        "calculation_defaults": {part: 0 for part in omitted},
        "nominal_civil_datetime": civil.isoformat(),
        "corrected_clock_datetime": normalized.corrected_datetime.isoformat(),
        "timezone": normalized.timezone,
        "uncertainty_interval": None,
        "observed_precision_certified": False,
        "scope": (
            "只声明输入分量及兼容计算参考；省略分量按既有00值计算，不表示实际出生"
            "在整时或整分。显式秒数也不认证记录准确度。未从分量省略推定舍入方式、"
            "误差区间或分量之间的稳定性；另行提供的时间范围核对保持其声明的采样范围。"
        ),
    }
    if person.birth_utc_offset is not None:
        offset = civil.utcoffset()
        assert offset is not None
        receipt.update(
            requested_utc_offset=person.birth_utc_offset,
            civil_utc_offset=format_utc_offset(offset),
            civil_instant_utc=utc_instant(civil).isoformat(),
            civil_fold=civil.fold,
            civil_time_ambiguous=(
                civil.replace(fold=0).utcoffset() != civil.replace(fold=1).utcoffset()
            ),
            timezone_source=normalized.timezone_source,
            timezone_rules=timezone_rules_metadata(normalized.timezone),
            offset_selection_scope="偏移只按已解析时区的规则校验并选择实际时刻；不认证出生记录、推断时区或未来规则。",
        )
    return receipt


def birth_clock_snapshot_lines(receipt: Dict[str, Any]) -> List[str]:
    """Keep source precision visible alongside the nominal chart."""
    omitted = receipt.get("omitted_components", [])
    assumptions = [
        f"{'分钟' if part == 'minute' else '秒数'}未提供，计算沿用00"
        for part in omitted
    ]
    lines = [
        f"出生钟时计算参考：{receipt.get('nominal_civil_datetime', '未提供')}",
        (
            "；".join(assumptions) + "；未推定记录精度或误差区间。"
            if assumptions
            else "已传入分、秒分量；这不认证出生记录的实际精度。"
        ),
    ]
    if "requested_utc_offset" in receipt:
        ambiguity = "重复钟时" if receipt.get("civil_time_ambiguous") else "唯一钟时"
        lines.append(
            f"民用偏移核对：{receipt['civil_utc_offset']}，{ambiguity}，"
            f"fold={receipt['civil_fold']}；实际UTC：{receipt['civil_instant_utc']}。"
            "原时区规则用于后续交运；偏移选择不认证出生记录。"
        )
    return lines
