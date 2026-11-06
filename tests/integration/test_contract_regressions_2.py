"""Related contract regressions with shared imports; original cases retained."""

import argparse
import asyncio
import copy
import json
from fractions import Fraction
from typing import Annotated, Optional, Union

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator
from mcp.types import CallToolResult
from pydantic import BaseModel, Field, StrictInt

import fatebridge.cli as cli
from fatebridge import api
from fatebridge.application import execution
from fatebridge.application.discovery import select_mcp_specs
from fatebridge.cli import run
from fatebridge.core import almanac, solar_term_clock
from fatebridge.core.astro import runtime
from fatebridge.diagnostics import diagnose
from fatebridge.mcp_server import _MCP_INSTRUCTIONS, create_mcp_app
from fatebridge.mcp_transport import protocol_result
from fatebridge.services.astrology import (
    calculate_core_chart_analysis,
    calculate_germany_chart_analysis,
)
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.validation.house_roles import audit_specialty_house_roles
from tests.evaluation.test_gauquelin_request_guard import HOUSE_SPECS, payload
from tests.support.transports import SPECS, native, rest, surface_calls
from tests.western.test_other_chart_angle_qualification import PAYLOAD


@pytest.mark.parametrize("field", ["lookup_mode", "selected_sections"])
def test_subject_null_nonnullable_field_is_rejected_on_three_protocols(
    field, surface_calls
):
    spec = SPECS["gua_lookup"]
    payload = {"query": "111111", field: None}
    http, protocol, code, cli = surface_calls(spec, payload, cli_first=False)
    assert http.status_code == 422 and protocol.is_error and code != 0
    assert http.json()["error_code"] == cli["error_code"] == "validation_error"
    assert field in str(cli["issues"])


