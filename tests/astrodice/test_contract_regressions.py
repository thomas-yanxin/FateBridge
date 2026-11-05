"""Related contract regressions with shared imports; original cases retained."""

import json
import math
from fractions import Fraction as Q
from math import isqrt

import pytest

from fatebridge.core.astro import ephemeris
from fatebridge.core.astro import lunar_source_window as window
from fatebridge.core.astro import runtime
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.zodiac import native_lahiri_positions
from fatebridge.utils.errors import EphemerisSourceError
from scripts.astrodice.astrodice_clock_interval import BITS, SCALE, A, I
from scripts.astrodice.astrodice_curve_math import (
    affine,
    bernstein,
    cheb_power,
    derivative,
    evaluate,
    leaves,
    metrics,
    pi,
)
from scripts.astrodice.audit_astrodice_horizons_wide_reference import DAY_US, input_tick
from scripts.astrodice.gen_astrodice_horizons_wide import (
    calendar_label,
    julian_input_label,
    wire_epochs,
)
from scripts.astrodice.verify_astrodice_compressed_curve import (
    B,
    binary64,
    cover,
    leaf_hulls,
    swe_chebyshev,
    vector_metrics,
)
from scripts.astrodice.verify_astrodice_observer_timescale import (
    expected_clock,
    inspect,
)
from tests.astrodice.test_astrodice_observer_timescale import (
    CASE,
    PLAN,
    calibration,
    raw,
)


@pytest.mark.parametrize("encoding", ["JD", "MJD", "CAL"])
def test_calendar_and_numeric_paths_keep_identical_guard_and_primary_epochs(encoding):
    center = input_tick("8103ad-Jul-26 18:51:11.123456")
    primary = [center + t * 1000000 for t in [-1435, 0, 1435]]
    plan = {
        "first_tlist_epoch_guard": {"method_id": "integer_jd_prefix_v1"},
        "reference_parameters": {"TLIST_TYPE": repr(encoding)},
        "maximum_labels_per_batch": 19,
    }
    wire, auxiliary = wire_epochs(plan, primary)
    assert wire == [auxiliary, *primary]
    # An independently fixed civil/JD identity: no calendar-midnight substitute.
    assert calendar_label(auxiliary) == "8103ad-Jul-25 12:00:00.000000"
    assert Q(julian_input_label(auxiliary)) == 4680825
    assert Q(julian_input_label(auxiliary, modified=True)) == Q(4561649, 2)
    for epoch in wire:
        assert input_tick(calendar_label(epoch)) == epoch
        assert abs(
            (Q(julian_input_label(epoch)) - Q(3442849, 2)) * DAY_US - epoch
        ) <= Q(1, 10**30)


def test_calendar_guard_does_not_admit_an_undocumented_encoding():
    plan = {
        "first_tlist_epoch_guard": {"method_id": "integer_jd_prefix_v1"},
        "reference_parameters": {"TLIST_TYPE": "'SECONDS'"},
        "maximum_labels_per_batch": 19,
    }
    with pytest.raises(ValueError, match="guard protocol"):
        wire_epochs(plan, [input_tick("2000ad-Jan-01 12:00:00.000000")])


@pytest.mark.parametrize(
    "bounds", [(Q(-7, 3), Q(-1, 7)), (Q(-1, 3), Q(8, 7)), (Q(1, 3), Q(8, 7))]
)
def test_all_rational_corners_are_enclosed_by_signed_arithmetic(bounds):
    a = I(*bounds)
    for other in [(Q(-8, 11), Q(-2, 11)), (Q(2, 11), Q(8, 11))]:
        b = I(*other)
        for x in bounds:
            for y in other:
                assert (a + b).contains(x + y)
                assert (a - b).contains(x - y)
                assert (a * b).contains(x * y)
                assert (a / b).contains(x / y)
        assert a.square().contains(bounds[0] ** 2)
        assert a.square().contains(bounds[1] ** 2)
        if bounds[0] <= 0 <= bounds[1]:
            assert a.square().contains(0)


