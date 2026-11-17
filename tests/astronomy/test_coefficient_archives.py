"""Original DE440 words and independent bounded DE441 source arithmetic."""

import gzip
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path

import erfa
import pytest

from fatebridge.core import de440_solar
from fatebridge.core.astro import de441_source
from fatebridge.core.astro.coefficient_storage import (
    RecordBlock,
    pack_records,
    unpack_records,
)
from fatebridge.utils.errors import EphemerisSourceError

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/de441-pluto-source-reference-v1.json"
    ).read_text()
)
OUTER_REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/de441-outer-source-reference-v2.json"
    ).read_text()
)
DATA = Path(de441_source.__file__).parents[2] / "data/astronomy"
SOURCE_REFERENCE = json.loads(
    (Path(__file__).parents[1] / "fixtures/de441-source-reference-v3.json").read_text()
)
ACCELERATION_REFERENCE = json.loads(
    (
        Path(__file__).parents[1]
        / "fixtures/de441-source-acceleration-reference-v1.json"
    ).read_text()
)


def test_byte_channels_preserve_every_bit_across_different_record_strides():
    # Includes all byte values, unlike a selected collection of rounded floats.
    raw = bytes(range(256)) * 3
    blocks = [RecordBlock(32, 8), RecordBlock(16, 32)]
    packed = pack_records(raw, blocks)
    assert unpack_records(packed, blocks) == raw
    with pytest.raises(ValueError, match="layout"):
        pack_records(raw[:-1], blocks)
    with pytest.raises(ValueError, match="layout"):
        unpack_records(gzip.compress(raw[:-1]), blocks)


def test_all_five_logical_solar_sources_keep_every_original_word_and_domain():
    data_ids = set()
    for original in REFERENCE["original_DE440_logical_views"]:
        profile = de440_solar._profile(original["model_id"])
        data_ids.add(id(profile.data))
        manifest = profile.manifest
        selected = b"".join(
            profile.data[s["offset_bytes"] : s["offset_bytes"] + s["bytes"]]
            for s in manifest["segments"]
        )
        assert len(selected) == original["uncompressed_bytes"]
        assert hashlib.sha256(selected).hexdigest() == original["uncompressed_sha256"]
        assert (
            manifest["software_solar_term_years"]
            == original["software_solar_term_years"]
        )
        for old, new in zip(original["segments"], manifest["segments"]):
            # Only the physical archive offset changes; local polynomial grids
            # and each original source-record selection remain identical.
            assert {k: v for k, v in old.items() if k != "offset_bytes"} == {
                k: v for k, v in new.items() if k != "offset_bytes"
            }
        for segment in manifest["segments"]:
            pair = segment["center"], segment["target"]
            low = segment["initial_seconds_from_j2000_tdb"] / 86400.0
            high = low + segment["record_count"] * segment["interval_seconds"] / 86400.0
            for outside in (
                math.nextafter(low, -math.inf),
                math.nextafter(high, math.inf),
            ):
                with pytest.raises(EphemerisSourceError, match="cover"):
                    de440_solar.state(pair, outside, profile_id=original["model_id"])
    assert len(data_ids) == 1


def test_full_native_JPL_source_controls_keep_the_original_ICRF_gates():
    assert len(REFERENCE["rows"]) == 636
    for row in REFERENCE["rows"]:
        days = row["source_TDB_JD"] - 2451545.0
        pluto = de441_source.barycentric_state("Pluto", days)
        sun = de441_source.barycentric_state("Sun", days)
        expected = row["heliocentric_ICRF_AU_and_AU_TDB_day"]
        dp = max(
            abs(a - b - e)
            for a, b, e in zip(pluto.position, sun.position, expected[:3])
        )
        dv = max(
            abs(a - b - e)
            for a, b, e in zip(pluto.velocity, sun.velocity, expected[3:])
        )
        assert dp <= REFERENCE["source_position_gate_AU"], row["id"]
        assert dv <= REFERENCE["source_velocity_gate_AU_per_TDB_day"], row["id"]


def test_every_outer_group_matches_independent_full_JPL_at_source_cell_edges():
    assert OUTER_REFERENCE["source_position_gate_AU"] == 1e-12
    assert OUTER_REFERENCE["source_velocity_gate_AU_per_TDB_day"] == 1e-13
    assert {row["body"] for row in OUTER_REFERENCE["rows"]} == {
        "Jupiter",
        "Saturn",
        "Uranus",
        "Neptune",
        "Pluto",
        "Sun",
    }
    for row in OUTER_REFERENCE["rows"]:
        state = de441_source.barycentric_state(
            row["body"], row["source_TDB_JD"] - 2451545.0
        )
        reference = row["ICRF_barycentric_AU_and_AU_TDB_day"]
        assert max(abs(a - b) for a, b in zip(state.position, reference[:3])) <= 1e-12
        assert max(abs(a - b) for a, b in zip(state.velocity, reference[3:])) <= 1e-13


