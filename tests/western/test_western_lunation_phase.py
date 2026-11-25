"""Actual-motion regression against frozen author-C and DE440/SOFA roots.

One synthetic40-day window covers all eight phase targets. It does not certify
other epochs, clock discontinuities, classical interpretations or prediction.
"""

import json
from datetime import datetime
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.ephemeris_runtime import preserve_ephemeris_path
from fatebridge.services.western_lifespan import calculate_lunation_phase


@pytest.mark.local_data
def test_lunation_phase_uses_actual_postbirth_ephemeris(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = Path(__file__).resolve().parents[1] / "data/progressed_lunation_v1"
    inputs = json.loads((data / "inputs.json").read_text())
    reference = json.loads((data / "expected-roots.json").read_text())
    birth = datetime.fromisoformat(inputs["birth_utc"])
    with preserve_ephemeris_path(), monkeypatch.context() as source_config:
        source_config.setenv(
            "SE_EPHE_PATH", str(Path(__file__).resolve().parents[2] / "ephe")
        )
        source_config.delenv("FATEBRIDGE_JPL_FILE", raising=False)
        result = calculate_lunation_phase(
            name="Frozen synthetic lunation control",
            birth_year=birth.year,
            birth_month=birth.month,
            birth_day=birth.day,
            birth_hour=birth.hour,
            birth_minute=birth.minute,
            birth_timezone="UTC",
            birth_longitude=0.0,
            birth_latitude=0.0,
            house_system="P",
            zodiac_type="Tropic",
            max_age_years=float(inputs["max_age_years"]),
        )
    assert "error" not in result
    payload = result["lunation_phase"]
    assert payload["method_id"] == "fatebridge_secondary_ephemeris_lunation_v1"
    assert "progression_rate_deg_per_year" not in payload
    assert "synodic_cycle_years" not in payload
    source = payload["physical_ephemeris_source"]
    assert {row["model"] for row in source["by_factor"].values()} == {"swieph"}
    expected_files = {
        asset["filename"]: asset["sha256"]
        for asset in reference["source_provenance"]["source_assets"]
        if asset["filename"].endswith(".se1")
    }
    assert {row["filename"]: row["sha256"] for row in source["files"]} == expected_files

    rows = payload["phase_ingresses"]
    native_roots = reference["roots"]["author_C"]
    independent_roots = reference["roots"]["DE440_SOFA"]
    assert len(rows) == len(native_roots) == len(independent_roots)
    assert [row["elongation_degree"] for row in rows] == [
        row["target"] for row in native_roots
    ]
    assert {row["elongation_degree"] for row in rows} == set(inputs["targets_degrees"])
    birth_day = Fraction(inputs["birth_utc_nominal_jd"])
    offset_days = Fraction(inputs["tt_minus_utc_seconds"]) / 86400
    for row, native, independent in zip(rows, native_roots, independent_roots):
        point = Fraction(row["progressed_julian_day_tt"])
        assert abs(point - Fraction(native["selected_tt"])) * 86400 <= Fraction(1, 1000)
        assert abs(point - Fraction(independent["selected_tt"])) * 86400 <= 60
        civil = row["progressed_utc_point"]
        civil_day = Fraction(int(civil["numerator"]), int(civil["denominator"]))
        assert civil_day == point - offset_days
        assert 0 < civil_day - birth_day <= Fraction(inputs["max_age_years"])
        assert row["ingress_age_years"] == native["display_age_years_3dp_nearest"]
        assert 0 <= Fraction(row["residual_degrees"]) <= Fraction(1, 100000000)
        low, high = row["source_root_bracket_tt"]
        assert low < high == row["progressed_julian_day_tt"]


@pytest.mark.local_data
@pytest.mark.parametrize(
    ("birth", "zone", "file_period", "first_tt", "first_age", "first_date", "count"),
    [
        (
            (1, 1, 1, 13, 59),
            "Etc/GMT-14",
            "00",
            1721427.964970462,
            2.344,
            "0001-01-03",
            10,
        ),
        (
            (9999, 12, 30, 12, 0),
            "UTC",
            "96",
            5373484.695935536,
            1.695,
            "+010000-01-01",
            11,
        ),
    ],
    ids=["birth-utc-year-zero", "cap-utc-year-10000"],
)
def test_lunation_phase_uses_extended_utc_calendar(
    monkeypatch: pytest.MonkeyPatch,
    birth: tuple[int, int, int, int, int],
    zone: str,
    file_period: str,
    first_tt: float,
    first_age: float,
    first_date: str,
    count: int,
) -> None:
    ephe = Path(__file__).resolve().parents[2] / "ephe"
    if not all(
        (ephe / f"{prefix}_{file_period}.se1").is_file() for prefix in ("sepl", "semo")
    ):
        pytest.skip(
            f"Swiss planetary and lunar files for period {file_period} required"
        )
    else:
        pass
    year, month, day, hour, minute = birth
    with preserve_ephemeris_path(), monkeypatch.context() as source_config:
        source_config.setenv("SE_EPHE_PATH", str(ephe))
        source_config.delenv("FATEBRIDGE_JPL_FILE", raising=False)
        result = calculate_lunation_phase(
            birth_year=year,
            birth_month=month,
            birth_day=day,
            birth_hour=hour,
            birth_minute=minute,
            birth_timezone=zone,
            birth_longitude=0.0,
            birth_latitude=0.0,
            house_system="W",
            max_age_years=40.0,
        )
    phase = result["lunation_phase"]
    source = phase["physical_ephemeris_source"]
    assert {row["model"] for row in source["by_factor"].values()} == {"swieph"}
    rows = phase["phase_ingresses"]
    assert len(rows) == count
    # Independent Swiss 2.10.03 C roots and matching clock inverse, R166.
    first = rows[0]
    tt_error = abs(Fraction(first["progressed_julian_day_tt"]) - Fraction(first_tt))
    assert tt_error * 86400 <= Fraction(1, 1000)
    assert first["ingress_age_years"] == first_age
    assert first["progressed_datetime_utc"].startswith(first_date + "T")
