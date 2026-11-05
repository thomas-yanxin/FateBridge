"""Source uncertainty survives conditional calculations and every transport."""

import copy
import importlib.util
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.application.examples import evidence_views
from fatebridge.core.metaphysics.jinkou_definitions import definition_evidence
from fatebridge.core.output_jinkou_definitions import JinkouDefinitionEvidence
from fatebridge.services.metaphysics import calculate_jinkou_analysis
from tests.support.transports import AS_OF, SPECS, business, rest, surface_calls

ROOT = Path(__file__).resolve().parents[2]
MOD = importlib.util.spec_from_file_location(
    "definition_audit", ROOT / "scripts/ren/audit_jinkou_definitions.py"
)
assert MOD and MOD.loader
AUDIT = importlib.util.module_from_spec(MOD)
MOD.loader.exec_module(AUDIT)
READINGS, FACTS = AUDIT.reference()
PAYLOAD = json.loads((ROOT / "tests/fixtures/ren_anchors_v1/faults.json").read_text())[
    "payloads"
]["jinkou"]


def test_new_witness_keeps_ambiguity_and_fixed_denominators():
    result = AUDIT.audit()
    assert result["engineering_checks_passed"]
    assert result["selected_pattern_notes"] == 6
    assert result["reading_annotations"] == 12
    assert result["distinct_selected_text_entries"] == 11
    assert (
        result["new_historical_cases"] == result["original_predicates_adjudicated"] == 0
    )
    assert result["hypotheses_promoted_to_predicates"] == 0
    assert result["classical_acceptance_passed"] is result["goal_complete"] is False
    a, b, _, _, back, ding = READINGS["entries"]
    assert a["witness_readings"][1] == b["witness_readings"][1]
    assert a["witness_readings"][0]["raw_alias"] == "匪棘卦"
    assert a["witness_readings"][1]["raw_alias"] == "利用卦"
    assert [r["literal_day_ganzhi"] for r in back["witness_readings"]] == [
        "甲辰",
        "丙辰",
    ]
    assert {r["raw_definition"] for r in ding["witness_readings"]} == {
        "丁酉入鬼作鬼是也"
    }


@pytest.mark.parametrize("change", ["edit", "missing", "extra", "shrink"])
def test_source_inventory_cannot_be_pruned_or_relabelled(tmp_path, change):
    target = tmp_path / "corpus"
    shutil.copytree(AUDIT.CORPUS, target)
    if change in {"edit", "shrink"}:
        p = target / "readings.json"
        value = json.loads(p.read_text())
        if change == "edit":
            value["entries"][0]["adjudicated_match"] = True
        else:
            value["entries"].pop()
        p.write_text(json.dumps(value))
    elif change == "missing":
        (target / "waseda-058.jpg").unlink()
    else:
        (target / "extra.txt").write_text("extra")
    with pytest.raises(ValueError, match="Frozen definition witness"):
        AUDIT.reference(target)


def test_p59_literal_example_does_not_identify_one_ding_route():
    value = definition_evidence(
        day_stem="戊",
        hour_branch="辰",
        is_diurnal=True,
        rows=AUDIT.literal_rows(["金", "土", "火", "金"]),
    )
    routes = {r["route_id"]: r for r in value["ding_routes"]}
    assert {k: r["stem"] for k, r in routes.items()} == FACTS["ding_example"]["routes"]
    for rid in ("daily_general", "human_redun_at_ground"):
        assert (
            routes[rid]["is_ding"]
            and routes[rid]["controls_human"]
            and routes[rid]["controls_ground"]
        )
    assert all(r["identified_by_original_clause"] is None for r in routes.values())


def test_two_different_pairings_fit_each_source_diagram_but_are_not_equivalent():
    # These two phase vectors distinguish the candidate formulae. The book's
    # alternating diagram does not, so neither candidate is adopted as truth.
    for phases, expected in [
        (["木", "木", "火", "水"], [True, False, False]),
        (["木", "水", "火", "木"], [False, True, False]),
    ]:
        value = definition_evidence(
            day_stem="戊",
            hour_branch="辰",
            is_diurnal=True,
            rows=AUDIT.literal_rows(phases),
        )
        assert [
            h["all_conditions_met"] for h in value["cross_generation_hypotheses"][:3]
        ] == expected
        assert all(
            h["adjudicated_predicate"] is None
            for h in value["cross_generation_hypotheses"]
        )


