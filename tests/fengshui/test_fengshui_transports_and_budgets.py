"""Three-surface parity (REST/MCP/CLI), projection, latency, and budget tests."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest
from fastmcp import Client

import fatebridge.mcp_server as mcp
from fatebridge.application.examples import example_input
from fatebridge.application.execution import execute_with_receipt
from fatebridge.application.response_delivery import deliver_response
from fatebridge.cli import run
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.schema_cache import model_schema
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.fengshui import payload
from tests.support.fengshui_transports import SPECS, mcp_call
from tests.support.mcp_result_assertions import without_transport
from tests.support.transports import call_calculation, rest_client

STANDALONE_TOOLS = (
    "fengshui_directions",
    "fengshui_minggua",
    "fengshui_bazhai",
    "fengshui_jinsuo",
    "fengshui_annual_stars",
    "fengshui_monthly_stars",
    "fengshui_xuankong_house_chart",
)


@pytest.mark.parametrize(
    "name",
    [
        "directions",
        "minggua",
        "bazhai",
        "jinsuo",
        "annual_stars",
        "monthly_stars",
        "xuankong_natal",
        "assess",
    ],
)
def test_three_surface_parity_audit_and_compact(
    name: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec = SPECS[name]
    inputs = payload(name)
    for detail in ("audit", "compact"):
        http = rest_client(monkeypatch).post(
            spec.rest_path,
            json=inputs,
            params={"detail": detail, "as_of": "2026-10-12T12:00:00+08:00"},
        )
        assert http.status_code == 200, http.text

        async def _mcp():
            async with Client(mcp.app) as client:
                return await call_calculation(
                    client,
                    spec.name,
                    {**inputs, "detail": detail, "as_of": "2026-10-12T12:00:00+08:00"},
                )

        protocol = asyncio.run(_mcp())
        assert not protocol.is_error
        req_file = tmp_path / f"{name}_{detail}.json"
        req_file.write_text(json.dumps(inputs), encoding="utf-8")
        capsys.readouterr()
        code = run(
            [
                spec.name,
                "--request-file",
                str(req_file),
                "--detail",
                detail,
                "--as-of",
                "2026-10-12T12:00:00+08:00",
            ]
        )
        assert code == 0
        cli_out = json.loads(capsys.readouterr().out)
        assert (
            without_transport(http.json())
            == without_transport(protocol.structured_content)
            == without_transport(cli_out)
        )


def test_invalid_projection_path_reports_constraints_available() -> None:
    res = asyncio.run(
        mcp_call(
            "directions",
            {
                "bearing_degrees": 0,
                "north_reference": "magnetic",
                "fields": ["layers.directions.nonexistent"],
            },
        )
    )
    assert res.is_error
    issue = res.structured_content["issues"][0]
    assert issue["code"] == "unknown_projection_path"
    assert "bearing" in issue["constraints"]["available"]


def test_latency_and_payload_and_schema_budgets() -> None:
    options = ExecutionOptions(detail="audit", as_of="2026-10-12T12:00:00+08:00")
    for spec in [s for s in CATALOG if s.family == "fengshui"]:
        ex = example_input(spec)
        if ex is None:
            ex = {"query_at": "2026-02-04T12:00:00+08:00"}
        req = spec.request_model.model_validate(ex)
        svc_fn, pos, kw = spec.bind(req)
        svc_fn(*pos, **kw)
        t0 = time.perf_counter()
        for _ in range(25):
            svc_fn(*pos, **kw)
        svc_ms = (time.perf_counter() - t0) * 1000 / 25
        assert svc_ms < 3.0, f"{spec.name} too slow: {svc_ms:.2f} ms"

        audit = execute_with_receipt(spec, req, options=options)
        compact = deliver_response(audit, spec=spec, detail="compact")
        compact_kb = len(json.dumps(compact, ensure_ascii=False).encode()) / 1024
        out_schema_kb = (
            len(
                json.dumps(model_schema(spec.output_model), ensure_ascii=False).encode()
            )
            / 1024
        )
        assert out_schema_kb < 6.0, f"{spec.name} out schema {out_schema_kb:.1f}KB"
        assert compact_kb < 4.0, f"{spec.name} compact {compact_kb:.1f}KB"
        if spec.name in STANDALONE_TOOLS:
            audit_kb = len(json.dumps(audit, ensure_ascii=False).encode()) / 1024
            assert audit_kb < 20.0, f"{spec.name} audit {audit_kb:.1f}KB"
