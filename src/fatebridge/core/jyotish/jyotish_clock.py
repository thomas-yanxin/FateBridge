"""Keep a recorded civil instant separate from its apparent-solar clock label."""

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from fractions import Fraction
from typing import Any

from fatebridge.core.astro.birth import AstroBirthInfo, require_resolved_birth_timezone
from fatebridge.core.astro.birth_clock import resolve_solar_epoch
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.sensitivity_grid import (
    RecordedBirthSample,
    civil_recorded_sample,
    sampling_radius,
    shift_civil_recorded_sample,
)
from fatebridge.core.astro.solar_sources import SunSourceCohort, sun_source
from fatebridge.core.astro.source_session import current_source_session
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.utils.civil_time import utc_calendar
from fatebridge.utils.errors import EphemerisSourceError

RULE_ID = "jyotish.recorded_instant.v1"


def require_recorded_instant(birth: AstroBirthInfo) -> None:
    """Require a known clock basis and preserve its unchanged physical instant."""
    require_resolved_birth_timezone(birth.timezone_source)
    recorded = birth.recorded_datetime or birth.local_datetime
    physical = (
        birth.require_utc_datetime
        if birth.clock_conversion is not None
        else birth.physical_datetime
    )
    if physical.utcoffset() is None or recorded.utcoffset() is None:
        raise ValueError("印占的记录钟时与物理时刻必须带时区。")
    else:
        pass
    if utc_calendar(physical) != utc_calendar(recorded):
        raise ValueError(
            "印占须保留记录钟时所指的物理时刻；不能把真太阳钟标签重新当作民用出生时间。"
            "构建 AstroBirthInfo 时使用 preserve_instant=true。"
        )
    else:
        pass


def clock_context(
    birth: AstroBirthInfo, display_context: dict[str, Any] | None = None
) -> dict[str, Any]:
    require_recorded_instant(birth)
    recorded = birth.recorded_datetime or birth.local_datetime
    conversion = birth.clock_conversion
    return {
        "rule_id": RULE_ID,
        "input_calendar": "proleptic_gregorian",
        "recorded_datetime": recorded.isoformat() if conversion is None else None,
        "input_clock_basis": conversion["input_clock_basis"] if conversion else "civil",
        "input_wall_datetime": (
            conversion["input_wall_datetime"]
            if conversion
            else recorded.replace(tzinfo=None).isoformat()
        ),
        "resolved_carrier_datetime": birth.local_datetime.isoformat(),
        "calculation_utc_datetime": birth.utc_isoformat,
        "birth_timezone": birth.timezone,
        "birth_timezone_role": (
            "UTC_carrier_for_solar_input" if conversion else "recorded_civil_zone"
        ),
        "input_clock_conversion": birth.clock_conversion,
        "physical_instant_shifted": False,
        "solar_display_requested": birth.applied_true_solar,
        "solar_display_status": (
            "not_requested"
            if not birth.applied_true_solar
            else "computed" if birth.solar_datetime is not None else "unavailable"
        ),
        "solar_wall_datetime": (
            birth.solar_datetime.replace(tzinfo=None).isoformat()
            if birth.solar_datetime is not None
            else None
        ),
        "solar_correction_minutes": birth.solar_correction_minutes,
        "solar_clock_scope": "wall label without timezone/offset; not another timestamp, birth date or analysis-date anchor",
        "solar_display_limitation": (
            "Derived from the nominal recorded instant under the current UT1/TT model; not measured Earth rotation or birth-clock accuracy. A label outside Python datetime's years is unavailable without moving that instant."
            if display_context is not None
            else "A requested label can be unavailable outside Python datetime's representable years, or absent in a manually supplied birth object; physical calculation remains on the recorded instant."
        ),
        "display_equation_of_time_method": (
            (
                "apparent_solar_hour_angle_shared_TT_model_UT1"
                if display_context is not None
                else "Swiss time_equ; UTC tag used as UT1 approximation"
            )
            if birth.applied_true_solar
            else None
        ),
        **({"solar_display_context": display_context} if display_context else {}),
        "calculation_basis": (
            "explicit input solar label converted by shared UT1/TT policy; no civil relocalization"
            if conversion
            else "recorded instant, then shared UTC/TT/model-UT1 conversion; solar display never rebases it"
        ),
        "time_scale_scope": "UTC-named carrier before1960 follows historical UT1 assumption; later offsets/future assumptions remain in time_scale_context. Solar display is not measured UT1 or certified clock precision.",
        "source_id": "swiss_ephemeris",
        "source_section": "9.2 UTC conversions; 9.4 mean versus apparent solar time",
        "policy_attribution": "FateBridge input/presentation separation, applying the manual's physical time-scale distinctions",
    }


