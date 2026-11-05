import asyncio

import pytest

from fatebridge.core.astro.relationship import relationship_focus_block
from fatebridge.services.astrology import calculate_relative_chart_analysis
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.fixtures.surface_payloads import astro_payload
from tests.support.relationship_inputs import payloads


def test_relationship_focus_block_romance_filters_to_significators():
    aspects = [
        {"inner": "Venus", "outer": "Mars", "aspect": "Trine", "orb": 1.0},
        {"inner": "Mercury", "outer": "Saturn", "aspect": "Square", "orb": 2.0},
        {"inner": "Moon", "outer": "Jupiter", "aspect": "Sextile", "orb": 3.0},
    ]
    block = relationship_focus_block("romance", aspects)
    assert block["focus"] == "romance"
    assert block["emphasis_houses"] == [5]
    kept = {(a["inner"], a["outer"]) for a in block["focused_synastry_aspects"]}
    assert ("Venus", "Mars") in kept  # both significators
    assert ("Moon", "Jupiter") in kept  # Moon is a significator
    assert ("Mercury", "Saturn") not in kept  # neither is a romance significator
    assert block["focused_aspect_count"] == 2


def test_relationship_focus_block_marriage_houses_and_bodies():
    block = relationship_focus_block("婚姻", [])
    assert block["focus"] == "marriage"
    assert block["emphasis_houses"] == [7]
    assert "Saturn" in block["emphasis_bodies"]


def test_relationship_focus_block_general_does_not_filter():
    block = relationship_focus_block(
        None, [{"inner": "Venus", "outer": "Mars", "aspect": "Trine", "orb": 1.0}]
    )
    assert block["focus"] == "general"
    assert block["emphasis_houses"] == []
    assert block["focused_synastry_aspects"] == []


def test_relative_chart_attaches_focus_block_subset_of_synastry():
    result = calculate_relative_chart_analysis(
        inner_payload=astro_payload(
            name="甲",
            birth_longitude=121.4667,
            birth_latitude=31.2167,
            birth_place="上海",
        ),
        outer_payload=astro_payload(
            name="乙",
            birth_longitude=116.4074,
            birth_latitude=39.9042,
            birth_place="北京",
        ),
        relative_mode="Composite",
        relationship_focus="romance",
        hsys=0,
        zodiacal=0,
    )

    focus = result["relationship_profile"]["focus"]
    assert focus["focus"] == "romance"
    assert focus["emphasis_houses"] == [5]
    # 过滤子集必须是完整 synastry 相位的子集。
    assert focus["focused_aspect_count"] <= len(result["synastry_aspects"])
    significators = set(focus["emphasis_bodies"])
    for aspect in focus["focused_synastry_aspects"]:
        assert aspect["inner"] in significators or aspect["outer"] in significators


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, "general"),
        ("", "general"),
        ("   ", "general"),
        ("general", "general"),
        ("泛", "general"),
        ("none", "general"),
        ("marriage", "marriage"),
        ("marry", "marriage"),
        ("婚姻", "marriage"),
        ("结婚", "marriage"),
        ("romance", "romance"),
        ("romantic", "romance"),
        ("dating", "romance"),
        ("love", "romance"),
        ("恋爱", "romance"),
        ("戀愛", "romance"),
    ],
)
def test_all_existing_focus_aliases_and_unspecified_values_are_retained(
    value, expected
):
    assert relationship_focus_block(value, [])["focus"] == expected
    if value is not None:
        assert relationship_focus_block(f" {value.upper()} ", [])["focus"] == expected


@pytest.mark.parametrize("value", ["romnace", "career", "unknown"])
def test_unknown_nonempty_focus_does_not_acquire_an_unspecified_general_result(value):
    with pytest.raises(ValueError, match="relationship_focus"):
        relationship_focus_block(value, [])


def test_unknown_focus_is_rejected_on_both_request_shapes_and_all_public_transports(
    rest, tmp_path, capsys
):
    from fatebridge.application.execution import execute_tool

    nested, flat = payloads("Comp", "uncorrected")
    nested["relationship_focus"] = flat["relationship_focus"] = "romnace"
    for key, inputs in (("astro_relative", nested), ("astro_relative_chart", flat)):
        spec = SPECS[key]
        result = execute_tool(spec, spec.request_model.model_validate(inputs))
        assert "relationship_focus" in result["error"]
        assert "relationship_profile" not in result
    response = rest.post("/api/astro/relative", json=nested)
    code, cli = call_cli(SPECS["astro_relative_chart"], flat, tmp_path, capsys)
    mcp = asyncio.run(native(SPECS["astro_relative_chart"], flat))
    assert response.status_code == 400 and code != 0 and mcp.is_error
    assert "relationship_focus" in response.json()["error"]
    assert "relationship_focus" in cli["error"]


@pytest.mark.parametrize(
    "value,expected", [(" MARRY ", "marriage"), ("戀愛", "romance"), ("   ", "general")]
)
def test_valid_focus_aliases_reach_all_public_transports(
    rest, tmp_path, capsys, value, expected
):
    nested, flat = payloads("Comp", "uncorrected")
    nested["relationship_focus"] = flat["relationship_focus"] = value
    fields = ["relationship_profile.focus"]
    response = rest.post(
        "/api/astro/relative",
        json=nested,
        params=[
            ("fields", fields[0]),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ],
    )
    code, cli = call_cli(
        SPECS["astro_relative_chart"],
        flat,
        tmp_path,
        capsys,
        flags=["--fields", *fields],
    )
    mcp = asyncio.run(
        native(
            SPECS["astro_relative_chart"],
            flat,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    assert outputs[0]["relationship_profile"]["focus"]["focus"] == expected
