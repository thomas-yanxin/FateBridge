"""Independent finite observer/optical/event controls, with failures retained."""

import gzip
import hashlib
import json
import math
from contextlib import nullcontext
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as runtime
from fatebridge.core.astro import classical, solar_events
from fatebridge.core.astro.classical import _planetary_hours
from fatebridge.core.astro.earth_attitude import physical_equator
from fatebridge.core.astro.iers_ut1 import use_ut1_source
from fatebridge.core.astro.reference_frames import dot
from fatebridge.core.astro.solar_observer import NativeSolarSource
from fatebridge.core.astro.terrestrial_observer import (
    AU_METRES,
    native_observer_site,
    terrestrial_observer,
)
from fatebridge.core.jyotish_kala import solar_packet, solar_parts
from fatebridge.utils.errors import EphemerisSourceError

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = json.loads(
    gzip.decompress(
        (ROOT / "tests/data/solar_horizon_v1/reference.json.gz").read_bytes()
    )
)
JPL_REFERENCE = json.loads(
    gzip.decompress(
        (ROOT / "tests/data/solar_horizon_v1/jpl-reference.json.gz").read_bytes()
    )
)
NATIVE_QUALIFICATION = json.loads(
    gzip.decompress(
        (
            ROOT / "tests/data/solar_horizon_v1/native-sign-qualification.json.gz"
        ).read_bytes()
    )
)
UNQUALIFIED_MOSHIER_CASES = {
    row["case"]
    for row in NATIVE_QUALIFICATION["windows"]
    if row["qualification"] == "solar_horizon_sign_unstable"
}


@pytest.fixture
def selected_path(monkeypatch, tmp_path):
    previous = runtime.configured_ephemeris_path()
    with monkeypatch.context() as change:
        change.delenv("FATEBRIDGE_JPL_FILE", raising=False)

        def select(no_data):
            path = tmp_path if no_data else ROOT / "ephe"
            change.setenv("SE_EPHE_PATH", str(path))
            runtime.configure_ephemeris_path(str(path))

        yield select
    runtime.configure_ephemeris_path(previous or "")


def test_external_provenance_and_original_gates_are_retained():
    assert REFERENCE["production_imported"] is False
    assert REFERENCE["gates"] == {
        "observer_position_metres": 0.0001,
        "observer_velocity_mps": 1e-8,
        "optics_arcseconds": 1e-6,
        "event_seconds": 0.001,
    }
    assert len(REFERENCE["observers"]) == 4428
    assert len(REFERENCE["optics"]) == 1042
    assert len(REFERENCE["events"]) == 2538
    assert {
        label: result["failures"]
        for label, result in REFERENCE["retained_before_failures"].items()
    } == {
        "edge": 24,
        "c04-edge": 72,
        "first-polar-cluster": 4,
        "first-spectral-polar-cluster": 33,
        "first-spectral-ordinary": 9,
    }
    assert len(REFERENCE["polar_constructions"]) == 48
    assert all(row["accepted"] for row in REFERENCE["polar_constructions"])
    assert REFERENCE["first_polar_construction_summary"]["construction_failures"] == 7
    assert REFERENCE["moshier_velocity_diagnostic"]["production_imported"] is False
    for name, source in REFERENCE["generator_sources"].items():
        assert (
            hashlib.sha256(source.encode()).hexdigest()
            == REFERENCE["generator_hashes"][name]
        )


@pytest.mark.local_data
@pytest.mark.parametrize(
    "row",
    JPL_REFERENCE["rows"],
    ids=lambda row: f'{row["family"]}-{row["case"]}',
)
def test_every_original_window_against_original_jpl_sources(row, selected_path):
    """File-dependent modeled UT1 clocks retain the original local-data scope."""
    case, expected = row["input"], row["reference"]
    selected_path(case["no_data"])
    assert JPL_REFERENCE["production_imported"] is False
    with use_ut1_source("iers_c04" if case["clock"] == "c04" else "swiss_delta_t"):
        actual = solar_events.solar_crossings_in_window(
            case["query_ut1"],
            case["query_ut1"] + 26 / 24,
            longitude=case["longitude"],
            latitude=case["latitude"],
            definition=(
                "hindu_geometric_center"
                if case["definition"] == 0
                else "apparent_topocentric_center"
            ),
        )
    assert expected["status"] == "ok"
    assert ["rise" if event.rising else "set" for event in actual] == [
        root["kind"] for root in expected["roots"]
    ]
    for event, root in zip(actual, expected["roots"], strict=True):
        assert event.ephemeris_model == (
            f'fatebridge_solar_horizon_{expected["source"].lower()}_v1'
        )
        assert event.ephemeris_flags is None
        assert abs(event.julian_day_ut1 - root["ut1"]) * 86400 <= 0.001
        assert abs(event.julian_day_tt - root["tt"]) * 86400 <= 0.001


