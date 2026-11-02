"""Printed Gujin 58 day tables: four extras, without a modern sky epoch.

The cumulative days are transcribed operands, not a table regenerated from
rounded rates. Reverse entry into a final degree is distinct from forward
entry into an initial degree. Neither denotes modern ecliptic degrees.
"""

from __future__ import annotations

import hashlib
import json
from bisect import bisect_right
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_classical import BRANCHES, MANSIONS, STEMS
from fatebridge.core.guolao_historical import (
    GUJIN_58_PURPLE,
    purple_historical_position,
)

DATA = (
    Path(__file__).resolve().parents[1] / "data/guolao/gujin58-four-extras-days-v1.json"
)


def _tables() -> tuple[dict[str, Any], str]:
    blob = DATA.read_bytes()
    source = json.loads(blob)
    for key, table in source["tables"].items():
        names = [row["mansion"] for row in table["intervals"]]
        ends = [Fraction(row["end_phase_days"]) for row in table["intervals"]]
        period = Fraction(table["period_days"])
        if (
            len(names) != 28
            or set(names) != set(MANSIONS)
            or any(b <= a for a, b in zip([Fraction()] + ends, ends))
            or ends[-1] != period
            or Fraction(table["printed_days_per_du"]) <= 0
        ):
            raise ValueError(f"{key}刊表须完整、严格递增并闭合刊载周积，禁止补格归一化")
        step = 1 if table["direction"] == "forward" else -1
        if table["direction"] not in {"forward", "reverse"} or any(
            MANSIONS[(MANSIONS.index(name) + step) % 28] != names[(i + 1) % 28]
            for i, name in enumerate(names)
        ):
            raise ValueError(f"{key}刊表宿序与顺逆方向不符")
        if table["entry_kind"] != ("initial_degree" if step == 1 else "final_degree"):
            raise ValueError(f"{key}顺行初度与逆行末度不得互换")
    offsets = source["factors"]
    node_period = Fraction(source["tables"]["nodes"]["period_days"])
    half = Fraction(source["half_node_period_days"])
    if (
        2 * half != node_period
        or Fraction(offsets["ketu"]["offset_days"])
        - Fraction(offsets["rahu"]["offset_days"])
        != half
    ):
        raise ValueError("罗计刊载半周积与两至后策不符，不能套现代180度修补")
    return source, hashlib.sha256(blob).hexdigest()


def four_extras_source_days(
    zhongji_days: Fraction, *, winter_cycle_days: Fraction | None = None
) -> dict[str, Any]:
    """Reproduce source phases, mansion intervals and the next boundary day.

    The optional winter fraction is a source 60-day-cycle operand, never a JD.
    Published day endpoints control mansion placement; rounded du rates only
    supply a separately labelled discrepancy diagnostic. No global angular
    rescaling, inferred civil dates or interpolation of the new tables.
    """
    if not isinstance(zhongji_days, Fraction):
        raise TypeError("中积须为明确的Fraction原历日数，不接收现代JD浮点值")
    if winter_cycle_days is not None:
        if not isinstance(winter_cycle_days, Fraction):
            raise TypeError("冬至分须为Fraction原历60日周期数")
        if not 0 <= winter_cycle_days < 60:
            raise ValueError("冬至分须在原历60日周期的[0,60)内")
    source, digest = _tables()
    factors = {}
    for key, info in source["factors"].items():
        table = source["tables"][info["table"]]
        period = Fraction(table["period_days"])
        rate = Fraction(table["printed_days_per_du"])
        ends = [Fraction(row["end_phase_days"]) for row in table["intervals"]]
        total = zhongji_days + Fraction(info["offset_days"])
        phase = total % period
        index = bisect_right(ends, phase)
        row = table["intervals"][index]
        name = row["mansion"]
        next_name = table["intervals"][(index + 1) % 28]["mansion"]
        start = ends[index - 1] if index else Fraction()
        end = ends[index]
        wait = end - phase
        boundary = (
            (winter_cycle_days + wait) % 60 if winter_cycle_days is not None else None
        )
        day = (
            boundary.numerator // boundary.denominator if boundary is not None else None
        )
        width = GUJIN_58_PURPLE.widths_du[MANSIONS.index(name)]
        degree = None
        if key == "purple":
            # Existing purple implementation is an independent integration
            # check: its exact width/rate reconstruction must match this table.
            purple = purple_historical_position(zhongji_days)
            if (
                purple.mansion != name
                or purple.interval_start_days != start
                or purple.interval_end_days != end
            ):
                raise ValueError("紫气新旧刊表不一致，不以改边界消除差异")
            degree = str(purple.degree_in_mansion_du)
        factors[key] = {
            "name": info["name"],
            "phase_origin": table["phase_origin"],
            "direction": table["direction"],
            "entry_kind": table["entry_kind"],
            "period_days_exact": str(period),
            "offset_days_exact": str(Fraction(info["offset_days"])),
            "sum_days_exact": str(total),
            "phase_days_exact": str(phase),
            "mansion": name,
            "next_mansion": next_name,
            "interval_start_days_exact": str(start),
            "interval_end_days_exact": str(end),
            "days_until_next_entry_exact": str(wait),
            "printed_days_per_historical_du_exact": str(rate),
            "published_interval_minus_width_times_printed_rate_days_exact": str(
                end - start - width * rate
            ),
            "width_comparison_basis": "same_book_purple_widths_not_independently_inferred_angular_interpolation",
            "degree_in_mansion_historical_du_exact": degree,
            "degree_status": (
                "existing_exact_purple_table"
                if degree is not None
                else "unassigned_published_day_endpoints_not_continuous_angular_calibration"
            ),
            "next_entry_day_cycle_exact": (
                str(boundary) if boundary is not None else None
            ),
            "next_entry_sexagenary_day": (
                STEMS[day % 10] + BRANCHES[day % 12] if day is not None else None
            ),
        }
    return {
        "model_id": source["model_id"],
        "source_data_sha256": digest,
        "source": source["source"],
        "input_kind": "source_zhongji_days_not_modern_julian_day",
        "zhongji_days_exact": str(zhongji_days),
        "winter_cycle_days_exact": (
            str(winter_cycle_days) if winter_cycle_days is not None else None
        ),
        "factors": factors,
        "entry_boundary_policy": "half_open_in_motion_direction_exact_endpoint_enters_next_mansion",
        "period_or_widths_normalized": False,
        "modern_longitudes": None,
        "modern_calendar_date_assigned": False,
        "modern_epoch_calibrated": False,
        "used_in_native_birth_chart": False,
        "gujin58_header_variants_resolved": False,
    }
