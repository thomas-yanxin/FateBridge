"""Known-false source prerequisites cannot become unknown from missing intent."""

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.meihua_stage_emphasis import _scenario_conditions
from fatebridge.services.meihua import calculate_meihua_cast
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

FIXTURE = Path(__file__).parents[1] / "fixtures/meihua_condition_logic_v2"
TRUTH = json.loads((FIXTURE / "truth-table.json").read_text())["rows"]
GEOMETRIES = json.loads((FIXTURE / "geometry384-reused.json").read_text())


def conjunction(structural, scenario_match, *, mutual=False):
    # Independent literal table, not a call into the implementation.
    return next(
        row["expected"]
        for row in TRUTH
        if row["structural"] is structural
        and row["scenario_match"] is scenario_match
        and row["unresolved"] is mutual
    )


def test_reference_was_frozen_before_the_production_change():
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    assert manifest["preimplementation"]
    for name, sha in manifest["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == sha


@pytest.mark.parametrize("row", TRUTH)
@pytest.mark.parametrize("required", ["favorable_matter", "unfavorable_matter"])
def test_complete_literal_truth_table(row, required):
    other = (
        "unfavorable_matter" if required == "favorable_matter" else "favorable_matter"
    )
    scenario = (
        None
        if row["scenario_match"] is None
        else required if row["scenario_match"] else other
    )
    actual = _scenario_conditions(
        {"required_scenario": required},
        row["structural"],
        scenario,
        unresolved=["mutual_phrase_scope"] if row["unresolved"] else [],
    )
    assert actual["full_clause_applies"] is row["expected"]
    assert actual["scenario_condition_met"] is row["scenario_match"]


@pytest.mark.parametrize("case", GEOMETRIES, ids=lambda c: f"{c['code']}-{c['line']}")
def test_each_actual_geometry_under_all_three_scenario_states(case):
    relations = {r["role"]: r["relation"] for r in case["rows"]}
    generation = [role for role, relation in relations.items() if relation == "用生体"]
    attack = [role for role, relation in relations.items() if relation == "用克体"]
    structural = [
        relations["use"] == "用生体",
        any(relations[r] == "用生体" for r in ["body_mutual", "use_mutual"]),
        relations["changed_use"] == "用生体",
        bool(generation and attack),
        bool(not generation and attack),
        bool(generation),
        not bool(generation),
    ]
    for scenario in [None, "favorable_matter", "unfavorable_matter"]:
        out = calculate_meihua_cast(
            casting={
                "method": "existing",
                "hexagram_code": case["code"],
                "moving_line": case["line"],
            },
            matter_scenario=scenario,
        )
        stage = out["interpretation"]["stage_emphasis"]
        assert stage["body"] == case["body"]
        assert stage["generation_roles"] == generation
        assert stage["control_roles"] == attack
        clauses = [
            *stage["relative_generation_clauses"],
            stage["mixed_generation_control"],
            *stage["scenario_clauses"],
        ]
        for i, (clause, structure) in enumerate(zip(clauses, structural, strict=True)):
            match = (
                None if scenario is None else scenario == clause["required_scenario"]
            )
            assert clause["structural_condition_met"] is structure
            assert clause["scenario_condition_met"] is match
            assert clause["full_clause_applies"] is conjunction(
                structure, match, mutual=i == 1
            )
        timing = stage["obstruction_timing"]
        assert timing["structural_condition_met"] is structural[3]
        assert timing["selected_clause_applies"] is clauses[3]["full_clause_applies"]
        assert all(
            r["selected_clause_applies"] is timing["selected_clause_applies"]
            for r in timing["attacker_records"]
        )
        assert (
            stage["real_outcome"] is stage["event_time"] is timing["event_time"] is None
        )
        if scenario is None:
            assert stage["matter_scenario"] == "not_collected"
            assert stage["scenario_declaration"] is None


@pytest.mark.parametrize("scenario", [None, "favorable_matter", "unfavorable_matter"])
@pytest.mark.parametrize("tool", ["meihua_cast", "meihua_analysis"])
def test_strict_projection_agrees_on_rest_mcp_cli(
    tool, scenario, rest, tmp_path, capsys
):
    spec = SPECS[tool]
    payload = (
        {"casting": {"method": "existing", "hexagram_code": "000000", "moving_line": 1}}
        if tool == "meihua_cast"
        else {
            "analysis_year": 2026,
            "analysis_month": 2,
            "analysis_day": 5,
            "analysis_hour": 12,
            "analysis_timezone": "Asia/Shanghai",
        }
    )
    if scenario is not None:
        payload["matter_scenario"] = scenario
    fields = ["interpretation.stage_emphasis", "meihua.stage_relations"]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
        ],
    )
    assert response.status_code == 200, response.text
    mcp = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    code, cli = call_cli(
        spec,
        payload,
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
    assert code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(mcp.structured_content) == business(cli)
    )
