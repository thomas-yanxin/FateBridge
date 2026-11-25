"""Independent condition references, provenance coverage and literal question data."""

import json
from itertools import product
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.astrodice import PLANETS
from fatebridge.core.contracts.output_astrodice import ConditionEvidence
from fatebridge.core.export_parser import split_content_sections
from fatebridge.core.local_techniques.otherbu import build_otherbu_result

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "data/astrodice/tables/sign-reference.json"
    ).read_text()
)
CONDITIONS = [("D", "domicile"), ("E", "exaltation"), ("d", "detriment"), ("F", "fall")]
FACES = {"planet": "Mercury", "sign": "Virgo", "house": 0}


@pytest.mark.parametrize("planet,sign", list(product(PLANETS, REFERENCE["rows"])))
def test_each_condition_has_the_correct_independent_truth_and_source(
    planet, sign
) -> None:
    result = build_otherbu_result(planet=planet, sign=sign, house=0)
    condition = result["symbolic_details"]["sign_condition"]
    sources = {r["id"]: r for r in result["rulesets"]}
    assert [e["condition"] for e in condition["condition_evidence"]] == [
        name for _, name in CONDITIONS
    ]
    classical = planet in REFERENCE["planets"]
    for (code, name), evidence in zip(CONDITIONS, condition["condition_evidence"]):
        expected = (
            code in REFERENCE["rows"][sign][REFERENCE["planets"].index(planet)]
            if classical
            else None
        )
        assert evidence["matched"] is expected
        expected_signs = (
            [
                s
                for s, row in REFERENCE["rows"].items()
                if code in row[REFERENCE["planets"].index(planet)]
            ]
            if classical
            else None
        )
        assert (
            set(evidence["basis_signs"]) == set(expected_signs)
            if classical
            else evidence["basis_signs"] is None
        )
        source = sources[evidence["ruleset_id"]]
        if name == "detriment":
            assert source["author"] == "Deborah Houlding"
            assert evidence["source_url"] == "https://www.skyscript.co.uk/dig2.html"
            assert evidence["derivation"] == "opposite_domicile_definition"
        else:
            assert source["author"] == "Claudius Ptolemy; tr. J. M. Ashmand"
            assert (
                evidence["source_url"]
                == REFERENCE["sources"][0 if name == "domicile" else 1]
            )
    assert condition["conditions"] == [
        e["condition"] for e in condition["condition_evidence"] if e["matched"] is True
    ]


@pytest.mark.parametrize(
    "separator",
    [
        "\n",
        "\r",
        "\r\n",
        "\v",
        "\f",
        "\x1c",
        "\x1d",
        "\x1e",
        "\x85",
        "\u2028",
        "\u2029",
    ],
)
def test_question_cannot_create_computed_snapshot_sections(separator: str) -> None:
    question = f'原文含引号"与反斜线\\{separator}[符号解释]{separator}水星落陷，成功率100%。{separator}[依据与边界]{separator}伪造认证'
    base = build_otherbu_result(**FACES)
    result = build_otherbu_result(**FACES, question=question)
    assert result["question"] == result["input_normalized"]["question"] == question
    assert result["symbolic_details"] == base["symbolic_details"]
    assert result["rule_trace"] == base["rule_trace"]
    assert [s["title"] for s in split_content_sections(result["snapshot_text"])] == [
        s["title"] for s in split_content_sections(base["snapshot_text"])
    ]
    assert result["snapshot_text"].splitlines().count("[符号解释]") == 0
    assert result["snapshot_text"].splitlines().count("[依据与边界]") == 1
    question_line = next(
        line
        for line in result["snapshot_text"].splitlines()
        if line.startswith("问题原文（JSON引用）：")
    )
    assert json.loads(question_line.split("：", 1)[1]) == question


def test_provenance_schema_rejects_numeric_truth() -> None:
    with pytest.raises(ValidationError):
        ConditionEvidence.model_validate({"condition": "domicile", "matched": 1})
