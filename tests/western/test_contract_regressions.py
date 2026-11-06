"""Related contract regressions with shared imports; original cases retained."""

import asyncio
import itertools
import json
import math
import random
from fractions import Fraction as F
from itertools import combinations

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
import fatebridge.cli as cli
from fatebridge.application.description import spec_is_cli_safe
from fatebridge.application.examples import evidence_views
from fatebridge.core.astro import runtime
from fatebridge.core.astro.geometry import _house_for_longitude
from fatebridge.core.astro.midpoints import midpoint_geometry
from fatebridge.core.astro.parts import _essential_dignity
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.solar_position import apparent_position_policy
from fatebridge.core.astrology_tables import _opposite_sign
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.astrology import calculate_germany_chart_analysis
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import EphemerisSourceError
from tests.fixtures.surface_payloads import astro_payload
from tests.support.transports import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
    surface_calls,
)
from tests.support.western_angular_reference import reference_phase
from tests.western.test_house_selection_contract import CODE_SPECS, HOUSE_SPECS, inputs
from tests.western.test_other_chart_schools_transports import (
    test_specialized_facts_across_three_real_surfaces as check_surfaces,
)
from tests.western.test_western_accuracy import BIRTH
from tests.western.test_western_election import CANDIDATE
from tests.western.test_western_horary import QUESTION


@pytest.mark.parametrize(
    "planet, sign, expected",
    [
        ("Sun", "Leo", "rulership"),
        ("Sun", "Aquarius", "detriment"),
        ("Sun", "Aries", "exaltation"),
        ("Sun", "Libra", "fall"),
        ("Moon", "Cancer", "rulership"),
        ("Moon", "Taurus", "exaltation"),
        ("Mars", "Aries", "rulership"),
        ("Mars", "Scorpio", "rulership"),
        ("Mars", "Libra", "detriment"),  # 命主火星天秤
        ("Mars", "Capricorn", "exaltation"),
        ("Mars", "Cancer", "fall"),
        ("Mercury", "Sagittarius", "detriment"),  # 命主水星射手
        ("Jupiter", "Gemini", "detriment"),  # 命主木星双子
        ("Saturn", "Taurus", "no_major_dignity"),
        ("Venus", "Aquarius", "no_major_dignity"),
    ],
)
def test_classical_dignities(planet, sign, expected):
    result = _essential_dignity(planet, sign)
    assert result is not None
    assert result["dignity"] == expected


@pytest.mark.parametrize("planet", ["Uranus", "Neptune", "Pluto", "North Node"])
def test_non_classical_bodies_have_no_dignity(planet):
    assert _essential_dignity(planet, "Aquarius") is None


def test_status_zh_labels():
    assert _essential_dignity("Mars", "Libra")["status_zh"] == "陷"
    assert _essential_dignity("Sun", "Leo")["status_zh"] == "庙"
    assert _essential_dignity("Sun", "Aries")["status_zh"] == "旺"
    assert _essential_dignity("Mars", "Cancer")["status_zh"] == "弱"


def test_opposite_sign():
    assert _opposite_sign("Aries") == "Libra"
    assert _opposite_sign("Libra") == "Aries"
    assert _opposite_sign("Pisces") == "Virgo"


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
def test_e_and_a_have_identical_native_cusps_on_the_predeclared_grid():
    count = 0
    for armc, lat, eps in itertools.product(
        range(0, 360, 30), [-55, -25, 0, 25, 55], [0, 23.4, 30]
    ):
        a = runtime.ephemeris_call("houses_armc", armc, lat, eps, b"A")
        e = runtime.ephemeris_call("houses_armc", armc, lat, eps, b"E")
        assert a == e
        count += 1
    assert count == 180


def test_last_house_does_not_round_up_at_the_wrapped_first_cusp():
    cusps = [(60.0 + i * 30) % 360 for i in range(12)]
    assert (
        _house_for_longitude(math.nextafter(60.0, -math.inf), 60.0, "whole_sign", cusps)
        == 12
    )
    assert _house_for_longitude(60.0, 60.0, "whole_sign", cusps) == 1


