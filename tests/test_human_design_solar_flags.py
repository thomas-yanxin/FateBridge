"""Same native Sun convention in roots, actual activations and every witness."""

import ast
import hashlib
import json
import math
import os
import subprocess
import sys
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.astro import native_execution, runtime
from fatebridge.core.human_design import solar_root_subdivisions
from fatebridge.core.human_design_solar_root import SOLAR_COORDINATE_POLICY
from fatebridge.core.human_design_time import sun_at_tt
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from tests.ephemeris_case_runtime import (
    native_ephemeris_files_module as native_ephemeris_files_module,
)

pytestmark = pytest.mark.usefixtures("native_ephemeris_files_module")


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "tests/fixtures/human-design-solar-flags-plan.json"
PLAN = json.loads(PLAN_PATH.read_text())
SPEC = next(s for s in CATALOG if s.key == "human_design")


def forbidden(*args, **kwargs):
    raise AssertionError("Pure verification called a native producer")


def check_solar_binding(chart):
    s = chart["design_solver"]
    w = s["numerical_precision"]
    assert w["sun_coordinate_policy"] == SOLAR_COORDINATE_POLICY
    p, d = [
        next(
            row["longitude"]
            for row in chart["activations"][side]
            if row["body"] == "Sun"
        )
        for side in ("personality", "design")
    ]
    assert p == w["birth_sun_longitude"] and d == w["selected"]["sun_longitude"]
    residual = (Fraction(p) - Fraction(d)) % 360 - 88
    assert s["residual_degrees"] == float(residual)
    for key in ("lower", "upper"):
        epoch = next(
            row
            for row in w["design_body_endpoint_assessment"]["evaluations"]
            if row["jd_tt"] == w[key]["jd_tt"]
        )
        assert epoch["native_positions"][0][0] == w[key]["sun_longitude"]
    assert w["physical_time_accuracy_certified"] is False
    assert (
        w["design_body_endpoint_assessment"][
            "solar_function_activation_subdivision_differences"
        ]
        == []
    )


def test_all_244_fixed_native_lattice_roots_in_a_fresh_process():
    path = ROOT / (
        "tests/fixtures/human-design-solar-speed-lattice-linux.json"
        if sys.platform == "linux"
        else "tests/fixtures/human-design-solar-speed-lattice.json"
    )
    ref = json.loads(path.read_text())
    gen = ROOT / "scripts/build_human_design_solar_speed_reference.py"
    assert hashlib.sha256(gen.read_bytes()).hexdigest() == ref["generator_sha256"]
    assert len(ref["cases"]) == 244
    tree = ast.parse(gen.read_text())
    assert not any(
        isinstance(n, ast.ImportFrom) and (n.module or "").startswith("fatebridge")
        for n in ast.walk(tree)
    )
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "strict.json"
        env = {**os.environ, "SE_EPHE_PATH": str(ROOT / "ephe")}
        env.pop("FATEBRIDGE_JPL_FILE", None)
        probe = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/check_human_design_solar_speed_lattice.py"),
                "--output",
                str(target),
                "--require-exact",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=120,
        )
        assert probe.returncode == 1, probe.stdout + probe.stderr
        report = json.loads(target.read_text())
    expected_strict = {
        "status": "failed",
        "total": 244,
        "passed": 243 if sys.platform == "linux" else 242,
        "failed": 1 if sys.platform == "linux" else 2,
    }
    assert report["strict_selected_root_conformance"] == expected_strict
    assert report["strict_selected_root_conformance"]["status"] == "failed"
    assert report["strict_selected_root_conformance"]["total"] == 244
    assert report["strict_selected_root_conformance"]["failed"] > 0
    assert report["bounded_numeric_conformance_passed"] is False


@pytest.mark.parametrize("backend", PLAN["backends"])
@pytest.mark.parametrize("mode", PLAN["modes"])
@pytest.mark.parametrize("case", PLAN["cases"], ids=lambda c: c["id"])
def test_all_old_public_inputs_keep_exact_solar_binding(
    case, backend, mode, tmp_path, monkeypatch
):
    monkeypatch.setenv(
        "SE_EPHE_PATH", str(ROOT / "ephe") if backend == "swieph" else str(tmp_path)
    )
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    run = execute_tool(SPEC, SPEC.request_model(**{**case["input"], "node_mode": mode}))
    check_solar_binding(run)
    with (
        patch.object(runtime, "ephemeris_call", forbidden),
        patch.object(native_execution, "calculate", forbidden),
    ):
        assert (
            verify_human_design_reading(run)["status"]
            == "verified_fixed_template_reading"
        )


