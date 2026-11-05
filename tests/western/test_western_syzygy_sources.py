"""Preserve real source transitions and reject unrequested lunation frames."""

import json
from pathlib import Path

import pytest

from fatebridge.core.astro import classical, runtime
from fatebridge.utils.errors import EphemerisSourceError
from tests.support.native_syzygy_witness import NativeSourceWitness
from tests.support.syzygy_source_profiles import PROTOCOL as PROFILE_PROTOCOL
from tests.support.syzygy_source_profiles import (  # noqa: F401
    syzygy_profile_directories,
    syzygy_source_profile,
)

FIXTURE = Path(__file__).parents[1] / "data/astro/syzygy_source"
PROTOCOL = json.loads((FIXTURE / "protocol.json").read_text())
INPUTS = json.loads((FIXTURE / "inputs.json").read_text())


@pytest.mark.parametrize("index", range(len(INPUTS)))
@pytest.mark.parametrize(
    "syzygy_source_profile", ["recorded5", "full37", "empty0"], indirect=True
)
def test_every_source_context_matches_the_actual_native_call(
    index,
    syzygy_source_profile,  # noqa: F811 - pytest fixture dependency
):
    row = INPUTS[index]
    expected = next(
        r
        for r in PROFILE_PROTOCOL["case_outcomes"]
        if (r["profile"], r["kind"], r["index"])
        == (syzygy_source_profile, "source", index)
    )
    witness = NativeSourceWitness(runtime)
    with witness.observe():
        result = classical._prenatal_syzygy(
            row["jd_ut1"], julian_day_tt=row["jd_tt"], sidereal=row["sidereal"]
        )
    assert (result is None) == (expected["status"] == "no_result")
    if result is not None:
        witness.assert_matches(result)
        assert (
            result["ephemeris_source"]["models_by_body"] == expected["models_by_body"]
        )
    if result is not None:
        assert witness.entries
        assert result["ephemeris_source"]["absolute_accuracy_certified"] is False
        for context in result["ephemeris_source"]["sample_contexts"]:
            assert context["minimum_jd_tt"] <= context["maximum_jd_tt"]
            if context["model"] == "moshier":
                assert context["file_ids"] == []


@pytest.mark.parametrize("body", ["SUN", "MOON"])
@pytest.mark.parametrize("flag_name", PROTOCOL["frame_fault_names"])
def test_lunation_helper_rejects_unrequested_frames(body, flag_name, monkeypatch):
    original = runtime.ephemeris_call

    def changed(operation, *args, **kwargs):
        values, flags = original(operation, *args, **kwargs)
        return values, flags | getattr(runtime.swe, flag_name)

    monkeypatch.setattr(runtime, "ephemeris_call", changed)
    with pytest.raises(EphemerisSourceError, match="coordinate frame"):
        classical._luminary_lon_speed(2461045.0, getattr(runtime.swe, body))


@pytest.mark.parametrize("body", ["SUN", "MOON"])
@pytest.mark.parametrize("fault", PROTOCOL["motion_faults"])
def test_lunation_helper_rejects_missing_or_invalid_motion(body, fault, monkeypatch):
    original = runtime.ephemeris_call

    def changed(operation, *args, **kwargs):
        values, flags = original(operation, *args, **kwargs)
        values = list(values)
        if fault == "missing_speed_flag":
            flags &= ~runtime.swe.FLG_SPEED
        elif fault == "truncated_coordinates":
            values = values[:3]
        else:
            values[3] = float("nan" if fault == "nan_speed" else "inf")
        return values, flags

    monkeypatch.setattr(runtime, "ephemeris_call", changed)
    with pytest.raises(EphemerisSourceError):
        classical._luminary_lon_speed(2461045.0, getattr(runtime.swe, body))


@pytest.mark.parametrize("reason", ["coordinate_contract_changed", "changed_during"])
def test_optional_lunation_never_hides_a_source_integrity_error(reason, monkeypatch):
    def broken(*args, **kwargs):
        raise EphemerisSourceError(reason)

    monkeypatch.setattr(runtime, "ephemeris_call", broken)
    with pytest.raises(EphemerisSourceError) as error:
        classical._prenatal_syzygy(2461045.0, julian_day_tt=2461045.0)
    assert error.value.reason == reason


def test_lahiri_event_display_rejects_a_different_native_frame(monkeypatch):
    original = runtime.ephemeris_call
    changed = []

    def fault(operation, *args, **kwargs):
        result = original(operation, *args, **kwargs)
        if operation == "calc" and args[2] & runtime.swe.FLG_SIDEREAL:
            changed.append(args[0])
            return result[0], result[1] | runtime.swe.FLG_EQUATORIAL
        return result

    monkeypatch.setattr(runtime, "ephemeris_call", fault)
    with pytest.raises(EphemerisSourceError) as error:
        classical._prenatal_syzygy(2461045.0, julian_day_tt=2461045.0, sidereal=True)
    assert error.value.reason == "coordinate_contract_changed" and changed
