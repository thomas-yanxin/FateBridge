"""Rational circle oracle and existing D1 boundary failures, without new accuracy claims."""

import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro import sidereal_origin_motion as origin
from fatebridge.core.jyotish import positions
from fatebridge.core.jyotish_longitude_motion import node_motion
from fatebridge.utils.errors import EphemerisSourceError
from tests.test_astrodice_jpl import jpl  # noqa: F401
from tests.test_jyotish_longitude_motion import from_tt
from tests.test_jyotish_sources import restore_runtime  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PATH = ROOT / "tests/fixtures/lahiri-origin-circle-reference-v1.json"
REF = json.loads(REFERENCE_PATH.read_text())
BEFORE = json.loads(
    (ROOT / "tests/fixtures/lahiri-origin-pipeline-before-v1.json").read_text()
)
ORACLE = {(r["epoch_jd_tt"], r["body"]): r for r in REF["rows"]}


def test_reference_precedes_production_and_retains_all_rows():
    assert hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest() == (
        "ce64bf292eba5ec70cdbe60c3a97cd669bbef891aee128e188cfb2d0c293a8e6"
    )
    assert len(REF["rows"]) == 153
    assert REF["summary"]["wrap_rows"] == 45
    assert REF["summary"]["algebraic_failures"] == 0
    assert REF["summary"]["new_physical_reference_passes"] == 0
    assert len(BEFORE["rows"]) == 34


@pytest.mark.parametrize("row", REF["rows"])
def test_integer_correction_matches_prior_exact_fraction_oracle(row):
    correction, turns, raw, principal = origin.circular_origin_correction(
        row["origin_current"], row["origin_previous"]
    )
    assert correction == row["expected_correction_degrees_per_day"]
    assert turns == row["whole_turns"]
    assert raw - principal == turns * 360
    corrected = math.fsum((row["sidereal_native_speed"], correction))
    assert abs(corrected - row["expected_same_source_circular_speed"]) * 3600 <= 1e-6


@pytest.mark.parametrize(
    "current,previous",
    [(0.01, 359.99), (359.99, 0.01), (30.0, 30.1), (0.0, 0.0)],
)
def test_both_directions_and_nonboundary_angles_have_rational_winding(
    current, previous
):
    difference = Fraction.from_float(current) - Fraction.from_float(previous)
    expected = (difference + 180) % 360 - 180
    turns = int((difference - expected) / 360)
    value, actual_turns, _, _ = origin.circular_origin_correction(current, previous)
    assert actual_turns == turns
    assert value == float(turns * 360 / Fraction.from_float(0.001))


@pytest.mark.parametrize(
    "current,previous",
    [(float("nan"), 0), (0, float("inf")), (-1, 0), (0, 360), (180, 0)],
)
def test_invalid_and_antipodal_inputs_are_not_inferred(current, previous):
    with pytest.raises(EphemerisSourceError):
        origin.circular_origin_correction(current, previous)