@pytest.mark.parametrize("value", [Q(0), Q(1, 3), Q(2), Q(10**30, 7)])
def test_integer_square_root_proves_outward_endpoints(value):
    a = I(value)
    result = a.sqrt()
    low, high = result.bounds()
    assert low**2 <= value <= high**2
    assert result.lo == isqrt(a.lo * SCALE)
    assert (result.hi - 1) ** 2 < a.hi * SCALE <= result.hi**2 or result.hi == 0


def test_reciprocal_requires_a_proven_nonzero_denominator():
    with pytest.raises(ValueError, match="contains zero"):
        1 / I(-Q(1, 10**80), Q(1, 10**80))
    with pytest.raises(ValueError, match="Reversed"):
        I(2, 1)
    with pytest.raises(ValueError, match="Negative"):
        I(-1, 1).sqrt()


def test_grid_does_not_lose_small_epoch_shifts_at_far_future_JD():
    epoch = Q(4680826) + Q(67871, 86400)
    shifted = I(epoch + Q(1, 86400000000))
    assert shifted.contains(epoch + Q(1, 86400000000))
    assert not shifted.contains(epoch)
    assert BITS == 256


def test_jet_derivative_is_enclosed_through_quotient_and_square_root():
    t = A(I(Q(1, 3), Q(2, 3)), 1)
    # f(t)=sqrt(t*t+1)/(t+2). Independent exact derivative comparison.
    f = (t * t + 1).sqrt() / (t + 2)
    for x in [Q(1, 3), Q(1, 2), Q(2, 3)]:
        root = I(x * x + 1).sqrt()
        expected = (2 * x - 1) / (root * (x + 2) * (x + 2))
        assert f.d.lo <= expected.lo <= expected.hi <= f.d.hi


def test_derivative_at_a_singular_sqrt_cannot_be_silently_certified():
    with pytest.raises(ValueError, match="Nondifferentiable"):
        A(I(0, 1), 1).sqrt()


@pytest.mark.parametrize(
    "polynomial",
    [
        [Q(7)],
        [Q(), Q(1)],
        [Q(1), Q(-2), Q(1)],
        [Q(3, 7), Q(-5, 11), Q(7, 13), Q(-9, 17)],
    ],
)
@pytest.mark.parametrize("depth", [1, 3, 5])
def test_integer_blossom_equals_exact_subdivision_control_hulls(polynomial, depth):
    coefficients = bernstein(polynomial)
    expected = [(min(c), max(c)) for c in leaves(coefficients, depth)]
    assert leaf_hulls(tuple(coefficients), depth) == expected


def test_manual_binary64_ties_to_even():
    assert binary64(1 + Q(1, 2**53)) == 1
    assert binary64(1 + Q(3, 2**53)) == 1 + Q(1, 2**51)
    assert binary64(Q(1, 2**30)) == Q(1, 2**30)


def test_source_polynomial_normalizer_is_defined_at_header_grid_limits():
    x = 1 + Q(1, 2**42)
    value, velocity = swe_chebyshev([Q(2), Q(), Q(), Q(1)], x)
    assert value == 2 + 4 * x**3 - 3 * x
    assert velocity == 12 * x * x - 3


def test_independent_higher_precision_metric_is_contained():
    fields = {
        "q": [Q(1), Q(1, 3), Q(1, 5)],
        "w": [Q(-1, 17), Q(1, 19), Q(2, 23)],
        "e": [Q(1, 10**8), Q(-1, 10**9), Q(2, 10**10)],
        "f": [Q(-1, 10**8), Q(2, 10**9), Q(3, 10**10)],
    }
    scales = []
    expected = metrics(
        **{k: list(map(I, v)) for k, v in fields.items()}, audit_scales=scales
    )
    actual = vector_metrics(
        **{k: list(map(B, v)) for k, v in fields.items()}, scales=scales
    )
    cover(actual, [list(map(str, x.bounds())) for x in expected])
    with pytest.raises(ValueError):
        cover(actual, [["0", "0"], ["0", "0"]])


def test_independent_metric_rejects_nonpositive_scaling():
    with pytest.raises(ValueError, match="positive"):
        vector_metrics(
            [B(1), B(), B()], [B()] * 3, [B()] * 3, [B()] * 3, ["1", "1", "1", "0"]
        )


