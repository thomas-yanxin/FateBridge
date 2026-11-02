"""Capture the actual solar correction, without computing astronomy again."""

import math
from datetime import datetime, timezone
from typing import Any

from fatebridge.utils.solar_time import EQUATION_OF_TIME_METHOD
from fatebridge.utils.timezones import parse_timezone_name


def solar_time_receipt(
    *,
    civil_instant: datetime,
    corrected_label: datetime,
    timezone_name: str,
    longitude: float,
    adjustment: dict[str, float],
) -> dict[str, Any]:
    """Bind the decomposed correction to its physical input and solar label."""
    if civil_instant.utcoffset() is None:
        raise ValueError("太阳时修正依据须保留带时区的原民用实际时刻")
    local = civil_instant.astimezone(parse_timezone_name(timezone_name))
    total = adjustment["total_correction_minutes"]
    parts = (
        adjustment["longitude_correction_minutes"]
        + adjustment["equation_of_time_minutes"]
        - adjustment["daylight_saving_minutes"]
    )
    actual_delta = (
        corrected_label.replace(tzinfo=None) - local.replace(tzinfo=None)
    ).total_seconds()
    if not all(math.isfinite(v) for v in (*adjustment.values(), longitude)) or not (
        abs(parts - total) < 1e-9 and abs(actual_delta - total * 60) < 2e-6
    ):
        raise ValueError("太阳时分项、总修正与实际钟表标签不一致；不能生成不实依据")
    seconds = (
        corrected_label.hour * 3600
        + corrected_label.minute * 60
        + corrected_label.second
        + corrected_label.microsecond / 1e6
    )
    hour_distance = (seconds - 3600) % 7200
    day_distance = (seconds - 23 * 3600) % 86400
    return {
        "status": "captured_at_seed_calculation",
        "applied": True,
        "strategy": "apparent",
        "equation_of_time_method": EQUATION_OF_TIME_METHOD,
        "equation_of_time_time_scale": "UTC_as_UT1",
        "civil_input_instant_utc": civil_instant.astimezone(timezone.utc).isoformat(),
        "civil_timezone": timezone_name,
        "longitude": longitude,
        **adjustment,
        "apparent_solar_label": corrected_label.replace(tzinfo=None).isoformat(),
        "correction_basis": "civil_wall_clock_to_solar_label_not_elapsed_time",
        "physical_input_instant_shifted": False,
        "subsecond_accuracy_certified": False,
        "boundary_distances_seconds": {
            "nearest_double_hour_boundary": min(hour_distance, 7200 - hour_distance),
            "day_boundary_23": min(day_distance, 86400 - day_distance),
            "certainty_inferred_from_distance": False,
        },
        "scope": "均时差按UTC近似UT1；未引入实测DUT1，太阳标签不是转换后的另一个物理时刻",
    }


def solar_time_evidence_lines(evidence: dict[str, Any]) -> list[str]:
    if not evidence.get("applied"):
        return []
    if evidence.get("status") != "captured_at_seed_calculation":
        return ["真太阳时修正：本种子未提供分项算法依据，不能从总修正量补写均时差方法"]
    return [
        f"真太阳时修正：经度差{evidence['longitude_correction_minutes']:.6f}分＋均时差{evidence['equation_of_time_minutes']:.6f}分－夏令时{evidence['daylight_saving_minutes']:.6f}分＝总修正{evidence['total_correction_minutes']:.6f}分；均时差方法{evidence['equation_of_time_method']}，UTC近似UT1，未认证亚秒精度",
        f"原实际时刻{evidence['civil_input_instant_utc']}，太阳钟表标签{evidence['apparent_solar_label']}；标签供日时取用，不移动原交节时刻",
        f"太阳标签距最近换时{evidence['boundary_distances_seconds']['nearest_double_hour_boundary']:.3f}秒、子初换日{evidence['boundary_distances_seconds']['day_boundary_23']:.3f}秒；距离不是误差界，不据此保证边界归属",
    ]
