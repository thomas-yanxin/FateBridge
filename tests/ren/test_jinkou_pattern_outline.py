"""Sparse source claims cannot discard their already known definition identity."""

import copy
import hashlib
import json
import shutil

import pytest
from pydantic import ValidationError

from fatebridge.core.output_chinese import Jinkou
from fatebridge.core.output_ren_patterns import JinkouPatternEvaluation, JinkouPatterns
from scripts.ren.audit_jinkou_pattern_outline import CORPUS, audit, reference


@pytest.mark.parametrize(
    "fault", ["data", "manifest", "missing", "extra", "joint_rewrite"]
)
def test_frozen_outline_identity_is_not_redefinable(fault, tmp_path):
    folder = tmp_path / "source"
    shutil.copytree(CORPUS, folder)
    p = folder / "reference.json"
    if fault in {"data", "joint_rewrite"}:
        value = json.loads(p.read_text())
        value["entries"].pop()
        p.write_text(json.dumps(value))
        if fault == "joint_rewrite":
            m = json.loads((folder / "freeze.json").read_text())
            m["reference.json"] = hashlib.sha256(p.read_bytes()).hexdigest()
            (folder / "freeze.json").write_text(json.dumps(m))
    elif fault == "manifest":
        (folder / "freeze.json").write_text("{}")
    elif fault == "missing":
        p.unlink()
    else:
        (folder / "extra").write_text("")
    with pytest.raises((ValueError, FileNotFoundError)):
        reference(folder)


def test_source_definition_and_unknown_fragments_keep_full_predeclared_denominators():
    result = audit()
    assert result["counts"] == dict(
        invalid=344, invalid_accepted=0, valid=144, valid_rejected=0, valid_changed=0
    )
    assert result["selected_outline_checks_passed"]
    assert result["new_classical_examples"] == 0
    assert result["complete_classical_conformance"] is result["goal_complete"] is False


@pytest.mark.parametrize(
    "value",
    [
        {"matched": True},
        {"condition": "external reading without a selected ID"},
        {"id": "P03", "matched": None, "status": "input_unavailable"},
        {"extension": {"source_unreviewed": True}},
    ],
)
def test_missing_course_or_id_never_invents_an_outcome(value):
    original = copy.deepcopy(value)
    got = JinkouPatternEvaluation.model_validate(value).model_dump(exclude_unset=True)
    assert got == original


def test_partial_source_validation_does_not_rewrite_existing_aliases_or_predicates():
    from fatebridge.core.metaphysics.jinkou_patterns import (
        pattern_identity,
        pattern_metadata,
    )

    ref = reference()
    assert pattern_metadata() == ref["metadata"]
    for row in ref["entries"]:
        expected = {k: v for k, v in row.items() if k != "id"}
        actual = pattern_identity(row["id"])
        assert {k: actual[k] for k in expected} == expected
    assert ref["unknown_ids"] == ["P52", "P53", "P56", "P57", "P58", "P59"]


def test_trace_only_source_claims_are_checked_without_inventing_a_raw_course():
    source = reference()["metadata"]["source_url"]
    value = {
        "rule_trace": [
            {
                "rule_id": "jinkou.structural_patterns",
                "source_url": source,
                "result": {"source_url": source},
            }
        ]
    }
    assert Jinkou.model_validate(value).model_dump(exclude_unset=True) == value
    bad = copy.deepcopy(value)
    bad["rule_trace"][0]["result"]["source_url"] = "https://example.invalid/forged"
    with pytest.raises(ValidationError):
        Jinkou.model_validate(bad)
    for other in [
        {"rule_trace": [{"rule_id": "jinkou.structural_patterns", "result": None}]},
        {"rule_trace": [{"rule_id": "external", "result": {"source_url": "external"}}]},
    ]:
        assert Jinkou.model_validate(other).model_dump(exclude_unset=True) == other


def test_selected_id_does_not_allow_unresolved_definition_promotion_by_omitting_status():
    for value in [True, False]:
        with pytest.raises(ValidationError):
            JinkouPatternEvaluation.model_validate(dict(id="P52", matched=value))
    JinkouPatterns.model_validate({"scope": reference()["metadata"]["scope"]})
