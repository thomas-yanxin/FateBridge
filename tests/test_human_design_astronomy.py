"""Independent fixed TT/root observations, full backend scope and honest failures."""

import ast
import copy
import csv
import hashlib
import io
import json
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core import human_design_backend as backend_module
from fatebridge.core.astro import runtime
from fatebridge.core.human_design import bodygraph, chart_at_tt, positions_at_tt
from fatebridge.core.human_design_backend import (
    compare_full_backends,
    full_backend_report,
)
from fatebridge.core.human_design_personality_color import personality_colors
from fatebridge.core.human_design_time import sun_at_tt
from fatebridge.validation.human_design_astronomy import physical_astronomy_checks
from fatebridge.validation.human_design_backend import verify_full_backend_report

ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads(
    (ROOT / "tests/fixtures/human-design-astronomy-plan.json").read_text()
)
REFERENCE = json.loads(
    (ROOT / "tests/fixtures/human-design-astronomy-de440.json").read_text()
)
CASE = json.loads(
    (ROOT / "tests/fixtures/human-design-full-backend-case.json").read_text()
)


def current_chart(side):
    # Preserve frozen coordinates, epochs and observations. The stored1.10
    # descriptive circuit groups are intentionally not rewritten in the fixture.
    # These backend tests need a current derived graph as their valid baseline.
    chart = copy.deepcopy(CASE[side])
    # The current protocol separates a node's computation model from its raw
    # flag label. Derive the added label from the frozen flags; keep all stored
    # observations and numeric fields intact, without rewriting the fixture.
    for rows in chart["activations"].values():
        for row in rows:
            if row["body"] in {"NorthNode", "SouthNode"}:
                row["native_return_flag_model"] = runtime.ephemeris_model_from_retflag(
                    row["return_flags"]
                )
    chart["bodygraph"] = bodygraph(
        (a["gate"] for a in chart["activations"]["personality"]),
        (a["gate"] for a in chart["activations"]["design"]),
    )
    # Add the current derived category layer from unchanged frozen raw Color.
    # Every original Variable field and all frozen observations remain intact.
    chart["variables"]["personality_colors"] = personality_colors(chart["activations"])
    return chart


@pytest.mark.parametrize("side", ["selected", "reference"])
def test_current_backend_adapter_preserves_every_frozen_activation_field(side):
    chart = current_chart(side)
    assert {
        k: v for k, v in chart["variables"].items() if k != "personality_colors"
    } == CASE[side]["variables"]
    assert chart["variables"]["personality_colors"] == personality_colors(
        chart["activations"]
    )
    for layer, rows in chart["activations"].items():
        for row, frozen in zip(rows, CASE[side]["activations"][layer]):
            comparable = {
                k: v for k, v in row.items() if k != "native_return_flag_model"
            }
            assert comparable == frozen


def test_independent_reference_keeps_predeclared_epochs_targets_roots_and_sources():
    assert len(REFERENCE["pairs"]) == 122
    labels = ["1800-01-01T00:00:00", "2399-12-31T23:59:00"] + [
        f"{y}-{md}T12:00:00" for y in range(1800, 2400, 10) for md in ("01-01", "07-02")
    ]
    assert [p["label"] for p in REFERENCE["pairs"]] == [
        x + " TT" for x in sorted(labels)
    ]
    assert PLAN["bodies"] == dict(
        Sun=10,
        Moon=301,
        Mercury=1,
        Venus=2,
        Mars=4,
        Jupiter=5,
        Saturn=6,
        Uranus=7,
        Neptune=8,
        Pluto=9,
    )
    assert PLAN["comparison_tolerance_arcseconds"] == 2.0
    assert PLAN["design_root_time_tolerance_seconds"] == 5.0
    assert (
        hashlib.sha256((ROOT / REFERENCE["plan_path"]).read_bytes()).hexdigest()
        == REFERENCE["plan_sha256"]
    )
    source = ROOT / "scripts/gen_human_design_astronomy_reference.py"
    assert (
        hashlib.sha256(source.read_bytes()).hexdigest() == REFERENCE["generator_sha256"]
    )
    imports = [
        n.module or ""
        for n in ast.walk(ast.parse(source.read_text()))
        if isinstance(n, ast.ImportFrom)
    ]
    assert all(not x.startswith(("fatebridge", "swisseph", "tests")) for x in imports)
    origin = datetime(2000, 1, 1, 12)
    for pair in REFERENCE["pairs"]:
        expected_tt = (
            2451545
            + (
                datetime.fromisoformat(pair["label"].removesuffix(" TT")) - origin
            ).total_seconds()
            / 86400
        )
        assert pair["personality"]["jd_tt"] == expected_tt
        assert 70 < expected_tt - pair["design"]["jd_tt"] < 110
        arc = (
            pair["personality"]["positions"]["Sun"]["longitude"]
            - pair["design"]["positions"]["Sun"]["longitude"]
        ) % 360
        assert abs(arc - 88) * 3600 <= 0.00005
        for side in ("personality", "design"):
            assert {
                k: v["target_id"] for k, v in pair[side]["positions"].items()
            } == PLAN["bodies"]


