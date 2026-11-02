"""Describe the existing winter selector without adjudicating an ancient epoch."""

from __future__ import annotations

from typing import Any


def winter_origin_selection(
    origin: dict[str, Any], winter: dict[str, Any], clock_basis: str
) -> dict[str, Any]:
    """Copy the actual count origin and selected solar anchor from this board."""
    return {
        "policy_id": "latest_elapsed_winter_solstice_instant_modern_v1",
        "selection_switch_basis": "winter_solstice_instant",
        "selected_winter_utc": winter["datetime_with_offset"],
        "count_origin_date": origin["origin_effective_date"],
        "count_origin_clock": origin.get(
            "origin_clock", origin["origin_effective_date"] + "T00:00:00"
        ),
        "clock_basis": clock_basis,
        "source": origin["source"],
        "classical_source_scope": "原书给冬至前甲子起计；该引文不裁定每年何时启用下一起元。",
        "classical_activation_adjudicated": False,
        "scope": (
            "当前现代适配按已过冬至实刻选元，随后取该冬至所属日或此前甲子。"
            "计数起点是所选钟面标签，选元切换是冬至瞬间，两者分列；"
            "即使下一冬至之前的甲子已开始，也不提前选用尚未到达的冬至。"
            "原典年度启元时点及冬至同日甲子取法均未裁定，不能据同相位认证。"
        ),
    }


def winter_origin_selection_text(selected: dict[str, Any]) -> str:
    return (
        f"冬至选元约定：按已过冬至实刻选元，所用冬至UTC标签{selected['selected_winter_utc']}；"
        f"计数起点钟面{selected['count_origin_clock']}（{selected['clock_basis']}）。"
        + str(selected["scope"])
    )
