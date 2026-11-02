"""Necessary outer constraints under an explicit, uncertified epoch hypothesis.

If |delta t| <= E days and |angle'| <= B arcsec/day, the mean-value
inequality gives a separate B*E angular envelope. The original printing
interval is unchanged. This relaxation does not prove actual epoch semantics,
polynomial truncation, physical feasibility, or candidate accuracy.
"""

import hashlib
import json
import math
from fractions import Fraction as Q
from itertools import combinations

from scripts.astrodice_interval_reference import (
    ORDERS,
    WINDOWS,
    certified_bound,
    system,
    tangent_geometry,
    vector_summary,
    verify,
)
from scripts.astrodice_reference_infeasibility import matrix_digest

METHOD = "bounded_epoch_odd_polynomial_outer_relaxation_v1"
LINE = 0.002


def envelope_system(row, window, order, axis, epoch_days, slope_bound):
    epoch_days, slope_bound = Q(epoch_days), Q(slope_bound)
    if epoch_days < 0 or slope_bound <= 0:
        raise ValueError("Invalid explicit epoch/slope hypothesis")
    a, printing_b, baseline, scale = system(
        row, None, window, order, axis, step_seconds=5
    )
    # Both observations in a symmetric half difference contribute B*E/2.
    # Their sum is B*E, not 2*B*E. Original printing and scaling stay intact.
    clock_arcsec = epoch_days * slope_bound
    b = [value + clock_arcsec / scale for value in printing_b]
    return (
        a,
        b,
        baseline,
        scale,
        {
            "original_printing_scale_arcsec": str(scale),
            "additional_epoch_envelope_arcsec": str(clock_arcsec),
            "epoch_uncertainty_days": str(epoch_days),
            "absolute_each_angle_slope_bound_arcsec_per_day": str(slope_bound),
            "matrix_sha256": matrix_digest(a, b),
        },
    )


def slope_triangle_bound(primal, baseline, scale, window, epoch_days):
    """Bound the primal odd polynomial on the extended support interval."""
    coefficients = [scale * Q(value) for value in primal]
    coefficients[0] += baseline
    extent = 1 + Q(epoch_days) * Q(86400, window)
    return sum(
        (
            power * abs(value) * extent ** (power - 1)
            for power, value in zip(range(1, 2 * len(coefficients), 2), coefficients)
        ),
        Q(),
    ) * Q(86400, window)


def solve_fit(row, window, order, epoch_days, slope_bound):
    axes = []
    for axis in (0, 1):
        a, b, baseline, scale, metadata = envelope_system(
            row, window, order, axis, epoch_days, slope_bound
        )
        certificates = [certified_bound(a, b, sign) for sign in (1, -1)]
        if any(c["status"] != "exact_primal_dual_optimum" for c in certificates):
            return {
                "window_seconds": window,
                "order": order,
                "status": "outer_solver_unresolved",
                "axis": axis,
                "results": certificates,
            }
        low = (baseline + scale * verify(a, b, certificates[0])) * Q(86400, window)
        high = (baseline - scale * verify(a, b, certificates[1])) * Q(86400, window)
        slopes = [
            slope_triangle_bound(c["primal"], baseline, scale, window, epoch_days)
            for c in certificates
        ]
        axes.append(
            {
                **metadata,
                "lower_arcsec_per_day": str(low),
                "upper_arcsec_per_day": str(high),
                "primal_odd_polynomial_slope_triangle_bounds": list(map(str, slopes)),
                "certificates": certificates,
            }
        )
    return {
        "window_seconds": window,
        "order": order,
        "status": "exact_angular_outer_interval",
        "axes": axes,
        "primal_odd_models_respect_slope_cap": all(
            Q(bound) <= Q(slope_bound)
            for axis in axes
            for bound in axis["primal_odd_polynomial_slope_triangle_bounds"]
        ),
        "actual_even_component_or_physical_curve_certified": False,
    }


