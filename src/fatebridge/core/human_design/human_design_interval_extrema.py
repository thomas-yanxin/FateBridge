"""Finite coordinate probes around observed native velocity candidates.

The parameter is birth TT even for Design activations. Returned velocity is
only a candidate selector, not a certificate of a coordinate derivative.
"""

from fractions import Fraction
from math import nextafter
from typing import Any, Callable

METHOD = "human_design_birth_TT_coordinate_extremum_probes_v1"
MAX_ADDITIONAL_EVALUATIONS = 4096


def zero_speed_components(
    grid: list[float],
    side: str,
    body: str,
    activation: Callable[[float, str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group adjacent observed zeroes without asserting a continuous plateau."""
    speeds = [activation(tt, side, body)["longitude_speed"] for tt in grid]
    result = []
    i = 0
    while i < len(grid):
        if speeds[i] != 0:
            i += 1
            continue
        start = i
        while i + 1 < len(grid) and speeds[i + 1] == 0:
            i += 1
        end = i
        left, right = max(0, start - 1), min(len(grid) - 1, end + 1)
        vl, vr = speeds[left], speeds[right]
        # A boundary zero has only one observed nonzero direction. Same-sign
        # neighbours or an all-zero interval do not identify an extremum kind.
        direction = (
            vl if vl != 0 and (vr == 0 or vl * vr < 0) else -vr if vl == 0 else 0
        )
        result.append(
            {
                "side": side,
                "body": body,
                "source": "sampled_zero_component",
                "kind": (
                    "maximum"
                    if direction > 0
                    else "minimum" if direction < 0 else "undirected"
                ),
                "coarse_bracket_jd_tt": [grid[left], grid[right]],
                "seed_birth_jd_tt": grid[start : end + 1],
                "observed_zero_component_jd_tt": [grid[start], grid[end]],
            }
        )
        i += 1
    return result


def probe_station_coordinates(
    candidates: list[dict[str, Any]],
    at: Callable[[float], dict[str, Any]],
    cache: dict[float, dict[str, Any]],
) -> dict[str, Any]:
    added = 0
    probes = []

    class BudgetExhausted(Exception):
        pass

    for candidate in candidates:
        side, body = candidate["side"], candidate["body"]
        observations: dict[float, list[Any]] = {}
        before = added

        def row(tt: float) -> list[Any]:
            nonlocal added
            if tt not in cache:
                if added >= MAX_ADDITIONAL_EVALUATIONS:
                    raise BudgetExhausted
                chart = at(tt)
                added += 1
            else:
                chart = at(tt)
            a = next(a for a in chart["activations"][side] if a["body"] == body)
            value = [tt, a["longitude"], a["longitude_speed"], a["return_flags"]]
            observations[tt] = value
            return value

        lo, hi = candidate["coarse_bracket_jd_tt"]
        left = row(lo)
        row(hi)
        seeds = [row(tt) for tt in candidate["seed_birth_jd_tt"]]
        maximize = candidate["kind"] == "maximum"

        def objective(value: list[Any]) -> Fraction:
            delta = (Fraction(value[1]) - Fraction(left[1]) + 180) % 360 - 180
            return -delta if maximize else delta

        baseline = min(seeds, key=lambda r: (objective(r), r[0]))
        status = "direction_not_inferred"
        iterations = 0
        if candidate["kind"] != "undirected":
            status = "iteration_limit"
            try:
                x = lo + (hi - lo) * 0.3819660112501051
                y = lo + (hi - lo) * 0.6180339887498949
                if not lo < x < y < hi:
                    status = "adjacent_float_or_quantized_bracket"
                else:
                    # Keep each actual read even when the next read exhausts
                    # the shared budget. No partially observed chart is lost.
                    xr = row(x)
                    yr = row(y)
                    for iterations in range(1, 129):
                        if nextafter(lo, hi) >= hi:
                            status = "adjacent_float_or_quantized_bracket"
                            break
                        fx, fy = objective(xr), objective(yr)
                        if fx < fy:
                            hi, y, yr = y, x, xr
                            x = lo + (hi - lo) * 0.3819660112501051
                            if not lo < x < y:
                                status = "adjacent_float_or_quantized_bracket"
                                break
                            xr = row(x)
                        elif fy < fx:
                            lo, x, xr = x, y, yr
                            y = lo + (hi - lo) * 0.6180339887498949
                            if not x < y < hi:
                                status = "adjacent_float_or_quantized_bracket"
                                break
                            yr = row(y)
                        else:
                            lo, hi = x, y
                            x = lo + (hi - lo) * 0.3819660112501051
                            y = lo + (hi - lo) * 0.6180339887498949
                            if not lo < x < y < hi:
                                status = "adjacent_float_or_quantized_bracket"
                                break
                            xr = row(x)
                            yr = row(y)
            except BudgetExhausted:
                status = "evaluation_budget_exhausted"
        selected = min(observations.values(), key=lambda r: (objective(r), r[0]))
        selected_chart = cache[selected[0]]
        gain = objective(baseline) - objective(selected)
        probes.append(
            {
                **candidate,
                "status": status,
                "iterations": iterations,
                "additional_evaluations": added - before,
                "final_search_bracket_birth_jd_tt": [lo, hi],
                "observations": [observations[tt] for tt in sorted(observations)],
                "observation_columns": [
                    "birth_jd_tt",
                    "longitude",
                    "longitude_speed",
                    "return_flags",
                ],
                "baseline": baseline,
                "selected": selected,
                "selected_activation_jd_tt": selected_chart["time_scales"][side][
                    "jd_tt"
                ],
                "observed_coordinate_gain_degrees": float(gain),
                "observed_coordinate_gain_exact": {
                    "numerator": str(gain.numerator),
                    "denominator": str(gain.denominator),
                },
                "continuous_extremum_certified": False,
                "physical_station_certified": False,
            }
        )
    return {
        "method_id": METHOD,
        "parameter_axis": "birth_jd_tt",
        "maximum_additional_evaluations": MAX_ADDITIONAL_EVALUATIONS,
        "additional_evaluations": added,
        "probe_count": len(probes),
        "budget_exhausted": any(
            p["status"] == "evaluation_budget_exhausted" for p in probes
        ),
        "probes": probes,
        "scope": "速度变号和网格零速度只选择候选；在出生TT轴细查返回黄经，每次整盘求值均进入联合见证。Design激活TT另列。有限黄金分割不证明单峰、连续极值、真实驻留、物理精度或连续区间完整性；平局收缩和黄经量化仍可漏掉更窄变化。",
    }
