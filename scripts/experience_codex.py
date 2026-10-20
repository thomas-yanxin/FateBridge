"""Replay fictional CLI, REST and real stdio journeys; no LLM or user config writes.

Run with the installed project interpreter:
    python scripts/experience_codex.py --output /tmp/fatebridge-experience
"""

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import jsonschema
from fastapi.testclient import TestClient
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from fatebridge import __version__
from fatebridge.api import app as rest_app
from fatebridge.application.examples import example_input, suggested_fields
from fatebridge.services.tool_catalog import CATALOG

AS_OF = "2026-10-12T04:00:00Z"
CASES = [
    "bazi_birth",
    "bazi_career",
    "timing_analysis",
    "ziwei_birth",
    "astro_chart",
    "astro_hellen",
    "two_person_compatibility",
    "meihua_analysis",
    "sixyao",
    "qimen",
    "fengshui_directions",
    "knowledge_read",
]


def save(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


async def exercise(output):
    records = {spec.key: spec for spec in CATALOG}
    report = {
        "version": __version__,
        "as_of": AS_OF,
        "scope": "local CLI, in-process REST, independent stdio MCP; fictional inputs",
        "mcp_profiles": {},
        "cases": [],
        "errors": [],
    }
    with tempfile.TemporaryDirectory(prefix="fatebridge-journey-") as cwd:
        for label, scenario in [("all", ""), ("career", "onda-shiye")]:
            with (output / f"{label}-stderr.log").open("w") as log:
                transport = StdioTransport(
                    command=sys.executable,
                    args=["-m", "fatebridge.mcp_server"],
                    cwd=cwd,
                    env={
                        "FATEBRIDGE_MCP_FAMILIES": "",
                        "FATEBRIDGE_MCP_SCENARIOS": scenario,
                    },
                    log_file=log,
                )
                started = time.monotonic()
                async with Client(transport, timeout=60) as client:
                    tools = {tool.name: tool for tool in await client.list_tools()}
                    report["mcp_profiles"][label] = {
                        "tool_count": len(tools),
                        "startup_and_list_ms": round(
                            (time.monotonic() - started) * 1000, 2
                        ),
                        "tools_wire_bytes": len(
                            json.dumps(
                                [
                                    t.model_dump(mode="json", by_alias=True)
                                    for t in tools.values()
                                ],
                                ensure_ascii=False,
                            ).encode()
                        ),
                    }
                    if label == "career":
                        scenario_data = await client.read_resource(
                            "fatebridge://scenarios/onda-shiye"
                        )
                        manifest = json.loads(scenario_data[0].text)
                        assert manifest["scenarios"][0]["availability"]["complete"]
                        continue
                    alias = await client.read_resource(
                        "fatebridge://tools/astro_hellen"
                    )
                    assert (
                        json.loads(alias[0].text)["tools"][0]["tool"]
                        == "astro_hellen_chart"
                    )
                    for key in CASES:
                        spec = records[key]
                        inputs = example_input(spec)
                        assert inputs is not None, key
                        result = await client.call_tool(
                            spec.tool_name,
                            {**inputs, "as_of": AS_OF},
                            raise_on_error=False,
                        )
                        assert not result.is_error, (key, result.structured_content)
                        data = result.structured_content
                        jsonschema.Draft202012Validator(
                            tools[spec.tool_name].model_dump(by_alias=True)[
                                "outputSchema"
                            ]
                        ).validate(data)
                        save(output / f"{key}.json", {"input": inputs, "result": data})
                        business = [
                            name
                            for name in data
                            if name
                            not in {"run_metadata", "snapshot_text", "snapshot_export"}
                        ]
                        fields = suggested_fields(spec) or business[:1]
                        projected = await client.call_tool(
                            spec.tool_name,
                            {
                                **inputs,
                                "as_of": AS_OF,
                                "fields": fields,
                                "strict_fields": True,
                            },
                            raise_on_error=False,
                        )
                        assert not projected.is_error, (
                            key,
                            projected.structured_content,
                        )
                        save(
                            output / f"{key}-projected.json",
                            projected.structured_content,
                        )
                        assert (
                            data["run_metadata"]["business_output_sha256"]
                            == projected.structured_content["run_metadata"][
                                "business_output_sha256"
                            ]
                        )
                        full_size = len(json.dumps(data, ensure_ascii=False).encode())
                        small_size = len(
                            json.dumps(
                                projected.structured_content, ensure_ascii=False
                            ).encode()
                        )
                        report["cases"].append(
                            {
                                "tool": spec.tool_name,
                                "ok": True,
                                "full_bytes": full_size,
                                "projected_bytes": small_size,
                                "fields": fields,
                                "business_sha256": data["run_metadata"][
                                    "business_output_sha256"
                                ],
                            }
                        )
                    base = example_input(records["bazi_birth"])
                    bad_cases = [
                        ({"birth_month": 2, "birth_day": 30}, "validation_error"),
                        ({"birth_hour": None}, "validation_error"),
                        ({"birth_minut": 31}, "validation_error"),
                        (
                            {"fields": ["bazi_birth.day_mastr"], "strict_fields": True},
                            "validation_error",
                        ),
                    ]
                    for overrides, error_code in bad_cases:
                        result = await client.call_tool(
                            "bazi_birth", {**base, **overrides}, raise_on_error=False
                        )
                        assert (
                            result.is_error
                            and result.structured_content["error_code"] == error_code
                        )
                        report["errors"].append(
                            {
                                "overrides": overrides,
                                "result": result.structured_content,
                            }
                        )
                    corrected = await client.call_tool(
                        "bazi_birth",
                        {
                            **base,
                            "fields": ["bazi_birth.day_master"],
                            "strict_fields": True,
                        },
                    )
                    assert not corrected.is_error
                    report["error_recovery"] = True
    # REST matching discovery and recovery, using the same fictional input.
    with TestClient(rest_app) as rest:
        search = rest.get("/api/tools", params={"q": "跳槽", "detail": "summary"})
        assert search.status_code == 200 and search.json()["matched_count"] > 0
        spec = records["bazi_birth"]
        inputs = example_input(spec)
        invalid = rest.post(
            spec.rest_path, json={**inputs, "birth_month": 2, "birth_day": 30}
        )
        valid = rest.post(
            spec.rest_path,
            json=inputs,
            params=[
                ("fields", "bazi_birth.day_master"),
                ("strict_fields", "true"),
                ("as_of", AS_OF),
            ],
        )
        assert invalid.status_code == 422 and valid.status_code == 200
        report["rest"] = {
            "search_count": search.json()["matched_count"],
            "invalid_status": invalid.status_code,
            "corrected_status": valid.status_code,
        }
    root = Path(__file__).resolve().parents[1]
    command = [
        sys.executable,
        "-m",
        "fatebridge.cli",
        "profile",
        "--systems",
        "bazi,八字,astro",
        "--subject-file",
        str(root / "examples/demo-subject.json"),
        "--as-of",
        AS_OF,
        "--fields",
        "profile.bazi.bazi_birth.day_master",
        "profile.astro.chart_profile",
        "--strict-fields",
        "--compact",
    ]
    response = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert response.returncode == 0, response.stdout
    data = json.loads(response.stdout)
    assert set(data["profile"]) == {"bazi", "astro"}
    save(output / "cli-profile.json", data)
    report["cli"] = {
        "profile_exit": response.returncode,
        "profile_bytes": len(response.stdout.encode()),
        "deduplicated_systems": list(data["profile"]),
    }
    report["ok"] = True
    save(output / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    directory = parser.parse_args().output
    directory.mkdir(parents=True, exist_ok=True)
    asyncio.run(exercise(directory))
