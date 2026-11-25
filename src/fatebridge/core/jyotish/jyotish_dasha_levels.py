"""Calculate Vimshottari periods on one exact Gregorian UTC birth epoch."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from fractions import Fraction
from typing import Any, TypedDict

from fatebridge.core.astro.reference import NAKSHATRAS
from fatebridge.core.jyotish.jyotish_vargas import longitude_ratio
from fatebridge.utils.civil_time import UTCCalendar, utc_calendar

ORDER = ("Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury")
YEARS = dict(zip(ORDER, (7, 20, 6, 10, 7, 18, 16, 19, 17)))
YEAR_MICROSECONDS = {
    "sidereal_365_25636": 31558149504000,
    "tropical_365_2425": 31556952000000,
    "savana_360": 31104000000000,
}
YEAR_DAYS = {
    "sidereal_365_25636": 365.25636,
    "tropical_365_2425": 365.2425,
    "savana_360": 360.0,
}
LEVELS = (
    ("mahadasha", "MD"),
    ("antardasha", "AD"),
    ("pratyantardasha", "PD"),
    ("sookshma", "SD"),
    ("prana", "PAD"),
    ("deha", "DAD"),
)
RULE = "jyotish.vimshottari_recursive_rao2000.v1"
QUANTIZATION_RULE = "jyotish.vimshottari_birth_epoch_quantization.v1"
QUANTIZATION_METHOD = "fatebridge_birth_epoch_rational_microseconds_v1"
QUANTIZATION_SOURCE = {
    "id": "fatebridge_vimshottari_quantization_v1",
    "title": "FateBridge common-birth-epoch rational boundary quantization",
    "source_kind": "implementation_policy",
    "version": "1",
    "scope": "Keep exact ratios of the supplied binary longitude and all period weights until each final edge; nearest microsecond ties-to-even on one nominal UTC birth epoch. This numerical convention is not an author's textual microsecond rule, measured birth-clock accuracy, SI leap-second elapsed time or empirical prediction evidence.",
}
SOURCE = {
    "id": "pvr_2000_recursive_dasha_1cafa828",
    "title": "P.V.R. Narasimha Rao, Vedic Astrology: An Integrated Approach (2000; 2010 update)",
    "url": "https://www.vedicastrologer.org/articles/vedic_astro_textbook.pdf",
    "sha256": "1cafa828f34764ed5e85816882df2e8f0bc014c5c57ccdb27169416e117fd4db",
    "sections": ["16.1 names; 16.2 Table38; 16.3 printed212/PDF223"],
    "scope": "Same cyclic lord order and year weights recursively divide complete parent periods. UTC nominal-day year conventions and microsecond rounding are implementation choices, not original-text precision or empirical timing accuracy.",
}


def active_levels(
    major_lord: str,
    major_start: datetime | UTCCalendar,
    analysis: datetime,
    *,
    year_basis: str,
    depth: int,
    _reference_epoch: datetime | UTCCalendar | None = None,
    _major_start_offset_us: Fraction | None = None,
) -> dict[str, Any]:
    """Return the active ancestry and nine siblings at each requested level.

    Fractions retain the complete MD origin. A displayed boundary is rounded
    once, with ties to even, never recursively derived from a rounded duration.
    All selections use those same half-open microsecond boundaries.
    """
    if type(depth) is not int or not 2 <= depth <= len(LEVELS):
        raise ValueError("Vimshottari depth must be an integer2..6")
    else:
        pass
    if major_lord not in YEARS or year_basis not in YEAR_MICROSECONDS:
        raise ValueError("Unknown Vimshottari lord or year basis")
    else:
        pass
    if analysis.utcoffset() is None or (
        isinstance(major_start, datetime) and major_start.utcoffset() is None
    ):
        raise ValueError("Vimshottari period and target clocks must carry a timezone")
    else:
        pass
    if (_reference_epoch is None) != (_major_start_offset_us is None):
        raise ValueError("A common epoch requires its exact major-period offset")
    else:
        pass
    if isinstance(_reference_epoch, datetime) and _reference_epoch.utcoffset() is None:
        raise ValueError("The common period epoch must carry a timezone")
    else:
        pass
    if _major_start_offset_us is not None and not isinstance(
        _major_start_offset_us, Fraction
    ):
        raise ValueError("The major-period offset must retain its exact fraction")
    else:
        pass
    global_epoch = _reference_epoch is not None
    supplied_start = (
        utc_calendar(major_start) if isinstance(major_start, datetime) else major_start
    )
    epoch_input = supplied_start if _reference_epoch is None else _reference_epoch
    epoch = (
        utc_calendar(epoch_input) if isinstance(epoch_input, datetime) else epoch_input
    )
    offset = Fraction(0) if _major_start_offset_us is None else _major_start_offset_us
    target = utc_calendar(analysis)
    unit = YEAR_MICROSECONDS[year_basis]
    duration = Fraction(YEARS[major_lord] * unit)

    def boundary(offset: Fraction) -> UTCCalendar:
        edge = epoch.shifted(timedelta(microseconds=round(offset)))
        if isinstance(major_start, datetime) and edge.as_datetime() is None:
            raise ValueError("Vimshottari boundaries exceed the datetime range")
        else:
            pass
        return edge

    if boundary(offset) != supplied_start:
        raise ValueError("The displayed major start contradicts its exact epoch offset")
    else:
        pass
    if not boundary(offset) <= target < boundary(offset + duration):
        raise ValueError("Target must lie within the complete supplied major period")
    else:
        pass

    def record(chain: list[str], start: Fraction, end: Fraction) -> dict[str, Any]:
        level = len(chain)
        ratio = (end - start) / unit
        return {
            "level": level,
            "name": LEVELS[level - 1][0],
            "abbreviation": LEVELS[level - 1][1],
            "lord": chain[-1],
            "lord_chain": chain,
            "start": boundary(start).isoformat(),
            "end": boundary(end).isoformat(),
            "duration_years": float(ratio),
            "duration_years_fraction": [ratio.numerator, ratio.denominator],
        }

    chain = [major_lord]
    current = [record(chain, offset, offset + duration)]
    siblings = []
    for level in range(2, depth + 1):
        index = ORDER.index(chain[-1])
        total = 0
        rows = []
        selected = None
        for step in range(len(ORDER)):
            lord = ORDER[(index + step) % len(ORDER)]
            start = offset + duration * total / 120
            total += YEARS[lord]
            end = offset + duration * total / 120
            row = record([*chain, lord], start, end)
            rows.append(row)
            if boundary(start) <= target < boundary(end):
                selected = (row, start, end)
            else:
                pass
        if selected is None:
            raise ValueError("Target falls outside its complete parent period")
        else:
            pass
        siblings.append(
            {"level": level, "parent_lord_chain": list(chain), "periods": rows}
        )
        row, start, end = selected
        current.append(row)
        chain = row["lord_chain"]
        offset, duration = start, end - start
    result: dict[str, Any] = {
        "method_id": (
            "rao2000_recursive_vimshottari_global_epoch_v2"
            if global_epoch
            else "rao2000_recursive_vimshottari_exact_fractions_v1"
        ),
        "depth": depth,
        "source_id": SOURCE["id"],
        "rule_ids": [RULE, *([QUANTIZATION_RULE] if global_epoch else [])],
        "current_levels": current,
        "siblings_by_level": siblings,
        "year_basis": year_basis,
        "rounding_policy": (
            "Exact rational offsets from the common birth epoch through every requested level; each final edge rounded once to nearest microsecond with ties-to-even; start inclusive/end exclusive"
            if global_epoch
            else "Exact rational offsets from complete MD origin; each edge rounded once to nearest microsecond with ties-to-even; start inclusive/end exclusive"
        ),
        "scope": "Active ancestry and nine siblings per requested lower level, not a complete nested120-year tree. The birth remainder is never repartitioned. Finer period labels are not observed event timing, confidence intervals, birth-record precision or prediction probabilities.",
    }
    if global_epoch and _major_start_offset_us is not None:
        result["epoch_context"] = {
            "reference_epoch_utc": epoch.isoformat(),
            "complete_major_start_offset_microseconds_fraction": {
                "numerator": str(_major_start_offset_us.numerator),
                "denominator": str(_major_start_offset_us.denominator),
            },
            "quantization_method_id": QUANTIZATION_METHOD,
            "source_id": QUANTIZATION_SOURCE["id"],
        }
    else:
        pass
    return result


class NakshatraPlacement(TypedDict):
    index: int
    name: str
    lord: str
    pada: int
    fraction_elapsed: float


def nakshatra(longitude: float | Fraction) -> NakshatraPlacement:
    numerator, denominator = longitude_ratio(longitude)
    index, remainder = divmod(numerator * 3, denominator * 40)
    fraction = min(remainder / (denominator * 40), math.nextafter(1.0, 0.0))
    return {
        "index": index + 1,
        "name": NAKSHATRAS[index],
        "lord": ORDER[index % 9],
        "pada": remainder * 4 // (denominator * 40) + 1,
        "fraction_elapsed": fraction,
    }


def vimshottari(
    birth_utc: datetime | UTCCalendar,
    moon_longitude: float,
    analysis: datetime,
    *,
    year_basis: str = "sidereal_365_25636",
    dasha_depth: int = 2,
) -> dict[str, Any]:
    if type(dasha_depth) is not int or not 2 <= dasha_depth <= 6:
        raise ValueError("Vimshottari 层数须为2至6的整数。")
    else:
        pass
    if year_basis not in YEAR_DAYS:
        raise ValueError("不支持的 Vimshottari 年长口径。")
    else:
        pass
    if analysis.utcoffset() is None or (
        isinstance(birth_utc, datetime) and birth_utc.utcoffset() is None
    ):
        raise ValueError("达沙的出生与分析时刻必须带时区。")
    else:
        pass
    origin = utc_calendar(birth_utc) if isinstance(birth_utc, datetime) else birth_utc
    target = utc_calendar(analysis)
    if target < origin:
        raise ValueError("分析时刻不能早于出生时刻。")
    else:
        pass
    seed = nakshatra(moon_longitude)
    first = ORDER.index(seed["lord"])
    year_microseconds = YEAR_MICROSECONDS[year_basis]
    numerator, denominator = longitude_ratio(moon_longitude)
    _, remainder = divmod(numerator * 3, denominator * 40)
    elapsed_fraction = Fraction(remainder, denominator * 40)
    first_years = YEARS[seed["lord"]]
    elapsed_years_exact = elapsed_fraction * first_years
    first_offset = -elapsed_years_exact * year_microseconds

    def edge(offset: Fraction) -> UTCCalendar:
        return origin.shifted(timedelta(microseconds=round(offset)))

    start = edge(first_offset)
    cycle_duration = timedelta(microseconds=120 * year_microseconds)
    cycle_index = target.elapsed_since(start) // cycle_duration
    active_start = start.shifted(cycle_index * cycle_duration)
    active_offset = first_offset + cycle_index * 120 * year_microseconds
    extended_calendar = (
        start.as_datetime() is None
        or active_start.shifted(cycle_duration).as_datetime() is None
    )
    timeline = []
    cumulative = 0
    current_major = current_sub = None
    current_major_offset = None
    # Derive each boundary from a shared origin; do not compound rounded dates.
    for step in range(9):
        lord = ORDER[(first + step) % 9]
        years = YEARS[lord]
        major_offset = active_offset + cumulative * year_microseconds
        major_start = edge(major_offset)
        major_end = edge(major_offset + years * year_microseconds)
        major: dict[str, Any] = {
            "lord": lord,
            "start": major_start.isoformat(),
            "end": major_end.isoformat(),
            "duration_years": years,
        }
        subs = []
        sub_total = 0
        for substep in range(9):
            sublord = ORDER[(first + step + substep) % 9]
            sub_start = edge(
                major_offset + Fraction(years * sub_total * year_microseconds, 120)
            )
            sub_total += YEARS[sublord]
            sub_end = (
                major_end
                if substep == 8
                else edge(
                    major_offset + Fraction(years * sub_total * year_microseconds, 120)
                )
            )
            sub = {
                "lord": sublord,
                "major_lord": lord,
                "start": sub_start.isoformat(),
                "end": sub_end.isoformat(),
                "duration_years": years * YEARS[sublord] / 120.0,
            }
            subs.append(sub)
            if sub_start <= target < sub_end:
                current_sub = dict(sub)
            else:
                pass
        if major_start <= target < major_end:
            current_major = dict(major)
            current_major_offset = major_offset
        else:
            pass
        timeline.append({**major, "antardashas": subs})
        cumulative += years
    if current_major is None or current_sub is None or current_major_offset is None:
        raise ValueError("达沙日期边界超出可计算范围。")
    else:
        pass
    birth_end = edge(first_offset + first_years * year_microseconds)
    elapsed_microseconds = round(elapsed_years_exact * year_microseconds)
    result: dict[str, Any] = {
        "method_id": "moon_nakshatra_vimshottari_v1",
        "year_basis": year_basis,
        "year_days": YEAR_DAYS[year_basis],
        "analysis_datetime": analysis.isoformat(),
        "boundary_convention": "start_inclusive_end_exclusive_UTC_elapsed",
        "elapsed_time_convention": (
            "Extended Gregorian UTC calendar labels: nominal 86400-second days, "
            "leap-second labels unrepresented; not a claim of continuous atomic SI elapsed time"
            if extended_calendar
            else "UTC calendar labels with Python datetime/timedelta: nominal 86400-second days, leap-second labels unrepresented; not a claim of continuous atomic SI elapsed time"
        ),
        "seed": {**seed, "moon_longitude": moon_longitude},
        "birth_balance": {
            "lord": seed["lord"],
            "elapsed_years": float(elapsed_years_exact),
            "remaining_years": float((1 - elapsed_fraction) * first_years),
            "elapsed_microseconds": elapsed_microseconds,
            "remaining_microseconds": first_years * year_microseconds
            - elapsed_microseconds,
            "major_start": start.isoformat(),
            "major_end": birth_end.isoformat(),
        },
        "current_major": current_major,
        "current_sub": current_sub,
        "timeline": timeline,
        "timeline_scope": {
            "cycle_index": cycle_index,
            "start": active_start.isoformat(),
            "end": timeline[-1]["end"],
            "cycle_years": 120,
            "meaning": "formal system cycle; not a lifespan estimate",
        },
        "time_quantization": {
            "method_id": QUANTIZATION_METHOD,
            "source_id": QUANTIZATION_SOURCE["id"],
            "reference_epoch_utc": origin.isoformat(),
            "source_mansion_fraction_exact": {
                "numerator": str(elapsed_fraction.numerator),
                "denominator": str(elapsed_fraction.denominator),
            },
            "year_microseconds": year_microseconds,
            "quantum_microseconds": 1,
            "rounding": "nearest_integer_ties_to_even_at_each_final_edge",
            "scope": QUANTIZATION_SOURCE["scope"],
        },
        "rule_ids": [
            "jyotish.nakshatra.v1",
            "jyotish.vimshottari.v1",
            QUANTIZATION_RULE,
        ],
        "interpretation_scope": "Period rulers and boundaries only; no event guarantee or probability. Year basis is a declared implementation choice.",
    }
    if dasha_depth > 2:
        subdivisions = active_levels(
            current_major["lord"],
            edge(current_major_offset),
            analysis,
            year_basis=year_basis,
            depth=dasha_depth,
            _reference_epoch=origin,
            _major_start_offset_us=current_major_offset,
        )
        for original, nested in zip(
            (current_major, current_sub), subdivisions["current_levels"][:2]
        ):
            if any(original[key] != nested[key] for key in ("lord", "start", "end")):
                raise ValueError("嵌套分期与同次主运／次运边界不一致。")
            else:
                pass
        result["subdivisions"] = subdivisions
        result["rule_ids"].append(RULE)
    else:
        pass
    return result
