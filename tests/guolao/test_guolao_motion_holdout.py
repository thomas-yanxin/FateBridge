"""New fixed-date source-frozen holdout, kept separate from development data."""

import json
import math
import sys
from pathlib import Path
from typing import Literal

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core import guolao
from fatebridge.core.astro.moshier_motion import METHOD_ID as MOSHIER_MOTION_METHOD_ID
from fatebridge.core.public_output import same_public_value
from fatebridge.services.tool_catalog import CATALOG
from scripts.guolao.audit_guolao_motion import evaluate, load_reference, main
from tests.fixtures.surface_payloads import astro_payload
from tests.support.transports import AS_OF, three_surfaces
from tests.western import test_other_chart_physical_sources as shared_sources

ephemeris_files = shared_sources.ephemeris_files
restore_configuration = shared_sources.restore_configuration
ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/data/astro/guolao_motion/protocol.json"
REFERENCE = ROOT / "tests/data/astro/guolao_motion/reference.json"


def test_holdout_keeps_predeclared_epochs_and_reference_uncertainty():
    protocol, reference = load_reference(PROTOCOL, REFERENCE)
    assert len(protocol["dates_tt"]) == 12
    assert len(protocol["targets"]) == 7
    assert reference["forbidden_implementation_imports"] == []
    assert reference["versions"] == {"pyerfa": "2.0.1.5", "numpy": "2.5.4"}
    for target in reference["references"]:
        for row in target["rows"]:
            assert row["status"] == "available"
            assert row["missing_probe_epochs"] == []
            assert row["stencil_difference_arcsec_per_day"] <= 0.002
            assert row["frame_step_difference_arcsec_per_day"] <= 0.002


def test_actual_guolao_seven_body_holdout_preserves_the_fixed_line(ephemeris_files):
    _, path = ephemeris_files
    e.swe.close()
    e.configure_ephemeris_path(str(path))
    protocol, reference = load_reference(PROTOCOL, REFERENCE)
    report = evaluate(protocol, reference, backend="swieph")
    assert report["requested_backend"] == "swieph"
    assert report["actual_models"] == ["swieph"]
    assert len(report["physical_ephemeris_sources"]) == 12
    assert report["requested"] == len(report["rows"]) == 84
    assert report["source_errors"] == report["unresolved_reference"] == 0
    assert report["passed"] == 84
    assert report["numerical_subset_checks_passed"]
    assert {row["actual_model"] for row in report["rows"]} == {"swieph"}
    assert not report["authority_certified"]
    assert not report["all_four_objectives_validated"]


