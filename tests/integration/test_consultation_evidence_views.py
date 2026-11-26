"""Task-level evidence: published views must retain the method users requested."""

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
from tests.support.transports import call_calculation


def spec_for(name):
    return next(s for s in CATALOG if s.name == name)


@pytest.mark.asyncio
async def test_published_knowledge_query_can_resolve_an_actual_aspect_source() -> None:
    guidance = call_guidance(spec_for("knowledge_read"))
    registry = call_guidance(spec_for("knowledge_catalog"))
    async with Client(create_mcp_app()) as client:
        catalog = await original_payload(
            client,
            await call_calculation(
                client,
                "knowledge_catalog",
                {
                    "domain": "astro",
                    "fields": registry["output_fields"],
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
            await call_calculation(
                client,
                "knowledge_read",
                {
                    **guidance["astro_aspect_query"],
                    "fields": [
                        "title",
                        "lines",
                        "source",
                        "citation",
                        "provenance.reference_only",
                    ],
                },
            ),
        )
        assert "相位角：90°" in payload["lines"]
        assert payload["source"] == "fatebridge_rule_references"
        assert "Tetrabiblos I.13" in payload["citation"]
        assert payload["provenance"]["reference_only"] is True


async def original_payload(client, result):
    assert not result.is_error, result
    return result.structured_content


async def call_view(client, name, view=None, **overrides):
    spec = spec_for(name)
    return await call_calculation(
        client,
        spec.name,
        {
            **example_input(spec),
            "as_of": "2026-10-20T12:00:00+08:00",
            "fields": suggested_fields(spec, view=view),
            **overrides,
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode", ["compare", "composite", "influence", "timespace", "marks"]
)
async def test_named_relationship_mode_keeps_its_primary_evidence(mode: str) -> None:
    spec = spec_for("relationship_chart")
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
            result = await call_view(client, spec.name, view, relative_mode=alias)
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
            elif mode == "marks":
                assert set(payload["marks_charts"]) == {"inner", "outer"}
                assert payload["relationship_profile"]["primary_chart_role"] == "inner"
                for side in ["inner", "outer"]:
                    personal = payload["marks_charts"][side]
                    assert personal["chart_profile"]["chart_type"] == "marks"
                    assert len(personal["planets"]) >= 10
                    assert len(personal["houses"]) == 12
                    assert personal["angles"] and personal["aspects"]
                assert (
                    payload["marks_charts"]["inner"]["planets"]
                    != payload["marks_charts"]["outer"]["planets"]
                )
                if view is not None:
                    assert "chart" not in payload
                else:
                    pass
            else:
                assert len(payload["chart"]["planets"]) >= 10
                assert payload["chart"]["angles"] and payload["chart"]["aspects"]
            # Mode-specific views avoid unrelated computed chart branches.
            if view is not None:
                assert "inner_chart" not in payload and "outer_chart" not in payload
                assert "in_to_out_midpoint" not in payload
            else:
                pass


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["qimen", "liuyao"])
async def test_divination_views_keep_palaces_and_line_cast_facts(name: str) -> None:
    async with Client(create_mcp_app()) as client:
        payload = await original_payload(client, await call_view(client, name))
    if name == "qimen":
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
async def test_western_timing_views_preserve_time_bounds_and_relevant_positions(
    view: str | None,
) -> None:
    async with Client(create_mcp_app()) as client:
        payload = await original_payload(
            client, await call_view(client, "western_timing", view)
        )
    if view in [None, "stage", "annual"]:
        firdaria = payload["time_lords"]["firdaria"]
        for name in ["current_major", "current_sub"]:
            assert firdaria[name]["start"] < firdaria[name]["end"]
    else:
        pass
    if view in [None, "annual"]:
        assert payload["returns"]["solar_return"]["sun"]["house"]
        assert payload["returns"]["solar_return"]["ascendant"]["sign"]
    else:
        pass
    if view in [None, "short_term"]:
        transit = payload["transits"]["current_transit"]
        assert isinstance(transit["hits"], list) and transit["hits"]
        assert all("orb" in hit for hit in transit["hits"])
    else:
        pass
    if view == "stage":
        assert "transits" not in payload and "directions" not in payload
    else:
        pass
    if view == "annual":
        assert (
            payload["directions"]["given_year"]["year_start"]
            < payload["directions"]["given_year"]["year_end"]
        )
    else:
        pass


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dimension,ten_god,visible_in,hidden_in,dayun_palace_hits",
    [
        ("marriage", "正财", [], ["day(辰)"], 0),
        ("romance", "正财", [], ["day(辰)"], 0),
        ("education", "正印", [], ["year(午)"], 3),
        ("personality", "比肩", ["year"], ["month(巳)", "hour(巳)"], 0),
        ("relatives", "正印", [], ["year(午)"], 3),
        ("children", "正官", [], ["year(午)"], 3),
    ],
)
async def test_bazi_topic_starter_preserves_structure_and_its_own_timing(
    dimension: str, ten_god: str, visible_in, hidden_in, dayun_palace_hits: int
) -> None:
    async with Client(create_mcp_app()) as client:
        payload = await original_payload(
            client, await call_view(client, "bazi_" + dimension)
        )
    analysis = payload[dimension + "_analysis"]
    assert analysis["timing_context"]["analysis_date"] == "2026-10-20"
    facts = analysis["topic_facts"]
    assert facts["natal_stars"][0] == {
        "ten_god": ten_god,
        "visible_in": visible_in,
        "hidden_in": hidden_in,
    }
    assert [(layer["layer"], layer["pillar"]) for layer in facts["timing_layers"]] == [
        ("dayun", "甲申"),
        ("liunian", "丙午"),
    ]
    assert len(facts["timing_layers"][0]["palace_hits"]) == dayun_palace_hits


@pytest.mark.asyncio
@pytest.mark.parametrize("view", ["classical_detail", "fixed_stars", "planetary_hours"])
async def test_natal_deep_views_read_real_branches_without_other_details(
    view: str,
) -> None:
    async with Client(create_mcp_app()) as client:
        payload = await original_payload(
            client, await call_view(client, "astrology_chart", view)
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
async def test_views_are_discoverable_on_demand_and_aliases_are_not_guessed() -> None:
    async with Client(create_mcp_app()) as client:
        tools = await client.list_tools()
        for name in [
            "relationship_chart",
            "astrology_chart",
            "qimen",
            "liuyao",
            "western_timing",
        ]:
            spec = spec_for(name)
            views = evidence_views(spec)
            assert all(
                json.dumps(views, ensure_ascii=False) not in (tool.description or "")
                for tool in tools
            )
            discovered = await client.call_tool(
                "discover_tools", {"tool": spec.name, "detail": "summary"}
            )
            assert discovered.structured_content["tools"][0]["evidence_views"] == (
                json.loads(json.dumps(views))
            )
            assert describe_spec(spec)["evidence_views"] == views
            assert describe_input_spec(spec)["evidence_views"] == views
    with pytest.raises(ValueError, match="Unknown evidence view"):
        suggested_fields(spec_for("qimen"), view="invented")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,view", [("qimen", "directional"), ("western_timing", "short_term")]
)
async def test_task_evidence_agrees_across_rest_mcp_and_cli(
    name: str, view: str, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = spec_for(name)
    fields = suggested_fields(spec, view=view)
    as_of = "2026-10-20T12:00:00+08:00"
    async with Client(create_mcp_app()) as client:
        result = await call_view(client, name, view)
        mcp = await original_payload(client, result)
    query = [("fields", f) for f in fields] + [
        ("as_of", as_of),
        ("detail", "audit"),
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
            "--detail",
            "audit",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert code == 0, output

    def business(p):
        return {k: v for k, v in p.items() if k != "run_metadata"}

    assert business(mcp) == business(response.json()) == business(output)


@pytest.mark.asyncio
async def test_audit_detail_keeps_full_result_despite_compact_views() -> None:
    async with Client(create_mcp_app()) as client:
        result = await call_view(
            client,
            "relationship_chart",
            relative_mode="Composite",
            fields=None,
            detail="audit",
        )
        assert "result_delivery" not in result.structured_content
        payload = await original_payload(client, result)
    assert payload["chart"]["planets"]
    assert payload["inner_chart"]["planets"]
    assert payload["in_to_out_midpoint"]