def require_clock_policy(birth: AstroBirthInfo, ephemeris_policy: str) -> None:
    conversion = birth.clock_conversion
    if (
        ephemeris_policy == "require_data_files"
        and conversion
        and conversion["input_clock_basis"] == "local_apparent_solar"
        and conversion.get("solar_ephemeris_policy") != "require_data_files"
    ):
        raise ValueError(
            "Strict Jyotish requires the LAT birth clock to be resolved under require_data_files as well"
        )
    else:
        pass


def check_clock_sources(
    birth: AstroBirthInfo, native: dict[str, Any], ephemeris_policy: str
) -> dict[str, Any] | None:
    """Validate a derived birth epoch without rebasing or guessing its source."""
    conversion = birth.clock_conversion
    if conversion is None:
        return None
    else:
        pass
    from fatebridge.core.astro.birth_clock import resolve_solar_birth_clock

    session = current_source_session()
    assert session is not None
    key = (
        "jyotish_clock_replay",
        id(birth),
        birth.require_utc_datetime,
        birth.longitude,
        ephemeris_policy,
        json.dumps(conversion, sort_keys=True),
    )
    if key not in session.memo:
        wall = datetime.fromisoformat(conversion["input_wall_datetime"])
        basis = conversion["input_clock_basis"]
        if conversion.get("converted_utc") is not None and (
            datetime.fromisoformat(conversion["converted_utc"])
            != birth.require_utc_datetime
        ):
            raise EphemerisSourceError("birth_clock_source_mismatch")
        else:
            pass
        moment, replay = resolve_solar_birth_clock(
            wall, birth.longitude, basis, ephemeris_policy=ephemeris_policy
        )
        difference = (moment - birth.require_utc_datetime).total_seconds()
        # The original solver's JD roundtrip tolerance is not widened here.
        if abs(difference) > 0.0002:
            raise EphemerisSourceError("birth_clock_source_mismatch")
        else:
            pass
        original_library = conversion.get("swisseph_version")
        if original_library and original_library != replay["swisseph_version"]:
            raise EphemerisSourceError("birth_clock_source_mismatch")
        else:
            pass
        cohort = SunSourceCohort()
        original = conversion.get("solar_source_comparison", {}).get(
            "physical_ephemeris_sources", []
        )
        original_models = set(conversion.get("solar_ephemeris_models_observed", []))
        if not original_models and conversion.get("solar_ephemeris_model"):
            original_models.add(conversion["solar_ephemeris_model"])
        else:
            pass
        if basis == "local_apparent_solar":
            if original_models and original_models != set(
                replay["solar_ephemeris_models_observed"]
            ):
                raise EphemerisSourceError("birth_clock_source_mismatch")
            else:
                pass
            try:
                for source in [
                    *original,
                    *replay["solar_source_comparison"]["physical_ephemeris_sources"],
                ]:
                    cohort.add(source)
            except EphemerisSourceError as error:
                raise EphemerisSourceError("birth_clock_source_mismatch") from error
        else:
            pass
        session.memo[key] = {
            "cohort": cohort,
            "difference": difference,
            "original_identity_recorded": bool(original)
            and bool(original_library)
            and not any(s["has_unidentified_sources"] for s in original),
            "original_library_known": bool(original_library),
            "original_models": sorted(original_models),
        }
    else:
        pass
    checked = session.memo[key]
    is_apparent = conversion["input_clock_basis"] == "local_apparent_solar"
    cohort = checked["cohort"]
    if is_apparent:
        try:
            cohort.add(sun_source(native, native["by_factor"]["equatorial_Sun"]))
        except EphemerisSourceError as error:
            raise EphemerisSourceError("birth_clock_source_mismatch") from error
    else:
        pass
    return {
        "rule_id": "jyotish.birth_clock_source_coherence.v1",
        "status": (
            "replayed_LMT_mapping"
            if not is_apparent
            else (
                "compatible_observed_sun_contexts"
                if checked["original_identity_recorded"]
                else "original_sun_identity_incomplete"
            )
        ),
        "nominal_utc_replay_difference_seconds": checked["difference"],
        "physical_instant_shifted": False,
        "original_sun_identity_recorded": checked["original_identity_recorded"],
        "original_sun_models": checked["original_models"],
        "original_library_version_known": checked["original_library_known"],
        "has_unidentified_sources": any(
            s["has_unidentified_sources"] for s in cohort.sources
        ),
        "physical_ephemeris_sources": list(cohort.sources),
        "scope": "Original nominal clock conversion, same-label replay and native Sun contexts observed so far in this session. Replay cached per original birth/policy, not per sample. LMT has no Sun-position prerequisite. Legacy missing identities remain unknown. Same physical epoch is retained; 0.0002-second check is numerical, not clock accuracy. Delta-T/rotation inputs are separate from physical file identities; not an exclusive or atomic read-set proof.",
    }