@pytest.mark.local_data
def test_physical_receiver_and_native_position_bridge_against_official_sofa(
    selected_path,
):
    selected_path(False)
    for row in REFERENCE["observers"]:
        tt, ut1, lon, lat, height = row["input"]
        equator = physical_equator(runtime.swe, ut1, julian_day_tt=tt)
        pv = terrestrial_observer(equator, longitude=lon, latitude=lat, height=height)
        expected = row["physical_pv"]
        assert math.dist(pv.position, expected[:3]) * AU_METRES <= 0.0001, row
        assert math.dist(pv.velocity, expected[3:]) * AU_METRES / 86400 <= 1e-8, row
        site = native_observer_site(
            runtime.swe, equator, pv, ephemeris_flags=row["source_flags"]
        )
        want = row["source_site"]
        local_error = math.hypot(
            math.radians(math.remainder(site[0] - want[0], 360))
            * 6378136.6
            * math.cos(math.radians(want[1])),
            math.radians(site[1] - want[1]) * 6378136.6,
            site[2] - want[2],
        )
        assert local_error <= 0.0001, row


@pytest.mark.local_data
def test_solar_optics_against_original_c_and_sofa_with_supplied_epochs(selected_path):
    selected_path(False)
    for row in REFERENCE["optics"]:
        tt, ut1, lon, lat, height, flags, definition = row["input"]
        kwargs = dict(
            julian_day_tt=tt,
            longitude=lon,
            latitude=lat,
            height=height,
            ephemeris_flags=int(flags),
            definition=(
                "hindu_geometric_center"
                if definition == 0
                else "apparent_topocentric_center"
            ),
        )
        if row["status"] != 0:
            with pytest.raises(EphemerisSourceError):
                solar_events.solar_observation(ut1, **kwargs)
            continue
        result = solar_events.solar_observation(ut1, **kwargs)
        want = row["values"]
        a, b = result.physical_equatorial_direction, want[:3]
        cross = (
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        )
        assert (
            math.degrees(math.atan2(math.hypot(*cross), dot(a, b))) * 3600 <= 1e-6
        ), row
        assert abs(result.altitude_degrees - want[3]) * 3600 <= 1e-6, row
        assert result.ephemeris_flags == want[4], row


@pytest.mark.parametrize(
    "row",
    [
        pytest.param(
            row,
            id=f"{row['family']}-{row['reference']['case']}",
            marks=() if row["input"]["no_data"] else pytest.mark.local_data,
        )
        for row in REFERENCE["events"]
    ],
)
def test_first_directed_event_against_independent_scipy_search(row, selected_path):
    case, expected = row["input"], row["reference"]
    selected_path(case["no_data"])
    with use_ut1_source("iers_c04" if case["clock"] == "c04" else "swiss_delta_t"):
        for rising in (True, False):
            kwargs = dict(
                longitude=case["longitude"],
                latitude=case["latitude"],
                rising=rising,
                definition=(
                    "hindu_geometric_center"
                    if case["definition"] == 0
                    else "apparent_topocentric_center"
                ),
                ephemeris_flags=case["source_flags"],
            )
            if expected["status"] != "ok":
                with pytest.raises(EphemerisSourceError):
                    solar_events.next_solar_event(case["query_ut1"], **kwargs)
                continue
            if (
                row["family"] == "polar-cluster"
                and expected["case"] in UNQUALIFIED_MOSHIER_CASES
            ):
                with pytest.raises(EphemerisSourceError) as raised:
                    solar_events.next_solar_event(case["query_ut1"], **kwargs)
                assert raised.value.reason == "solar_horizon_sign_unstable"
                continue
            result = solar_events.next_solar_event(case["query_ut1"], **kwargs)
            want = next(
                (
                    event
                    for event in expected["roots"]
                    if event["kind"] == ("rise" if rising else "set")
                ),
                None,
            )
            assert (result is None) == (want is None), row
            if result is not None:
                assert abs(result.julian_day_ut1 - want["ut1"]) * 86400 <= 0.001, row
                assert result.ephemeris_flags == expected["actual_source"], row


