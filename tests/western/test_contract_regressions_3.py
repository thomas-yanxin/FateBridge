"""Related contract regressions with shared imports; original cases retained."""

import asyncio
import hashlib
import json
import shutil
from fractions import Fraction

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import evidence_views
from fatebridge.cli import run
from scripts.western.audit_western_tt_events import (
    CORPUS,
    ROOT,
    validate_reference_identity,
)
from tests.fixtures.surface_payloads import REST_POST_CASES
from tests.support.transports import (
    SPECS,
    business,
    inputs,
    native,
    rest,
    surface_calls,
)
from tests.western.test_western_event_clock_transports import surfaces
from tests.western.test_western_horary import QUESTION
from tests.western.test_western_mixed_moon import selected


@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
def test_c04_last_nominal_epoch_computes_lilly_daily_motion_on_all_protocols(
    zodiac, rest, tmp_path, capsys
):
    values = surfaces(
        "astro_horary",
        dict(
            question_year=2026,
            question_month=9,
            question_day=19,
            question_hour=0,
            timezone_name="UTC",
            longitude=0,
            latitude=40,
            ut1_source="iers_c04",
            zodiac_type=zodiac,
            category="career",
        ),
        [
            "clock_conversion",
            "horary.calculation_basis",
            "horary.fortitudes.physical_inputs",
            "horary.fortitudes.summary",
            "horary.fortitudes.full_original_text_acceptance",
            "horary.verdict",
        ],
        rest,
        tmp_path,
        capsys,
    )
    for value in values:
        clock = value["clock_conversion"]
        horary = value["horary"]
        assert clock["ut1_reference"]["instant_value_kind"] == "published_daily_sample"
        assert clock["julian_day_tt"] == horary["calculation_basis"]["julian_day_tt"]
        ledger = horary["fortitudes"]
        data = ledger["physical_inputs"]
        assert data["status"] == "computed"
        assert data["day_interval_tt"] == [
            clock["julian_day_tt"],
            clock["julian_day_tt"] + 1,
        ]
        assert len(data["motion"]) == 7
        assert all(
            row["status"] == "computed" and len(row["samples"]) == 5
            for row in data["motion"].values()
        )
        assert all(row["row_count"] == 41 for row in ledger["summary"].values())
        assert ledger["full_original_text_acceptance"] is False
        assert horary["verdict"] == "uncertain"


def test_uncovered_nominal_ut1_is_still_rejected_on_all_protocols(surface_calls):
    spec = SPECS["astro_horary"]
    args = dict(
        question_year=2026,
        question_month=9,
        question_day=20,
        question_hour=0,
        timezone_name="UTC",
        longitude=0,
        latitude=40,
        ut1_source="iers_c04",
    )
    response, mcp, code, cli = surface_calls(spec, args)
    # Runtime coverage validation uses the existing 400 envelope; schema
    # validation uses 422. The TT-only change must not make this request valid.
    assert response.status_code == 400 and code != 0 and mcp.is_error
    assert response.json()["error_code"] == cli["error_code"] == "validation_error"
    assert response.json()["retryable"] is False and cli["retryable"] is False
    assert "horary" not in cli


