"""Pinned mathematical reference, failure retention and real-source guard faults."""

import importlib
import importlib.machinery
import importlib.util
import json
import math
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

import fatebridge.core.output_charts as outputs
from fatebridge.core.astro import position_motion, runtime
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.utils.errors import EphemerisSourceError
from tests.ephemeris_case_runtime import (
    native_ephemeris_files_module as native_ephemeris_files_module,
)
from tests.reference_data import verify_source_files

pytestmark = pytest.mark.usefixtures("native_ephemeris_files_module")

FIXTURE = Path(__file__).parent / "data/astro/decimal_reduction"
REFERENCE = json.loads((FIXTURE / "independent-model-reference.json").read_text())
PRIMARY_FAILURES = json.loads(
    (FIXTURE / "primary-stage-failure-inputs.json").read_text()
)


def reduction():
    try:
        return importlib.import_module("fatebridge.core.astro.solar_decimal")
    except ModuleNotFoundError:
        pytest.fail("The checked decimal source-reduction service is missing")


def test_reference_producer_and_original_failed_rows_remain_sealed():
    verify_source_files(FIXTURE)
    assert REFERENCE["candidate_imports"] is False
    assert REFERENCE["independent_ephemeris"] is False
    assert REFERENCE["independent_model_reduction"] is True
    assert len(REFERENCE["rows"]) == 68
    assert all(row["reference_converged"] for row in REFERENCE["rows"])
    assert len(PRIMARY_FAILURES) == 2


@pytest.mark.parametrize(
    "row",
    REFERENCE["rows"],
    ids=lambda r: f"{r['body']}-{r['julian_day_tt']}-{r['frame']}",
)
def test_complete_motion_matches_the_sealed_source_model_and_retains_old_attempts(row):
    swe = runtime.swe
    sidereal = row["frame"] == "Sidereal"
    runtime.ephemeris_call("set_sid_mode", swe.SIDM_LAHIRI, 0, 0)
    raw, returned = runtime.ephemeris_call(
        "calc",
        row["julian_day_tt"],
        getattr(swe, row["body"].upper()),
        swe.FLG_SWIEPH | swe.FLG_SPEED | (swe.FLG_SIDEREAL if sidereal else 0),
    )
    assert runtime.ephemeris_model_from_retflag(returned) == "swieph"
    trace = PhysicalEphemerisTrace()
    trace.observe(row["body"], "swieph")
    rate, policy = position_motion.complete_position_rate(
        row["body"],
        row["julian_day_tt"],
        raw,
        "swieph",
        sidereal=sidereal,
        source_trace=trace,
    )
    expected = float(row["estimates"][-1]["rate_degrees_per_day"])
    assert abs(rate - expected) * 3600 <= 0.002
    assert policy["convergence_line_arcsec_per_day"] == 0.0002
    key = [row["body"], row["julian_day_tt"], row["frame"]]
    if key in PRIMARY_FAILURES:
        assert policy["primary_attempt"]["status"] == "not_converged"
        assert (
            policy["sampling_stabilization"]["symmetric_stabilized_attempt"]["status"]
            == "not_converged"
        )
        assert policy["decimal_reduction_previous_attempt"]["status"] == "not_converged"
        branch = policy["source_branch_motion"]
        assert branch["required_consecutive_levels"] == 3
        assert branch["levels"][-1]["passed"]
        assert branch["levels"][-1]["disagreement_arcsec_per_day"] <= 0.0002
        assert len(branch["levels"][-1]["eligible_directions"]) == 2
        receipt = branch["decimal_reduction"]
        assert receipt["precision_decimal_digits"] == 50
        assert receipt["displayed_native_position_changed"] is False
        assert receipt["independent_astronomical_accuracy_certified"] is False
    outputs.CompletePositionMotion.model_validate(policy)
    trace.finish()


def test_stable_vector_identities_retain_exact_small_separations():
    service = reduction()
    t = Fraction(1, 10**12)
    qx, qy = (1 - t * t) / (1 + t * t), 2 * t / (1 + t * t)
    expected = 2 * t * t / (1 + t * t)
    assert 1 - float(qx) == 0  # Binary64 subtractive form loses this separation.
    with localcontext() as ctx:
        ctx.prec = 50
        q = [
            Decimal(qx.numerator) / qx.denominator,
            Decimal(qy.numerator) / qy.denominator,
            Decimal(0),
        ]
        e = [Decimal(-1), Decimal(0), Decimal(0)]
        addition = service.add(q, e)
        denominator = service.dot(addition, addition) / 2
        exact = Decimal(expected.numerator) / expected.denominator
        assert abs(denominator / exact - 1) < Decimal("1e-25")
        assert service.norm(service.cross(q, e)) > 0


