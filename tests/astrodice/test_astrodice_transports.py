"""REST, native MCP, CLI and projected schema parity for actual dice faces."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.fixtures.mcp_receipt import verified_inline_business

SPEC = next(spec for spec in CATALOG if spec.key == "otherbu")
FACES = {"planet": "☊", "sign": "处女座", "house": 11}


def test_published_astronomical_view_recovers_complete_same_run_across_transports(
    rest, capsys
):
    from fatebridge.application.examples import suggested_fields

    inputs = {
        "planet": "Jupiter",
        "sign": "Aries",
        "house": 0,
        "date": "2024-03-20",
        "time": "06:30",
        "zone": "UTC",
        "gps_lat": 51.5,
        "gps_lon": 0,
    }
    fields = suggested_fields(SPEC, view="astronomical_context")
    assert "chart" in fields and "input_normalized" in fields
    response = rest.post(
        SPEC.rest_path,
        json=inputs,
        params={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
    )
    assert response.status_code == 200, response.text
    expected = response.json()
    assert expected["input_normalized"]["zone"] == "UTC"
    assert expected["chart"]["params"]["ephemerisReferencePoints"][
        "system_barycenters"
    ] == ["Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "otherbu",
                {
                    **inputs,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not result.is_error
            first = result.structured_content
            if "result_delivery" not in first:
                return first
            ref = first["result_delivery"]
            parts = []
            uri = ref["first_page_uri"]
            while uri is not None:
                page = json.loads((await client.read_resource(uri))[0].text)
                parts.append(page["text"])
                uri = page["next_uri"]
            text = "".join(parts)
            assert len(text) == ref["total_chars"]
            full = json.loads(text)
            assert full["run_metadata"]["run_id"] == first["run_metadata"]["run_id"]
            return full

    native = asyncio.run(invoke())
    flags = ["otherbu"]
    for key, value in inputs.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run([*flags, "--fields", *fields, "--strict-fields"]) == 0
    cli = json.loads(capsys.readouterr().out)
    for current in (expected, native, cli):
        current.pop("run_metadata")
    assert expected == native == cli


@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize("failed_body", [None, "Pluto", "North Node"])
def test_actual_reference_points_project_across_three_transports(
    rest, capsys, monkeypatch, zodiacal, failed_body
):
    from fatebridge.core.astro import ephemeris

    original = ephemeris._swisseph_planet_state
    if failed_body:
        monkeypatch.setattr(
            ephemeris,
            "_swisseph_planet_state",
            lambda name, *a, **kw: (
                None if name == failed_body else original(name, *a, **kw)
            ),
        )
    inputs = {
        "planet": "Jupiter",
        "sign": "Aries",
        "house": 0,
        "date": "2024-03-20",
        "time": "06:30",
        "zone": "UTC",
        "gps_lat": 51.5,
        "gps_lon": 0,
        "zodiacal": zodiacal,
    }
    fields = ["chart.params.ephemerisReferencePoints"]
    response = rest.post(
        SPEC.rest_path,
        json=inputs,
        params={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
    )
    assert response.status_code == 200, response.text
    expected = response.json()
    basis = expected["chart"]["params"]["ephemerisReferencePoints"]
    assert basis["approximate_points"] == ([failed_body] if failed_body else [])
    assert basis["center_body_correction_applied"] is False
    assert ("Pluto" in basis["system_barycenters"]) is (failed_body != "Pluto")
    assert basis["theoretical_points"] == (
        [] if failed_body == "North Node" else ["North Node"]
    )
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "otherbu",
                {
                    **inputs,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not result.is_error
            return await verified_inline_business(client, result.structured_content)

    native = asyncio.run(invoke())
    flags = ["otherbu"]
    for key, value in inputs.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run([*flags, "--fields", *fields, "--strict-fields"]) == 0
    cli = json.loads(capsys.readouterr().out)
    for current in (expected, native, cli):
        current.pop("run_metadata")
    assert expected == native == cli


@pytest.mark.parametrize(
    "planet,assignment",
    [
        ("Sun", "day"),
        ("Moon", "night"),
        ("Mercury", None),
        ("Saturn", "day"),
        ("Mars", "night"),
        ("NorthNode", None),
    ],
)
def test_i7_natural_assignment_and_unknown_chart_sect_project_across_three_transports(
    rest, capsys, planet, assignment
):
    inputs = {"planet": planet, "sign": "Aries", "house": 11}
    fields = [
        "method_id",
        "symbolic_details.planet_sect_condition",
        "symbolic_details.triplicity_condition.sect",
        "interpretation.planet_sect_meaning",
        "interpretation.evidence.planet_sect_meaning",
    ]
    response = rest.post(
        SPEC.rest_path,
        json=inputs,
        params={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
    )
    assert response.status_code == 200, response.text
    expected = response.json()
    condition = expected["symbolic_details"]["planet_sect_condition"]
    assert condition["natural_sect"] == assignment
    assert condition["applied_chart_sect"] is None
    assert condition["matches_chart_sect"] is None
    if planet == "Mercury":
        assert condition["assignments_by_solar_phase"] == {
            "morning_star": "day",
            "evening_star": "night",
        }
    assert expected["symbolic_details"]["triplicity_condition"]["sect"] is None
    assert expected["interpretation"]["evidence"]["planet_sect_meaning"][
        "rule_ids"
    ] == ["natural_planet_sect"]
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "otherbu",
                {
                    **inputs,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not result.is_error
            return await verified_inline_business(client, result.structured_content)

    native = asyncio.run(invoke())
    flags = ["otherbu"]
    for key, value in inputs.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run([*flags, "--fields", *fields, "--strict-fields"]) == 0
    cli = json.loads(capsys.readouterr().out)
    for current in (expected, native, cli):
        current.pop("run_metadata")
    assert expected == native == cli


@pytest.mark.parametrize("zodiacal", [0, 1])
def test_one_failed_body_and_its_model_project_across_three_transports(
    rest, capsys, monkeypatch, zodiacal
):
    from fatebridge.core.astro import ephemeris

    original = ephemeris._swisseph_planet_state
    monkeypatch.setattr(
        ephemeris,
        "_swisseph_planet_state",
        lambda name, *a, **kw: None if name == "Pluto" else original(name, *a, **kw),
    )
    inputs = {
        **FACES,
        "date": "2024-03-20",
        "time": "06:30",
        "zone": "UTC",
        "gps_lat": 51.5,
        "gps_lon": 0,
        "hsys": 0,
        "zodiacal": zodiacal,
    }
    fields = [
        "chart.chart.objects",
        "chart.params.chart_profile.engine_precision",
        "chart.params.chart_profile.planetary_models.Sun",
        "chart.params.chart_profile.planetary_models.Pluto",
        "chart.params.chart_profile.orbital_fallback.approximate_planets",
        "chart.params.chart_profile.orbital_fallback.time_argument",
        "chart.params.chart_profile.orbital_fallback.candidate_files",
    ]
    if zodiacal:
        fields.append("chart.params.chart_profile.sidereal_planetary_methods.Pluto")
    response = rest.post(
        SPEC.rest_path, json=inputs, params={"fields": fields, "strict_fields": True}
    )
    assert response.status_code == 200, response.text
    expected = response.json()
    profile = expected["chart"]["params"]["chart_profile"]
    assert profile["orbital_fallback"]["approximate_planets"] == ["Pluto"]
    assert (
        profile["planetary_models"]["Pluto"] == "fatebridge_approximate_orbital_model"
    )
    assert profile["planetary_models"]["Sun"] != "fatebridge_approximate_orbital_model"
    assert expected["run_metadata"]["engine_is_approximate"] is True
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "otherbu",
                {
                    **inputs,
                    "fields": fields,
                    "strict_fields": True,
                    "response_char_limit": 0,
                },
            )
            assert not result.is_error
            return result.structured_content

    native = asyncio.run(invoke())
    flags = ["otherbu"]
    for key, value in inputs.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run([*flags, "--fields", *fields, "--strict-fields"]) == 0
    cli = json.loads(capsys.readouterr().out)
    for current in (expected, native, cli):
        current.pop("run_metadata")
    assert expected == native == cli


@pytest.fixture
def rest(monkeypatch):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as client:
        yield client


@pytest.mark.parametrize(
    "context",
    [
        {},
        {
            "date": "2000-02-29",
            "time": "18:15:59",
            "zone": "UTC",
            "lat": "0",
            "lon": "0",
        },
        {
            "date": "2024-03-20",
            "time": "00:30:00.123456",
            "zone": "UTC",
            "gps_lat": 51.500000123,
            "gps_lon": 0.000000123,
            "fortune_method": "ptolemy_iii10",
        },
        {
            "date": "2000-01-01",
            "time": "12:00",
            "zone": "UTC",
            "gps_lat": 51.5,
            "gps_lon": 0,
            "zodiacal": 1,
            "hsys": 8,
        },
        {
            "date": "2024-06-21",
            "time": "00:30",
            "zone": "UTC",
            "gps_lat": 66.5,
            "gps_lon": 0,
            "hsys": 6,
        },
        {
            "date": "2024-06-21",
            "time": "00:30",
            "zone": "UTC",
            "gps_lat": 80,
            "gps_lon": 0,
            "zodiacal": 1,
            "hsys": 2,
        },
        {
            "date": "2024-06-21",
            "time": "12:00",
            "zone": "UTC",
            "gps_lat": 90,
            "gps_lon": 0,
            "hsys": 0,
        },
        {
            "date": "2024-06-21",
            "time": "12:00",
            "zone": "UTC",
            "gps_lat": -90,
            "gps_lon": 0,
            "hsys": 0,
            "zodiacal": 1,
        },
    ],
)
def test_full_results_match_across_three_transports(rest, capsys, context):
    args = {**FACES, **context, "response_char_limit": 0}
    response = rest.post(SPEC.rest_path, json={**FACES, **context})
    assert response.status_code == 200, response.text
    expected = response.json()
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)

    async def mcp_result():
        async with Client(create_mcp_app()) as client:
            tools = {t.name: t for t in await client.list_tools()}
            schema = tools["otherbu"].model_dump(by_alias=True)["inputSchema"]
            assert {"planet", "sign", "house"} <= set(schema["required"])
            assert "date" not in schema["required"]
            result = await client.call_tool("otherbu", args)
            assert not result.is_error
            Draft202012Validator(
                tools["otherbu"].model_dump(by_alias=True)["outputSchema"]
            ).validate(result.structured_content)
            return result.structured_content

    via_mcp = asyncio.run(mcp_result())
    flags = ["otherbu"]
    for name, value in args.items():
        flags.extend(["--" + name.replace("_", "-"), str(value)])
    assert run(flags) == 0
    via_cli = json.loads(capsys.readouterr().out)
    for current in (expected, via_mcp, via_cli):
        current.pop("run_metadata")
    assert expected == via_mcp == via_cli


@pytest.mark.parametrize(
    "changes",
    [
        {"planet": "typo"},
        {"sign": "unknown"},
        {"house": 12},
        {"house": True},
        {"house": 1.2},
        {"planet": None},
    ],
)
def test_invalid_faces_rejected_by_rest_and_native_mcp(rest, changes):
    args = {**FACES, **changes}
    assert rest.post(SPEC.rest_path, json=args).status_code == 422

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool("otherbu", args, raise_on_error=False)
            assert result.is_error

    asyncio.run(invoke())


def test_projection_and_same_run_calculation_claims(rest, capsys):
    fields = [
        "planet",
        "symbolic_details.house_number",
        "symbolic_details.sign_condition.conditions",
        "validation.prediction",
        "rule_trace",
        "rulesets",
    ]
    response = rest.post(
        SPEC.rest_path,
        json=FACES,
        params={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "snapshot_text" not in body
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(body)
    assert body["symbolic_details"]["house_number"] == 12
    assert body["validation"]["prediction"] == "not_validated"
    assert (
        run(
            [
                "otherbu",
                "--planet",
                "NorthNode",
                "--sign",
                "Virgo",
                "--house",
                "11",
                "--fields",
                *fields,
                "--strict-fields",
            ]
        )
        == 0
    )
    cli = json.loads(capsys.readouterr().out)
    assert cli["symbolic_details"] == body["symbolic_details"]
    # The claim verifier operates on the complete original run, not this projection.
    full = rest.post(SPEC.rest_path, json=FACES).json()
    receipt = full["run_metadata"]
    claim = CalculationClaim(
        path="symbolic_details.house_number",
        value=12,
        run_id=receipt["run_id"],
    )
    assert (
        verify_calculation_claims(full, [claim])["status"]
        == "verified_structured_facts"
    )
    changed = claim.model_copy(update={"value": 1})
    assert verify_calculation_claims(full, [changed])["status"] == "rejected"


def test_joy_and_self_dispositor_fields_project_on_all_surfaces(rest, capsys):
    inputs = {"planet": "Mercury", "sign": "Virgo", "house": 0}
    fields = [
        "symbolic_details.house_condition.in_joy",
        "symbolic_details.sign_condition.dispositor_status",
        "interpretation.house_condition_meaning",
    ]
    expected = rest.post(
        SPEC.rest_path, json=inputs, params={"fields": fields, "strict_fields": True}
    ).json()
    assert expected["symbolic_details"]["house_condition"] == {"in_joy": True}
    assert expected["symbolic_details"]["sign_condition"] == {
        "dispositor_status": "self_symbolic"
    }

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "otherbu", {**inputs, "fields": fields, "strict_fields": True}
            )
            assert not result.is_error
            return await verified_inline_business(client, result.structured_content)

    native = asyncio.run(invoke())
    assert (
        run(
            [
                "otherbu",
                "--planet",
                "Mercury",
                "--sign",
                "Virgo",
                "--house",
                "0",
                "--fields",
                *fields,
                "--strict-fields",
            ]
        )
        == 0
    )
    cli = json.loads(capsys.readouterr().out)
    for result in (expected, native, cli):
        result.pop("run_metadata")
    assert expected == native == cli


@pytest.mark.parametrize("latitude", [-90, 90])
@pytest.mark.parametrize("offline", [True, False])
def test_pole_convention_projects_across_three_transports(
    rest, capsys, monkeypatch, latitude, offline
):
    if offline:
        from fatebridge.core.astro import runtime

        monkeypatch.setattr(runtime, "swe", None)
    inputs = {
        **FACES,
        "date": "2024-06-21",
        "time": "12:00",
        "zone": "UTC",
        "gps_lat": latitude,
        "gps_lon": 0,
        "hsys": 0,
    }
    fields = [
        "chart.params.chart_profile.angle_definition.status",
        "chart.params.chart_profile.angle_definition.fixed_direction_diurnal_rising_defined",
        "chart.params.chart_profile.angle_definition.reference_meridian",
        "chart.params.chart_profile.angle_definition.note_zh",
    ]
    response = rest.post(
        SPEC.rest_path, json=inputs, params={"fields": fields, "strict_fields": True}
    )
    assert response.status_code == 200, response.text
    expected = response.json()
    definition = expected["chart"]["params"]["chart_profile"]["angle_definition"]
    assert definition["status"] == "geographic_pole_meridian_convention"
    assert definition["fixed_direction_diurnal_rising_defined"] is False
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "otherbu", {**inputs, "fields": fields, "strict_fields": True}
            )
            assert not result.is_error
            return await verified_inline_business(client, result.structured_content)

    native = asyncio.run(invoke())
    flags = ["otherbu"]
    for key, value in inputs.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run([*flags, "--fields", *fields, "--strict-fields"]) == 0
    cli = json.loads(capsys.readouterr().out)
    for current in (expected, native, cli):
        current.pop("run_metadata")
    assert expected == native == cli


@pytest.mark.parametrize("hemisphere", [1, -1])
@pytest.mark.parametrize("offline", [True, False])
def test_horizon_degeneracy_projects_across_three_transports(
    rest, capsys, monkeypatch, hemisphere, offline
):
    from fatebridge.core.astro import runtime
    from tests.astrodice.test_astrodice_horizon_degeneracy import singular_sky_inputs

    if offline:
        monkeypatch.setattr(runtime, "swe", None)
    sky = singular_sky_inputs(native=not offline, hemisphere=hemisphere)
    inputs = {
        **FACES,
        "date": sky["date"],
        "time": sky["time"],
        "zone": sky["zone"],
        "gps_lat": sky["lat"],
        "gps_lon": sky["lon"],
        "hsys": 0,
    }
    fields = [
        "chart.params.chart_profile.angle_definition",
        "chart.chart.angles",
    ]
    response = rest.post(
        SPEC.rest_path, json=inputs, params={"fields": fields, "strict_fields": True}
    )
    assert response.status_code == 200, response.text
    expected = response.json()
    definition = expected["chart"]["params"]["chart_profile"]["angle_definition"]
    assert definition["status"] == "ecliptic_horizon_numerically_unresolved"
    assert definition["geometric_ascendant_resolved"] is False
    assert "无法从这些数值解析唯一ASC" in definition["note_zh"]
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "otherbu", {**inputs, "fields": fields, "strict_fields": True}
            )
            assert not result.is_error
            return await verified_inline_business(client, result.structured_content)

    native = asyncio.run(invoke())
    flags = ["otherbu"]
    for key, value in inputs.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run([*flags, "--fields", *fields, "--strict-fields"]) == 0
    cli = json.loads(capsys.readouterr().out)
    for current in (expected, native, cli):
        current.pop("run_metadata")
    assert expected == native == cli


@pytest.mark.parametrize("date", ["0001-06-21", "2050-12-21", "9999-06-21"])
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_rotation_phase_policy_and_angles_project_across_three_transports(
    rest, capsys, date, zodiacal
):
    inputs = {
        **FACES,
        "date": date,
        "time": "12:00",
        "zone": "UTC",
        "gps_lat": 51.5,
        "gps_lon": 0,
        "hsys": 0,
        "zodiacal": zodiacal,
    }
    root = "chart.params.chart_profile.earth_rotation."
    fields = [
        root + "policy_id",
        root + "sidereal_time_model",
        root + "longterm_phase_alignment",
        root + "tt_argument_policy",
        "chart.chart.angles",
    ]
    response = rest.post(
        SPEC.rest_path, json=inputs, params={"fields": fields, "strict_fields": True}
    )
    assert response.status_code == 200, response.text
    expected = response.json()
    policy = expected["chart"]["params"]["chart_profile"]["earth_rotation"]
    assert policy["policy_id"] == "fatebridge_standard_rotation_v3"
    assert policy["tt_argument_policy"] == (
        "shared_default_DeltaT_minus1_before1960_SWIEPH_from1960"
    )
    if date.startswith("2050"):
        assert policy["sidereal_time_model"] == "IERS2010_expression_Swiss_nutation"
        assert policy["longterm_phase_alignment"] is None
    else:
        assert (
            policy["sidereal_time_model"]
            == "Swiss_longterm_with_boundary_phase_alignment"
        )
        assert (
            policy["longterm_phase_alignment"]["absolute_accuracy_certified"] is False
        )
        assert policy["longterm_phase_alignment"]["boundary_tt_jd"] in [
            2378495.0,
            2524595.0,
        ]
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "otherbu", {**inputs, "fields": fields, "strict_fields": True}
            )
            assert not result.is_error
            return await verified_inline_business(client, result.structured_content)

    native = asyncio.run(invoke())
    flags = ["otherbu"]
    for key, value in inputs.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run([*flags, "--fields", *fields, "--strict-fields"]) == 0
    cli = json.loads(capsys.readouterr().out)
    for current in (expected, native, cli):
        current.pop("run_metadata")
    assert expected == native == cli


@pytest.mark.parametrize(
    "changes",
    [
        {"gps_lat": True},
        {"gps_lon": False},
        {"gps_lat": 0},
        {"lat": "nonsense", "gps_lat": 51.5},
        {"fortune_method": "guess"},
    ],
)
def test_sky_coordinate_and_formula_errors_rejected_by_rest_and_mcp(rest, changes):
    inputs = {
        **FACES,
        "date": "2024-03-20",
        "time": "00:30",
        "zone": "UTC",
        "lat": "51.5",
        "lon": "0",
        **changes,
    }
    response = rest.post(SPEC.rest_path, json=inputs)
    assert response.status_code == 422, response.text

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool("otherbu", inputs, raise_on_error=False)
            assert result.is_error

    asyncio.run(invoke())


def test_sky_formula_provenance_projects_on_all_surfaces(rest, capsys):
    inputs = {
        **FACES,
        "date": "2024-03-20",
        "time": "00:30",
        "zone": "UTC",
        "gps_lat": 51.500000123,
        "gps_lon": 0.000000123,
        "fortune_method": "ptolemy_iii10",
    }
    fields = [
        "chart.params.fortuneDefinition.method",
        "chart.params.fortuneDefinition.sect_applied",
        "chart.params.fortuneDefinition.source_url",
        "chart.params.birthLatitude",
        "chart.params.birthLongitude",
    ]
    response = rest.post(
        SPEC.rest_path, json=inputs, params={"fields": fields, "strict_fields": True}
    )
    assert response.status_code == 200, response.text
    expected = response.json()
    assert expected["chart"]["params"]["fortuneDefinition"]["method"] == "ptolemy_iii10"
    assert expected["chart"]["params"]["fortuneDefinition"]["sect_applied"] is None
    assert expected["chart"]["params"]["birthLatitude"] == 51.500000123
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "otherbu", {**inputs, "fields": fields, "strict_fields": True}
            )
            assert not result.is_error
            return await verified_inline_business(client, result.structured_content)

    native = asyncio.run(invoke())
    flags = ["otherbu"]
    for key, value in inputs.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run([*flags, "--fields", *fields, "--strict-fields"]) == 0
    cli = json.loads(capsys.readouterr().out)
    for current in (expected, native, cli):
        current.pop("run_metadata")
    assert expected == native == cli


@pytest.mark.parametrize(
    "planet,sign,assigned,day_role,day_match",
    [
        ("Jupiter", "Aries", True, "assigned_not_selected", False),
        ("Mars", "Aries", False, "not_assigned", False),
        ("Venus", "Cancer", True, "co_ruler", True),
        ("NorthNode", "Aries", None, "outside_seven_planet_scope", None),
    ],
)
def test_triangle_assignment_and_conditional_roles_project_across_three_transports(
    rest, capsys, planet, sign, assigned, day_role, day_match
):
    inputs = {"planet": planet, "sign": sign, "house": 0}
    fields = [
        "method_id",
        "symbolic_details.triplicity_condition.assigned_rulers",
        "symbolic_details.triplicity_condition.in_assigned_group",
        "symbolic_details.triplicity_condition.roles_by_sect.day",
        "symbolic_details.triplicity_condition.matches_by_sect.day",
        "symbolic_details.triplicity_condition.match_definition",
        "interpretation.triplicity_meaning",
    ]
    response = rest.post(
        SPEC.rest_path,
        json=inputs,
        params={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
    )
    assert response.status_code == 200, response.text
    expected = response.json()
    assert expected["method_id"] == "astrodice_symbolic_v7"
    relation = expected["symbolic_details"]["triplicity_condition"]
    assert relation["in_assigned_group"] is assigned
    assert relation["roles_by_sect"] == {"day": day_role}
    assert relation["matches_by_sect"] == {"day": day_match}
    assert "不属于该组" not in expected["interpretation"]["triplicity_meaning"]

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "otherbu",
                {
                    **inputs,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not result.is_error
            return await verified_inline_business(client, result.structured_content)

    native = asyncio.run(invoke())
    assert (
        run(
            [
                "otherbu",
                "--planet",
                planet,
                "--sign",
                sign,
                "--house",
                "0",
                "--fields",
                *fields,
                "--strict-fields",
            ]
        )
        == 0
    )
    cli = json.loads(capsys.readouterr().out)
    for result in (expected, native, cli):
        result.pop("run_metadata")
    assert expected == native == cli


def test_default_native_delivery_recovers_the_same_run_roles_and_explanation():
    async def invoke():
        async with Client(create_mcp_app()) as client:
            response = await client.call_tool(
                "otherbu", {"planet": "Jupiter", "sign": "Aries", "house": 0}
            )
            assert not response.is_error
            first = response.structured_content
            reference = first["result_delivery"]
            assert "interpretation" in reference["deferred_fields"]
            parts = []
            uri = reference["first_page_uri"]
            while uri is not None:
                page = json.loads((await client.read_resource(uri))[0].text)
                parts.append(page["text"])
                uri = page["next_uri"]
            text = "".join(parts)
            assert len(text) == reference["total_chars"]
            full = json.loads(text)
            assert full["run_metadata"]["run_id"] == first["run_metadata"]["run_id"]
            assert full["method_id"] == "astrodice_symbolic_v7"
            relation = full["symbolic_details"]["triplicity_condition"]
            assert relation["in_assigned_group"] is True
            assert relation["matches_by_sect"]["day"] is False
            assert relation["roles_by_sect"]["day"] == "assigned_not_selected"
            assert "本骰星属总体分派" in full["interpretation"]["triplicity_meaning"]
            receipt = full["run_metadata"]
            claim = CalculationClaim(
                path="symbolic_details.triplicity_condition.in_assigned_group",
                value=True,
                run_id=receipt["run_id"],
            )
            assert (
                verify_calculation_claims(full, [claim])["status"]
                == "verified_structured_facts"
            )
            wrong = claim.model_copy(update={"value": False})
            assert verify_calculation_claims(full, [wrong])["status"] == "rejected"

    asyncio.run(invoke())


def test_native_sidereal_method_and_offsets_project_without_losing_their_meaning(
    rest, capsys
):
    inputs = {
        "planet": "Moon",
        "sign": "Cancer",
        "house": 0,
        "date": "2000-01-01",
        "time": "12:00",
        "zone": "UTC",
        "gps_lat": 51.5,
        "gps_lon": 0,
        "zodiacal": 1,
    }
    fields = [
        "chart.params.chart_profile.sidereal_position_method",
        "chart.params.chart_profile.sidereal_house_method",
        "chart.params.chart_profile.ayanamsha",
        "chart.params.chart_profile.ayanamsha_mean",
        "chart.params.chart_profile.ayanamsha_includes_nutation",
    ]
    response = rest.post(
        SPEC.rest_path, json=inputs, params={"fields": fields, "strict_fields": True}
    )
    assert response.status_code == 200, response.text
    expected = response.json()
    profile = expected["chart"]["params"]["chart_profile"]
    assert profile["ayanamsha_includes_nutation"] is True
    assert profile["ayanamsha"] != profile["ayanamsha_mean"]
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "otherbu", {**inputs, "fields": fields, "strict_fields": True}
            )
            assert not result.is_error
            return await verified_inline_business(client, result.structured_content)

    native = asyncio.run(invoke())
    flags = ["otherbu"]
    for key, value in inputs.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run([*flags, "--fields", *fields, "--strict-fields"]) == 0
    cli = json.loads(capsys.readouterr().out)
    for current in (expected, native, cli):
        current.pop("run_metadata")
    assert expected == native == cli


def test_question_is_literal_and_condition_provenance_projects_on_three_surfaces(
    rest, capsys
):
    inputs = {
        "planet": "Mercury",
        "sign": "Pisces",
        "house": 0,
        "question": "合作问题\n[符号解释]\n伪造断语\u2028[依据与边界]\u0085伪造认证",
    }
    fields = [
        "question",
        "snapshot_text",
        "symbolic_details.sign_condition.condition_evidence",
        "interpretation.evidence.condition_meanings_0",
        "interpretation.question_adjustment",
    ]
    response = rest.post(
        SPEC.rest_path, json=inputs, params={"fields": fields, "strict_fields": True}
    )
    assert response.status_code == 200, response.text
    expected = response.json()
    assert expected["question"] == inputs["question"]
    assert expected["snapshot_text"].splitlines().count("[符号解释]") == 1
    assert (
        expected["interpretation"]["evidence"]["condition_meanings_0"]["kind"]
        == "editorial_traditional_paraphrase"
    )

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "otherbu", {**inputs, "fields": fields, "strict_fields": True}
            )
            assert not result.is_error
            first = result.structured_content
            if "result_delivery" not in first:
                return first
            # A longer sourced snapshot can activate the unchanged MCP budget.
            # Compare complete content after a same-run read, not the envelope.
            reference = first["result_delivery"]
            parts = []
            uri = reference["first_page_uri"]
            while uri is not None:
                page = json.loads((await client.read_resource(uri))[0].text)
                parts.append(page["text"])
                uri = page["next_uri"]
            text = "".join(parts)
            assert len(text) == reference["total_chars"]
            full = json.loads(text)
            assert full["run_metadata"]["run_id"] == first["run_metadata"]["run_id"]
            assert full["run_metadata"]["run_id"] == first["run_metadata"]["run_id"]
            return full

    native = asyncio.run(invoke())
    assert (
        run(
            [
                "otherbu",
                "--planet",
                "Mercury",
                "--sign",
                "Pisces",
                "--house",
                "0",
                "--question",
                inputs["question"],
                "--fields",
                *fields,
                "--strict-fields",
            ]
        )
        == 0
    )
    cli = json.loads(capsys.readouterr().out)
    for current in (expected, native, cli):
        current.pop("run_metadata")
    assert expected == native == cli

    full = rest.post(SPEC.rest_path, json=inputs).json()
    receipt = full["run_metadata"]
    claim = CalculationClaim(
        path="symbolic_details.sign_condition.condition_evidence.2.ruleset_id",
        value="houlding_opposite_domicile_definition_v1",
        run_id=receipt["run_id"],
    )
    assert (
        verify_calculation_claims(full, [claim])["status"]
        == "verified_structured_facts"
    )
    incorrect = claim.model_copy(update={"value": "ptolemy_ashmand_1822_signs"})
    assert verify_calculation_claims(full, [incorrect])["status"] == "rejected"


@pytest.mark.parametrize("planet,matches", [("Mars", True), ("NorthNode", None)])
def test_conditional_triplicity_projects_without_selecting_sect(
    rest, capsys, planet, matches
):
    inputs = {"planet": planet, "sign": "Cancer", "house": 0}
    fields = [
        "symbolic_details.triplicity_condition.sect",
        "symbolic_details.triplicity_condition.rulers_by_sect.day.co_ruler",
        "symbolic_details.triplicity_condition.matches_by_sect.night",
        "interpretation.triplicity_meaning",
    ]
    response = rest.post(
        SPEC.rest_path, json=inputs, params={"fields": fields, "strict_fields": True}
    )
    assert response.status_code == 200, response.text
    expected = response.json()
    relation = expected["symbolic_details"]["triplicity_condition"]
    assert relation["sect"] is None
    assert relation["rulers_by_sect"]["day"] == {"co_ruler": "Venus"}
    assert relation["matches_by_sect"]["night"] is matches

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "otherbu", {**inputs, "fields": fields, "strict_fields": True}
            )
            assert not result.is_error
            return await verified_inline_business(client, result.structured_content)

    native = asyncio.run(invoke())
    assert (
        run(
            [
                "otherbu",
                "--planet",
                planet,
                "--sign",
                "Cancer",
                "--house",
                "0",
                "--fields",
                *fields,
                "--strict-fields",
            ]
        )
        == 0
    )
    cli = json.loads(capsys.readouterr().out)
    for result in (expected, native, cli):
        result.pop("run_metadata")
    assert expected == native == cli


def test_polar_projection_parameters_are_projectable_across_all_transports(
    rest, capsys
):
    inputs = {
        "planet": "Mercury",
        "sign": "Virgo",
        "house": 6,
        "date": "2024-06-21",
        "time": "00:30",
        "zone": "UTC",
        "gps_lat": 66.5,
        "gps_lon": 0,
        "hsys": 6,
    }
    fields = [
        "chart.params.housePositionMethod",
        "chart.params.housePositionProjection.armc",
        "chart.params.housePositionProjection.input_ecliptic_latitude",
        "chart.params.chart_profile.house_position_projection.reason",
        "chart.chart.objects",
    ]
    response = rest.post(
        SPEC.rest_path,
        json=inputs,
        params={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
    )
    assert response.status_code == 200, response.text
    expected = response.json()
    params = expected["chart"]["params"]
    assert (
        params["housePositionMethod"]
        == "fatebridge_topocentric_zero_ecliptic_latitude_v1"
    )
    assert params["housePositionProjection"]["input_ecliptic_latitude"] == 0.0
    assert params["chart_profile"]["house_position_projection"] == {
        "reason": "labelled_cusps_not_single_prograde_partition"
    }

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "otherbu",
                {
                    **inputs,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not result.is_error
            first = result.structured_content
            if "result_delivery" not in first:
                return first
            ref = first["result_delivery"]
            parts = []
            uri = ref["first_page_uri"]
            while uri is not None:
                page = json.loads((await client.read_resource(uri))[0].text)
                parts.append(page["text"])
                uri = page["next_uri"]
            text = "".join(parts)
            assert len(text) == ref["total_chars"]
            full = json.loads(text)
            assert full["run_metadata"]["run_id"] == first["run_metadata"]["run_id"]
            return full

    native = asyncio.run(invoke())
    flags = ["otherbu"]
    for name, value in inputs.items():
        flags.extend(["--" + name.replace("_", "-"), str(value)])
    assert run([*flags, "--fields", *fields, "--strict-fields"]) == 0
    cli = json.loads(capsys.readouterr().out)
    for current in (expected, native, cli):
        current.pop("run_metadata")
    assert expected == native == cli
