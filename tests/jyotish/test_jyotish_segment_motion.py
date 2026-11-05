"""The original overlap epoch computes without changing its native state."""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro import motion_source_window as window
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.position_motion import complete_position_rate
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
from fatebridge.core.output_charts import CompletePositionMotion, SolarBranchGeometry
from fatebridge.utils.errors import EphemerisSourceError
from tests.jyotish.test_jyotish_sources import data18, restore_runtime  # noqa: F401

EPOCH = 2597651.3591456483  # Fixed original civil input's TT, not a neighbor.
REFERENCE = Path(__file__).parents[1] / "fixtures/jyotish-segment-reference.json"


def full_files(data18):
    import shutil

    root, directory = data18
    for name in ("sepl_24.se1", "semo_24.se1"):
        shutil.copy2(root / name, directory / name)
    e.configure_ephemeris_path(str(directory))
    return directory


def raw(planet, *, sidereal=False, warm=False):
    flags = e.swe.FLG_SWIEPH | e.swe.FLG_SPEED
    if sidereal:
        e.ephemeris_call("set_sid_mode", e.swe.SIDM_LAHIRI, 0, 0)
        flags |= e.swe.FLG_SIDEREAL
    if warm:
        e.ephemeris_call("calc", EPOCH + 0.75, PLANET_SWISSEPH_IDS[planet], flags)
    result, returned = e.ephemeris_call(
        "calc", EPOCH, PLANET_SWISSEPH_IDS[planet], flags
    )
    assert e.ephemeris_model_from_retflag(returned) == "swieph"
    return tuple(result)


@pytest.mark.parametrize("planet", ["Sun", "Mercury", "Venus", "Mars"])
@pytest.mark.parametrize("sidereal", [False, True])
@pytest.mark.parametrize("warm", [False, True])
def test_original_overlap_state_has_a_converged_complete_derivative(
    data18, planet, sidereal, warm
):
    full_files(data18)
    state = raw(planet, sidereal=sidereal, warm=warm)
    original = tuple(state)
    rate, policy = complete_position_rate(
        planet, EPOCH, state, "swieph", sidereal=sidereal
    )
    assert state == original
    assert rate is not None
    assert policy["status"] == "applied"
    assert policy["method_id"] == "fatebridge_complete_position_derivative_v8"
    assert policy["convergence_line_arcsec_per_day"] == 0.0002
    assert policy["step_difference_arcsec_per_day"] <= 0.0002
    source_side = policy["source_branch_motion"]
    if policy["selected_stencil"] == "center_file_homogeneous_side_degree6_ls13_ls25":
        assert source_side["center_file_replay"][
            "center_native_state_reproduced_exactly"
        ]
        assert (
            source_side["center_file_replay"]["displayed_native_position_changed"]
            is False
        )
        assert source_side["required_consecutive_levels"] == 3
        assert source_side["levels"][-1]["disagreement_arcsec_per_day"] <= 0.0002
        assert {x["sample_count"] for x in source_side["levels"][-1]["estimates"]} == {
            13,
            25,
        }
    CompletePositionMotion.model_validate(policy)


def probe(planet):
    state = raw(planet)
    trace = PhysicalEphemerisTrace()
    windows = window.observed_windows()
    assert windows is not None
    source = trace.observe("center", "swieph", record_factor=False)
    return window.CenterWindowProbe(
        planet, EPOCH, state, windows, source, trace, sidereal=False
    )


def test_replay_rejects_a_changed_center_instead_of_correcting_birth(
    data18, monkeypatch
):
    full_files(data18)
    subject = probe("Sun")
    original = subject._raw

    def shifted(at):
        state = list(original(at))
        state[0] += 1e-8
        return tuple(state)

    monkeypatch.setattr(subject, "_raw", shifted)
    with pytest.raises(EphemerisSourceError, match="step-convergence"):
        subject.value(0.0)


def test_source_window_does_not_hide_an_ambiguous_solar_mass_knot(data18, monkeypatch):
    full_files(data18)
    subject = probe("Mercury")
    monkeypatch.setattr(
        window, "solar_interpolation_branch", lambda *a, **k: {"cell": None}
    )
    assert subject.branch(0.0)["cell"] is None
    with pytest.raises(EphemerisSourceError):
        subject.value(0.0)


def test_auxiliary_context_must_match_center_file_fingerprints(data18, monkeypatch):
    full_files(data18)
    subject = probe("Sun")
    original = subject.trace.observe

    def changed(*args, **kwargs):
        value = original(*args, **kwargs)
        return {**value, "file_ids": ["different-source"]}

    monkeypatch.setattr(subject.trace, "observe", changed)
    assert subject.branch(0.0)["cell"] is None
    with pytest.raises(EphemerisSourceError):
        subject.value(0.0)


@pytest.mark.parametrize("label", ["arbitrary", "center_files_solar_cell_101"])
def test_public_file_cell_contract_rejects_unrecognized_labels(label):
    with pytest.raises(ValidationError):
        SolarBranchGeometry.model_validate({"cell": label})


def test_file_cell_contract_distinguishes_file_context_from_solar_radius_cell():
    value = SolarBranchGeometry.model_validate({"cell": "center_files_solar_direction"})
    assert value.cell == "center_files_solar_direction"
    assert SolarBranchGeometry.model_validate({"cell": 100}).cell == 100


def test_external_reference_is_sealed_and_does_not_import_the_candidate():
    import ast

    assert (
        hashlib.sha256(REFERENCE.read_bytes()).hexdigest()
        == "5b4328fdcd1903df9902d0f7c84d73fb2bcd9f1c64c0e082dc2be879b2270ac2"
    )
    reference = json.loads(REFERENCE.read_text())
    assert reference["candidate_imports"] is False
    assert reference["Swiss_imports"] is False
    assert reference["independent_synthetic_epochs"] == 1
    assert len(reference["rows"]) == 4
    for row in reference["rows"]:
        text = reference["raw_material"][row["raw_file"]]
        assert hashlib.sha256(text.encode()).hexdigest() == row["raw_sha256"]
        assert row["reference_converged"]
        assert row["reference_agreement_arcsec_per_day"] <= 0.0002
    generator = (
        REFERENCE.parents[2] / "scripts/jyotish/gen_jyotish_segment_reference.py"
    )
    for node in ast.walk(ast.parse(generator.read_text())):
        names = []
        if isinstance(node, ast.Import):
            names = [name.name for name in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        assert not any(
            name == "swisseph" or name.startswith("fatebridge") for name in names
        )


@pytest.mark.parametrize("planet", ["Sun", "Mercury", "Venus", "Mars"])
@pytest.mark.parametrize("warm", [False, True])
def test_complete_rates_match_frozen_independent_JPL_ERFA_reference(
    data18, planet, warm
):
    import math

    full_files(data18)
    state = raw(planet, warm=warm)
    rate, _ = complete_position_rate(planet, EPOCH, state, "swieph")
    reference = json.loads(REFERENCE.read_text())
    row = next(value for value in reference["rows"] if value["body"] == planet)
    assert abs(rate - row["reference_rates_degrees_per_day"][-1]) * 3600 <= 0.002
    assert (
        abs(math.remainder(state[0] - row["reference_longitude_degrees"], 360)) * 3600
        <= 2.0
    )
