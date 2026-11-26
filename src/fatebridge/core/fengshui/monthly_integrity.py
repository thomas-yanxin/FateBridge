"""Check literal month centers and raw calendar/plate coherence without builders."""

from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter
from typing_extensions import TypedDict

from fatebridge.core.fengshui.calendar import resolution_point
from fatebridge.core.fengshui.models import MonthlyRequest
from fatebridge.utils.civil_time import ZonedCalendar, utc_calendar
from fatebridge.utils.errors import FengshuiCalculationError
from fatebridge.utils.timezones import is_unspecified_local_time, parse_timezone_name

JIE = tuple("立春 惊蛰 清明 立夏 芒种 小暑 立秋 白露 寒露 立冬 大雪 小寒".split())
BRANCHES = "寅卯辰巳午未申酉戌亥子丑"
FIXED = {"C": 5, "N": 1, "NE": 8, "E": 3, "SE": 4, "S": 9, "SW": 2, "W": 7, "NW": 6}


def _check(condition: bool) -> None:
    if not condition:
        raise FengshuiCalculationError("monthly_plate_inconsistent")


class PrintedCenterColumn(TypedDict):
    branches: list[str]
    centers: list[int]


class MonthlyIntegrityReference(TypedDict):
    printed_center_columns: list[PrintedCenterColumn]
    palace_offsets: dict[str, int]
    star_identities: dict[str, dict[str, str]]


@lru_cache(maxsize=1)
def _reference() -> MonthlyIntegrityReference:
    try:
        raw = (
            Path(__file__).parents[2] / "data/fengshui/monthly-integrity-v1.json"
        ).read_bytes()
        return TypeAdapter(MonthlyIntegrityReference).validate_json(raw, strict=True)
    except (OSError, ValueError) as error:
        raise FengshuiCalculationError("monthly_plate_inconsistent") from error


def _integer(value: object, low: int, high: int) -> int:
    if type(value) is int and low <= value <= high:
        return value
    else:
        raise FengshuiCalculationError("monthly_plate_inconsistent")


def _window(
    time: dict[str, Any],
    year: int,
    month: int,
    *,
    query: Fraction | None,
    provisional: bool = False,
) -> None:
    span = time["provisional_interval"] if provisional else time
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    points = []
    for side, y, m, moment in (
        ("start", year, month, span["valid_from"]),
        ("end", next_year, next_month, span["valid_until"]),
    ):
        source = time["timing"][side + "_resolution"]
        _check(source["term_name"] == JIE[m - 1])
        _check(
            type(source["civil_year"]) is int
            and source["civil_year"] == y + int(m == 12)
        )
        _check(source["moment"] == moment)
        calendar = ZonedCalendar.from_isoformat(moment).utc
        point = resolution_point(source.get("civil_point"), moment)
        _check(point.as_calendar() == calendar)
        points.append(point.day)
    start, end = points
    _check(start < end)
    if query is not None:
        _check(start <= query < end)


