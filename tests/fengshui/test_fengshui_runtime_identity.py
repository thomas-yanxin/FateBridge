"""Observed calculation identity and honest calendar fallback receipts."""

import asyncio
import hashlib
import json
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pygeomag
import pytest
from pygeomag import geomag

from fatebridge.cli import run
from fatebridge.core.fengshui import calendar, geomagnetic
from fatebridge.core.fengshui.geomagnetic_inputs import GeomagneticReference
from fatebridge.services import replay_metadata
from fatebridge.services.fengshui import (
    calculate_annual_stars,
    calculate_directions,
    calculate_minggua,
    calculate_xuankong_natal,
)
from fatebridge.services.run_metadata import attach_run_metadata
from tests.fengshui.test_fengshui_geomagnetic import FOLDER, inputs
from tests.fixtures.fengshui import payload
from tests.support.fengshui_transports import mcp_call
from tests.support.transports import rest_client


def test_installed_algorithm_identity_matches_independently_pinned_wheel():
    reference = json.loads((FOLDER / "implementation-reference.json").read_text())
    for name, module in (
        ("pygeomag/__init__.py", pygeomag),
        ("pygeomag/geomag.py", geomag),
    ):
        assert (
            hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
            == reference["source_files"][name]
        )
    value = geomagnetic.geomagnetic_reference(
        GeomagneticReference.model_validate(inputs())
    )
    model = value["model"]
    identity = model["implementation_identity"]
    assert model["implementation"] == "pygeomag==" + replay_metadata.version("pygeomag")
    assert identity["source_sha256"] == reference["source_files"]["pygeomag/geomag.py"]
    assert identity["validated_wheel_match"] is True
    assert str(Path(geomag.__file__).parent) not in json.dumps(model)


@pytest.mark.parametrize(
    "fault",
    [
        "distribution_version",
        "missing_metadata",
        "module_version",
        "algorithm_source",
        "package_source",
        "unreadable_source",
    ],
)
def test_unsupported_runtime_rejects_model_without_breaking_plain_directions(
    monkeypatch, tmp_path, fault
):
    if fault == "distribution_version":
        monkeypatch.setattr(geomagnetic, "version", lambda _: "9.9.9")
    elif fault == "missing_metadata":

        def missing(_):
            raise PackageNotFoundError("pygeomag")

        monkeypatch.setattr(geomagnetic, "version", missing)
    elif fault == "module_version":
        monkeypatch.delattr(pygeomag, "__version__")
    else:
        changed = tmp_path / "untrusted.py"
        if fault != "unreadable_source":
            changed.write_text("# deliberately differs from the independent wheel\n")
        monkeypatch.setattr(
            pygeomag if fault == "package_source" else geomag, "__file__", str(changed)
        )
    with pytest.raises(ImportError):
        geomagnetic.geomagnetic_reference(GeomagneticReference.model_validate(inputs()))
    assert (
        calculate_directions(bearing_degrees=0, north_reference="true")["status"]
        == "complete"
    )


def test_mismatch_is_a_correlated_dependency_fault_on_rest_mcp_cli(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(geomagnetic, "version", lambda _: "9.9.9")
    request = {"geomagnetic_reference": inputs(), "trace_id": "dependency-identity"}
    http = rest_client(monkeypatch).post(
        "/api/fengshui/directions",
        json={"geomagnetic_reference": inputs()},
        params={"trace_id": "dependency-identity"},
    )
    protocol = asyncio.run(mcp_call("directions", request))
    path = tmp_path / "input.json"
    path.write_text(json.dumps({"geomagnetic_reference": inputs()}))
    code = run(
        [
            "fengshui_directions",
            "--request-file",
            str(path),
            "--trace-id",
            "dependency-identity",
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 503
    assert protocol.is_error and code != 0
    for body in (http.json(), protocol.structured_content, cli):
        assert body["error_code"] == "dependency_missing"
        assert body["retryable"] is False
        assert body["trace_id"] == "dependency-identity"
        assert "layers" not in body


def test_runtime_receipt_includes_observed_pygeomag_version(monkeypatch):
    original = replay_metadata.version
    replay_metadata.environment_receipt.cache_clear()
    try:
        before = replay_metadata.environment_receipt()
        assert before["dependencies"]["pygeomag"] == original("pygeomag")
        monkeypatch.setattr(
            replay_metadata,
            "version",
            lambda name: "9.9.9" if name == "pygeomag" else original(name),
        )
        replay_metadata.environment_receipt.cache_clear()
        after = replay_metadata.environment_receipt()
        assert after["dependencies"]["pygeomag"] == "9.9.9"
        assert after != before
    finally:
        replay_metadata.environment_receipt.cache_clear()


@pytest.mark.parametrize("kind", ["annual", "birth_date", "period"])
def test_used_calendar_fallback_reaches_outer_receipt_even_away_from_boundary(
    monkeypatch, kind
):
    original = calendar.lichun_resolution
    fallback = lambda *a: {
        **original(*a),
        "provider": "linear_fallback",
        "approximate": True,
    }
    monkeypatch.setattr(calendar, "lichun_resolution", fallback)
    # bazhai and xuankong bind this helper explicitly as well.
    from fatebridge.core.fengshui import bazhai, xuankong

    monkeypatch.setattr(bazhai, "lichun_resolution", fallback)
    monkeypatch.setattr(xuankong, "lichun_resolution", fallback)
    if kind == "annual":
        result = calculate_annual_stars(effective_year=2026)
    elif kind == "birth_date":
        result = calculate_minggua(birth_date="2000-07-01", gender_convention="male")
    else:
        request = payload("xuankong_natal")
        request["period"] = {
            "basis": "construction_completion",
            "effective_event_year": 2004,
            "evidence": "fixture only",
        }
        result = calculate_xuankong_natal(**request)
    assert result["status"] == "complete"
    assert (
        attach_run_metadata(result, tool_name="fengshui_" + kind)["run_metadata"][
            "engine_is_approximate"
        ]
        is True
    )


def test_no_false_degradation_from_unused_solver_or_statistical_uncertainty(
    monkeypatch,
):
    monkeypatch.setattr(calendar.almanac, "swe", None)
    # No solar-term lookup is needed for a confirmed effective birth year.
    monkeypatch.setattr(
        calendar, "lichun_resolution", lambda *a: pytest.fail("unused solver called")
    )
    result = calculate_minggua(effective_birth_year=2000, gender_convention="male")
    assert (
        attach_run_metadata(result, tool_name="fengshui_minggua")["run_metadata"][
            "engine_is_approximate"
        ]
        is False
    )
    result = calculate_directions(geomagnetic_reference=inputs())
    assert (
        attach_run_metadata(result, tool_name="fengshui_directions")["run_metadata"][
            "engine_is_approximate"
        ]
        is False
    )
    unrelated = {"approximate": True, "evidence": {"provider": "linear_fallback"}}
    assert (
        attach_run_metadata(unrelated, tool_name="fengshui_assess")["run_metadata"][
            "engine_is_approximate"
        ]
        is False
    )