@pytest.mark.parametrize("origin", [0.0, 30.0, 60.0, 215.12345])
def test_every_cusp_matches_independent_circular_interval_membership(origin):
    cusps = [(origin + i * 30) % 360 for i in range(12)]
    for edge in cusps:
        for probe in [
            math.nextafter(edge, -math.inf),
            edge,
            math.nextafter(edge, math.inf),
        ]:
            matches = []
            for i, start in enumerate(cusps):
                width = (F(cusps[(i + 1) % 12]) - F(start)) % 360
                offset = (F(probe) - F(start)) % 360
                if offset < width:
                    matches.append(i + 1)
            assert len(matches) == 1
            assert _house_for_longitude(probe, origin, "equal", cusps) == matches[0]


def test_equal_house_fallback_also_retains_both_sides_of_every_edge():
    ascendant = 60.0
    for i in range(12):
        edge = (ascendant + 30 * i) % 360
        assert _house_for_longitude(edge, ascendant, "equal") == i + 1
        assert (
            _house_for_longitude(math.nextafter(edge, -math.inf), ascendant, "equal")
            == (i - 1) % 12 + 1
        )
        assert (
            _house_for_longitude(math.nextafter(edge, math.inf), ascendant, "equal")
            == i + 1
        )


def test_whole_sign_fallback_handles_negative_wrap_without_rounding_to_zero():
    assert _house_for_longitude(math.nextafter(0.0, -math.inf), 0.0, "whole_sign") == 12
    assert _house_for_longitude(0.0, 0.0, "whole_sign") == 1


def test_nonfinite_geometry_is_rejected_explicitly():
    for invalid in [math.nan, math.inf, -math.inf]:
        invalid_cusps = [invalid, *[float(i * 30) for i in range(1, 12)]]
        for args in [
            (invalid, 0.0, None),
            (0.0, invalid, None),
            (0.0, 0.0, invalid_cusps),
        ]:
            with pytest.raises(ValueError, match="finite"):
                _house_for_longitude(args[0], args[1], "equal", args[2])