def test_native_and_jpl_constant_conventions_and_chebyshev_derivative():
    assert cheb_power([4, 0, 0, 1], True) == [2, -3, 0, 4]
    assert cheb_power([4, 0, 0, 1], False) == [4, -3, 0, 4]
    assert derivative(cheb_power([4, 0, 0, 1], True), Q(2)) == [Q(-3, 2), 0, 6]


def test_exact_affine_composition_for_nonunit_source_span():
    p = [Q(3), Q(-2), Q(5), Q(7)]
    a, b = Q(11, 13), Q(17, 19)
    composed = affine(p, a, b)
    for u in (Q(), Q(1, 7), Q(1, 2), Q(1)):
        assert evaluate(composed, u) == evaluate(p, a + b * u)


def test_bernstein_hull_and_complete_fixed_subdivision():
    controls = bernstein([Q(), Q(1), Q(-1)])
    assert controls == [0, Q(1, 2), 0]
    nodes = leaves(controls, 5)
    assert len(nodes) == 32
    for j, row in enumerate(nodes):
        for u in (Q(j, 32), Q(2 * j + 1, 64), Q(j + 1, 32)):
            assert min(row) <= u * (1 - u) <= max(row)
    assert all(a[-1] == b[0] for a, b in zip(nodes, nodes[1:]))


def test_radial_position_and_velocity_changes_have_no_direction_error():
    values = metrics(
        list(map(I, [1, 0, 0])),
        list(map(I, [2, 0, 0])),
        list(map(I, [1, 0, 0])),
        list(map(I, [7, 0, 0])),
    )
    assert all(v.contains(0) and v.absolute_upper() < Q(1, 10**60) for v in values)


def test_known_transverse_rate_change_has_exact_radian_norm():
    position, rate = metrics(
        list(map(I, [1, 0, 0])),
        list(map(I, [0, 1, 0])),
        list(map(I, [0, 0, 0])),
        [I(0), I(Q(1, 10)), I(0)],
    )
    assert position.contains(0)
    expected = Q(64800) / pi()
    lo, hi = expected.bounds()
    assert rate.bounds()[0] <= lo <= hi <= rate.bounds()[1]


def test_zero_radius_cannot_receive_an_error_certificate():
    with pytest.raises(ValueError):
        metrics([I()] * 3, [I()] * 3, [I()] * 3, [I()] * 3)


def test_nonlinear_complete_leaf_ranges_cover_direct_unit_vector_derivatives():
    fields = {
        "q": [[Q(1)], [Q(), Q(1, 8)], [Q(1, 2)]],
        "e": [[Q(1, 10**6), Q(), Q(-1, 10**6)], [Q(), Q(2, 10**6)], [Q()]],
    }
    fields["w"] = [derivative(p, Q(1)) for p in fields["q"]]
    fields["f"] = [derivative(p, Q(1)) for p in fields["e"]]
    nodes = {k: [leaves(bernstein(p), 5) for p in v] for k, v in fields.items()}

    def direction(p, v):
        r = math.hypot(*p)
        u = [x / r for x in p]
        radial = sum(x * y for x, y in zip(u, v))
        return u, [(x - y * radial) / r for x, y in zip(v, u)]

    for j in range(32):
        box = {k: [I(min(p[j]), max(p[j])) for p in v] for k, v in nodes.items()}
        bound = metrics(**box)
        for k in range(1, 4):
            u = Q(j, 32) + Q(k, 128)
            value = {
                key: [float(evaluate(p, u)) for p in v] for key, v in fields.items()
            }
            q, w, e, f = [value[k] for k in ("q", "w", "e", "f")]
            a, da = direction(q, w)
            b, db = direction(
                [x + y for x, y in zip(q, e)], [x + y for x, y in zip(w, f)]
            )
            assert bound[0].contains(math.dist(a, b) * 648000 / math.pi)
            assert bound[1].contains(math.dist(da, db) * 648000 / math.pi)


@pytest.mark.parametrize(
    "start,end,good",
    [
        (99, 101, True),
        (99.99999, 101, False),
        (99, 99.99999, False),
        (math.nan, 101, False),
    ],
)
def test_selected_context_must_cover_both_endpoints(start, end, good, monkeypatch):
    monkeypatch.setattr(
        runtime.swe,
        "get_current_file_data",
        lambda slot: ("/private/data/file.se1", start, end, 441),
    )
    if good:
        result = window.selected_windows(100, 99.99998)
        assert all(r["filename"] == "file.se1" for r in result)
    else:
        with pytest.raises(EphemerisSourceError) as error:
            window.selected_windows(100, 99.99998)
        assert error.value.reason == "lunar_source_window_incoherent"


