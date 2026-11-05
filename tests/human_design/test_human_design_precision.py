"""Node-backend changes must survive transport and reading projections."""

import copy
import json
import math
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.human_design import bodygraph, chart_at, longitude_activation
from fatebridge.core.human_design_mechanics import GATE_ORDER
from fatebridge.core.human_design_precision import compare_node_backends


def _at_gate(gate):
    return (302 + GATE_ORDER.index(gate) * 5.625 + 0.25) % 360


def _chart():
    # 3-60 defines root and sacral. Replacing 60/56 by 41/31 breaks it.
    activations = {}
    for side in ("personality", "design"):
        activations[side] = [
            {
                "body": body,
                **longitude_activation(_at_gate(gate)),
                "longitude_speed": -0.1,
                "return_flags": runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED,
                "ephemeris_model": "swieph",
            }
            for body, gate in (("Sun", 3), ("NorthNode", 60), ("SouthNode", 56))
        ]
    return {
        "activations": activations,
        "bodygraph": bodygraph([3, 60, 56], [3, 60, 56]),
        "time_scales": {side: {"jd_tt": 2451545.0} for side in activations},
        "profile": "1/3",
    }


def test_backend_comparison_recomputes_joint_mechanics_and_preserves_selected_chart(
    monkeypatch,
):
    chart = _chart()
    before = copy.deepcopy(chart)
    calls = []

    def reference(operation, jd, body, flags):
        calls.append((operation, jd, body, flags))
        return (_at_gate(41), 0, 0, -0.2, 0, 0), flags

    monkeypatch.setattr(runtime, "ephemeris_call", reference)
    result = compare_node_backends(chart, "true")
    assert chart == before
    assert result["status"] == "cross_backend_compared"
    assert len(result["rows"]) == 4
    assert len(calls) == 2
    assert all(c[3] == runtime.swe.FLG_MOSEPH | runtime.swe.FLG_SPEED for c in calls)
    assert result["rows"][0]["selected"]["gate"] == 60
    assert result["rows"][0]["reference"]["gate"] == 41
    assert result["mechanical_comparison"]["changed_classifications"] == [
        "type",
        "subtype",
        "authority",
        "strategy",
        "definition",
    ]
    assert result["subdivision_accuracy_certified"] is False


def test_node_reference_does_not_inherit_the_selected_native_flag_label(monkeypatch):
    from fatebridge.core import human_design_precision as module

    chart = _chart()
    for rows in chart["activations"].values():
        for row in rows:
            if row["body"] in {"NorthNode", "SouthNode"}:
                row["native_return_flag_model"] = "swieph"
    original = copy.deepcopy(chart)
    monkeypatch.setattr(
        runtime,
        "ephemeris_call",
        lambda operation, jd, body, flags: ((_at_gate(41), 0, 0, -0.2, 0, 0), flags),
    )
    captured = []
    compare = module.compare_charts

    def inspect(selected, alternate, **kwargs):
        captured.append(copy.deepcopy(alternate))
        return compare(selected, alternate, **kwargs)

    monkeypatch.setattr(module, "compare_charts", inspect)
    assert compare_node_backends(chart, "true")["status"] == "cross_backend_compared"
    assert chart == original
    assert len(captured) == 1
    for rows in captured[0]["activations"].values():
        for row in rows:
            if row["body"] in {"NorthNode", "SouthNode"}:
                assert (
                    row["native_return_flag_model"]
                    == (runtime.ephemeris_model_from_retflag(row["return_flags"]))
                    == "moshier"
                )


@pytest.mark.parametrize("invalid", ["bad", None])
def test_invalid_node_convention_cannot_be_hidden_by_diagnostic(invalid):
    with pytest.raises(ValueError):
        compare_node_backends(_chart(), invalid)


