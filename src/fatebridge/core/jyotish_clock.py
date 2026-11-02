"""Keep a recorded civil instant separate from its apparent-solar clock label."""

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from fatebridge.core.astro.birth import AstroBirthInfo, require_resolved_birth_timezone
from fatebridge.core.astro.solar_sources import SunSourceCohort, sun_source
from fatebridge.core.astro.source_session import current_source_session
from fatebridge.utils.errors import EphemerisSourceError

RULE_ID = "jyotish.recorded_instant.v1"


def require_recorded_instant(birth: AstroBirthInfo) -> None:
    """Require a known clock basis and preserve its unchanged physical instant."""
    require_resolved_birth_timezone(birth.timezone_source)
    recorded = birth.recorded_datetime or birth.local_datetime
    if birth.require_utc_datetime.utcoffset() is None or recorded.utcoffset() is None:
        raise ValueError("印占的记录钟时与物理时刻必须带时区。")
    if birth.require_utc_datetime != recorded.astimezone(timezone.utc):
        raise ValueError(
            "印占须保留记录钟时所指的物理时刻；不能把真太阳钟标签重新当作民用出生时间。"
            "构建 AstroBirthInfo 时使用 preserve_instant=true。"
        )


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
        "calculation_utc_datetime": birth.require_utc_datetime.astimezone(
            timezone.utc
        ).isoformat(),
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


def check_clock_sources(
    birth: AstroBirthInfo, native: dict[str, Any], ephemeris_policy: str
) -> dict[str, Any] | None:
    """Validate a derived birth epoch without rebasing or guessing its source."""
    conversion = birth.clock_conversion
    if conversion is None:
        return None
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
        moment, replay = resolve_solar_birth_clock(
            wall, birth.longitude, basis, ephemeris_policy=ephemeris_policy
        )
        difference = (moment - birth.require_utc_datetime).total_seconds()
        # The original solver's JD roundtrip tolerance is not widened here.
        if abs(difference) > 0.0002:
            raise EphemerisSourceError("birth_clock_source_mismatch")
        original_library = conversion.get("swisseph_version")
        if original_library and original_library != replay["swisseph_version"]:
            raise EphemerisSourceError("birth_clock_source_mismatch")
        cohort = SunSourceCohort()
        original = conversion.get("solar_source_comparison", {}).get(
            "physical_ephemeris_sources", []
        )
        original_models = set(conversion.get("solar_ephemeris_models_observed", []))
        if not original_models and conversion.get("solar_ephemeris_model"):
            original_models.add(conversion["solar_ephemeris_model"])
        if basis == "local_apparent_solar":
            if original_models and original_models != set(
                replay["solar_ephemeris_models_observed"]
            ):
                raise EphemerisSourceError("birth_clock_source_mismatch")
            try:
                for source in [
                    *original,
                    *replay["solar_source_comparison"]["physical_ephemeris_sources"],
                ]:
                    cohort.add(source)
            except EphemerisSourceError as error:
                raise EphemerisSourceError("birth_clock_source_mismatch") from error
        session.memo[key] = {
            "cohort": cohort,
            "difference": difference,
            "original_identity_recorded": bool(original)
            and bool(original_library)
            and not any(s["has_unidentified_sources"] for s in original),
            "original_library_known": bool(original_library),
            "original_models": sorted(original_models),
        }
    checked = session.memo[key]
    is_apparent = conversion["input_clock_basis"] == "local_apparent_solar"
    cohort = checked["cohort"]
    if is_apparent:
        try:
            cohort.add(sun_source(native, native["by_factor"]["equatorial_Sun"]))
        except EphemerisSourceError as error:
            raise EphemerisSourceError("birth_clock_source_mismatch") from error
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


def birth_grid(
    birth: AstroBirthInfo, radius_minutes: float, ephemeris_policy: str
) -> tuple[list[float], dict[str, Any]]:
    """Preserve the civil grid; solar wall bounds are converted before sampling."""
    span = radius_minutes * 60.0
    if birth.clock_conversion is None:
        count = max(1, math.ceil(2.0 * span / 30.0))
        return (
            sorted({-span + 2.0 * span * i / count for i in range(count + 1)} | {0.0}),
            {},
        )
    from fatebridge.core.astro.birth_clock import resolve_solar_birth_clock

    conversion = birth.clock_conversion
    wall = datetime.fromisoformat(conversion["input_wall_datetime"])
    try:
        lower_wall = wall - timedelta(minutes=radius_minutes)
        upper_wall = wall + timedelta(minutes=radius_minutes)
    except OverflowError as error:
        raise ValueError(
            "Solar input uncertainty extends outside supported datetime years; bounds are not clipped"
        ) from error
    bounds = [
        resolve_solar_birth_clock(
            w,
            birth.longitude,
            conversion["input_clock_basis"],
            ephemeris_policy=ephemeris_policy,
        )
        for w in (lower_wall, upper_wall)
    ]
    origin = birth.require_utc_datetime.astimezone(timezone.utc)

    def ticks(moment: datetime) -> int:
        delta = moment - origin
        return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds

    low, high = (ticks(moment) for moment, _ in bounds)
    if low > 0 or high < 0:
        raise ValueError("Converted solar interval must contain its nominal instant")
    duration = high - low
    count = max(1, (duration + 29_999_999) // 30_000_000)
    points = sorted({low + duration * i // count for i in range(count + 1)} | {0})
    return [p / 1_000_000 for p in points], {
        "input_clock_basis": conversion["input_clock_basis"],
        "requested_clock_radius_seconds": span,
        "input_wall_start": lower_wall.isoformat(),
        "input_wall_end": upper_wall.isoformat(),
        "calculation_utc_start": bounds[0][0].isoformat(),
        "calculation_utc_end": bounds[1][0].isoformat(),
        "endpoint_conversions": [receipt for _, receipt in bounds],
        "scope": "converted recorded-clock endpoints, then max30-second physical UTC grid including nominal instant; no continuous-interval proof or birth-time rectification",
    }
