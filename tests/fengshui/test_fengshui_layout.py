"""General layout calculation regressions: dates, scopes, stars and alternatives."""

import asyncio
import json
from datetime import timedelta
from pathlib import Path

import pytest
from fastmcp import Client
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.cli import run
from fatebridge.core.fengshui.calendar import lichun
from fatebridge.core.fengshui.layout import element_relationships
from fatebridge.core.fengshui.models import AssessRequest, BazhaiRequest, MingguaRequest
from fatebridge.core.fengshui.output import FengshuiOutput
from fatebridge.services.fengshui import assess as _assess
from fatebridge.services.fengshui import calculate_bazhai as _calculate_bazhai
from fatebridge.services.fengshui import calculate_minggua as _calculate_minggua
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.fengshui import payload
from tests.support.mcp_result_assertions import (
    same_run_projected_response,
    without_transport,
)
from tests.support.transports import call_calculation, rest_client
from tests.unit_test.fixtures.fengshui_layout import (
    facing_only,
)


def assess(**kwargs):
    return _assess(AssessRequest.model_validate(kwargs))


def calculate_bazhai(**kwargs):
    return _calculate_bazhai(BazhaiRequest.model_validate(kwargs))


def calculate_minggua(**kwargs):
    return _calculate_minggua(MingguaRequest.model_validate(kwargs))


def test_nonboundary_date_needs_no_hour_and_preserves_minggua() -> None:
    actual = calculate_minggua(birth_date="2000-12-10", gender_convention="male")
    reference = calculate_minggua(effective_birth_year=2000, gender_convention="male")
    assert actual["status"] == "complete"
    assert (
        actual["layers"]["minggua"]["candidates"]
        == reference["layers"]["minggua"]["candidates"]
    )
    time = actual["layers"]["minggua"]["time_context"]
    assert time["input_basis"] == "civil_date_no_fabricated_birth_hour"
    assert "local_moment" not in time


@pytest.mark.parametrize(
    "element,generator,drain,controller,controlled",
    [
        ("木", "水", "火", "金", "土"),
        ("火", "木", "土", "水", "金"),
        ("土", "火", "金", "木", "水"),
        ("金", "土", "水", "火", "木"),
        ("水", "金", "木", "土", "火"),
    ],
)
def test_independent_five_element_relation_table(
    element: str, generator: str, drain: str, controller: str, controlled: str
) -> None:
    assert element_relationships(element) == {
        "same_element": element,
        "generating_element": generator,
        "draining_element": drain,
        "controlling_element": controller,
        "controlled_element": controlled,
    }


def test_boundary_date_keeps_uncertainty_and_timezone() -> None:
    for zone in ["Asia/Shanghai", "UTC", "America/New_York"]:
        day = lichun(2026, zone).date()
        for offset, year in [(-1, 2025), (1, 2026)]:
            actual = calculate_minggua(
                birth_date=(day + timedelta(days=offset)),
                gender_convention="male",
                timezone_name=zone,
            )
            assert actual["layers"]["minggua"]["time_context"]["effective_year"] == year
        actual = calculate_minggua(
            birth_date=day, gender_convention="male", timezone_name=zone
        )
        assert (
            actual["status"] == "partial"
            and actual["layers"]["minggua"]["candidates"] == []
        )
        assert actual["layers"]["minggua"]["missing_inputs"] == [
            "occupants.occupant.birth_at_on_year_boundary"
        ]
    civil = calculate_minggua(
        birth_date="2026-01-01", gender_convention="male", year_boundary="january_1"
    )
    assert civil["status"] == "complete"


