"""Rao16.3 recursive Vimshottari periods, from the complete major-period origin."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fractions import Fraction
from typing import Any

ORDER = ("Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury")
YEARS = dict(zip(ORDER, (7, 20, 6, 10, 7, 18, 16, 19, 17)))
YEAR_MICROSECONDS = {
    "sidereal_365_25636": 31558149504000,
    "tropical_365_2425": 31556952000000,
    "savana_360": 31104000000000,
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
    major_start: datetime,
    analysis: datetime,
    *,
    year_basis: str,
    depth: int,
    _reference_epoch: datetime | None = None,
    _major_start_offset_us: Fraction | None = None,
) -> dict[str, Any]:
    """Return the active ancestry and nine siblings at each requested level.

    Fractions retain the complete MD origin. A displayed boundary is rounded
    once, with ties to even, never recursively derived from a rounded duration.
    All selections use those same half-open microsecond boundaries.
    """
    if type(depth) is not int or not 2 <= depth <= len(LEVELS):
        raise ValueError("Vimshottari depth must be an integer2..6")
    if major_lord not in YEARS or year_basis not in YEAR_MICROSECONDS:
        raise ValueError("Unknown Vimshottari lord or year basis")
    if major_start.utcoffset() is None or analysis.utcoffset() is None:
        raise ValueError("Vimshottari period and target clocks must carry a timezone")
    if (_reference_epoch is None) != (_major_start_offset_us is None):
        raise ValueError("A common epoch requires its exact major-period offset")
    if _reference_epoch is not None and _reference_epoch.utcoffset() is None:
        raise ValueError("The common period epoch must carry a timezone")
    if _major_start_offset_us is not None and not isinstance(
        _major_start_offset_us, Fraction
    ):
        raise ValueError("The major-period offset must retain its exact fraction")
    global_epoch = _reference_epoch is not None
    origin = (_reference_epoch or major_start).astimezone(timezone.utc)
    offset = Fraction(0) if _major_start_offset_us is None else _major_start_offset_us
    target = analysis.astimezone(timezone.utc)
    unit = YEAR_MICROSECONDS[year_basis]
    duration = Fraction(YEARS[major_lord] * unit)

    def boundary(offset: Fraction) -> datetime:
        try:
            return origin + timedelta(microseconds=round(offset))
        except OverflowError as error:
            raise ValueError(
                "Vimshottari boundaries exceed the datetime range"
            ) from error

    if boundary(offset) != major_start.astimezone(timezone.utc):
        raise ValueError("The displayed major start contradicts its exact epoch offset")
    if not boundary(offset) <= target < boundary(offset + duration):
        raise ValueError("Target must lie within the complete supplied major period")

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
        if selected is None:
            raise ValueError("Target falls outside its complete parent period")
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
            "reference_epoch_utc": origin.isoformat(),
            "complete_major_start_offset_microseconds_fraction": {
                "numerator": str(_major_start_offset_us.numerator),
                "denominator": str(_major_start_offset_us.denominator),
            },
            "quantization_method_id": QUANTIZATION_METHOD,
            "source_id": QUANTIZATION_SOURCE["id"],
        }
    return result