def test_horizons_raw_tt_anchors_crosscheck_the_independent_pipeline():
    path = ROOT / "tests/fixtures/human-design-astronomy-horizons.json"
    reference = json.loads(path.read_text())
    assert (
        reference["de440_reference_sha256"]
        == hashlib.sha256(
            (ROOT / "tests/fixtures/human-design-astronomy-de440.json").read_bytes()
        ).hexdigest()
    )
    assert reference["plan_sha256"] == REFERENCE["plan_sha256"]
    assert (
        reference["generator_sha256"]
        == hashlib.sha256(
            (ROOT / "scripts/gen_human_design_astronomy_horizons.py").read_bytes()
        ).hexdigest()
    )
    assert [r["body"] for r in reference["records"]] == ["Sun", "Moon", "Pluto"]
    count = 0
    for record in reference["records"]:
        assert (
            hashlib.sha256(record["raw_response_utf8"].encode()).hexdigest()
            == record["raw_response_sha256"]
        )
        assert json.loads(record["raw_response_utf8"]) == record["response"]
        assert record["parameters"]["TIME_TYPE"] == "'TT'"
        table = record["response"]["result"].split("$$SOE")[1].split("$$EOE")[0].strip()
        assert len(record["rows"]) == 6
        for raw, parsed in zip(csv.reader(io.StringIO(table)), record["rows"]):
            assert float(raw[0]) == parsed["jd_tt"]
            assert float(raw[3]) == parsed["longitude"]
            pair = next(r for r in REFERENCE["pairs"] if r["label"] == parsed["label"])
            skyfield = pair[parsed["side"]]["positions"][record["body"]]["longitude"]
            assert skyfield == parsed["skyfield_longitude"]
            error = abs((skyfield - parsed["longitude"] + 180) % 360 - 180) * 3600
            assert error == parsed["error_arcseconds"]
            assert error <= 2.0
            count += 1
    assert count == 18


def test_fixed_independent_reference_keeps_moshier_position_and_line_failures():
    report = physical_astronomy_checks(ROOT)
    selected, moshier = report["selected"], report["moshier_diagnostic"]
    assert moshier["same_epoch_observations_checked"] == 2440
    assert moshier["same_epoch_observations_within_tolerance"] < 2440
    assert moshier["status"] == "failed"
    assert moshier["design_roots_checked"] == 122
    row = next(
        r
        for r in moshier["same_epoch_rows"]
        if r["label"] == "1810-07-02T12:00:00 TT"
        and r["side"] == "design"
        and r["body"] == "Pluto"
    )
    assert row["different_levels"] == ["line", "color", "tone", "base"]
    assert row["error_arcseconds"] > 3
    # File-less CI must retain the selected backend failure, not skip it or
    # mistake the requested SWIEPH flag for actual high-precision data.
    if selected["models"] == ["moshier"]:
        assert selected["status"] == "failed"
    else:
        assert selected["models"] == ["swieph"]
        assert selected["status"] == "bounded_independent_physical_checks_passed"


def test_full_backend_reference_recomputes_own_root_and_every_activation(monkeypatch):
    selected, alternate = current_chart("selected"), current_chart("reference")
    original = copy.deepcopy(selected)
    calls = []

    def at(jd_tt, node_mode, **kwargs):
        calls.append((jd_tt, node_mode, kwargs))
        return copy.deepcopy(alternate)

    monkeypatch.setattr(backend_module, "chart_at_tt", at)
    report = compare_full_backends(selected, "true")
    assert selected == original
    assert calls == [
        (
            selected["time_scales"]["personality"]["jd_tt"],
            "true",
            {"backend": "moshier"},
        )
    ]
    assert len(report["rows"]) == 26
    assert report["design_time_difference_seconds"] != 0
    assert all(
        r["selected_jd_tt"] != r["reference_jd_tt"]
        for r in report["rows"]
        if r["side"] == "design"
    )
    pluto = next(
        r for r in report["rows"] if r["side"] == "design" and r["body"] == "Pluto"
    )
    assert (pluto["selected"]["line"], pluto["reference"]["line"]) == (6, 5)
    assert pluto["selected"]["gate"] == pluto["reference"]["gate"] == 63
    assert report["independent_astronomy_certified"] is False
    payload = {
        **selected,
        "calculation_policy": {"node_mode": "true"},
        "ephemeris_backend_comparison": report,
    }
    assert verify_full_backend_report(payload)["errors"] == []