def test_january_minggua_distinguishes_unspecified_local_clock_from_date() -> None:
    zone = "Antarctica/Vostok"
    instant = calculate_minggua(
        birth_at="1994-07-01T13:00:00+01:00",
        timezone_name=zone,
        year_boundary="january_1",
        gender_convention="male",
    )["layers"]["minggua"]
    time = instant["time_context"]
    assert time["effective_year"] is None
    assert time["effective_year_status"] == "requires_confirmation"
    assert time["local_moment"] is None
    assert time["local_clock_status"] == "undefined"
    assert time["utc_moment"] == "1994-07-01T12:00:00Z"
    assert time["valid_from"] is None and time["valid_until"] is None
    assert instant["status"] == "partial" and instant["candidates"] == []
    assert instant["missing_inputs"] == [
        "occupants.occupant.confirmed_effective_birth_year_due_to_undefined_local_clock"
    ]

    for birth in ({"birth_date": "1994-07-01"}, {"effective_birth_year": 1994}):
        explicit = calculate_minggua(
            **birth,
            timezone_name=zone,
            year_boundary="january_1",
            gender_convention="male",
        )["layers"]["minggua"]
        assert explicit["status"] == "complete"
        assert explicit["time_context"]["effective_year"] == 1994
        assert "local_moment" not in explicit["time_context"]
        assert explicit["candidates"][0]["palace_number"] == 6


@pytest.mark.parametrize(
    ("zone", "birth_at", "year", "valid_from", "valid_until"),
    [
        (
            "Antarctica/Davis",
            "1964-07-01T12:00:00Z",
            1964,
            "1964-01-01T00:00:00+07:00",
            None,
        ),
        (
            "Antarctica/Davis",
            "1969-07-01T12:00:00Z",
            1969,
            None,
            "1970-01-01T00:00:00+07:00",
        ),
        (
            "Antarctica/Vostok",
            "1957-12-20T12:00:00Z",
            1957,
            None,
            "1958-01-01T00:00:00+07:00",
        ),
        (
            "Antarctica/Vostok",
            "1994-11-02T05:00:00Z",
            1994,
            "1994-01-01T00:00:00+07:00",
            "1995-01-01T00:00:00+07:00",
        ),
    ],
)
def test_january_minggua_keeps_known_year_with_unspecified_interval_endpoint(
    zone: str, birth_at: str, year: int, valid_from: str | None, valid_until: str | None
) -> None:
    person = calculate_minggua(
        birth_at=birth_at,
        timezone_name=zone,
        year_boundary="january_1",
        gender_convention="female",
    )["layers"]["minggua"]
    time = person["time_context"]
    assert person["status"] == "complete" and len(person["candidates"]) == 1
    assert person["missing_inputs"] == []
    assert time["effective_year"] == year
    assert time["valid_from"] == valid_from
    assert time["valid_until"] == valid_until
    assert time["interval_policy"] == "start_inclusive_end_exclusive"


@pytest.mark.parametrize(
    ("zone", "birth_at", "year", "valid_from", "valid_until"),
    [
        (
            "America/Phoenix",
            "1944-01-01T06:00:00Z",
            1944,
            "1944-01-01T00:00:00-06:00",
            "1943-12-31T23:01:00-07:00",
        ),
        (
            "America/Phoenix",
            "1944-01-01T06:01:00Z",
            1943,
            "1943-12-31T23:01:00-07:00",
            "1944-01-01T00:00:00-07:00",
        ),
        (
            "America/Phoenix",
            "1944-01-01T07:00:00Z",
            1944,
            "1944-01-01T00:00:00-07:00",
            "1945-01-01T00:00:00-07:00",
        ),
        (
            "Asia/Kathmandu",
            "1985-12-31T18:29:59Z",
            1985,
            "1985-01-01T00:00:00+05:30",
            "1986-01-01T00:15:00+05:45",
        ),
        (
            "Asia/Kathmandu",
            "1985-12-31T18:30:00Z",
            1986,
            "1986-01-01T00:15:00+05:45",
            "1987-01-01T00:00:00+05:45",
        ),
    ],
)
def test_january_minggua_uses_actual_query_interval_across_clock_changes(
    zone: str, birth_at: str, year: int, valid_from: str, valid_until: str
) -> None:
    person = calculate_minggua(
        birth_at=birth_at,
        timezone_name=zone,
        year_boundary="january_1",
        gender_convention="female",
    )["layers"]["minggua"]
    time = person["time_context"]
    assert person["status"] == "complete"
    assert time["effective_year"] == year
    assert time["valid_from"] == valid_from
    assert time["valid_until"] == valid_until
    assert time["interval_policy"] == "start_inclusive_end_exclusive"


