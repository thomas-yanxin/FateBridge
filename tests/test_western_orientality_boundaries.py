"""Independent supplied-angle references and faithful consumer propagation."""

import asyncio
import json
import math
from fractions import Fraction
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import fatebridge.core.classical_western as classical
import fatebridge.core.output_charts as contracts
from fatebridge.core.astrology_tables import SIGNS
from fatebridge.core.ptolemy import build_ptolemy_layer
from tests.reference_data import verify_source_files
from tests.test_agentic_nested_outputs import rest  # noqa: F401
from tests.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
)

FIXTURE = Path(__file__).parent / "data/astro/orientality"
ANGLES = json.loads((FIXTURE / "independent-angle-reference.json").read_text())["cases"]
NATIVE = json.loads((FIXTURE / "native-phase-reference.json").read_text())["rows"]
PUBLIC = [
    row
    for row in json.loads((FIXTURE / "public-input-plan.json").read_text())["rows"]
    if row["cohort"] == "all7conjunctions_fixed_clock_neighbours"
]


def decode(value):
    return (
        float.fromhex(value["hex"])
        if value["kind"] == "float"
        else Fraction(value["value"])
    )


def test_independent_preedit_reference_seal_and_rejected_input_attempt_are_retained():
    verify_source_files(FIXTURE)
    assert len(PUBLIC) == 42


@pytest.mark.parametrize("row", ANGLES, ids=lambda row: row["id"])
def test_literal_neighbours_keep_their_preedit_independent_phase(row):
    assert (
        classical.orientality(decode(row["planet"]), decode(row["sun"]))
        == row["expected"]
    )


@pytest.mark.parametrize("row", NATIVE)
def test_native_coordinates_propagate_phase_to_mercury_sect_without_new_astrometry(row):
    longitude, sun, phase = row["mercury"], row["sun"], row["expected"]
    assert classical.orientality(longitude, sun) == phase
    own = None if phase is None else "day" if phase == "oriental" else "night"
    layer = build_ptolemy_layer(
        {"Sun": sun, "Mercury": longitude}, "day", tropical=True
    )
    assert layer["planets"]["Mercury"]["natural_sect"] == own
    for sect in ["day", "night"]:
        item = classical.build_planet_classical(
            planet="Mercury",
            sign=SIGNS[int(longitude // 30)],
            degree_in_sign=longitude % 30,
            longitude=longitude,
            house=1,
            sun_longitude=sun,
            chart_sect=sect,
            altitude=10,
        )
        assert item["orientality"] == phase
        assert item["sect_placement"] == (
            None if own is None else "of_sect" if sect == own else "contrary_to_sect"
        )
        assert item["in_halb"] is (None if own is None else sect == own)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("slot", ["sun", "planet"])
def test_nonfinite_coordinates_never_become_an_occidental_result(value, slot):
    with pytest.raises(ValueError):
        classical.orientality(
            value if slot == "planet" else 1, value if slot == "sun" else 1
        )


def test_missing_sun_and_exact_coincidence_keep_unknown_semantics():
    assert classical.orientality(1, None) is None
    assert classical.orientality(1, 1) is None
    assert classical.orientality(361, 1) is None
    assert classical.orientality(181, 1) == "oriental"  # Retained legacy tie.


@pytest.mark.parametrize(
    "field",
    [
        "physical_rise_set_verified",
        "heliacal_visibility_verified",
        "author_transition_endpoints_certified",
    ],
)
def test_policy_cannot_claim_unperformed_observation_or_author_endpoint_acceptance(
    field,
):
    model = getattr(contracts, "OrientalityPolicy", None)
    assert model is not None
    policy = classical.orientality_policy()
    assert policy["nonzero_deadband"] == "none" and policy[field] is False
    model.model_validate(policy)
    with pytest.raises(ValueError):
        model.model_validate({**policy, field: True})


@pytest.mark.parametrize("row", PUBLIC, ids=lambda row: row["id"])
def test_all_frozen_event_inputs_across_public_rest_mcp_and_cli(
    row,
    rest,  # noqa: F811 - pytest fixture dependency
    tmp_path,
    capsys,  # noqa: F811 - pytest fixture dependency
):
    spec = SPECS[row["key"]]
    prefix = "base_chart." if row["key"] == "astro_germany" else ""
    fields = [prefix + key for key in ["person_info", "planets", "classical"]]
    query = [("fields", name) for name in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", 0),
        ("as_of", "2000-12-31T12:00:00+00:00"),
    ]
    response = rest.post(spec.rest_path, json=row["inputs"], params=query)
    code, cli = call_cli(
        spec,
        row["inputs"],
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
            "--as-of",
            "2000-12-31T12:00:00+00:00",
        ],
    )
    protocol = asyncio.run(
        native(
            spec,
            row["inputs"],
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
            response_char_limit=0,
            as_of="2000-12-31T12:00:00+00:00",
        )
    )
    values = [response.json(), cli, protocol.structured_content]
    for surface, value in zip(["rest", "cli", "mcp"], values):
        (tmp_path / f"{surface}-observed.json").write_text(json.dumps(value))
    (tmp_path / "invocation-status.json").write_text(
        json.dumps(
            {
                "case": row,
                "fields": fields,
                "rest_status": response.status_code,
                "cli_exit": code,
                "mcp_is_error": protocol.is_error,
            }
        )
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert business(values[0]) == business(values[1]) == business(values[2])
    for surface, value in zip(["rest", "cli", "mcp"], values):
        Draft202012Validator(spec.output_model.model_json_schema()).validate(value)
        chart = value["base_chart"] if prefix else value
        planets = {planet["id"]: planet for planet in chart["planets"]}
        reference = independent_delivered_phase(
            planets["Mercury"]["longitude"], planets["Sun"]["longitude"]
        )
        actual = chart["classical"]["planets"]["Mercury"]
        assert actual["orientality"] == reference
        assert chart["classical"]["orientality_policy"]["nonzero_deadband"] == "none"
        expected_sect = (
            None if reference is None else "day" if reference == "oriental" else "night"
        )
        assert (
            chart["classical"]["ptolemy"]["planets"]["Mercury"]["natural_sect"]
            == expected_sect
        )


def independent_delivered_phase(planet, sun):
    # Separate Decimal implementation, not an import/copy of the producer's
    # Fraction or legacy signed-delta helper. It certifies only these inputs.
    from decimal import ROUND_FLOOR, Decimal, localcontext

    with localcontext() as context:
        context.prec = 1200
        difference = Decimal.from_float(planet) - Decimal.from_float(sun)
        turns = (difference / Decimal(360)).to_integral_value(rounding=ROUND_FLOOR)
        remainder = difference - Decimal(360) * turns
        return (
            None if remainder == 0 else "occidental" if remainder < 180 else "oriental"
        )
