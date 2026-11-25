"""Davison variants and both Marks charts agree over actual public transports."""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fatebridge.application.examples import evidence_views, suggested_fields
from tests.fixtures.surface_payloads import J2000_UNRESOLVED_ASC_SITE
from tests.support.relationship_inputs import relationship_payload
from tests.support.transports import (
    SPECS,
    business,
    cached_output_validator,
    call_cli,
    native,
    rest,
)


def test_marks_requires_only_the_selected_personal_charts(
    rest: TestClient, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    flat = relationship_payload("Marks", "spherical")
    flat.update(
        inner_birth_latitude=40,
        inner_birth_longitude=0,
        outer_birth_latitude=40,
        outer_birth_longitude=180,
        hsys=3,
        zodiacal=0,
    )
    spec = SPECS["astro_relative_chart"]
    response = rest.post(
        "/api/astrology/relationship-chart",
        json=flat,
        params={"response_char_limit": 0},
    )
    code, cli = call_cli(
        spec, flat, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    mcp = asyncio.run(native(spec, flat))
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    results = [response.json(), cli, mcp.structured_content]
    assert business(results[0]) == business(results[1]) == business(results[2])
    for result in results:
        assert result["chart"] == result["marks_charts"]["inner"]
        for role, longitude in (("inner", 0), ("outer", -180)):
            chart = result["marks_charts"][role]
            policy = chart["chart_profile"]["derivation_policy"]
            assert policy["midpoint_latitude"] == pytest.approx(65, rel=0, abs=1e-9)
            assert policy["midpoint_longitude"] == pytest.approx(
                longitude, rel=0, abs=1e-9
            )
            assert chart["chart_profile"]["house_system"] == "placidus"
            assert len(chart["houses"]) == 12 and chart["planets"]

    # note (houses): The common chart has separate Placidus admission from the personal Marks charts.
    flat["relative_mode"] = "TimeSpace"
    response = rest.post("/api/astrology/relationship-chart", json=flat)
    code, cli = call_cli(spec, flat, tmp_path, capsys)
    mcp = asyncio.run(native(spec, flat))
    assert response.status_code == 400 and code == 1 and mcp.is_error
    assert all(
        "placidus" in body["error"]
        for body in (response.json(), cli, mcp.structured_content)
    )


@pytest.mark.parametrize("mode", ["TimeSpace", "Marks"])
@pytest.mark.parametrize("variant", ["uncorrected", "corrected", "spherical"])
def test_relationship_variants_and_full_precision_match_all_transports(
    mode: str,
    variant: str,
    rest: TestClient,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    flat = relationship_payload(mode, variant)
    spec = SPECS["astro_relative_chart"]
    response = rest.post(
        "/api/astrology/relationship-chart",
        json=flat,
        params={"response_char_limit": 0},
    )
    code, cli = call_cli(
        spec, flat, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    mcp = asyncio.run(native(spec, flat))
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    for result in (response.json(), cli, mcp.structured_content):
        spec.output_model.model_validate(business(result))
        cached_output_validator(spec.output_model).validate(result)
        assert result["relationship_profile"]["davison_variant"] == variant
        assert (
            result["chart"]["chart_profile"]["sidereal_position_method"]
            == "swisseph_calc_sidereal_lahiri"
        )
        if mode == "Marks":
            assert set(result["marks_charts"]) == {"inner", "outer"}
            assert result["chart"] == result["marks_charts"]["inner"]
        else:
            pass


def test_marks_person_specific_source_and_times_support_strict_projection(
    rest: TestClient, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    flat = relationship_payload("Marks", "corrected")
    fields = [
        "relationship_profile.primary_chart_role",
        "marks_charts.outer.chart_profile.julian_day_tt",
        "marks_charts.outer.chart_profile.derivation_policy.recipe",
        "marks_charts.inner.person_info.name",
    ]
    response = rest.post(
        "/api/astrology/relationship-chart",
        json=flat,
        params=[("fields", path) for path in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
    )
    code, cli = call_cli(
        SPECS["astro_relative_chart"],
        flat,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ],
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
    for result in (response.json(), cli, mcp.structured_content):
        assert result["relationship_profile"]["primary_chart_role"] == "inner"
        assert isinstance(
            result["marks_charts"]["outer"]["chart_profile"]["julian_day_tt"], float
        )
        assert (
            "natal data"
            in result["marks_charts"]["outer"]["chart_profile"]["derivation_policy"][
                "recipe"
            ]
        )
        assert result["marks_charts"]["inner"]["person_info"]["name"].startswith("甲")
        assert not result.get("projection_warnings")


@pytest.mark.parametrize("variant", ["uncorrected", "corrected", "spherical"])
def test_published_marks_view_delivers_both_people_on_all_transports(
    variant: str, rest: TestClient, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    flat = relationship_payload("Marks", variant)
    spec = SPECS["astro_relative_chart"]
    card = evidence_views(spec)["marks"]
    fields = card["fields"]
    response = rest.post(
        "/api/astrology/relationship-chart",
        json=flat,
        params=[("fields", path) for path in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", 0),
        ],
    )
    code, cli = call_cli(
        spec,
        flat,
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
    mcp = asyncio.run(
        native(
            spec, flat, fields=fields, strict_fields=True, include_snapshot_text=False
        )
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    values = [response.json(), cli, mcp.structured_content]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for value in values:
        assert (
            value["relationship_profile"]["primary_layer"]
            == card["primary_layer"]
            == "marks_chart_pair"
        )
        assert value["relationship_profile"]["davison_variant"] == variant
        assert "chart" not in value and set(value["marks_charts"]) == {"inner", "outer"}
        pair = value["marks_charts"]
        assert pair["inner"]["planets"] != pair["outer"]["planets"]
        for role in ["inner", "outer"]:
            assert (
                pair[role]["chart_profile"]["derivation_policy"]["method_id"]
                == "marks_natal_davison_v1"
            )
            assert len(pair[role]["planets"]) >= 10 and len(pair[role]["houses"]) == 12
            assert pair[role]["angles"] and pair[role]["aspects"]
        spec.output_model.model_validate(value)


@pytest.mark.parametrize(
    "mode", ["Comp", "Composite", "Synastry", "TimeSpace", "Marks"]
)
def test_safe_union_includes_only_the_selected_marks_pair(
    mode: str, rest: TestClient
) -> None:
    flat = relationship_payload(mode, "uncorrected")
    response = rest.post(
        "/api/astrology/relationship-chart",
        json=flat,
        params=[
            ("fields", path) for path in suggested_fields(SPECS["astro_relative_chart"])
        ]
        + [("strict_fields", "true"), ("response_char_limit", 0)],
    )
    assert response.status_code == 200, response.text
    pair = response.json()["marks_charts"]
    assert set(pair) == ({"inner", "outer"} if mode == "Marks" else set())


def test_invalid_davison_selector_is_rejected_on_all_transports(
    rest: TestClient, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    flat = relationship_payload("TimeSpace", "unrecognised")
    response = rest.post("/api/astrology/relationship-chart", json=flat)
    code, cli = call_cli(SPECS["astro_relative_chart"], flat, tmp_path, capsys)
    mcp = asyncio.run(native(SPECS["astro_relative_chart"], flat))
    assert response.status_code == 422 and code != 0 and mcp.is_error


def test_real_natal_inputs_keep_contacts_when_participants_are_exchanged(
    rest: TestClient,
) -> None:
    flat = relationship_payload("Synastry", "uncorrected")
    reverse = {
        **flat,
        **{
            f"{side}_{key.removeprefix(other + '_')}": value
            for side, other in (("inner", "outer"), ("outer", "inner"))
            for key, value in flat.items()
            if key.startswith(other + "_")
        },
    }
    results = [
        rest.post(
            "/api/astrology/relationship-chart",
            json=inputs,
            params={"response_char_limit": 0},
        )
        for inputs in (flat, reverse)
    ]
    assert all(result.status_code == 200 for result in results)
    left, right = [result.json() for result in results]
    forward = {
        (row["inner"], row["outer"], row["aspect"], row["orb"])
        for row in left["synastry_aspects"]
    }
    reverse = {
        (row["outer"], row["inner"], row["aspect"], row["orb"])
        for row in right["synastry_aspects"]
    }
    assert forward == reverse


@pytest.mark.parametrize("hsys", [0, 8])
def test_composite_with_unresolved_ascendant_preserves_planets_aspects_and_mc(
    hsys: int, rest: TestClient, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    flat = relationship_payload("Composite", "uncorrected")
    flat.update(
        inner_birth_year=2000,
        inner_birth_month=1,
        inner_birth_day=1,
        inner_birth_hour=12,
        inner_birth_minute=0,
        inner_birth_timezone="UTC",
        inner_birth_longitude=J2000_UNRESOLVED_ASC_SITE["birth_longitude"],
        inner_birth_latitude=J2000_UNRESOLVED_ASC_SITE["birth_latitude"],
        hsys=hsys,
        zodiacal=0,
    )
    spec = SPECS["astro_relative_chart"]
    response = rest.post(
        "/api/astrology/relationship-chart",
        json=flat,
        params={"response_char_limit": 0},
    )
    code, cli = call_cli(
        spec, flat, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    mcp = asyncio.run(native(spec, flat))
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    results = [response.json(), cli, mcp.structured_content]
    assert business(results[0]) == business(results[1]) == business(results[2])

    for result in results:
        spec.output_model.model_validate(business(result))
        cached_output_validator(spec.output_model).validate(result)
        chart = result["chart"]
        assert chart["status"] == "underdetermined_ascendant"
        assert chart["ascendant_resolved"] is False
        assert chart["angles"]["ascendant"]["longitude"] is None
        assert chart["angles"]["ascendant"]["sign"] is None
        assert chart["angles"]["ascendant"]["status"] == "underdetermined_ascendant"
        assert chart["angles"]["midheaven"]["longitude"] is not None
        assert chart["angles"]["midheaven"]["sign"] is not None
        assert len(chart["planets"]) == 11
        assert chart["aspects"]
        assert chart["element_balance"]
        assert chart["modality_balance"]
        if hsys == 0:
            assert chart["houses"] == []
            assert all(planet["house"] is None for planet in chart["planets"])
        else:
            assert len(chart["houses"]) == 12
            assert all(planet["house"] is not None for planet in chart["planets"])