def test_mean_node_cannot_gain_independence_by_switching_ephemeris_flags(monkeypatch):
    def forbidden(*args):
        raise AssertionError("mean-node backend switch must not be called")

    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    result = compare_node_backends(_chart(), "mean")
    assert result["status"] == "analytic_mean_node_not_cross_validated"
    assert result["rows"] == [] and result["mechanical_comparison"] is None
    assert result["reference_backend"] is None


@pytest.mark.parametrize(
    "failure", ["exception", "nan", "negative_flag", "wrong_backend"]
)
def test_unavailable_reference_never_becomes_silent_agreement(monkeypatch, failure):
    def failed(*args):
        if failure == "exception":
            raise RuntimeError("reference failed")
        return (
            (float("nan") if failure == "nan" else 100, 0, 0, 0, 0, 0),
            (
                -1
                if failure == "negative_flag"
                else (
                    runtime.swe.FLG_SWIEPH
                    if failure == "wrong_backend"
                    else runtime.swe.FLG_MOSEPH
                )
            ),
        )

    monkeypatch.setattr(runtime, "ephemeris_call", failed)
    result = compare_node_backends(_chart(), "true")
    assert result["status"] == "reference_unavailable"
    assert result["mechanical_comparison"] is None and result["rows"] == []


def test_moshier_compared_to_itself_is_explicitly_not_independent():
    from tests.support.ephemeris_context import moshier_ephemeris

    with moshier_ephemeris():
        chart = chart_at(datetime.fromisoformat("2000-01-01T12:00:00+00:00"))
        result = compare_node_backends(chart, "true")
    assert result["status"] == "same_backend_not_independent"
    assert result["changed_levels"] == []
    assert all(row["difference_arcseconds"] == 0 for row in result["rows"])
    assert result["independent_astronomy_certified"] is False


def test_same_backend_equality_cannot_certify_fine_subdivision_accuracy():
    from fatebridge.services.human_design import calculate_human_design
    from tests.support.ephemeris_context import moshier_ephemeris

    with moshier_ephemeris():
        result = calculate_human_design(
            birth_year=2000,
            birth_month=1,
            birth_day=1,
            birth_hour=12,
            birth_minute=0,
            birth_timezone="UTC",
        )
    assert result["node_backend_comparison"]["status"] == "same_backend_not_independent"
    assert result["node_backend_comparison"]["subdivision_accuracy_certified"] is False
    assert result["interpretation"]["ephemeris_scope"]
    assert result["validation"]["all_three_axes_full_marks"] is False


def test_independent_de440_reference_recomposes_from_saved_raw_vectors():
    path = Path(__file__).parents[1] / "fixtures/human-design-node-de440.json"
    reference = json.loads(path.read_text())
    assert reference["tolerance_arcseconds"] == 1.0
    assert reference["kernel_md5"] == "c9d581bfd84209dbeee8b1583939b148"
    assert len(reference["rows"]) == 122
    assert reference["rows"][0]["label"].startswith("1799-")
    assert reference["rows"][-1]["label"].startswith("2399-")
    for row in reference["rows"]:
        matrix = row["icrf_to_mean_ecliptic_of_date_matrix"]
        for i in range(3):
            for j in range(3):
                assert sum(
                    matrix[i][k] * matrix[j][k] for k in range(3)
                ) == pytest.approx(1 if i == j else 0, abs=2e-14)

        def rotate(vector):
            return [sum(matrix[i][k] * vector[k] for k in range(3)) for i in range(3)]

        r = rotate(row["retarded_geocentric_position_icrf_km"])
        v = rotate(row["retarded_geocentric_velocity_icrf_km_per_day"])
        nx = r[0] * v[2] - r[2] * v[0]
        ny = r[1] * v[2] - r[2] * v[1]
        recomposed = (
            math.degrees(math.atan2(ny, nx) + row["nutation_longitude_radians"]) % 360
        )
        assert recomposed == pytest.approx(row["node_longitude"], abs=1e-10)
    j2000 = next(r for r in reference["rows"] if r["jd_tt"] == 2451545.0)
    assert j2000["node_longitude"] == pytest.approx(123.95406, abs=0.00002)
