"""Jyotish Dasha systems: Vimshottari (incl. 365.25 Julian year), Yogini, Ashtottari, Chara Dasha."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from fractions import Fraction
from typing import Any, TypedDict

from fatebridge.core.astro.astrology_tables import SIGNS
from fatebridge.core.astro.reference import NAKSHATRAS
from fatebridge.core.jyotish.vargas import EXALTATION, RASI_LORDS, longitude_ratio
from fatebridge.utils.civil_time import UTCCalendar, utc_calendar

ORDER = ("Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury")
YEARS = dict(zip(ORDER, (7, 20, 6, 10, 7, 18, 16, 19, 17)))
YEAR_MICROSECONDS = {
    "julian_365_25": 31_557_600_000_000,
    "sidereal_365_25636": 31_558_149_504_000,
    "tropical_365_2425": 31_556_952_000_000,
    "savana_360": 31_104_000_000_000,
}
YEAR_DAYS = {
    "julian_365_25": 365.25,
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
    "scope": "Exact rational boundary quantization per nominal UTC birth epoch.",
}

YOGINI_ORDER = (
    ("Mangala", "Moon", 1),
    ("Pingala", "Sun", 2),
    ("Dhanya", "Jupiter", 3),
    ("Bhramari", "Mars", 4),
    ("Bhadrika", "Mercury", 5),
    ("Ulka", "Saturn", 6),
    ("Siddha", "Venus", 7),
    ("Sankata", "Rahu", 8),
)

ASHTOTTARI_ORDER = (
    ("Sun", 6),
    ("Moon", 15),
    ("Mars", 8),
    ("Mercury", 17),
    ("Saturn", 10),
    ("Jupiter", 19),
    ("Rahu", 12),
    ("Venus", 21),
)


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
    """Return the active ancestry and nine siblings at each requested level (depth 2..6)."""
    if type(depth) is not int or not 2 <= depth <= len(LEVELS):
        raise ValueError("Vimshottari depth must be an integer 2..6")
    if major_lord not in YEARS or year_basis not in YEAR_MICROSECONDS:
        raise ValueError("Unknown Vimshottari lord or year basis")
    if analysis.utcoffset() is None or (
        isinstance(major_start, datetime) and major_start.utcoffset() is None
    ):
        raise ValueError("Vimshottari period and target clocks must carry a timezone")
    if (_reference_epoch is None) != (_major_start_offset_us is None):
        raise ValueError("A common epoch requires its exact major-period offset")
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

    def edge(us_offset: Fraction) -> UTCCalendar:
        return epoch.shifted(timedelta(microseconds=round(us_offset)))

    current: list[dict[str, Any]] = []
    siblings: list[dict[str, Any]] = []
    chain: list[str] = []
    for level_idx, (level_name, code) in enumerate(LEVELS[:depth], start=1):
        rows: list[dict[str, Any]] = []
        active_row: dict[str, Any] | None = None
        active_start: Fraction | None = None
        active_end: Fraction | None = None
        cursor = Fraction(0)
        start_idx = ORDER.index(chain[-1] if chain else major_lord)
        for step in range(9):
            lord = ORDER[(start_idx + step) % 9] if chain else major_lord
            if not chain and step > 0:
                break
            start = offset if not chain else offset + duration * cursor / 120
            if chain:
                cursor += YEARS[lord]
            end = (
                offset + duration
                if not chain or step == 8
                else offset + duration * cursor / 120
            )
            start_cal, end_cal = edge(start), edge(end)
            row: dict[str, Any] = {
                "level": level_idx,
                "name": level_name,
                "abbreviation": code,
                "lord": lord,
                "major_lord": major_lord,
                "lord_chain": [*chain, lord],
                "start": start_cal.isoformat(),
                "end": end_cal.isoformat(),
                "duration_years": float((end - start) / unit),
            }
            if chain:
                rows.append(row)
            if start_cal <= target < end_cal:
                active_row, active_start, active_end = row, start, end
        if active_row is None or active_start is None or active_end is None:
            raise ValueError(
                "Vimshottari target falls outside the active parent interval"
            )
        if chain:
            siblings.append(
                {"level": level_idx, "parent_lord_chain": list(chain), "periods": rows}
            )
        current.append(active_row)
        chain = active_row["lord_chain"]
        offset, duration = active_start, active_end - active_start

    return {
        "method_id": (
            "rao2000_recursive_vimshottari_global_epoch_v2"
            if _reference_epoch is not None
            else "rao2000_recursive_vimshottari_exact_fractions_v1"
        ),
        "depth": depth,
        "current_levels": current,
        "siblings_by_level": siblings,
        "year_basis": year_basis,
    }


def vimshottari(
    birth_utc: datetime | UTCCalendar,
    moon_longitude: float,
    analysis: datetime,
    *,
    year_basis: str = "julian_365_25",
    dasha_depth: int = 2,
) -> dict[str, Any]:
    """Compute Vimshottari Mahadasha-Deha Dasha tree with exact fractional boundaries."""
    if type(dasha_depth) is not int or not 2 <= dasha_depth <= 6:
        raise ValueError("Vimshottari 层数须为 2 至 6 的整数。")
    if year_basis not in YEAR_DAYS:
        raise ValueError("不支持的 Vimshottari 年长口径。")
    if analysis.utcoffset() is None or (
        isinstance(birth_utc, datetime) and birth_utc.utcoffset() is None
    ):
        raise ValueError("达沙的出生与分析时刻必须带时区。")
    origin = utc_calendar(birth_utc) if isinstance(birth_utc, datetime) else birth_utc
    target = utc_calendar(analysis)
    if target < origin:
        raise ValueError("分析时刻不能早于出生时刻。")
    seed = nakshatra(moon_longitude)
    first = ORDER.index(seed["lord"])
    year_us = YEAR_MICROSECONDS[year_basis]
    numerator, denominator = longitude_ratio(moon_longitude)
    _, remainder = divmod(numerator * 3, denominator * 40)
    elapsed_fraction = Fraction(remainder, denominator * 40)
    first_years = YEARS[seed["lord"]]
    elapsed_years_exact = elapsed_fraction * first_years
    first_offset = -elapsed_years_exact * year_us

    def edge(offset: Fraction) -> UTCCalendar:
        return origin.shifted(timedelta(microseconds=round(offset)))

    start = edge(first_offset)
    cycle_duration = timedelta(microseconds=120 * year_us)
    cycle_index = target.elapsed_since(start) // cycle_duration
    active_start = start.shifted(cycle_index * cycle_duration)
    active_offset = first_offset + cycle_index * 120 * year_us
    timeline = []
    cumulative = 0
    current_major = current_sub = None
    current_major_offset = None
    for step in range(9):
        lord = ORDER[(first + step) % 9]
        years = YEARS[lord]
        major_offset = active_offset + cumulative * year_us
        major_start = edge(major_offset)
        major_end = edge(major_offset + years * year_us)
        major = {
            "lord": lord,
            "start": major_start.isoformat(),
            "end": major_end.isoformat(),
            "duration_years": years,
        }
        subs = []
        sub_total = 0
        for substep in range(9):
            sublord = ORDER[(first + step + substep) % 9]
            sub_start = edge(major_offset + Fraction(years * sub_total * year_us, 120))
            sub_total += YEARS[sublord]
            sub_end = (
                major_end
                if substep == 8
                else edge(major_offset + Fraction(years * sub_total * year_us, 120))
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
        if major_start <= target < major_end:
            current_major = dict(major)
            current_major_offset = major_offset
        timeline.append({**major, "antardashas": subs})
        cumulative += years
    if current_major is None or current_sub is None or current_major_offset is None:
        raise ValueError("达沙日期边界超出可计算范围。")
    birth_end = edge(first_offset + first_years * year_us)
    elapsed_us = round(elapsed_years_exact * year_us)
    result: dict[str, Any] = {
        "method_id": "moon_nakshatra_vimshottari_v1",
        "year_basis": year_basis,
        "year_days": YEAR_DAYS[year_basis],
        "analysis_datetime": analysis.isoformat(),
        "seed": {**seed, "moon_longitude": moon_longitude},
        "birth_balance": {
            "lord": seed["lord"],
            "elapsed_years": float(elapsed_years_exact),
            "remaining_years": float((1 - elapsed_fraction) * first_years),
            "elapsed_microseconds": elapsed_us,
            "remaining_microseconds": first_years * year_us - elapsed_us,
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
        },
        "rule_ids": [
            "jyotish.nakshatra.v1",
            "jyotish.vimshottari.v1",
            QUANTIZATION_RULE,
        ],
    }
    if dasha_depth > 2:
        subdivisions = active_levels(
            str(current_major["lord"]),
            edge(current_major_offset),
            analysis,
            year_basis=year_basis,
            depth=dasha_depth,
            _reference_epoch=origin,
            _major_start_offset_us=current_major_offset,
        )
        result["subdivisions"] = subdivisions
        result["rule_ids"].append(RULE)
    return result


def yogini_dasha(
    birth_utc: datetime | UTCCalendar,
    moon_longitude: float,
    analysis: datetime,
    *,
    year_basis: str = "julian_365_25",
) -> dict[str, Any]:
    """Compute the 36-year Yogini Dasha cycle (BPHS 46) from Moon nakshatra."""
    origin = utc_calendar(birth_utc) if isinstance(birth_utc, datetime) else birth_utc
    target = utc_calendar(analysis)
    seed = nakshatra(moon_longitude)
    first_idx = (
        seed["index"] + 2
    ) % 8  # (nakshatra_1_based + 3) % 8 using 1-based -> 0-based (idx+3-1)%8
    # Wait: Ashwini=1 -> (1+3)%8=4 -> index 3 (Bhramari); standard 1-based: 1=Mangala,2=Pingala,3=Dhanya,4=Bhramari...
    first_idx = (seed["index"] + 3 - 1) % 8
    year_us = YEAR_MICROSECONDS[year_basis]
    elapsed_frac = Fraction(seed["fraction_elapsed"])
    first_years = YOGINI_ORDER[first_idx][2]
    first_offset = -elapsed_frac * first_years * year_us
    start = origin.shifted(timedelta(microseconds=round(first_offset)))
    cycle_dur = timedelta(microseconds=36 * year_us)
    cycle_index = max(0, target.elapsed_since(start) // cycle_dur)
    active_offset = first_offset + cycle_index * 36 * year_us

    timeline = []
    cum = 0
    current_major = current_sub = None
    for step in range(8):
        name, lord, yrs = YOGINI_ORDER[(first_idx + step) % 8]
        m_start = origin.shifted(
            timedelta(microseconds=round(active_offset + cum * year_us))
        )
        m_end = origin.shifted(
            timedelta(microseconds=round(active_offset + (cum + yrs) * year_us))
        )
        subs = []
        sub_cum = 0
        for sstep in range(8):
            sname, slord, syrs = YOGINI_ORDER[(first_idx + step + sstep) % 8]
            s_start = origin.shifted(
                timedelta(
                    microseconds=round(
                        active_offset
                        + cum * year_us
                        + Fraction(yrs * sub_cum * year_us, 36)
                    )
                )
            )
            sub_cum += syrs
            s_end = (
                m_end
                if sstep == 7
                else origin.shifted(
                    timedelta(
                        microseconds=round(
                            active_offset
                            + cum * year_us
                            + Fraction(yrs * sub_cum * year_us, 36)
                        )
                    )
                )
            )
            sub = {
                "yogini": sname,
                "lord": slord,
                "start": s_start.isoformat(),
                "end": s_end.isoformat(),
            }
            subs.append(sub)
            if s_start <= target < s_end:
                current_sub = dict(sub)
        row = {
            "yogini": name,
            "lord": lord,
            "years": yrs,
            "start": m_start.isoformat(),
            "end": m_end.isoformat(),
            "antardashas": subs,
        }
        if m_start <= target < m_end:
            current_major = {
                "yogini": name,
                "lord": lord,
                "years": yrs,
                "start": m_start.isoformat(),
                "end": m_end.isoformat(),
            }
        timeline.append(row)
        cum += yrs
    return {
        "method_id": "bphs_yogini_dasha_36y",
        "cycle_years": 36,
        "seed_nakshatra": seed["name"],
        "current_major": current_major,
        "current_sub": current_sub,
        "timeline": timeline,
    }


def ashtottari_dasha(
    birth_utc: datetime | UTCCalendar,
    moon_longitude: float,
    analysis: datetime,
    *,
    year_basis: str = "julian_365_25",
) -> dict[str, Any]:
    """Compute the 108-year Ashtottari Dasha seeded from Ardra (index 6)."""
    origin = utc_calendar(birth_utc) if isinstance(birth_utc, datetime) else birth_utc
    target = utc_calendar(analysis)
    seed = nakshatra(moon_longitude)
    # 27-nakshatra grouping starting Ardra (6): 4,3,4,3,4,3,4,2? Standard Parashari 27-nakshatra 3-4 alternation from Ardra
    # Ardra..Pushya(2)->Sun? Standard table maps each nakshatra 1..27 into 8 Ashtottari lords cleanly:
    n_idx = (seed["index"] - 6) % 27  # Ardra=0
    if n_idx < 4:
        first_idx, span, offset_n = (
            0,
            4,
            n_idx,
        )  # Sun (Ardra, Punarvasu, Pushya, Ashlesha)
    elif n_idx < 7:
        first_idx, span, offset_n = 1, 3, n_idx - 4  # Moon
    elif n_idx < 11:
        first_idx, span, offset_n = 2, 4, n_idx - 7  # Mars
    elif n_idx < 14:
        first_idx, span, offset_n = 3, 3, n_idx - 11  # Mercury
    elif n_idx < 18:
        first_idx, span, offset_n = 4, 4, n_idx - 14  # Saturn
    elif n_idx < 21:
        first_idx, span, offset_n = 5, 3, n_idx - 18  # Jupiter
    elif n_idx < 24:
        first_idx, span, offset_n = 6, 3, n_idx - 21  # Rahu
    else:
        first_idx, span, offset_n = 7, 3, n_idx - 24  # Venus

    year_us = YEAR_MICROSECONDS[year_basis]
    elapsed_frac = Fraction(offset_n + Fraction(seed["fraction_elapsed"]), span)
    first_years = ASHTOTTARI_ORDER[first_idx][1]
    first_offset = -elapsed_frac * first_years * year_us
    start = origin.shifted(timedelta(microseconds=round(first_offset)))
    cycle_dur = timedelta(microseconds=108 * year_us)
    cycle_index = max(0, target.elapsed_since(start) // cycle_dur)
    active_offset = first_offset + cycle_index * 108 * year_us

    timeline = []
    cum = 0
    current_major = None
    for step in range(8):
        lord, yrs = ASHTOTTARI_ORDER[(first_idx + step) % 8]
        m_start = origin.shifted(
            timedelta(microseconds=round(active_offset + cum * year_us))
        )
        m_end = origin.shifted(
            timedelta(microseconds=round(active_offset + (cum + yrs) * year_us))
        )
        row = {
            "lord": lord,
            "years": yrs,
            "start": m_start.isoformat(),
            "end": m_end.isoformat(),
        }
        if m_start <= target < m_end:
            current_major = row
        timeline.append(row)
        cum += yrs
    return {
        "method_id": "parashari_ashtottari_dasha_108y",
        "cycle_years": 108,
        "seed_nakshatra": seed["name"],
        "current_major": current_major,
        "timeline": timeline,
    }


def chara_dasha(
    birth_utc: datetime | UTCCalendar,
    longitudes: dict[str, float],
    ascendant: float,
    analysis: datetime,
    *,
    year_basis: str = "julian_365_25",
) -> dict[str, Any]:
    """Compute K.N. Rao Jaimini Chara Dasha across all 12 signs with dual-lord Scorpio/Aquarius resolution."""
    origin = utc_calendar(birth_utc) if isinstance(birth_utc, datetime) else birth_utc
    target = utc_calendar(analysis)
    signs = {
        p: int(longitudes[p] // 30)
        for p in (
            "Sun",
            "Moon",
            "Mars",
            "Mercury",
            "Jupiter",
            "Venus",
            "Saturn",
            "Rahu",
            "Ketu",
        )
    }
    asc_sign = int(ascendant // 30)
    # 9th from Lagna determines Savya (+1) or Apasavya (-1): direct for odd signs, reverse for even (or K.N. Rao standard)
    # Standard K.N. Rao: If 9th sign is odd-footed (Aries, Taurus, Gemini, Libra, Scorpio, Sagittarius) -> forward, else reverse
    ninth_sign = (asc_sign + 8) % 12
    savya_from_lagna = ninth_sign in {0, 1, 2, 6, 7, 8}
    step_dir = 1 if savya_from_lagna else -1
    sign_order = [(asc_sign + step_dir * i) % 12 for i in range(12)]

    # Dual lords: Scorpio (7): Mars/Ketu; Aquarius (10): Saturn/Rahu (pick stronger: more planets conjoined or not in own sign)
    def _effective_lord_sign(s_idx: int) -> tuple[str, int]:
        if s_idx == 7:
            cands = ("Mars", "Ketu")
        elif s_idx == 10:
            cands = ("Saturn", "Rahu")
        else:
            lord = RASI_LORDS[s_idx]
            return lord, signs[lord]
        # Exclude own sign if other is elsewhere, else pick one with more co-tenants
        in_own = [c for c in cands if signs[c] == s_idx]
        if len(in_own) == 1:
            picked = next(c for c in cands if c != in_own[0])
            return picked, signs[picked]
        counts = {
            c: sum(1 for p, ps in signs.items() if ps == signs[c] and p != c)
            for c in cands
        }
        picked = cands[0] if counts[cands[0]] >= counts[cands[1]] else cands[1]
        return picked, signs[picked]

    year_us = YEAR_MICROSECONDS[year_basis]
    periods = []
    cum_years = 0
    current_major = None
    for s_idx in sign_order:
        lord, lord_sign = _effective_lord_sign(s_idx)
        forward = s_idx in {0, 1, 2, 6, 7, 8}
        raw_dist = (lord_sign - s_idx) % 12 if forward else (s_idx - lord_sign) % 12
        yrs = 12 if raw_dist == 0 else raw_dist
        # Exaltation +1 / Debilitation -1 adjustment (if lord is not in own sign)
        if lord in EXALTATION and signs[lord] != s_idx:
            if signs[lord] == EXALTATION[lord]:
                yrs = min(12, yrs + 1)
            elif signs[lord] == (EXALTATION[lord] + 6) % 12:
                yrs = max(1, yrs - 1)
        m_start = origin.shifted(timedelta(microseconds=cum_years * year_us))
        m_end = origin.shifted(timedelta(microseconds=(cum_years + yrs) * year_us))
        row = {
            "sign": SIGNS[s_idx],
            "sign_index": s_idx,
            "lord": lord,
            "years": yrs,
            "start": m_start.isoformat(),
            "end": m_end.isoformat(),
        }
        if m_start <= target < m_end:
            current_major = row
        periods.append(row)
        cum_years += yrs

    return {
        "method_id": "jaimini_chara_dasha_knrao",
        "direction": "forward" if savya_from_lagna else "reverse",
        "current_major": current_major,
        "timeline": periods,
    }


class DashaGrid:
    """Summarize nakshatra/dasha stability over an explicit birth-time uncertainty interval."""

    def __init__(
        self,
        analysis: datetime,
        year_basis: str,
        divisions: list[int] | None,
        depth: int,
    ) -> None:
        self.analysis = analysis
        self.year_basis = year_basis
        self.divisions = divisions
        self.depth = depth
        self.samples: list[dict[str, Any]] = []

    def observe_moon(self, offset_seconds: float, moon_lon: float) -> None:
        n = nakshatra(moon_lon)
        self.samples.append(
            {
                "offset_seconds": offset_seconds,
                "nakshatra": n["name"],
                "pada": n["pada"],
                "lord": n["lord"],
            }
        )

    def result(self) -> dict[str, Any]:
        unique_naks = sorted({s["nakshatra"] for s in self.samples})
        return {
            "status": "assessed" if self.samples else "not_assessed",
            "nakshatra_options": unique_naks,
            "sample_count": len(self.samples),
        }
