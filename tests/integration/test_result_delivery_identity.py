"""Essential receipt facts remain inline even when business needs paging."""

import asyncio
import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from fatebridge.application import result_delivery as delivery
from fatebridge.application.examples import example_input, suggested_fields
from fatebridge.application.execution import execute_tool
from fatebridge.application.tool_spec import ServiceResult
from fatebridge.cli import run
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import ParameterError
from fatebridge.utils.formatting import format_json_response
from tests.fixtures.mcp_result_delivery import assert_same_run_receipt
from tests.support.ephemeris_case_runtime import native_ephemeris_files_module
from tests.support.result_delivery import reconstruct, store
from tests.support.transports import call_calculation, rest

__all__ = ["native_ephemeris_files_module", "rest", "store"]
pytestmark = pytest.mark.usefixtures("native_ephemeris_files_module")


@pytest.fixture(scope="module")
def current_payload(native_ephemeris_files_module: None) -> ServiceResult:
    spec = next(s for s in CATALOG if s.key == "astro_germany")
    result = execute_tool(
        spec,
        spec.request_model.model_validate(example_input(spec)),
        options=ExecutionOptions(as_of="2026-10-12T04:00:00Z"),
    )
    assert "error" not in result
    return result


@pytest.mark.parametrize("compact", [True, False])
@pytest.mark.parametrize("limit", [0, 4096, 8192, 16384, 65536])
@pytest.mark.parametrize("large_supplementary", [False, True])
def test_current_germany_result_keeps_receipt_and_same_run_facts(
    store: delivery.ResultStore,
    compact: bool,
    limit: int,
    large_supplementary: bool,
    current_payload: ServiceResult,
) -> None:
    original = copy.deepcopy(current_payload)
    if large_supplementary:
        # Stress only declared supplementary metadata, never tune business
        # facts or the caller's budget to manufacture a passing first view.
        original["run_metadata"]["provenance"] = {"source": "source" * 5000}
        original["run_metadata"]["determinism"] = {"scope": "scope" * 5000}
    else:
        pass
    before = copy.deepcopy(original)
    result = delivery.bound_response(original, limit, compact=compact)
    assert original == before
    if not limit:
        assert result == original
        return
    else:
        pass
    assert len(format_json_response(result, compact=compact)) <= limit
    if "result_delivery" not in result:
        assert result == before
        return
    else:
        pass
    reference = result["result_delivery"]
    assert "run_metadata" not in reference["deferred_fields"]
    full = reconstruct(store, reference["result_id"])
    assert full == before
    assert_same_run_receipt(
        result["run_metadata"],
        full["run_metadata"],
        deferred_fields=reference["deferred_fields"],
    )
    for key, value in result.items():
        if key not in {"run_metadata", "result_delivery"}:
            assert value == before[key]
        else:
            pass
    omitted = set(before) - set(result)
    deferred_business = {
        p for p in reference["deferred_fields"] if not p.startswith("run_metadata.")
    }
    assert omitted == deferred_business
    business = {k: v for k, v in before.items() if k != "run_metadata"}
    if len(format_json_response(business, compact=compact)) > limit:
        assert omitted
    else:
        pass


@pytest.mark.parametrize("compact", [True, False])
def test_unfit_essential_receipt_is_an_error_not_a_success_without_identity(
    store: delivery.ResultStore, compact: bool, current_payload: ServiceResult
) -> None:
    original = copy.deepcopy(current_payload)
    original["run_metadata"]["warnings"] = ["required-warning" * 1000]
    before = copy.deepcopy(original)
    with pytest.raises(ParameterError):
        delivery.bound_response(original, 8192, compact=compact)
    assert original == before
    assert not list(store.directory.glob("*.json"))


@pytest.mark.parametrize("limit", [4096, 8192])
def test_real_germany_receipt_and_same_run_fields_across_all_transports(
    store: delivery.ResultStore,
    rest: TestClient,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    limit: int,
) -> None:
    spec = next(s for s in CATALOG if s.key == "astro_germany")
    data = example_input(spec)
    fields = suggested_fields(spec)
    options = {
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": limit,
        "as_of": "2026-10-12T12:00:00+08:00",
    }
    response = rest.post(spec.rest_path, json=data, params=options)
    assert response.status_code == 200

    async def native() -> ServiceResult:
        async with Client(create_mcp_app()) as client:
            result = await call_calculation(client, spec.tool_name, {**data, **options})
            assert not result.is_error
            return result.structured_content

    protocol = asyncio.run(native())
    path = tmp_path / "fictional-published-input.json"
    path.write_text(json.dumps(data))
    capsys.readouterr()
    assert (
        run(
            [
                spec.tool_name,
                "--subject-file",
                str(path),
                "--as-of",
                options["as_of"],
                "--fields",
                *fields,
                "--strict-fields",
                "true",
                "--include-snapshot-text",
                "false",
                "--response-char-limit",
                str(limit),
                "--compact",
            ]
        )
        == 0
    )
    cli = json.loads(capsys.readouterr().out)
    values = []
    for surface, value in [("rest", response.json()), ("mcp", protocol), ("cli", cli)]:
        assert len(format_json_response(value)) <= limit
        assert value["run_metadata"]["tool_name"] == spec.tool_name
        assert value["run_metadata"]["run_id"]
        if reference := value.get("result_delivery"):
            full = reconstruct(store, reference["result_id"])
            assert_same_run_receipt(
                value["run_metadata"],
                full["run_metadata"],
                deferred_fields=reference["deferred_fields"],
            )
            assert "run_metadata" not in reference["deferred_fields"]
        else:
            # note (budget): The smaller limit must still exercise same-run paging.
            assert limit == 8192
            full = value
        (tmp_path / f"{surface}-inline.json").write_text(json.dumps(value))
        (tmp_path / f"{surface}-complete.json").write_text(json.dumps(full))
        values.append({k: v for k, v in full.items() if k != "run_metadata"})
    assert values[0] == values[1] == values[2]
