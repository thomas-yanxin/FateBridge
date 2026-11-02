"""Primary epochs and calendar lookups without a fabricated UTC datetime."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from typing import Any

from fatebridge.core import almanac
from fatebridge.core.astro.birth import AstroBirthInfo, NativeSolarBirthInfo
from fatebridge.core.astro.historical_utc import (
    historical_utc_table,
    historical_utc_to_tt_point,
    utc1960_table,
)
from fatebridge.core.astro.physical_epoch import PhysicalEpoch, _calendar_from_jd
from fatebridge.core.astro.time_scales import EphemerisTime, ephemeris_time
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.utc_policy import leap_table
from fatebridge.utils.civil_time import UTCCalendar
from fatebridge.utils.errors import EphemerisSourceError


def native_birth_epoch(birth: AstroBirthInfo) -> PhysicalEpoch | None:
    return birth.native_epoch if isinstance(birth, NativeSolarBirthInfo) else None


def birth_time_scales(birth: AstroBirthInfo) -> EphemerisTime:
    native = native_birth_epoch(birth)
    return (
        native.time if native is not None else ephemeris_time(birth.physical_datetime)
    )


def birth_utc_label(birth: AstroBirthInfo) -> str | None:
    native = native_birth_epoch(birth)
    return native.utc_label if native is not None else birth.utc_isoformat


def native_year_context(birth: AstroBirthInfo) -> tuple[int, dict[str, Any]]:
    """The shared UTC LiChun crossing, compared on physical TT.

    The supplied solar-label year selects the yearly crossing only. LMT/LAT
    differ from UT1 by less than a day, so a New-Year label crossing is still
    on the same side of February's LiChun. This also avoids an artificial
    request for year0/10000 datetime while retaining the same seasonal year.
    """
    native = native_birth_epoch(birth)
    if native is None:
        raise ValueError("Native year context requires a primary physical epoch")
    return year_context_for_epoch(native, birth.local_datetime.year)


def year_context_for_epoch(
    native: PhysicalEpoch,
    reference_year: int,
    *,
    reference_year_basis: str = "input_solar_label_year_selects_crossing_only",
) -> tuple[int, dict[str, Any]]:
    year = reference_year
    term = next(
        t for t in almanac.get_solar_terms_for_year(year, "UTC") if t.name == "立春"
    )
    almanac.require_calculated_solar_term(term)
    # No generic yearly-lookup assumption may silently choose a remote root.
    if term.moment.year != year or term.moment.month != 2:
        raise ValueError("UTC LiChun crossing is not in the declared February window")
    boundary_tt = ephemeris_time(term.moment).jd_tt
    assert native.time.jd_tt is not None
    if boundary_tt is None:
        raise ValueError("Native year comparison requires a calculated TT boundary")
    selected = year if native.time.jd_tt >= boundary_tt else year - 1
    return selected, {
        "policy_id": "shared_UTC_LiChun_primary_TT_comparison_v1",
        "reference_year": year,
        "reference_year_basis": reference_year_basis,
        "calendar_timezone": "UTC_reference_not_inferred_original_zone",
        "birth_julian_day_tt": native.time.jd_tt,
        "boundary_julian_day_tt": boundary_tt,
        "boundary": term.as_dict(),
        "year": selected,
        "comparison": "physical_TT_half_open_at_LiChun",
        "classical_clock_mapping_accepted": False,
    }


_UTC = re.compile(
    r"^([+-]?\d{4,})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?\+00:00$"
)


def _ordinal(year: int, month: int, day: int) -> int:
    previous = year - 1
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    months = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if not 1 <= month <= 12 or not 1 <= day <= months[month - 1]:
        raise ValueError("Invalid native UTC calendar label")
    return (
        365 * previous
        + previous // 4
        - previous // 100
        + previous // 400
        + sum(months[: month - 1])
        + day
    )


def native_utc8_clock(epoch: PhysicalEpoch) -> tuple[str | None, datetime | None]:
    """An actual UTC+08 label and a date-only lookup anchor, never a new epoch."""
    if epoch.utc_label is None:
        return None, None
    match = _UTC.fullmatch(epoch.utc_label)
    if match is None:
        raise ValueError("Native UTC label cannot be parsed without changing it")
    y, m, d, hour, minute, second = map(int, match.groups()[:6])
    micro = int((match[7] or "0").ljust(6, "0"))
    if not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= second <= 60):
        raise ValueError("Invalid native UTC clock fields")
    if (second == 60) != epoch.utc_is_leap_second:
        raise ValueError("Native UTC leap-second label and epoch disagree")
    carry, local_hour = divmod(hour + 8, 24)
    date = UTCCalendar(_ordinal(y, m, d) + carry, 0)
    year, month, day = date.date_parts
    year_text = f"{year:04d}" if 0 <= year <= 9999 else f"{year:+07d}"
    fraction = f".{micro:06d}" if micro else ""
    label = (
        f"{year_text}-{month:02d}-{day:02d}T{local_hour:02d}:{minute:02d}:"
        f"{second:02d}{fraction}+08:00"
    )
    lookup = (
        datetime(year, month, day, 12, tzinfo=timezone(timedelta(hours=8)))
        if 1 <= year <= 9999
        else None
    )
    return label, lookup


def _historical_utc8_date(
    point: TTInstant,
) -> tuple[datetime, dict[str, Any]] | None:
    """Prove a fixed UTC+08 DATE without assigning a UTC clock label.

    A TT calendar date supplies search candidates only. Membership is proved
    against actual UTC+08 midnights, encoded directly from published atomic
    offsets. Positive gaps and negative overlaps at UTC00:00 need not make
    the surrounding UTC+08 day ambiguous. No UT1 model or inverse UTC label
    is used here. The result's noon is a date-table index, never an epoch.
    """
    early, historical, atomic = utc1960_table(), historical_utc_table(), leap_table()
    first = datetime.fromisoformat(early["entries"][0]["effective_date"]).replace(
        tzinfo=timezone.utc
    )
    stop = datetime.fromisoformat(historical["valid_until"]).replace(
        tzinfo=timezone.utc
    )
    first_tt = historical_utc_to_tt_point(first)
    first_atomic = atomic["entries"][0]
    if first_tt is None or first_atomic["effective_date"] != historical["valid_until"]:
        raise EphemerisSourceError("birth_clock_source_mismatch")
    stop_offset = Fraction(str(first_atomic["tai_minus_utc_seconds"]))
    stop_tt = TTInstant.from_utc(stop, tai_minus_utc_seconds=stop_offset)
    # Include the first published atomic boundary itself. Its UTC+08 date
    # is still bracketed by supported midnights; later points are outside
    # this historical-adjustment resolver's scope.
    if not first_tt.days <= point.days <= stop_tt.days:
        return None

    def source_record(table: dict[str, Any]) -> dict[str, str]:
        return {
            "source_url": table["source_url"],
            "declared_source_sha256": table["source_sha256"],
            "loaded_table_sha256": hashlib.sha256(
                json.dumps(table, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        }

    def midnight_boundary(moment: datetime) -> tuple[TTInstant, dict[str, str]] | None:
        found = historical_utc_to_tt_point(moment)
        if found is not None:
            return found, source_record(
                early if moment.year == first.year else historical
            )
        # Only the first atomic UTC day is needed to close the1972 transition
        # date. This is not an extrapolation of the historical affine table.
        if stop <= moment < stop + timedelta(days=1):
            return (
                TTInstant.from_utc(moment, tai_minus_utc_seconds=stop_offset),
                source_record(atomic),
            )
        return None

    # TT+08 is a calendar search hint, not a conversion to UTC+08. Search
    # adjacent dates too: TT-UTC can put that hint beyond a civil midnight.
    hint = date(*_calendar_from_jd(point.days + Fraction(1, 3)).date_parts)
    zone = timezone(timedelta(hours=8))
    matches = []
    for shift in (-1, 0, 1):
        day = hint + timedelta(days=shift)
        midnight = datetime(day.year, day.month, day.day, tzinfo=zone)
        start_utc = midnight.astimezone(timezone.utc)
        end_utc = (midnight + timedelta(days=1)).astimezone(timezone.utc)
        start, end = midnight_boundary(start_utc), midnight_boundary(end_utc)
        if start is None or end is None:
            continue
        if end[0].days <= start[0].days:
            raise EphemerisSourceError("birth_clock_source_mismatch")
        if start[0].days <= point.days < end[0].days:
            matches.append(
                (
                    midnight + timedelta(hours=12),
                    {
                        "policy_id": "published_offsets_TT_bracket_fixed_UTC8_date_v1",
                        "comparison_basis": "primary_TT_point_half_open_between_UTC8_midnights",
                        "calendar_date": day.isoformat(),
                        "primary_julian_day_tt_exact": str(point.days),
                        "start_boundary": {
                            "utc_datetime": start_utc.isoformat(),
                            "julian_day_tt_exact": str(start[0].days),
                            "coefficient_source": start[1],
                        },
                        "next_boundary": {
                            "utc_datetime": end_utc.isoformat(),
                            "julian_day_tt_exact": str(end[0].days),
                            "coefficient_source": end[1],
                        },
                        "utc_clock_label_assigned": False,
                        "classical_clock_mapping_accepted": False,
                    },
                )
            )
    return matches[0] if len(matches) == 1 else None


def native_month_context(epoch: PhysicalEpoch, basis: str) -> dict[str, Any]:
    label, lookup = native_utc8_clock(epoch)
    clocks: dict[str, Any] = {
        "instant_utc": epoch.utc_label,
        "calendar_datetime": label,
        "timezone": "UTC+08:00",
        "primary_julian_day_tt": epoch.time.jd_tt,
        "primary_julian_day_ut1": epoch.time.jd_ut1,
        "utc_representation": epoch.representation(),
    }
    if lookup is None and basis == "jie_month":
        # _term_window uses only the anchor's Gregorian YEAR to obtain the
        # previous/current/next year's candidates. A missing UTC clock label
        # does not prevent selecting those candidates from the primary TT
        # calendar. This anchor is never the event or the comparison instant.
        assert epoch.time.jd_tt is not None
        search_year = _calendar_from_jd(Fraction(epoch.time.jd_tt)).date_parts[0]
        if 2 <= search_year <= 9998:
            lookup = datetime(
                search_year, 7, 1, 12, tzinfo=timezone(timedelta(hours=8))
            )
            clocks.update(
                term_search_year=search_year,
                term_search_year_basis=(
                    "primary_TT_Gregorian_year_selects_candidates_only"
                ),
            )
    if lookup is None and label is None and basis == "chinese_lunar_utc8":
        assert epoch.time.jd_tt is not None
        proved = _historical_utc8_date(TTInstant.from_float(epoch.time.jd_tt))
        if proved is not None:
            lookup, evidence = proved
            clocks.update(
                calendar_date=evidence["calendar_date"], calendar_date_evidence=evidence
            )
    if lookup is None:
        return {
            **clocks,
            "status": (
                "outside_datetime_calendar_range" if label else "calendar_unavailable"
            ),
            "month_number": None,
            "is_leap_month": None,
            "unavailable_reason": (
                "fixed_utc8_label_outside_datetime_range"
                if label
                else (
                    "native_epoch_has_no_proved_fixed_utc8_date"
                    if basis == "chinese_lunar_utc8"
                    else "native_epoch_has_no_unique_UTC_label"
                )
            ),
        }
    if basis == "chinese_lunar_utc8":
        # The shared lunar table is indexed by a Gregorian DATE. Noon selects
        # that date only, and is never substituted for the physical epoch.
        lunar = almanac.get_lunar_context(lookup, timezone_name="Etc/GMT-8")
        if lunar is None:
            return {
                **clocks,
                "status": "calendar_unavailable",
                "month_number": None,
                "boundary_basis": "shared_chinese_lunar_table_utc8_civil_date",
            }
        return {
            **clocks,
            "status": "available",
            "month_number": lunar["month"],
            "lunar_year": lunar["year"],
            "lunar_day": lunar["day"],
            "is_leap_month": lunar["is_leap_month"],
            "boundary_basis": "shared_chinese_lunar_table_utc8_civil_date",
            "conversion_source": lunar.get("conversion_source"),
            "calendar_lookup_basis": (
                "primary_TT_bracketed_UTC8_date_no_clock_label_or_epoch_substitution"
                if "calendar_date_evidence" in clocks
                else "unique_UTC8_date_only_no_epoch_substitution"
            ),
        }
    if basis != "jie_month":
        raise ValueError("Unknown native month policy")
    try:
        terms = [
            t
            for t in almanac._term_window(lookup, "Etc/GMT-8")
            if t.name in almanac.BAZI_MONTH_START_TERMS
        ]
    except OverflowError:
        return {
            **clocks,
            "status": "outside_datetime_calendar_range",
            "month_number": None,
            "is_leap_month": None,
            "unavailable_reason": "jie_neighbour_calendar_year_outside_datetime_range",
        }
    assert epoch.time.jd_tt is not None
    start = stop = None
    for term in terms:
        tt = ephemeris_time(term.moment).jd_tt
        if tt is None:
            raise ValueError("Native jie comparison requires physical TT boundaries")
        if tt <= epoch.time.jd_tt:
            start = term
        else:
            stop = term
            break
    if start is None or stop is None:
        raise ValueError("Unable to bracket native epoch by shared jie boundaries")
    almanac.require_calculated_solar_term(start)
    almanac.require_calculated_solar_term(stop)
    branch = almanac.BAZI_MONTH_START_TERMS[start.name]
    return {
        **clocks,
        "status": "available",
        "month_number": almanac.BAZI_MONTH_SEQUENCE.index(branch) + 1,
        "month_branch": branch,
        "is_leap_month": False,
        "start_boundary": start.as_dict(),
        "next_boundary": stop.as_dict(),
        "boundary_basis": "calculated_jie_instants_half_open",
        "comparison_basis": "primary_TT_not_a_datetime_surrogate",
    }
