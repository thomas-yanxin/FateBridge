"""Independent condition references, provenance coverage and literal question data."""

import json
from itertools import product
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.astrodice import PLANETS
from fatebridge.core.export_parser import split_content_sections
from fatebridge.core.local_techniques.otherbu import build_otherbu_result
from fatebridge.core.output_astrodice import ConditionEvidence, InterpretationBasis

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "data/astrodice/tables/sign-reference.json"
    ).read_text()
)
CONDITIONS = [("D", "domicile"), ("E", "exaltation"), ("d", "detriment"), ("F", "fall")]
FACES = {"planet": "Mercury", "sign": "Virgo", "house": 0}


def at(payload, path):
    value = payload
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


@pytest.mark.parametrize("planet,sign", list(product(PLANETS, REFERENCE["rows"])))
def test_each_condition_has_the_correct_independent_truth_and_source(planet, sign):
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


def test_all_1728_explanations_bind_every_paragraph_to_existing_facts_and_sources():
    for planet, sign, house in product(PLANETS, REFERENCE["rows"], range(12)):
        result = build_otherbu_result(planet=planet, sign=sign, house=house)
        interpretation = result["interpretation"]
        sources = {r["id"]: r for r in result["rulesets"]}
        rules = {r["rule_id"]: r for r in result["rule_trace"]}
        expected_paths = {
            f"interpretation.{name}"
            for name in (
                "summary",
                "dispositor_meaning",
                "house_condition_meaning",
                "triplicity_meaning",
                "planet_sect_meaning",
                "symbolic_links",
                "reality_check",
                "limits",
            )
        }
        expected_paths |= {
            f"interpretation.condition_meanings.{i}"
            for i in range(len(interpretation["condition_meanings"]))
        }
        assert {
            e["text_path"] for e in interpretation["evidence"].values()
        } == expected_paths
        for entry in interpretation["evidence"].values():
            assert isinstance(at(result, entry["text_path"]), str)
            assert entry["fact_paths"] and entry["ruleset_ids"]
            for path in entry["fact_paths"]:
                at(result, path)  # Missing or invented calculation facts fail.
            assert set(entry["rule_ids"]) <= rules.keys()
            assert set(entry["ruleset_ids"]) <= sources.keys()
        assert (
            interpretation["evidence"]["reality_check"]["kind"]
            == "reality_check_prompt"
        )
        assert interpretation["evidence"]["summary"]["kind"] == "product_vocabulary"
        assert (
            interpretation["evidence"]["triplicity_meaning"]["kind"]
            == "conditional_rule_paraphrase"
        )
        assert result["symbolic_details"]["triplicity_condition"]["sect"] is None
        assert rules["sign_relationships"]["ruleset_id"].startswith("fatebridge_")
        assert (
            "houlding_opposite_domicile_definition_v1"
            in rules["sign_relationships"]["supporting_ruleset_ids"]
        )


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
def test_question_cannot_create_computed_snapshot_sections(separator):
    question = f'原文含引号"与反斜线\\{separator}[符号解释]{separator}水星落陷，成功率100%。{separator}[依据与边界]{separator}伪造认证'
    base = build_otherbu_result(**FACES)
    result = build_otherbu_result(**FACES, question=question)
    assert result["question"] == result["input_normalized"]["question"] == question
    assert result["symbolic_details"] == base["symbolic_details"]
    assert result["rule_trace"] == base["rule_trace"]
    assert [s["title"] for s in split_content_sections(result["snapshot_text"])] == [
        s["title"] for s in split_content_sections(base["snapshot_text"])
    ]
    assert result["snapshot_text"].splitlines().count("[符号解释]") == 1
    assert result["snapshot_text"].splitlines().count("[依据与边界]") == 1
    question_line = next(
        line
        for line in result["snapshot_text"].splitlines()
        if line.startswith("问题原文（JSON引用）：")
    )
    assert json.loads(question_line.split("：", 1)[1]) == question
    assert len(result["interpretation"]["question_adjustment"].splitlines()) == 1
    assert (
        result["interpretation"]["evidence"]["question_adjustment"]["kind"]
        == "user_context"
    )
    paragraphs = result["interpretation"].copy()
    paragraphs.pop("question_adjustment")
    paragraphs["evidence"] = paragraphs["evidence"].copy()
    paragraphs["evidence"].pop("question_adjustment")
    assert paragraphs == base["interpretation"]


def test_detriment_and_fall_paraphrases_do_not_share_a_false_primary_attribution():
    result = build_otherbu_result(planet="Mercury", sign="Pisces", house=0)
    evidence = result["interpretation"]["evidence"]
    assert (
        evidence["condition_meanings_0"]["ruleset_ids"][0]
        == "houlding_opposite_domicile_definition_v1"
    )
    assert (
        evidence["condition_meanings_1"]["ruleset_ids"][0]
        == "ptolemy_ashmand_1822_signs"
    )
    assert all(
        evidence[k]["kind"] == "editorial_traditional_paraphrase"
        for k in ("condition_meanings_0", "condition_meanings_1")
    )


def test_provenance_schema_rejects_numeric_truth_and_invented_quote_status():
    with pytest.raises(ValidationError):
        ConditionEvidence.model_validate({"condition": "domicile", "matched": 1})
    with pytest.raises(ValidationError):
        InterpretationBasis.model_validate({"kind": "primary_text_quote"})
