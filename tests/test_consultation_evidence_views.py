"""Task-level evidence: published views must retain the method users requested."""

import hashlib
import json
import shlex

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from fatebridge import cli
from fatebridge.api import app
from fatebridge.application.description import describe_input_spec, describe_spec
from fatebridge.application.examples import (
    call_guidance,
    evidence_views,
    example_input,
    suggested_fields,
)
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG


def spec_for(key):
    return next(s for s in CATALOG if s.key == key)


@pytest.mark.asyncio
async def test_published_knowledge_query_can_resolve_an_actual_aspect_source():
    guidance = call_guidance(spec_for("knowledge_read"))
    registry = call_guidance(spec_for("knowledge_registry"))
    async with Client(create_mcp_app(scenarios="onda-xingpan")) as client:
        catalog = await original_payload(
            client,
            await client.call_tool(
                "knowledge_registry",
                {
                    "domain": "astro",
                    "fields": registry["output_fields"],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            ),
        )
        assert any(
            category["name"] == "aspect"
            for domain in catalog["domains"]
            for category in domain["categories"]
        )
        payload = await original_payload(
            client,
            await client.call_tool(
                "knowledge_read",
                {
                    **guidance["astro_aspect_query"],
                    "fields": ["title", "lines", "source", "citation"],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            ),
        )
        assert payload["lines"] and payload["source"]
        assert "astro/aspect/90" in payload["citation"]


async def original_payload(client, result):
    """Read the original run's pages, never calculate again to fill missing data."""
    assert not result.is_error, result
    payload = result.structured_content
    if "result_delivery" not in payload:
        return payload
    delivery = payload["result_delivery"]
    uri = delivery["first_page_uri"]
    fragments = []
    while uri:
        page = json.loads((await client.read_resource(uri))[0].text)
        assert page["result_id"] == delivery["result_id"]
        fragments.append(page["text"])
        uri = page["next_uri"]
    serialized = "".join(fragments)
    assert hashlib.sha256(serialized.encode()).hexdigest() == delivery["sha256"]
    restored = json.loads(serialized)
    assert restored["run_metadata"]["run_id"] == payload["run_metadata"]["run_id"]
    return restored


async def call_view(client, key, view=None, **overrides):
    spec = spec_for(key)
    return await client.call_tool(
        spec.tool_name,
        {
            **example_input(spec),
            "as_of": "2026-10-20T12:00:00+08:00",
            "fields": suggested_fields(spec, view=view),
            "strict_fields": True,
            "include_snapshot_text": False,
            **overrides,
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode", ["compare", "composite", "influence", "timespace", "marks"]
)
async def test_named_relationship_mode_keeps_its_primary_evidence(mode):
    spec = spec_for("astro_relative_chart")
    card = evidence_views(spec)[mode]
    # Exercise actual engine aliases, including the unintuitive Synastry mapping.
    alias = {
        "compare": "Comp",
        "composite": "Composite",
        "influence": "Synastry",
        "timespace": "TimeSpace",
        "marks": "Marks",
    }[mode]
    assert alias in card["aliases"]
    async with Client(create_mcp_app()) as client:
        for view in [mode, None]:
            result = await call_view(client, spec.key, view, relative_mode=alias)
            payload = await original_payload(client, result)
            assert payload["relationship_profile"]["relative_mode_normalized"] == mode
            assert (
                payload["relationship_profile"]["primary_layer"]
                == card["primary_layer"]
            )
            if mode == "compare":
                assert payload["synastry_aspects"]
                assert payload["in_to_out_aspects"] and payload["out_to_in_aspects"]
            elif mode == "influence":
                for side in ["inner", "outer"]:
                    assert payload[side]["chart_profile"]["reference_frame"]
                    assert len(payload[side]["chart"]["planets"]) >= 10
                    assert len(payload[side]["chart"]["houses"]) == 12
            else:
                assert len(payload["chart"]["planets"]) >= 10
                assert payload["chart"]["angles"] and payload["chart"]["aspects"]
            # Mode-specific views avoid unrelated computed chart branches.
            if view is not None:
                assert "inner_chart" not in payload and "outer_chart" not in payload
                assert "in_to_out_midpoint" not in payload


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["qimen", "sixyao"])
async def test_divination_views_keep_palaces_and_line_cast_facts(key):
    async with Client(create_mcp_app()) as client:
        payload = await original_payload(client, await call_view(client, key))
    if key == "qimen":
        assert len(payload["qimen"]["palaces"]) == 9
        assert payload["qimen"]["zhifu"] and payload["qimen"]["zhishi"]
        assert payload["four_pillars"]["day"]
    else:
        assert len(payload["lines"]) == 6
        assert {"branch", "element", "liuqin", "liushen", "shi_ying"} <= payload[
            "lines"
        ][0].keys()
        assert any(line["shi_ying"] == "世" for line in payload["lines"])
        assert any(line["shi_ying"] == "应" for line in payload["lines"])
        assert payload["hexagram_info"]["shi_line"]
        assert payload["nongli"]


@pytest.mark.asyncio
@pytest.mark.parametrize("view", [None, "stage", "annual", "short_term"])
async def test_western_timing_views_preserve_time_bounds_and_relevant_positions(view):
    async with Client(create_mcp_app()) as client:
        payload = await original_payload(
            client, await call_view(client, "western_timing_analysis", view)
        )
    if view in [None, "stage", "annual"]:
        firdaria = payload["time_lords"]["firdaria"]
        for name in ["current_major", "current_sub"]:
            assert firdaria[name]["start"] < firdaria[name]["end"]
    if view in [None, "annual"]:
        assert payload["returns"]["solar_return"]["sun"]["house"]
        assert payload["returns"]["solar_return"]["ascendant"]["sign"]
    if view in [None, "short_term"]:
        transit = payload["transits"]["current_transit"]
        assert isinstance(transit["hits"], list) and transit["hits"]
        assert all("orb" in hit for hit in transit["hits"])
    if view == "stage":
        assert "transits" not in payload and "directions" not in payload
    if view == "annual":
        assert (
            payload["directions"]["given_year"]["year_start"]
            < payload["directions"]["given_year"]["year_end"]
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dimension",
    ["marriage", "romance", "education", "personality", "relatives", "children"],
)
async def test_bazi_topic_starter_preserves_structure_and_its_own_timing(dimension):
    async with Client(create_mcp_app()) as client:
        payload = await original_payload(
            client, await call_view(client, "bazi_" + dimension)
        )
    analysis = payload[dimension + "_analysis"]
    assert len(analysis) >= 5
    assert analysis["timing_context"]["analysis_date"] == "2026-10-20"
    structure = {
        "marriage": "spouse_palace",
        "romance": "peach_blossom",
        "education": "study_stars",
        "personality": "dominant_traits",
        "relatives": "palaces",
        "children": "child_palace",
    }[dimension]
    assert analysis[structure]


@pytest.mark.asyncio
@pytest.mark.parametrize("view", ["classical_detail", "fixed_stars", "planetary_hours"])
async def test_natal_deep_views_read_real_branches_without_other_details(view):
    async with Client(create_mcp_app()) as client:
        payload = await original_payload(
            client, await call_view(client, "astro_chart", view)
        )
    assert payload["person_info"] and payload["chart_profile"]
    if view == "classical_detail":
        classical = payload["classical"]
        for name in [
            "sect",
            "planets",
            "dispositors",
            "topic_almutens",
            "lots",
            "syzygy",
            "almuten_figuris",
        ]:
            assert classical[name]
        assert "fixed_stars" not in payload and "planetary_hours" not in payload
    elif view == "fixed_stars":
        assert isinstance(payload["fixed_stars"], list)
        assert payload["planets"] and payload["angles"]
        assert "classical" not in payload
    else:
        assert payload["planetary_hours"]
        assert "planets" not in payload and "fixed_stars" not in payload


@pytest.mark.asyncio
async def test_views_are_published_in_all_descriptions_and_aliases_are_not_guessed():
    async with Client(create_mcp_app()) as client:
        tools = {t.name: t for t in await client.list_tools()}
    for key in [
        "astro_relative_chart",
        "astro_chart",
        "qimen",
        "sixyao",
        "western_timing_analysis",
    ]:
        spec = spec_for(key)
        views = evidence_views(spec)
        assert describe_spec(spec)["evidence_views"] == views
        assert describe_input_spec(spec)["evidence_views"] == views
        assert (
            json.dumps(views, ensure_ascii=False) in tools[spec.tool_name].description
        )
    assert evidence_views(spec_for("astro_relative")) == evidence_views(
        spec_for("astro_relative_chart")
    )
    with pytest.raises(ValueError, match="Unknown evidence view"):
        suggested_fields(spec_for("qimen"), view="invented")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "key,view", [("qimen", "directional"), ("western_timing_analysis", "short_term")]
)
async def test_task_evidence_agrees_across_rest_mcp_and_cli(key, view, capsys):
    spec = spec_for(key)
    fields = suggested_fields(spec, view=view)
    as_of = "2026-10-20T12:00:00+08:00"
    async with Client(create_mcp_app()) as client:
        result = await call_view(client, key, view, response_char_limit=0)
        mcp = await original_payload(client, result)
    query = [("fields", f) for f in fields] + [
        ("as_of", as_of),
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", "0"),
    ]
    with TestClient(app) as client:
        response = client.post(spec.rest_path, json=example_input(spec), params=query)
    assert response.status_code == 200, response.text
    command = shlex.split(cli._cli_example(spec, example_input(spec)))[1:]
    code = cli.run(
        command
        + [
            "--as-of",
            as_of,
            "--fields",
            *fields,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert code == 0, output

    def business(p):
        return {k: v for k, v in p.items() if k != "run_metadata"}

    assert business(mcp) == business(response.json()) == business(output)


@pytest.mark.asyncio
async def test_full_export_keeps_full_original_run_despite_new_task_views():
    async with Client(create_mcp_app()) as client:
        result = await call_view(
            client, "astro_relative_chart", relative_mode="Composite", fields=None
        )
        assert "result_delivery" in result.structured_content
        payload = await original_payload(client, result)
    assert payload["chart"]["planets"]
    assert payload["inner_chart"]["planets"]
    assert payload["in_to_out_midpoint"]
    assert payload["snapshot_export"]["technique"]["key"] == "relative"