@pytest.mark.parametrize(
    "bad",
    [
        "missing_row",
        "wrong_root_shift",
        "invented_certificate",
        "reference_color",
        "reference_model",
        "reference_native_flag",
        "reference_birth",
        "reference_graph",
        "summary",
        "status",
    ],
)
def test_full_backend_local_verifier_rejects_forged_context(bad):
    selected, alternate = current_chart("selected"), current_chart("reference")
    report = full_backend_report(selected, alternate, "true")
    assert (
        verify_full_backend_report(
            {
                **selected,
                "calculation_policy": {"node_mode": "true"},
                "ephemeris_backend_comparison": report,
            }
        )["errors"]
        == []
    )
    if bad == "missing_row":
        report["rows"].pop()
    elif bad == "wrong_root_shift":
        report["design_time_difference_seconds"] = 0
    elif bad == "invented_certificate":
        report["subdivision_accuracy_certified"] = True
    elif bad == "reference_color":
        alternate["activations"]["design"][0]["color"] = 0
    elif bad == "reference_model":
        alternate["activations"]["design"][0]["ephemeris_model"] = "swieph"
    elif bad == "reference_native_flag":
        next(
            row
            for row in alternate["activations"]["design"]
            if row["body"] == "NorthNode"
        )["native_return_flag_model"] = "swieph"
    elif bad == "reference_birth":
        alternate["time_scales"]["personality"]["jd_tt"] += 1
    elif bad == "reference_graph":
        alternate["bodygraph"]["channels"].pop()
    elif bad == "summary":
        report["joint_evidence_summary"]["line_fixing_change_count"] += 1
    else:
        report["status"] = "same_backend_not_independent"
    payload = {
        **selected,
        "calculation_policy": {"node_mode": "true"},
        "ephemeris_backend_comparison": report,
    }
    assert verify_full_backend_report(payload)["errors"]


def test_no_data_or_same_backend_does_not_become_full_comparison(monkeypatch):
    def failed(*args, **kwargs):
        raise RuntimeError("unavailable")

    monkeypatch.setattr(backend_module, "chart_at_tt", failed)
    report = compare_full_backends(CASE["selected"], "true")
    assert (
        report["status"] == "reference_unavailable"
        and report["reference_chart"] is None
    )
    same = compare_full_backends(CASE["reference"], "true")
    assert same["status"] == "same_backend_not_independent" and same["rows"] == []
    assert same["joint_evidence_summary"] is None


def test_forced_moshier_backend_is_explicit_and_does_not_mutate_operator_path():
    from fatebridge.core.ephemeris_runtime import configured_ephemeris_path

    before = configured_ephemeris_path()
    chart = chart_at_tt(2451545.0, backend="moshier")
    assert configured_ephemeris_path() == before
    assert {
        a["ephemeris_model"] for rows in chart["activations"].values() for a in rows
    } == {"moshier"}
    with pytest.raises(ValueError):
        positions_at_tt(2451545, "true", backend="moshier", require_swiss_files=True)
    with pytest.raises(ValueError):
        sun_at_tt(2451545, True, backend="moshier")
    with pytest.raises(ValueError):
        positions_at_tt(2451545, "true", backend="unknown")


def test_reference_backend_requires_actual_return_flags(monkeypatch):
    monkeypatch.setattr(
        runtime,
        "ephemeris_call",
        lambda *args: (
            (10, 0, 0, 1, 0, 0),
            runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED,
        ),
    )
    with pytest.raises(RuntimeError):
        positions_at_tt(2451545, "true", backend="moshier")
    with pytest.raises(RuntimeError):
        sun_at_tt(2451545, backend="moshier")


def test_analytic_mean_node_flag_cannot_turn_moshier_into_file_comparison():
    from tests.ephemeris_context import moshier_ephemeris

    with moshier_ephemeris():
        chart = chart_at_tt(2451545, "mean")
        report = compare_full_backends(chart, "mean")
    north = next(
        a for a in chart["activations"]["personality"] if a["body"] == "NorthNode"
    )
    assert north["return_flags"] == runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED
    assert north["ephemeris_model"] == "swisseph_analytical_mean_node"
    assert north["native_return_flag_model"] == "swieph"
    assert report["selected_models"] == ["moshier", "swisseph_analytical_mean_node"]
    assert report["selected_physical_models"] == ["moshier"]
    assert report["status"] == "same_backend_not_independent"
    assert report["reference_chart"] is None and report["mean_node_flag_scope"]
