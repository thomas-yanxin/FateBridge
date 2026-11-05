"""A missing frame must never erase an available numerical comparison."""

import hashlib
import json
import math

import pytest

from scripts.astrodice.audit_astrodice_apparent_source import (
    FAIL,
    PASS,
    audit,
    collect_frames,
    project,
)


@pytest.mark.parametrize("lahiri_error", [False, True])
@pytest.mark.parametrize("delivered_arcsec", [0, 0.003])
def test_complete_audit_entry_keeps_delivered_rate_failure(
    tmp_path, monkeypatch, lahiri_error, delivered_arcsec
):
    """Exercise the audit entry; helper-only checks miss a misplaced callback."""
    import scripts.astrodice.audit_astrodice_apparent_source as grader
    from fatebridge.core.astro import ephemeris, physical_sources, runtime, zodiac

    identity = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    zero = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    kernel = tmp_path / "test-kernel.bin"
    kernel.write_bytes(b"synthetic kernel identity for audit orchestration")
    (tmp_path / "geometric-reference.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "kernel_path": kernel.name,
                        "kernel_sha256": hashlib.sha256(
                            kernel.read_bytes()
                        ).hexdigest(),
                    }
                ]
            }
        )
    )
    center = {"direction_icrf": ["1", "0", "0"], "derivative_per_day": ["0", "0", "0"]}
    reference = tmp_path / "reference.json"
    reference.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "id": "synthetic-entry-check",
                        "role": "test",
                        "body": "Mercury",
                        "date_tdb": "2000-01-01T12:00:00",
                        "native_numeric_argument": 2451545.0,
                        "window_index": 0,
                        "position_status": "qualified_under_declared_source_position_model",
                        "status": "qualified_under_declared_continuous_source_model",
                        "position_centers": [center],
                        "centers": [center],
                    }
                ]
            }
        )
    )
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", kernel.name)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    flags = (
        runtime.swe.FLG_JPLEPH
        | runtime.swe.FLG_SPEED
        | runtime.swe.FLG_XYZ
        | runtime.swe.FLG_J2000
        | runtime.swe.FLG_ICRS
        | runtime.swe.FLG_EQUATORIAL
        | runtime.swe.FLG_NONUT
    )
    monkeypatch.setattr(
        runtime, "ephemeris_call", lambda *args: ((1, 0, 0, 0, 0, 0), flags)
    )

    class SyntheticTrace:
        def observe(self, *args):
            pass

        def finish(self):
            return {"test_only": True}

    monkeypatch.setattr(physical_sources, "PhysicalEphemerisTrace", SyntheticTrace)

    def state(name, metadata):
        metadata.setdefault("complete_position_derivatives", {})["Mercury:" + name] = {
            "status": "applied",
            "method_id": "test-method",
        }
        return {"longitude_speed": delivered_arcsec / 3600}

    monkeypatch.setattr(
        ephemeris,
        "_swisseph_planet_state",
        lambda *args, motion_metadata, **kwargs: (
            state("tropical", motion_metadata),
            "jpl",
        ),
    )

    def lahiri(*args, motion_metadata, **kwargs):
        if lahiri_error:
            raise ValueError("Lahiri state unavailable")
        return {"Mercury": state("lahiri", motion_metadata)}

    monkeypatch.setattr(zodiac, "native_lahiri_positions", lahiri)
    monkeypatch.setattr(
        grader, "orientation_derivative", lambda *args: (identity, [zero, zero], {})
    )
    result = audit(
        tmp_path, tmp_path, reference, 0, expected_derivative_method_id="test-method"
    )
    assert result["layers"]["position"]["status"] == PASS, result["layers"]["position"]
    numeric_status = FAIL if delivered_arcsec else PASS
    expected_status = (
        FAIL if delivered_arcsec else "candidate_error" if lahiri_error else PASS
    )
    assert result["status"] == expected_status
    assert result["exit_code"] == (0 if expected_status == PASS else 1)
    frames = result["layers"]["rate"]["frames"]
    assert frames["tropical"]["status"] == numeric_status
    assert frames["lahiri"]["status"] == (
        "candidate_error" if lahiri_error else numeric_status
    )


def broken():
    raise ValueError("Independent frame failure")


def test_a_numeric_failure_survives_another_frames_state_error():
    calls = []

    def comparison(name, state):
        calls.append(name)
        return {"status": FAIL, "difference_arcsec_per_day": 0.003}

    result = collect_frames({"tropical": lambda: 1, "lahiri": broken}, comparison)
    assert result["status"] == FAIL
    assert result["frames"]["tropical"]["difference_arcsec_per_day"] == 0.003
    assert result["frames"]["lahiri"]["status"] == "candidate_error"
    assert calls == ["tropical"]


def test_one_frame_error_still_allows_the_other_comparison():
    result = collect_frames(
        {"tropical": broken, "lahiri": lambda: 1},
        lambda name, state: {"status": PASS, "rate": 0.5},
    )
    assert result["status"] == "candidate_error"
    assert result["frames"]["lahiri"] == {"status": PASS, "rate": 0.5}


def test_a_projection_error_does_not_replace_an_already_failed_frame():
    def compare(name, state):
        return {"status": FAIL, "rate": 1} if name == "tropical" else broken()

    result = collect_frames({"tropical": lambda: 1, "lahiri": lambda: 2}, compare)
    assert result["status"] == FAIL
    assert result["frames"]["lahiri"]["type"] == "ValueError"


def test_removing_a_declared_frame_cannot_turn_a_partial_audit_into_a_pass():
    with pytest.raises(ValueError, match="All declared"):
        collect_frames({"tropical": lambda: 1}, lambda name, state: {"status": PASS})


def test_display_reference_adds_source_motion_and_moving_frame_once():
    identity = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    rate, frame = 0.00073, 0.00091
    derivative = [[0, -frame, 0], [frame, 0, 0], [0, 0, 0]]
    center = {
        "direction_icrf": ["1", "0", "0"],
        "derivative_per_day": ["0", str(rate), "0"],
    }
    result = project(center, identity, [derivative, derivative])
    assert result["rate_arcsec_per_day"] == pytest.approx(
        (rate + frame) * 180 * 3600 / math.pi, abs=1e-12
    )
    assert result["frame_check_difference_arcsec_per_day"] == 0


def test_display_longitude_at_the_frame_pole_is_not_silently_divided_by_zero():
    identity = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    center = {"direction_icrf": ["0", "0", "1"], "derivative_per_day": ["1", "0", "0"]}
    with pytest.raises(ValueError, match="ill-conditioned"):
        project(center, identity, [identity, identity])
