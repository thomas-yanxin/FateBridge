"""Actual REST, FastMCP protocol and CLI parity, not just service calls."""

import asyncio
import json
import math
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.description import describe_spec
from fatebridge.cli import run
from tests.fixtures.fengshui import PAYLOADS, payload
from tests.support.fengshui_transports import SPECS, mcp_call
from tests.support.mcp_result_assertions import (
    same_run_projected_response,
    without_transport,
)
from tests.support.transports import rest_client


@pytest.mark.parametrize("name", list(PAYLOADS))
def test_all_residential_tools_match_rest_mcp_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    name,
) -> None:
    inputs = payload(name)
    response = rest_client(monkeypatch).post(
        SPECS[name].rest_path, json=inputs, params={"detail": "audit"}
    )
    protocol = asyncio.run(mcp_call(name, inputs))
    request_file = tmp_path / "住宅.json"
    request_file.write_text(json.dumps(inputs, ensure_ascii=False))
    code = run(
        [SPECS[name].name, "--request-file", str(request_file), "--detail", "audit"]
    )
    cli_body = json.loads(capsys.readouterr().out)
    assert response.status_code == 200, response.text
    assert not protocol.is_error
    assert code == 0
    assert (
        without_transport(response.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli_body)
    )
    schema = SPECS[name].output_model.model_json_schema()
    for body in [response.json(), protocol.structured_content, cli_body]:
        Draft202012Validator(schema).validate(body)
        assert body["status"] == "complete"
        assert body["run_metadata"]["tool_name"] == SPECS[name].name
        if name == "xuankong_natal":
            ruleset = next(
                ruleset
                for ruleset in body["rulesets"]
                if ruleset["ruleset_id"] == "xuankong_zhongzhou_v1"
            )
            assert ruleset["source_citations"]["X1"]["retrieved_at"] == "2026-10-12"
        else:
            pass


@pytest.mark.parametrize(
    "name,inputs",
    [
        ("assess", {"house": {"facing_degrees": 180}}),
        (
            "assess",
            {
                "house": {
                    "sitting_trigram": "乾",
                    "facing_degrees": 180,
                    "north_reference": "true",
                }
            },
        ),
        ("minggua", {"ruleset_id": "unknown_v9"}),
        ("annual_stars", {"query_at": "2026-01-01T00:00:00"}),
        (
            "assess",
            {
                "features": [
                    {
                        "object_id": "x",
                        "direction": "N",
                        "classification": "water",
                        "classification_basis": "guessed",
                        "evidence": "猜测",
                    }
                ]
            },
        ),
        ("assess", {"house": {"facing_degreess": 180}}),
        ("assess", {"unrecognized": True}),
        (
            "xuankong_natal",
            {"house": {"facing_degrees": 180, "north_reference": "true"}},
        ),
        (
            "xuankong_natal",
            {
                "period": {
                    "basis": "construction_completion",
                    "effective_event_year": 2004,
                    "evidence": "竣工",
                    "guess_period": 8,
                }
            },
        ),
        (
            "xuankong_natal",
            {
                "period": {
                    "basis": "confirmed_major_renovation",
                    "period_number": 9,
                    "evidence": "油漆",
                }
            },
        ),
    ],
)
def test_invalid_nested_inputs_fail_on_every_surface(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    name: str,
    inputs,
) -> None:
    rest = rest_client(monkeypatch).post(SPECS[name].rest_path, json=inputs)
    protocol = asyncio.run(mcp_call(name, inputs))
    path = tmp_path / "request.json"
    path.write_text(json.dumps(inputs))
    code = run([SPECS[name].name, "--request-file", str(path)])
    body = json.loads(capsys.readouterr().out)
    assert rest.status_code == 422
    assert protocol.is_error
    assert code == 1
    assert (
        rest.json()["issues"] == protocol.structured_content["issues"] == body["issues"]
    )
    assert (
        rest.json()["error_code"]
        == protocol.structured_content["error_code"]
        == body["error_code"]
        == "validation_error"
    )


def test_partial_is_success_not_protocol_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    inputs = {"methods": ["bazhai", "jinsuo", "annual_stars"]}
    rest = rest_client(monkeypatch).post(
        "/api/fengshui/assess", json=inputs, params={"detail": "audit"}
    )
    protocol = asyncio.run(mcp_call("assess", inputs))
    path = tmp_path / "selected-layers.json"
    path.write_text(json.dumps(inputs))
    code = run(["fengshui_assess", "--request-file", str(path), "--detail", "audit"])
    assert code == 0 and rest.status_code == 200 and not protocol.is_error
    assert json.loads(capsys.readouterr().out)["status"] == "partial"
    assert without_transport(rest.json()) == without_transport(
        protocol.structured_content
    )