@dataclass(frozen=True)
class BirthTimeGrid:
    samples: tuple[tuple[float, RecordedBirthSample], ...]
    nominal_index: int
    clock_interval: dict[str, object]


def birth_grid(
    birth: AstroBirthInfo, radius_minutes: float, ephemeris_policy: str
) -> BirthTimeGrid:
    """Use elapsed TT for the civil grid and preserve solved solar bounds."""
    radius = sampling_radius(radius_minutes)
    span = radius_minutes * 60.0
    conversion = birth.clock_conversion
    if conversion is None:
        nominal = civil_recorded_sample(birth.utc_calendar)
        count = max(1, math.ceil(2.0 * span / 30.0))
        # Endpoints share the accepted radius. The exact middle subdivision
        # is the nominal slot even when the floating formula would miss zero.
        shifts = {0.0: timedelta(), -span: -radius, span: radius}
        for index in range(1, count):
            if 2 * index == count:
                continue
            else:
                pass
            offset = -span + 2.0 * span * index / count
            shifts[offset] = timedelta(seconds=offset)
        offsets = sorted(shifts)
        return BirthTimeGrid(
            tuple(
                (offset, shift_civil_recorded_sample(nominal, shifts[offset]))
                for offset in offsets
            ),
            offsets.index(0.0),
            {},
        )
    else:
        pass

    assert birth.native_epoch is not None  # The solar input resolver owns it.
    wall = datetime.fromisoformat(conversion["input_wall_datetime"])
    try:
        lower_wall = wall - radius
        upper_wall = wall + radius
    except OverflowError as error:
        raise ValueError(
            "Solar input uncertainty extends outside supported datetime years; bounds are not clipped"
        ) from error
    bounds = [
        resolve_solar_epoch(
            w,
            birth.longitude,
            conversion["input_clock_basis"],
            ephemeris_policy=ephemeris_policy,
        )
        for w in (lower_wall, upper_wall)
    ]
    nominal = RecordedBirthSample(birth.native_epoch)
    lower, upper = (RecordedBirthSample(epoch) for epoch, _ in bounds)
    low, center, high = lower.tt.days, nominal.tt.days, upper.tt.days
    if not low <= center <= high:
        raise ValueError("Converted solar interval must contain its nominal instant")
    else:
        pass
    duration = high - low
    count = max(1, math.ceil(duration / Fraction(30, 86400)))
    samples = {low: lower, high: upper, center: nominal}
    for i in range(1, count):
        point = low + duration * i / count
        if point != center:
            samples[point] = RecordedBirthSample(
                PhysicalEpoch.from_tt(TTInstant(point))
            )
        else:
            pass
    ordered = sorted(samples)
    return BirthTimeGrid(
        tuple((float((point - center) * 86400), samples[point]) for point in ordered),
        ordered.index(center),
        {
            "input_clock_basis": conversion["input_clock_basis"],
            "requested_clock_radius_seconds": span,
            "input_wall_start": lower_wall.isoformat(),
            "input_wall_end": upper_wall.isoformat(),
            "calculation_utc_start": lower.epoch.utc_label,
            "calculation_utc_end": upper.epoch.utc_label,
            "endpoint_conversions": [receipt for _, receipt in bounds],
            "scope": "Physical TT interval from solved solar-wall endpoints. Retains solved TT and UT1; UTC is a label. Sample gaps are at most 30 SI seconds.",
        },
    )
