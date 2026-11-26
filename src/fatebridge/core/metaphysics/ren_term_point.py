"""Numerical integrity of a consumed TT root, separate from orbit accuracy."""

from __future__ import annotations

import math
from datetime import datetime

from fatebridge.core.astro.time_scales import utc_calendar_from_tt
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.utils.civil_time import ZonedCalendar, utc_calendar

SCALAR = "explicit_ieee_float_tt_point"
PARTS = "explicit_two_part_tt"
REQUIRED = {
    "selected_crossing_jd_tt",
    "root_bracket_tt",
    "root_bracket_seconds",
    "root_time_scale",
    "numerical_epoch_representation",
    "scalar_jd_scope",
    "numerical_resolution_is_physical_accuracy",
}


def _bad() -> ValueError:
    return ValueError("六壬金口诀交气数值回执与所用TT点或民用瞬间不一致")


def _finite_number(number: object) -> float:
    if type(number) is not int and type(number) is not float:
        raise _bad()
    try:
        if not math.isfinite(number):
            raise _bad()
        return float(number)
    except OverflowError as error:
        raise _bad() from error


def _numerical_pair(pair: object) -> tuple[float, float]:
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        raise _bad()
    return _finite_number(pair[0]), _finite_number(pair[1])


def _tt_instant_from_parts(parts: object) -> TTInstant:
    day, fraction = _numerical_pair(parts)
    return TTInstant.from_parts(day, fraction)


def validate_term_point(
    details: object,
    moment: datetime | ZonedCalendar | None,
    *,
    complete: bool,
) -> None:
    """Check exact TT inputs and the civil label under the loaded clock policy.

    Runtime consumers require a complete receipt. Projections check present evidence.
    """
    if details is None and not complete:
        return
    if not isinstance(details, dict) or (complete and not REQUIRED <= details.keys()):
        raise _bad()
    representation = details.get("numerical_epoch_representation")
    if "numerical_epoch_representation" in details and representation not in (
        SCALAR,
        PARTS,
    ):
        raise _bad()
    if "root_time_scale" in details and details["root_time_scale"] != "TT":
        raise _bad()
    if (
        "numerical_resolution_is_physical_accuracy" in details
        and details["numerical_resolution_is_physical_accuracy"] is not False
    ):
        raise _bad()
    scope = (
        {
            SCALAR: "exact_value_of_selected_ieee_float",
            PARTS: "rounded_display_of_selected_tt_parts",
        }.get(representation)
        if isinstance(representation, str)
        else None
    )
    if scope and "scalar_jd_scope" in details and details["scalar_jd_scope"] != scope:
        raise _bad()

    scalar = (
        _finite_number(details["selected_crossing_jd_tt"])
        if "selected_crossing_jd_tt" in details
        else None
    )
    display_bracket = None
    if "root_bracket_tt" in details:
        display_bracket = _numerical_pair(details["root_bracket_tt"])
        if display_bracket[0] > display_bracket[1]:
            raise _bad()
    point = None
    bracket = None
    if representation == SCALAR:
        if (
            "selected_crossing_tt_parts" in details
            or "root_bracket_tt_parts" in details
        ):
            raise _bad()
        if scalar is not None:
            point = TTInstant.from_float(scalar)
        if display_bracket is not None:
            bracket = tuple(TTInstant.from_float(x) for x in display_bracket)
    elif representation == PARTS:
        if (
            complete
            and not {"selected_crossing_tt_parts", "root_bracket_tt_parts"}
            <= details.keys()
        ):
            raise _bad()
        if "selected_crossing_tt_parts" in details:
            point = _tt_instant_from_parts(details["selected_crossing_tt_parts"])
            if scalar is not None and scalar != point.as_float():
                raise _bad()
        if "root_bracket_tt_parts" in details:
            bracket_parts = details["root_bracket_tt_parts"]
            if not isinstance(bracket_parts, (list, tuple)) or len(bracket_parts) != 2:
                raise _bad()
            bracket = (
                _tt_instant_from_parts(bracket_parts[0]),
                _tt_instant_from_parts(bracket_parts[1]),
            )
            if display_bracket is not None and display_bracket != tuple(
                x.as_float() for x in bracket
            ):
                raise _bad()

    width = None
    if "root_bracket_seconds" in details:
        width = _finite_number(details["root_bracket_seconds"])
        if width < 0:
            raise _bad()
    if bracket is not None:
        low, high = bracket
        if low.days > high.days or (
            point is not None and not low.days <= point.days <= high.days
        ):
            raise _bad()
        # Compare the width of the exact input doubles, never rounded large-JD
        # display sums. This is a numerical identity, not an accuracy tolerance.
        if width is not None and width != float((high.days - low.days) * 86400):
            raise _bad()
    if complete and (point is None or bracket is None or moment is None):
        raise _bad()
    if point is not None and moment is not None:
        if isinstance(moment, datetime) and moment.utcoffset() is None:
            raise _bad()
        actual = (
            moment.utc if isinstance(moment, ZonedCalendar) else utc_calendar(moment)
        )
        # Preserve the original rounded-microsecond label identity; this is
        # not a comparison against the unrounded retained TT inverse point.
        expected = utc_calendar_from_tt(point)
        if actual != expected:
            raise _bad()
