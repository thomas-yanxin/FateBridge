"""Absent native time stays absent; a native backend still requires its TT."""

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.solar_position import apparent_position_policy
from fatebridge.utils.errors import EphemerisSourceError


def test_offline_geometry_policy_does_not_invent_a_tt_epoch(monkeypatch):
    monkeypatch.setattr(runtime, "swe", None)
    policy = apparent_position_policy(
        None,
        {"Mercury": "fatebridge_approximate_orbital_model"},
        PhysicalEphemerisTrace(),
    )
    assert policy["epoch_jd_tt"] is None
    assert policy["bodies"]["Mercury"]["status"] == "not_evaluated"
    assert policy["source_contexts"] == {}
    assert not policy["observational_accuracy_certified"]


def test_available_native_backend_rejects_an_unknown_tt():
    assert runtime.swe is not None
    with pytest.raises(EphemerisSourceError) as error:
        apparent_position_policy(None, {"Mercury": "swieph"}, PhysicalEphemerisTrace())
    assert error.value.reason == "coordinate_values_unavailable"
