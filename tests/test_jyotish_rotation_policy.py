"""The explicit UT1 source survives fresh exec and describes actual D1 axes."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core import astro_models as rotation
from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.iers_ut1 import use_ut1_source
from fatebridge.core.jyotish import positions
from fatebridge.core.output_jyotish import JyotishProfile
from tests.test_jyotish_sources import restore_runtime  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = json.loads(
    (ROOT / "tests/fixtures/jyotish-rotation-c04-controls-v1.json").read_text()
)


def subject(stamp):
    moment = datetime.fromisoformat(stamp)
    return build_astro_birth_info(
        birth_year=moment.year,
        birth_month=moment.month,
        birth_day=moment.day,
        birth_hour=moment.hour,
        birth_minute=moment.minute,
        birth_second=moment.second,
        birth_microsecond=moment.microsecond,
        birth_timezone="UTC",
        birth_latitude=40,
        birth_longitude=0,
    )


@pytest.mark.parametrize("row", REFERENCE["rows"], ids=lambda r: r["utc"])
def test_explicit_c04_reaches_actual_private_worker_and_literal_epoch(row):
    assert (
        hashlib.sha256(
            (ROOT / "tests/fixtures/jyotish-rotation-c04-controls-v1.json").read_bytes()
        ).hexdigest()
        == "c134cc2000bf4a948982bc91143d3ab4b53c16c0abf0aab2bedd28d82ec9fd77"
    )
    e.configure_ephemeris_path(str(ROOT / "ephe"))
    with use_ut1_source("iers_c04"):
        result = positions(subject(row["utc"]), ephemeris_policy="require_data_files")
    assert result["native_execution_context"]["mechanism"] == "fresh_exec_process"
    assert abs(result["julian_day_tt"] - row["expected_jd_tt"]) * 86400 <= 0.0002
    assert abs(result["julian_day_ut"] - row["expected_jd_ut1"]) * 86400 <= 0.0002
    policy = result["earth_rotation"]
    assert policy["policy_id"] == "fatebridge_standard_rotation_v3"
    assert policy["measured_eop_applied"] is True
    assert policy["tt_argument_policy"] == "selected_IERS_C04_UT1_to_TT"
    assert policy["model_epoch_jd_tt"] == result["julian_day_tt"]
    assert policy["model_epoch_jd_ut1"] == result["julian_day_ut"]
    evidence = policy["ut1_reference"]
    assert evidence["asset_sha256"] == REFERENCE["asset_sha256"]
    assert evidence["source_sha256"] == REFERENCE["source_sha256"]
    assert evidence["source_mjd"] == [r[0] for r in row["source_rows"]]
    assert evidence["query_julian_day_tt"] == result["julian_day_tt"]
    assert evidence["query_julian_day_ut1"] == result["julian_day_ut"]
    assert evidence["absolute_accuracy_certified"] is False
    assert (
        result["time_scale_context"]["houses_timescale"]
        == "UT1_selected_final_C04_daily_series"
    )


@pytest.mark.parametrize(
    "stamp", ["1961-01-01T00:00:00+00:00", "2050-01-01T00:00:00+00:00"]
)
def test_selected_c04_outside_coverage_never_silently_uses_delta_t(stamp):
    e.configure_ephemeris_path(str(ROOT / "ephe"))
    with use_ut1_source("iers_c04"), pytest.raises(ValueError, match="C04"):
        positions(subject(stamp), ephemeris_policy="require_data_files")


def test_default_worker_after_c04_does_not_inherit_its_source():
    e.configure_ephemeris_path(str(ROOT / "ephe"))
    birth = subject("2000-01-01T12:00:00+00:00")
    with use_ut1_source("iers_c04"):
        selected = positions(birth, ephemeris_policy="require_data_files")
    normal = positions(birth, ephemeris_policy="require_data_files")
    assert selected["earth_rotation"]["measured_eop_applied"] is True
    assert normal["earth_rotation"]["measured_eop_applied"] is False
    assert "ut1_reference" not in normal["earth_rotation"]
    assert (
        normal["earth_rotation"]["tt_argument_policy"]
        == "native_internal_sidereal_time_argument"
    )
    assert normal["time_scale_context"]["houses_timescale"] == "UT1_model_estimate"
    assert normal["julian_day_tt"] == selected["julian_day_tt"]


@pytest.mark.native_engine_fault
@pytest.mark.parametrize(
    "year,source",
    [
        (1800, "swiss_delta_t"),
        (2024, "swiss_delta_t"),
        (2050, "swiss_delta_t"),
        (2000, "iers_c04"),
    ],
)
def test_rotation_tt_observation_is_bound_to_the_reported_point(
    monkeypatch, year, source
):
    e.configure_ephemeris_path(str(ROOT / "ephe"))
    actual = rotation._rotation_tt
    observed = []

    def tracked(module, ut1):
        tt = actual(module, ut1)
        observed.append((ut1, tt))
        return tt

    monkeypatch.setattr(rotation, "_rotation_tt", tracked)
    with use_ut1_source(source):
        result = positions(
            subject(f"{year:04d}-03-20T12:00:00+00:00"),
            ephemeris_policy="require_data_files",
        )
    policy = result["earth_rotation"]
    if year == 2024:
        assert policy["implementation"] == "native_public_API"
        assert policy["tt_argument_policy"] == "native_internal_sidereal_time_argument"
    else:
        assert any(
            abs(ut - result["julian_day_ut"]) * 86400 <= 0.0002
            and abs(tt - result["julian_day_tt"]) * 86400 <= 0.0002
            for ut, tt in observed
        )
        assert policy["tt_argument_policy"] == (
            "selected_IERS_C04_UT1_to_TT"
            if source == "iers_c04"
            else "shared_default_DeltaT_minus1_before1960_SWIEPH_from1960"
        )


@pytest.mark.parametrize(
    "invalid",
    [
        {"earth_rotation": {"tt_argument_policy": 5}},
        {"local_apparent_sidereal_meridian_degrees": 360},
    ],
)
def test_corrupt_projected_rotation_evidence_is_rejected(invalid):
    with pytest.raises(ValidationError):
        JyotishProfile.model_validate(invalid)
