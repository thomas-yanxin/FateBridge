"""Named-source mean lunations: never infer true lunar calendar dates."""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_classical import BRANCHES, STEMS
from fatebridge.core.guolao_four_extras import four_extras_source_days

DATA = (
    Path(__file__).resolve().parents[1] / "data/guolao/shoushi-mean-lunations-v1.json"
)
GUJIN = "gujin36_shoushi"
YUANSHI = "yuanshi54_nlc166"


def source_mean_lunation(
    zhongji_days: Fraction,
    days_after_winter: Fraction,
    *,
    profile_id: str,
) -> dict[str, Any]:
    """Exact lower-reckoning mean month and day-cycle arithmetic.

    Gujin36 prints runying20.205; NLC YuanShi54 prints20.185. Both are kept,
    and the caller must name one. A mean-lunation slot is not a civil lunar
    month. Printed unadjusted labels do not establish intercalary months.
    """
    for name, value in [("中积", zhongji_days), ("距冬至日数", days_after_winter)]:
        if not isinstance(value, Fraction):
            raise TypeError(f"{name}须为明确的Fraction原历日数，不接收现代JD浮点值")
        if value < 0:
            raise ValueError(f"{name}须非负；不借下算公式推定上考或岁前事件")
    blob = DATA.read_bytes()
    source = json.loads(blob)
    if not isinstance(profile_id, str) or profile_id not in source["profiles"]:
        raise ValueError("须明确选择具名经朔参数，不能混用闰应")
    profile = source["profiles"][profile_id]
    month = Fraction(profile["synodic_month_days"])
    offset = Fraction(profile["runying_days"])
    qiying = Fraction(profile["qiying_days"])
    if not 0 <= offset < month or not 0 <= qiying < 60:
        raise ValueError("具名经朔参数超出原历周期")
    rows = source["gujin58_month_table"]
    if len(rows) != 12 or any(
        row["lunation_index"] != i
        or Fraction(row["cumulative_days"])
        != i * Fraction(source["profiles"][GUJIN]["synodic_month_days"])
        for i, row in enumerate(rows)
    ):
        raise ValueError("刊载月数钤不符，不补格或改值归一化")
    runyu = (zhongji_days + offset) % month
    month_total = runyu + days_after_winter
    index = month_total // month
    elapsed = month_total - index * month
    winter_total = zhongji_days + qiying
    mean_total = winter_total - runyu + index * month
    event_total = winter_total + days_after_winter
    mean_cycle = mean_total % 60
    event_cycle = event_total % 60
    day = mean_cycle // 1
    row = (
        rows[index]
        if profile["month_table_applicable"] and 0 <= index < len(rows)
        else None
    )
    return {
        "model_id": source["model_id"],
        "profile_id": profile_id,
        "source_profile": profile,
        "source_data_sha256": hashlib.sha256(blob).hexdigest(),
        "zhongji_days_exact": str(zhongji_days),
        "days_after_winter_exact": str(days_after_winter),
        "runying_days_exact": str(offset),
        "synodic_month_days_exact": str(month),
        "runyu_days_exact": str(runyu),
        "winter_cycle_days_exact": str(winter_total % 60),
        "runyu_plus_event_days_exact": str(month_total),
        "mean_lunation_index": index,
        "unintercalated_table_slot_label": (
            row["unintercalated_slot_label"] if row is not None else None
        ),
        "table_slot_status": (
            "unadjusted_mean_slot_not_assigned_lunar_month"
            if row is not None
            else "no_applicable_printed_slot_not_wrapped_modulo_twelve"
        ),
        "days_since_mean_conjunction_exact": str(elapsed),
        "mean_conjunction_offset_from_winter_days_exact": str(index * month - runyu),
        "mean_conjunction_day_cycle_exact": str(mean_cycle),
        "mean_conjunction_sexagenary_day": STEMS[day % 10] + BRANCHES[day % 12],
        "event_day_cycle_exact": str(event_cycle),
        "unaccepted_day_diagnostics": {
            "floor_elapsed_plus_one": elapsed // 1 + 1,
            "midnight_difference_plus_one": event_total // 1 - mean_total // 1 + 1,
            "either_is_accepted_lunar_day": False,
        },
        "lunar_date": None,
        "true_new_moon_calibrated": False,
        "intercalation_reconstructed": False,
        "modern_calendar_date_assigned": False,
        "modern_epoch_calibrated": False,
        "used_in_native_birth_chart": False,
    }


def gujin_four_extras_lunations(zhongji_days: Fraction) -> dict[str, Any]:
    """Connect the Gujin58 entry waits to its explicitly named mean-month chain.

    The YuanShi profile is returned only as a comparison at identical input
    operands; it does not replace Gujin's runying to improve a match.
    """
    reference = source_mean_lunation(zhongji_days, Fraction(), profile_id=GUJIN)
    alternative = source_mean_lunation(zhongji_days, Fraction(), profile_id=YUANSHI)
    positions = four_extras_source_days(
        zhongji_days,
        winter_cycle_days=Fraction(reference["winter_cycle_days_exact"]),
    )
    factors = {
        key: source_mean_lunation(
            zhongji_days,
            Fraction(record["days_until_next_entry_exact"]),
            profile_id=GUJIN,
        )
        for key, record in positions["factors"].items()
    }
    return {
        "profile_id": GUJIN,
        "reference_at_winter": reference,
        "yuanshi_reference_comparison_at_same_operands": alternative,
        "comparison_replaces_gujin_parameters": False,
        "four_extras_source_data_sha256": positions["source_data_sha256"],
        "factors": factors,
        "printed_calendar_dates_used_as_algorithm_outputs": False,
        "lunar_dates_assigned": False,
    }