@pytest.mark.parametrize("selected", [True, False])
def test_conditional_twilight_example_changes_policy_selection_not_observed_twilight(
    selected,
):
    value = definition_evidence(
        day_stem="甲",
        hour_branch="寅",
        is_diurnal=selected,
        rows=AUDIT.literal_rows(["火", "水", "土", "水"], ["丙", "子", "戌", "子"]),
    )
    assert [c["god_name"] for c in value["day_night_candidates"]] == ["天后", "白虎"]
    assert [
        c["selected_under_current_policy"] for c in value["day_night_candidates"]
    ] == [selected, not selected]
    assert (
        value["observed_twilight_transition"] is value["front_back_predicate"] is None
    )


FAULTS = [
    ("entries.0.adjudicated_match", True),
    ("cross_generation_hypotheses.0.adjudicated_predicate", True),
    ("observed_twilight_transition", True),
    ("complete_classical_conformance", True),
    ("ding_routes.2.stem", "甲"),
    ("day_night_candidates.0.ground_clockwise_steps", 11),
    ("day_stem", "甲"),
    ("hour_branch", "巳"),
]


@pytest.mark.parametrize("fault", FAULTS, ids=lambda f: f[0])
@pytest.mark.parametrize("project", [False, True])
def test_unrelated_projection_cannot_hide_false_definition_facts(
    fault, project, monkeypatch, surface_calls
):
    spec = SPECS["jinkou"]
    bad = calculate_jinkou_analysis(**PAYLOAD)
    cursor = bad["jinkou"]["definition_evidence"]
    parts = fault[0].split(".")
    for key in parts[:-1]:
        cursor = cursor[int(key)] if isinstance(cursor, list) else cursor[key]
    cursor[parts[-1]] = fault[1]
    with pytest.raises(ValidationError):
        spec.output_model.model_validate(bad)
    original = execution.execute_spec

    def broken(actual, request):
        if actual.key == spec.key:
            actual = replace(
                actual, bind=lambda _: (lambda: copy.deepcopy(bad), (), {})
            )
        return original(actual, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    params, options, flags = (
        dict(as_of=AS_OF, response_char_limit=0),
        {},
        ["--response-char-limit", "0"],
    )
    if project:
        params.update(fields="analysis_type", strict_fields="true")
        options.update(fields=["analysis_type"], strict_fields=True)
        flags += ["--fields", "analysis_type", "--strict-fields", "true"]
    http, protocol, code, output = surface_calls(
        spec, PAYLOAD, params=params, options=options, flags=flags, cli_first=False
    )
    assert http.status_code == 500 and protocol.is_error and code == 1
    assert output["error_code"] == "internal_error"


@pytest.mark.parametrize("project", [False, True])
def test_three_ports_preserve_all_six_null_verdicts_and_same_run_facts(
    project, surface_calls
):
    spec = SPECS["jinkou"]
    fields = evidence_views(spec)["definition_witnesses"]["fields"]
    params = [("as_of", AS_OF), ("response_char_limit", "0")]
    flags, options = ["--response-char-limit", "0"], {}
    if project:
        params += [("fields", f) for f in fields] + [
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
        options.update(fields=fields, strict_fields=True, include_snapshot_text=False)
    http, protocol, code, cli = surface_calls(
        spec, PAYLOAD, params=params, options=options, flags=flags, cli_first=False
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    for body in (http.json(), protocol.structured_content, cli):
        spec.output_model.model_validate(body)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(body)
        evidence = body["jinkou"]["definition_evidence"]
        assert evidence["entries"] == READINGS["entries"]
        assert all(e["adjudicated_match"] is None for e in evidence["entries"])
        assert body["jinkou"]["patterns"]["evaluation_counts"]["unresolved"] == 6


@pytest.mark.parametrize(
    "field",
    ["entries", "ding_routes", "day_night_candidates", "cross_generation_hypotheses"],
)
def test_complete_gate_requires_evidence_but_projection_model_stays_sparse(field):
    spec = SPECS["jinkou"]
    valid = calculate_jinkou_analysis(**PAYLOAD)
    del valid["jinkou"]["definition_evidence"][field]
    spec.output_model.model_validate(valid)
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(spec, valid)


def test_sparse_null_projections_and_unrelated_fields_are_still_valid():
    value = {"observed_twilight_transition": None, "front_back_predicate": None}
    assert (
        JinkouDefinitionEvidence.model_validate(value).model_dump(exclude_unset=True)
        == value
    )
    sparse = {"jinkou": {"definition_evidence": {"entries": READINGS["entries"]}}}
    assert (
        SPECS["jinkou"]
        .output_model.model_validate(sparse)
        .model_dump(exclude_unset=True)
        == sparse
    )
