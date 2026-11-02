"""Actual protocols share night Fortune, source assignment and all28 printed rows."""

import asyncio
from fractions import Fraction

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import evidence_views
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_western_horary import QUESTION


@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
@pytest.mark.parametrize("card", [True, False])
def test_fortune_night_formula_cusp_assignment_and_row_projection_across_protocols(
    zodiac, card, rest, tmp_path, capsys
):
    spec = SPECS["astro_horary"]
    payload = {
        **QUESTION,
        "question_hour": 2,
        "category": "wealth",
        "zodiac_type": zodiac,
        "house_system": "whole_sign",
    }
    fields = (
        evidence_views(spec)["lilly_fortune"]["fields"]
        if card
        else [
            "horary.ascendant.longitude",
            "horary.planets.Sun.longitude",
            "horary.planets.Moon.longitude",
            "horary.fortune.exact_longitude",
            "horary.fortune.rows",
            "horary.fortune.full_original_text_acceptance",
            "horary.planets.Saturn.house_assignment",
            "horary.fortitudes.planets.Saturn.rows",
            "horary.verdict",
        ]
    )
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
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
    results = [response.json(), cli, protocol.structured_content]
    assert business(results[0]) == business(results[1]) == business(results[2])
    for value in results:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(value)
        assert not value.get("projection_warnings")
        h = value["horary"]
        f = h["fortune"]
        assert (
            h["verdict"] == "uncertain" and f["full_original_text_acceptance"] is False
        )
        if card:
            formula = f["formula"]
            assert formula["reverses_at_night"] is False
            expected = (
                Fraction(formula["ascendant"])
                + Fraction(formula["moon"])
                - Fraction(formula["sun"])
            ) % 360
            assert abs(float(expected) - f["longitude"]) < 1e-12
            assert f["house_assignment"]["status"] == "computed_under_declared_policy"
        else:
            assert len(f["rows"]) == 28
            assert (
                Fraction(f["exact_longitude"])
                == (
                    Fraction(h["ascendant"]["longitude"])
                    + Fraction(h["planets"]["Moon"]["longitude"])
                    - Fraction(h["planets"]["Sun"]["longitude"])
                )
                % 360
            )
            scored = h["planets"]["Saturn"]["house_assignment"]["assigned_house"]
            row = next(
                r
                for r in h["fortitudes"]["planets"]["Saturn"]["rows"]
                if r["code"] == "F01"
            )
            assert row["inputs"]["scored_house"] == scored