def test_all_selector_endpoints_reject_invalid_input_before_any_calculation(
    monkeypatch, tmp_path, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("invalid house selection reached calculation")

    monkeypatch.setattr("fatebridge.transports.rest.execute_tool", forbidden)
    monkeypatch.setattr("fatebridge.transports.mcp.execute_tool", forbidden)
    monkeypatch.setattr(cli, "execute_tool", forbidden)
    rest = TestClient(api.app)
    seen = []

    async def run():
        async with Client(create_mcp_app()) as client:
            available_tools = {tool.name for tool in await client.list_tools()}
            for field, specs, issue_code in (
                ("house_system", HOUSE_SPECS, "invalid_house_system"),
                ("hsys", CODE_SPECS, "invalid_house_code"),
            ):
                for i, spec in enumerate(specs):
                    value = [True, 99, 3.7, "unknown-name", " "][i % 5]
                    body = {**inputs(spec), field: value}
                    results = []
                    if spec.rest_path is not None:
                        response = rest.post(spec.rest_path, json=body)
                        assert response.status_code == 422, spec.key
                        results.append(response.json())
                    path = tmp_path / f"{field}-{spec.key}.json"
                    path.write_text(json.dumps(body))
                    capsys.readouterr()
                    cli_available = spec_is_cli_safe(spec)
                    code = cli.run(
                        [
                            spec.tool_name,
                            (
                                "--request-file"
                                if spec.cli_request_file
                                else "--subject-file"
                            ),
                            str(path),
                        ]
                        if cli_available
                        else [spec.tool_name]
                    )
                    local = json.loads(capsys.readouterr().out)
                    if cli_available:
                        assert code == 1, spec.key
                        results.append(local)
                    else:
                        assert (
                            code == 2 and local["error_code"] == "cli_unsupported"
                        ), spec.key
                    if spec.mcp_name is not None:
                        assert spec.tool_name in available_tools
                        native = await client.call_tool(
                            spec.tool_name, body, raise_on_error=False
                        )
                        assert native.is_error, spec.key
                        results.append(json.loads(native.content[0].text))
                    else:
                        # Retain the REST/CLI case; a REST-only compatibility
                        # alias must not be tested as an invented MCP tool.
                        assert spec.tool_name not in available_tools
                    assert results, spec.key
                    for result in results:
                        assert result["issues"][0] == {
                            "path": field,
                            "code": issue_code,
                        }, (spec.key, result)
                        assert (
                            result["retryable"] is False
                            and "run_metadata" not in result
                        )
                    seen.append((field, spec.key))

    asyncio.run(run())
    assert seen == [
        (f, s.key)
        for f, ss in (("house_system", HOUSE_SPECS), ("hsys", CODE_SPECS))
        for s in ss
    ]


@pytest.mark.parametrize(
    "key,variant", [("astro_germany", None), ("astro_chart", "germany")]
)
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_native_meridian_cusps_across_three_surfaces(
    monkeypatch, capsys, tmp_path, key, variant, zodiacal
):
    spec = next(row for row in CATALOG if row.key == "astro_germany")
    card = evidence_views(spec)["meridian_houses"]
    check_surfaces(
        monkeypatch,
        capsys,
        tmp_path,
        key,
        variant,
        card["fields"],
        {"zodiacal": zodiacal, "birth_time_uncertainty_minutes": 1},
    )


def test_offline_geometry_policy_does_not_invent_a_tt_epoch(monkeypatch):
    monkeypatch.setattr(runtime, "swe", None)
    policy = apparent_position_policy(
        None,
        {"Mercury": "fatebridge_approximate_orbital_model"},
        PhysicalEphemerisTrace(),
    )
    assert policy["epoch_jd_tt"] is None
    assert policy["bodies"]["Mercury"]["status"] == "not_evaluated"
    assert policy["source_contexts"] == {}
    assert not policy["observational_accuracy_certified"]


def test_available_native_backend_rejects_an_unknown_tt():
    assert runtime.swe is not None
    with pytest.raises(EphemerisSourceError) as error:
        apparent_position_policy(None, {"Mercury": "swieph"}, PhysicalEphemerisTrace())
    assert error.value.reason == "coordinate_values_unavailable"


@pytest.mark.parametrize("separation", range(0, 360, 45))
def test_hard_angles_keep_full_circle_identity(separation):
    # Rudolph 1979 laws 13/16 specify the angle classes, not these numerical
    # examples or our one-degree inclusive tolerance.
    result = midpoint_geometry({"A": 0.0, "B": float(separation)}, orb_degrees=0)
    for period in (90, 45):
        contacts = result["dials"][str(period)]["two_factor_contacts"]
        assert len(contacts) == int(separation % period == 0)
        if contacts:
            row = contacts[0]
            assert row["equation"] == "A=B"
            assert row["orb"] == row["signed_orb"] == 0
            assert row["factor_offset_degrees"] == (-separation) % 360
            assert row["aspect_degrees"] == min(separation, 360 - separation)
            assert row["separation_degrees"] == min(separation, 360 - separation)
            assert row["rule_id"] == "hamburg.two_factor_hard_contacts.v1"
    # The same pair in two dials is still one pair, not two independent facts.
    assert result["unique_two_factor_pair_count"] == 1


@pytest.mark.parametrize("period", [90, 45])
def test_two_factor_orb_boundaries_use_unrounded_inputs(period):
    for center in range(0, 361, 45):
        for sign in (-1, 1):
            boundary = float(center + sign)
            for value, expected in (
                (math.nextafter(boundary, float(center)), True),
                (boundary, True),
                (math.nextafter(boundary, boundary + sign), False),
            ):
                contacts = midpoint_geometry({"A": 0.0, "B": value})["dials"][
                    str(period)
                ]["two_factor_contacts"]
                assert bool(contacts) == (expected and center % period == 0), (
                    period,
                    center,
                    sign,
                    value,
                )
                if contacts:
                    assert contacts[0]["aspect_degrees"] == min(
                        center % 360, (-center) % 360
                    )
                    assert contacts[0]["orb"] <= 1


@pytest.mark.parametrize("seed,size", [(13981, 9), (68219, 22)])
def test_two_factor_set_against_independent_trigonometry(seed, size):
    rng = random.Random(seed)
    points = {f"P{i:02}": rng.uniform(-400, 700) for i in range(size)}
    result = midpoint_geometry(points)
    union = set()
    for period in (90, 45):
        expected = {}
        for a, b in combinations(sorted(points), 2):
            phi = 2 * math.pi * (points[a] - points[b]) / period
            signed = math.atan2(math.sin(phi), math.cos(phi)) * period / (2 * math.pi)
            if abs(signed) <= 1:
                expected[a, b] = signed
        rows = result["dials"][str(period)]["two_factor_contacts"]
        actual = {(row["id_a"], row["id_b"]): row for row in rows}
        assert len(actual) == len(rows)  # No reversed pairs or self-pair hits.
        assert set(actual) == set(expected)
        union.update(actual)
        for pair, signed in expected.items():
            assert actual[pair]["signed_orb"] == pytest.approx(signed, abs=2e-12)
            theta = math.radians(points[pair[0]] - points[pair[1]])
            separation = abs(math.degrees(math.atan2(math.sin(theta), math.cos(theta))))
            assert actual[pair]["separation_degrees"] == pytest.approx(
                separation, abs=2e-12
            )
    assert result["unique_two_factor_pair_count"] == len(union)


def test_two_factor_pairs_are_order_and_common_rotation_invariant():
    points = {"Sun": 350.0, "Cupido": 35.125, "Midheaven": 80.5, "Aries Point": 0.0}
    first = midpoint_geometry(points)
    reordered = midpoint_geometry(dict(reversed(list(points.items()))))
    rotated = midpoint_geometry({name: value + 17.25 for name, value in points.items()})
    for period in ("90", "45"):
        contacts = first["dials"][period]["two_factor_contacts"]
        assert contacts
        assert contacts == reordered["dials"][period]["two_factor_contacts"]
        assert contacts == rotated["dials"][period]["two_factor_contacts"]


def test_empty_and_single_factor_catalogues_cannot_inflate_contact_counts():
    for points in ({}, {"A": 0.0}):
        result = midpoint_geometry(points)
        assert result["unique_two_factor_pair_count"] == 0
        for dial in result["dials"].values():
            assert not dial["two_factor_contacts"]
            assert not dial["three_factor_contacts"]
            assert not dial["four_factor_contacts"]


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
def test_native_two_factor_layer_covers_all_factors_without_invented_readings():
    layer = calculate_germany_chart_analysis(**astro_payload())["midpoint_analysis"]
    assert layer["ruleset_id"] == "hamburg_midpoint_geometry_v3"
    assert layer["version"] == "3"
    factors = {row["id"]: row for row in layer["factors"]}
    assert len(factors) == 22
    hypotheticals = {
        name for name, row in factors.items() if row["kind"] == "hypothetical"
    }
    union = set()
    all_contacts = []
    for period, dial in layer["dials"].items():
        rows = dial["two_factor_contacts"]
        assert layer["contact_counts"][period]["two_factor"] == len(rows)
        assert rows
        for row in rows:
            union.add((row["id_a"], row["id_b"]))
            assert row["contains_hypothetical"] == bool(
                {row["id_a"], row["id_b"]} & hypotheticals
            )
            assert "source_interpretation" not in row
        all_contacts.extend(rows)
    assert layer["unique_two_factor_pair_count"] == len(union)
    assert any(row["contains_hypothetical"] for row in all_contacts)
    assert any("Midheaven" in (row["id_a"], row["id_b"]) for row in all_contacts)
    trace = next(
        row
        for row in layer["rule_trace"]
        if row["rule_id"] == "hamburg.two_factor_hard_contacts.v1"
    )
    assert trace["source_id"] == "rudolph_1979_17laws"
    assert trace["source_sections"] == ["13", "16"]
    assert layer["original_text_conformance"] == "not_assessed"
    assert layer["real_world_efficacy"] == "not_tested"


@pytest.mark.parametrize(
    "key",
    ["astro_chart", "astro_chart13", "astro_hellen", "astro_india", "astro_germany"],
)
def test_published_motion_card_reads_conditions_with_instantaneous_evidence(key, rest):
    spec = SPECS[key]
    card = evidence_views(spec)["aspect_motion"]
    response = rest.post(
        spec.rest_path,
        json=BIRTH,
        params=[("fields", p) for p in card["fields"]]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", 0),
        ],
    )
    assert response.status_code == 200
    payload = response.json()
    assert not payload.get("projection_warnings")
    result = payload["base_chart"] if key == "astro_germany" else payload
    assert result["classical_patterns"]["aspect_motion"]
    assert (
        result["classical_patterns"]["application_policy"]["rule_id"]
        == "instantaneous_longitude_phase_v1"
    )
    assert "no future perfection" in card["purpose"].lower()


