"""Regression coverage for the first-use journeys a Codex user follows."""

import json
import shlex
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from fatebridge import cli
from fatebridge.api import app
from fatebridge.application.discovery import discover_specs
from fatebridge.application.examples import example_input, suggested_fields
from fatebridge.diagnostics import (
    _probe_stdio,
    _StdioProbeError,
    diagnose,
    resolve_codex_cli,
)
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import ParameterError
from tests.fixtures.mcp_receipt import verified_inline_business
from tests.support.mcp_result_assertions import same_run_projected_response
from tests.support.transports import cached_mcp_app, call_calculation

SUBJECT = str(Path(__file__).parents[2] / "examples/demo-subject.json")


def invoke(capsys, *args):
    code = cli.run(list(args))
    text = capsys.readouterr().out
    return code, json.loads(text), text


def test_tool_summary_search_keeps_filters() -> None:
    result = discover_specs(CATALOG, q="事业", surface="mcp", detail="summary")
    assert "bazi_career" in {tool["tool"] for tool in result["tools"]}
    limited = discover_specs(CATALOG, q="事业", family="bazi", detail="summary")
    assert limited["tools"] and all(t["family"] == "bazi" for t in limited["tools"])
    empty = discover_specs(CATALOG, q="事业", allowed_names=set(), detail="summary")
    assert empty["matched_count"] == 0
    response = TestClient(app).get(
        "/api/tools", params={"q": "事业", "detail": "summary"}
    )
    assert response.status_code == 200
    assert response.json()["matched_count"] > 0
    # A caller may pass an already scoped catalog, including no matching tool summaries.
    scoped = [spec for spec in CATALOG if spec.family == "fengshui"]
    assert discover_specs(scoped, q="事业", detail="summary")["matched_count"] == 0


def test_public_name_resolves_across_describe_discovery_and_cli(
    capsys: pytest.CaptureFixture[str],
) -> None:
    tool = "hellenistic_chart"
    code, result, _ = invoke(capsys, "describe", tool, "--detail", "input")
    assert code == 0
    assert result["key"] == "astro_hellen"
    assert result["tool"] == result["surfaces"]["cli_name"] == tool
    assert "output_schema" not in result
    assert discover_specs(CATALOG, tool=tool)["tools"][0]["tool"] == tool
    parser = cli.build_parser()
    flags = shlex.split(result["cli_example"])[2:]
    assert parser.parse_args([tool, *flags])._spec.key == "astro_hellen"

    code, error, _ = invoke(capsys, "describe", "astro_hellen", "--detail", "input")
    assert code == 2 and error["error_code"] == "unknown_tool"
    with pytest.raises(ParameterError):
        discover_specs(CATALOG, tool="astro_hellen")


