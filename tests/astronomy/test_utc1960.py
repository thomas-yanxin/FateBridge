"""Compiled official SOFA epochs, including the previously missing 1960 UTC."""

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.historical_utc import (
    historical_tai_minus_utc,
    historical_utc_source,
    historical_utc_table,
    utc1960_table,
)
from fatebridge.core.astro.time_scales import datetime_from_tt, ephemeris_time
from fatebridge.core.human_design import chart_at
from fatebridge.core.jyotish import positions
from scripts.astronomy.build_utc1960_reference import SOURCE_FILES, build

REFERENCE = json.loads(
    (Path(__file__).parents[1] / "fixtures/historical-utc-sofa.json").read_text()
)
UTC = timezone.utc


def test_reference_generator_refuses_unpinned_source_before_compiling(tmp_path):
    for name in SOURCE_FILES:
        (tmp_path / name).write_bytes(b"not the official source")
    with pytest.raises(ValueError, match="pinned official release"):
        build(tmp_path, "compiler-must-not-be-invoked")


def test_all_planned_compiled_sofa_epochs_and_offsets():
    cases = REFERENCE["cases"]
    assert len(cases) == 233
    assert len({row["utc"] for row in cases}) == 233
    assert {row["utc"][:4] for row in cases} == {
        str(year) for year in range(1960, 1973)
    }
    failures = []
    for row in cases:
        assert row["statuses"] == [0, 0, 0, 0]
        moment = datetime.fromisoformat(row["utc"])
        actual = ephemeris_time(moment)
        delta = abs(math.fsum([actual.jd_tt, *(-p for p in row["tt_jd_parts"])]))
        if delta * 86400 > REFERENCE["comparison_tolerance_seconds"]:
            failures.append((row["utc"], delta * 86400))
        if moment.year < 1972:
            assert historical_tai_minus_utc(moment) == pytest.approx(
                row["tai_minus_utc_seconds"], abs=1e-10
            ), row["utc"]
    assert not failures


def test_sofa_supplement_does_not_rewrite_the_iers_source():
    assert REFERENCE["historical_coefficients"][1:] == historical_utc_table()["entries"]
    assert len(historical_utc_table()["entries"]) == 13
    assert utc1960_table()["entries"] == REFERENCE["historical_coefficients"][:1]
    assert utc1960_table()["valid_until"] == "1961-01-01"
    assert utc1960_table()["source_sha256"] == REFERENCE["source_file_sha256"]["dat.c"]


def test_1960_uses_the_full_fractional_day_and_correct_source():
    # Independent source-array constants; 1960 Jan 1 is MJD 36934.
    start = datetime(1960, 1, 1, tzinfo=UTC)
    assert historical_tai_minus_utc(start) == pytest.approx(0.943482, abs=1e-10)
    assert historical_tai_minus_utc(start + timedelta(hours=12)) == pytest.approx(
        0.944130, abs=1e-10
    )
    assert ephemeris_time(start).method == (
        "SOFA_1960_UTC_drift_to_TT_swiss_delta_t_to_UT1"
    )
    assert historical_utc_source(start)["source_url"] == REFERENCE["source_url"]
    local = start.astimezone(timezone(timedelta(hours=-1)))
    assert local.year == 1959
    assert historical_utc_source(local) == utc1960_table()
    assert (
        abs((datetime_from_tt(ephemeris_time(start).jd_tt) - start).total_seconds())
        < 0.0002
    )
    with pytest.raises(ValueError, match="aware"):
        historical_utc_source(start.replace(tzinfo=None))


def test_sofa_epoch_reaches_actual_human_design_calc(monkeypatch):
    # A fixed, independently compiled SOFA monthly clock, not a chart-derived
    # expected longitude. This assertion works with either actual backend.
    row = next(
        c for c in REFERENCE["cases"] if c["utc"] == "1960-06-15T12:34:56.125000+00:00"
    )
    moment = datetime.fromisoformat(row["utc"])
    expected_tt = math.fsum(row["tt_jd_parts"])
    original = runtime.ephemeris_call
    moon_epochs = []

    def observe(operation, *args, **kwargs):
        if operation == "calc" and args[1] == runtime.swe.MOON:
            moon_epochs.append(args[0])
        return original(operation, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", observe)
    chart = chart_at(moment)
    # The nominal birth/design pair remains first. Later Moon calls must be
    # exactly the published root-candidate epochs, each observed once.
    from fatebridge.validation.human_design_solar_root import verify_solar_root_context

    assert len(moon_epochs[:2]) == 2
    precision = chart["design_solver"]["numerical_precision"]
    declared = {chart["time_scales"]["personality"]["jd_tt"]} | {
        r["jd_tt"] for r in precision["design_body_endpoint_assessment"]["evaluations"]
    }
    family = precision["local_root_family"]
    if family is not None:
        declared.update(r["jd_tt"] for r in family["candidates"])
    assert len(moon_epochs) == len(declared)
    assert set(moon_epochs) == declared
    assert verify_solar_root_context(chart)["errors"] == []
    assert abs(moon_epochs[0] - expected_tt) * 86400 < 0.0002
    assert moon_epochs[1] == chart["time_scales"]["design"]["jd_tt"]
    assert chart["time_scales"]["personality"]["method"].startswith("SOFA_1960")


def test_shared_jyotish_context_does_not_mislabel_1960_as_ut1_input():
    birth = build_astro_birth_info(
        birth_year=1960,
        birth_month=6,
        birth_day=15,
        birth_hour=12,
        birth_minute=34,
        birth_timezone="UTC",
        birth_latitude=0,
        birth_longitude=0,
    )
    raw = positions(birth)
    assert raw["julian_day_utc"] is not None
    context = raw["time_scale_context"]
    assert context["method"].startswith("SOFA_1960")
    assert context["houses_timescale"] == "UT1_model_estimate"
    assert context["historical_utc_source"] == REFERENCE["source_url"]
    assert context["historical_utc_source_sha256"] == REFERENCE["source_sha256"]
