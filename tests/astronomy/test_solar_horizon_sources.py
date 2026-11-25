"""Automatic production source versus independent original JPL/SOFA roots."""

import gzip
import json
import math
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as runtime
from fatebridge.core.astro import solar_events, solar_observer
from fatebridge.core.astro.iers_ut1 import use_ut1_source
from fatebridge.core.astro.jpl_kinematics import source_kinematics
from fatebridge.core.astro.solar_events import (
    SolarDefinition,
    solar_crossings_in_window,
)
from fatebridge.core.astro.solar_observer import SolarSource
from fatebridge.core.jyotish_kala import solar_packet
from fatebridge.utils.errors import EphemerisSourceError
from tests.support.transports import (
    AS_OF,
    SPECS,
    business,
    rest,
    surface_calls,
    three_surfaces,
)

REFERENCE = json.loads(
    gzip.decompress(
        (
            Path(__file__).parents[1] / "data/solar_horizon_v1/de440-reference.json.gz"
        ).read_bytes()
    )
)
DATA = Path(__file__).parents[1] / "data/solar_horizon_v1"
FILE_REFERENCE = json.loads(
    gzip.decompress((DATA / "jpl-file-reference.json.gz").read_bytes())
)
FILE_FIXTURE = Path(__file__).parents[1] / "data/astrodice/tables/de441-j2000.eph"
HOURS_PAYLOAD = {
    "birth_year": 2000,
    "birth_month": 1,
    "birth_day": 1,
    "birth_hour": 12,
    "birth_minute": 0,
    "birth_timezone": "UTC",
    "birth_longitude": 0,
    "birth_latitude": 51.5,
    "hsys": 2,
}


@pytest.fixture
def selected_jpl(tmp_path, monkeypatch):
    previous = runtime.configured_ephemeris_path()
    path = tmp_path / "solar-source.eph"
    path.write_bytes(FILE_FIXTURE.read_bytes())
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", path.name)
    runtime.configure_ephemeris_path(str(tmp_path))
    yield path
    monkeypatch.undo()
    runtime.configure_ephemeris_path(previous or "")


