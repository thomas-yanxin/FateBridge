"""Check Guolao motion against two fixed Horizons and ERFA reference cohorts."""

import math
from pathlib import Path
from typing import Literal

import pytest

from fatebridge.core import ephemeris_runtime as ephemeris
from fatebridge.core.guolao import guolao
from fatebridge.core.public_output import same_public_value
from scripts.guolao import audit_guolao_moshier_motion as moshier_reference
from scripts.guolao.audit_guolao_motion import evaluate, load_reference
from tests.support.transports import AS_OF, SPECS, three_surfaces
from tests.unit_test.fixtures.western_ephemeris import (
    birth,
    ephemeris_files,
    restore_configuration,
)

REFERENCE_ROOT = Path(__file__).resolve().parents[1] / "data/astro"
RATE_TOLERANCE_ARCSEC_PER_DAY = 0.002
Backend = Literal["swieph", "moshier"]


@pytest.fixture
def configure_backend(request, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def configure(backend: Backend) -> None:
        directory = (
            request.getfixturevalue("ephemeris_files")[1]
            if backend == "swieph"
            else tmp_path
        )
        monkeypatch.setenv("SE_EPHE_PATH", str(directory))
        monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
        ephemeris.swe.close()
        ephemeris.configure_ephemeris_path(str(directory))

    return configure


@pytest.mark.parametrize("backend", ["swieph", "moshier"])
def test_motion_against_fixed_reference_cohorts(
    backend: Backend, configure_backend
) -> None:
    configure_backend(backend)
    first = REFERENCE_ROOT / "guolao_motion"
    second = REFERENCE_ROOT / "guolao_moshier_motion"
    first_protocol, first_reference = load_reference(
        first / "protocol.json", first / "reference.json"
    )
    second_protocol, second_reference = load_reference(
        second / "protocol.json",
        second / "reference.json",
        protocol_sha256=moshier_reference.PROTOCOL_SHA256,
        reference_sha256=moshier_reference.REFERENCE_SHA256,
    )
    assert set(first_protocol["dates_tt"]).isdisjoint(second_protocol["dates_tt"])

    cohorts = [(second_protocol, second_reference, 52 if backend == "moshier" else 84)]
    if backend == "swieph":
        cohorts.append((first_protocol, first_reference, 84))
    for protocol, reference, expected_passes in cohorts:
        assert len(protocol["dates_tt"]) == 12
        assert len(protocol["targets"]) == 7
        assert protocol["display_longitude_speed_tolerance_arcsec_per_day"] == (
            RATE_TOLERANCE_ARCSEC_PER_DAY
        )
        report = evaluate(protocol, reference, backend=backend)
        rows = report["rows"]
        assert report["requested"] == len(rows) == 84
        assert len({(row["body"], row["date_tt"]) for row in rows}) == 84
        assert report["source_errors"] == report["unresolved_reference"] == 0
        assert {row["actual_model"] for row in rows} == {backend}
        assert report["passed"] == expected_passes
        if backend == "moshier":
            assert (
                sum(
                    abs(row["native_signed_residual_arcsec_per_day"])
                    <= RATE_TOLERANCE_ARCSEC_PER_DAY
                    for row in rows
                )
                == 27
            )

    other_backend: Backend = "moshier" if backend == "swieph" else "swieph"
    single_epoch = {**second_protocol, "dates_tt": second_protocol["dates_tt"][:1]}
    mismatch = evaluate(single_epoch, second_reference, backend=other_backend)
    assert mismatch["actual_models"] == [backend]
    assert mismatch["requested"] == mismatch["source_errors"] == 7
    assert mismatch["passed"] == 0


@pytest.mark.parametrize("backend", ["swieph", "moshier"])
def test_chart_motion_matches_source_and_converged_tt_rate(
    backend: Backend, configure_backend, tmp_path: Path, monkeypatch, capsys
) -> None:
    configure_backend(backend)
    result = three_surfaces(
        SPECS["astro_guolao"],
        {
            "birth_year": 2000,
            "birth_month": 1,
            "birth_day": 1,
            "birth_hour": 12,
            "birth_minute": 0,
            "birth_timezone": "UTC",
            "birth_longitude": 0,
            "birth_latitude": 0,
            "use_true_solar_time": False,
        },
        ["guolao.bodies", "guolao.profile"],
        AS_OF,
        tmp_path,
        monkeypatch,
        capsys,
    )["guolao"]
    raw = guolao.positions(birth())
    profile = result["profile"]
    assert profile["ephemeris_models"] == [backend]
    assert same_public_value(profile["longitude_motion"], raw["longitude_motion"])
    assert same_public_value(
        profile["ephemeris_provenance"], raw["ephemeris_provenance"]
    )
    bodies = {body["id"]: body for body in result["bodies"]}
    for name, state in raw["states"].items():
        body = bodies[name]
        assert body["longitude"] == state["longitude"]
        assert body["longitude_speed"] == state["longitude_speed"]
        assert body["longitude_speed_native"] == state["longitude_speed_native"]
        assert body["longitude_speed_reference_frame"] == "tropical_ecliptic_of_date"
        rates = []
        for step_days in (0.5, 0.25, 0.125):
            differences = []
            for offset in (-2, -1, 1, 2):
                coordinates, flags = ephemeris.ephemeris_call(
                    "calc",
                    raw["julian_day_tt"] + offset * step_days,
                    getattr(ephemeris.swe, name.upper()),
                    ephemeris.swe.FLG_SWIEPH | ephemeris.swe.FLG_SPEED,
                )
                assert ephemeris.ephemeris_model_from_retflag(flags) == backend
                differences.append(
                    math.remainder(coordinates[0] - state["longitude"], 360)
                )
            rates.append(
                math.fsum(w * delta for w, delta in zip((1, -8, 8, -1), differences))
                / (12 * step_days)
            )
        wide, coarse, fine = rates
        coarse_extrapolation = coarse + (coarse - wide) / 15
        fine_extrapolation = fine + (fine - coarse) / 15
        assert abs(fine_extrapolation - coarse_extrapolation) * 3600 < (
            RATE_TOLERANCE_ARCSEC_PER_DAY
        )
        assert abs(state["longitude_speed"] - fine_extrapolation) * 3600 < (
            RATE_TOLERANCE_ARCSEC_PER_DAY
        )
