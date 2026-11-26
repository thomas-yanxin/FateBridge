"""Bind derived day meridians to the actual native grid and Sun observations.

These are exact same-run role/coherence checks, not an independent astronomical
oracle. No ephemeris call, coordinate fit or time-key substitution occurs here.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from typing import Any, Callable, Mapping, Sequence

from fatebridge.core.astro.reference_angles import reference_angle_basis
from fatebridge.core.astro.sensitivity_timing import (
    SpecialtySampleTime,
    SpecialtySampleTimes,
    sample_time_receipt,
)
from fatebridge.core.astro.solar_arc_state import (
    YEAR_DAYS,
    SolarArcSampleUnavailable,
    SolarArcState,
    SolarArcTimeRangeError,
    exact_solar_arc_timing,
    retained_solar_arc_timing,
)
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.utils.civil_time import utc_calendar
from fatebridge.utils.errors import EphemerisSourceError


def finite_number(value: object) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError("Day-meridian inputs must be finite numbers")
    return Fraction(value)


def _require(condition: bool) -> None:
    if not condition:
        raise ValueError("Day-meridian inputs are not coherent")


def _instant(value: Any) -> datetime:
    _require(isinstance(value, str))
    result = datetime.fromisoformat(value)
    _require(result.utcoffset() is not None)
    return result.astimezone(timezone.utc)


def _reference(definition: Any) -> str | None:
    _require(
        definition is None
        or (
            isinstance(definition, Mapping)
            and (not definition or isinstance(definition.get("status"), str))
        )
    )
    return reference_angle_basis(definition, "Midheaven")


def _validate(
    *,
    natal_upper_meridian: float,
    native_profile: Mapping[str, Any],
    native_factors: Sequence[Mapping[str, Any]],
    nominal_effective_utc: str,
    solar_state: SolarArcState,
    sun_observations: Sequence[Mapping[str, object]],
    sample_states: Sequence[SolarArcState | SolarArcSampleUnavailable],
    target: Mapping[str, Any],
    uncertainty: Mapping[str, Any],
    samples: Sequence[Mapping[str, Any]],
    supported_key_years: tuple[float, float],
    calculate: Callable[[float, float, float | Fraction, float], Mapping[str, float]],
    sample_times: SpecialtySampleTimes | None = None,
    nominal_clock: SpecialtySampleTime | None = None,
    nominal_birth_tt: TTInstant | None = None,
    analysis_tt: TTInstant | None = None,
) -> dict[str, Any]:
    mc = finite_number(natal_upper_meridian)
    _require(0 <= mc < 360)
    factors = [r for r in native_factors if r["id"] == "Midheaven"]
    _require(len(factors) == 1 and finite_number(factors[0]["longitude"]) == mc)
    birth_tt = finite_number(native_profile["julian_day_tt"])
    _require(birth_tt == finite_number(solar_state.birth_julian_day_tt))
    birth = _instant(nominal_effective_utc)
    _require(birth == solar_state.birth_effective_utc)
    analysis = solar_state.analysis_utc
    _require(analysis == _instant(target["analysis_utc"]))
    basis = _reference(native_profile.get("angle_definition"))
    _require(factors[0].get("coordinate_basis") == basis)
    if basis is not None:
        _require(
            factors[0].get("angle_definition") == native_profile.get("angle_definition")
        )
    year_days = finite_number(YEAR_DAYS)
    lower, upper = map(finite_number, supported_key_years)
    _require(year_days > 0 and lower <= upper)
    observations = sun_observations
    epochs = []
    for index, row in enumerate(observations):
        _require(isinstance(row["index"], int) and not isinstance(row["index"], bool))
        _require(row["index"] == index)
        epochs.append(finite_number(row["julian_day_tt"]))
        _require(0 <= finite_number(row["longitude"]) < 360)
    _require(len(epochs) == len(set(epochs)))

    def observe(index: Any, tt: Any, longitude: Any) -> None:
        _require(isinstance(index, int) and not isinstance(index, bool))
        _require(0 <= index < len(observations))
        row = observations[index]
        _require(isinstance(row["index"], int) and not isinstance(row["index"], bool))
        _require(row["index"] == index)
        _require(finite_number(row["julian_day_tt"]) == finite_number(tt))
        _require(finite_number(row["longitude"]) == finite_number(longitude))
        _require(0 <= finite_number(longitude) < 360)

    def key_years(moment: datetime) -> float:
        return ((analysis - moment).total_seconds() / 86400) / float(year_days)

    def direction(
        state: SolarArcState, tt: float, label: str, key: float, progressed_tt: float
    ) -> None:
        _require(lower <= finite_number(key) <= upper)
        _require(finite_number(state.key_years) == finite_number(key))
        _require(finite_number(state.birth_julian_day_tt) == finite_number(tt))
        _require(state.birth_label == label)
        _require(state.analysis_utc == analysis)
        _require(
            finite_number(state.progressed_julian_day_tt)
            == finite_number(progressed_tt)
        )
        indices = state.sun_observation_indices
        observe(indices[0], tt, state.natal_tropical_sun)
        observe(
            indices[1], state.progressed_julian_day_tt, state.progressed_tropical_sun
        )

    if nominal_clock is not None:
        assert analysis_tt is not None
        timing = retained_solar_arc_timing(nominal_clock, analysis, analysis_tt)
        nominal_key = timing.key_years
        nominal_progressed_tt = timing.progressed_julian_day_tt
    elif nominal_birth_tt is not None:
        timing = exact_solar_arc_timing(
            nominal_birth_tt, utc_calendar(birth).julian_day_exact(), analysis
        )
        nominal_key = timing.key_years
        nominal_progressed_tt = timing.progressed_julian_day_tt
    else:
        nominal_key = key_years(birth)
        nominal_progressed_tt = float(birth_tt) + nominal_key
    direction(
        solar_state,
        float(birth_tt),
        birth.isoformat(),
        nominal_key,
        nominal_progressed_tt,
    )
    observe(
        target["target_sun_observation_index"],
        target["target_julian_day_tt"],
        target["target_tropical_sun"],
    )
    target_is_birth = (
        analysis == birth
        if nominal_clock is None
        else analysis_tt == nominal_clock.effective.time.tt
    )
    if target_is_birth:
        _require(finite_number(target["target_julian_day_tt"]) == birth_tt)
    coordinate_keys = calculate(
        natal_upper_meridian,
        solar_state.natal_tropical_sun,
        solar_state.arc,
        target["target_tropical_sun"],
    ).keys()
    result: dict[str, Any] = {
        "status": "verified",
        "birth_julian_day_tt": float(birth_tt),
        "target_julian_day_tt": float(finite_number(target["target_julian_day_tt"])),
        "sample_count": None,
        "nominal_sample_index": None,
        "scope": "Exact supplied native/grid/clock/TT/observation-role coherence; not independent astronomy, atomic provenance or predictive validation",
    }
    if uncertainty["status"] != "sampled":
        _require(
            uncertainty["status"] == "not_assessed"
            and not samples
            and not sample_states
        )
        return result
    native = uncertainty["samples"]
    count = uncertainty["sample_count"]
    _require(isinstance(count, int) and not isinstance(count, bool) and count > 0)
    _require(len(native) == len(samples) == len(sample_states) == count)
    radius = finite_number(uncertainty["uncertainty_minutes"])
    _require(0 <= radius <= 120)
    delta = timedelta(minutes=float(radius))
    physical = sample_times.physical_grid if sample_times is not None else None
    if physical is None:
        offsets = [finite_number(r["offset_seconds"]) for r in native]
        _require(offsets == sorted(set(offsets)) and 0 in offsets)
        zero = offsets.index(Fraction(0))
        nominal = native[zero]
        recorded = _instant(nominal["recorded_utc"])
        start = _instant(native[0]["recorded_utc"])
        end = _instant(native[-1]["recorded_utc"])
        _require(start == _instant(uncertainty["recorded_interval_start_utc"]))
        _require(end == _instant(uncertainty["recorded_interval_end_utc"]))
        _require(
            finite_number(uncertainty["represented_radius_seconds"])
            == max(abs(v) for v in offsets)
        )
        if "input_clock_basis" not in uncertainty:
            _require(start == recorded - delta and end == recorded + delta)
        else:
            _require(
                finite_number(uncertainty["requested_clock_radius_seconds"])
                == finite_number(delta.total_seconds())
            )
            clock_start = datetime.fromisoformat(
                uncertainty["recorded_interval_start_clock"]
            )
            clock_end = datetime.fromisoformat(
                uncertainty["recorded_interval_end_clock"]
            )
            _require(clock_end - clock_start == delta * 2)
        gaps = [
            (_instant(b["recorded_utc"]) - _instant(a["recorded_utc"])).total_seconds()
            for a, b in zip(native, native[1:])
        ]
        _require(all(0 < value <= 30 for value in gaps))
        _require(
            finite_number(uncertainty["maximum_recorded_sample_gap_seconds"])
            == finite_number(max(gaps, default=0.0))
        )
    else:
        assert sample_times is not None
        _require(physical == uncertainty["recorded_physical_grid"])
        zero = sample_times.nominal_index
        sequence = [clock.recorded.tt.days for clock in sample_times.samples]
        _require(len(sequence) == count and sequence == sorted(set(sequence)))
        _require(all(0 < (b - a) * 86400 <= 30 for a, b in zip(sequence, sequence[1:])))
        _require(
            uncertainty["recorded_interval_start_utc"]
            == sample_times.samples[0].recorded.epoch.utc_label
        )
        _require(
            uncertainty["recorded_interval_end_utc"]
            == sample_times.samples[-1].recorded.epoch.utc_label
        )
        if "input_clock_basis" not in uncertainty:
            tt_radius = Fraction(delta // timedelta(microseconds=1), 86_400_000_000)
            _require(
                sequence[0] == sequence[zero] - tt_radius
                and sequence[-1] == sequence[zero] + tt_radius
            )
        else:
            _require(
                all(
                    uncertainty[key] == value
                    for key, value in sample_times.clock_interval.items()
                )
            )
        nominal = native[zero]
    _require(finite_number(nominal["julian_day_tt"]) == birth_tt)
    _require(finite_number(nominal["factor_longitudes"]["Midheaven"]) == mc)
    _require(nominal.get("angle_definition") == native_profile.get("angle_definition"))
    _require(nominal["effective_utc"] == birth.isoformat())
    for i, (raw, derived, state) in enumerate(zip(native, samples, sample_states)):
        _require(
            finite_number(raw["julian_day_tt"])
            == finite_number(derived["julian_day_tt"])
        )
        for key in ("offset_seconds", "recorded_utc", "effective_utc"):
            _require(raw[key] == derived[key])
        key_year: float | None
        progressed_tt: float | None = None
        if sample_times is not None:
            assert analysis_tt is not None
            clock = sample_times.samples[i]
            _require(raw["recorded_utc"] == clock.recorded.epoch.utc_label)
            _require(raw["effective_utc"] == clock.effective.utc_label)
            _require(raw["julian_day_tt"] == clock.effective.time.jd_tt)
            _require(raw["julian_day_ut1"] == clock.effective.time.jd_ut1)
            if physical is not None:
                offset = sample_times.label_offsets[i]
                _require(
                    raw["offset_seconds"]
                    == (offset.total_seconds() if offset is not None else None)
                )
                _require(raw["physical_timing"] == sample_time_receipt(clock))
            same_physical_time = analysis_tt == clock.effective.time.tt
            try:
                timing = retained_solar_arc_timing(clock, analysis, analysis_tt)
                key_year = timing.key_years
                progressed_tt = timing.progressed_julian_day_tt
                expected_error = None
            except SolarArcSampleUnavailable as error:
                expected_error = error
                key_year = (
                    error.key_years
                    if isinstance(error, SolarArcTimeRangeError)
                    else None
                )
        else:
            stamp = _instant(raw["recorded_utc"])
            _require(finite_number((stamp - recorded).total_seconds()) == offsets[i])
            instant = _instant(raw["effective_utc"])
            same_physical_time = analysis == instant
            key_year = key_years(instant)
            progressed_tt = float(raw["julian_day_tt"]) + key_year
            expected_error = (
                SolarArcTimeRangeError(key_year)
                if not lower <= finite_number(key_year) <= upper
                else None
            )
        if same_physical_time:
            _require(
                finite_number(target["target_julian_day_tt"])
                == finite_number(raw["julian_day_tt"])
            )
        _require(raw.get("angle_definition") == derived.get("angle_definition"))
        _reference(raw.get("angle_definition"))
        finite_number(raw["factor_longitudes"]["Midheaven"])
        if isinstance(state, SolarArcSampleUnavailable):
            _require(derived.get("status", "computed") == "unavailable" and i != zero)
            _require(expected_error is not None and type(state) is type(expected_error))
            _require(
                expected_error is not None
                and derived["reason_code"]
                == state.reason_code
                == expected_error.reason_code
            )
            if isinstance(state, SolarArcTimeRangeError):
                _require(
                    finite_number(derived["key_years"])
                    == finite_number(state.key_years)
                    == finite_number(key_year)
                )
                _require(
                    list(map(finite_number, derived["supported_key_years"]))
                    == [lower, upper]
                )
            else:
                _require(
                    "key_years" not in derived and "supported_key_years" not in derived
                )
            _require(not any(k in derived for k in coordinate_keys))
            _require("sun_observation_indices" not in derived)
            _require("progressed_julian_day_tt" not in derived)
            continue
        _require(
            expected_error is None
            and key_year is not None
            and progressed_tt is not None
        )
        assert key_year is not None and progressed_tt is not None
        _require(derived.get("status", "computed") == "computed")
        direction(
            state, raw["julian_day_tt"], raw["effective_utc"], key_year, progressed_tt
        )
        _require(
            finite_number(derived["progressed_julian_day_tt"])
            == finite_number(state.progressed_julian_day_tt)
        )
        _require(finite_number(derived["key_years"]) == finite_number(state.key_years))
        _require(
            derived["sun_observation_indices"] == list(state.sun_observation_indices)
        )
        expected = calculate(
            raw["factor_longitudes"]["Midheaven"],
            state.natal_tropical_sun,
            state.arc,
            target["target_tropical_sun"],
        )
        _require(
            all(
                finite_number(derived[k]) == finite_number(v)
                for k, v in expected.items()
            )
        )
        if i == zero:
            _require(state.arc == solar_state.arc)
            _require(
                state.natal_tropical_sun == solar_state.natal_tropical_sun
                and state.progressed_julian_day_tt
                == solar_state.progressed_julian_day_tt
            )
            _require(
                state.sun_observation_indices == solar_state.sun_observation_indices
            )
    result.update(sample_count=count, nominal_sample_index=zero)
    return result


def day_meridian_input_coherence(**kwargs: Any) -> dict[str, Any]:
    try:
        return _validate(**kwargs)
    except (
        KeyError,
        IndexError,
        TypeError,
        ValueError,
        OverflowError,
        AttributeError,
    ) as error:
        raise EphemerisSourceError("day_meridian_inputs") from error