@pytest.mark.parametrize("row", BEFORE["rows"])
def test_full_d1_preserves_positions_and_native_rates_but_repairs_winding(row):
    e.configure_ephemeris_path(str(ROOT / "ephe"))
    result = positions(
        from_tt(row["epoch_jd_tt"]),
        node_mode=row["node_mode"],
        ephemeris_policy="require_data_files",
    )
    assert result["julian_day_tt"] == row["epoch_jd_tt"]
    assert result["longitudes"] == row["longitudes"]
    states = result["physical_states"]
    for name, before in row["physical_states"].items():
        state = states[name]
        assert (
            state["longitude_speed_native_degrees_per_day"]
            == before["longitude_speed_native_degrees_per_day"]
        )
        body = (
            ("Mean Node" if row["node_mode"] == "mean" else "True Node")
            if name in {"Rahu", "Ketu"}
            else name
        )
        oracle = ORACLE[row["epoch_jd_tt"], body]
        context = state["longitude_motion_context"]
        policy = context["traditional_sidereal_origin_wrap"]
        assert policy["whole_turns_removed"] == oracle["whole_turns"]
        assert policy["center_origin_reproduced_exactly"] is True
        assert policy["complete_origin_derivative_certified"] is False
        assert policy["physical_TT_clock_mapping_certified"] is False
        if oracle["whole_turns"]:
            assert (
                context["corrections_degrees_per_day"][
                    "sidereal_origin_wrap_correction"
                ]
                == oracle["expected_correction_degrees_per_day"]
            )
            if name in {"Jupiter", "Saturn", "Rahu", "Ketu"}:
                assert (
                    abs(
                        state["longitude_speed_degrees_per_day"]
                        - oracle["expected_same_source_circular_speed"]
                    )
                    * 3600
                    <= 1e-6
                )
            elif name == "Moon":
                assert (
                    abs(
                        state["longitude_speed_degrees_per_day"]
                        - math.fsum(
                            (
                                before["longitude_speed_degrees_per_day"],
                                oracle["expected_correction_degrees_per_day"],
                            )
                        )
                    )
                    * 3600
                    <= 1e-6
                )
            else:
                # These four already used a complete-position stencil. The
                # new explicit term changes its remainder, not its target.
                assert (
                    abs(
                        state["longitude_speed_degrees_per_day"]
                        - before["longitude_speed_degrees_per_day"]
                    )
                    * 3600
                    <= 1e-6
                )
        else:
            assert (
                state["longitude_speed_degrees_per_day"]
                == before["longitude_speed_degrees_per_day"]
            )
        if name in {"Jupiter", "Saturn", "Rahu", "Ketu"}:
            expected = oracle["expected_same_source_circular_speed"]
            assert state["motion"] == (
                "retrograde"
                if expected < 0
                else "direct" if expected > 0 else "stationary"
            )
    assert (
        states["Ketu"]["longitude_speed_degrees_per_day"]
        == states["Rahu"]["longitude_speed_degrees_per_day"]
    )
    assert (
        states["Ketu"]["longitude_speed_native_degrees_per_day"]
        == states["Rahu"]["longitude_speed_native_degrees_per_day"]
    )


@pytest.mark.parametrize("mode", ["mean", "true"])
def test_antipode_keeps_original_native_rate_without_applying_repair_twice(mode):
    policy = {"status": "applied", "longitude_speed_correction": -360000.0}
    rahu = node_motion(1825399.072, 359999.95, mode, origin_wrap_policy=policy)
    ketu = node_motion(
        1825399.072, 359999.95, mode, antipode=True, origin_wrap_policy=policy
    )
    assert (
        rahu["longitude_speed_degrees_per_day"]
        == ketu["longitude_speed_degrees_per_day"]
    )
    assert ketu["longitude_speed_native_degrees_per_day"] == 359999.95


@pytest.mark.parametrize("fault", ["flags", "nan", "malformed", "restore", "path"])
def test_origin_integrity_faults_propagate_without_filling_zero(fault, monkeypatch):
    e.configure_ephemeris_path(str(ROOT / "ephe"))
    e.ephemeris_call("set_sid_mode", e.swe.SIDM_LAHIRI, 0, 0)
    original = origin.runtime.ephemeris_call
    calls = 0

    def changed(operation, *args, **kwargs):
        nonlocal calls
        value = original(operation, *args, **kwargs)
        if operation != "get_ayanamsa_ex":
            return value
        calls += 1
        if fault == "flags":
            return value[0] & ~e.swe.FLG_NONUT, value[1]
        if fault == "nan":
            return value[0], float("nan")
        if fault == "malformed":
            return ()
        if fault == "restore" and calls == 3:
            return value[0], (value[1] + 0.01) % 360
        if fault == "path" and calls == 2:
            e.configure_ephemeris_path(str(ROOT / "ephe-does-not-exist"))
        return value

    monkeypatch.setattr(origin.runtime, "ephemeris_call", changed)
    context = {}
    with pytest.raises(EphemerisSourceError):
        origin.traditional_lahiri_origin_wrap(1825399.072, context)
    assert "traditional_sidereal_origin_wrap" not in context


def test_unverified_binding_retains_unqualified_status(monkeypatch):
    monkeypatch.setattr(origin, "binding_distribution_version", lambda *args: "0.0")
    context = {}
    assert origin.traditional_lahiri_origin_wrap(1825399.072, context) is None
    assert context["traditional_sidereal_origin_wrap"]["status"] == "not_applied"


