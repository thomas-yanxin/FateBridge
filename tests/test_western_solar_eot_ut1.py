"""Solar-clock rebasing uses the UT1 axis of the recorded instant.

References use standalone calendar arithmetic/native-model inversion, not
FateBridge output. Both routes reuse the same96 development epochs.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.sensitivity import _sample_birth
from tests.ephemeris_case_runtime import (
    native_ephemeris_files_module as native_ephemeris_files_module,
)
from tests.reference_data import verify_source_files

pytestmark = pytest.mark.usefixtures("native_ephemeris_files_module")

FIXTURE = Path(__file__).parent / "data/astro/solar_eot_ut1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())
COHERENT = json.loads(
    (FIXTURE.parent / "solar_clock_coherence/reference.json").read_text()
)
COHERENT_BY_UTC = {
    row["utc"]: row for row in COHERENT["rows"] if row["source"] == "swiss_delta_t"
}
LINE_SECONDS = 0.0002


def test_independent_model_reference_identity():
    verify_source_files(FIXTURE)
    assert len(REFERENCE["rows"]) == 96
    assert REFERENCE["fatebridge_imported"] is False
    assert REFERENCE["independent_dynamical_model"] is False
    # Retain the original native time_equ model and its original threshold.
    # The adopted coherent-TT/GAST successor explicitly records both models.
    for row in REFERENCE["rows"]:
        successor = COHERENT_BY_UTC[row["utc"]]
        assert successor["jd_ut1"] == row["jd_ut1"]
        assert successor["jd_tt"] == row["jd_tt"]
        assert (
            abs(successor["original_native_time_equ_seconds"] - row["eot_seconds"])
            <= LINE_SECONDS
        )


@pytest.mark.parametrize(
    "route",
    [
        "nominal",
        "sensitivity_zero_offset",
        "sensitivity_forward_minute",
        "sensitivity_backward_minute",
    ],
)
@pytest.mark.parametrize("row", REFERENCE["rows"], ids=lambda r: r["utc"])
def test_rebase_matches_frozen_ut1_model(row, route):
    moment = datetime.fromisoformat(row["utc"])
    offset = {
        "sensitivity_forward_minute": timedelta(minutes=1),
        "sensitivity_backward_minute": timedelta(minutes=-1),
    }.get(route, timedelta())
    recorded = moment - offset
    birth = build_astro_birth_info(
        birth_year=recorded.year,
        birth_month=recorded.month,
        birth_day=recorded.day,
        birth_hour=recorded.hour,
        birth_minute=recorded.minute,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=40,
        use_true_solar_time=True,
    )
    if route != "nominal":
        birth = _sample_birth(birth, offset)
    actual_seconds = (birth.require_utc_datetime - moment).total_seconds()
    assert (
        abs(actual_seconds - COHERENT_BY_UTC[row["utc"]]["eot_seconds"]) <= LINE_SECONDS
    )
    assert birth.recorded_datetime == moment