@pytest.mark.local_data
@pytest.mark.parametrize(
    "row", [row for row in REFERENCE["events"] if row["family"] == "polar-cluster"]
)
def test_complete_polar_sequence_keeps_every_ordered_crossing(row, selected_path):
    case, expected = row["input"], row["reference"]
    selected_path(False)
    unqualified = expected["case"] in UNQUALIFIED_MOSHIER_CASES
    with (
        use_ut1_source("swiss_delta_t"),
        (
            pytest.raises(
                EphemerisSourceError, match="unresolved repeated sign changes"
            )
            if unqualified
            else nullcontext()
        ),
    ):
        events = solar_events.solar_crossings_in_window(
            case["query_ut1"],
            case["query_ut1"] + 26 / 24,
            longitude=case["longitude"],
            latitude=case["latitude"],
            definition=(
                "hindu_geometric_center"
                if case["definition"] == 0
                else "apparent_topocentric_center"
            ),
            ephemeris_flags=case["source_flags"],
        )
    if unqualified:
        assert len(expected["roots"]) > 0
    else:
        assert len(events) == len(expected["roots"]), row
        for actual, wanted in zip(events, expected["roots"], strict=True):
            assert actual.rising == (wanted["kind"] == "rise"), row
            assert abs(actual.julian_day_ut1 - wanted["ut1"]) * 86400 <= 0.001, row
            assert abs(actual.julian_day_tt - wanted["tt"]) * 86400 <= 0.001, row


@pytest.mark.local_data
@pytest.mark.parametrize(
    "row",
    [
        row
        for row in REFERENCE["events"]
        if row["family"] == "polar-cluster"
        and row["input"]["source_flags"] == 2
        and row["input"]["definition"] == 0
    ],
)
def test_jyotish_packet_and_active_arcs_keep_complete_polar_sequence(
    row, selected_path
):
    case, expected = row["input"], row["reference"]
    selected_path(False)
    with use_ut1_source("swiss_delta_t"):
        packet = solar_packet(
            case["query_ut1"] + 3 / 24,
            case["longitude"],
            case["latitude"],
            "require_data_files",
        )
        in_window = [
            event
            for event in packet["events"]
            if case["query_ut1"]
            <= event["julian_day_ut1"]
            <= case["query_ut1"] + 26 / 24
        ]
        assert len(in_window) == len(expected["roots"]), row
        for actual, wanted in zip(in_window, expected["roots"], strict=True):
            assert actual["kind"] == wanted["kind"], row
            assert abs(actual["julian_day_ut1"] - wanted["ut1"]) * 86400 <= 0.001, row
        for left, right in zip(expected["roots"], expected["roots"][1:]):
            at = left["ut1"] + (right["ut1"] - left["ut1"]) * 3 / 8
            parts = solar_parts(at, case["longitude"], packet)
            assert parts["active_arc_status"] == "bracketed", row
            assert parts["is_day"] == (left["kind"] == "rise"), row
            assert abs(parts["arc_start_jd_ut1"] - left["ut1"]) * 86400 <= 0.001, row
            assert abs(parts["arc_end_jd_ut1"] - right["ut1"]) * 86400 <= 0.001, row


@pytest.mark.local_data
@pytest.mark.parametrize(
    "row",
    [
        row
        for row in REFERENCE["events"]
        if row["family"] == "polar-cluster"
        and row["input"]["source_flags"] == 2
        and row["input"]["definition"] == 1
        and len(row["reference"]["roots"]) == 3
    ],
)
def test_western_hours_use_adjacent_polar_arc_without_half_day_skip(
    row, selected_path, monkeypatch
):
    case, expected = row["input"], row["reference"]
    selected_path(False)
    monkeypatch.setattr(
        classical, "select_solar_source", lambda *args: NativeSolarSource(2)
    )
    with use_ut1_source("swiss_delta_t"):
        for left, right in zip(expected["roots"], expected["roots"][1:]):
            if not any(
                event["kind"] == "rise" and event["ut1"] <= left["ut1"]
                for event in expected["roots"]
            ):
                # The frozen26h oracle does not supply this night arc's
                # opening sunrise; no weekday availability claim is made.
                continue
            at = left["ut1"] + (right["ut1"] - left["ut1"]) * 3 / 8
            hours = _planetary_hours(at, case["longitude"], case["latitude"], "UTC")
            assert hours is not None, row
            assert hours["is_day"] == (left["kind"] == "rise"), row
            assert hours["hour_number"] == 5, row
            assert abs(hours["arc_start_jd_ut1"] - left["ut1"]) * 86400 <= 0.001, row
            assert abs(hours["arc_end_jd_ut1"] - right["ut1"]) * 86400 <= 0.001, row


