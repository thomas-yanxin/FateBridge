"""Independent standard rotation, frozen before observing candidate outputs.

ERFA reference generation imports neither FateBridge nor Swiss. Raw native
default-clock negative controls remain separate from the corrected native
house contract; a deliberately disabled adapter must fail this accuracy gate.
"""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime
from fatebridge.core.astro.ephemeris import _swisseph_angles
from fatebridge.core.astro_models import (
    MODERN_HALF_WINDOW_DAYS,
    MODERN_REFERENCE_JD_TT,
)

ROOT = Path(__file__).parents[1]
REFERENCE = json.loads(
    (ROOT / "tests/data/astrodice/tables/rotation-erfa.json").read_text()
)
PROTOCOL = REFERENCE["protocol"]
LOCATIONS = [
    (case, location) for case in REFERENCE["cases"] for location in case["locations"]
]


def error_arcseconds(a, b):
    return abs((a - b + 180) % 360 - 180) * 3600


def rotation_matches(case):
    actual = ephemeris_runtime.ephemeris_call("sidtime", case["jd_ut1"]) * 15
    return (
        error_arcseconds(actual, case["gast_degrees"])
        <= PROTOCOL["gast_tolerance_arcseconds"]
    )


def test_reference_keeps_the_prepared_protocol_and_independent_generator():
    assert (
        REFERENCE["protocol_sha256"]
        == hashlib.sha256(
            (ROOT / "tests/data/astrodice/tables/rotation-protocol.json").read_bytes()
        ).hexdigest()
    )
    assert (
        REFERENCE["generator_sha256"]
        == hashlib.sha256(
            (ROOT / "scripts/gen_astrodice_rotation_reference.py").read_bytes()
        ).hexdigest()
    )
    assert REFERENCE["forbidden_implementation_imports"] == []
    assert len(REFERENCE["cases"]) == 39 and len(LOCATIONS) == 195
    assert {e["civil_utc"][:4] for e in REFERENCE["cases"]} >= {
        "1800",
        "2050",
        "2099",
        "2200",
    }
    assert PROTOCOL["gast_tolerance_arcseconds"] == 0.02
    assert PROTOCOL["angle_tolerance_arcseconds"] == 1.0


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: c["civil_utc"])
def test_managed_apparent_sidereal_time_matches_independent_erfa(case):
    assert rotation_matches(case)


@pytest.mark.parametrize("case,location", LOCATIONS)
def test_core_tropical_axes_match_independent_erfa_vector_geometry(case, location):
    result = _swisseph_angles(
        case["jd_ut1"], location["longitude"], location["latitude"]
    )
    assert result is not None
    for name in ["ascendant", "midheaven"]:
        assert (
            error_arcseconds(result[name], location["axes"][name])
            <= PROTOCOL["angle_tolerance_arcseconds"]
        )


@pytest.mark.parametrize("date", ["2050-12-21", "2099-09-23"])
def test_disabling_rotation_adapter_is_detected_by_the_same_erfa_gate(
    monkeypatch, date
):
    case = next(
        c for c in REFERENCE["cases"] if c["civil_utc"].startswith(date + "T12:00")
    )
    assert rotation_matches(case)
    monkeypatch.setattr(
        ephemeris_runtime,
        "native_rotation_call",
        lambda module, operation, args, kwargs: getattr(module, operation)(
            *args, **kwargs
        ),
    )
    assert not rotation_matches(case)


def test_inventing_a_ten_arcsecond_reference_shift_is_detected():
    case = REFERENCE["cases"][0]
    assert rotation_matches(case)
    assert not rotation_matches(
        {**case, "gast_degrees": case["gast_degrees"] + 10 / 3600}
    )


def adoption_edge_discontinuity_arcseconds(boundary_tt):
    swe = ephemeris_runtime.swe
    ut1 = boundary_tt
    for _ in range(5):
        ut1 = boundary_tt - swe.deltat_ex(ut1, swe.FLG_SWIEPH)
    before, after = ut1 - 0.001 / 86400, ut1 + 0.001 / 86400
    left = ephemeris_runtime.ephemeris_call("sidtime", before) * 15
    right = ephemeris_runtime.ephemeris_call("sidtime", after) * 15
    # Subtract nominal rotation over this ~2ms bracket. Precession/nutation
    # change over 2ms is negligible relative to the predeclared 0.02" gate.
    advance = (right - left + 180) % 360 - 180
    nominal_rotation = 360.98564736629 * (after - before)
    return abs(advance - nominal_rotation) * 3600


@pytest.mark.parametrize("sign", [-1, 1])
def test_adoption_edge_has_no_resolvable_phase_jump(sign):
    boundary = MODERN_REFERENCE_JD_TT + sign * MODERN_HALF_WINDOW_DAYS
    assert (
        adoption_edge_discontinuity_arcseconds(boundary)
        <= PROTOCOL["gast_tolerance_arcseconds"]
    )


@pytest.mark.parametrize("sign", [-1, 1])
def test_old_hard_switch_is_detected_at_both_adoption_edges(monkeypatch, sign):
    import fatebridge.core.astro_models as models

    boundary = MODERN_REFERENCE_JD_TT + sign * MODERN_HALF_WINDOW_DAYS
    assert (
        adoption_edge_discontinuity_arcseconds(boundary)
        <= PROTOCOL["gast_tolerance_arcseconds"]
    )
    standard = models._standard_correction

    def old_correction(module, jd_ut1):
        tt = jd_ut1 + module.deltat_ex(jd_ut1, module.FLG_SWIEPH)
        return (
            standard(module, jd_ut1) if models.selected_sidereal_model(tt) == 3 else 0
        )

    monkeypatch.setattr(models, "_correction", old_correction)
    assert (
        adoption_edge_discontinuity_arcseconds(boundary)
        > PROTOCOL["gast_tolerance_arcseconds"]
    )