def test_moshier_uses_own_position_derivative_without_swiss_light_time(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    e.swe.close()
    e.configure_ephemeris_path(str(tmp_path))
    raw = guolao.positions(shared_sources.birth(), observer_geometry=False)
    assert raw["models"] == ["moshier"]
    assert "longitude_speed_light_time_correction" not in raw["states"]["Moon"]
    for name in guolao.CN:
        assert "longitude_speed_position_derivative_correction" in raw["states"][name]
    assert (
        raw["longitude_motion"]["lunar_light_time"]["reason"]
        == "unsupported_physical_model"
    )
    assert all(
        value["status"] == "applied" and value["method_id"] == MOSHIER_MOTION_METHOD_ID
        for value in raw["longitude_motion"]["complete_position_derivatives"].values()
    )


@pytest.mark.parametrize("backend", ["swieph", "moshier"])
def test_audit_rejects_wrong_actual_backend(
    ephemeris_files: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    backend: Literal["swieph", "moshier"],
) -> None:
    """A Moshier-labelled audit previously accepted Swiss results and vice versa."""
    _, physical_path = ephemeris_files
    selected_path = physical_path if backend == "swieph" else tmp_path
    monkeypatch.setenv("SE_EPHE_PATH", str(selected_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    e.swe.close()
    e.configure_ephemeris_path(str(selected_path))
    protocol, reference = load_reference(PROTOCOL, REFERENCE)
    protocol = {**protocol, "dates_tt": protocol["dates_tt"][:1]}
    opposite_backend: Literal["swieph", "moshier"] = (
        "moshier" if backend == "swieph" else "swieph"
    )
    report = evaluate(protocol, reference, backend=opposite_backend)
    assert report["actual_models"] == [backend]
    assert report["requested"] == report["source_errors"] == 7
    assert report["passed"] == 0
    assert report["unresolved_reference"] == 0
    assert all("signed_residual_arcsec_per_day" in row for row in report["rows"])
    assert not report["numerical_subset_checks_passed"]


@pytest.mark.parametrize("backend", ["swieph", "moshier"])
def test_guolao_chart_delivers_the_same_actual_motion_source_on_three_surfaces(
    ephemeris_files: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    backend: Literal["swieph", "moshier"],
) -> None:
    """Published motion must match its source and a converged TT derivative."""
    _, physical_path = ephemeris_files
    selected_path = physical_path if backend == "swieph" else tmp_path
    monkeypatch.setenv("SE_EPHE_PATH", str(selected_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    e.swe.close()
    e.configure_ephemeris_path(str(selected_path))
    payload = {
        **astro_payload(),
        "birth_year": 2000,
        "birth_month": 1,
        "birth_day": 1,
        "birth_hour": 12,
        "birth_minute": 0,
        "birth_timezone": "UTC",
        "birth_longitude": 0,
        "birth_latitude": 0,
        "use_true_solar_time": False,
    }
    spec = next(spec for spec in CATALOG if spec.key == "astro_guolao")
    result = three_surfaces(
        spec,
        payload,
        ["guolao.bodies", "guolao.profile"],
        AS_OF,
        tmp_path,
        monkeypatch,
        capsys,
    )
    raw = json.loads(json.dumps(guolao.positions(shared_sources.birth())))
    (tmp_path / "native.json").write_text(
        json.dumps(raw, sort_keys=True, indent=2, allow_nan=False), encoding="utf-8"
    )
    profile = result["guolao"]["profile"]
    assert profile["ephemeris_models"] == [backend]
    assert same_public_value(profile["longitude_motion"], raw["longitude_motion"])
    assert same_public_value(
        profile["ephemeris_provenance"], raw["ephemeris_provenance"]
    )
    bodies = {body["id"]: body for body in result["guolao"]["bodies"]}
    for name, state in raw["states"].items():
        assert bodies[name]["longitude"] == state["longitude"]
        assert bodies[name]["longitude_speed"] == state["longitude_speed"]
        assert bodies[name]["longitude_speed_native"] == state["longitude_speed_native"]
        derivative_rates_degrees_per_day = []
        for step_days in (0.5, 0.25, 0.125):
            differences_degrees = []
            for offset in (-2, -1, 1, 2):
                coordinates, returned_flags = e.ephemeris_call(
                    "calc",
                    raw["julian_day_tt"] + offset * step_days,
                    getattr(e.swe, name.upper()),
                    e.swe.FLG_SWIEPH | e.swe.FLG_SPEED,
                )
                assert e.ephemeris_model_from_retflag(returned_flags) == backend
                differences_degrees.append(
                    math.remainder(coordinates[0] - state["longitude"], 360)
                )
            derivative_rates_degrees_per_day.append(
                math.fsum(
                    weight * difference_degrees
                    for weight, difference_degrees in zip(
                        (1, -8, 8, -1), differences_degrees
                    )
                )
                / (12 * step_days)
            )
        (
            wide_rate_degrees_per_day,
            coarse_rate_degrees_per_day,
            fine_rate_degrees_per_day,
        ) = derivative_rates_degrees_per_day
        coarse_extrapolated_rate_degrees_per_day = (
            coarse_rate_degrees_per_day
            + (coarse_rate_degrees_per_day - wide_rate_degrees_per_day) / 15
        )
        extrapolated_rate_degrees_per_day = (
            fine_rate_degrees_per_day
            + (fine_rate_degrees_per_day - coarse_rate_degrees_per_day) / 15
        )
        assert (
            abs(
                extrapolated_rate_degrees_per_day
                - coarse_extrapolated_rate_degrees_per_day
            )
            * 3600
            < 0.002
        )
        assert (
            abs(state["longitude_speed"] - extrapolated_rate_degrees_per_day) * 3600
            < 0.002
        )
        assert (
            bodies[name]["longitude_speed_reference_frame"]
            == "tropical_ecliptic_of_date"
        )


def test_changed_reference_is_not_used_or_reported_as_a_numeric_failure(
    tmp_path, monkeypatch
):
    changed = tmp_path / "changed.json"
    changed.write_bytes(REFERENCE.read_bytes() + b"\n")
    output = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit",
            "--protocol",
            str(PROTOCOL),
            "--reference",
            str(changed),
            "--output",
            str(output),
        ],
    )
    monkeypatch.setattr(
        guolao,
        "positions",
        lambda *a, **k: pytest.fail("Do not use changed oracle bytes"),
    )
    assert main() == 2
    report = json.loads(output.read_text())
    assert "reference_validation_error" in report
    assert not report["numerical_subset_checks_passed"]
