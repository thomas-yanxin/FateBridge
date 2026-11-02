"""Actual local REST/MCP/CLI transport, not resident-server or model acceptance."""

import asyncio

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import evidence_views
from fatebridge.core.lilly_rays import (
    describe_sign_relationship,
    directed_sign_relationship,
)
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native
from tests.test_agentic_nested_outputs import rest as transport_rest
from tests.test_western_horary import QUESTION

rest = transport_rest


@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
@pytest.mark.parametrize("category", ["general", "career"])
def test_source_directed_sign_witness_across_actual_protocols(
    project, zodiac, category, rest, tmp_path, capsys
):
    spec = SPECS["astro_horary"]
    inputs = {**QUESTION, "category": category, "zodiac_type": zodiac}
    fields = evidence_views(spec)["lilly_sign_rays"]["fields"]
    params = [("response_char_limit", 0)]
    flags = ["--response-char-limit", "0"]
    kwargs = {}
    if project:
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        kwargs = {
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        }
    http = rest.post(spec.rest_path, json=inputs, params=params)
    code, cli = call_cli(spec, inputs, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(native(spec, inputs, **kwargs))
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    values = [http.json(), cli, protocol.structured_content]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for output in values:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        assert not output.get("projection_warnings")
        h = output["horary"]
        receipt = h["significators"]["directed_sign_relationship"]
        a, b = h["significators"]["querent"], h["significators"]["quesited"]
        expected = directed_sign_relationship(
            a["planet"],
            a["longitude"],
            b["planet"],
            b["longitude"],
            selected_degree_aspect=receipt["selected_degree_aspect"],
            zodiac_type=zodiac,
        )
        assert receipt == expected
        assert (
            describe_sign_relationship(receipt, a["planet_label"], b["planet_label"])
            in h["reasoning"]
        )
        assert receipt["distinct_bodies"] is (
            category == "career" and zodiac == "Tropic"
        )
        assert receipt["coordinate_scope"] == (
            "tropical_selected_edition"
            if zodiac == "Tropic"
            else "sidereal_extension_not_original_edition_acceptance"
        )
        assert h["rule_profile"]["sign_relationship_policy"] == receipt["method_id"]
        assert (
            108 in h["rule_profile"]["chapter_pages"]
            and 109 in h["rule_profile"]["chapter_pages"]
        )
        assert (
            receipt["quantitative_bonus_added"]
            is receipt["full_original_text_acceptance"]
            is False
        )
        assert h["verdict"] == "uncertain"
        if project:
            assert "snapshot_text" not in output
        else:
            assert h["reasoning"] in output["snapshot_text"]