def test_lichun_minggua_date_waits_for_confirmed_year_if_boundary_has_no_local_date() -> (
    None
):
    query = {"birth_date": "1994-02-03", "gender_convention": "male"}
    closed = calculate_minggua(**query, timezone_name="Antarctica/Vostok")["layers"][
        "minggua"
    ]
    utc = calculate_minggua(**query, timezone_name="UTC")["layers"]["minggua"]
    time = closed["time_context"]
    boundary = time["boundary_resolution"]
    assert boundary["local_clock_status"] == "undefined"
    assert (
        boundary["civil_point"]
        == utc["time_context"]["boundary_resolution"]["civil_point"]
    )
    assert time["birth_date"] == "1994-02-03"
    assert "local_moment" not in time and "utc_moment" not in time
    assert time["effective_year"] is None
    assert time["effective_year_status"] == "requires_confirmation"
    assert closed["status"] == "partial" and closed["candidates"] == []
    assert closed["missing_inputs"] == [
        "occupants.occupant.confirmed_effective_birth_year_due_to_undefined_local_clock"
    ]
    assert utc["status"] == "complete"
    assert utc["time_context"]["effective_year"] == 1993
    assert utc["candidates"][0]["palace_number"] == 7


@pytest.mark.parametrize(
    "extra",
    [
        {"birth_date": "2000-02-30"},
        {"birth_date": "1700-12-10"},
        {"birth_date": "2000-12-10", "effective_birth_year": 2000},
        {"birth_date": "2000-12-10", "birth_at": "2000-12-10T09:55:00+08:00"},
    ],
)
def test_birth_date_validation(extra) -> None:
    with pytest.raises(ValidationError):
        MingguaRequest.model_validate(extra)


def test_facing_only_is_computed_without_invented_location() -> None:
    actual = assess(**facing_only())
    assert actual["status"] == actual["layout_analysis"]["status"] == "partial"
    assert (
        "placements.table.location_direction"
        in actual["layout_analysis"]["missing_inputs"]
    )
    findings = actual["layout_analysis"]["placement_findings"]
    assert len(findings) == 1
    assert findings[0]["aspect"] == "facing" and findings[0]["star"]["name"] == "五鬼"
    options = actual["layout_analysis"]["adjustment_options"][0]
    assert options["agreed_matching_directions"] == ["N", "E", "SE", "S"]
    assert options["scopes"][0]["matches_convention"] is False
    elem = actual["layout_analysis"]["element_relationships"][0]
    assert (
        elem["star_element"],
        elem["draining_element"],
        elem["controlling_element"],
    ) == ("火", "土", "水")
    assert elem["application_scope"] == "element_relation_only_not_object_prescription"


def test_no_house_or_hour_is_required_to_return_existing_personal_finding() -> None:
    req = facing_only()
    req.pop("methods")
    req.pop("analyze_layout")
    actual = calculate_bazhai(**req)
    assert actual["layers"]["bazhai"]["placement_findings"][0]["direction"] == "W"
    assert actual["status"] == "partial"
    with pytest.raises(ValidationError):
        BazhaiRequest(placements=[{"object_id": "empty", "purpose": "desk"}])


