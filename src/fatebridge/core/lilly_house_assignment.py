"""Lilly p33 cusp virtue, kept distinct from geometric house occupancy."""

from __future__ import annotations

from typing import Any, Sequence

from fatebridge.core.astro.geometry import Angle, angle_fraction, longitude_float
from fatebridge.core.lilly import SOURCE_URL
from fatebridge.core.lilly_houses import house_condition

HOUSE_ATTRIBUTES = tuple(
    f"{name}_house"
    for name in (
        "first",
        "second",
        "third",
        "fourth",
        "fifth",
        "sixth",
        "seventh",
        "eighth",
        "ninth",
        "tenth",
        "eleventh",
        "twelfth",
    )
)


def subject_cusps(subject: Any) -> list[Angle] | None:
    values = [
        getattr(getattr(subject, key, None), "abs_pos", None)
        for key in HOUSE_ATTRIBUTES
    ]
    return (
        None
        if any(v is None for v in values)
        else [angle_fraction(v) for v in values if v is not None]
    )


def assign_cusp_virtue(
    longitude: Angle | None,
    occupied_house: int | None,
    lower_cusp: Angle | None,
    next_cusp: Angle | None,
    *,
    house_system: str | None = None,
    zodiac_type: str | None = None,
) -> dict[str, Any]:
    """Nearest bordering cusp within five degrees, in a valid local arc.

    The source says nearest, not unconditional +5 to every longitude. Exact
    five-degree inclusion is an operational convention; equal nearest cusps
    stay unresolved. P180's wider exception is reported, never fitted here.
    """
    if occupied_house is not None and occupied_house not in range(1, 13):
        raise ValueError("Occupied house must be1..12 or unknown")
    result: dict[str, Any] = {
        "rule_id": "lilly_1647_p33_nearest_cusp_virtue_v1",
        "source_url": SOURCE_URL,
        "source_pages": [33, 154, 180, 552],
        "status": "unavailable",
        "unavailable_reason": "missing_longitude_house_or_adjacent_cusps",
        "geometric_house": occupied_house,
        "assigned_house": None,
        "changed_from_geometric_house": None,
        "five_degree_limit": 5,
        "boundary_policy": "Closed five-degree operational convention; equal nearest cusps unresolved; no same-sign restriction added",
        "assignment_policy": "p33_nearest_adjacent_cusp_within_five_degrees",
        "house_system": house_system,
        "zodiac_type": zodiac_type,
        "source_method_scope": (
            "tropical_regiomontanus_declared_p33_policy"
            if house_system == "R" and zodiac_type in {"Tropic", "Tropical"}
            else "other_or_unknown_chart_method_modern_extension"
        ),
        "source_exception": "p180 assigns Fortune beyond five degrees to house2; this exception is not generalized or threshold-fitted",
        "full_original_text_acceptance": False,
    }
    if (
        longitude is None
        or occupied_house is None
        or lower_cusp is None
        or next_cusp is None
    ):
        return result
    lon, lower, upper = [
        angle_fraction(v) % 360 for v in (longitude, lower_cusp, next_cusp)
    ]
    span, offset = (upper - lower) % 360, (lon - lower) % 360
    result.update(
        longitude=longitude_float(lon),
        lower_cusp=longitude_float(lower),
        next_cusp=longitude_float(upper),
    )
    if not 0 < span < 180 or not 0 <= offset < span:
        result["unavailable_reason"] = (
            "local_arc_not_prograde_short_or_occupancy_inconsistent"
        )
        return result
    previous_gap, next_gap = offset, span - offset
    result.update(
        previous_cusp_gap_degrees=float(previous_gap),
        next_cusp_gap_degrees=float(next_gap),
        previous_cusp_gap_exact_degrees=str(previous_gap),
        next_cusp_gap_exact_degrees=str(next_gap),
    )
    if previous_gap == next_gap and next_gap <= 5:
        result["unavailable_reason"] = "equal_nearest_cusps_within_five_degrees"
        return result
    assigned = (
        occupied_house % 12 + 1
        if next_gap <= 5 and next_gap < previous_gap
        else occupied_house
    )
    result.update(
        status="computed_under_declared_policy",
        unavailable_reason=None,
        assigned_house=assigned,
        changed_from_geometric_house=assigned != occupied_house,
        assigned_p115_house_points=house_condition(assigned, house_system, zodiac_type)[
            "p115_house_points"
        ],
        conditional_reading_zh=(
            f"几何落第{occupied_house}宫；按第33页最近宫头五度政策，效力归第{assigned}宫。"
            "这不改写原生坐标、主掌宫位或宫头，也不等于完整原典居宫判断。"
        ),
    )
    return result


def assign_from_cusps(
    longitude: Angle | None,
    cusps: Sequence[Angle] | None,
    *,
    native_occupied_house: int | None = None,
    house_system: str | None = None,
    zodiac_type: str | None = None,
) -> dict[str, Any]:
    """Validate the complete ring before using adjacent zodiacal house arcs.

    Reversed/projected polar houses are not a zodiacal interval partition.
    Preserve their native occupancy and leave this source policy unavailable.
    """
    empty = assign_cusp_virtue(
        longitude,
        native_occupied_house,
        None,
        None,
        house_system=house_system,
        zodiac_type=zodiac_type,
    )
    if longitude is None or cusps is None:
        return empty
    if len(cusps) != 12:
        raise ValueError("Twelve actual house cusps are required")
    values = [angle_fraction(v) % 360 for v in cusps]
    spans = [(values[(i + 1) % 12] - v) % 360 for i, v in enumerate(values)]
    if sum(spans) != 360 or any(not 0 < v < 180 for v in spans):
        empty["unavailable_reason"] = "cusps_not_one_prograde_short_arc_partition"
        return empty
    lon = angle_fraction(longitude) % 360
    index = next(i for i, v in enumerate(values) if (lon - v) % 360 < spans[i])
    if native_occupied_house is not None and index + 1 != native_occupied_house:
        empty["unavailable_reason"] = (
            "native_occupancy_disagrees_with_zodiacal_cusp_partition"
        )
        return empty
    return assign_cusp_virtue(
        lon,
        index + 1,
        values[index],
        values[(index + 1) % 12],
        house_system=house_system,
        zodiac_type=zodiac_type,
    )
