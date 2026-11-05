"""External projected directions, same-point identity, and retained controls."""

import os
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.ephemeris import _swisseph_planet_state
from fatebridge.core.astro.ephemeris_integrity import (
    load_ephemeris_manifest,
    verify_ephemeris_bytes,
)
from fatebridge.core.astro.iers_ut1 import use_ut1_source
from scripts.western.audit_western_tt_common_frame import (
    angular_distance,
    unit,
    validate_corpus,
)
from tests.western.test_western_tt_events import refuse_ut1


def test_complete_corpus_identity_and_mixed_point_controls_are_preserved():
    plan, reference = validate_corpus()
    assert plan["position_line_arcseconds"] == 0.02
    assert plan["native_reference_targets"]["Mars"] == 4
    assert plan["native_reference_targets"]["Jupiter"] == 5
    assert plan["native_reference_targets"]["Saturn"] == 6
    assert plan["body_control_targets"] == {
        "Mars_body": 499,
        "Jupiter_body": 599,
        "Saturn_body": 699,
    }
    assert (
        sum(
            len(t["rows"])
            for c in reference["cases"]
            for name, t in c["targets"].items()
            if name in plan["native_reference_targets"]
        )
        == 8078
    )
    assert (
        sum(
            len(t["rows"])
            for c in reference["cases"]
            for name, t in c["targets"].items()
            if name in plan["body_control_targets"]
        )
        == 3462
    )
    assert plan["known_development_epochs_not_blind"]
    assert (
        not plan["full_original_text_acceptance"] and plan["real_world_outcomes"] == 0
    )


@pytest.fixture
def pinned_ephemeris(monkeypatch):
    directory = Path(
        os.environ.get(
            "FATEBRIDGE_TEST_EPHE_DIR",
            str(Path(__file__).resolve().parents[2] / "ephe"),
        )
    )
    manifest = load_ephemeris_manifest()
    for name in ("sepl_18.se1", "semo_18.se1"):
        if not (directory / name).is_file():
            pytest.fail(
                "Pinned Swiss1800 segments required; set FATEBRIDGE_TEST_EPHE_DIR"
            )
        verify_ephemeris_bytes(name, (directory / name).read_bytes(), manifest)
    with runtime.preserve_ephemeris_path():
        monkeypatch.setenv("SE_EPHE_PATH", str(directory))
        yield


@pytest.mark.parametrize("case_id", ["0", "1"])
def test_actual_published_frame_at_sealed_daily_controls(
    case_id, pinned_ephemeris, monkeypatch
):
    plan, reference = validate_corpus()
    case = next(c for c in reference["cases"] if c["case_id"] == case_id)
    refuse_ut1(monkeypatch)
    with use_ut1_source("iers_c04"):
        for planet in plan["native_reference_targets"]:
            for sample in case["targets"][planet]["rows"][::144]:
                actual = _swisseph_planet_state(
                    planet, julian_day_tt=sample["tt"], correct_motion=False
                )
                assert actual is not None and actual[1] == "swieph"
                expected = sample["projections"][plan["primary_projection"]]
                error = angular_distance(
                    unit(actual[0]["longitude"], actual[0]["latitude"]), unit(*expected)
                )
                assert error <= plan["position_line_arcseconds"], (
                    planet,
                    sample["tt"],
                    error,
                )
