"""Retain complete failed candidate study and every declared negative gate."""

import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.validation.bazi_source_corpus import (
    case_strength_constraints,
    strength_annotation,
)

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-controller-root-load-v1"


def saved(name):
    p = STUDY / name
    raw = p.read_bytes()
    if p.suffix == ".gz":
        assert (
            hashlib.sha256(raw).hexdigest()
            == (
                p.with_suffix(".gz.sha256")
                if name == "corpus-nested-constraints-first.json.gz"
                else p.with_suffix(".sha256")
            )
            .read_text()
            .strip()
        )
        return json.loads(gzip.decompress(raw))
    return json.loads(raw)


@pytest.mark.parametrize(
    "constraints",
    [
        None,
        "weak",
        [1],
        [{"forbidden_strengths": []}],
        [{"forbidden_strengths": ["旺"]}],
        [{"forbidden_strengths": [{}]}],
        [{"forbidden_strengths": [True]}],
        [{"case_id": "other", "forbidden_strengths": ["弱"]}],
    ],
)
def test_invalid_nested_constraints_cannot_be_silently_discarded(constraints):
    with pytest.raises(ValueError):
        case_strength_constraints(
            {
                "id": "case",
                "expected_strength": None,
                "negative_constraints": constraints,
            }
        )


def test_bound_is_preserved_without_inventing_an_exact_source_grade():
    case = {
        "id": "case",
        "expected_strength": None,
        "negative_constraints": [
            {"forbidden_strengths": ["弱"], "source_anchor": "非身弱論也"}
        ],
    }
    before = deepcopy(case)
    rows = case_strength_constraints(case)
    assert rows == [
        {
            "case_id": "case",
            "forbidden_strengths": ["弱"],
            "source_anchor": "非身弱論也",
        }
    ]
    assert strength_annotation(case) == ("explicitly_unknown_body_strength", None)
    rows[0]["forbidden_strengths"].clear()
    assert case == before


def test_complete_corpus_includes_nested_constraint_and_preserves_old361():
    result = saved("corpus-nested-constraints-first.json.gz")
    p = (
        ROOT
        / "docs/validation/bazi-capacity-caid-fenyu-enyuan-v1/source-corpus-first-v7.json.gz"
    )
    before = json.loads(gzip.decompress(p.read_bytes()))
    assert result["groups"] == before["groups"]
    assert result["record_count"] == 361
    claims = result["local_and_negative_claims"]
    assert [r for r in claims if "annotation_location" not in r] == before[
        "local_and_negative_claims"
    ]
    nested = [r for r in claims if "annotation_location" in r]
    assert len(nested) == 1
    assert nested[0]["annotation"]["case_id"] == "DTCW1947-SJ05"
    assert nested[0]["annotation"]["forbidden_strengths"] == ["弱"]
    assert nested[0]["matches"] is False
    assert result["classical_acceptance_passed"] is False


def test_complete_candidate_and_prespecified_new_units_cannot_be_promoted():
    development = saved("development-first.json.gz")
    prospective = saved("prospective-first.json.gz")
    closed = saved("constraints-closed-assessment.json")
    reference = saved("reference.json")
    assert (
        development["row_count"],
        development["known"],
        development["unknown_retained"],
    ) == (361, 121, 240)
    assert len(development["summary"]["candidate"]["improvements"]) == 7
    assert development["summary"]["candidate"]["regressions"] == []
    assert len(prospective["rows"]) == 6
    assert sum(r["unit"] == "清氣" for r in prospective["rows"]) == 3
    assert sum(r["unit"] == "濁氣" for r in prospective["rows"]) == 3
    assert (prospective["known_exact"], prospective["unknown_exact_retained"]) == (2, 4)
    assert prospective["counts"]["candidate"]["new_exact_corrections"] == []
    assert prospective["combined_adoption_gates_passed"] is False
    assert prospective["adopted"] is False
    assert closed["all_declared_negative_constraints_evaluated"] == 2
    assert closed["combined_adoption_gates_passed"] is False
    assert next(r for r in reference["cases"] if r["id"] == "DTCW1947-QQ-03")[
        "pages"
    ] == [238, 239]
    missing = next(r for r in prospective["rows"] if r["id"] == "DTCW1947-QQ-01")
    assert missing["retained_expected_strength"] == "强"
    assert (
        missing["baseline"]["strength_level"]
        == missing["candidate"]["strength_level"]
        == "弱"
    )
    assert prospective["bounded_claims"][0]["candidate_matches"] is False


def test_reference_freeze_covers_every_page_and_keeps_unrelated_exposure_separate():
    freeze = saved("reference-freeze.json")
    for rel, h in freeze["files"].items():
        assert hashlib.sha256((STUDY / rel).read_bytes()).hexdigest() == h
    assert freeze["before_any_selected_unit_computation"] is True
    assert freeze["all_cases"] == 6
    assert len([p for p in freeze["files"] if p.startswith("source-pages/")]) == 8
