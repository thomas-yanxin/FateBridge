"""Independent finite observer/optical/event controls, with failures retained."""

import gzip
import hashlib
import json
import math
import struct
from fractions import Fraction
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
from fatebridge.core.jyotish.jyotish_kala import solar_packet, solar_parts
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
C04_REFERENCE = json.loads(
    gzip.decompress(
        (ROOT / "tests/data/solar_horizon_v1/c04-reference.json.gz").read_bytes()
    )
)
C04_OUTSIDE_SOURCE = "IERS C04 UT1 is outside the modern forward source bounds"


@pytest.mark.parametrize(
    "case, start, expected",
    [
        ("binade", 0, [(0, 0)]),
        ("grid_zero_interval", -1, []),
        ("bisection_zero_interval", -1, []),
    ],
)
def test_solar_events_require_an_isolated_crossing(
    case: str, start, expected, monkeypatch: pytest.MonkeyPatch
) -> None:
    epoch = float(2**21)
    native_flags = runtime.swe.FLG_MOSEPH

    def observe(ut1, **kwargs):
        x = (ut1 - epoch) * 64
        if case == "binade":
            # At the adjacent left point the sign is negative. A full ulp
            # measured at the epoch steps twice as far and has a positive sign.
            altitude = max(x, -2 * x - 3 * 2**-26)
        else:
            left, right = (
                (-0.5, 0.5) if case == "grid_zero_interval" else (1 / 16, 3 / 16)
            )
            altitude = (min(x - left, 0) + max(x - right, 0)) * 2**-48
        return solar_events.SolarObservation(
            ut1,
            ut1,
            altitude,
            (1.0, 0.0, 0.0),
            "moshier",
            native_flags,
            kwargs["definition"],
        )

    monkeypatch.setattr(solar_events, "solar_observation", observe)
    with use_ut1_source("swiss_delta_t"):
        events = solar_events.solar_crossings_in_window(
            epoch + start / 64,
            epoch + 1 / 64,
            longitude=0,
            latitude=0,
            definition="hindu_geometric_center",
            source=NativeSolarSource(native_flags),
        )
    assert [event.bracket_ut1 for event in events] == [
        (epoch + left / 64, epoch + right / 64) for left, right in expected
    ]
    assert all(event.rising for event in events)


def test_spectral_crossing_stays_in_its_closed_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = float.fromhex("0x1.ffffffffffffcp+20")
    end = float.fromhex("0x1.0000000000003p+21")
    next_point = math.nextafter(start, math.inf)
    native_flags = runtime.swe.FLG_MOSEPH
    samples = []

    def observe(ut1, **kwargs):
        samples.append(ut1)
        return solar_events.SolarObservation(
            ut1,
            ut1,
            -0.5 if ut1 == start else 0.5,
            (1.0, 0.0, 0.0),
            "moshier",
            native_flags,
            kwargs["definition"],
        )

    monkeypatch.setattr(solar_events, "solar_observation", observe)
    with use_ut1_source("swiss_delta_t"):
        events = solar_events.solar_crossings_in_window(
            start,
            end,
            longitude=0,
            latitude=0,
            definition="hindu_geometric_center",
            source=NativeSolarSource(native_flags),
        )
    assert all(start <= point <= end for point in samples)
    assert [(event.bracket_ut1, event.rising) for event in events] == [
        ((start, next_point), True)
    ]


def test_solar_bisection_keeps_strict_brackets_around_reverse_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    epoch = 2451545.0
    step = math.ulp(epoch)
    flags = runtime.swe.FLG_MOSEPH

    def observe(ut1, **kwargs):
        word = (ut1 - epoch) / step
        altitude = (
            (word - 135.5)
            / 256
            * ((word - 144) / 256)
            * ((word - 151.5) / 256)
            * 2**-56
        )
        return solar_events.SolarObservation(
            ut1,
            ut1,
            altitude,
            (1.0, 0.0, 0.0),
            "moshier",
            flags,
            kwargs["definition"],
        )

    monkeypatch.setattr(solar_events, "solar_observation", observe)
    with use_ut1_source("swiss_delta_t"):
        events = solar_events.solar_crossings_in_window(
            epoch,
            epoch + 256 * step,
            longitude=0,
            latitude=0,
            definition="hindu_geometric_center",
            source=NativeSolarSource(flags),
        )
    assert [(event.bracket_ut1, event.rising) for event in events] == [
        ((epoch + 135 * step, epoch + 136 * step), True),
        ((epoch + 144 * step, epoch + 144 * step), False),
        ((epoch + 151 * step, epoch + 152 * step), True),
    ]


