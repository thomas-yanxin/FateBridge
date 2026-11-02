"""Exercise actual REST, native in-process MCP and CLI for the same inputs."""

import asyncio
import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.examples import example_input, suggested_fields
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG


async def _same_run_payload(client, result, *, require_business_inline=False):
    """Check actual evidence visibility, including an explicitly deferred runtime.

    A delivery reference may now point only to metadata. Presence of that
    reference is not a proxy for missing calculation facts. Compare every
    business value to the exact stored run instead of weakening the evidence.
    """
    assert not result.is_error, result
    first = result.structured_content
    assert len(json.dumps(first, ensure_ascii=False, separators=(",", ":"))) <= 8192
    ref = first.get("result_delivery")
    if ref is None:
        return first
    parts = []
    uri = ref.get("first_page_uri")
    if uri is None:
        manifest = json.loads((await client.read_resource(ref["manifest_uri"]))[0].text)
        assert manifest["result_id"] == ref["result_id"]
        assert manifest["sha256"] == ref["sha256"]
        assert manifest["run_metadata"]["run_id"] == first["run_metadata"]["run_id"]
        uri = manifest["first_page_uri"]
    while uri:
        page = json.loads((await client.read_resource(uri))[0].text)
        parts.append(page["text"])
        uri = page["next_uri"]
    raw = "".join(parts)
    assert hashlib.sha256(raw.encode()).hexdigest() == ref["sha256"]
    original = json.loads(raw)
    receipt = first["run_metadata"]
    runtime = receipt.get("runtime", {})
    full_receipt = original["run_metadata"]
    if "run_metadata" in ref["deferred_fields"]:
        assert ref["deferred_fields"] == ["run_metadata"]
        assert set(receipt) == {
            "run_id",
            "trace_id",
            "tool_name",
            "generated_at",
            "engine",
            "engine_is_approximate",
        }
        assert receipt == {key: full_receipt[key] for key in receipt}
    elif runtime.get("delivery_path") == "run_metadata.runtime":
        assert "run_metadata.runtime" in ref["deferred_fields"]
        full_runtime = full_receipt["runtime"]
        files = full_runtime["ephemeris"]["files"]
        assert runtime["ephemeris_files_count"] == len(files)
        digest = hashlib.sha256(
            json.dumps(
                files, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        assert (
            runtime["ephemeris_inventory_sha256"]
            == full_runtime["ephemeris"]["sha256"]
            == digest
        )
        assert runtime["environment_sha256"] == full_runtime["environment_sha256"]
        restored_receipt = {**receipt, "runtime": full_runtime}
        for path in ref["deferred_fields"]:
            if path in {"run_metadata.provenance", "run_metadata.determinism"}:
                key = path.removeprefix("run_metadata.")
                assert key not in receipt
                restored_receipt[key] = full_receipt[key]
        assert restored_receipt == full_receipt
    else:
        assert receipt == full_receipt
    if require_business_inline:
        assert "run_metadata" not in ref["deferred_fields"]
        business_deferred = {
            p for p in ref["deferred_fields"] if not p.startswith("run_metadata.")
        }
        assert business_deferred == set(original) - set(first)
        for key in set(original) & set(first) - {"run_metadata"}:
            assert first[key] == original[key]
        if business_deferred:
            # The successor receipt contract keeps identities and hashes
            # inline. Paging is permitted only if even a lower bound with
            # every optional locator/supplement removed exceeds8192.
            essential = {
                k: v
                for k, v in receipt.items()
                if k not in {"provenance", "determinism"}
            }
            minimal_ref = {k: ref[k] for k in ("result_id", "sha256", "manifest_uri")}
            floor = {
                **original,
                "run_metadata": essential,
                "result_delivery": minimal_ref,
            }
            assert (
                len(json.dumps(floor, ensure_ascii=False, separators=(",", ":"))) > 8192
            )
        for key in (
            "run_id",
            "trace_id",
            "input_sha256",
            "contract_sha256",
            "business_output_sha256",
        ):
            assert receipt[key] == full_receipt[key]
    return original


@pytest.mark.parametrize(
    "key,view",
    [
        ("taiyi", None),
        ("taiyi", "annual_cycles"),
        ("taiyi", "conditions"),
        ("taiyi", "enclosures"),
        ("taiyi", "oppositions"),
        ("taiyi", "counts"),
        ("taiyi", "count_sources"),
        ("taiyi", "shiji_derivation"),
        ("taiyi", "elemental_relations"),
        ("taiyi", "victory_matrix"),
        ("taiyi", "gates"),
        ("taiyi", "gate_comparison"),
        ("taiyi", "determinate"),
        ("sanshiunited", None),
        ("sanshiunited", "taiyi_depth"),
        ("sanshiunited", "palace_correspondences"),
        ("sanshiunited", "annual_cycles"),
        ("sanshiunited", "taiyi_conditions"),
        ("sanshiunited", "taiyi_enclosures"),
        ("sanshiunited", "taiyi_oppositions"),
        ("sanshiunited", "taiyi_counts"),
        ("sanshiunited", "taiyi_count_sources"),
        ("sanshiunited", "taiyi_shiji_derivation"),
        ("sanshiunited", "taiyi_elemental_relations"),
        ("sanshiunited", "taiyi_victory_matrix"),
        ("sanshiunited", "taiyi_gates"),
        ("sanshiunited", "taiyi_gate_comparison"),
        ("sanshiunited", "taiyi_determinate"),
    ],
)
@pytest.mark.parametrize(
    "mode,hour_profile,month_profile",
    [
        ("year", None, None),
        ("month", None, None),
        ("month", None, "key_month_tianzheng_jie_v1"),
        ("day", None, None),
        ("hour", None, None),
        ("hour", "key_hour_winter_jiazi_v1", None),
    ],
)
def test_published_first_views_preserve_evidence_under_default_limits(
    key, view, mode, hour_profile, month_profile
):
    spec = next(s for s in CATALOG if s.key == key)
    inputs = example_input(spec)
    assert inputs is not None
    if key == "taiyi":
        inputs["calculation_mode"] = mode
        if month_profile:
            inputs["month_profile"] = month_profile
        if hour_profile:
            inputs["hour_profile"] = hour_profile
    else:
        inputs["taiyi_options"] = {"calculation_mode": mode}
        if month_profile:
            inputs["taiyi_options"]["month_profile"] = month_profile
        if hour_profile:
            inputs["taiyi_options"]["hour_profile"] = hour_profile

    async def protocol():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                spec.tool_name,
                {
                    **inputs,
                    "fields": suggested_fields(spec, view=view),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
                raise_on_error=False,
            )
            body = await _same_run_payload(client, result, require_business_inline=True)
            return result, body

    result, body = asyncio.run(protocol())
    assert not result.is_error, result
    # Every requested business value was checked against the same-run archive.
    if view in {"conditions", "taiyi_conditions"}:
        assessment = body["taiyi"]["condition_assessment"]
        assert len(assessment["five_generals"]["clauses"]) == 3
        assert assessment["three_gates"]["status"] == (
            "not_assessed" if mode in {"hour", "day"} or month_profile else "computed"
        )
        from fatebridge.core.metaphysics.taiyi_conditions import conjunction

        assert assessment["menju_jiangfa"] is conjunction(
            assessment["five_generals"]["conditions_satisfied"],
            assessment["three_gates"].get("conditions_satisfied"),
        )
        assert body["taiyi"]["ruleset"]["classical_acceptance_passed"] is False
    elif view in {"counts", "taiyi_counts"}:
        assessed = body["taiyi"]["count_assessment"]
        assert len(assessed["entries"]) == 2 and len(assessed["sources"]) == 5
        assert assessed["overall_harmony_assessed"] is False
        assert len(assessed["unadjudicated_source_readings"]) == 2
    elif view in {"oppositions", "taiyi_oppositions"}:
        assessed = body["taiyi"]["opposition_assessment"]
        assert len(assessed["entries"]) == 6
        assert assessed["main_names_unified"] is False
        assert all(
            row["status"] in {"opposite", "not_opposite", "no_ring_bearing"}
            for row in assessed["entries"]
        )
        assert body["taiyi"]["ruleset"]["classical_acceptance_passed"] is False
    elif view in {"enclosures", "taiyi_enclosures"}:
        assessment = body["taiyi"]["enclosure_assessment"]
        assert assessment["principal_enclosure"]["status"] == "assessed_geometry"
        assert type(assessment["principal_enclosure"]["present"]) is bool
        assert {p["name"] for p in assessment["unassessed"]} == {
            "挟闭",
            "四郭固",
            "四郭杜",
        }
        assert {p["status"] for p in assessment["unassessed"]} == {"not_assessed"}
        assert body["taiyi"]["ruleset"]["classical_acceptance_passed"] is False
        assert body["taiyi"]["ruleset"]["real_world_efficacy"] == "not_tested"
    elif view in {"gates", "taiyi_gates", "gate_comparison", "taiyi_gate_comparison"}:
        gates = body["taiyi"]["gates"]
        if mode == "hour" and hour_profile is None:
            assert gates["status"] == "not_computed_for_selected_mode"
            assert gates["reason"] and gates["selected_profile"] is None
        else:
            assert gates["status"] == "computed"
            assert gates["selected_profile"]
    elif view in {"determinate", "taiyi_determinate"}:
        result = body["taiyi"]["determinate_calculation"]
        assert result["status"] == (
            "not_computed_for_selected_mode"
            if mode == "hour" and hour_profile is None
            else "computed"
        )
    elif view == "annual_cycles":
        cycles = body["taiyi"]["long_cycles"]
        assert cycles["time_granularity"] == "year"
        if mode == "year":
            assert len(cycles["records"]) == 11  # Ten markers plus 大游天目.
            assert cycles["ruleset"]["classical_acceptance_passed"] is False
        else:
            assert cycles["status"] == "not_computed_for_selected_mode"
    else:
        assert body["taiyi"]["ruleset"]["real_world_efficacy"] == "not_tested"
    if key == "sanshiunited" and view is None:
        assert body["synthesis"]["source_profiles"]["qimen"]
        profiles = body["qimen"]["rule_profiles"]
        for profile in ("god", "season", "wonder_tomb"):
            assert profiles[profile]["id"]
            assert profiles[profile]["source"]
            assert profiles[profile]["variant_note"]
        assert profiles["wonder_tomb"]["source_priority_resolved"] is False
        assert profiles["wonder_tomb"]["whole_book_conformance_established"] is False
        assert body["liureng"]["ruleset"]
        assert body["liureng"]["three_transmissions"]
        assert (
            body["synthesis"]["time_scopes"]["taiyi"]
            == {
                "year": "year",
                "month": "solar_month",
                "day": "selected_clock_day",
                "hour": "double_hour",
            }[mode]
        )


@pytest.mark.parametrize(
    "key,payload,fields",
    [
        (
            "taiyi",
            {
                "analysis_year": 2026,
                "analysis_month": 2,
                "analysis_day": 4,
                "analysis_hour": 12,
                "analysis_timezone": "Asia/Shanghai",
                "use_true_solar_time": False,
            },
            ["taiyi", "snapshot_text"],
        ),
        (
            "sanshiunited",
            {
                "date": "2026-02-04",
                "time": "12:00:00",
                "zone": "Asia/Shanghai",
                "use_true_solar_time": False,
            },
            ["taiyi", "synthesis", "snapshot_text"],
        ),
    ],
)
@pytest.mark.parametrize(
    "mode,hour_profile,month_profile",
    [
        ("year", None, None),
        ("month", None, None),
        ("month", None, "key_month_tianzheng_jie_v1"),
        ("day", None, None),
        ("hour", None, None),
        ("hour", "key_hour_winter_jiazi_v1", None),
    ],
)
def test_taiyi_evidence_across_real_transports(
    monkeypatch, capsys, key, payload, fields, mode, hour_profile, month_profile
):
    payload = dict(payload)
    if key == "taiyi":
        payload.update(calculation_mode=mode, analysis_second=2)
        if month_profile:
            payload["month_profile"] = month_profile
        if hour_profile:
            payload["hour_profile"] = hour_profile
    else:
        payload.update(taiyi_options={"calculation_mode": mode}, time="12:00:02")
        if month_profile:
            payload["taiyi_options"]["month_profile"] = month_profile
        if hour_profile:
            payload["taiyi_options"]["hour_profile"] = hour_profile
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    options = {
        "as_of": "2026-10-22T12:00:00+08:00",
        "fields": fields,
        "strict_fields": True,
        "response_char_limit": 0,
    }
    route = "/api/cn/taiyi" if key == "taiyi" else "/api/divination/sanshiunited"
    response = TestClient(api.app).post(
        route,
        json=payload,
        params=[
            ("as_of", options["as_of"]),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )
    assert response.status_code == 200, response.text

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                key, {**payload, **options}, raise_on_error=False
            )

    native = asyncio.run(protocol())
    assert not native.is_error, native
    mcp = native.structured_content
    assert mcp == json.loads(native.content[0].text)
    args = [key]
    for name, value in payload.items():
        args += [
            "--" + name.replace("_", "-"),
            json.dumps(value) if isinstance(value, dict) else str(value),
        ]
    args += [
        "--as-of",
        options["as_of"],
        "--strict-fields",
        "--response-char-limit",
        "0",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    status = run(args)
    cli = json.loads(capsys.readouterr().out)
    assert status == 0, cli
    bodies = [
        {k: v for k, v in body.items() if k != "run_metadata"}
        for body in (response.json(), mcp, cli)
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    taiyi = bodies[0]["taiyi"]
    if mode == "year":
        assert taiyi["calendar_rules"]["year"] == 2025
    else:
        assert taiyi["calendar_rules"]["calculation_mode"] == mode
        assert "12:00:02" in taiyi["calendar_rules"]["civil_datetime"]
    assert taiyi["ruleset"]["classical_acceptance_passed"] is False
    assert taiyi["ruleset"]["real_world_efficacy"] == "not_tested"
    assert "= " + str(taiyi["core_board"]["main_count"]) in bodies[0]["snapshot_text"]


def test_fabricated_offset_rejected_by_rest_mcp_and_cli(monkeypatch, capsys):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    payload = {
        "date": "2026-04-04",
        "time": "12:00:00",
        "use_true_solar_time": False,
        "taiyi_options": {"accNum": 1},
    }
    response = TestClient(api.app).post("/api/divination/sanshiunited", json=payload)
    assert response.status_code == 400
    assert "原典" in response.text

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool("sanshiunited", payload, raise_on_error=False)

    native = asyncio.run(protocol())
    assert native.is_error
    capsys.readouterr()
    code = run(
        [
            "sanshiunited",
            "--date",
            payload["date"],
            "--time",
            payload["time"],
            "--use-true-solar-time",
            "false",
            "--taiyi-options",
            json.dumps(payload["taiyi_options"]),
        ]
    )
    assert code != 0
    result = json.loads(capsys.readouterr().out)
    assert "taiyi" not in result


@pytest.mark.parametrize("mode", ["year", "day"])
def test_hour_profile_is_rejected_in_non_hour_mode_on_all_transports(
    monkeypatch, capsys, mode
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    payload = {
        "analysis_year": 2026,
        "analysis_month": 4,
        "analysis_day": 4,
        "analysis_hour": 12,
        "use_true_solar_time": False,
        "calculation_mode": mode,
        "hour_profile": "key_hour_winter_jiazi_v1",
    }
    response = TestClient(api.app).post("/api/cn/taiyi", json=payload)
    assert response.status_code == 400

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool("taiyi", payload, raise_on_error=False)

    native = asyncio.run(protocol())
    assert native.is_error
    status = run(
        [
            "taiyi",
            "--analysis-year",
            "2026",
            "--analysis-month",
            "4",
            "--analysis-day",
            "4",
            "--analysis-hour",
            "12",
            "--no-use-true-solar-time",
            "--calculation-mode",
            mode,
            "--hour-profile",
            "key_hour_winter_jiazi_v1",
        ]
    )
    body = json.loads(capsys.readouterr().out)
    assert status != 0
    for result in [response.json(), native.structured_content, body]:
        assert "hour_profile" in result["error"]
        assert "taiyi" not in result


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize("view", ["daily_calendar", "daily_essences"])
def test_daily_first_views_preserve_unknowns_and_source_variants(key, view):
    spec = next(s for s in CATALOG if s.key == key)
    inputs = example_input(spec)
    if key == "taiyi":
        inputs["calculation_mode"] = "day"
    else:
        inputs["taiyi_options"] = {"calculation_mode": "day"}

    async def protocol():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                spec.tool_name,
                {
                    **inputs,
                    "fields": suggested_fields(spec, view=view),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
                raise_on_error=False,
            )
            await _same_run_payload(client, result, require_business_inline=True)
            return result

    result = asyncio.run(protocol())
    assert not result.is_error
    body = result.structured_content
    # A runtime-only delivery reference is allowed; business deferral is not.
    if view == "daily_essences":
        records = body["taiyi"]["ten_jing"]["records"]
        assert len(records) == 10
        assert records["heaven_time"]["palace"] in "子丑寅卯辰巳午未申酉戌亥"
        assert records["heaven_time"]["rule_evidence"]["unresolved"]
        assert records["taiyi_ordinal"]["palace"] is None
        assert records["taiyi_ordinal"]["ordinal"]
        assert body["taiyi"]["ten_jing"]["classical_acceptance_passed"] is False
    else:
        assert (
            body["taiyi"]["calendar_rules"]["day_origin"]["day_boundary"]
            == "00:00_selected_clock_modern_convention"
        )


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
def test_daily_complete_board_paging_recovers_same_run_evidence_and_receipt(key):
    spec = next(s for s in CATALOG if s.key == key)
    inputs = example_input(spec)
    if key == "taiyi":
        inputs.update(calculation_mode="day", analysis_month=2, analysis_day=2)
    else:
        inputs.update(date="2026-02-02", taiyi_options={"calculation_mode": "day"})

    async def protocol():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                spec.tool_name,
                {
                    **inputs,
                    "fields": ["taiyi"],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert "result_delivery" in result.structured_content
            return await _same_run_payload(client, result)

    body = asyncio.run(protocol())
    records = body["taiyi"]["ten_jing"]["records"]
    assert records["heaven_time"]["palace"] == "酉"
    assert {
        c["source_value"] for c in records["eight_winds"]["source_comparisons"]
    } == {"乾", "艮"}
    assert records["eight_winds"]["palace"] == "巽"
    assert body["taiyi"]["core_board"]["main_count"] == 33
    assert body["taiyi"]["day_source_comparisons"][0]["source_value"] == 32
