"""Real REST, native MCP and CLI preserve the selected source and open gates."""

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import evidence_views
from fatebridge.core import astrology_horary
from tests.support.transports import SPECS, business, native, rest, surface_calls
from tests.western.test_western_horary import QUESTION


@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("profile", ["lilly_1647_p107_first", "lilly_1647_p107_second"])
def test_orbs_houses_source_facts_cross_actual_three_local_transports(
    project, profile, surface_calls
):
    spec = SPECS["astro_horary"]
    inputs = {**QUESTION, "category": "career", "orb_profile": profile}
    params = [("response_char_limit", 0)]
    flags = ["--response-char-limit", "0"]
    kwargs = {}
    if project:
        fields = evidence_views(spec)["lilly_orbs_houses"]["fields"]
        params += [("fields", field) for field in fields] + [
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
        kwargs = {
            "fields": fields,
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
        assert output["analysis_context"]["orb_profile"] == profile
        assert h["rule_profile"]["orb_table"]["profile_id"] == profile
        assert h["rule_profile"]["orb_table"]["full_orbs_degrees"]["Mars"] == (
            7.5 if profile.endswith("first") else 7
        )
        assert h["significators"]["querent"]["house"] == 1
        assert h["significators"]["quesited"]["house"] == 10
        for role in ["querent", "quesited"]:
            point = h["significators"][role]
            assert (
                point["occupied_house"]
                == h["planets"][point["planet"]]["occupied_house"]
            )
            assert point["house_condition"]["occupied_house"] == point["occupied_house"]
        assert h["significators"]["quesited"]["occupied_house"] != 10
        clause = h["perfection"]["lilly_conditions"]["p126_127_dwelling"]
        assert (
            clause["quesited_occupied_house"]
            == h["significators"]["quesited"]["occupied_house"]
        )
        assert clause["dwelling_alone_sufficient"] is False
        assert clause["full_judgement_accepted"] is False
        assert h["perfection"]["perfects"] is None and h["verdict"] == "uncertain"
        if clause["event_history_status"] == "unavailable":
            assert clause["lunar_sequence_subconditions_satisfied"] is None
            assert clause["event_history_unavailable_reason"]
        if h["moon"]["next_aspect"]:
            assert h["moon"]["next_aspect"]["orb_profile"] == profile
        if project:
            assert "snapshot_text" not in output
        else:
            assert (
                "occupied_house" in output["snapshot_text"]
                and profile in output["snapshot_text"]
            )


def test_exact_nullable_necessary_conditions_are_published_and_strictly_projectable(
    rest,
):
    spec = SPECS["astro_horary"]
    fields = [
        "horary.rule_profile.orb_table.profile_id",
        "horary.significators.querent.occupied_house",
        "horary.planets.Moon.house_condition.p48_strength_rank",
        "horary.perfection.lilly_conditions.p126_127_dwelling.moon_last_contact_is_quesited",
        "horary.perfection.lilly_conditions.p126_127_dwelling.full_judgement_accepted",
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
    assert response.status_code == 200, response.text
    result = response.json()
    assert not result.get("projection_warnings")
    clause = result["horary"]["perfection"]["lilly_conditions"]["p126_127_dwelling"]
    assert (
        clause["moon_last_contact_is_quesited"] is None
        and clause["full_judgement_accepted"] is False
    )


@pytest.mark.parametrize("available", [False, True])
def test_strict_view_accepts_both_available_and_unavailable_histories(
    available, monkeypatch, surface_calls
):
    def history(subject):
        return {
            "status": "computed" if available else "unavailable",
            "constant_velocity_projection": False,
            "events": [],
            "window_tt": [subject.julian_day_tt - 30, subject.julian_day_tt + 30],
            "completeness_scope": "Controlled engineering history; no astronomical acceptance",
            **(
                {} if available else {"unavailable_reason": "Controlled source failure"}
            ),
        }

    monkeypatch.setattr(astrology_horary, "native_planetary_events", history)
    monkeypatch.setattr(
        astrology_horary,
        "native_lunar_contacts",
        lambda subject: {
            "status": "unavailable",
            "constant_velocity_projection": False,
            "contacts": [],
            "void_of_course": None,
            "unavailable_reason": "Controlled lunar source failure",
        },
    )
    spec = SPECS["astro_horary"]
    inputs = {**QUESTION, "category": "career"}
    fields = evidence_views(spec)["lilly_orbs_houses"]["fields"]
    response, protocol, code, cli = surface_calls(
        spec,
        inputs,
        projection={
            **{"fields": fields, "strict_fields": True, "include_snapshot_text": False},
            "response_char_limit": 0,
        },
    )
    assert response.status_code == 200, response.text
    assert code == 0 and not protocol.is_error
    values = [response.json(), cli, protocol.structured_content]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for value in values:
        assert not value.get("projection_warnings")
        h = value["horary"]
        clause = h["perfection"]["lilly_conditions"]["p126_127_dwelling"]
        assert clause["event_history_status"] == (
            "computed" if available else "unavailable"
        )
        assert clause["event_history_unavailable_reason"] == (
            None if available else "Controlled source failure"
        )
        assert (
            clause["event_history_window_tt"][1] - clause["event_history_window_tt"][0]
            == 60
        )
        assert clause["lunar_sequence_subconditions_satisfied"] is None
        assert h["moon"]["motion_basis"]["status"] == "unavailable"
        assert h["moon"]["void_of_course"] is None