def test_solar_crossing_covers_each_word_of_a_narrow_binade_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = float.fromhex("0x1.ffffffffffffbp+20")
    bits = struct.unpack(">Q", struct.pack(">d", first))[0]
    words = [struct.unpack(">d", struct.pack(">Q", bits + i))[0] for i in range(15)]
    heights = dict(zip(words, (1, 1, 1, -1, 1, 1, -1, 1, -1, 1, 1, -1, 1, 1, 1)))
    flags = runtime.swe.FLG_MOSEPH

    def observe(ut1, **kwargs):
        return solar_events.SolarObservation(
            ut1,
            ut1 + 0.01,
            heights[ut1] * 2**-20,
            (1.0, 0.0, 0.0),
            "moshier",
            flags,
            kwargs["definition"],
        )

    monkeypatch.setattr(solar_events, "solar_observation", observe)
    with use_ut1_source("swiss_delta_t"):
        events = solar_events.solar_crossings_in_window(
            words[1],
            words[13],
            longitude=0,
            latitude=0,
            definition="hindu_geometric_center",
            source=NativeSolarSource(flags),
        )
    lower_indices = (2, 3, 5, 6, 7, 8, 10, 11)
    assert [(event.bracket_ut1, event.rising) for event in events] == [
        ((words[i], words[i + 1]), heights[words[i + 1]] > 0) for i in lower_indices
    ]
    assert [event.julian_day_tt for event in events] == [
        words[i] + 0.01 for i in lower_indices
    ]


def _c04_window(mode, key):
    request = C04_REFERENCE["requests"][mode][key]
    return request["admission"], C04_REFERENCE["windows"][request["window"]]


def _assert_c04_event_epoch(julian_day, bracket):
    point = Fraction(julian_day)
    assert max(abs(point - Fraction(edge)) for edge in bracket) * 86400 <= Fraction(
        1, 1000
    )


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


@pytest.mark.local_data
def test_solar_optics_against_original_c_and_sofa_with_supplied_epochs(
    selected_path,
) -> None:
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
        else:
            pass
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


@pytest.mark.parametrize("chunk_index", range(6), ids=lambda i: f"native-{i}")
def test_first_directed_event_against_independent_scipy_search(
    chunk_index, selected_path
) -> None:
    selected_path(True)
    native_rows = [row for row in REFERENCE["events"] if row["input"]["no_data"]]
    root_rows = [row for row in native_rows if row["family"] == "root"]
    edge_rows = [row for row in native_rows if row["family"] != "root"][::4]
    rows = (root_rows + edge_rows)[chunk_index::6]
    modern = False
    for row in rows:
        case, expected = row["input"], row["reference"]
        modern = case["clock"] == "c04"
        start = case["query_ut1"]
        site = dict(
            longitude=case["longitude"],
            latitude=case["latitude"],
            definition=(
                "hindu_geometric_center"
                if case["definition"] == 0
                else "apparent_topocentric_center"
            ),
            ephemeris_flags=case["source_flags"],
        )
        with use_ut1_source("iers_c04" if modern else "swiss_delta_t"):
            if modern:
                key = f'{row["family"]}-{expected["case"]}'
                admission, window = _c04_window("native", key)
                assert (
                    window["source"]
                    == {2: "Swiss", 4: "Moshier"}[expected["actual_source"]]
                )
                if admission != "in_range":
                    for rising in (True, False):
                        with pytest.raises(ValueError, match=C04_OUTSIDE_SOURCE):
                            solar_events.next_solar_event(start, rising=rising, **site)
                    paired = solar_events.solar_crossings_in_window(
                        *window["ut1"], **site
                    )
                else:
                    paired = None
                    assert window["ut1"] == [start, start + 26 / 24]
                wanted = window["roots"]
            else:
                paired = None
                wanted = expected["roots"]
            for rising in (True, False):
                if expected["status"] != "ok":
                    with pytest.raises(EphemerisSourceError):
                        solar_events.next_solar_event(start, rising=rising, **site)
                    continue
                else:
                    pass
                result = (
                    solar_events.next_solar_event(start, rising=rising, **site)
                    if paired is None
                    else next(
                        (event for event in paired if event.rising == rising), None
                    )
                )
                want = next(
                    (
                        event
                        for event in wanted
                        if event["kind"] == ("rise" if rising else "set")
                    ),
                    None,
                )
                assert (result is None) == (want is None), row
                if result is not None:
                    if modern:
                        _assert_c04_event_epoch(result.julian_day_ut1, want["UT1"])
                    else:
                        assert (
                            abs(result.julian_day_ut1 - want["ut1"]) * 86400 <= 0.001
                        ), row
                    assert result.ephemeris_flags == expected["actual_source"], row
                else:
                    pass


