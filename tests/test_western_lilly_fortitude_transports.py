"""All three real protocols expose literal table facts and incomplete acceptance."""

import asyncio

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import evidence_views
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_western_horary import QUESTION


@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
@pytest.mark.parametrize("published_card", [True, False])
def test_literal_table_summary_and_leaf_projection_match_all_protocols(
    zodiac, published_card, rest, tmp_path, capsys
):
    spec = SPECS["astro_horary"]
    payload = {**QUESTION, "category": "career", "zodiac_type": zodiac}
    fields = (
        evidence_views(spec)["lilly_fortitudes"]["fields"]
        if published_card
        else [
            "horary.fortitudes.planets.Sun.rows",
            "horary.fortitudes.physical_inputs.motion.Mercury.daily_motion_exact_degrees",
            "horary.fortitudes.full_original_text_acceptance",
            "horary.verdict",
        ]
    )
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", p) for p in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", 0),
        ],
    )
    code, cli = call_cli(
        spec,
        payload,
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
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert response.status_code == 200, response.text
    assert code == 0 and not protocol.is_error
    values = [response.json(), cli, protocol.structured_content]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for result in values:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        assert not result.get("projection_warnings")
        h = result["horary"]
        f = h["fortitudes"]
        assert (
            h["verdict"] == "uncertain" and f["full_original_text_acceptance"] is False
        )
        if published_card:
            assert f["physical_inputs"]["status"] == "computed"
            assert len(f["summary"]) == 7
            assert all(p["row_count"] == 41 for p in f["summary"].values())
            assert ("modern_extension" in f["source_method_scope"]) is (
                zodiac == "Sidereal"
            )
        else:
            assert len(f["planets"]["Sun"]["rows"]) == 41
            direct = next(r for r in f["planets"]["Sun"]["rows"] if r["code"] == "F06")
            assert direct["status"] == "not_applicable" and direct["contribution"] == 0