@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
@pytest.mark.parametrize("published_card", [True, False])
def test_literal_table_summary_and_leaf_projection_match_all_protocols(
    zodiac, published_card, surface_calls
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
    response, protocol, code, cli = surface_calls(
        spec,
        payload,
        projection={
            **{"fields": fields, "strict_fields": True, "include_snapshot_text": False},
            "response_char_limit": 0,
        },
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


@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
@pytest.mark.parametrize("card", [True, False])
def test_fortune_night_formula_cusp_assignment_and_row_projection_across_protocols(
    zodiac, card, surface_calls
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
    response, protocol, code, cli = surface_calls(
        spec,
        payload,
        projection={
            **{"fields": fields, "strict_fields": True, "include_snapshot_text": False},
            "response_char_limit": 0,
        },
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


def test_house_assignment_wording_reaches_rows_and_summary_on_all_protocols(
    rest, tmp_path, capsys
):
    values = surfaces(
        "astro_horary",
        dict(
            question_year=2026,
            question_month=9,
            question_day=19,
            question_hour=0,
            timezone_name="UTC",
            longitude=0,
            latitude=40,
            ut1_source="iers_c04",
            category="career",
        ),
        [
            "horary.planets.Sun.occupied_house",
            "horary.planets.Sun.house_assignment",
            "horary.fortitudes.planets.Sun.rows",
            "horary.fortitudes.planets.Venus.rows",
            "horary.fortitudes.summary.Sun.applied_conditions",
            "horary.fortitudes.summary.Venus.applied_conditions",
            "horary.fortitudes.full_original_text_acceptance",
            "horary.verdict",
        ],
        rest,
        tmp_path,
        capsys,
    )
    for value in values:
        h = value["horary"]
        assert h["planets"]["Sun"]["occupied_house"] == 3
        assert h["planets"]["Sun"]["house_assignment"]["assigned_house"] == 4
        for planet, code, occupied, scored, points in [
            ("Sun", "F02", 3, 4, 4),
            ("Venus", "F03", 4, 5, 3),
        ]:
            rows = h["fortitudes"]["planets"][planet]["rows"]
            row = next(r for r in rows if r["code"] == code)
            assert row["inputs"]["occupied_house"] == occupied
            assert row["inputs"]["scored_house"] == scored
            assert row["contribution"] == points
            assert row["label_zh"].startswith("计分归")
            assert row["source_pages"] == [33, 115]
            summary = h["fortitudes"]["summary"][planet]["applied_conditions"]
            assert (
                next(r for r in summary if r["code"] == code)["label_zh"]
                == row["label_zh"]
            )
        assert not h["fortitudes"]["full_original_text_acceptance"]
        assert h["verdict"] == "uncertain"


@pytest.mark.parametrize("extension", [False, True])
def test_radicality_card_and_leaf_context_on_rest_native_mcp_and_cli(
    extension, rest, tmp_path, capsys
):
    spec = SPECS["astro_horary"]
    context = {
        "figure_origin": "timed_event" if extension else "propounded_question",
        "event_time_certain_reported": True,
        "age_degree_agreement_reported": False,
        "principal_significators_very_strong_reported": False,
    }
    payload = {
        **QUESTION,
        "zodiac_type": "Sidereal" if extension else "Tropic",
        "house_system": "whole_sign" if extension else "R",
        "radicality_context": context,
    }
    fields = list(evidence_views(spec)["lilly_radicality"]["fields"]) + [
        "horary.radicality.clause_count",
        "horary.radicality.real_world_prediction_established",
        "horary.radicality.source_method_scope",
        "horary.rule_profile.radicality_policy",
    ]
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
    request_file = tmp_path / "horary.json"
    request_file.write_text(
        json.dumps({k: v for k, v in payload.items() if k != "radicality_context"})
    )
    # Exercise the public JSON object argument as well as --request-file.
    code = run(
        [
            spec.tool_name,
            "--request-file",
            str(request_file),
            "--radicality-context",
            json.dumps(context),
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ]
    )
    cli = json.loads(capsys.readouterr().out)
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
    assert json.loads(protocol.content[0].text) == protocol.structured_content
    results = [response.json(), cli, protocol.structured_content]
    assert business(results[0]) == business(results[1]) == business(results[2])
    for value in results:
        spec.output_model.model_validate(value)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(value)
        assert not value.get("projection_warnings")
        h = value["horary"]
        r = h["radicality"]
        assert h["verdict"] == "uncertain" and r["safe_to_judge"] is None
        assert len(r["clauses"]) == r["clause_count"] == 12
        assert r["full_original_text_acceptance"] is False
        assert r["full_judgement_accepted"] is False
        assert r["real_world_prediction_established"] is False
        assert r["source_method_scope"] == (
            "other_or_unknown_chart_method_modern_extension"
            if extension
            else "tropical_regiomontanus_declared_review"
        )
        assert r["hour_inputs"]["status"] == "computed"
        assert r["hour_inputs"]["actual_solar_backend_verified"] is False
        assert r["reported_context"]["provided_fields"] == sorted(context)
        assert r["reported_context"]["very_young_querent_reported"] is None
        assert r["ascendant_degree_gate"]["certain_timed_event_exception"] is extension
        assert value["analysis_context"]["radicality_context"] == r["reported_context"]
        assert "C03" in r["unknown_clauses"] and "C11" in r["unknown_clauses"]
        for key, expected in context.items():
            assert r["reported_context"][key] == expected


@pytest.mark.parametrize(
    "context",
    [
        {"event_time_certain_reported": "true"},
        {"event_time_certain_reported": 1},
        {"safe_to_judge": True},
        {"figure_origin": "known_clock"},
    ],
)
def test_context_faults_fail_before_calculation_on_all_protocols(
    context, surface_calls
):
    spec = SPECS["astro_horary"]
    payload = {**QUESTION, "radicality_context": context}
    http, protocol, code, cli = surface_calls(spec, payload)
    assert http.status_code == 422 and code != 0 and protocol.is_error
    assert "horary" not in cli


@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
@pytest.mark.parametrize("category", ["marriage", "career"])
def test_lilly_source_receipts_across_rest_native_mcp_and_cli(
    project, zodiac, category, surface_calls
):
    spec = SPECS["astro_horary"]
    inputs = {**QUESTION, "category": category, "zodiac_type": zodiac}
    card = evidence_views(spec)["lilly_reception_conditions"]
    params = [("response_char_limit", 0)]
    flags = ["--response-char-limit", "0"]
    kwargs = {}
    if project:
        params += [("fields", field) for field in card["fields"]] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            *card["fields"],
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        kwargs = {
            "fields": card["fields"],
            "strict_fields": True,
            "include_snapshot_text": False,
        }
    response, protocol, code, cli = surface_calls(
        spec, inputs, params=params, options=kwargs, flags=flags
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    values = [response.json(), cli, protocol.structured_content]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for output in values:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        assert not output.get("projection_warnings")
        h = output["horary"]
        facts = h["perfection"]["lilly_conditions"]
        assert len(h["planets"]) == 7
        assert facts["chart_sect"] == "day"
        assert facts["coordinate_scope"] == (
            "tropical_selected_edition"
            if zodiac == "Tropic"
            else "sidereal_extension_not_original_edition_acceptance"
        )
        assert (
            facts["full_original_text_acceptance"] is False
            and h["verdict"] == "uncertain"
        )
        if category == "career" and zodiac == "Tropic":
            assert any(route["mode"] == "direct" for route in facts["routes"])
        if category == "marriage" and zodiac == "Tropic":
            assert facts["p112_mutual_reception"]["premise_satisfied"] is True
        assert (
            facts["p112_mutual_reception"]["premise_satisfied"]
            == facts["principal_reception"]["mutual"]
        )
        for row in facts["principal_reception"]["directions"]:
            assert row["receiver"] != row["guest"]
            assert row["guest_longitude"] == h["planets"][row["guest"]]["longitude"]
        if project:
            assert "snapshot_text" not in output and "heuristic_verdict" not in h
        else:
            assert (
                "本质尊贵" in output["snapshot_text"]
                and "p112_mutual_reception" in output["snapshot_text"]
            )


def test_projection_of_deep_nullable_source_condition_is_declared(rest):
    spec = SPECS["astro_horary"]
    fields = [
        "horary.planets.Moon.essential_condition.peregrine",
        "horary.perfection.lilly_conditions.principal_reception.mutual",
        "horary.perfection.lilly_conditions.p112_mutual_reception.conditional_reading_zh",
    ]
    response = rest.post(
        spec.rest_path,
        json={**QUESTION, "category": "general"},
        params=[("fields", p) for p in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", 0),
        ],
    )
    assert response.status_code == 200
    out = response.json()
    assert not out.get("projection_warnings")
    assert (
        out["horary"]["perfection"]["lilly_conditions"]["principal_reception"]["mutual"]
        is None
    )
    Draft202012Validator(spec.output_model.model_json_schema()).validate(out)


def test_election_major_dignity_scope_is_available_in_strict_view(surface_calls):
    spec = SPECS["astro_election"]
    inputs = REST_POST_CASES[spec.rest_path]()
    fields = ["election.dignity_scope"]
    response, protocol, code, cli = surface_calls(
        spec,
        inputs,
        projection={
            **{"fields": fields, "strict_fields": True, "include_snapshot_text": False},
            "response_char_limit": 0,
        },
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    values = [response.json(), cli, protocol.structured_content]
    assert business(values[0]) == business(values[1]) == business(values[2])
    assert "peregrine_not_classified" in values[0]["election"]["dignity_scope"]


def test_native_sun_regulus_five_to_six_degrees_on_rest_mcp_cli(rest, tmp_path, capsys):
    values = surfaces(
        "astro_horary",
        dict(
            question_year=2024,
            question_month=8,
            question_day=17,
            question_hour=12,
            timezone_name="UTC",
            longitude=0,
            latitude=40,
            category="career",
        ),
        [
            "horary.fortitudes.method_id",
            "horary.fortitudes.planets.Sun.rows",
            "horary.fortitudes.full_original_text_acceptance",
            "horary.fortune.method_id",
            "horary.fortune.rows",
            "horary.verdict",
        ],
        rest,
        tmp_path,
        capsys,
    )
    for value in values:
        h = value["horary"]
        f = h["fortitudes"]
        assert f["method_id"].endswith("v3")
        row = next(r for r in f["planets"]["Sun"]["rows"] if r["code"] == "F17")
        assert 5 < row["inputs"]["separation_degrees"] < 6
        assert row["inputs"]["orb_degrees"] == 6
        assert row["satisfied"] and row["contribution"] == 6
        assert row["condition"] == "regulus_within_six_degrees"
        assert "六度" in row["label_zh"]
        assert row["source_pages"] == [115, 179]
        fortune = h["fortune"]
        assert fortune["method_id"].endswith("v2")
        r = next(r for r in fortune["rows"] if r["code"] == "P14")
        assert r["inputs"]["orb_degrees"] == 6
        assert "declared convention" in r["inputs"]["star_policy"]
        assert r["source_pages"] == [145, 179]
        assert not f["full_original_text_acceptance"]
        assert h["verdict"] == "uncertain"


@pytest.mark.parametrize(
    "key",
    [
        "astro_chart",
        "astro_hellen",
        "astro_chart13",
        "astro_germany",
        "astro_horary",
        "astro_election",
        "profection",
        "solararc",
    ],
)
def test_partial_physical_data_is_an_explicit_source_error(
    key, selected, tmp_path, surface_calls
):
    spec = SPECS[key]
    selected("planet_only")
    payload = inputs(spec)
    # All cases are synthetic catalog engineering fixtures at contemporary epochs.
    http, protocol, code, cli = surface_calls(spec, payload, flags=[])
    assert http.status_code == 503 and code == 1 and protocol.is_error
    for index, value in enumerate(
        [http.json(), cli, json.loads(protocol.content[0].text)]
    ):
        assert value["error_code"] == "ephemeris_source_inconsistent"
        assert value["retryable"] is False
        assert value["issues"] == [
            {"path": "runtime.ephemeris_data", "code": "swiss_dependency_unavailable"}
        ]
        assert (
            "backend" not in value and "planets" not in value and "score" not in value
        )
        (tmp_path / f"{key}-{index}.json").write_text(json.dumps(value))


def test_canonical_corpus_is_accepted():
    validate_reference_identity(ROOT / CORPUS)


def test_alternate_reference_and_its_rewritten_manifest_cannot_replace_answers(
    tmp_path,
):
    chosen = tmp_path / "reference"
    shutil.copytree(ROOT / CORPUS, chosen)
    target = chosen / "reference.json.gz"
    target.write_bytes(b"caller-changed answers")
    manifest = json.loads((chosen / "source-files.json").read_text())
    manifest["files"]["reference.json.gz"] = hashlib.sha256(
        target.read_bytes()
    ).hexdigest()
    (chosen / "source-files.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Independent physical reference changed"):
        validate_reference_identity(chosen)
