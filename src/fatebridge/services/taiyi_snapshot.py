"""Taiyi snapshot sections."""

from __future__ import annotations

from typing import Any

from fatebridge.core.local_techniques.snapshot import join_lines
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.taiyi_long_cycles import long_cycle_text
from fatebridge.core.metaphysics.taiyi_year import evidence_text as taiyi_evidence_text
from fatebridge.services.snapshot_builders import render_snapshot_text


def build_taiyi_snapshot_text(
    *,
    seed: MetaphysicsSeed,
    taiyi: dict[str, Any],
) -> str:
    lunar_calendar = seed.calendar_context.get("lunar_calendar") or {}
    calendar_rules = taiyi.get("calendar_rules") or {}
    historical = calendar_rules.get("historical_calendar")
    civil_lunar = calendar_rules.get("civil_lunar_calendar")
    lunar_display = (
        historical["display"] + "（历史历表，太乙专用）"
        if historical
        else (
            civil_lunar["display"]
            if civil_lunar
            else lunar_calendar.get("display") or "未提供"
        )
    )
    mark_lines = [
        f"{item.get('palace', '宫位')}：{'、'.join(item.get('markers', []) or []) or '无'}"
        for item in taiyi.get("palace_marks", []) or []
    ]
    sections = [
        (
            "起盘信息",
            join_lines(
                [
                    f"{'年计所用农历' if historical or civil_lunar else '时间上下文农历'}：{lunar_display}",
                    f"输入钟时：{seed.input_isoformat()}；时区：{seed.timezone}",
                    f"计算钟面：{seed.calendar_context['solar_datetime']}；{'真太阳时' if seed.applied_true_solar else '直接时间'}",
                    (
                        f"时间上下文农历：{lunar_calendar.get('display') or '未提供'}（校正钟面上下文，不替代年计所用农历）"
                        if historical or civil_lunar
                        else ""
                    ),
                    (
                        f"四柱：{seed.pillars['year'][0]}{seed.pillars['year'][1]}年/"
                        f"{seed.pillars['month'][0]}{seed.pillars['month'][1]}月/"
                        f"{seed.pillars['day'][0]}{seed.pillars['day'][1]}日/"
                        f"{seed.pillars['hour'][0]}{seed.pillars['hour'][1]}时"
                    ),
                    f"当前节气：{seed.calendar_context['current_solar_term']['name']}",
                    f"下个节气：{seed.calendar_context['next_solar_term']['name']}",
                    f"时间算法：{'真太阳时' if seed.applied_true_solar else '直接时间'}",
                ]
            ),
        ),
        (
            "太乙盘",
            join_lines(
                [
                    taiyi.get("style_label", "无"),
                    taiyi.get("accumulation_label", "无"),
                    f"布盘方向：{taiyi.get('rotation', '无')}",
                    f"计法：{taiyi.get('life_method', '无')}",
                    (taiyi.get("core_board") or {}).get("main_calculation", "无"),
                    (taiyi.get("core_board") or {}).get("taiyi_position", "无"),
                    (taiyi.get("core_board") or {}).get("wenchang_position", "无"),
                    f"{taiyi['core_board'].get('ruler_label', '岁君')}：{taiyi['core_board'].get('ruler_branch', taiyi['core_board'].get('suijun', '无'))}",
                    f"合神：{(taiyi.get('core_board') or {}).get('heshen', '无')}",
                ]
            ),
        ),
        ("十六宫标记", join_lines(mark_lines) or "无"),
        ("中宫标记", "、".join(taiyi["center_marks"]["markers"]) or "无星标"),
        ("规则依据", taiyi_evidence_text(taiyi)),
        ("年运十神", long_cycle_text(taiyi.get("long_cycles"))),
    ]
    return render_snapshot_text(sections)
