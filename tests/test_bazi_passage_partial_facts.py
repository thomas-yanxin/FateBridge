"""Known physical facts survive partial projection; no force inference."""

import copy
import hashlib
import itertools
import json
import runpy
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.classical_passage import build_passage_evidence
from fatebridge.core.output_classical_passage import (
    ClassicalPassage,
    PassageNode,
    PassagePath,
)
from fatebridge.core.output_passage_relations import PassageRelationContext
from fatebridge.core.passage_relations import build_passage_relation_context

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/data/bazi_month_passage_next_v1"
CASES = json.loads((FIXTURE / "first-independent-counterexamples.json").read_bytes())[
    "cases"
]
REFERENCE_PATH = FIXTURE / "independent_reference.py"
REFERENCE = runpy.run_path(str(REFERENCE_PATH))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_all_first_counterexamples_and_valid_controls(case):
    before = copy.deepcopy(case["value"])
    model = {"path": PassagePath, "node": PassageNode, "passage": ClassicalPassage}[
        case["model"]
    ]
    if case["expected_accept"]:
        value = model.model_validate(case["value"])
        assert value.model_dump(exclude_unset=True) == before
    else:
        with pytest.raises(ValidationError):
            model.model_validate(case["value"])
    assert case["value"] == before


def accepted(value):
    try:
        PassagePath.model_validate(value)
    except ValidationError:
        return False
    return True


def test_literal_reference_is_frozen_and_every_visible_stem_triple_agrees():
    assert (
        hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest()
        == Path(str(REFERENCE_PATH) + ".sha256").read_text().strip()
    )
    elements = "木火土金水"
    glyphs = REFERENCE["STEMS"]
    for stems in itertools.product(glyphs, repeat=3):
        value = dict(
            zip(
                ("from_node", "via_node", "to_node"),
                (f"{p}:stem:{s}" for p, s in zip(REFERENCE["PILLARS"], stems)),
            )
        )
        indexes = [elements.index(glyphs[s]) for s in stems]
        expected = indexes == [(indexes[0] + offset) % 5 for offset in range(3)]
        assert accepted(value) == expected, value


def test_all_pillar_layer_and_principal_combinations_match_literal_physical_reference():
    for positions, planes, principal in itertools.product(
        itertools.product(REFERENCE["PILLARS"], repeat=3),
        itertools.product(("stem", "hidden"), repeat=3),
        (None, True, False),
    ):
        value = dict(
            zip(
                ("from_node", "via_node", "to_node"),
                (
                    f"{p}:{plane}:{s}"
                    for p, plane, s in zip(positions, planes, "甲丙戊")
                ),
            )
        )
        if principal is not None:
            value["principal_hidden_only"] = principal
        assert accepted(value) == REFERENCE["possible_path"](value), value


@pytest.mark.parametrize("kind", ["未来未分类关系", "天干合", "六合", "三合", "六冲"])
def test_binding_uses_the_same_classification_as_retained_relation_context(kind):
    pillars = dict(
        year=("甲", "辰"), month=("己", "卯"), day=("庚", "申"), hour=("乙", "酉")
    )
    assessment = {
        "relations": [
            {"kind": kind, "positions": ["year", "month"], "status": "binding"}
        ]
    }
    before = copy.deepcopy(assessment)
    passage = build_passage_evidence(pillars, assessment)
    context = build_passage_relation_context(passage, assessment)
    ClassicalPassage.model_validate(passage)
    PassageRelationContext.model_validate(context)
    plane = context["events"][0]["plane"]
    for node in passage["nodes"]:
        expected = node["pillar"] in {"year", "month"} and (
            (node["plane"] == "stem" and plane == "stem")
            or (node["plane"] == "hidden" and plane == "branch")
        )
        assert (node["binding_state"] == "binding_recorded") == expected
    assert context["unclassified_event_refs"] == (
        ["assessment.relations:0"] if plane == "unclassified" else []
    )
    assert passage["summary"]["effective_passage"] == "not_adjudicated"
    assert passage["summary"]["calculation_effect"] == "none"
    assert assessment == before