def replay_fit(row, record, epoch_days, slope_bound):
    if record["status"] != "exact_angular_outer_interval":
        return None
    axes, slopes = [], []
    window, order = record["window_seconds"], record["order"]
    if len(record["axes"]) != 2:
        raise ValueError("Incomplete outer angular interval")
    for axis, declared in enumerate(record["axes"]):
        a, b, baseline, scale, metadata = envelope_system(
            row, window, order, axis, epoch_days, slope_bound
        )
        if any(declared.get(key) != value for key, value in metadata.items()):
            raise ValueError(
                "Epoch hypothesis, printing or constraint identity changed"
            )
        certs = declared["certificates"]
        if len(certs) != 2 or [c["objective_sign"] for c in certs] != [1, -1]:
            raise ValueError("Outer objective changed")
        low = (baseline + scale * verify(a, b, certs[0])) * Q(86400, window)
        high = (baseline - scale * verify(a, b, certs[1])) * Q(86400, window)
        if low > high or [str(low), str(high)] != [
            declared["lower_arcsec_per_day"],
            declared["upper_arcsec_per_day"],
        ]:
            raise ValueError(
                "Outer derivative interval differs from exact certificates"
            )
        bounds = [
            slope_triangle_bound(c["primal"], baseline, scale, window, epoch_days)
            for c in certs
        ]
        if (
            list(map(str, bounds))
            != declared["primal_odd_polynomial_slope_triangle_bounds"]
        ):
            raise ValueError("Primal slope check changed")
        slopes.extend(bounds)
        axes.append((low, high))
    if record["primal_odd_models_respect_slope_cap"] != all(
        value <= Q(slope_bound) for value in slopes
    ):
        raise ValueError("Primal slope-cap declaration changed")
    return axes


def summary(row, axes, epoch_days, slope_bound):
    if Q(epoch_days) == 0:
        return vector_summary(row, axes)
    _, alpha_axis, delta_axis, printing_noise = tangent_geometry(row)
    mid = [float((low + high) / 2) for low, high in axes]
    radius = [float((high - low) / 2) for low, high in axes]
    clock_center_noise = float(2 * Q(epoch_days) * Q(slope_bound)) * math.pi / 648000
    center_noise = printing_noise + clock_center_noise
    return {
        "derivative_arcsec_per_day": [
            a * mid[0] + d * mid[1] for a, d in zip(alpha_axis, delta_axis)
        ],
        "radius_arcsec_per_day": math.nextafter(
            math.hypot(math.hypot(*alpha_axis) * radius[0], radius[1])
            + center_noise * sum(abs(m) + r for m, r in zip(mid, radius))
            + 1e-9,
            math.inf,
        ),
        "angular_midpoint_arcsec_per_day": mid,
        "angular_half_widths_arcsec_per_day": radius,
        "separate_epoch_center_direction_envelope_radians": clock_center_noise,
    }


def quality(row, fits, epoch_days, slope_bound):
    if set(row["samples"]) != set(map(str, range(-1440, 1441, 5))):
        raise ValueError("Complete original 577-point grid required")
    if any(value is None for value in row["samples"].values()):
        raise ValueError(
            "An unavailable point cannot be fitted by the clock hypothesis"
        )
    expected = {(window, order) for window in WINDOWS for order in ORDERS}
    if (
        len(fits) != len(expected)
        or {(f["window_seconds"], f["order"]) for f in fits} != expected
    ):
        raise ValueError("Original windows and orders cannot be narrowed")
    summaries = {}
    for fit in fits:
        axes = replay_fit(row, fit, epoch_days, slope_bound)
        if axes is not None and fit["primal_odd_models_respect_slope_cap"]:
            summaries[fit["window_seconds"], fit["order"]] = summary(
                row, axes, epoch_days, slope_bound
            )
    checks, selected = [], None
    for i in range(len(WINDOWS) - 2):
        triple = WINDOWS[i : i + 3]
        keys = [(window, order) for window in triple for order in ORDERS]
        complete = all(key in summaries for key in keys)
        spread = (
            max(
                (
                    math.dist(
                        summaries[a]["derivative_arcsec_per_day"],
                        summaries[b]["derivative_arcsec_per_day"],
                    )
                    for a, b in combinations(keys, 2)
                ),
                default=0,
            )
            if complete
            else None
        )
        radius = (
            max(summaries[key]["radius_arcsec_per_day"] for key in keys)
            if complete
            else None
        )
        passed = complete and spread <= LINE and radius <= LINE
        checks.append(
            {
                "windows_seconds": list(triple),
                "complete_exact_outer_certificates": complete,
                "maximum_midpoint_difference_arcsec_per_day": spread,
                "maximum_outer_radius_arcsec_per_day": radius,
                "declared_line_satisfied": passed,
            }
        )
        if passed and selected is None:
            selected = triple[1], 5
    return {
        "status": (
            "outer_reference_numerical_quality_satisfied"
            if selected
            else "outer_reference_quality_unresolved"
        ),
        "selected_window_seconds": selected[0] if selected else None,
        "selected_order": 5 if selected else None,
        "selected": summaries[selected] if selected else None,
        "all_window_checks": checks,
        "fixed_line_arcsec_per_day": LINE,
        "actual_epoch_envelope_certified": False,
        "slope_bound_physically_certified": False,
        "physical_curve_feasibility_certified": False,
        "candidate_accuracy_certified": False,
        "production_acceptance_status": "unresolved_epoch_and_model_premises",
    }


def binding(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