@pytest.mark.parametrize("key", ["astro_chart", "astro_hellen", "astro_india"])
@pytest.mark.parametrize("project", [False, True])
def test_motion_facts_and_limits_agree_across_rest_native_mcp_and_cli(
    key, project, surface_calls
):
    spec = SPECS[key]
    fields = [
        "classical_patterns.aspect_motion",
        "classical_patterns.application_policy",
    ]
    query = [("response_char_limit", 0)]
    flags = ["--response-char-limit", "0"]
    protocol_flags = {}
    if project:
        query += [("fields", f) for f in fields] + [
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
        protocol_flags = {
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        }
    response, protocol, code, local = surface_calls(
        spec, BIRTH, params=query, options=protocol_flags, flags=flags
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        assert not result.get("projection_warnings")
        patterns = result["classical_patterns"]
        assert (
            patterns["application_policy"]["rule_id"]
            == "instantaneous_longitude_phase_v1"
        )
        assert "not_future_perfection" in patterns["application_policy"]["scope"]
        assert patterns["aspect_motion"]
        if project:
            assert "snapshot_text" not in result
            continue
        planets = {p["id"]: p for p in result["planets"]}
        for row in patterns["aspect_motion"]:
            # Only relative speed is needed by the independent gap derivative.
            expected = reference_phase(
                planets[row["planet_a"]]["longitude"],
                0.0,
                planets[row["planet_b"]]["longitude"],
                row["relative_longitude_speed"],
                row["exact_angle"],
            )
            assert row["phase"] == expected
        assert "未检验未来成相及完整原典条件" in result["snapshot_text"]


@pytest.mark.parametrize(
    "tool,prefix,body,inputs",
    [
        ("astro_horary", "question_", "horary", QUESTION),
        ("astro_election", "candidate_", "election", CANDIDATE),
    ],
)
def test_julian_and_gregorian_same_instant_on_rest_native_mcp_cli(
    tool, prefix, body, inputs, rest, tmp_path, capsys
):
    spec = SPECS[tool]
    original = {
        **inputs,
        prefix + "year": 2024,
        prefix + "month": 6,
        prefix + "day": 1,
        prefix + "hour": 14,
        prefix + "minute": 30,
    }
    julian = {
        **original,
        prefix + "month": 5,
        prefix + "day": 19,
        prefix + "calendar": "julian",
    }
    fields = list(evidence_views(spec)["calendar_input"]["fields"]) + (
        [
            "horary.ascendant.longitude",
            "horary.planets.Sun.longitude",
            "horary.moon.sign",
            "horary.verdict",
        ]
        if tool == "astro_horary"
        else [
            "election.axes",
            "election.moon.longitude",
            "election.score",
            "election.verdict",
        ]
    )
    params = [("fields", f) for f in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", 0),
    ]
    reference = rest.post(spec.rest_path, json=original, params=params)
    http = rest.post(spec.rest_path, json=julian, params=params)
    code, cli = call_cli(
        spec,
        julian,
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
            spec, julian, fields=fields, strict_fields=True, include_snapshot_text=False
        )
    )
    assert reference.status_code == http.status_code == 200, http.text
    assert code == 0 and not protocol.is_error
    results = [http.json(), cli, protocol.structured_content]
    assert business(results[0]) == business(results[1]) == business(results[2])
    assert reference.json()[body] == results[0][body]
    assert {
        k: v
        for k, v in reference.json()["analysis_context"].items()
        if k not in {"input_calendar", "input_date"}
    } == {
        k: v
        for k, v in results[0]["analysis_context"].items()
        if k not in {"input_calendar", "input_date"}
    }
    for value in results:
        spec.output_model.model_validate(value)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(value)
        c = value["calendar_conversion"]
        assert c["input_calendar"] == "julian"
        assert c["input_date"] == {"year": 2024, "month": 5, "day": 19}
        assert c["normalized_local_datetime"] == "2024-06-01T14:30:00"
        assert c["same_label_gregorian_offset_days"] == 13
        assert c["automatic_regional_reform_applied"] is False
        assert c["historical_clock_reconstruction_performed"] is False
        assert value[body]["calculation_basis"]["calendar"] == "proleptic_gregorian"
        assert (
            value["analysis_context"][prefix.rstrip("_") + "_datetime"]
            == c["normalized_local_datetime"]
        )
    c = reference.json()["calendar_conversion"]
    assert c["input_calendar"] == "proleptic_gregorian"
    assert c["calendar_conversion_performed"] is False


@pytest.mark.parametrize(
    "tool,prefix,inputs",
    [
        ("astro_horary", "question_", QUESTION),
        ("astro_election", "candidate_", CANDIDATE),
    ],
)
@pytest.mark.parametrize(
    "calendar,year,month,day",
    [
        ("julian", 1700, 2, 30),
        ("proleptic_gregorian", 1700, 2, 29),
        ("auto", 1582, 10, 4),
        ("julian", 1, 1, 1),
    ],
)
def test_calendar_faults_are_rejected_consistently_before_calculation(
    tool, prefix, inputs, calendar, year, month, day, surface_calls
):
    spec = SPECS[tool]
    payload = {
        **inputs,
        prefix + "calendar": calendar,
        prefix + "year": year,
        prefix + "month": month,
        prefix + "day": day,
    }
    http, protocol, code, cli = surface_calls(spec, payload)
    assert http.status_code == 422 and code != 0 and protocol.is_error
    assert "calendar_conversion" not in cli


@pytest.mark.parametrize("key", ["astro_horary", "astro_election"])
@pytest.mark.parametrize("house", ["R", "E", "N"])
@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
def test_unresolved_physical_reference_is_not_a_confirmed_fact_on_any_adapter(
    key, house, zodiac, tmp_path, surface_calls
):
    prefix = "question" if key == "astro_horary" else "candidate"
    root = "horary" if key == "astro_horary" else "election"
    payload = {
        f"{prefix}_year": 2000,
        f"{prefix}_month": 1,
        f"{prefix}_day": 1,
        f"{prefix}_hour": 12,
        "name": "Synthetic reference-geometry engineering fixture",
        "timezone_name": "UTC",
        "longitude": -10.458556062519506,
        "latitude": 66.56232328397007,
        "house_system": house,
        "zodiac_type": zodiac,
    }
    spec = SPECS[key]
    # Full JSON validates all nested facts, not a stubbed domain calculation.
    http, protocol, code, cli = surface_calls(
        spec,
        payload,
        params={"response_char_limit": 0},
        flags=["--response-char-limit", "0"],
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    values = [http.json(), cli, json.loads(protocol.content[0].text)]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for index, value in enumerate(values):
        spec.output_model.model_validate(value)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(value)
        facts = value[root]
        assert facts["ascendant"]["longitude"] is None
        assert facts["reference_geometry"]["ascendant_resolved"] is False
        assert (
            facts["calculation_basis"]["angle_definition"][
                "geometric_ascendant_resolved"
            ]
            is False
        )
        assert facts["backend_convention"]["ascendant"]["longitude"] is not None
        if root == "horary":
            assert facts["fortune"]["longitude"] is None
            assert facts["significators"]["querent"] is None
            assert facts["perfection"]["event_history"]["status"] == "computed"
            assert facts["rule_profile"]["full_original_text_acceptance"] is False
        else:
            assert facts["score"] is None and facts["score_bounds"] is not None
            assert facts["axes"]["midheaven_longitude"] is not None
            assert "非概率区间" in value["summary"]
        (tmp_path / f"{root}-{index}.json").write_text(json.dumps(value))
