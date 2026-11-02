"""Numerical integrity of a consumed TT root, separate from orbit accuracy."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from ..astro.time_scales import datetime_from_tt_point
from ..astro.tt_epoch import TTInstant

_SCALAR = "explicit_ieee_float_tt_point"
_PARTS = "explicit_two_part_tt"
_REQUIRED = {
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


def _number(value: Any) -> float:
    if type(value) not in (int, float):
        raise _bad()
    try:
        if not math.isfinite(value):
            raise _bad()
        return float(value)
    except OverflowError as exc:
        raise _bad() from exc


def _pair(value: Any) -> tuple[Any, Any]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise _bad()
    return value[0], value[1]


def _parts(value: Any) -> TTInstant:
    day, fraction = _pair(value)
    return TTInstant.from_parts(_number(day), _number(fraction))


def validate_term_point(
    details: Any,
    moment: datetime | None,
    *,
    complete: bool,
) -> None:
    """Check exact supplied doubles and their civil label under loaded policy.

    Runtime consumers require the whole numerical receipt. Projected/legacy
    output checks compare only present evidence; absence is not verification.
    Neither path checks the Sun's longitude or certifies physical accuracy.
    """
    if details is None and not complete:
        return
    if not isinstance(details, dict) or (complete and not _REQUIRED <= details.keys()):
        raise _bad()
    representation = details.get("numerical_epoch_representation")
    if "numerical_epoch_representation" in details and representation not in (
        _SCALAR,
        _PARTS,
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
            _SCALAR: "exact_value_of_selected_ieee_float",
            _PARTS: "rounded_display_of_selected_tt_parts",
        }.get(representation)
        if isinstance(representation, str)
        else None
    )
    if scope and "scalar_jd_scope" in details and details["scalar_jd_scope"] != scope:
        raise _bad()

    scalar = (
        _number(details["selected_crossing_jd_tt"])
        if "selected_crossing_jd_tt" in details
        else None
    )
    display_bracket = None
    if "root_bracket_tt" in details:
        display_bracket = tuple(_number(x) for x in _pair(details["root_bracket_tt"]))
        if display_bracket[0] > display_bracket[1]:
            raise _bad()
    point = None
    bracket = None
    if representation == _SCALAR:
        if (
            "selected_crossing_tt_parts" in details
            or "root_bracket_tt_parts" in details
        ):
            raise _bad()
        if scalar is not None:
            point = TTInstant.from_float(scalar)
        if display_bracket is not None:
            bracket = tuple(TTInstant.from_float(x) for x in display_bracket)
    elif representation == _PARTS:
        if (
            complete
            and not {"selected_crossing_tt_parts", "root_bracket_tt_parts"}
            <= details.keys()
        ):
            raise _bad()
        if "selected_crossing_tt_parts" in details:
            point = _parts(details["selected_crossing_tt_parts"])
            if scalar is not None and scalar != point.as_float():
                raise _bad()
        if "root_bracket_tt_parts" in details:
            bracket = tuple(_parts(x) for x in _pair(details["root_bracket_tt_parts"]))
            if display_bracket is not None and display_bracket != tuple(
                x.as_float() for x in bracket
            ):
                raise _bad()

    width = None
    if "root_bracket_seconds" in details:
        width = _number(details["root_bracket_seconds"])
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
        if moment.utcoffset() is None:
            raise _bad()
        expected = datetime_from_tt_point(point)
        if moment.astimezone(timezone.utc) != expected.astimezone(timezone.utc):
            raise _bad()