@pytest.mark.parametrize(
    "definition", ["hindu_geometric_center", "apparent_topocentric_center"]
)
def test_strict_source_admission_also_runs_when_no_polar_event_exists(
    selected_path, definition
):
    selected_path(True)
    kwargs = dict(longitude=0, latitude=90, rising=True, definition=definition)
    with use_ut1_source("swiss_delta_t"):
        assert solar_events.next_solar_event(2451545.0, **kwargs) is None
        assert (
            solar_events.next_solar_event(2451545.0, ephemeris_flags=4, **kwargs)
            is None
        )
        with pytest.raises(ValueError, match="require_data_files"):
            solar_events.next_solar_event(
                2451545.0, ephemeris_policy="require_data_files", **kwargs
            )


def test_optical_source_failure_restores_the_requested_receiver(
    monkeypatch, selected_path
):
    selected_path(True)
    original_state = solar_events._cartesian_state
    original_site = runtime.swe.set_topo
    calls = []
    sites = []
    failure = EphemerisSourceError("unavailable_during")

    def fail_natural_sun(tt, body, flags):
        calls.append(flags)
        if len(calls) == 2:
            raise failure
        return original_state(tt, body, flags)

    def track_site(*site):
        sites.append(site)
        return original_site(*site)

    monkeypatch.setattr(solar_events, "_cartesian_state", fail_natural_sun)
    monkeypatch.setattr(runtime.swe, "set_topo", track_site)
    with pytest.raises(EphemerisSourceError) as caught:
        solar_events.solar_observation(
            2451545.0,
            longitude=121.47,
            latitude=31.23,
            height=25,
            definition="apparent_topocentric_center",
            ephemeris_flags=4,
        )
    assert caught.value is failure
    assert len(sites) == 2 and sites[-1] == (121.47, 31.23, 25)


def test_native_qualification_preserves_all_original_root_denominators():
    """Numerical abstentions must not erase the original failed comparison rows."""
    historic = NATIVE_QUALIFICATION["historical_53"]
    assert (
        NATIVE_QUALIFICATION["original_sign_reference_sha256"]
        == REFERENCE["polar_adjacent_root_diagnostic"]["reference_sha256"]
    )
    assert len(historic["cases"]) == 25
    assert historic["roots"] == 53
    assert historic["baseline_tt_passes"] == historic["baseline_ut1_passes"] == 23
    assert historic["original_c_roots_with_multiple_sign_changes"] == 53
    assert historic["original_c_sign_changes"] == 739
    native_rows = {
        row["reference"]["case"]: row
        for row in REFERENCE["events"]
        if row["family"] == "polar-cluster" and row["input"]["source_flags"] == 4
    }
    assert len(native_rows) == len(NATIVE_QUALIFICATION["windows"]) == 96
    assert sum(len(row["reference"]["roots"]) for row in native_rows.values()) == 192
    for window in NATIVE_QUALIFICATION["windows"]:
        assert len(window["roots"]) == len(
            native_rows[window["case"]]["reference"]["roots"]
        )
        for diagnostic, expected in zip(
            window["roots"],
            native_rows[window["case"]]["reference"]["roots"],
            strict=True,
        ):
            assert diagnostic["expected_ut1"] == expected["ut1"]
            assert diagnostic["expected_tt"] == expected["tt"]
    assert (
        sum(len(native_rows[case]["reference"]["roots"]) for case in historic["cases"])
        == 53
    )
    assert set(historic["cases"]) <= UNQUALIFIED_MOSHIER_CASES


@pytest.mark.local_data
def test_moshier_ambiguity_is_not_hidden_by_a_one_ulp_query_window(selected_path):
    """Moving query bounds must not admit one arbitrary reversal of an unstable root."""
    selected_path(False)
    historic = NATIVE_QUALIFICATION["historical_53"]["baseline_replay"][0]
    case = next(
        row["input"]
        for row in REFERENCE["events"]
        if row["family"] == "polar-cluster"
        and row["reference"]["case"] == historic["case"]
    )
    root_ut1 = historic["roots"][1]["actual_ut1"]
    with use_ut1_source("swiss_delta_t"), pytest.raises(EphemerisSourceError) as raised:
        solar_events.solar_crossings_in_window(
            root_ut1,
            math.nextafter(root_ut1, math.inf),
            longitude=case["longitude"],
            latitude=case["latitude"],
            definition="hindu_geometric_center",
            ephemeris_flags=4,
        )
    assert raised.value.reason == "solar_horizon_sign_unstable"
