"""Independent complete-grid sky axes and an audit that cannot hide failures."""

import copy
import json
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from scripts.audit_western_houses import audit, separation

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/western-houses-erfa-astrolog.json").read_text()
)


@pytest.mark.parametrize("case", REFERENCE["cases"])
def test_independent_erfa_vector_axes_across_the_complete_frozen_grid(case):
    p = case["input"]
    _, angles = runtime.ephemeris_call(
        "houses_ex", p["jd_ut1"], p["latitude"], p["longitude"], b"E"
    )
    for i, key in enumerate(("ascendant", "midheaven")):
        assert (
            separation(angles[i], case["erfa_vector_angles"][key])
            <= REFERENCE["protocol"]["angle_tolerance_arcseconds"]
        )


def test_full_independent_audit_retains_future_and_polar_cases_and_detects_false_angles():
    result = audit(REFERENCE)
    assert result["angle_count"] == len(REFERENCE["cases"]) == 126
    assert result["house_comparison_count"] == 13 * 126
    assert sum(result["house_status_counts"].values()) == 13 * 126
    control = copy.deepcopy(REFERENCE)
    control["cases"][0]["erfa_vector_angles"]["ascendant"] += 10
    negative = audit(control)
    assert negative["angles"][0]["matched"] is False
    assert negative["all_independent_checks_passed"] is False
