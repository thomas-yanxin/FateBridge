"""An unexpected COB bit cannot inherit default system-point semantics."""

import json
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.ephemeris import _swisseph_planet_state
from fatebridge.core.astro.native_coordinates import require_spherical_coordinates
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.solar_position import apparent_position_policy
from fatebridge.utils.errors import EphemerisSourceError
from tests.support.reference_data import verify_source_files

FIXTURE = Path(__file__).parents[1] / "data/astro/point_flag"
PROTOCOL = json.loads((FIXTURE / "protocol.json").read_text())


def test_flag_contract_and_expected_packets_are_frozen_before_candidate():
    verify_source_files(FIXTURE)
    assert PROTOCOL["source_constant"]["value"] == 1048576
    assert runtime.swe.FLG_CENTER_BODY == 1048576
    assert len(PROTOCOL["cases"]) == 48
    assert len({c["returned_flags"] for c in PROTOCOL["cases"]}) == 48
    assert not PROTOCOL["production_default_reference_point_changed"]


@pytest.mark.parametrize(
    "case", PROTOCOL["cases"], ids=lambda c: str(c["returned_flags"])
)
def test_spherical_contract_requires_the_default_reference_point(case):
    args = dict(
        native=runtime.swe,
        equatorial=case["equatorial"],
        sidereal=case["sidereal"],
    )
    if case["expected"] == "accepted":
        assert require_spherical_coordinates(
            PROTOCOL["coordinates"], case["returned_flags"], **args
        ) == tuple(PROTOCOL["coordinates"][:3])
    else:
        with pytest.raises(EphemerisSourceError) as caught:
            require_spherical_coordinates(
                PROTOCOL["coordinates"], case["returned_flags"], **args
            )
        assert caught.value.reason == "coordinate_contract_changed"


@pytest.mark.parametrize("equatorial", [False, True])
def test_actual_native_state_rejects_reference_point_flag_drift(
    equatorial, monkeypatch
):
    original = runtime.ephemeris_call
    swe = runtime.swe

    def changed(operation, *args, **kwargs):
        result = original(operation, *args, **kwargs)
        if (
            operation == "calc"
            and args[1] == swe.SATURN
            and bool(args[2] & swe.FLG_EQUATORIAL) == equatorial
        ):
            values, flags = result
            return values, flags | 1048576
        return result

    monkeypatch.setattr(runtime, "ephemeris_call", changed)
    with pytest.raises(EphemerisSourceError) as caught:
        _swisseph_planet_state("Saturn", julian_day_tt=2451545.0, correct_motion=False)
    assert caught.value.reason == "coordinate_contract_changed"


def test_solar_source_receipt_rejects_the_same_unrequested_point_override(monkeypatch):
    original = runtime.ephemeris_call
    swe = runtime.swe
    calls = []

    def changed(operation, *args, **kwargs):
        result = original(operation, *args, **kwargs)
        if operation == "calc" and args[1] == swe.SATURN:
            values, flags = result
            calls.append(flags)
            return values, flags | 1048576
        return result

    monkeypatch.setattr(runtime, "ephemeris_call", changed)
    with pytest.raises(EphemerisSourceError) as caught:
        apparent_position_policy(
            2451545.0, {"Saturn": "swieph"}, PhysicalEphemerisTrace()
        )
    assert calls and caught.value.reason == "coordinate_contract_changed"
