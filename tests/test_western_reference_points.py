"""Independent center controls and faithful native model/motion receipts."""

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core.horary_events import native_planetary_events
from fatebridge.core.horary_motion import native_lunar_contacts
from fatebridge.core.predictive.native_chart import build_native_subject

FIXTURES = Path(__file__).parent / "fixtures"
PRIMARY = "IAU2006/2000A_true_ecliptic_of_date"
SECONDARY = "IAU2006/2000B_true_ecliptic_of_date"


def native_subject(monkeypatch, tmp_path, zodiac="Tropic"):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    return build_native_subject(
        name="reference-point controls",
        local_datetime=datetime.fromisoformat("2022-10-23T04:10:00+00:00"),
        longitude=0,
        latitude=51.5,
        timezone_name="UTC",
        house_system="R",
        zodiac_type=zodiac,
    )


def test_frozen_initial_frame_and_center_controls_keep_their_own_identities():
    old = FIXTURES / "western-event-paths-horizons.json"
    frame_protocol = json.loads(
        (FIXTURES / "western-event-frames-protocol.json").read_text()
    )
    point_protocol = json.loads(
        (FIXTURES / "western-event-reference-points-protocol.json").read_text()
    )
    frame = FIXTURES / "western-event-frames-horizons.json"
    assert (
        hashlib.sha256(old.read_bytes()).hexdigest()
        == frame_protocol["initial_reference_sha256"]
    )
    assert (
        hashlib.sha256(frame.read_bytes()).hexdigest()
        == point_protocol["prior_common_frame_reference_sha256"]
    )
    controlled = json.loads(
        (FIXTURES / "western-event-reference-points-horizons.json").read_text()
    )
    assert (
        controlled["reference_point_control_protocol_sha256"]
        == hashlib.sha256(
            (FIXTURES / "western-event-reference-points-protocol.json").read_bytes()
        ).hexdigest()
    )
    assert not controlled["production_imports"] and not controlled["swiss_imports"]
    for c in controlled["cases"]:
        assert set(c["rows"]) == set(point_protocol["native_reference_targets"])
        for p, r in c["receipts"].items():
            assert (
                r["parameters"]["COMMAND"]
                == f"'{point_protocol['native_reference_targets'][p]}'"
            )
            assert (
                hashlib.sha256(r["raw_response_utf8"].encode()).hexdigest()
                == r["response_sha256"]
            )


def test_independent_saturn_control_separates_target_center_from_frame_effect():
    bodies = json.loads((FIXTURES / "western-event-frames-horizons.json").read_text())[
        "cases"
    ][1]
    bary = json.loads(
        (FIXTURES / "western-event-reference-points-horizons.json").read_text()
    )["cases"][1]

    def station(c, f):
        return next(
            e["julian_day_tt"]
            for e in c["frames"][f]["events"]
            if e["kind"] == "station" and e["bodies"] == ["Saturn"]
        )

    # No production value enters this test: the two independent target centers
    # differ by more than the original tolerance while frame variants differ
    # by only seconds. The old body-center reference remains a different test.
    assert abs(station(bodies, PRIMARY) - station(bary, PRIMARY)) * 86400 > 120
    assert abs(station(bodies, PRIMARY) - station(bodies, SECONDARY)) * 86400 < 5
    assert bodies["receipts"]["Saturn"]["parameters"]["COMMAND"] == "'699'"
    assert bary["receipts"]["Saturn"]["parameters"]["COMMAND"] == "'6'"


@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
def test_native_basis_excludes_analytical_node_from_physical_backend_summary(
    zodiac, monkeypatch, tmp_path
):
    subject = native_subject(monkeypatch, tmp_path, zodiac)
    b = subject.calculation_basis
    assert b["ephemeris_model"] == "moshier"
    p = b["ephemeris_reference_points"]
    assert set(p["system_barycenters"]) == {
        "Mars",
        "Jupiter",
        "Saturn",
        "Uranus",
        "Neptune",
        "Pluto",
    }
    assert set(p["body_centers"]) == {"Sun", "Moon", "Mercury", "Venus"}
    assert (
        p["theoretical_points"] == ["North Node"]
        and p["center_body_correction_applied"] is False
    )
    assert "North Node" not in b["physical_ephemeris_source"]["by_factor"]
    assert {
        v["model"] for v in b["physical_ephemeris_source"]["by_factor"].values()
    } == {"moshier"}
    assert b["longitude_motion"]["lunar_light_time"]["status"] == "not_applied"
    assert (
        b["longitude_motion"]["lunar_light_time"]["reason"]
        == "unsupported_physical_model"
    )
    assert math.isfinite(
        b["longitude_motion"]["display_longitude_offset_speed_degrees_per_day"]
    )


@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
def test_history_points_and_velocity_decomposition_match_same_subject(
    zodiac, monkeypatch, tmp_path
):
    subject = native_subject(monkeypatch, tmp_path, zodiac)
    events = native_planetary_events(subject)
    lunar = native_lunar_contacts(subject)
    assert events["status"] == lunar["status"] == "computed"
    for key in (
        "body_centers",
        "system_barycenters",
        "theoretical_points",
        "approximate_points",
        "unresolved_points",
    ):
        assert set(events["ephemeris_reference_points"][key]) == set(
            lunar["ephemeris_reference_points"][key]
        )
    assert events["ephemeris_reference_points"]["system_barycenters"] == [
        "Mars",
        "Jupiter",
        "Saturn",
    ]
    assert (
        events["longitude_motion"]["lunar_light_time"]["reason"]
        == "unsupported_physical_model"
    )
    assert (
        events["longitude_motion"]["display_longitude_offset_speed_degrees_per_day"]
        == lunar["longitude_motion"]["display_longitude_offset_speed_degrees_per_day"]
    )
    for name, s in events["question_states"].items():
        assert s["speed"] == getattr(subject, name.lower()).speed
        reconstructed = sum(
            s.get(k, 0.0)
            for k in (
                "speed_native",
                "speed_light_time_correction",
                "speed_spatial_aberration_correction",
                "speed_lunar_source_remainder_correction",
                "speed_sidereal_origin_wrap_correction",
                "speed_rotation_correction",
                "speed_analytic_frame_correction",
                "speed_position_derivative_correction",
                "speed_display_offset_correction",
            )
        )
        assert reconstructed == pytest.approx(s["speed"], abs=1e-14)
    assert events["full_original_text_acceptance"] is False


def test_astrodice_reference_field_uses_the_shared_definition():
    from fatebridge.core.output_astrodice import DiceSkyParams
    from fatebridge.core.output_charts import EphemerisReferencePoints

    points = EphemerisReferencePoints()
    assert (
        DiceSkyParams(ephemerisReferencePoints=points).ephemerisReferencePoints
        is points
    )
