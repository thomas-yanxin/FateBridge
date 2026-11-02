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
from fatebridge.utils.errors import EphemerisSourceError


def finite_number(value: Any) -> Fraction:
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
    solar_profile: Mapping[str, Any],
    target: Mapping[str, Any],
    uncertainty: Mapping[str, Any],
    samples: Sequence[Mapping[str, Any]],
    supported_key_years: tuple[float, float],
    calculate: Callable[[float, float, float, float], Mapping[str, float]],
) -> dict[str, Any]:
    mc = finite_number(natal_upper_meridian)
    _require(0 <= mc < 360)
    factors = [r for r in native_factors if r["id"] == "Midheaven"]
    _require(len(factors) == 1 and finite_number(factors[0]["longitude"]) == mc)
    birth_tt = finite_number(native_profile["julian_day_tt"])
    _require(birth_tt == finite_number(solar_profile["birth_julian_day_tt"]))
    birth = _instant(nominal_effective_utc)
    _require(birth == _instant(solar_profile["birth_effective_utc"]))
    analysis = _instant(solar_profile["analysis_utc"])
    _require(analysis == _instant(target["analysis_utc"]))
    basis = _reference(native_profile.get("angle_definition"))
    _require(factors[0].get("coordinate_basis") == basis)
    if basis is not None:
        _require(
            factors[0].get("angle_definition") == native_profile.get("angle_definition")
        )
    year_days = finite_number(solar_profile["year_days"])
    lower, upper = map(finite_number, supported_key_years)
    _require(year_days > 0 and lower <= upper)
    observations = solar_profile["sun_ephemeris_source"]["observations"]
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

    def direction(row: Mapping[str, Any], tt: Any, instant: datetime) -> None:
        key = key_years(instant)
        _require(lower <= finite_number(key) <= upper)
        _require(finite_number(row["key_years"]) == finite_number(key))
        _require(
            finite_number(row["progressed_julian_day_tt"])
            == finite_number(float(tt) + key)
        )
        indices = row["sun_observation_indices"]
        _require(len(indices) == 2)
        observe(indices[0], tt, row["natal_tropical_sun"])
        progressed = observations[indices[1]]["longitude"]
        observe(indices[1], row["progressed_julian_day_tt"], progressed)
        arc = (
            finite_number(progressed) - finite_number(row["natal_tropical_sun"])
        ) % 360
        _require(finite_number(row["solar_arc_degrees"]) == finite_number(float(arc)))

    direction(solar_profile, float(birth_tt), birth)
    observe(
        target["target_sun_observation_index"],
        target["target_julian_day_tt"],
        target["target_tropical_sun"],
    )
    if analysis == birth:
        _require(finite_number(target["target_julian_day_tt"]) == birth_tt)
    coordinate_keys = calculate(
        natal_upper_meridian,
        solar_profile["natal_tropical_sun"],
        solar_profile["solar_arc_degrees"],
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
        _require(uncertainty["status"] == "not_assessed" and not samples)
        return result
    native = uncertainty["samples"]
    count = uncertainty["sample_count"]
    _require(isinstance(count, int) and not isinstance(count, bool) and count > 0)
    _require(len(native) == len(samples) == count)
    offsets = [finite_number(r["offset_seconds"]) for r in native]
    _require(offsets == sorted(set(offsets)) and 0 in offsets)
    zero = offsets.index(Fraction(0))
    nominal = native[zero]
    _require(finite_number(nominal["julian_day_tt"]) == birth_tt)
    _require(finite_number(nominal["factor_longitudes"]["Midheaven"]) == mc)
    _require(nominal.get("angle_definition") == native_profile.get("angle_definition"))
    _require(_instant(nominal["effective_utc"]) == birth)
    recorded = _instant(nominal["recorded_utc"])
    radius = finite_number(uncertainty["uncertainty_minutes"])
    _require(0 <= radius <= 120)
    start = _instant(native[0]["recorded_utc"])
    end = _instant(native[-1]["recorded_utc"])
    _require(start == _instant(uncertainty["recorded_interval_start_utc"]))
    _require(end == _instant(uncertainty["recorded_interval_end_utc"]))
    _require(
        finite_number(uncertainty["represented_radius_seconds"])
        == max(abs(v) for v in offsets)
    )
    delta = timedelta(minutes=float(radius))
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
        clock_end = datetime.fromisoformat(uncertainty["recorded_interval_end_clock"])
        _require(clock_end - clock_start == delta * 2)
    gaps = [
        (_instant(b["recorded_utc"]) - _instant(a["recorded_utc"])).total_seconds()
        for a, b in zip(native, native[1:])
    ]
    _require(all(0 < value <= 30 for value in gaps))
    represented_gap = max(
        (b["offset_seconds"] - a["offset_seconds"] for a, b in zip(native, native[1:])),
        default=0.0,
    )
    _require(
        finite_number(uncertainty["maximum_recorded_sample_gap_seconds"])
        == finite_number(represented_gap)
    )
    for i, (raw, derived) in enumerate(zip(native, samples)):
        for key in ("offset_seconds", "julian_day_tt"):
            _require(finite_number(raw[key]) == finite_number(derived[key]))
        for key in ("recorded_utc", "effective_utc"):
            _require(raw[key] == derived[key])
        stamp = _instant(raw["recorded_utc"])
        _require(finite_number((stamp - recorded).total_seconds()) == offsets[i])
        instant = _instant(raw["effective_utc"])
        if analysis == instant:
            _require(
                finite_number(target["target_julian_day_tt"])
                == finite_number(raw["julian_day_tt"])
            )
        _require(raw.get("angle_definition") == derived.get("angle_definition"))
        _reference(raw.get("angle_definition"))
        finite_number(raw["factor_longitudes"]["Midheaven"])
        if derived.get("status", "computed") == "unavailable":
            unavailable_key_years = finite_number(key_years(instant))
            _require(unavailable_key_years < lower or unavailable_key_years > upper)
            _require(i != zero)
            _require(finite_number(derived["key_years"]) == unavailable_key_years)
            _require(
                list(map(finite_number, derived["supported_key_years"]))
                == [lower, upper]
            )
            _require(
                derived["reason_code"]
                == (
                    "target_before_birth_time_sample"
                    if unavailable_key_years < lower
                    else "target_after_supported_key_range_for_sample"
                )
            )
            _require(not any(k in derived for k in coordinate_keys))
            _require("sun_observation_indices" not in derived)
            _require("progressed_julian_day_tt" not in derived)
            continue
        _require(derived.get("status", "computed") == "computed")
        direction(derived, raw["julian_day_tt"], instant)
        expected = calculate(
            raw["factor_longitudes"]["Midheaven"],
            derived["natal_tropical_sun"],
            derived["solar_arc_degrees"],
            target["target_tropical_sun"],
        )
        _require(
            all(
                finite_number(derived[k]) == finite_number(v)
                for k, v in expected.items()
            )
        )
        if i == zero:
            for key in (
                "solar_arc_degrees",
                "natal_tropical_sun",
                "progressed_julian_day_tt",
            ):
                _require(
                    finite_number(derived[key]) == finite_number(solar_profile[key])
                )
            _require(
                derived["sun_observation_indices"]
                == solar_profile["sun_observation_indices"]
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