@pytest.mark.local_data
def test_jyotish_packet_and_active_arcs_keep_complete_polar_sequence(
    selected_path,
) -> None:
    selected_path(False)
    for row in REFERENCE["events"]:
        if not (
            row["family"] == "polar-cluster"
            and row["input"]["source_flags"] == 2
            and row["input"]["definition"] == 0
        ):
            continue
        else:
            pass
        case, expected = row["input"], row["reference"]
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
                assert (
                    abs(actual["julian_day_ut1"] - wanted["ut1"]) * 86400 <= 0.001
                ), row
            for left, right in zip(expected["roots"], expected["roots"][1:]):
                at = left["ut1"] + (right["ut1"] - left["ut1"]) * 3 / 8
                parts = solar_parts(at, case["longitude"], packet)
                assert parts["active_arc_status"] == "bracketed", row
                assert parts["is_day"] == (left["kind"] == "rise"), row
                assert (
                    abs(parts["arc_start_jd_ut1"] - left["ut1"]) * 86400 <= 0.001
                ), row
                assert abs(parts["arc_end_jd_ut1"] - right["ut1"]) * 86400 <= 0.001, row


@pytest.mark.local_data
def test_western_hours_use_adjacent_polar_arc_without_half_day_skip(
    selected_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected_path(False)
    monkeypatch.setattr(
        classical, "select_solar_source", lambda *args: NativeSolarSource(2)
    )
    for row in REFERENCE["events"]:
        if not (
            row["family"] == "polar-cluster"
            and row["input"]["source_flags"] == 2
            and row["input"]["definition"] == 1
            and len(row["reference"]["roots"]) == 3
        ):
            continue
        else:
            pass
        case, expected = row["input"], row["reference"]
        with use_ut1_source("swiss_delta_t"):
            for left, right in zip(expected["roots"], expected["roots"][1:]):
                if not any(
                    event["kind"] == "rise" and event["ut1"] <= left["ut1"]
                    for event in expected["roots"]
                ):
                    # The frozen26h oracle does not supply this night arc's
                    # opening sunrise; no weekday availability claim is made.
                    continue
                else:
                    pass
                at = left["ut1"] + (right["ut1"] - left["ut1"]) * 3 / 8
                hours = _planetary_hours(at, case["longitude"], case["latitude"], "UTC")
                assert hours is not None, row
                assert hours["is_day"] == (left["kind"] == "rise"), row
                assert hours["hour_number"] == 5, row
                assert (
                    abs(hours["arc_start_jd_ut1"] - left["ut1"]) * 86400 <= 0.001
                ), row
                assert abs(hours["arc_end_jd_ut1"] - right["ut1"]) * 86400 <= 0.001, row


@pytest.mark.parametrize(
    "definition", ["hindu_geometric_center", "apparent_topocentric_center"]
)
def test_strict_source_admission_also_runs_when_no_polar_event_exists(
    selected_path, definition: str
) -> None:
    selected_path(True)
    kwargs = dict(longitude=0, latitude=90, rising=True, definition=definition)
    with use_ut1_source("swiss_delta_t"):
        assert solar_events.next_solar_event(2451545.0, **kwargs) is None
        with pytest.raises(ValueError, match="require_data_files"):
            solar_events.next_solar_event(
                2451545.0, ephemeris_policy="require_data_files", **kwargs
            )


def test_optical_source_failure_restores_the_requested_receiver(
    monkeypatch: pytest.MonkeyPatch, selected_path
) -> None:
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
        else:
            pass
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