@pytest.mark.parametrize("angle", [7.5, 355.5, None])
def test_natal_boundary_or_missing_input_is_partial_on_all_surfaces(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    angle: float | None,
) -> None:
    inputs = payload("xuankong_natal")
    if angle is None:
        inputs.pop("house")
    else:
        inputs["house"]["facing_degrees"] = angle
    rest = rest_client(monkeypatch).post(
        "/api/fengshui/xuankong-house-chart", json=inputs, params={"detail": "audit"}
    )
    protocol = asyncio.run(mcp_call("xuankong_natal", inputs))
    path = tmp_path / "natal.json"
    path.write_text(json.dumps(inputs))
    assert (
        run(
            [
                "fengshui_xuankong_house_chart",
                "--request-file",
                str(path),
                "--detail",
                "audit",
            ]
        )
        == 0
    )
    cli_body = json.loads(capsys.readouterr().out)
    assert rest.status_code == 200 and not protocol.is_error
    assert (
        without_transport(rest.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli_body)
    )
    assert cli_body["status"] == "partial"
    assert cli_body["layers"]["xuankong_natal"]["chart"] is None


@pytest.mark.parametrize(
    "angle,mode",
    [
        (math.nextafter(355.5, -math.inf), "replacement"),
        (math.nextafter(355.5, math.inf), "lower"),
        (math.nextafter(7.5, -math.inf), "lower"),
        (math.nextafter(7.5, math.inf), "lower"),
    ],
)
def test_precise_near_boundaries_have_one_chart_on_all_surfaces(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    angle,
    mode: str,
) -> None:
    inputs = payload("xuankong_natal")
    inputs["house"]["facing_degrees"] = angle
    rest = rest_client(monkeypatch).post(
        SPECS["xuankong_natal"].rest_path, json=inputs, params={"detail": "audit"}
    )
    protocol = asyncio.run(mcp_call("xuankong_natal", inputs))
    path = tmp_path / "precise.json"
    path.write_text(json.dumps(inputs))
    assert (
        run(
            [
                "fengshui_xuankong_house_chart",
                "--request-file",
                str(path),
                "--detail",
                "audit",
            ]
        )
        == 0
    )
    body = json.loads(capsys.readouterr().out)
    assert rest.status_code == 200 and not protocol.is_error
    assert (
        without_transport(rest.json())
        == without_transport(protocol.structured_content)
        == without_transport(body)
    )
    layer = body["layers"]["xuankong_natal"]
    assert body["status"] == "complete" and len(layer["candidates"]) == 1
    assert layer["chart"]["chart_mode"] == mode


