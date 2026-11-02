"""Decompose the actual selected counter without replacing it by a residue."""

from __future__ import annotations

from typing import Any

UNITS = {"year": "年", "month": "节月", "day": "日", "hour": "时辰"}
SOURCE = "https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷01"


def counter_cycles(
    core: dict[str, Any], *, calculation_mode: str | None
) -> dict[str, Any]:
    """Bind 360/60/72 positions to this core's full counter and actual ju.

    Group coordinates do not adjudicate a source caption or the alignment of
    an adapter's origin with actual sexagenary time. No ganzhi is inferred.
    """
    mode = "year" if calculation_mode is None else calculation_mode
    counter, ju = core.get("accumulation"), core.get("kook_number")
    if (
        type(counter) is not int
        or counter < 1
        or type(ju) is not int
        or not 1 <= ju <= 72
        or not isinstance(mode, str)
        or mode not in UNITS
    ):
        raise ValueError("太乙周期分解需要同盘正整数完整计数、实际局号和明确计量单位")
    completed, offset = divmod(counter - 1, 360)
    ji, within_ji = divmod(offset, 60)
    yuan, within_yuan = divmod(offset, 72)
    if within_yuan + 1 != ju:
        raise ValueError("太乙同盘完整计数的72周期位与实际局号不一致")
    return {
        "ruleset_id": "taiyi_selected_counter_cycles_v1",
        "version": "1.0.0",
        "source": SOURCE,
        "paths_relative_to": "taiyi_board",
        "counter_path": "core_board.accumulation",
        "actual_ju_path": "core_board.kook_number",
        "counter": counter,
        "calculation_mode": mode,
        "counter_unit": UNITS[mode],
        "completed_cycles_before_current360": completed,
        "position360": offset + 1,
        "ji60": {"number": ji + 1, "position": within_ji + 1, "size": 60},
        "yuan72": {"number": yuan + 1, "position": within_yuan + 1, "size": 72},
        "actual_kook_number": ju,
        "calendar_ganzhi_alignment": "not_assessed_by_counter_decomposition",
        "scope": "仅分解本次所选完整计数；纪、元指60与72计数组。局号或组内余数不替代完整积数，不据分组反推实际干支、古历起元或原例纪名含义。",
    }


def counter_cycles_text(cycles: dict[str, Any]) -> str:
    """Render stored arithmetic evidence, never recalculate from a clock."""
    ji, yuan = cycles["ji60"], cycles["yuan72"]
    return (
        f"周期计数：本次完整计数{cycles['counter']}{cycles['counter_unit']}，"
        f"当前360周期之前整周{cycles['completed_cycles_before_current360']}，"
        f"周内第{cycles['position360']}位；60组第{ji['number']}组内{ji['position']}，"
        f"72组第{yuan['number']}组内{yuan['position']}，实际局号{cycles['actual_kook_number']}。"
        f"{cycles['scope']}"
    )
