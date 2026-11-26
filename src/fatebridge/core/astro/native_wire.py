"""Preserve finite results, exact clock points and typed arguments across native IPC."""

from __future__ import annotations

import math
from dataclasses import fields
from datetime import datetime
from fractions import Fraction
from typing import Any, TypeGuard

from pydantic import JsonValue

from fatebridge.core.astro.birth import AstroBirthInfo, NativeSolarBirthInfo
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.time_scales import EphemerisTime
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant
from fatebridge.utils.civil_time import (
    CivilPoint,
)
from fatebridge.utils.civil_time import (
    datetime_fromisoformat_preserving_offset as parse_iso_datetime,
)
from fatebridge.utils.timezones import parse_timezone_name


class NativeExecutionError(RuntimeError):
    """Bounded, non-input-bearing failure of the private calculation process."""


RESULT_ENCODING = "native_result_v1"


def _json_tree(value: object) -> TypeGuard[JsonValue]:
    """Identify exact finite JSON types while retaining typed values separately."""
    if value is None or type(value) in (str, bool, int):
        return True
    elif type(value) is float:
        return math.isfinite(value)
    elif type(value) is list:
        return all(_json_tree(element) for element in value)
    elif type(value) is dict:
        return all(
            type(field_name) is str and _json_tree(field_value)
            for field_name, field_value in value.items()
        )
    else:
        return False


def encode_result(value: object) -> list[JsonValue]:
    """Envelope plain JSON results and preserve the types of other values."""
    if _json_tree(value):
        return [RESULT_ENCODING, "json", value]
    else:
        return [RESULT_ENCODING, "typed", encode(value)]


def decode_result(value: object) -> Any:
    if not isinstance(value, list) or len(value) != 3 or value[0] != RESULT_ENCODING:
        raise NativeExecutionError("Invalid native result envelope")
    if value[1] == "json":
        if not _json_tree(value[2]):
            raise NativeExecutionError("Invalid native JSON tree")
        return value[2]
    if value[1] == "typed":
        return decode(value[2])
    raise NativeExecutionError("Invalid native result representation")


def encode(value: object) -> JsonValue:
    """Typed JSON only; maps cannot impersonate protocol type envelopes."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Native calculation values must be finite")
        return value
    if isinstance(value, datetime):
        zone = getattr(value.tzinfo, "key", None) or getattr(value.tzinfo, "zone", None)
        return ["datetime", value.isoformat(), zone, value.fold]
    if isinstance(value, TTInstant):
        return ["tt_instant", value.days.numerator, value.days.denominator]
    if isinstance(value, UT1Instant):
        return ["ut1_instant", value.days.numerator, value.days.denominator]
    if isinstance(value, AstroBirthInfo):
        return [
            (
                "native_solar_birth"
                if isinstance(value, NativeSolarBirthInfo)
                else "birth"
            ),
            encode({f.name: getattr(value, f.name) for f in fields(value)}),
        ]
    if isinstance(value, PhysicalEpoch):
        epoch = [
            "physical_epoch",
            encode({f.name: getattr(value.time, f.name) for f in fields(value.time)}),
            value.utc_label,
            encode(value.utc_datetime),
            value.utc_is_leap_second,
        ]
        source = value.source_calendar
        if source is not None:
            encoded_calendar: list[JsonValue] = [
                source.day.numerator,
                source.day.denominator,
            ]
            excluded_before = source.excluded_before
            if excluded_before is not None:
                encoded_calendar.extend(
                    [excluded_before.numerator, excluded_before.denominator]
                )
            epoch.append(encoded_calendar)
        return epoch
    if isinstance(value, dict):
        return ["map", [[encode(k), encode(v)] for k, v in value.items()]]
    if isinstance(value, (tuple, list)):
        return [
            "tuple" if isinstance(value, tuple) else "list",
            [encode(v) for v in value],
        ]
    raise TypeError("Unsupported native calculation argument type")


def decode(value: Any) -> Any:
    if not isinstance(value, list):
        if value is None or isinstance(value, (str, bool, int)):
            return value
        if isinstance(value, float) and math.isfinite(value):
            return value
        raise NativeExecutionError("Invalid native calculation value")
    if not value:
        raise NativeExecutionError("Invalid native calculation envelope")
    tag = value[0]
    if not isinstance(tag, str):
        raise NativeExecutionError("Invalid native calculation envelope")
    if tag == "tt_instant" and len(value) == 3:
        if type(value[1]) is not int or type(value[2]) is not int or value[2] <= 0:
            raise NativeExecutionError("Invalid exact TT point")
        return TTInstant(Fraction(value[1], value[2]))
    if tag == "ut1_instant" and len(value) == 3:
        if type(value[1]) is not int or type(value[2]) is not int or value[2] <= 0:
            raise NativeExecutionError("Invalid exact UT1 point")
        return UT1Instant(Fraction(value[1], value[2]))
    if tag == "datetime" and len(value) == 4:
        moment = parse_iso_datetime(value[1])
        if value[2] is not None:
            # Use the package's pinned TZif, as birth normalization does. The
            # host ZoneInfo database can contain different historical rules.
            named = moment.replace(tzinfo=parse_timezone_name(value[2]), fold=value[3])
            if named.utcoffset() != moment.utcoffset():
                raise NativeExecutionError("Native datetime zone offset changed")
            moment = named
        return moment.replace(fold=value[3])
    if tag in {"birth", "native_solar_birth"} and len(value) == 2:
        birth_type = (
            NativeSolarBirthInfo if tag == "native_solar_birth" else AstroBirthInfo
        )
        return birth_type(**decode(value[1]))
    if tag == "physical_epoch" and len(value) in (5, 6):
        source = None
        if len(value) == 6:
            point = value[5]
            if (
                not isinstance(point, list)
                or len(point) not in (2, 4)
                or any(type(limb) is not int for limb in point)
                or any(denominator <= 0 for denominator in point[1::2])
            ):
                raise NativeExecutionError("Invalid exact source calendar")
            source = CivilPoint(
                Fraction(*point[:2]), Fraction(*point[2:]) if len(point) == 4 else None
            )
        return PhysicalEpoch(
            EphemerisTime(**decode(value[1])),
            value[2],
            decode(value[3]),
            value[4],
            source_calendar=source,
        )
    if tag == "map" and len(value) == 2:
        return {decode(k): decode(v) for k, v in value[1]}
    if tag in {"list", "tuple"} and len(value) == 2:
        items = [decode(v) for v in value[1]]
        return tuple(items) if tag == "tuple" else items
    raise NativeExecutionError("Invalid native calculation envelope")
