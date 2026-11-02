"""Real local protocol paths preserve source facts, directions and open gates."""

import asyncio

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import evidence_views
from tests.fixtures.surface_payloads import REST_POST_CASES
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_western_horary import QUESTION


@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
@pytest.mark.parametrize("category", ["marriage", "career"])
def test_lilly_source_receipts_across_rest_native_mcp_and_cli(
    project, zodiac, category, rest, tmp_path, capsys
):
    spec = SPECS["astro_horary"]
    inputs = {**QUESTION, "category": category, "zodiac_type": zodiac}
    card = evidence_views(spec)["lilly_reception_conditions"]
    params = [("response_char_limit", 0)]
    flags = ["--response-char-limit", "0"]
    kwargs = {}
    if project:
        params += [("fields", field) for field in card["fields"]] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            *card["fields"],
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        kwargs = {
            "fields": card["fields"],
            "strict_fields": True,
            "include_snapshot_text": False,
        }
    response = rest.post(spec.rest_path, json=inputs, params=params)
    code, cli = call_cli(spec, inputs, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(native(spec, inputs, **kwargs))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    values = [response.json(), cli, protocol.structured_content]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for output in values:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        assert not output.get("projection_warnings")
        h = output["horary"]
        facts = h["perfection"]["lilly_conditions"]
        assert len(h["planets"]) == 7
        assert facts["chart_sect"] == "day"
        assert facts["coordinate_scope"] == (
            "tropical_selected_edition"
            if zodiac == "Tropic"
            else "sidereal_extension_not_original_edition_acceptance"
        )
        assert (
            facts["full_original_text_acceptance"] is False
            and h["verdict"] == "uncertain"
        )
        if category == "career" and zodiac == "Tropic":
            assert any(route["mode"] == "direct" for route in facts["routes"])
        if category == "marriage" and zodiac == "Tropic":
            assert facts["p112_mutual_reception"]["premise_satisfied"] is True
        assert (
            facts["p112_mutual_reception"]["premise_satisfied"]
            == facts["principal_reception"]["mutual"]
        )
        for row in facts["principal_reception"]["directions"]:
            assert row["receiver"] != row["guest"]
            assert row["guest_longitude"] == h["planets"][row["guest"]]["longitude"]
        if project:
            assert "snapshot_text" not in output and "heuristic_verdict" not in h
        else:
            assert (
                "本质尊贵" in output["snapshot_text"]
                and "p112_mutual_reception" in output["snapshot_text"]
            )


def test_projection_of_deep_nullable_source_condition_is_declared(rest):
    spec = SPECS["astro_horary"]
    fields = [
        "horary.planets.Moon.essential_condition.peregrine",
        "horary.perfection.lilly_conditions.principal_reception.mutual",
        "horary.perfection.lilly_conditions.p112_mutual_reception.conditional_reading_zh",
    ]
    response = rest.post(
        spec.rest_path,
        json={**QUESTION, "category": "general"},
        params=[("fields", p) for p in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", 0),
        ],
    )
    assert response.status_code == 200
    out = response.json()
    assert not out.get("projection_warnings")
    assert (
        out["horary"]["perfection"]["lilly_conditions"]["principal_reception"]["mutual"]
        is None
    )
    Draft202012Validator(spec.output_model.model_json_schema()).validate(out)


def test_election_major_dignity_scope_is_available_in_strict_view(
    rest, tmp_path, capsys
):
    spec = SPECS["astro_election"]
    inputs = REST_POST_CASES[spec.rest_path]()
    fields = ["election.dignity_scope"]
    response = rest.post(
        spec.rest_path,
        json=inputs,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", 0),
        ],
    )
    code, cli = call_cli(
        spec,
        inputs,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(
        native(
            spec, inputs, fields=fields, strict_fields=True, include_snapshot_text=False
        )
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    values = [response.json(), cli, protocol.structured_content]
    assert business(values[0]) == business(values[1]) == business(values[2])
    assert "peregrine_not_classified" in values[0]["election"]["dignity_scope"]
