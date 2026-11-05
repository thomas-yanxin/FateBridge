"""T inverse facts, explanation provenance, and failures on all adapters."""

import asyncio
import json

import pytest
from jsonschema import Draft202012Validator

from fatebridge.core.astro import house_positions
from fatebridge.core.astro.topocentric_precision import TOPOCENTRIC_PROJECTION_METHOD
from fatebridge.core.local_techniques.otherbu import build_otherbu_result
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.western.test_western_house_projection_precision_transports import payload


def invoke(spec, p, fields, rest, tmp_path, capsys):
    include_text = "snapshot_text" in fields
    http = rest.post(
        spec.rest_path,
        json=p,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", str(include_text).lower()),
        ],
    )
    code, cli = call_cli(
        spec,
        p,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "--include-snapshot-text" if include_text else "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(
        native(
            spec,
            p,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=include_text,
        )
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    results = [http.json(), cli, protocol.structured_content]
    assert business(results[0]) == business(results[1]) == business(results[2])
    for result in results:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        assert not result.get("projection_warnings")
    return results


def checked(projection):
    assert projection["method"] == TOPOCENTRIC_PROJECTION_METHOD
    assert projection["house_code"] == "T"
    precision = projection["precision"]
    assert precision["latitude_clamped"] is False
    assert precision["maximum_physical_error_arcseconds"] is None
    assert precision["checks"]
    for check in precision["checks"]:
        branch = check["topocentric_branch"]
        assert branch["geographic_latitude_used"] == projection["geographic_latitude"]
        assert branch["latitude_clamped"] is False
        assert branch["candidate_root_degrees"]


@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize("latitude", [80.0, 89.999999, -89.999999])
def test_t_projection_and_explanation_survive_three_surfaces(
    zodiacal, latitude, rest, tmp_path, capsys
):
    p = payload(6, zodiacal)
    p["birth_latitude"] = latitude
    # A real epoch with a folded T partition; retain longitude zero.
    p.update(birth_year=2024, birth_month=3, birth_day=20, birth_longitude=0)
    spec = SPECS["astro_chart"]
    fields = [
        "chart_profile.house_position_projection",
        "planets",
        "summary",
        "interpretation_evidence.social_style.source_paths",
    ]
    for result in invoke(spec, p, fields, rest, tmp_path, capsys):
        projection = result["chart_profile"]["house_position_projection"]
        checked(projection)
        assert projection["note_zh"] in result["summary"]
        assert (
            "chart_profile.house_position_projection"
            in result["interpretation_evidence"]["social_style"]["source_paths"]
        )


@pytest.mark.parametrize("zodiacal", [0, 1])
def test_t_actual_dice_context_is_distinct_from_symbolic_dice(
    zodiacal, rest, tmp_path, capsys
):
    spec = SPECS["otherbu"]
    p = dict(
        planet="Moon",
        sign="Cancer",
        house=0,
        date="2024-03-20",
        time="00:30",
        zone="UTC",
        gps_lat=89.999999,
        gps_lon=0,
        hsys=6,
        zodiacal=zodiacal,
    )
    fields = [
        "chart",
        "symbolic_details",
        "interpretation",
        "rule_trace",
        "rulesets",
        "diceChart",
        "snapshot_text",
    ]
    plain = build_otherbu_result(planet="Moon", sign="Cancer", house=0)
    for result in invoke(spec, p, fields, rest, tmp_path, capsys):
        projection = result["chart"]["params"]["housePositionProjection"]
        checked(projection)
        assert projection["note_zh"] in result["snapshot_text"]
        for key in (
            "symbolic_details",
            "interpretation",
            "rule_trace",
            "rulesets",
            "diceChart",
        ):
            assert result[key] == plain[key]


@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
def test_t_predictive_contract_uses_same_inverse(zodiac, rest, tmp_path, capsys):
    p = payload(6)
    del p["hsys"], p["zodiacal"]
    p.update(
        birth_year=2024,
        birth_month=3,
        birth_day=20,
        birth_longitude=0,
        birth_latitude=89.999999,
        house_system="T",
        zodiac_type=zodiac,
        analysis_year=2024,
        analysis_month=3,
        analysis_day=20,
        analysis_hour=0,
        analysis_minute=30,
        return_timezone="UTC",
        return_longitude=0,
        return_latitude=89.999999,
    )
    fields = [
        f"{layer}.calculation_basis.house_position_projection"
        for layer in ("natal_reference", "transit")
    ]
    for result in invoke(SPECS["transit"], p, fields, rest, tmp_path, capsys):
        for layer in ("natal_reference", "transit"):
            checked(result[layer]["calculation_basis"]["house_position_projection"])


def test_t_precision_failure_cannot_be_hidden_by_fields(
    monkeypatch, rest, tmp_path, capsys
):
    def fail(**kwargs):
        raise ArithmeticError("injected T precision failure")

    monkeypatch.setattr(house_positions, "checked_topocentric_position", fail)
    p = payload(6)
    p.update(
        birth_year=2024,
        birth_month=3,
        birth_day=20,
        birth_longitude=0,
        birth_latitude=89.999999,
    )
    spec = SPECS["astro_chart"]
    fields = ["person_info.name"]
    http = rest.post(
        spec.rest_path,
        json=p,
        params=[("fields", fields[0]), ("strict_fields", "true")],
    )
    code, cli = call_cli(
        spec, p, tmp_path, capsys, flags=["--fields", *fields, "--strict-fields"]
    )
    protocol = asyncio.run(native(spec, p, fields=fields, strict_fields=True))
    assert http.status_code == 503 and code == 1 and protocol.is_error
    for result in (http.json(), cli, json.loads(protocol.content[0].text)):
        assert result["error_code"] == "ephemeris_source_inconsistent"
        assert result["issues"] == [
            {
                "path": "runtime.ephemeris_data",
                "code": "house_projection_precision_unavailable",
            }
        ]
        assert result["retryable"] is False and "person_info" not in result
