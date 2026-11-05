"""Coordinated corruption must still agree with the displayed calculation."""

import copy
import importlib.util
import json
import shutil
from dataclasses import replace
from itertools import product
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.metaphysics.jinkou_stems import ganzhi_pair_facts
from fatebridge.core.output_jinkou_stems import (
    JinkouDunStemNode,
    JinkouGanzhiPairFacts,
    JinkouStemRelations,
)
from fatebridge.services.metaphysics import calculate_jinkou_analysis
from tests.support.transports import AS_OF, SPECS, rest, surface_calls

ROOT = Path(__file__).resolve().parents[2]
MODULE = importlib.util.spec_from_file_location(
    "stem_integrity_audit", ROOT / "scripts/ren/audit_jinkou_stem_integrity.py"
)
assert MODULE and MODULE.loader
AUDIT = importlib.util.module_from_spec(MODULE)
MODULE.loader.exec_module(AUDIT)
FROZEN, LEDGER = AUDIT.reference()
BUSINESS_FAULTS = [f for f in FROZEN["faults"] if f["target"] == "business"]
PAIR_FAULTS = [f for f in FROZEN["faults"] if f["target"] == "pair"]


def test_fixed_denominators_do_not_turn_missing_source_stems_into_matches():
    result = AUDIT.audit()
    assert result["required_fault_count"] == result["rejected_fault_count"] == 20
    assert result["fault_rejection_passed"]
    assert result["diagram_display_count"] == 64
    assert result["required_carried_stem_slots"] == result["not_printed_slots"] == 128
    assert result["literal_carried_stem_labels"] == 0
    assert result["diagram_calculation_match_rate"] is None
    assert result["classical_acceptance_passed"] is result["goal_complete"] is False


@pytest.mark.parametrize("change", ["edit", "missing", "extra", "shrink"])
def test_independent_faults_and_display_inventory_cannot_drift(tmp_path, change):
    target = tmp_path / "corpus"
    shutil.copytree(AUDIT.CORPUS, target)
    if change in {"edit", "shrink"}:
        p = target / "faults.json"
        value = json.loads(p.read_text())
        if change == "edit":
            value["faults"][0]["expected_acceptance"] = True
        else:
            value["faults"].pop()
        p.write_text(json.dumps(value))
    elif change == "missing":
        (target / "diagram-ledger.json").unlink()
    else:
        (target / "extra.json").write_text("{}")
    with pytest.raises(ValueError, match="Frozen stem-integrity"):
        AUDIT.reference(target)


@pytest.mark.parametrize("fault", PAIR_FAULTS, ids=lambda f: f["id"])
def test_pair_facts_reject_coordinated_and_invalid_cycle_changes(fault):
    with pytest.raises(ValidationError):
        JinkouGanzhiPairFacts.model_validate(
            AUDIT.corrupt(FROZEN["pair_anchor"], fault["updates"])
        )


def test_all_3600_valid_pairs_remain_valid_after_stronger_guard():
    # This is acceptance coverage; source-derived pair truth stays in the
    # independently frozen audit_jinkou_stems corpus, not this generated loop.
    stems, branches = "甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥"
    cycle = [stems[i % 10] + branches[i % 12] for i in range(60)]
    for a, b in product(cycle, repeat=2):
        JinkouGanzhiPairFacts.model_validate(ganzhi_pair_facts(a, b))


@pytest.mark.parametrize("fault", BUSINESS_FAULTS, ids=lambda f: f["id"])
@pytest.mark.parametrize("project", [False, True])
def test_coordinated_faults_fail_on_all_ports_before_unrelated_projection(
    fault, project, monkeypatch, surface_calls
):
    spec = SPECS["jinkou"]
    valid = calculate_jinkou_analysis(**FROZEN["business_payload"])
    execution.validate_output(spec, valid)
    bad = AUDIT.corrupt(valid, fault["updates"])
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
    options = {}
    params = dict(as_of=AS_OF, response_char_limit=0)
    flags = ["--response-char-limit", "0"]
    if project:
        params.update(fields="analysis_type", strict_fields="true")
        options.update(fields=["analysis_type"], strict_fields=True)
        flags += ["--fields", "analysis_type", "--strict-fields", "true"]
    http, protocol, code, output = surface_calls(
        spec,
        FROZEN["business_payload"],
        params=params,
        options=options,
        flags=flags,
        cli_first=False,
    )
    assert http.status_code == 500 and protocol.is_error and code == 1
    assert output["error_code"] == "internal_error"


@pytest.mark.parametrize(
    "model,value",
    [
        (JinkouGanzhiPairFacts, {"candidate_element": "火"}),
        (JinkouGanzhiPairFacts, {"transformation_confirmed": None}),
        (JinkouGanzhiPairFacts, {"stem_harmony_matched": False}),
        (JinkouDunStemNode, {"dun_stem": "壬"}),
        (JinkouStemRelations, {"complete_classical_conformance": False}),
        (JinkouStemRelations, {"god": {"dun_element": "水"}}),
    ],
)
def test_independent_sparse_fields_keep_projection_semantics(model, value):
    assert model.model_validate(value).model_dump(exclude_unset=True) == value


@pytest.mark.parametrize(
    "value",
    [
        {"day_stem": "乙", "god": {"branch": "午", "dun_stem": "丙"}},
        {"day_stem": "乙", "god": {"branch": "午", "dun_ganzhi": "丙午"}},
        {"day_stem": "乙", "god": {"branch": "午", "dun_element": "火"}},
        {
            "god": {"dun_stem": "壬"},
            "general": {"dun_stem": "己"},
            "relation": "神干生将干",
        },
    ],
)
def test_sparse_objects_still_reject_contradictions_when_anchors_are_present(value):
    with pytest.raises(ValidationError):
        JinkouStemRelations.model_validate(value)