def test_explicit_cli_flag_overrides_null_subject_value(tmp_path, capsys):
    subject = tmp_path / "null-lookup.json"
    subject.write_text(json.dumps({"query": "111111", "lookup_mode": None}))
    code = run(
        [
            "gua_lookup",
            "--subject-file",
            str(subject),
            "--lookup-mode",
            "hexagram",
            "--response-char-limit",
            "0",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert code == 0 and "error_code" not in output


def test_profile_keeps_explicit_null_instead_of_default_zero(tmp_path, capsys):
    subject = tmp_path / "null-minute.json"
    subject.write_text(
        json.dumps(
            dict(
                birth_year=1990,
                birth_month=1,
                birth_day=1,
                birth_hour=12,
                birth_minute=None,
                birth_timezone="UTC",
                use_true_solar_time=False,
            )
        )
    )
    code = run(
        [
            "profile",
            "--systems",
            "bazi",
            "--subject-file",
            str(subject),
            "--response-char-limit",
            "0",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert code != 0
    child = output["profile"]["bazi"]
    assert child["error_code"] == "validation_error"
    assert "birth_minute" in str(child["issues"])
    assert "bazi_birth" not in child


def test_omitted_optional_value_still_uses_declared_default(tmp_path, capsys):
    subject = tmp_path / "omitted-lookup.json"
    subject.write_text(json.dumps({"query": "111111"}))
    code = run(
        ["gua_lookup", "--subject-file", str(subject), "--response-char-limit", "0"]
    )
    output = json.loads(capsys.readouterr().out)
    assert code == 0 and "error_code" not in output


@pytest.mark.parametrize(
    "annotation",
    [
        Union[int, str],
        Optional[Union[int, str]],
        int | str,
        Annotated[Union[int, str], "example"],
    ],
)
def test_textual_union_branch_is_not_discarded(annotation):
    assert cli._argument_type(annotation) is str


def test_numeric_strictness_optional_and_list_items_still_reach_pydantic_as_integers():
    class Numeric(BaseModel):
        count: Optional[StrictInt] = None
        items: list[Annotated[int, Field(ge=0)]]

    parser = argparse.ArgumentParser()
    for name, field in Numeric.model_fields.items():
        cli._add_field_argument(parser, name, field)
    namespace = parser.parse_args(["--count", "3", "--items", "0", "2"])
    result = Numeric.model_validate(vars(namespace))
    assert result.count == 3 and result.items == [0, 2]
    assert type(namespace.count) is int


@pytest.mark.parametrize(
    "value,expected", [("P", "P"), ("R", "R"), ("X", "X"), ("3", "P"), ("8", "D")]
)
def test_supported_house_flags_on_every_live_tool_reach_the_shared_dispatch(
    value, expected, monkeypatch, tmp_path, capsys
):
    from fatebridge.utils.house_systems import normalize_house_system

    captured = []

    def stop_at_dispatch(spec, request, *args, **kwargs):
        captured.append((spec.key, request.house_system))
        return {
            "error": "test_dispatch_spy",
            "error_code": "test_dispatch_spy",
            "retryable": False,
        }

    monkeypatch.setattr(cli, "execute_tool", stop_at_dispatch)
    for spec in HOUSE_SPECS:
        subject = tmp_path / f"{spec.key}.json"
        subject.write_text(
            json.dumps({k: v for k, v in payload(spec).items() if k != "house_system"})
        )
        capsys.readouterr()
        code = cli.run(
            [spec.tool_name, "--subject-file", str(subject), "--house-system", value]
        )
        result = json.loads(capsys.readouterr().out)
        # This is a dispatch spy, never a fabricated successful calculation.
        assert code == 1 and result["error_code"] == "test_dispatch_spy", (
            spec.key,
            result,
        )
        assert captured[-1][0] == spec.key
        assert normalize_house_system(captured[-1][1]) == expected
    assert len(captured) == len(HOUSE_SPECS)


def test_documented_gauquelin_direct_flags_return_shared_validation_error(
    monkeypatch, capsys
):
    def forbidden(*args, **kwargs):
        raise AssertionError("invalid direct flags reached calculation")

    monkeypatch.setattr(cli, "execute_tool", forbidden)
    code = cli.run(
        [
            "astro_horary",
            "--question-year",
            "2000",
            "--question-month",
            "1",
            "--question-day",
            "1",
            "--question-hour",
            "12",
            "--timezone-name",
            "UTC",
            "--longitude",
            "0",
            "--latitude",
            "0",
            "--house-system",
            "G",
        ]
    )
    body = json.loads(capsys.readouterr().out)
    assert code == 1 and body["error_code"] == "validation_error"
    assert body["issues"][0] == {
        "path": "house_system",
        "code": "unsupported_house_system",
    }


@pytest.mark.parametrize("include_metadata", [False, True])
@pytest.mark.parametrize("typed_source", [False, True])
def test_dispatch_preserves_source_failure_and_plain_input_error_semantics(
    monkeypatch, include_metadata, typed_source
):
    spec = next(s for s in CATALOG if s.key == "fengshui_xuankong_natal")
    request = spec.request_model.model_validate(
        {
            "house": {"facing_degrees": 180, "north_reference": "magnetic"},
            "period": {
                "basis": "construction_completion",
                "effective_event_year": 1800,
                "evidence": "Synthetic dispatcher test",
            },
        }
    )

    def failed(*args):
        if typed_source:
            raise EphemerisSourceError("solar_de440_invalid")
        raise ValueError("private raw input details must not be echoed")

    monkeypatch.setattr(execution, "execute_spec", failed)
    result = execution.execute_tool(spec, request, include_metadata=include_metadata)
    assert "run_metadata" not in result
    assert "private raw input" not in str(result)
    assert result["retryable"] is False
    if typed_source:
        assert result["error_code"] == "ephemeris_source_inconsistent"
        assert result["status_code"] == 503
        assert result["issues"] == [
            {"path": "runtime.ephemeris_data", "code": "solar_de440_invalid"}
        ]
    else:
        assert result["error_code"] == "validation_error"


def test_default_profile_preserves_every_published_tool():
    assert {s.tool_name for s in select_mcp_specs(CATALOG)} == {
        s.tool_name for s in CATALOG if s.mcp_name
    }


def test_profile_doctor_matches_real_child_and_registration_environment():
    result = diagnose(mcp=True, family="bazi")
    assert result["ok"], result
    assert result["mcp_tool_count"] == result["mcp"]["tool_count"]
    assert result["codex"]["config"]["env"] == {"FATEBRIDGE_MCP_FAMILIES": "bazi"}


def test_all_published_parameters_explain_their_role():
    async def run():
        async with Client(create_mcp_app()) as client:
            for tool in await client.list_tools():
                schema = tool.model_dump(by_alias=True)["inputSchema"]
                for name, field in schema["properties"].items():
                    assert field.get("description"), (tool.name, name)

    asyncio.run(run())
    # Project budget for a self-contained server introduction, per OpenAI guidance.
    assert len(_MCP_INSTRUCTIONS) <= 512


@pytest.mark.parametrize(
    "payload,failed",
    [
        ({"layers": {"directions": {"ruleset": {"version": "1.0.0"}}}}, False),
        (
            {
                "error": "请求参数无效",
                "error_code": "validation_error",
                "retryable": False,
                "issues": [{"path": "fields", "code": "unknown_projection_path"}],
            },
            True,
        ),
    ],
)
def test_native_result_preserves_sdk_independent_wire_contract(payload, failed):
    result = protocol_result(payload, failed=failed)
    assert result.is_error is failed
    converted = result.to_mcp_result()
    if failed:
        assert isinstance(converted, CallToolResult)
        wire = converted.model_dump(mode="json", by_alias=True, exclude_none=True)
    else:
        content, structured = converted
        wire = {
            "content": [item.model_dump(mode="json") for item in content],
            "structuredContent": structured,
            "isError": False,
        }
    assert wire["structuredContent"] == payload
    assert wire["isError"] is failed
    assert "structured_content" not in wire and "is_error" not in wire
    assert json.loads(wire["content"][0]["text"]) == payload


@pytest.mark.parametrize(
    "key,variant", [("astro_germany", None), ("astro_chart", "germany")]
)
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_mixed_pair_catalogue_across_three_surfaces(
    monkeypatch, capsys, tmp_path, key, variant, zodiacal
):
    spec = next(s for s in CATALOG if s.key == key)
    payload = {
        "name": "虚构：交错因素接口验收",
        "birth_year": 2000,
        "birth_month": 1,
        "birth_day": 1,
        "birth_hour": 4,
        "birth_minute": 30,
        "birth_timezone": "UTC",
        "birth_longitude": 0.0,
        "birth_latitude": 0.0,
        "zodiacal": zodiacal,
        "analysis_datetime": "2000-02-01T00:00:00Z",
    }
    if variant:
        payload["chart_variant"] = variant
    fields = [
        "midpoint_analysis.factors",
        "midpoint_analysis.solar_arc_analysis.profile",
        "midpoint_analysis.solar_arc_analysis.mixed_pair_geometry",
    ]
    as_of = "2026-01-01T00:00:00Z"
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    response = TestClient(api.app).post(
        spec.rest_path,
        json=payload,
        params=[
            ("as_of", as_of),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )

    async def native():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                spec.tool_name,
                {
                    **payload,
                    "as_of": as_of,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
                raise_on_error=False,
            )

    protocol = asyncio.run(native())
    request_file = tmp_path / "request.json"
    request_file.write_text(json.dumps(payload))
    capsys.readouterr()
    code = run(
        [
            spec.tool_name,
            "--subject-file",
            str(request_file),
            "--as-of",
            as_of,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
            "--fields",
            *fields,
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200, response.text
    assert not protocol.is_error, protocol.content
    assert code == 0, cli
    assert protocol.structured_content == json.loads(protocol.content[0].text)
    bodies = []
    for label, body in [
        ("rest", response.json()),
        ("mcp", protocol.structured_content),
        ("cli", cli),
    ]:
        (tmp_path / (label + ".json")).write_text(
            json.dumps(body, sort_keys=True, ensure_ascii=False, allow_nan=False)
        )
        Draft202012Validator(spec.output_model.model_json_schema()).validate(body)
        bodies.append({k: v for k, v in body.items() if k != "run_metadata"})
    assert bodies[0] == bodies[1] == bodies[2]
    layer = bodies[0]["midpoint_analysis"]
    values = {f["id"]: Fraction(f["longitude"]) for f in layer["factors"]}
    direction = layer["solar_arc_analysis"]
    arc = Fraction(direction["profile"]["solar_arc_degrees"])
    mixed = direction["mixed_pair_geometry"]
    assert mixed["profile"]["factor_count"] == len(values) == 22
    assert (
        mixed["profile"]["birth_time_contact_sensitivity"]
        == "not_assessed_for_this_catalogue"
    )
    assert mixed["real_world_efficacy"] == "not_tested"
    for period in (90, 45):
        dial = mixed["dials"][str(period)]
        assert dial["arc_dependent_contacts"] and dial["arc_invariant_contacts"]
        for field in ("arc_dependent_contacts", "arc_invariant_contacts"):
            for row in dial[field]:
                a, b, c, d = [row[k] for k in ("id_a", "id_b", "id_c", "id_d")]
                assert len({a, b, c, d}) == 4
                assert row["arc_invariant"] == (field == "arc_invariant_contacts")
                for assignment in row["factor_layer_assignments"]:
                    x = {
                        n: values[n] + (arc if l == "solar_arc" else 0)
                        for n, l in assignment.items()
                    }
                    delta = (
                        (x[a] + x[b] - x[c] - x[d]) / 2 + Fraction(period, 2)
                    ) % period - Fraction(period, 2)
                    assert abs(delta) <= 1
                    assert float(delta) == row["signed_orb"]


@pytest.mark.parametrize(
    "year,method,historical,future",
    [
        (1700, "pre_1972_swiss_UT1_delta_t", True, False),
        (1965, "IERS_1961_1971_UTC_drift_to_TT_swiss_delta_t_to_UT1", False, False),
        (1972, "IERS_UTC_to_TT_swiss_delta_t_to_UT1", False, False),
        (2000, "IERS_UTC_to_TT_swiss_delta_t_to_UT1", False, False),
        (2300, "IERS_UTC_to_TT_swiss_delta_t_to_UT1", False, True),
    ],
)
def test_actual_native_calendar_carries_each_clock_policy(
    year, method, historical, future, monkeypatch, tmp_path
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    terms = almanac.get_solar_terms_for_year(year, "UTC")
    assert len(terms) == 24
    for term in terms:
        details = term.as_dict()["solar_model_details"]
        # Native file fallback now solves the named complete revision, not
        # the stock Swiss Sun. Its identity must not borrow native Sun flags.
        assert term.resolution_provider == "fatebridge_moshier"
        assert (
            term.ephemeris_model
            == details["model_id"]
            == details["ephemeris_model"]
            == "fatebridge_complete_moshier_solar_v1"
        )
        assert term.ephemeris_retflags == ()
        assert "ephemeris_retflags" not in details
        assert details["native_moshier_relabelled"] is False
        assert details["civil_time_policy"] == method
        assert details["historical_ut1_convention"] is historical
        assert details["future_leap_seconds_assumed_unchanged"] is future
        assert details["accuracy_certified"] is False
        assert details["root_time_scale"] == "TT"
        assert details["civil_time_method"] == "datetime_from_tt_point"
        assert details["numerical_resolution_is_physical_accuracy"] is False


@pytest.mark.parametrize(
    "error,reason",
    [
        (ValueError("private-policy"), "solar_root_civil_unrepresentable"),
        (ImportError("private-clock"), "solar_root_clock_unavailable"),
    ],
)
def test_policy_failure_on_selected_root_cannot_become_linear(
    error, reason, monkeypatch, tmp_path
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)

    def fail(*args):
        raise error

    monkeypatch.setattr(solar_term_clock, "ephemeris_time", fail)
    with pytest.raises(solar_term_clock.SolarTermClockError) as caught:
        almanac.get_solar_terms_for_year(2000, "UTC")
    assert caught.value.reason == reason
    assert "private" not in str(caught.value.as_result())


def test_original_policy_source_error_is_preserved(monkeypatch):
    error = EphemerisSourceError("solar_spk_changed")

    def fail(*args):
        raise error

    monkeypatch.setattr(solar_term_clock, "ephemeris_time", fail)
    from datetime import datetime, timezone

    with pytest.raises(EphemerisSourceError) as caught:
        solar_term_clock.native_solar_root_time_policy(
            datetime(2000, 1, 1, tzinfo=timezone.utc)
        )
    assert caught.value is error


@pytest.mark.parametrize(
    "place,timezone,longitude",
    [
        ("江苏省宿迁市宿豫区", "Asia/Shanghai", 118.32),
        ("Paris, France", "Europe/Paris", 2.35),
        ("悉尼, 澳大利亚", "Australia/Sydney", 151.21),
        ("Coyhaique, Chile", "America/Coyhaique", -72.07),
    ],
)
@pytest.mark.parametrize("key", ["bazi_birth", "astro_chart"])
def test_place_only_input_infers_the_same_point_on_all_surfaces(
    key, place, timezone, longitude, surface_calls
):
    spec = SPECS[key]
    payload = dict(
        birth_year=2000,
        birth_month=7,
        birth_day=1,
        birth_hour=12,
        birth_minute=10,
        birth_place=place,
        gender="男",
        use_true_solar_time=True,
    )
    response, protocol, code, local = surface_calls(
        spec, payload, flags=["--response-char-limit", "0"]
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    points = []
    for result in [response.json(), local, protocol.structured_content]:
        info = (
            result["bazi_birth"]["person_info"]
            if key == "bazi_birth"
            else result["person_info"]
        )
        if key == "bazi_birth":
            point = info["time_adjustment"]
            points.append((point["timezone"], point["longitude"]))
        else:
            points.append((info["birth_timezone"], info["birth_longitude"]))
    assert points[0] == points[1] == points[2]
    assert points[0][0] == timezone
    assert points[0][1] == pytest.approx(longitude, abs=0.1)


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
@pytest.mark.parametrize("kind", ["germany", "chart13"])
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_actual_native_calls_separate_selected_houses_reference_angles_and_partition(
    monkeypatch, kind, zodiacal
):
    original = runtime.ephemeris_call
    calls = []

    def observed(name, *args, **kwargs):
        result = original(name, *args, **kwargs)
        if name == "houses_ex":
            calls.append((args, result))
        return result

    monkeypatch.setattr(runtime, "ephemeris_call", observed)
    request = {
        **PAYLOAD,
        "birth_longitude": 10.0,
        "birth_latitude": 20.0,
        "zodiacal": zodiacal,
    }
    payload = (
        calculate_germany_chart_analysis(**request)
        if kind == "germany"
        else calculate_core_chart_analysis(**request, chart_variant="chart13")
    )
    assert "error" not in payload, payload
    base = payload.get("base_chart", payload)
    profile = base["chart_profile"]
    assert profile["house_system"] == "alcabitus"
    assert profile["house_system_code"] == 1
    assert profile["house_system_label_zh"] == "Alcabitus"
    base_calls = [(args, result) for args, result in calls if args[3] == b"B"]
    assert base_calls, "The recorded Alcabitus label must have a real B call"
    assert [row["cusp_longitude"] for row in base["houses"]] == list(
        base_calls[0][1][0]
    )
    native = payload.get("midpoint_analysis", payload)
    models = [
        row["reference_angle_model"] for row in native["time_sensitivity"]["samples"]
    ]
    if kind == "germany":
        models.append(native["profile"]["reference_angle_model"])
        assert native["meridian_houses"]["profile"]["house_code"] == "X"
        assert any(args[3] == b"X" for args, _ in calls)
    else:
        assert payload["sector_profile"]["ruleset_id"] == "fatebridge_equal13_v1"
    for model in models:
        assert model["house_code"] == "E"
        assert model["cusp_output_used"] is False
        assert model["role"] == "reference_angles_only"
        assert any(
            args[3] == b"E" and len(args) > 4 and args[4] == model["house_flags"]
            for args, _ in calls
        )
    roles = audit_specialty_house_roles(
        payload, requested_hsys=1, declared_base_house_system="Alcabitus"
    )
    assert roles["status"] == "consistent_recorded_roles", roles
    assert roles["base_house_system"]["swiss_house_code"] == "B"
    wrong = audit_specialty_house_roles(
        payload, requested_hsys=1, declared_base_house_system="Equal"
    )
    assert wrong["status"] == "mismatch"
    assert "declared_base_house_system_differs_from_recorded_base" in wrong["issues"]


def test_unrecorded_reference_model_is_not_inferred_from_the_house_label():
    payload = {
        "base_chart": {
            "chart_profile": {
                "house_system": "alcabitus",
                "house_system_code": 1,
                "house_system_label_zh": "Alcabitus",
            }
        },
        "midpoint_analysis": {
            "profile": {},
            "meridian_houses": {"profile": {"house_code": "X"}},
        },
    }
    roles = audit_specialty_house_roles(
        payload, requested_hsys=1, declared_base_house_system="Alcabitus"
    )
    assert roles["status"] == "partial"
    assert roles["native_reference_angle_model"] is None
    assert roles["missing_evidence"] == ["native_reference_angle_model"]
    altered = copy.deepcopy(payload)
    altered["base_chart"]["chart_profile"]["house_system_label_zh"] = "等宫制"
    assert audit_specialty_house_roles(altered)["status"] == "mismatch"


@pytest.mark.parametrize("code", [True, 1.0, -1, 9, "1"])
def test_invalid_requested_codes_do_not_become_partial_evidence(code):
    with pytest.raises(ValueError, match="integer0..8"):
        audit_specialty_house_roles({}, requested_hsys=code)


def test_a_house_label_alone_does_not_certify_unrecorded_specialty_roles():
    profile = {
        "house_system": "alcabitus",
        "house_system_code": 1,
        "house_system_label_zh": "Alcabitus",
    }
    audit = audit_specialty_house_roles({"chart_profile": profile}, requested_hsys=1)
    assert audit["status"] == "partial"
    assert "specialty_geometry_layer" in audit["missing_evidence"]
