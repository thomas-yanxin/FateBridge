"""Explicit event clock labels on the native chart's physical TT/UT1 axis.

The date label must already be normalized to proleptic Gregorian. Solar clock
inversion is shared with other chart families, never reimplemented here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fatebridge.core.astro.birth_clock import SOLAR_BASES, resolve_solar_epoch
from fatebridge.core.astro.iers_ut1 import ut1_reference
from fatebridge.core.astro.solar_sources import SunSourceCohort
from fatebridge.core.astro.source_session import source_session
from fatebridge.core.predictive._common import build_subject
from fatebridge.core.predictive.native_chart import NativeSubject
from fatebridge.utils.errors import EphemerisSourceError

METHOD = "fatebridge.western_event_clock.v1"


def _compare_sun_sources(
    solar: dict[str, Any], subject: NativeSubject
) -> dict[str, Any]:
    """Compare observed source identities, not equatorial/ecliptic coordinates."""
    observed = solar["solar_source_comparison"]
    native = subject.calculation_basis["physical_ephemeris_source"]
    row = native["by_factor"]["Sun"]
    ids = set(row["file_ids"])
    chart_source = {
        **native,
        "by_factor": {"Sun": row},
        "files": [f for f in native["files"] if f["id"] in ids],
        "has_unidentified_sources": row["status"]
        in {"identity_unavailable", "se1_contexts_partly_identified"},
    }
    cohort = SunSourceCohort()
    try:
        for source in observed["physical_ephemeris_sources"]:
            cohort.add(source)
        # The existing comparator names its generic model/slot input
        # equatorial_Sun. This local adapter compares identities only; the
        # public native observation retains its actual ecliptic Sun label.
        cohort.add({**chart_source, "by_factor": {"equatorial_Sun": row}})
    except EphemerisSourceError as error:
        raise EphemerisSourceError("event_clock_source_mismatch") from error
    return {
        "status": "compatible_observed_sun_contexts",
        "chart_sun_source": chart_source,
        "has_unidentified_sources": observed["has_unidentified_sources"]
        or chart_source["has_unidentified_sources"],
        "scope": "Clock equatorial Sun and native ecliptic Sun: returned model, overlapping observed slot DE editions and same-name hashes compared. Native contexts are not exclusive read sets. Endpoint checks do not prove atomic reads, source completeness, measured Earth rotation or accuracy.",
    }


def build_event_subject(
    *,
    name: str,
    local_datetime: datetime,
    longitude: float,
    latitude: float,
    timezone_name: str | None = None,
    clock_basis: str = "civil",
    house_system: str = "R",
    zodiac_type: str = "Tropic",
) -> tuple[NativeSubject, dict[str, Any]]:
    """Keep the input wall label separate from the resolved physical instant.

    Civil omission preserves the API's legacy +08:00 convention. Solar labels
    require an explicit basis and no timezone. No source's clock is inferred.
    """
    if clock_basis not in {"civil", *SOLAR_BASES}:
        raise ValueError("Unknown event clock basis")
    if local_datetime.tzinfo is not None:
        raise ValueError("Event input must be a naive wall-clock label")
    if local_datetime.second or local_datetime.microsecond:
        raise ValueError("Event clock input supports minute labels")
    if clock_basis in SOLAR_BASES and timezone_name is not None:
        raise ValueError(
            "Solar event clock must omit timezone_name; no civil zone is applied"
        )
    civil_zone = (
        ("+08:00" if timezone_name is None else timezone_name)
        if clock_basis == "civil"
        else None
    )
    chart_zone = civil_zone if civil_zone is not None else "UTC"
    solar = None
    comparison = {"status": "no_solar_position_dependency"}
    with source_session():
        moment = local_datetime
        expected_time = None
        if clock_basis in SOLAR_BASES:
            epoch, solar = resolve_solar_epoch(local_datetime, longitude, clock_basis)
            expected_time = epoch.time
            if clock_basis == "local_apparent_solar":
                last_sun = solar["solar_source_comparison"]["observations"][-1]
                if (
                    abs(expected_time.jd_tt - last_sun["julian_day_tt"]) * 86400
                    > 0.0002
                ):
                    raise EphemerisSourceError("event_clock_source_mismatch")
        subject = build_subject(
            name=name,
            **(
                {"physical_epoch": epoch}
                if solar is not None
                else {"local_datetime": moment}
            ),
            longitude=longitude,
            latitude=latitude,
            timezone_name=chart_zone,
            house_system=house_system,
            zodiac_type=zodiac_type,
        )
        if solar is not None:
            # Native chart must use the very same physical axis as inversion.
            assert expected_time is not None
            if (
                abs(subject.julian_day - solar["julian_day_ut1"]) * 86400 > 0.0002
                or abs(subject.julian_day_tt - expected_time.jd_tt) * 86400 > 0.0002
            ):
                raise EphemerisSourceError("event_clock_source_mismatch")
            if clock_basis == "local_apparent_solar":
                comparison = _compare_sun_sources(solar, subject)
        return subject, {
            "method_id": METHOD,
            "input_clock_basis": clock_basis,
            "input_wall_datetime": local_datetime.isoformat(),
            "input_granularity": "minute",
            "input_timezone": timezone_name,
            "effective_civil_timezone": civil_zone,
            "timezone_selection_source": (
                "not_applicable_solar_label"
                if civil_zone is None
                else (
                    "legacy_api_default" if timezone_name is None else "caller_supplied"
                )
            ),
            "chart_timezone": chart_zone,
            "converted_utc": subject.iso_formatted_utc_datetime,
            "julian_day_tt": subject.julian_day_tt,
            "julian_day_ut1": subject.julian_day,
            "time_scale_method": subject.calculation_basis["time_scale"],
            "ut1_reference": ut1_reference(subject.julian_day_tt, subject.julian_day),
            "utc_representation": (
                epoch.representation() if solar is not None else None
            ),
            "modeled_solar_conversion_performed": solar is not None,
            "source_clock_identification_performed": False,
            "input_clock_accuracy_certified": False,
            "solar_conversion": solar,
            "clock_chart_source_comparison": comparison,
            "scope": "Normalized Gregorian minute labels; explicit civil/LMT/geocentric LAT convention. Before 1960 the UTC-named carrier denotes modeled UT1 labels, not atomic UTC. Numerical resolution does not establish original record accuracy. No regional clock, original author's convention, measured EOP or event outcome inferred.",
        }
