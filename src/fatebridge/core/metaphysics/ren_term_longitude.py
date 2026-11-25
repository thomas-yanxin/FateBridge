"""Named solar crossings under their declared model, not an accuracy certificate."""

from __future__ import annotations

import json
import math
from fractions import Fraction
from typing import Any

from fatebridge.core import (
    aa1996_solar,
    analytic_solar,
    de440_solar,
    de441_solar,
    spk_solar,
    vsop2013_solar,
)
from fatebridge.core.almanac import (
    NATIVE_SOLAR_ROOT_MODEL_ID,
    SOLAR_TERM_LONGITUDES,
    SOLAR_TERM_NAMES,
)
from fatebridge.core.ephemeris_runtime import (
    ephemeris_call,
    lock_ephemeris_configuration,
    swe,
)
from fatebridge.core.native_solar_source import (
    native_solar_file_context,
    prime_swiss_solar_context,
    swiss_solar_context_required,
)
from fatebridge.core.solar_term_runtime import solar_term_cache_context
from fatebridge.utils.errors import EphemerisSourceError

TARGETS = dict(zip(SOLAR_TERM_NAMES, SOLAR_TERM_LONGITUDES))
_REASON = "ren_solar_term_longitude_inconsistent"


def _fail() -> EphemerisSourceError:
    return EphemerisSourceError(_REASON)


def _present_matches(observed: Any, expected: Any) -> bool:
    if isinstance(observed, dict) and isinstance(expected, dict):
        return all(
            key in expected and _present_matches(value, expected[key])
            for key, value in observed.items()
        )
    else:
        pass
    if isinstance(observed, list) and isinstance(expected, list):
        return len(observed) <= len(expected) and all(
            _present_matches(a, b) for a, b in zip(observed, expected)
        )
    else:
        pass
    return json.dumps(observed, sort_keys=True, allow_nan=False) == json.dumps(
        expected, sort_keys=True, allow_nan=False
    )


def _source(details: dict[str, Any], expected: dict[str, Any], complete: bool) -> None:
    observed = {key: details[key] for key in expected if key in details}
    compare = expected if complete else {key: expected[key] for key in observed}
    if not (
        _present_matches(observed, compare)
        if not complete
        else json.dumps(observed, sort_keys=True, allow_nan=False)
        == json.dumps(compare, sort_keys=True, allow_nan=False)
    ):
        raise _fail()
    else:
        pass


def _bracket(details: dict[str, Any], name: str) -> list[tuple[float, ...]]:
    representation = details["numerical_epoch_representation"]
    if representation == "explicit_ieee_float_tt_point":
        low, high = details["root_bracket_tt"]
        # Original scalar solvers finish on adjacent large-JD grid values.
        # This is solver localization, not a fitted timing-error tolerance.
        if not 0 < high - low <= max(math.ulp(low), math.ulp(high)):
            raise _fail()
        else:
            pass
        return [(low,), (high,)]
    else:
        pass
    if representation == "explicit_two_part_tt":
        low, high = details["root_bracket_tt_parts"]
        day, a = low
        other_day, b = high
        if day != other_day or day != math.floor(day):
            raise _fail()
        else:
            pass
        width = Fraction(b) - Fraction(a)
        index = SOLAR_TERM_NAMES.index(name)
        initial = 11 if index % 2 == 0 else 16
        maximum = Fraction(initial, 2**48) + 2 * max(
            Fraction(math.ulp(a)), Fraction(math.ulp(b))
        )
        if not 0 < width <= maximum:
            raise _fail()
        else:
            pass
        return [tuple(low), tuple(high)]
    else:
        pass
    raise _fail()


def _native(
    points: list[tuple[float, ...]],
    model: str,
    flags: list[int] | tuple[int, ...],
    library_version: str,
    details: dict[str, Any],
    complete: bool,
) -> list[float]:
    if swe is None:
        raise ModuleNotFoundError("swisseph is unavailable")
    else:
        pass
    expected_flag = {"jpl": 1, "swieph": 2, "moshier": 4}.get(model)
    if expected_flag is None or tuple(flags) != (expected_flag,):
        raise _fail()
    else:
        pass
    if library_version != str(getattr(swe, "version", "unknown")):
        raise _fail()
    else:
        pass
    native_model_id = details.get("model_id")
    if native_model_id != NATIVE_SOLAR_ROOT_MODEL_ID:
        raise _fail()
    else:
        pass
    expected = dict(
        model_id=native_model_id,
        ephemeris_model=model,
        ephemeris_retflags=[expected_flag],
        ephemeris_library_version=library_version,
        accuracy_certified=False,
    )
    expected.update(
        root_selection_policy="first_post_crossing_tt_float",
        selected_crossing_jd_tt=points[1][0],
    )
    _source(details, expected, complete)
    if any(len(point) != 1 for point in points):
        raise _fail()
    else:
        pass
    midpoint_tt = (points[0][0] + points[1][0]) / 2.0
    pin_source = model == "swieph" and swiss_solar_context_required(midpoint_tt)
    if model == "swieph":
        if pin_source and complete and "native_source_context" not in details:
            raise _fail()
        else:
            pass
        if not pin_source and "native_source_context" in details:
            raise _fail()
        else:
            pass
    else:
        pass
    with lock_ephemeris_configuration():
        before = solar_term_cache_context(swe, native_only=True)
        context = None
        if pin_source:
            primed, context = prime_swiss_solar_context(
                midpoint_tt,
                native=swe,
                invoke=ephemeris_call,
            )
            if primed[1] != expected_flag or context is None:
                raise _fail()
            else:
                pass
            if "native_source_context" in details:
                _source(details, {"native_source_context": context}, complete)
            else:
                pass
        else:
            pass
        values = []
        for point in points:
            vector, actual_flags = ephemeris_call(
                "calc", point[0], swe.SUN, expected_flag
            )
            if type(actual_flags) is not int or actual_flags != expected_flag:
                raise _fail()
            else:
                pass
            values.append(float(vector[0]))
            if context is not None and native_solar_file_context(swe) != context:
                raise EphemerisSourceError("solar_configuration_changed")
            else:
                pass
        if before != solar_term_cache_context(swe, native_only=True):
            raise EphemerisSourceError("solar_configuration_changed")
        else:
            pass
    return values


