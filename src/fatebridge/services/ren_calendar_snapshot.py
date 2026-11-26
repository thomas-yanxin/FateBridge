"""Civil calendar evidence shared by Liu Ren and Jin Kou snapshots."""

from __future__ import annotations

from typing import Any


def ren_calendar_snapshot_lines(policy: dict[str, Any]) -> list[str]:
    if policy.get("mode") != "civil_instant_checked":
        return ["历法依据：符号推演，未核验真实民用时刻"]
    providers = sorted({term["provider"] for term in policy["solar_term_dependencies"]})
    models = sorted(
        {
            term.get("ephemeris_model", "unknown")
            for term in policy["solar_term_dependencies"]
        }
    )
    future = any(
        term.get("future_leap_seconds_assumed_unchanged")
        for term in policy["solar_term_dependencies"]
    )
    lines = [
        f"输入民用时间：{policy['civil_datetime']}",
        f"日时取用钟：{policy['corrected_clock']}（{'真太阳钟' if policy['day_hour_clock'] == 'apparent_solar' else '民用钟'}）",
        f"换日约定：{policy['day_boundary']}子初；日柱归属日期：{policy['effective_day_date']}（{policy['effective_day_ganzhi']}）",
        "年/月柱以民用瞬间交节换界；月将以民用瞬间中气换界",
        f"交气提供者：{'、'.join(providers)}；提供者状态不代替独立精度核验",
        f"实际交气星历模型：{'、'.join(models)}；依据各交气的模型与来源回执，未据此认证完整精度",
        "交气以TT求解后转换民用时间；小数秒仅为数值分辨率",
        (
            "未来闰秒：依冻结表末值保持不变的假设"
            if future
            else "未来闰秒假设未触发；历史时刻按所列UT1或历史UTC政策处理"
        ),
    ]
    lines.append(
        "香港天文台逐日表仅核对固定UTC+08日期；相符不认证交气时刻，冲突不改计算交界"
    )
    for term in policy["solar_term_dependencies"]:
        ref = term["published_date_reference"]
        if ref["status"] == "outside_published_range":
            lines.append(
                f"{term['role']} {term['name']}：计算+08日期{ref['computed_hko_date']}；超出官方1901—2100逐日表范围，未比较"
            )
        else:
            lines.append(
                f"{term['role']} {term['name']}：计算+08日期{ref['computed_hko_date']}；天文台刊载{ref['published_date']}；{'日期相符' if ref['dates_equal'] else '日期不一致'}"
            )
    resolution = policy.get("civil_clock_resolution")
    if resolution:
        selection = (
            f"重复钟时第{resolution['fold'] + 1}次"
            if resolution["was_ambiguous"]
            else "明确偏移已核对"
        )
        lines.insert(
            1,
            f"民用钟消歧：{resolution['timezone']} {resolution['resolved_utc_offset']}，"
            f"{selection}；对应UTC {resolution['instant_utc']}",
        )
    return lines