@pytest.mark.parametrize("frame", ["tropical", "lahiri"])
def test_known_boundary_retains_both_native_states_and_auxiliary_source_scope(frame):
    jd = 5227387.5
    metadata = {}
    trace = PhysicalEphemerisTrace()
    if frame == "tropical":
        state, model = ephemeris._swisseph_planet_state(
            "Moon", jd, julian_day_tt=jd, source_trace=trace, motion_metadata=metadata
        )
        assert set(trace.finish()["by_factor"]) == {"Moon"}
    else:
        state = native_lahiri_positions(
            ["Moon"],
            julian_day_ut1=jd,
            julian_day_tt=jd,
            source_trace=trace,
            motion_metadata=metadata,
        )["Moon"]
        trace.finish()
    policy = metadata["lunar_source_windows"][frame]
    assert policy["status"] == "recomputed_in_common_window"
    assert state["longitude"] == policy["coherent_spherical_coordinates"][0]
    assert state["latitude"] == policy["coherent_spherical_coordinates"][1]
    assert len(policy["initial_spherical_coordinates"]) == 3
    assert set(policy["source_contexts"]) == {
        "Moon_light_path_geometric",
        "Moon_light_path_retarded_barycentric",
    }
    for interval in policy["selected_windows_after_recomputation"]:
        assert (
            interval["start_jd_tt"]
            <= policy["retarded_jd_tt"]
            <= jd
            <= interval["end_jd_tt"]
        )


@pytest.mark.parametrize(
    "model", ["jpl", "moseph", "fatebridge_approximate_orbital_model"]
)
def test_other_kernels_do_not_claim_a_compressed_context_fix(model):
    policy = window.prime_lunar_source_window(
        2451545.0, model, PhysicalEphemerisTrace()
    )
    assert policy["status"] == "not_applied"


def test_unverified_native_identity_never_primes_a_state(monkeypatch):
    monkeypatch.setattr(window, "binding_distribution_version", lambda *args: "unknown")
    policy = window.prime_lunar_source_window(
        2451545.0, "swieph", PhysicalEphemerisTrace()
    )
    assert (
        policy["status"] == "not_applied"
        and policy["reason"] == "unverified_native_version"
    )


def test_equatorial_output_and_cartesian_diagnostic_use_the_same_window():
    from fatebridge.core.astro.lunar_source_window import coherent_lunar_native_state

    jd = 5227387.5
    metadata = {}
    trace = PhysicalEphemerisTrace()
    swe = runtime.swe
    state, model = ephemeris._swisseph_planet_state(
        "Moon", jd, julian_day_tt=jd, source_trace=trace, motion_metadata=metadata
    )
    eq = metadata["lunar_source_windows"]["equatorial"]
    assert state["declination"] == eq["coherent_native_state"][1]
    flags = (
        swe.FLG_SWIEPH
        | swe.FLG_SPEED
        | swe.FLG_XYZ
        | swe.FLG_EQUATORIAL
        | swe.FLG_ICRS
        | swe.FLG_J2000
    )
    with runtime.preserve_ephemeris_path():
        values, returned, policy = coherent_lunar_native_state(
            "calc", jd, flags, jd, model, trace
        )
    assert policy["coordinate_kind"] == "cartesian"
    assert "coherent_spherical_coordinates" not in policy
    assert list(values) == policy["coherent_native_state"]
    assert returned & swe.FLG_SPEED
    trace.finish()


def test_a_different_overlapping_fit_is_rejected_after_recomputation(monkeypatch):
    first = [
        {
            "slot": 0,
            "filename": "first.se1",
            "start_jd_tt": 99.0,
            "end_jd_tt": 101.0,
            "de_number": 441,
        }
    ]
    changed = [{**first[0], "filename": "second.se1"}]
    monkeypatch.setattr(window, "selected_windows", lambda *args: changed)
    policy = {
        "status": "primed",
        "epoch_jd_tt": 100.0,
        "retarded_jd_tt": 99.999,
        "selected_windows": first,
    }
    with pytest.raises(EphemerisSourceError) as error:
        window.finish_lunar_source_window(
            policy, (0, 0, 1, 0, 0, 0), (0, 0, 1, 0, 0, 0)
        )
    assert error.value.reason == "lunar_source_window_incoherent"