@pytest.mark.parametrize("backend,mask", [("swieph", 2), ("moshier", 4)])
def test_sun_requests_activation_flags_and_rejects_a_missing_speed_bit(
    backend, mask, monkeypatch
):
    calls = []

    def native(operation, tt, body, flags):
        calls.append((operation, tt, body, flags))
        return (10.0, 0.0, 1.0, 1.0, 0.0, 0.0), flags

    monkeypatch.setattr(runtime, "ephemeris_call", native)
    assert sun_at_tt(2451545.0, backend=backend) == 10.0
    assert calls == [("calc", 2451545.0, 0, mask | 256)]
    monkeypatch.setattr(
        runtime, "ephemeris_call", lambda *a: ((10.0, 0, 1, 0, 0, 0), mask)
    )
    with pytest.raises(RuntimeError):
        sun_at_tt(2451545.0, backend=backend)


@pytest.fixture(scope="module")
def complete():
    return execute_tool(
        SPEC,
        SPEC.request_model(
            **{**PLAN["cases"][1]["input"], "birth_time_uncertainty_minutes": 1}
        ),
    )


def test_every_actual_sample_and_full_backend_uses_its_own_solar_policy(complete):
    assert (
        verify_human_design_reading(complete)["status"]
        == "verified_fixed_template_reading"
    )
    for row in complete["time_sensitivity"]["evaluation_witnesses"]["samples"]:
        w = row["design_solver"]["numerical_precision"]
        assert w["sun_coordinate_policy"] == SOLAR_COORDINATE_POLICY
        assert w["birth_sun_longitude"] == row["native_positions"]["personality"][0][0]
        assert w["selected"]["sun_longitude"] == row["native_positions"]["design"][0][0]
    check_solar_binding(complete["ephemeris_backend_comparison"]["reference_chart"])


@pytest.mark.parametrize("kind", PLAN["negative_receipts"][2:])
def test_rehashed_sub_tolerance_solar_contradictions_cannot_pass(complete, kind):
    run = deepcopy(complete)
    s = run["design_solver"]
    w = s["numerical_precision"]
    if kind == "wrong_policy":
        w["sun_coordinate_policy"] = "position_only"
    elif kind == "missing_policy":
        w.pop("sun_coordinate_policy")
    elif kind == "missing_reference_policy":
        run["ephemeris_backend_comparison"]["reference_chart"]["design_solver"][
            "numerical_precision"
        ].pop("sun_coordinate_policy")
    elif kind == "sample_policy":
        run["time_sensitivity"]["evaluation_witnesses"]["samples"][0]["design_solver"][
            "numerical_precision"
        ]["sun_coordinate_policy"] = "position_only"
    elif kind == "invented_accuracy":
        w["physical_time_accuracy_certified"] = True
    else:
        if kind == "birth_sun_ULP":
            w["birth_sun_longitude"] = math.nextafter(
                w["birth_sun_longitude"], math.inf
            )
        else:
            key = (
                ("lower" if w["selected"]["jd_tt"] != w["lower"]["jd_tt"] else "upper")
                if kind == "endpoint_sun_ULP"
                else (
                    "lower"
                    if w["selected"]["jd_tt"] == w["lower"]["jd_tt"]
                    else "upper"
                )
            )
            w[key]["sun_longitude"] = math.nextafter(w[key]["sun_longitude"], math.inf)
        for key in ("lower", "upper"):
            r = (
                Fraction(w["birth_sun_longitude"]) - Fraction(w[key]["sun_longitude"])
            ) % 360 - 88
            w[key]["exact_residual"] = {
                "numerator": str(r.numerator),
                "denominator": str(r.denominator),
            }
            w[key]["residual_degrees"] = float(r)
        selected = next(
            w[k] for k in ("lower", "upper") if w[k]["jd_tt"] == s["design_jd_tt"]
        )
        w["selected"] = deepcopy(selected)
        s["residual_degrees"] = selected["residual_degrees"]
        w.update(solar_root_subdivisions(s))
    for trace in run["rule_trace"]:
        if trace["rule_id"] == "design_solar_arc":
            trace["result"] = {"design_utc": run["design_utc"], **s}
    run["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in run.items() if k != "run_metadata"}
    )
    with (
        patch.object(runtime, "ephemeris_call", forbidden),
        patch.object(native_execution, "calculate", forbidden),
    ):
        assert verify_human_design_reading(run)["status"] == "rejected"