@pytest.mark.local_data
def test_relationship_cli_retains_directional_evidence(
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec = next(s for s in CATALOG if s.key == "two_person_compatibility")
    example = cli._cli_example(
        spec, {**example_input(spec), "relationship_type": "marriage"}
    )
    code, result, _ = invoke(capsys, *shlex.split(example)[1:])
    assert code == 0
    assert result["relationship_type"] == "marriage"
    assert result["cross_chart_relations"]["pairs"]
    assert result["directional_ten_gods"]["person2_to_person1"]["target"] == "person1"


@pytest.mark.parametrize("systems", ["", ",, "])
def test_profile_empty_selection_is_failure(
    systems: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code, result, _ = invoke(capsys, "profile", "--systems", systems)
    assert code == 2 and result["error_code"] == "usage_error"


def test_profile_deduplicates_and_preserves_projected_receipts(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    original = cli.execute_tool
    calls = []

    def execute(spec, *args, **kwargs):
        calls.append(spec.key)
        return original(spec, *args, **kwargs)

    monkeypatch.setattr(cli, "execute_tool", execute)
    code, result, text = invoke(
        capsys,
        "profile",
        "--systems",
        "bazi,八字,bazi_birth_chart",
        "--subject-file",
        SUBJECT,
        "--fields",
        "profile.bazi.bazi_birth.day_master",
        "--strict-fields",
        "--compact",
    )
    assert code == 0 and calls == ["bazi_birth"]
    assert text.count("\n") == 1
    leg = result["profile"]["bazi"]
    assert set(leg) == {"bazi_birth", "run_metadata"}
    assert set(leg["bazi_birth"]) == {"day_master"}
    assert leg["run_metadata"]["parent_run_id"] == result["run_metadata"]["run_id"]


def test_profile_projection_keeps_failed_leg(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, result, _ = invoke(
        capsys,
        "profile",
        "--systems",
        "bazi,astro",
        "--subject-file",
        SUBJECT,
        "--birth-latitude",
        "91",
        "--fields",
        "profile.bazi.bazi_birth.day_master",
        "--strict-fields",
    )
    assert code == 1
    assert "day_master" in result["profile"]["bazi"]["bazi_birth"]
    assert result["profile"]["astro"]["error_code"] == "validation_error"


def test_profile_unknown_projection_is_actionable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, result, _ = invoke(
        capsys,
        "profile",
        "--systems",
        "bazi",
        "--subject-file",
        SUBJECT,
        "--fields",
        "profile.bazi.misspelled",
        "--strict-fields",
    )
    assert code == 1
    assert result["issues"][0]["path"] == "profile.bazi.misspelled"


@pytest.mark.parametrize("before", [True, False])
def test_metadata_switch_works_before_or_after_tool(
    before: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    command = [
        "bazi_birth_chart",
        "--subject-file",
        SUBJECT,
        "--fields",
        "analysis_type",
    ]
    command = ["--no-metadata", *command] if before else [*command, "--no-metadata"]
    code, result, _ = invoke(capsys, *command)
    assert code == 0 and "run_metadata" not in result


def test_profile_removes_child_snapshot_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, result, _ = invoke(
        capsys,
        "profile",
        "--systems",
        "bazi",
        "--subject-file",
        SUBJECT,
        "--no-include-snapshot-text",
    )
    assert code == 0
    assert "snapshot_text" not in result["profile"]["bazi"]
    assert "snapshot_export" in result["profile"]["bazi"]


def test_doctor_real_stdio_and_invalid_family() -> None:
    result = diagnose(mcp=True, family="bazi")
    assert result["ok"], result
    assert result["mcp"]["tool_count"] == result["mcp_tool_count"]
    assert result["mcp"]["smoke_tool"]
    assert Path(result["codex"]["config"]["command"]).is_absolute()
    empty = diagnose(family="missing-family")
    assert not empty["ok"] and empty["issues"][0]["code"] == "unknown_family"


@pytest.mark.asyncio
async def test_doctor_keeps_the_child_startup_failure_and_stage() -> None:
    with pytest.raises(_StdioProbeError) as caught:
        await _probe_stdio({"FATEBRIDGE_MCP_FAMILIES": "missing-family"})
    details = caught.value.details
    assert details["stage"] == "initialize"
    assert details["error_type"]
    assert "Traceback" in details["server_stderr"]
    assert len(details["server_stderr"]) <= 8192


def test_doctor_returns_structured_stdio_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail(env):
        raise _StdioProbeError("tools/list", OSError("probe failed"), "child stderr")

    monkeypatch.setattr("fatebridge.diagnostics._probe_stdio", fail)
    result = diagnose(mcp=True, family="bazi")
    assert not result["ok"]
    assert result["mcp"]["stage"] == "tools/list"
    assert result["mcp"]["error_type"] == "OSError"
    assert result["mcp"]["error"] == "probe failed"
    assert result["mcp"]["server_stderr"] == "child stderr"


def test_doctor_checks_active_dependency_markers_and_skips_unselected_extras(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "fatebridge.diagnostics.importlib.metadata.requires",
        lambda _: [
            "fastmcp>=3.4.2; python_version >= '3.10'",
            "absent-platform-package; sys_platform == 'imaginary'",
            "absent-dev-package; extra == 'dev'",
        ],
    )
    result = diagnose()
    assert result["ok"]
    assert set(result["dependencies"]) == {"fastmcp"}


@pytest.mark.asyncio
async def test_mcp_resource_requires_public_name_and_exposed_family() -> None:
    async with Client(cached_mcp_app(families="astro")) as client:
        for suffix in ("", "/input"):
            resource = await client.read_resource(
                f"fatebridge://tools/hellenistic_chart{suffix}"
            )
            assert (
                json.loads(resource[0].text)["tools"][0]["tool"] == "hellenistic_chart"
            )
            for old in ("astro_hellen_chart", "astro_hellen"):
                with pytest.raises(Exception, match="工具未在当前 MCP 配置中公开"):
                    await client.read_resource(f"fatebridge://tools/{old}{suffix}")
    async with Client(cached_mcp_app(families="bazi")) as client:
        with pytest.raises(Exception, match="工具未在当前 MCP 配置中公开"):
            await client.read_resource("fatebridge://tools/hellenistic_chart")


def test_doctor_prefers_running_desktop_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    desktop = tmp_path / "Desktop CLI" / "codex"
    desktop.parent.mkdir()
    desktop.write_text("#!/bin/sh\nexit 0\n")
    desktop.chmod(0o755)
    monkeypatch.setenv("CODEX_CLI_PATH", str(desktop))
    monkeypatch.setattr("fatebridge.diagnostics.shutil.which", lambda _: "/older/codex")
    result = diagnose()
    assert result["codex"]["cli"]["source"] == "desktop"
    assert shlex.split(result["codex"]["add_command"])[0] == str(desktop)
    assert result["codex"]["cli"]["path_cli"] == "/older/codex"


def test_nonexecutable_desktop_cli_falls_back_to_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    desktop = tmp_path / "codex"
    desktop.touch(mode=0o644)
    monkeypatch.setenv("CODEX_CLI_PATH", str(desktop))
    monkeypatch.setattr(
        "fatebridge.diagnostics.shutil.which", lambda _: "/terminal/codex"
    )
    assert resolve_codex_cli()["path"] == "/terminal/codex"


@pytest.mark.asyncio
async def test_mcp_input_contract_is_small_and_projections_are_callable() -> None:
    async with Client(cached_mcp_app(families="bazi")) as client:
        small = await client.read_resource("fatebridge://tools/bazi_career/input")
        full = await client.read_resource("fatebridge://tools/bazi_career")
        record = json.loads(small[0].text)["tools"][0]
        assert "output_schema" not in record
        assert "career_analysis" in record["output_fields"]
        assert len(small[0].text.encode()) < len(full[0].text.encode()) / 2
        result = await call_calculation(
            client,
            record["surfaces"]["mcp_name"],
            {
                **record["example_input"],
                "fields": ["career_analysis.evidence_chain.topic.first_view"],
                "strict_fields": True,
            },
        )
        restored = await verified_inline_business(client, result.structured_content)
        assert set(restored) == {"career_analysis", "run_metadata"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "key", ["analyze_destiny", "astro_chart", "ziwei_birth", "meihua_analysis"]
)
async def test_consultation_first_views_keep_interpretable_evidence_across_surfaces(
    key: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """A successful first call must contain the facts its reading relies on.

    This catches views which omitted structure rules, the Sun/Moon, palace
    stars, or moving line. Compare the transports each tool actually exposes.
    """
    spec = next(s for s in CATALOG if s.key == key)
    inputs = example_input(spec)
    as_of = "2026-10-15T12:00:00+08:00"
    fields = suggested_fields(spec)
    async with Client(cached_mcp_app()) as client:
        result = await call_calculation(
            client,
            spec.tool_name,
            {
                **inputs,
                "as_of": as_of,
                "fields": fields,
                "strict_fields": True,
                "include_snapshot_text": False,
            },
        )
        assert not result.is_error
        await verified_inline_business(client, result.structured_content)
    payload = result.structured_content
    assert not result.is_error
    if key == "analyze_destiny":
        assert payload["four_pillars"]["day"]["stem"]
        assert payload["day_master"]["element"]
        assert payload["ten_gods"]
        assert payload["structure_profile"]["decision_basis"]
        profile = payload["structure_profile"]
        assert profile["resolution_policy"] == "source_force_before_preference_v4"
        assert (
            payload["day_master"]["classical_adjudication"]["status"]
            == "not_adjudicated"
        )
        assert payload["day_master"]["classical_adjudication"]["body_strength"] is None
        reference = profile["dominant_structure"]
        assert reference["key"] == "month_use_reference"
        assert reference["formation_status"] == "not_adjudicated"
        assert reference["useful_elements"] == reference["avoid_elements"] == []
        assert set(profile["useful_elements"]).isdisjoint(profile["avoid_elements"])
        assert profile["layers"] and profile["conditional_elements"]
        assert payload["person_info"]["normalized_birth_datetime"]
    elif key == "astro_chart":
        assert {"Sun", "Moon"} <= {p["id"] for p in payload["planets"]}
        assert payload["aspects"] and all("orb" in a for a in payload["aspects"])
    elif key == "ziwei_birth":
        reading = payload["ziwei_birth"]["reading_view"]
        assert reading["schema_version"] == "ziwei_natal_reading_v1"
        assert len(reading["palaces"]) == 12
        assert sum(len(p["stars"]) for p in reading["palaces"]) == 66
        assert all(len(p["sanfang_sizheng_branches"]) == 4 for p in reading["palaces"])
        assert payload["ziwei_birth"]["sihua"]
    else:
        assert 1 <= payload["meihua"]["seed"]["moving_line"] <= 6
        assert payload["meihua"]["body_use_relation"]
        assert payload["analysis_context"]["analysis_datetime"]
    mcp_business = {
        k: v for k, v in payload.items() if k not in {"run_metadata", "result_delivery"}
    }
    query = [("fields", field) for field in fields] + [
        ("as_of", as_of),
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
    ]
    if spec.rest_path is not None:
        with TestClient(app) as rest:
            response = rest.post(spec.rest_path, json=inputs, params=query)
        assert response.status_code == 200, response.json()
        assert {
            k: v for k, v in response.json().items() if k != "run_metadata"
        } == mcp_business
    else:
        pass
    command = shlex.split(cli._cli_example(spec, example_input(spec)))[1:]
    code, cli_payload, _ = invoke(
        capsys,
        *command,
        "--as-of",
        as_of,
        "--fields",
        *fields,
        "--strict-fields",
        "--no-include-snapshot-text",
    )
    assert code == 0
    assert {k: v for k, v in cli_payload.items() if k != "run_metadata"} == mcp_business


def _schema_has_field_path(schema: dict, path: str) -> bool:
    defs = schema.get("$defs", {})

    def resolve(node):
        seen = set()
        while isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"]
                if not ref.startswith("#/$defs/") or ref in seen:
                    break
                else:
                    pass
                seen.add(ref)
                node = defs.get(ref.removeprefix("#/$defs/"), {})
                continue
            else:
                pass
            for branch in ("anyOf", "oneOf", "allOf"):
                if branch in node:
                    opts = [
                        o
                        for o in node[branch]
                        if isinstance(o, dict) and o.get("type") != "null"
                    ]
                    obj_opts = [
                        o
                        for o in opts
                        if o.get("type") == "object" or "properties" in o or "$ref" in o
                    ]
                    chosen = obj_opts[0] if obj_opts else (opts[0] if opts else None)
                    if chosen is not None and chosen is not node:
                        node = chosen
                        break
                    else:
                        pass
                else:
                    pass
            else:
                break
        return node if isinstance(node, dict) else {}

    node = resolve(schema)
    for part in path.split("."):
        node = resolve(node)
        props = node.get("properties")
        if isinstance(props, dict) and part in props:
            node = resolve(props[part])
            continue
        else:
            pass
        addl = node.get("additionalProperties")
        if addl is True:
            return True
        else:
            pass
        if isinstance(addl, dict):
            if addl.get("$ref") == "#/$defs/JsonValue":
                return True
            else:
                pass
            node = resolve(addl)
            continue
        else:
            pass
        if node.get("type") == "object" and "properties" not in node:
            return True
        else:
            pass
        return False
    return True


def test_published_starter_projection_is_runnable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from fatebridge.core.schema_cache import model_schema

    parser = cli.build_parser()
    starter_specs = [spec for spec in CATALOG if suggested_fields(spec) is not None]
    for spec in starter_specs:
        example = example_input(spec)
        spec.request_model.model_validate(example)
        command = shlex.split(cli._cli_example(spec, example))[1:]
        parsed = parser.parse_args(command)
        assert parsed._spec.key == spec.key
        schema = model_schema(spec.output_model)
        for field in suggested_fields(spec):
            assert _schema_has_field_path(schema, field), (spec.key, field)

    by_key = {spec.key: spec for spec in starter_specs}
    # Execute a representative fast tool from each family end-to-end via CLI.
    representative_keys = (
        "analyze_destiny",
        "bazi_birth",
        "bazi_career",
        "ziwei_birth",
        "astro_chart",
        "astro_hellen",
        "astro_india",
        "astro_guolao",
        "human_design",
        "meihua_analysis",
        "sixyao",
        "qimen",
        "liureng_gods",
        "taiyi",
        "jinkou",
        "fengshui_assess",
        "fengshui_directions",
        "suzhan",
        "otherbu",
        "heluo",
        "knowledge_read",
        "firdaria",
        "sukuyo_compatibility",
    )
    for key in representative_keys:
        spec = by_key[key]
        command = shlex.split(cli._cli_example(spec, example_input(spec)))[1:]
        code, result, _ = invoke(
            capsys,
            *command,
            "--as-of",
            "2026-10-12T04:00:00Z",
            "--fields",
            *suggested_fields(spec),
            "--strict-fields",
        )
        assert code == 0, (key, result)
        assert result["run_metadata"]["tool_name"] == spec.tool_name


@pytest.mark.asyncio
async def test_published_input_contract_delivers_strict_fields_from_one_run() -> None:
    async with Client(cached_mcp_app(families="bazi")) as client:
        tool = "bazi_career"
        resource = await client.read_resource(f"fatebridge://tools/{tool}/input")
        fields = json.loads(resource[0].text)["tools"][0]["suggested_fields"]
        spec = next(s for s in CATALOG if s.tool_name == tool)
        result = await call_calculation(
            client,
            tool,
            {
                **example_input(spec),
                "fields": fields,
                "strict_fields": True,
                "include_snapshot_text": False,
            },
        )
        payload = await same_run_projected_response(client, result)
        evidence = payload["career_analysis"]["evidence_chain"]["topic"]["first_view"]
        assert evidence["natal_stars"]
        assert "run_metadata" in payload


@pytest.mark.local_data
def test_relationship_example_and_default_do_not_assume_marriage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec = next(s for s in CATALOG if s.key == "two_person_compatibility")
    inputs = example_input(spec)
    assert inputs["relationship_type"] == "general"
    inputs.pop("relationship_type")
    assert spec.request_model.model_validate(inputs).relationship_type == "general"
    code, result, _ = invoke(capsys, *shlex.split(cli._cli_example(spec, inputs))[1:])
    assert code == 0 and result["relationship_type"] == "general"


@pytest.mark.asyncio
async def test_explicit_pillar_context_can_be_projected_without_a_retry() -> None:
    spec = next(s for s in CATALOG if s.key == "bazi_career")
    inputs = {**example_input(spec), "dayun_pillar": "甲申", "liunian_pillar": "丙午"}
    async with Client(cached_mcp_app(families="bazi")) as client:
        response = await call_calculation(
            client,
            spec.tool_name,
            {
                **inputs,
                "fields": [
                    *suggested_fields(spec),
                ],
                "strict_fields": True,
                "include_snapshot_text": False,
            },
        )
    assert not response.is_error
    career = response.structured_content["career_analysis"]
    assert career["evidence_chain"]["topic"]["first_view"]["natal_stars"]
    assert career["timing_context"]["source"] == "explicit_pillar_overrides"
    assert "analysis_date" not in career["timing_context"]
    assert "dayun_age" not in career["timing_context"]


def test_timing_first_view_keeps_current_basis_without_year_grids(
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec = next(s for s in CATALOG if s.key == "timing_analysis")
    code, result, _ = invoke(
        capsys,
        *shlex.split(cli._cli_example(spec, example_input(spec)))[1:],
        "--fields",
        *suggested_fields(spec),
        "--strict-fields",
        "--as-of",
        "2026-10-12T04:00:00Z",
        "--response-char-limit",
        "8192",
    )
    assert code == 0
    calendar = result["analysis_calendar"]
    assert set(calendar) == {"analysis_date_context"}
    context = calendar["analysis_date_context"]
    assert context["timezone"] == "Asia/Shanghai"
    assert context["current_solar_term"] and context["next_solar_term"]
    assert context["bazi_month_boundary"]
    assert result["dayun_analysis"] and result["liunian_analysis"]
    assert len(json.dumps(result, ensure_ascii=False).encode()) < 10000