def test_declared_frame_bias_matches_the_independent_ERFA_standard():
    expected = erfa.bp06(2451545.0, 0.0)[0]
    actual = de441_source._parameters()["frame_bias"]["ICRF_to_mean_J2000"]
    assert (
        max(
            abs(a - b)
            for row, other in zip(actual, expected)
            for a, b in zip(row, other)
        )
        < 1e-22
    )


def test_source_coverage_and_nonfinite_epochs_do_not_return_an_old_orbit():
    p = de441_source._parameters()
    low, high = (jd - 2451545.0 for jd in p["source_TDB_JD_bounds"])
    for days in (low, high):
        assert all(
            math.isfinite(v)
            for v in de441_source.barycentric_state("Pluto", days).position
        )
    for days in (math.nextafter(low, -math.inf), math.nextafter(high, math.inf)):
        with pytest.raises(EphemerisSourceError) as error:
            de441_source.barycentric_state("Pluto", days)
        assert error.value.reason == "jpl_kinematics_outside_source"
    # The delayed source clock carries lower bits than a scalar epoch ULP.
    # An exact out-of-source value must not round back onto a legal endpoint.
    for days in (
        Fraction(low) - Fraction(1, 2**80),
        Fraction(high) + Fraction(1, 2**80),
    ):
        with pytest.raises(EphemerisSourceError) as error:
            de441_source.barycentric_state("Pluto", days)
        assert error.value.reason == "jpl_kinematics_outside_source"
    with pytest.raises(ValueError, match="finite"):
        de441_source.barycentric_state("Pluto", math.nan)


@pytest.mark.parametrize("fault", ["missing", "bytes", "rehash"])
def test_corrupt_continuous_source_has_an_owned_error(monkeypatch, tmp_path, fault):
    folder = tmp_path / "data/astronomy"
    folder.mkdir(parents=True)
    name = "de441-planetary-0001-9999-v3"
    metadata = (DATA / (name + ".json")).read_bytes()
    manifest = json.loads(metadata)
    filename = manifest["chunks"][0]["file"]
    packed = (DATA / filename).read_bytes()
    if fault != "missing":
        raw = bytearray(packed)
        raw[len(raw) // 2] ^= 1
        packed = bytes(raw)
        (folder / filename).write_bytes(packed)
    if fault == "rehash":
        manifest["chunks"][0]["compressed_sha256"] = hashlib.sha256(packed).hexdigest()
        metadata = json.dumps(manifest).encode()
    (folder / (name + ".json")).write_bytes(metadata)
    de441_source._parameters.cache_clear()
    de441_source._coefficients.cache_clear()
    try:
        monkeypatch.setattr(de441_source, "files", lambda _: tmp_path)
        with pytest.raises(EphemerisSourceError) as error:
            de441_source.barycentric_state(
                "Pluto", manifest["source_TDB_JD_bounds"][0] - 2451545.0 + 1.0
            )
        assert error.value.reason == "jpl_kinematics_invalid"
    finally:
        de441_source._parameters.cache_clear()
        de441_source._coefficients.cache_clear()


def test_coherent_Earth_Moon_and_planets_keep_native_JPL_gates_at_all_source_cells():
    assert SOURCE_REFERENCE["source_position_gate_AU"] == 1e-12
    assert SOURCE_REFERENCE["source_velocity_gate_AU_per_TDB_day"] == 1e-13
    assert {r["body"] for r in SOURCE_REFERENCE["rows"]} == {
        "Earth",
        "Moon",
        "Sun",
        "Mercury",
        "Venus",
        "Mars",
        "Jupiter",
        "Saturn",
        "Uranus",
        "Neptune",
        "Pluto",
    }
    for row in sorted(SOURCE_REFERENCE["rows"], key=lambda r: r["source_TDB_JD"]):
        state = de441_source.barycentric_state(
            row["body"], row["source_TDB_JD"] - 2451545.0
        )
        expected = row["ICRF_barycentric_AU_and_AU_TDB_day"]
        assert (
            max(abs(a - b) for a, b in zip(state.position, expected[:3])) <= 1e-12
        ), row["id"]
        assert (
            max(abs(a - b) for a, b in zip(state.velocity, expected[3:])) <= 1e-13
        ), row["id"]


def test_source_acceleration_matches_original_word_high_precision_polynomials():
    assert len(ACCELERATION_REFERENCE["rows"]) == 2585
    for row in ACCELERATION_REFERENCE["rows"]:
        actual = de441_source.barycentric_state(
            row["body"], row["source_TDB_JD"] - 2451545.0
        )
        expected = list(
            map(float, row["ICRF_barycentric_AU_and_AU_TDB_day_and_AU_TDB_day2"])
        )
        for values, start, line in (
            (actual.position, 0, 1e-12),
            (actual.velocity, 3, 1e-13),
            (
                actual.acceleration,
                6,
                ACCELERATION_REFERENCE["gate_acceleration_AU_per_TDB_day2"],
            ),
        ):
            assert (
                max(abs(a - b) for a, b in zip(values, expected[start : start + 3]))
                <= line
            ), (row["body"], row["source_TDB_JD"], start)
