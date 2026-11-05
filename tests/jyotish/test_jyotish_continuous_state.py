"""The auxiliary frame state restores the original center and source context."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro import jyotish_continuous_state as continuous
from fatebridge.core.astro import runtime
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.utils.errors import EphemerisSourceError
from tests.jyotish.test_jyotish_sources import restore_runtime  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = json.loads(
    (ROOT / "tests/fixtures/jyotish-continuous-state-reference-v1.json").read_text()
)
BINDING = json.loads(
    (ROOT / "tests/fixtures/jyotish-continuous-input-binding-v2.json").read_text()
)
assert (
    hashlib.sha256(
        (ROOT / "tests/fixtures/jyotish-continuous-input-binding-v2.json").read_bytes()
    ).hexdigest()
    == "8fcc67370a57d59d643db624a1f4a76ad49db8bc706d2aa0bdd9f8ade309a3dd"
)
assert (
    hashlib.sha256(
        (
            ROOT / "tests/fixtures/jyotish-continuous-state-reference-v1.json"
        ).read_bytes()
    ).hexdigest()
    == BINDING["original_reference_sha256"]
)
CURRENT_ROWS = {
    row["native_case_index"]: row
    for row in BINDING["rows"]
    if row["vector_rate_scale_rational"] == "1"
}
CURRENT_INPUTS = {row["native_case_index"]: row for row in BINDING["native_inputs"]}


def test_all518_apparent_input_states_and_original14_gate_scope(record_property):
    e.configure_ephemeris_path(str(ROOT / "ephe"))
    swe = runtime.swe
    swe.set_ephe_path(str(ROOT / "ephe"))
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
    rows = [
        r
        for r in REFERENCE["rows"]
        if r["mode"] == "apparent" and r["vector_rate_scale_rational"] == "1"
    ]
    assert len(rows) == 518
    failures = []
    legacy_failures = []
    native_position_differences = []
    trace = PhysicalEphemerisTrace()
    for row in rows:
        tt, planet = row["epoch_jd_tt"], row["body"]
        current = CURRENT_ROWS[row["native_case_index"]]
        bound = CURRENT_INPUTS[row["native_case_index"]]
        assert (tt, planet) == (current["epoch_jd_tt"], current["body"])
        native, flags = runtime.ephemeris_call(
            "calc",
            tt,
            getattr(swe, planet.upper()),
            swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL,
        )
        model = runtime.ephemeris_model_from_retflag(flags)
        value = continuous.continuous_state_evidence(
            planet, tt, native, flags, model, source_trace=trace
        )
        assert value["status"] == "partial"
        assert value["native_center_reproduced_exactly"] is True
        assert value["source_context_reproduced_exactly"] is True
        assert value["primary_D1_factors_changed"] is False
        assert value["complete_apparent_rate_certified"] is False
        assert value["physical_TT_clock_mapping_certified"] is False
        assert value["J2000_returned_flags"] == bound["returned_flags"]
        assert value["source_context"] == bound["source_context"]
        assert value["native_J2000_state"] == pytest.approx(
            bound["inertial_values"],
            rel=0,
            abs=BINDING["raw_inertial_component_line"],
        )
        if not value["native_position_reproduced_within_line"]:
            native_position_differences.append((tt, planet))
        actual = value["state"]["spherical"]
        expected = current["expected"]["spherical"]
        for key in ["longitude_rate_degrees_per_day", "latitude_rate_degrees_per_day"]:
            if abs(actual[key] - expected[key]) * 3600 > 1e-6:
                failures.append((tt, planet, key, actual[key], expected[key]))
        # Keep the old producer-input compatibility failure visible. The old
        # independent frame fixture and its acceptance line are unchanged.
        if (
            max(
                abs(actual[key] - row["expected"]["spherical"][key]) * 3600
                for key in [
                    "longitude_rate_degrees_per_day",
                    "latitude_rate_degrees_per_day",
                ]
            )
            > 1e-6
        ):
            legacy_failures.append([row["native_case_index"], tt, planet])
        for key in ["position", "velocity_per_TT_day"]:
            assert value["state"][key] == pytest.approx(
                current["expected"][key], rel=0, abs=1e-12
            )
    trace.finish()
    assert not failures, failures
    assert legacy_failures == BINDING["legacy_original_rate_gate"]["failed_case_ids"]
    assert BINDING["legacy_original_rate_gate"]["passed"] is False
    record_property("legacy_original_rate_gate_passed", False)
    record_property(
        "legacy_original_rate_gate_failed_case_ids", json.dumps(legacy_failures)
    )
    record_property("current_bound_frame_gate_passed", True)
    # This service uses apparent states only: seven of the original14
    # geometric/apparent J2000 discrepancies. It never regrades the other7.
    assert len(native_position_differences) == 7
    assert all(tt == 2451545.0 for tt, _ in native_position_differences)


@pytest.mark.native_engine_fault
@pytest.mark.parametrize(
    "fault", ["bad_flags", "bad_values", "wrong_backend", "failed_restore"]
)
def test_auxiliary_corruption_is_rejected_after_restoration(monkeypatch, fault):
    e.configure_ephemeris_path(str(ROOT / "ephe"))
    swe = runtime.swe
    swe.set_ephe_path(str(ROOT / "ephe"))
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
    original = runtime.ephemeris_call
    tt = 2451545.0
    native, flags = original(
        "calc", tt, swe.MOON, swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
    )
    restored = []

    def injected(name, *args, **kwargs):
        value = original(name, *args, **kwargs)
        if name == "calc" and args[2] & swe.FLG_XYZ:
            if fault == "bad_flags":
                return value[0], value[1] | swe.FLG_RADIANS
            if fault == "wrong_backend":
                return value[0], (value[1] & ~7) | swe.FLG_MOSEPH
            if fault == "bad_values":
                return (float("nan"), *value[0][1:]), value[1]
        elif name == "calc":
            restored.append(value)
            if fault == "failed_restore":
                return (value[0][0] + 0.1, *value[0][1:]), value[1]
        return value

    monkeypatch.setattr(runtime, "ephemeris_call", injected)
    with pytest.raises(EphemerisSourceError):
        continuous.continuous_state_evidence(
            "Moon", tt, native, flags, "swieph", source_trace=PhysicalEphemerisTrace()
        )
    assert restored and restored[-1] == (native, flags)