def validate_term_longitude(
    *,
    name: str | None,
    provider: str | None,
    model: str | None,
    flags: list[int] | tuple[int, ...] | None,
    library_version: str | None,
    details: dict[str, Any] | None,
    complete: bool,
) -> dict[str, Any] | None:
    """Reobserve the two endpoints using the actual declared source family.

    Point/civil numerical consistency is checked separately before this call.
    Sparse output compares co-present facts; omissions are not verified here.
    No reference crossing times or physical accuracy thresholds are fitted.
    """
    if name is not None and name not in TARGETS:
        raise _fail()
    else:
        pass
    if any(value is None for value in (name, provider, model, flags, details)):
        if complete:
            raise _fail()
        else:
            pass
        return None
    else:
        pass
    assert name is not None and model is not None and flags is not None
    assert details is not None
    representation = details.get("numerical_epoch_representation")
    bracket_key = (
        "root_bracket_tt_parts"
        if representation == "explicit_two_part_tt"
        else "root_bracket_tt"
    )
    if (
        representation is None
        or bracket_key not in details
        or "selected_crossing_jd_tt" not in details
    ):
        if complete:
            raise _fail()
        else:
            pass
        return None
    else:
        pass
    try:
        points = _bracket(details, name)
        target = TARGETS[name]
        if provider == "swisseph":
            if library_version is None:
                if complete:
                    raise _fail()
                else:
                    pass
                return None
            else:
                pass
            values = _native(points, model, flags, library_version, details, complete)
        elif provider == de441_solar.PROVIDER:
            if (
                model != de441_solar.MODEL_ID
                or flags
                or any(len(p) != 1 for p in points)
            ):
                raise _fail()
            else:
                pass
            expected = de441_solar.model_details()
            expected.update(
                root_selection_policy="first_post_crossing_tt_float",
                selected_crossing_jd_tt=points[1][0],
            )
            _source(details, expected, complete)
            values = [de441_solar.solar_longitude(p[0]) for p in points]
        elif provider == "fatebridge_analytic":
            if (
                model != analytic_solar.MODEL_ID
                or flags
                or any(len(p) != 1 for p in points)
            ):
                raise _fail()
            else:
                pass
            expected = analytic_solar.model_details(details["selected_crossing_jd_tt"])
            _source(details, expected, complete)
            values = [analytic_solar.solar_longitude(p[0]) for p in points]
            if expected != analytic_solar.model_details(
                details["selected_crossing_jd_tt"]
            ):
                raise EphemerisSourceError("solar_configuration_changed")
            else:
                pass
        elif provider == "jpl_de440":
            if (
                model not in {de440_solar.MODEL_ID, de440_solar.EXTENDED_MODEL_ID}
                or flags
            ):
                raise _fail()
            else:
                pass
            expected = de440_solar.source_receipt(model)
            _source(details, expected, complete)
            values = [
                (
                    de440_solar.solar_longitude_parts(*p, profile_id=model)
                    if len(p) == 2
                    else de440_solar.solar_longitude(p[0], profile_id=model)
                )
                for p in points
            ]
            if expected != de440_solar.source_receipt(model):
                raise EphemerisSourceError("solar_configuration_changed")
            else:
                pass
        elif provider == "vsop2013":
            if (
                model != vsop2013_solar.MODEL_ID
                or flags
                or any(len(p) != 1 for p in points)
            ):
                raise _fail()
            else:
                pass
            observations = vsop2013_solar.solar_longitudes_tt([p[0] for p in points])
            _source(details, observations["model"], complete)
            values = observations["longitudes"]
        elif provider == "moshier_aa1996":
            if (
                model != aa1996_solar.MODEL_ID
                or flags
                or any(len(p) != 1 for p in points)
            ):
                raise _fail()
            else:
                pass
            observations = aa1996_solar.solar_longitudes_tt([p[0] for p in points])
            _source(details, observations["model"], complete)
            values = observations["longitudes"]
        elif provider == "jpl_spk":
            if model != spk_solar.MODEL_ID or flags or any(len(p) != 1 for p in points):
                raise _fail()
            else:
                pass
            observations = spk_solar.solar_longitudes_tt([p[0] for p in points])
            _source(details, observations["model"], complete)
            values = observations["longitudes"]
        else:
            raise _fail()
        if len(values) != 2 or not all(math.isfinite(v) for v in values):
            raise _fail()
        else:
            pass
        if (
            provider == "swisseph"
            and details.get("model_id") != NATIVE_SOLAR_ROOT_MODEL_ID
        ):
            low, high = [(v % 360.0 - target + 540.0) % 360.0 - 180.0 for v in values]
        else:
            low, high = [math.remainder(v - target, 360) for v in values]
        if not low < 0 <= high or high - low >= 90:
            raise _fail()
        else:
            pass
        return {
            "term": name,
            "target_longitude_degrees": target,
            "provider": provider,
            "model": model,
            "tt_bracket_arguments": points,
            "observed_longitudes_degrees": values,
            "observed_residuals_degrees": [low, high],
            "forward_numerical_crossing": True,
            "physical_accuracy_certified": False,
        }
    except EphemerisSourceError:
        raise
    except (TypeError, ValueError, OverflowError, KeyError) as exc:
        raise _fail() from exc