def test_auxiliary_position_gap_retains_the_valid_origin_repair(monkeypatch):
    from fatebridge.core.astro import longitude_motion as shared
    from fatebridge.core.astro.position_motion import AuxiliaryPositionModelChange
    from fatebridge.core.astro.source_session import source_session
    from fatebridge.core.compressed_ephemeris import audit_compressed_endpoints
    from fatebridge.core.jyotish_longitude_motion import longitude_motion

    e.configure_ephemeris_path(str(ROOT / "ephe"))
    row = next(
        r for r in REF["rows"] if r["body"] == "Sun" and r["offset_seconds"] == 30
    )
    epoch = row["epoch_jd_tt"]

    def missing(*args, **kwargs):
        raise AuxiliaryPositionModelChange(epoch + 0.1, "swieph", "moshier")

    monkeypatch.setattr(shared, "complete_position_rate", missing)
    with audit_compressed_endpoints(), source_session() as session:
        e.ephemeris_call("set_sid_mode", e.swe.SIDM_LAHIRI, 0, 0)
        values, flags = e.ephemeris_call(
            "calc",
            epoch,
            e.swe.SUN,
            e.swe.FLG_SWIEPH | e.swe.FLG_SPEED | e.swe.FLG_SIDEREAL,
        )
        assert e.ephemeris_model_from_retflag(flags) == "swieph"
        result = longitude_motion(
            "Sun", epoch, values, "swieph", source_trace=session.trace
        )
    context = result["longitude_motion_context"]
    assert (
        context["complete_position_derivative"]["reason"]
        == "auxiliary_sample_backend_changed"
    )
    assert (
        context["rate_basis"] == "native_with_traditional_sidereal_origin_wrap_removed"
    )
    assert result["longitude_speed_native_degrees_per_day"] == values[3]
    assert (
        abs(
            result["longitude_speed_degrees_per_day"]
            - row["expected_same_source_circular_speed"]
        )
        * 3600
        <= 1e-6
    )


def test_jpl_origin_uses_the_selected_return_flag_without_claiming_vector_evidence(jpl):
    e.ephemeris_call("set_sid_mode", e.swe.SIDM_LAHIRI, 0, 0)
    context = {}
    assert origin.traditional_lahiri_origin_wrap(2451545.0, context) == 0
    policy = context["traditional_sidereal_origin_wrap"]
    assert policy["status"] == "not_needed"
    assert policy["requested_origin_flags"] == e.swe.FLG_JPLEPH | e.swe.FLG_NONUT
    assert policy["current_returned_flags"] == policy["requested_origin_flags"]


def test_shared_motion_schema_and_numeric_text_use_the_repaired_sign():
    from fatebridge.core.astro.longitude_motion import corrected_longitude_motion
    from fatebridge.core.astro.native_motion import context_motion
    from fatebridge.core.local_techniques.otherbu import _motion_snapshot_line
    from fatebridge.core.output_astrodice import DiceLongitudeMotion
    from fatebridge.core.output_charts import LongitudeMotionPolicy

    e.configure_ephemeris_path(str(ROOT / "ephe"))
    row = next(
        r for r in REF["rows"] if r["body"] == "Saturn" and r["offset_seconds"] == 30
    )
    metadata = {}
    with e.preserve_ephemeris_path():
        e.ephemeris_call("set_sid_mode", e.swe.SIDM_LAHIRI, 0, 0)
        coordinates, flags = e.ephemeris_call(
            "calc",
            row["epoch_jd_tt"],
            e.swe.SATURN,
            e.swe.FLG_SWIEPH | e.swe.FLG_SPEED | e.swe.FLG_SIDEREAL,
        )
        values = corrected_longitude_motion(
            "Saturn",
            row["epoch_jd_tt"],
            coordinates,
            "swieph",
            sidereal=True,
            context=metadata,
        )
        again, flags_again = e.ephemeris_call(
            "calc",
            row["epoch_jd_tt"],
            e.swe.SATURN,
            e.swe.FLG_SWIEPH | e.swe.FLG_SPEED | e.swe.FLG_SIDEREAL,
        )
        assert tuple(again) == tuple(coordinates) and flags_again == flags
    motion = context_motion(
        "Saturn",
        {"Saturn": values["longitude_speed"]},
        {"Saturn": "swieph"},
        "lahiri_sidereal_ecliptic_of_date",
        values,
    )
    assert motion["direction"] == "retrograde"
    typed = DiceLongitudeMotion.model_validate(motion).model_dump(exclude_none=True)
    assert typed["sidereal_origin_wrap_correction"] == -360000
    policy = LongitudeMotionPolicy.model_validate(metadata).model_dump(
        exclude_none=True
    )
    assert (
        policy["traditional_sidereal_origin_wrap"]
        == metadata["traditional_sidereal_origin_wrap"]
    )
    text = _motion_snapshot_line({"id": "Saturn", "motion": motion})
    assert "逆行" in text and "整圈差分修正 -360000.0 度/日" in text
    assert f"原生日速 {coordinates[3]} 度/日" in text