def test_location_and_facing_options_obey_stove_rules_independently() -> None:
    req = payload("assess")
    req["analyze_layout"] = True
    actual = assess(**req)
    options = [
        o
        for o in actual["layout_analysis"]["adjustment_options"]
        if o["object_id"] == "stove"
    ]
    location, facing = options
    # 1990 male 坎: stove seat uses the four inauspicious sectors; fire mouth uses auspicious.
    personal_location = next(
        s for s in location["scopes"] if s["subject_kind"] == "occupant"
    )
    personal_facing = next(
        s for s in facing["scopes"] if s["subject_kind"] == "occupant"
    )
    assert personal_location["matching_directions"] == ["NE", "SW", "W", "NW"]
    assert personal_facing["matching_directions"] == ["N", "E", "SE", "S"]
    assert set(location["agreed_matching_directions"]).isdisjoint(
        facing["agreed_matching_directions"]
    )


def test_unknown_personal_convention_does_not_create_confirmed_consensus() -> None:
    req = facing_only()
    req["occupants"][0].pop("gender_convention")
    actual = assess(**req)["layout_analysis"]["adjustment_options"][0]
    assert len(actual["scopes"]) == 2
    assert all(s["candidate_only"] for s in actual["scopes"])
    assert actual["agreed_matching_directions"] == []
    assert actual["resolution"] == "no_confirmed_scope"


def test_house_and_person_disagreement_has_no_single_best_direction() -> None:
    req = facing_only()
    req["house"] = {"sitting_trigram": "乾"}
    actual = assess(**req)["layout_analysis"]["adjustment_options"][0]
    assert len(actual["scopes"]) == 2
    assert actual["agreed_matching_directions"] == []
    assert actual["resolution"] == "confirmed_scopes_intersection"
    assert {s["subject_kind"] for s in actual["scopes"]} == {"house", "occupant"}


@pytest.mark.parametrize(
    "purpose,role",
    [
        ("desk", "desk_facing"),
        ("bed", "headboard"),
        ("door", "door_facing"),
        ("stove", "fire_mouth"),
    ],
)
def test_annual_location_is_independent_of_facing_and_object_purpose(
    purpose: str, role: str
) -> None:
    inputs = {
        "methods": ["annual_stars"],
        "effective_year": 2026,
        "analyze_layout": True,
        "placements": [
            {
                "object_id": "x",
                "purpose": purpose,
                "location_direction": "S",
                "facing_direction": "W",
                "facing_role": role,
            }
        ],
    }
    a = assess(**inputs)["layout_analysis"]
    inputs["placements"][0]["facing_direction"] = "E"
    b = assess(**inputs)["layout_analysis"]
    af = a["placement_findings"][0]
    assert af == b["placement_findings"][0]
    assert af["annual_star_number"] == 5 and af["direction"] == "S"
    assert af["aspect"] == "location"
    elements = a["element_relationships"][0]
    assert (
        elements["star_element"],
        elements["draining_element"],
        elements["controlling_element"],
    ) == ("土", "金", "木")


def test_no_location_does_not_project_facing_into_annual_palace() -> None:
    req = facing_only()
    req["methods"] = ["annual_stars"]
    req["effective_year"] = 2026
    actual = assess(**req)
    assert actual["status"] == "complete"  # requested raw annual chart is complete
    assert actual["layout_analysis"]["status"] == "partial"  # layout lookup is not
    assert actual["layout_analysis"]["placement_findings"] == []
    assert actual["layout_analysis"]["element_relationships"] == []


def test_natal_candidates_and_three_roles_are_not_collapsed() -> None:
    inputs = {
        "methods": ["xuankong_natal"],
        "analyze_layout": True,
        "xuankong": payload("xuankong_natal"),
        "placements": [
            {"object_id": "bed", "purpose": "bed", "location_direction": "E"}
        ],
    }
    inputs["xuankong"]["house"]["facing_degrees"] = 355.5
    actual = assess(**inputs)
    candidates = actual["layers"]["xuankong_natal"]["candidates"]
    findings = actual["layout_analysis"]["placement_findings"]
    assert len(findings) == len(candidates) > 1
    for c, f in zip(candidates, findings):
        assert f["candidate_id"] == c["candidate_id"] and f["candidate_only"]
        assert f["palace"] == c["palaces"]["E"]
    assert len(actual["layout_analysis"]["element_relationships"]) == 3 * len(
        candidates
    )
    assert {
        e["star_role"] for e in actual["layout_analysis"]["element_relationships"]
    } == {"period", "mountain", "facing"}


