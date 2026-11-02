"""Check literal month centers and raw calendar/plate coherence without builders."""

import hashlib
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from fatebridge.utils.errors import FengshuiCalculationError
from fatebridge.utils.timezones import parse_timezone_name

from .models import MonthlyRequest

DATA_SHA256 = "570c0f0fbc5c7f1140ddb4f82510c56bbc922950153eeab9cff812992e5a9cb8"
JIE = tuple("立春 惊蛰 清明 立夏 芒种 小暑 立秋 白露 寒露 立冬 大雪 小寒".split())
BRANCHES = "寅卯辰巳午未申酉戌亥子丑"
FIXED = {"C": 5, "N": 1, "NE": 8, "E": 3, "SE": 4, "S": 9, "SW": 2, "W": 7, "NW": 6}


def _check(condition: bool) -> None:
    if not condition:
        raise FengshuiCalculationError("monthly_plate_inconsistent")


@lru_cache(maxsize=1)
def _reference() -> dict[str, Any]:
    try:
        raw = (
            Path(__file__).parents[2] / "data/fengshui/monthly-integrity-v1.json"
        ).read_bytes()
        _check(hashlib.sha256(raw).hexdigest() == DATA_SHA256)
        return cast(dict[str, Any], json.loads(raw))
    except (OSError, ValueError, TypeError) as error:
        raise FengshuiCalculationError("monthly_plate_inconsistent") from error


def _integer(value: Any, low: int, high: int) -> int:
    _check(type(value) is int and low <= value <= high)
    return cast(int, value)


def _instant(value: Any) -> datetime:
    _check(type(value) is str)
    result = datetime.fromisoformat(value)
    _check(result.utcoffset() is not None)
    return result.astimezone(timezone.utc)


def _window(time: dict[str, Any], year: int, month: int) -> None:
    start, end = _instant(time["valid_from"]), _instant(time["valid_until"])
    _check(start < end)
    if time.get("local_moment") is not None:
        _check(start <= _instant(time["local_moment"]) < end)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    for side, y, m, moment in (
        ("start", year, month, time["valid_from"]),
        ("end", next_year, next_month, time["valid_until"]),
    ):
        source = time["timing"][side + "_resolution"]
        _check(source["term_name"] == JIE[m - 1])
        _check(
            type(source["civil_year"]) is int
            and source["civil_year"] == y + int(m == 12)
        )
        _check(source["moment"] == moment)


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
                _check(time["local_moment"] == local.isoformat())
                _check(time["input_basis"] == "aware_datetime")
            elif request.effective_solar_year is not None:
                _check(time["input_basis"] == "confirmed_solar_month")
                _check(time["effective_solar_year"] == request.effective_solar_year)
                _check(time["solar_month_number"] == request.solar_month_number)
                _check(time["local_moment"] is None)
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
                _check(
                    (
                        provisional["effective_solar_year"],
                        provisional["solar_month_number"],
                    )
                    in identities
                )
                # The provisional window belongs to the same reported model.
                _check(
                    _instant(provisional["valid_from"])
                    <= _instant(time["local_moment"])
                    < _instant(provisional["valid_until"])
                )
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
        _window(time, year, month)
        _check(set(layer["palaces"]) == set(FIXED))
        offsets = data["palace_offsets"]
        _check(layer["flight_path"] == sorted(offsets, key=offsets.get))
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
    ) as error:
        raise FengshuiCalculationError("monthly_plate_inconsistent") from error