@pytest.mark.parametrize(
    "calendar,mjd",
    [
        ("1858ad-Nov-17 00:00:00.000000", "0"),
        ("2000ad-Jan-01 12:00:00.000000", "51544.5"),
    ],
)
def test_documented_mjd_zero_and_j2000_literals(calendar, mjd):
    assert Q(julian_input_label(input_tick(calendar), modified=True)) == Q(mjd)


@pytest.mark.parametrize(
    "calendar",
    [
        "1bc-Dec-31 23:59:59.123456",
        "1431ad-Mar-17 09:23:41.000000",
        "6431ad-Sep-17 09:04:16.000000",
        "9431ad-Dec-17 09:23:41.000000",
        "10000ad-Jan-01 00:00:00.999999",
    ],
)
def test_mjd_preserves_the_exact_requested_microsecond_and_day_origin(calendar):
    tick = input_tick(calendar)
    mjd = Q(julian_input_label(tick, modified=True))
    # Independent rational inverse. No float JD or collector helper is used.
    assert abs((mjd + 678576) * DAY_US - tick) <= Q(1, 10**30)
    assert abs(Q(julian_input_label(tick)) - mjd - Q(4800001, 2)) <= Q(1, 10**45)


def test_mjd_retains_the_same_integer_jd_guard_and_all_primary_ticks():
    primary = [
        input_tick("6431ad-Sep-17 09:04:16.000000") + s * 1000000 for s in [-5, 0, 5]
    ]
    policy = {
        "first_tlist_epoch_guard": {"method_id": "integer_jd_prefix_v1"},
        "reference_parameters": {"TLIST_TYPE": "'MJD'"},
        "maximum_labels_per_batch": 19,
    }
    wire, auxiliary = wire_epochs(policy, primary)
    assert wire == [auxiliary, *primary]
    guard_jd = Q(julian_input_label(auxiliary, modified=True)) + Q(4800001, 2)
    assert guard_jd.denominator == 1
    # A JD-integer guard has a half-integer MJD; an integer-MJD substitute
    # would shift the protected auxiliary epoch by twelve hours.
    assert Q(julian_input_label(auxiliary, modified=True)).denominator == 2


@pytest.mark.parametrize("tt", ["TT", "TDB"])
def test_independent_reader_preserves_actual_time_header_and_raw_delta(tt):
    result = inspect(raw(tt), 200, {"time_type": tt}, [CASE], PLAN)
    assert result["status"] == "supported"
    assert result["actual_time_type"] == tt
    assert result["rows"][0]["TDB_minus_UT_seconds"] == "69.185000"


@pytest.mark.parametrize(
    "payload,status",
    [
        (b"[]", "invalid_response"),
        (b'{"result":null}', "invalid_response"),
        (
            json.dumps(
                {"error": "Only UT or TT are allowed for observer table TIME_TYPE"}
            ).encode(),
            "service_refused",
        ),
    ],
)
def test_independent_reader_does_not_promote_invalid_or_refused_responses(
    payload, status
):
    assert inspect(payload, 200, {"time_type": "TDB"}, [CASE], PLAN)["status"] == status


def test_independent_field_comparison_does_not_insert_unpublished_error_budgets():
    epoch = Q(CASE["nominal_JD"])
    row = {"nominal_JD": str(epoch), "TDB_minus_UT_seconds": "69.185000"}
    result = expected_clock(
        row,
        calibration(epoch + Q(1005, 1000000 * 86400)),
        calibration(epoch),
        "printing_only",
        PLAN,
    )
    assert result["status"] == "conditional_leap_hold_comparison"
    assert result["overlap_nominal_state"] is False
    assert result["overlap_paired_state"] is False
    assert result["time_field_is_internal_clock_bound_certified"] is False
    assert result["TT_geometric_six_not_refuted"] is False