def test_checked_frame_rotation_preserves_a_known_proper_rotation():
    service = reduction()
    axes = [[Decimal(int(i == j)) for i in range(3)] for j in range(3)]
    turned = [axes[1], [-v for v in axes[0]], axes[2]]
    value, error = service.rotate(
        [Decimal(2), Decimal(3), Decimal(5)], list(zip(axes, turned))
    )
    assert value == [Decimal(-3), Decimal(2), Decimal(5)]
    assert error == 0


@pytest.mark.parametrize("fault", ["singular", "reflected", "sheared"])
def test_bad_frame_basis_never_authorizes_a_rate(fault):
    service = reduction()
    axes = [[Decimal(int(i == j)) for i in range(3)] for j in range(3)]
    fixed, shown = axes, [row[:] for row in axes]
    if fault == "singular":
        fixed = [axes[0], axes[0], axes[2]]
    elif fault == "reflected":
        shown[0] = [-v for v in shown[0]]
    else:
        shown[1][0] = Decimal(1)
    with pytest.raises(EphemerisSourceError):
        service.rotate(axes[0], list(zip(fixed, shown)))


def setup_source():
    swe = runtime.swe
    epoch = 2451673.659770648
    runtime.ephemeris_call("calc", epoch, swe.MERCURY, swe.FLG_SWIEPH | swe.FLG_SPEED)
    trace = PhysicalEphemerisTrace()
    center = trace.observe("decimal_fault_center", "swieph")
    return epoch, trace, center


@pytest.mark.parametrize(
    "fault,reason",
    [
        ("frame", "coordinate_contract_changed"),
        ("speed", "coordinate_contract_changed"),
        ("model", "model_changed"),
        ("nan", "coordinate_values_unavailable"),
        ("short", "coordinate_values_unavailable"),
    ],
)
def test_decimal_auxiliary_calls_retain_native_flag_value_and_model_guards(
    fault, reason, monkeypatch
):
    service = reduction()
    epoch, trace, center = setup_source()
    original = runtime.ephemeris_call

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[0] != "calc":
            return result
        values, returned = result
        if fault == "frame":
            returned &= ~runtime.swe.FLG_EQUATORIAL
        elif fault == "speed":
            returned &= ~runtime.swe.FLG_SPEED
        elif fault == "model":
            returned = (returned & ~runtime.swe.FLG_SWIEPH) | runtime.swe.FLG_MOSEPH
        elif fault == "nan":
            values = (math.nan, *values[1:])
        else:
            values = values[:5]
        return values, returned

    monkeypatch.setattr(service.runtime, "ephemeris_call", changed)
    with pytest.raises(EphemerisSourceError) as caught:
        service.reduced_longitude(
            "Mercury",
            epoch,
            sidereal=False,
            trace=trace,
            contexts={},
            prefix="fault",
            center_source=center,
        )
    assert caught.value.reason == reason


def test_decimal_auxiliary_calls_reject_changed_physical_context():
    service = reduction()
    epoch, trace, center = setup_source()
    wrong = {**center, "file_ids": ["changed"]}
    with pytest.raises(EphemerisSourceError) as caught:
        service.reduced_longitude(
            "Mercury",
            epoch,
            sidereal=False,
            trace=trace,
            contexts={},
            prefix="fault",
            center_source=wrong,
        )
    assert caught.value.reason == "dependency_source_window_incoherent"


def test_solar_mass_profile_cannot_be_silently_replaced(monkeypatch):
    service = reduction()
    monkeypatch.setattr(
        service,
        "files",
        lambda _: SimpleNamespace(
            joinpath=lambda _: SimpleNamespace(read_bytes=lambda: b"{}")
        ),
    )
    with pytest.raises(EphemerisSourceError) as caught:
        service.mass_profile()
    assert caught.value.reason == "coordinate_values_unavailable"


@pytest.mark.parametrize(
    "field",
    [
        "displayed_native_position_changed",
        "independent_astronomical_accuracy_certified",
    ],
)
def test_receipt_cannot_claim_an_unperformed_position_or_accuracy_change(field):
    model = getattr(outputs, "DecimalApparentReduction", None)
    assert model is not None
    with pytest.raises(ValueError):
        model.model_validate({field: True})