def validate_monthly_layer(
    layer: dict[str, Any], request: MonthlyRequest | None = None
) -> dict[str, int]:
    """No re-solving clocks, rebuilding stars or rendering text as an oracle.

    Calendar roots need a separate astronomical reference. This checks the
    returned month against its own clock, literal source numbers and planes.
    Old partial receipts do not acquire newer candidate-window requirements.
    """
    try:
        data = _reference()
        time = layer["time_context"]
        label = time.get("local_moment")
        undefined_clock = time.get("local_clock_status") == "undefined"
        if undefined_clock:
            _check(time["local_moment"] is None)
            label = time["utc_moment"]
            _check(label.endswith("Z"))
        query = (
            ZonedCalendar.from_isoformat(label).utc.julian_day_exact()
            if label is not None
            else None
        )
        _check(time.get("input_basis") != "aware_datetime" or query is not None)
        _check(time["year_boundary"] == "lichun")
        _check(
            time["month_boundary"]
            == "twelve_jie_instants_not_zhongqi_lunar_or_gregorian_months"
        )
        if request is not None:
            _check(time["timezone_name"] == request.timezone_name)
            if request.query_at is not None:
                local = request.query_at.astimezone(
                    parse_timezone_name(request.timezone_name)
                )
                _check(undefined_clock == is_unspecified_local_time(local))
                if undefined_clock:
                    _check(query == utc_calendar(request.query_at).julian_day_exact())
                else:
                    _check(time["local_moment"] == local.isoformat())
                _check(time["input_basis"] == "aware_datetime")
            elif request.effective_solar_year is not None:
                _check(time["input_basis"] == "confirmed_solar_month")
                _check(time["effective_solar_year"] == request.effective_solar_year)
                _check(time["solar_month_number"] == request.solar_month_number)
                _check(time["local_moment"] is None and query is None)
            else:
                _check(time["input_basis"] == "missing")
        if layer["status"] == "partial":
            _check(not layer["palaces"] and bool(layer["missing_inputs"]))
            _check(
                all(
                    key not in layer
                    for key in ("center_star_number", "year_branch", "year_group")
                )
            )
            _check(time["solar_month_number"] is None)
            if (
                request is not None
                and time.get("month_status") == "requires_confirmation"
            ):
                _check(time["valid_from"] is None and time["valid_until"] is None)
                candidates = time["candidate_months"]
                _check(len(candidates) == 2)
                identities = [
                    (c["effective_solar_year"], c["solar_month_number"])
                    for c in candidates
                ]
                first, second = identities
                _check(
                    second
                    == (
                        (first[0] + 1, 1)
                        if first[1] == 12
                        else (first[0], first[1] + 1)
                    )
                )
                provisional = time["provisional_interval"]
                selected = (
                    provisional["effective_solar_year"],
                    provisional["solar_month_number"],
                )
                _check(selected in identities)
                _window(time, *selected, query=query, provisional=True)
            return {"numeric_palaces": 0}
        _check(layer["status"] == "complete" and not layer["missing_inputs"])
        year = _integer(time["effective_solar_year"], 1, 9998)
        month = _integer(time["solar_month_number"], 1, 12)
        _check(time["month_branch"] == BRANCHES[month - 1])
        branch = "子丑寅卯辰巳午未申酉戌亥"[(year - 4) % 12]
        _check(layer["year_branch"] == branch)
        source = next(
            g for g in data["printed_center_columns"] if branch in g["branches"]
        )
        group = layer["year_group"]
        _check(group["branches"] == source["branches"])
        _check(
            type(group["first_month_center"]) is int
            and group["first_month_center"] == source["centers"][0]
        )
        center = _integer(layer["center_star_number"], 1, 9)
        _check(center == source["centers"][month - 1])
        _window(time, year, month, query=query)
        _check(set(layer["palaces"]) == set(FIXED))
        offsets = data["palace_offsets"]
        _check(layer["flight_path"] == sorted(offsets, key=offsets.__getitem__))
        for direction, palace in layer["palaces"].items():
            number = _integer(palace["monthly_star_number"], 1, 9)
            _check(number == (center + offsets[direction] - 1) % 9 + 1)
            _check(
                type(palace["palace_number"]) is int
                and palace["palace_number"] == FIXED[direction]
            )
            _check(palace["monthly_star"] == data["star_identities"][str(number)])
            _check(palace["method"] == "monthly_stars")
            _check(
                palace["rule_id"] == "monthly_zibai_jie_v1.reverse_month_forward_palace"
            )
            _check(palace["source_ids"] == ["MP1", "MP2"])
        return {"numeric_palaces": 9}
    except (
        KeyError,
        TypeError,
        ValueError,
        AttributeError,
        IndexError,
        StopIteration,
        ZeroDivisionError,
    ) as error:
        raise FengshuiCalculationError("monthly_plate_inconsistent") from error