def test_complete_four_layers_are_separate_on_all_surfaces(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    inputs = payload("assess")
    natal = payload("xuankong_natal")
    inputs["house"] = natal.pop("house")
    inputs["xuankong"] = natal
    inputs["methods"] = ["bazhai", "jinsuo", "annual_stars", "xuankong_natal"]
    rest = rest_client(monkeypatch).post(
        SPECS["assess"].rest_path, json=inputs, params={"detail": "audit"}
    )
    protocol = asyncio.run(mcp_call("assess", inputs))
    path = tmp_path / "four-layers.json"
    path.write_text(json.dumps(inputs))
    assert (
        run(["fengshui_assess", "--request-file", str(path), "--detail", "audit"]) == 0
    )
    body = json.loads(capsys.readouterr().out)
    assert rest.status_code == 200 and not protocol.is_error
    assert (
        without_transport(rest.json())
        == without_transport(protocol.structured_content)
        == without_transport(body)
    )
    assert body["status"] == "complete"
    assert set(body["layers"]) == set(inputs["methods"])
    annual, natal_layer = (
        body["layers"]["annual_stars"],
        body["layers"]["xuankong_natal"],
    )
    assert annual["current_period"]["number"] == 9
    assert natal_layer["period_context"]["number"] == 8
    assert "annual_star_number" not in natal_layer["chart"]["palaces"]["C"]
    assert "mountain_star_number" not in annual["palaces"]["C"]


def test_natal_projection_and_annual_layer_match_all_transports(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    inputs = payload("xuankong_natal")
    inputs = {
        "house": inputs["house"],
        "xuankong": {"period": inputs["period"]},
        "effective_year": 2026,
        "methods": ["annual_stars", "xuankong_natal"],
    }
    field = "layers.xuankong_natal.chart.palaces.C.mountain_star_number"
    rest = rest_client(monkeypatch).post(
        "/api/fengshui/assess",
        json=inputs,
        params={"fields": field, "detail": "audit"},
    )
    protocol = asyncio.run(mcp_call("assess", {**inputs, "fields": [field]}))
    path = tmp_path / "combined.json"
    path.write_text(json.dumps(inputs))
    assert (
        run(
            [
                "fengshui_assess",
                "--request-file",
                str(path),
                "--fields",
                field,
                "--detail",
                "audit",
            ]
        )
        == 0
    )
    cli_body = json.loads(capsys.readouterr().out)
    assert rest.status_code == 200 and not protocol.is_error
    assert (
        without_transport(rest.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli_body)
    )
    assert (
        cli_body["layers"]["xuankong_natal"]["chart"]["palaces"]["C"][
            "mountain_star_number"
        ]
        == 6
    )


def test_natal_nested_cli_flags_succeed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    inputs = payload("xuankong_natal")
    assert (
        run(
            [
                "fengshui_xuankong_house_chart",
                "--house",
                json.dumps(inputs["house"]),
                "--period",
                json.dumps(inputs["period"]),
            ]
        )
        == 0
    )
    body = json.loads(capsys.readouterr().out)
    assert body["status"] == "complete"
    assert "snapshot_export" not in body


def test_projection_flags_match(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    field = "layers.annual_stars.palaces.S.annual_star_number"
    inputs = {"effective_year": 2026}
    rest = rest_client(monkeypatch).post(
        "/api/fengshui/annual-stars",
        json=inputs,
        params={"fields": field},
    )
    protocol = asyncio.run(
        mcp_call(
            "annual_stars",
            {**inputs, "fields": [field], "detail": "compact"},
        )
    )
    code = run(
        [
            "fengshui_annual_stars",
            "--effective-year",
            "2026",
            "--fields",
            field,
            "--detail",
            "compact",
        ]
    )
    cli_body = json.loads(capsys.readouterr().out)
    assert code == 0 and rest.status_code == 200 and not protocol.is_error
    assert (
        without_transport(rest.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli_body)
    )
    assert cli_body["layers"]["annual_stars"]["palaces"]["S"] == {
        "annual_star_number": 5
    }
    assert "snapshot_text" not in cli_body
    Draft202012Validator(
        SPECS["annual_stars"].output_model.model_json_schema()
    ).validate(cli_body)


def test_discovery_publishes_nested_inputs_and_outputs_on_three_surfaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = rest_client(monkeypatch).get("/api/tools").json()["tools"]
    for spec in SPECS.values():
        descriptor = describe_spec(spec)
        assert descriptor["surfaces"]["cli"] and descriptor["cli_request_file"]
        assert descriptor["input_schema"] and descriptor["output_schema"]
        assert any(r["tool"] == spec.name for r in records)


def test_cli_explicit_flags_override_request_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "request.json"
    path.write_text(
        json.dumps({"effective_birth_year": 1990, "gender_convention": "female"})
    )
    code = run(
        [
            "fengshui_minggua",
            "--request-file",
            str(path),
            "--gender-convention",
            "male",
        ]
    )
    body = json.loads(capsys.readouterr().out)
    assert code == 0
    assert body["layers"]["minggua"]["time_context"]["effective_year"] == 1990
    assert body["layers"]["minggua"]["candidates"][0]["trigram"] == "坎"


def test_cli_nested_json_flags_are_usable(capsys: pytest.CaptureFixture[str]) -> None:
    inputs = payload("assess")
    args = ["fengshui_assess"]
    for key, value in inputs.items():
        args += [
            "--" + key.replace("_", "-"),
            json.dumps(value) if isinstance(value, (dict, list)) else str(value),
        ]
    assert run(args) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "complete"


@pytest.mark.parametrize("content", ["[1,2]", "{invalid"])
def test_cli_malformed_request_file_is_json_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], content: str
) -> None:
    path = tmp_path / "request.json"
    path.write_text(content)
    assert run(["fengshui_assess", "--request-file", str(path)]) == 2
    assert json.loads(capsys.readouterr().out)["error_code"] == "usage_error"
