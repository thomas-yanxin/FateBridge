"""Automatic production source versus independent original JPL/SOFA roots."""

import gzip
import hashlib
import json
import math
import struct
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core import de440_solar
from fatebridge.core import ephemeris_runtime as runtime
from fatebridge.core.astro import solar_events, solar_observer
from fatebridge.core.astro.cartesian import CartesianState
from fatebridge.core.astro.iers_ut1 import use_ut1_source
from fatebridge.core.astro.jpl_kinematics import source_kinematics
from fatebridge.core.astro.solar_events import solar_crossings_in_window
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.jyotish.jyotish_kala import solar_packet
from fatebridge.utils.errors import EphemerisSourceError

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
FIXED_RECEIVER = CartesianState(
    (-1.482086030143487e-05, -3.997626937223486e-05, 3.644206482022839e-08),
    (0.00025186529158070645, -9.337744457961186e-05, -5.920769800297563e-07),
)


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
def test_automatic_source_against_every_fixed_original_de440_window(row) -> None:
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


def test_de440_solar_direction_retains_two_instants_with_the_same_scalar_tt() -> None:
    # R49 DE440.minus and DE440.plus, original DE440 with CALCEPH 5.0.1
    # and SOFA 2023-10-11. The receiver is fixed to isolate the source clock.
    early = TTInstant(Fraction(27863804814188085012223, 11324620800000000))
    late = TTInstant(Fraction(27863804814188089206527, 11324620800000000))
    assert early.as_float() == late.as_float()
    source = solar_observer.PackagedSolarSource.DE440
    first = solar_observer.precise_solar_direction(early, FIXED_RECEIVER, source)
    second = solar_observer.precise_solar_direction(late, FIXED_RECEIVER, source)
    difference = tuple(right - left for left, right in zip(first, second, strict=True))
    expected = (-5.8462679142223806e-12, 1.8824941605544154e-12, 8.163469900068776e-13)
    assert math.degrees(math.dist(difference, expected)) * 3600 <= 1e-8


S3_RECEIVING_RECORDS = [
    "d20e4dad598d1bf26324b3a247faa88be0908185760da8785ba75d9c73167d79",
    "80701efd6609ad74c604e5a49d2a4ab697bbaa8e1783ea302df4da16944b75b0",
    "b752dae7cd64c483fda1deed2715cb746d36a5e13607bfa6bcb07855dab539d7",
]


@pytest.mark.parametrize(
    "mode, tt, expected",
    [
        pytest.param(
            "horizon",
            TTInstant(
                Fraction(1960742545946534227368982398739, 796899343984252629811200)
            ),
            S3_RECEIVING_RECORDS,
            id="horizon-S3",
        ),
        pytest.param(
            "parts",
            ("0x1.2c5983fffffebp+21", "-0x1.73377e9db0216p-33"),
            S3_RECEIVING_RECORDS,
            id="term-parts-S3",
        ),
        pytest.param(
            "scalar",
            ("0x1.295003fffffd9p+21",),
            [
                "98b100731d324a84caa7061b3974cf506bcf1c650a69c3afb3e029ebe50b6db6",
                "fba31b94b3dfa1bf664254b1882eb5ceb0de12154db89afbfd8c8afd58e8ec9c",
                "78382a93441dba6951be7231726d639e15217f3428ec3d4e3ee49bb96b5adda2",
            ],
            id="term-scalar-L2",
        ),
    ],
)
def test_de440_solar_reception_selects_original_records_left_of_tdb_seam(
    monkeypatch: pytest.MonkeyPatch, mode: str, tt, expected
) -> None:
    # Original DE440 SPK words and SOFA iauDtdb. S3 is 1.199 ps left of
    # TDB JD 2460464.5 and L2 is 40.988 ns left of TDB JD 2435584.5.
    source_data = de440_solar._selected_profile(de440_solar.EXTENDED_MODEL_ID).data
    read_record = struct.unpack_from
    selected = []

    def capture_record(fmt, buffer, offset=0):
        if buffer is source_data:
            size = struct.calcsize(fmt)
            selected.append(hashlib.sha256(buffer[offset : offset + size]).hexdigest())
        else:
            pass
        return read_record(fmt, buffer, offset)

    monkeypatch.setattr(de440_solar.struct, "unpack_from", capture_record)
    if mode == "horizon":
        solar_observer.precise_solar_direction(
            tt, FIXED_RECEIVER, solar_observer.PackagedSolarSource.DE440
        )
    elif mode == "parts":
        de440_solar.solar_longitude_parts(*map(float.fromhex, tt))
    else:
        de440_solar.solar_longitude(*map(float.fromhex, tt))
    # First reads are the receiving EMB, geocentric Earth and zero-delay Sun.
    assert selected[:3] == expected


def test_packaged_source_change_is_not_hidden_by_absent_native_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_real_polar_no_event_retains_the_consumed_source() -> None:
    packet = solar_packet(2451717.0, 0, 90, "auto")
    assert packet["events"] == []
    assert len(packet["no_event_searches"]) == 16
    assert packet["ephemeris_models"] == ["fatebridge_solar_horizon_de440_v1"]
    reference = packet["ephemeris_sources"]["fatebridge_solar_horizon_de440_v1"]
    assert reference["source_version"] == "DE440 (2020; published 2021)"


def test_invalid_packaged_source_cannot_become_a_polar_no_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
def test_selected_original_file_uses_full_tdb_optics(row, selected_jpl) -> None:
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
def test_selected_file_preserves_sub_ulp_source_epochs(row) -> None:
    epoch = Fraction(row["jd0"]) + Fraction(*row["tdb_fraction"])
    values, _ = source_kinematics(FILE_FIXTURE, epoch, row["body"])
    assert math.dist(values[:3], row["position_au"]) * 149597870700 <= 0.0001
    assert math.dist(values[3:6], row["velocity_au_day"]) * 149597870700 / 86400 <= 1e-8


def test_no_event_packet_retains_selected_file_identity(selected_jpl) -> None:
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


def test_file_reader_failure_cannot_become_a_polar_no_event(
    selected_jpl, monkeypatch: pytest.MonkeyPatch
) -> None:
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