@pytest.mark.parametrize("mode", ["true", "mean"])
@pytest.mark.parametrize("tt", [2385984.0, 2513637.0, 2593990.0])
def test_all_three_platform_controls_keep_actual_whole_numeric_candidates(
    tt, mode, monkeypatch
):
    from fatebridge.core.human_design import chart_at_tt
    from fatebridge.validation.human_design_solar_root import verify_solar_root_context

    monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    chart = chart_at_tt(tt, mode, backend="moshier")
    check_solar_binding(chart)
    w = chart["design_solver"]["numerical_precision"]
    lattice = w["local_solar_lattice"]
    family = w["local_root_family"]
    assert (family is not None) == lattice["multiple_numeric_contacts_observed"]
    if family:
        assert family["actual_epoch_count"] == len(lattice["candidate_epoch_indices"])
        assert family["unique_physical_root_certified"] is False
        for c in family["candidates"]:
            assert len(c["native_positions"]) == 11
            assert (
                sum(
                    len(c["snapshot"]["activations"][side])
                    for side in ["personality", "design"]
                )
                == 26
            )
            assert len(c["interpretation_from_selected"]["candidates"]) == 2
    with (
        patch.object(runtime, "ephemeris_call", forbidden),
        patch.object(native_execution, "calculate", forbidden),
    ):
        assert verify_solar_root_context(chart)["errors"] == []


@pytest.fixture(scope="module")
def actual_family():
    from fatebridge.core.human_design import chart_at_tt

    with pytest.MonkeyPatch.context() as p:
        p.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
        p.delenv("FATEBRIDGE_JPL_FILE", raising=False)
        tt = 2385984.0 if sys.platform == "linux" else 2513637.0
        c = chart_at_tt(tt, "true", backend="moshier")
        assert (
            c["design_solver"]["numerical_precision"]["local_root_family"] is not None
        )
        return c


@pytest.mark.parametrize(
    "kind",
    [
        "sample_missing",
        "sample_sun",
        "fake_monotonicity",
        "bracket_missing",
        "candidate_missing",
        "candidate_sun",
        "candidate_snapshot",
        "candidate_reading",
        "candidate_TT",
        "summary",
    ],
)
def test_local_curve_and_complete_candidate_contradictions_reject_without_native(
    actual_family, kind
):
    from fatebridge.validation.human_design_solar_root import verify_solar_root_context

    c = deepcopy(actual_family)
    w = c["design_solver"]["numerical_precision"]
    lattice = w["local_solar_lattice"]
    family = w["local_root_family"]
    if kind == "sample_missing":
        lattice["samples"].pop()
    elif kind == "sample_sun":
        lattice["samples"][0]["sun_longitude"] += 0.01
    elif kind == "fake_monotonicity":
        lattice["continuous_monotonicity_certified"] = True
    elif kind == "bracket_missing":
        lattice["observed_sign_brackets"].pop()
    elif kind == "candidate_missing":
        family["candidates"].pop()
    elif kind == "candidate_sun":
        family["candidates"][0]["native_positions"][0][0] += 0.01
    elif kind == "candidate_snapshot":
        family["candidates"][0]["snapshot"]["variable_code"] = "R-R-R-R"
    elif kind == "candidate_reading":
        family["candidates"][0]["interpretation_from_selected"][
            "scope"
        ] = "All line meanings certified"
    elif kind == "candidate_TT":
        family["candidates"][0]["jd_tt"] = math.nextafter(
            family["candidates"][0]["jd_tt"], math.inf
        )
    else:
        w["local_root_family_summary"]["actual_epoch_count"] = 999
    with (
        patch.object(runtime, "ephemeris_call", forbidden),
        patch.object(native_execution, "calculate", forbidden),
    ):
        assert verify_solar_root_context(c)["errors"]


@pytest.mark.parametrize("wrap", [False, True])
def test_solar_zero_and_natural_360_wrap_do_not_fabricate_backward_motion(wrap):
    from fatebridge.core.human_design_solar_lattice import derive_lattice, lattice_times

    t = 2451545.0
    origin = Fraction(0 if wrap else 100)
    samples = [
        {
            "jd_tt": tt,
            "sun_longitude": float((origin + Fraction(tt) - Fraction(t)) % 360),
        }
        for tt in lattice_times(t, t)
    ]
    r = derive_lattice(float(origin + 88), t, t, samples)
    assert r["observed_decreasing_step_indices"] == []
    assert r["observed_exact_zero_indices"] == [4]
    assert r["unique_physical_root_certified"] is False


@pytest.mark.parametrize("backend,mask", [("swieph", 2), ("moshier", 4)])
def test_wrong_actual_solar_backend_is_rejected_with_correct_speed_bit(
    backend, mask, monkeypatch
):
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setattr(
        runtime,
        "ephemeris_call",
        lambda *a: ((10.0, 0, 1, 1, 0, 0), (4 if mask == 2 else 2) | 256),
    )
    with pytest.raises(RuntimeError):
        sun_at_tt(2451545.0, require_swiss_files=backend == "swieph", backend=backend)
