"""An evaluation's declared solar backend must reach its real MCP child."""

import json
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from scripts.evaluate_agent import command_for
from tests.fixtures.mcp_result_delivery import read_full_result

ROOT = Path(__file__).resolve().parents[2]
MODE = "FATEBRIDGE_SOLAR_TERM_MODEL"
SPK = "FATEBRIDGE_SOLAR_SPK_FILE"


def server_settings(command):
    settings = {}
    for index, token in enumerate(command[:-1]):
        if token == "-c":
            key, value = command[index + 1].split("=", 1)
            settings[key] = json.loads(value)
    return settings


@pytest.mark.parametrize(
    "mode", ["auto", "native", "de440", "analytic", "spk", "invalid"]
)
def test_explicit_source_selection_survives_cli_mcp_environment(mode, monkeypatch):
    monkeypatch.setenv(MODE, mode)
    monkeypatch.setenv(SPK, "/data/solar kernel.bsp")
    settings = server_settings(command_for("codex", ROOT, Path("/output"), {}))
    prefix = "mcp_servers.fatebridge.env."
    assert settings.get(prefix + MODE) == mode
    assert settings.get(prefix + SPK) == "/data/solar kernel.bsp"


def test_unspecified_selection_stays_unspecified_and_secrets_are_not_forwarded(
    monkeypatch,
):
    monkeypatch.delenv(MODE, raising=False)
    monkeypatch.delenv(SPK, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-value-must-not-be-forwarded")
    settings = server_settings(command_for("codex", ROOT, Path("/output"), {}))
    assert "mcp_servers.fatebridge.env." + MODE not in settings
    assert "mcp_servers.fatebridge.env." + SPK not in settings
    assert not any("API_KEY" in key for key in settings)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode,parent_after_build,expected",
    [
        ("native", "auto", "fatebridge_complete_moshier_solar_v1"),
        ("auto", "native", "fatebridge_de440_solar_v1"),
    ],
)
async def test_actual_mcp_uses_the_constructed_configuration(
    mode, parent_after_build, expected, monkeypatch, tmp_path
):
    monkeypatch.setenv(MODE, mode)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.delenv(SPK, raising=False)
    settings = server_settings(command_for("codex", ROOT, tmp_path, {}))
    prefix = "mcp_servers.fatebridge.env."
    env = {
        key[len(prefix) :]: value
        for key, value in settings.items()
        if key.startswith(prefix)
    }
    # A different parent mode makes omission of the explicit setting observable.
    monkeypatch.setenv(MODE, parent_after_build)
    transport = StdioTransport(
        command=settings["mcp_servers.fatebridge.command"],
        args=settings["mcp_servers.fatebridge.args"],
        cwd=str(ROOT),
        env=env,
        log_file=tmp_path / "mcp-stderr.log",
    )
    async with Client(transport) as client:
        result = await client.call_tool(
            "heluo",
            {
                "date": "2024-03-28",
                "time": "00:40",
                "zone": "Europe/London",
                "gender": "女",
                "use_true_solar_time": False,
                "fields": ["solar_term.boundary_context"],
                "strict_fields": True,
                "include_snapshot_text": False,
                "response_char_limit": 8192,
            },
            raise_on_error=False,
        )
        assert not result.is_error
        assert len(result.content[0].text) <= 8192
        inline = result.structured_content
        receipt = inline["result_delivery"]
        assert "sha256" not in receipt
        # Compact receipts may omit file_path. Read every page of this run
        # through MCP and check the complete manifest, offsets and metadata.
        data = await read_full_result(client, inline)
        run_id = data["run_metadata"]["run_id"]
        verified = json.loads(
            (
                await client.read_resource(
                    f"fatebridge://results/{receipt['result_id']}/verified/{run_id}/0"
                )
            )[0].text
        )
        assert verified["result_id"] == receipt["result_id"]
        assert verified["total_chars"] == receipt["total_chars"]
        assert verified["verification"]["method"] == "retained_payload_integrity_v2"
        assert verified["verification"]["scope"] == "entire_retained_payload"
        assert verified["verification"]["run_id"] == run_id
        assert verified["verification"]["calculation_repeated"] is False
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        assert verified["text"] == text[:2048]
        assert data["run_metadata"]["runtime"]["solar_term_policy"]["mode"] == mode
        rows = data["solar_term"]["boundary_context"]["dependencies"]
        assert {row["record"]["ephemeris_model"] for row in rows} == {expected}
        for row in rows:
            record = row["record"]
            details = record["solar_model_details"]
            assert details["model_id"] == expected
            assert record["resolution_provider"] == (
                "fatebridge_moshier" if mode == "native" else "jpl_de440"
            )
            assert "ephemeris_retflags" not in record
            assert details["accuracy_certified"] is False