@pytest.mark.parametrize("row", REFERENCE["rows"], ids=lambda r: str(r["case"]))
def test_automatic_source_against_every_fixed_original_de440_window(row):
    case = row["input"]
    with use_ut1_source("swiss_delta_t"):
        actual = solar_crossings_in_window(
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
    assert ["rise" if event.rising else "set" for event in actual] == [
        event["kind"] for event in row["roots"]
    ]
    for event, expected in zip(actual, row["roots"], strict=True):
        assert event.ephemeris_model == "fatebridge_solar_horizon_de440_v1"
        assert event.ephemeris_flags is None  # Packaged source has no native flag.
        assert abs(event.julian_day_ut1 - expected["ut1"]) * 86400 <= 0.001
        assert abs(event.julian_day_tt - expected["tt"]) * 86400 <= 0.001


def test_packaged_source_change_is_not_hidden_by_absent_native_flags(monkeypatch):
    def observe(ut1, *, definition, **kwargs):
        return solar_events.SolarObservation(
            ut1,
            ut1 + 64 / 86400,
            10.0,
            (1.0, 0.0, 0.0),
            (
                "fatebridge_solar_horizon_de440_v1"
                if ut1 == 2451545.0
                else "fatebridge_solar_horizon_de441_v1"
            ),
            None,
            definition,
        )

    monkeypatch.setattr(solar_events, "solar_observation", observe)
    with pytest.raises(EphemerisSourceError) as raised:
        solar_crossings_in_window(
            2451545.0,
            2451546.0,
            longitude=0,
            latitude=0,
            definition="hindu_geometric_center",
        )
    assert raised.value.reason == "coordinate_model_changed"


def test_real_polar_no_event_retains_the_consumed_source():
    packet = solar_packet(2451717.0, 0, 90, "auto")
    assert packet["events"] == []
    assert len(packet["no_event_searches"]) == 16
    assert packet["ephemeris_models"] == ["fatebridge_solar_horizon_de440_v1"]
    reference = packet["ephemeris_sources"]["fatebridge_solar_horizon_de440_v1"]
    assert reference["source_version"] == "DE440 (2020; published 2021)"


def test_invalid_packaged_source_cannot_become_a_polar_no_event(monkeypatch):
    failure = EphemerisSourceError("solar_de440_invalid")

    def invalid(*args, **kwargs):
        raise failure

    monkeypatch.setattr(solar_observer.de440_solar, "state", invalid)
    with pytest.raises(EphemerisSourceError) as raised:
        solar_crossings_in_window(
            2451717.0,
            2451718.0,
            longitude=0,
            latitude=90,
            definition="hindu_geometric_center",
        )
    assert raised.value is failure


@pytest.mark.parametrize(
    "row", FILE_REFERENCE["rows"], ids=lambda row: str(row["case"])
)
def test_selected_original_file_uses_full_tdb_optics(row, selected_jpl):
    case, expected = row["input"], row["reference"]
    with use_ut1_source("swiss_delta_t"):
        actual = solar_crossings_in_window(
            case["query_ut1"],
            case["query_ut1"] + 26 / 24,
            longitude=case["longitude"],
            latitude=case["latitude"],
            definition=(
                "hindu_geometric_center"
                if case["definition"] == 0
                else "apparent_topocentric_center"
            ),
            ephemeris_policy="require_data_files",
        )
    assert ["rise" if event.rising else "set" for event in actual] == [
        event["kind"] for event in expected["roots"]
    ]
    for event, root in zip(actual, expected["roots"], strict=True):
        assert event.ephemeris_model == "fatebridge_solar_horizon_de441_file_v1"
        assert event.ephemeris_flags is None
        assert abs(event.julian_day_ut1 - root["ut1"]) * 86400 <= 0.001
        assert abs(event.julian_day_tt - root["tt"]) * 86400 <= 0.001


@pytest.mark.parametrize("row", FILE_REFERENCE["split_epoch_states"])
def test_selected_file_preserves_sub_ulp_source_epochs(row):
    epoch = Fraction(row["jd0"]) + Fraction(*row["tdb_fraction"])
    values, _ = source_kinematics(FILE_FIXTURE, epoch, row["body"])
    assert math.dist(values[:3], row["position_au"]) * 149597870700 <= 0.0001
    assert math.dist(values[3:6], row["velocity_au_day"]) * 149597870700 / 86400 <= 1e-8


def test_no_event_packet_retains_selected_file_identity(selected_jpl):
    with use_ut1_source("swiss_delta_t"):
        packet = solar_packet(2451545.0, 0, 90, "require_data_files")
    assert packet["events"] == []
    assert packet["ephemeris_models"] == ["fatebridge_solar_horizon_de441_file_v1"]
    reference = packet["ephemeris_sources"]["fatebridge_solar_horizon_de441_file_v1"]
    assert (
        reference["calculation_library"]
        == "FateBridge selected-file reader; SOFA/ERFA optics"
    )
    assert (
        reference["time_argument"]
        == "TDB from declared TT via geocentric Fairhead model"
    )


def test_file_reader_failure_cannot_become_a_polar_no_event(selected_jpl, monkeypatch):
    failure = EphemerisSourceError("jpl_kinematics_invalid")

    def invalid(*args, **kwargs):
        raise failure

    monkeypatch.setattr(solar_observer, "source_kinematics", invalid)
    with pytest.raises(EphemerisSourceError) as raised:
        solar_crossings_in_window(
            2451545.0,
            2451546.0,
            longitude=0,
            latitude=90,
            definition="hindu_geometric_center",
            ephemeris_policy="require_data_files",
        )
    assert raised.value is failure


@pytest.mark.parametrize("minimum", [-1, 0, 1], ids=["short-arc", "tangent", "no-root"])
def test_moshier_admission_keeps_resolved_short_arcs_and_tangent_controls(
    minimum, monkeypatch
):
    """A real short visibility arc must not be mistaken for numerical reversals."""
    start_ut1 = 2451545.0
    middle_ut1 = start_ut1 + 0.5 / 86400
    half_width_days = 0.005 / 86400
    evaluations = []

    def observe(
        julian_day_ut1: float,
        *,
        longitude: float,
        latitude: float,
        height: float,
        definition: SolarDefinition,
        source: SolarSource,
    ) -> solar_events.SolarObservation:
        evaluations.append(julian_day_ut1)
        altitude_degrees = 1e8 * (
            (julian_day_ut1 - middle_ut1) ** 2 + minimum * half_width_days**2
        )
        return solar_events.SolarObservation(
            julian_day_ut1,
            julian_day_ut1 + 64 / 86400,
            altitude_degrees,
            (1.0, 0.0, 0.0),
            "moshier",
            4,
            definition,
        )

    monkeypatch.setattr(solar_events, "solar_observation", observe)
    events = solar_crossings_in_window(
        start_ut1,
        start_ut1 + 1 / 86400,
        longitude=0,
        latitude=90,
        definition="hindu_geometric_center",
        ephemeris_flags=4,
    )
    if minimum < 0:
        assert [event.rising for event in events] == [False, True]
        for event, expected_ut1 in zip(
            events,
            [middle_ut1 - half_width_days, middle_ut1 + half_width_days],
            strict=True,
        ):
            assert abs(event.julian_day_ut1 - expected_ut1) * 86400 <= 0.001
            assert event.observation_evaluations == len(evaluations)
        for lower_ut1, upper_ut1, rising in (
            (start_ut1, middle_ut1, False),
            (middle_ut1, start_ut1 + 1 / 86400, True),
        ):
            partial = solar_crossings_in_window(
                lower_ut1,
                upper_ut1,
                longitude=0,
                latitude=90,
                definition="hindu_geometric_center",
                ephemeris_flags=4,
            )
            assert [event.rising for event in partial] == [rising]
            assert lower_ut1 <= partial[0].julian_day_ut1 <= upper_ut1
    else:
        assert events == []


@pytest.mark.parametrize("latitude", [51.5, 90.0])
def test_planetary_hours_automatic_source_across_real_surfaces(
    latitude, tmp_path, monkeypatch, capsys
):
    """The consumer keeps automatic DE440 source identity, including no sunrise."""
    result = three_surfaces(
        SPECS["astro_chart"],
        {**HOURS_PAYLOAD, "birth_latitude": latitude},
        ["planetary_hours"],
        AS_OF,
        tmp_path,
        monkeypatch,
        capsys,
    )
    if latitude == 90:
        assert result["planetary_hours"] is None
    else:
        hours = result["planetary_hours"]
        assert hours["ephemeris_models"] == ["fatebridge_solar_horizon_de440_v1"]
        assert hours["arc_start_jd_ut1"] < hours["arc_end_jd_ut1"]
        assert hours["hour_start_utc"] < hours["hour_end_utc"]


def test_planetary_hours_full_response_on_real_surfaces(surface_calls):
    """Full consumer responses must retain the same solar evidence on every surface."""
    response, protocol, code, local = surface_calls(
        SPECS["astro_chart"],
        HOURS_PAYLOAD,
        params={"as_of": AS_OF, "response_char_limit": 0},
        options={"response_char_limit": 0},
        flags=["--response-char-limit", "0"],
    )
    assert response.status_code == 200 and not protocol.is_error and code == 0
    outputs = [response.json(), protocol.structured_content, local]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        hours = output["planetary_hours"]
        assert hours["ephemeris_models"] == ["fatebridge_solar_horizon_de440_v1"]
        assert hours["arc_start_jd_ut1"] < hours["arc_end_jd_ut1"]