def test_unknown_sand_water_produces_no_adjustment_prescription() -> None:
    inputs = payload("assess")
    inputs["analyze_layout"] = True
    inputs["features"][0]["classification"] = "unknown"
    actual = assess(**inputs)["layout_analysis"]["environment_adjustments"]
    assert actual[0]["adjustment"] == "needs_confirmed_classification"
    assert actual[0]["target_classification"] is None
    inputs["features"][0]["classification"] = "sand"
    actual = assess(**inputs)["layout_analysis"]["environment_adjustments"]
    assert actual[0]["target_classification"] == "water"
    assert (
        actual[0]["application_scope"]
        == "confirmed_environment_classification_not_small_object_substitution"
    )


def test_opt_in_analysis_preserves_existing_calculation_values() -> None:
    inputs = payload("assess")
    base = assess(**inputs)
    extended = assess(**{**inputs, "analyze_layout": True})
    assert extended["layers"] == base["layers"]
    assert extended["conflicts"] == base["conflicts"]
    assert "layout_analysis" not in base
    FengshuiOutput.model_validate(extended)


@pytest.mark.parametrize(
    "inputs",
    [
        facing_only(),
        {**payload("assess"), "analyze_layout": True},
        {"methods": ["annual_stars"], "effective_year": 2026, "analyze_layout": True},
    ],
)
def test_extended_layout_matches_rest_mcp_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    inputs,
) -> None:
    from fatebridge.mcp_server import create_mcp_app

    async def call():
        async with Client(create_mcp_app()) as client:
            return await call_calculation(
                client,
                "fengshui_assess",
                {"detail": "audit", **inputs},
                raise_on_error=False,
            )

    rest = rest_client(monkeypatch).post(
        "/api/fengshui/assess", json=inputs, params={"detail": "audit"}
    )
    mcp = asyncio.run(call())
    request = tmp_path / "layout.json"
    request.write_text(json.dumps(inputs))
    assert (
        run(["fengshui_assess", "--request-file", str(request), "--detail", "audit"])
        == 0
    )
    cli = json.loads(capsys.readouterr().out)
    assert rest.status_code == 200 and not mcp.is_error
    assert (
        without_transport(rest.json())
        == without_transport(mcp.structured_content)
        == without_transport(cli)
    )
    schema = FengshuiOutput.model_json_schema()
    for result in [rest.json(), mcp.structured_content, cli]:
        Draft202012Validator(schema).validate(result)


def test_strict_projected_analysis_works_on_real_mcp() -> None:
    from fatebridge.mcp_server import create_mcp_app

    async def call():
        async with Client(create_mcp_app()) as client:
            response = await call_calculation(
                client,
                "fengshui_assess",
                {
                    **facing_only(),
                    "detail": "audit",
                    "fields": [
                        "layout_analysis.adjustment_options",
                        "layout_analysis.status",
                        "layout_analysis.unsupported_queries",
                    ],
                },
            )
            return response.structured_content

    result = asyncio.run(call())
    assert set(result) == {"layout_analysis", "run_metadata"}
    assert set(result["layout_analysis"]) == {
        "adjustment_options",
        "status",
        "unsupported_queries",
    }
    assert result["run_metadata"]["tool_name"] == "fengshui_assess"


def test_layout_uses_existing_tools_no_special_workspace_entry() -> None:
    names = {s.name for s in CATALOG if s.family == "fengshui"}
    assert names == {
        "fengshui_directions",
        "fengshui_minggua",
        "fengshui_bazhai",
        "fengshui_jinsuo",
        "fengshui_annual_stars",
        "fengshui_monthly_stars",
        "fengshui_xuankong_house_chart",
        "fengshui_assess",
    }
    assert "analyze_layout" in AssessRequest.model_fields
