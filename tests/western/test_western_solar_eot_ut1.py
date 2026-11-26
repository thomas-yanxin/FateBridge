"""Solar-clock rebasing uses the UT1 axis of the recorded instant.

References use standalone calendar arithmetic/native-model inversion, not
FateBridge output. Both routes reuse the same96 development epochs.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tests.support.ephemeris_case_runtime import (
    native_ephemeris_files_module as native_ephemeris_files_module,
)
from tests.support.reference_data import verify_source_files
from tests.support.solar_clock_grid import (
    civil_solar_birth,
    verify_recorded_grid_solar_reset,
)

pytestmark = pytest.mark.usefixtures("native_ephemeris_files_module")

FIXTURE = Path(__file__).parents[1] / "data/astro/solar_eot_ut1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())
COHERENT = json.loads(
    (FIXTURE.parent / "solar_clock_coherence/reference.json").read_text()
)
COHERENT_BY_UTC = {
    row["utc"]: row for row in COHERENT["rows"] if row["source"] == "swiss_delta_t"
}
COHERENT_TT_BY_ID = {
    row["id"]: row["tt_days"]
    for row in json.loads(
        (
            FIXTURE.parent / "solar_clock_coherence/same-definition-reference.json"
        ).read_text()
    )["rows"]
}
LINE_SECONDS = 0.0002


def test_independent_model_reference_identity() -> None:
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
def test_rebase_matches_frozen_ut1_model(row, route: str) -> None:
    moment = datetime.fromisoformat(row["utc"])
    offset_seconds = {
        "sensitivity_forward_minute": 60,
        "sensitivity_backward_minute": -60,
    }.get(route, 0)
    recorded = moment - timedelta(seconds=offset_seconds)
    birth = civil_solar_birth(recorded)
    coherent = COHERENT_BY_UTC[row["utc"]]
    if route == "nominal":
        actual = birth.require_utc_datetime
        assert birth.recorded_datetime == moment
    else:
        actual = verify_recorded_grid_solar_reset(
            birth,
            moment,
            offset_seconds,
            COHERENT_TT_BY_ID[coherent["id"]],
            coherent["eot_seconds"],
            LINE_SECONDS,
        )
    actual_seconds = (actual - moment).total_seconds()
    assert abs(actual_seconds - coherent["eot_seconds"]) <= LINE_SECONDS
