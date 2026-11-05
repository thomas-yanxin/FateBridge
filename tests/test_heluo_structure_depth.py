"""One literal Jian structural paragraph, distinct from derived operator coverage."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.core.heluo_structure as structure
from fatebridge.core.heluo import gua_lines, judge
from fatebridge.core.heluo_hexagrams import _gua_tables
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.core.output_numerology import HeluoBodyStructure, HeluoStructurePhase
from fatebridge.utils.errors import NumerologySourceError
from tests.test_heluo_month_depth import chart_for
from tests.test_heluo_najia_depth import PILLARS

ROOT = Path(__file__).parent / "fixtures/heluo_structure_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text())


def test_literal_jian_paragraph_reproduces_eight_mixed_arity_records_and_reversal():
    case = REFERENCE["source_case"]
    row = structure.body_structure(chart_for(case["gua"]))["phases"][0]
    assert row["input_lines"] == case["lines"]
    assert row["record_count"] == len(row["records"]) == 8
    for actual, expected in zip(row["records"], case["bodies"]):
        assert actual == {
            "kind": expected["kind"],
            "arity": expected["arity"],
            "original_positions": expected["positions"],
            "lines": expected["bits"],
            "name": expected["name"],
        }
    assert row["whole_reversal"] == {
        "original_positions": case["whole_reversal"]["positions"],
        "lines": case["whole_reversal"]["bits"],
        "name": case["whole_reversal"]["name"],
    }
    assert row["literal_case_match"] is row["literal_names_reproduced"] is True
    assert [r["arity"] for r in row["records"]] == [3, 3, 3, 3, 3, 3, 6, 6]


@pytest.mark.parametrize("gua,parts", list(_gua_tables()[0].items()))
def test_64_derived_operator_applications_keep_original_positions_without_new_source_claims(
    gua, parts
):
    # Apply the manually frozen position maps. These 64 cases test operators,
    # not 64 additional passages of the classical text.
    chart = chart_for(gua)
    row = structure.body_structure(chart)["phases"][0]
    bits = gua_lines(parts["up"], parts["low"])
    for actual, shape in zip(row["records"], REFERENCE["source_case"]["bodies"]):
        assert actual["original_positions"] == shape["positions"]
        assert actual["lines"] == [bits[p - 1] for p in shape["positions"]]
    assert row["whole_reversal"]["lines"] == bits[::-1]
    assert sorted(row["whole_reversal"]["lines"]) == sorted(bits)
    if gua != "風山漸":
        assert row["literal_case_match"] is False
        assert row["literal_names_reproduced"] is None
        assert "not_this_hexagrams_literal_source_example" in row["source_application"]
    HeluoStructurePhase.model_validate(row)


def test_jian_coincidence_does_not_allow_complement_instead_of_reversal():
    # Jian's complement happens to equal its whole reversal. Qian exposes the
    # wrong implementation even though that original example alone would pass.
    qian = structure.body_structure(chart_for("乾為天"))["phases"][0]
    assert qian["whole_reversal"]["name"] == "乾為天"
    assert qian["whole_reversal"]["lines"] != [0, 0, 0, 0, 0, 0]
    assert len(qian["records"]) == 8  # repeated names must not be deduplicated
    jian = structure.body_structure(chart_for("風山漸"))["phases"][0]
    assert jian["records"][2]["name"] == "震"  # reverse Gen, not complement Dui
    assert jian["records"][6]["name"] == "天地否"  # move, not flip, line three
    assert jian["records"][7]["original_positions"] == [6, 5, 3, 2, 1, 4]


def test_phase_separation_yuantang_independence_and_existing_nayin_qi_stability():
    chart = chart_for("風山漸")
    chart["hou"] = deepcopy(chart_for("雷澤歸妹")["hou"])
    a = judge(chart, PILLARS, "卯")
    chart["xian"]["yuan"] = 1
    chart["hou"]["yuan"] = 6
    b = judge(chart, PILLARS, "卯")
    assert a["body_structure"] == b["body_structure"]
    assert a["body_structure"]["phases"][0]["literal_case_match"] is True
    assert a["body_structure"]["phases"][1]["literal_case_match"] is False
    for key in ["deTi", "qi_phases", "xie", "yuan", "huagong"]:
        assert a[key] == b[key]


def test_actual_same_run_trace_and_snapshot_copy_the_structure_without_global_verdict():
    data = build_heluo_result(
        date="1990-12-13",
        time="01:30",
        zone="Asia/Shanghai",
        gender="女",
        use_true_solar_time=False,
    )
    actual = data["judge"]["body_structure"]
    trace = next(
        r["facts"]
        for r in data["numerology_evidence"]["rule_trace"]
        if r["rule_id"] == structure.RULESET_ID
    )
    assert actual == trace
    assert [r["literal_case_match"] for r in actual["phases"]] == [True, False]
    assert (
        "先天·風山漸：艮、巽、震、兌、離、坎、天地否、地天泰" in data["snapshot_text"]
    )
    assert (
        actual["five_ming_terminology"]["symbol_readings"]
        == REFERENCE["five_ming_symbol_readings"]
    )
    assert actual["five_ming_terminology"]["selected_pillar"] is None
    assert actual["complete_assessment"] is actual["complete_futi_assessment"] is False
    actual["phases"][0]["records"][0]["lines"][0] = 1
    assert trace["phases"][0]["records"][0]["lines"] == [0, 0, 1]


@pytest.mark.parametrize(
    "mutation",
    [
        {"records": []},
        {"record_count": 6},
        {"literal_case_match": False},
        {"literal_names_reproduced": False},
        {
            "source_application": "permutation_derivation; not_this_hexagrams_literal_source_example"
        },
        {"input_lines": [1] * 6},
        {"whole_reversal": {"original_positions": [1, 2, 3, 4, 5, 6]}},
        {"whole_reversal": {"lines": [0] * 6, "name": "坤為地"}},
    ],
)
def test_contract_rejects_same_phase_and_source_claim_contradictions(mutation):
    row = structure.body_structure(chart_for("風山漸"))["phases"][0]
    row.update(mutation)
    with pytest.raises(ValidationError):
        HeluoStructurePhase.model_validate(row)


@pytest.mark.parametrize(
    "mutation",
    [
        {"original_positions": [3, 1, 2]},
        {"arity": 6},
        {"name": "兌"},
        {"lines": [True, False, False]},
        {"lines": [1, 1, 0], "name": "兌"},
    ],
)
def test_contract_rejects_wrong_operator_and_coherent_but_wrong_phase_bits(mutation):
    row = structure.body_structure(chart_for("風山漸"))["phases"][0]
    row["records"][2].update(mutation)
    with pytest.raises(ValidationError):
        HeluoStructurePhase.model_validate(row)


def test_projection_does_not_invent_missing_line_facts():
    output = HeluoBodyStructure.model_validate(
        {"phases": [{"phase": "hou", "whole_reversal": {"name": "雷澤歸妹"}}]}
    )
    assert output.phases[0].input_lines is None


def test_audit_rejects_complement_that_would_pass_jian_alone(monkeypatch):
    from scripts import audit_numerology as audit

    original = audit.body_structure

    def wrong(chart):
        result = original(chart)
        result["phases"][1]["whole_reversal"] = {
            "original_positions": [6, 5, 4, 3, 2, 1],
            "lines": [0, 0, 0, 0, 0, 0],
            "name": "坤為地",
        }
        return result

    monkeypatch.setattr(audit, "body_structure", wrong)
    result = audit.body_structure_checks()
    assert result["checks_passed"] is False
    assert any(
        x["kind"] == "structure_reversal_not_complement" for x in result["failures"]
    )


def test_terminology_copy_cannot_modify_cached_source():
    result = structure.body_structure(chart_for("風山漸"))
    result["five_ming_terminology"]["symbol_readings"]["金"] = "changed"
    assert (
        structure.body_structure(chart_for("風山漸"))["five_ming_terminology"][
            "symbol_readings"
        ]["金"]
        == "庚辛申酉"
    )
    variants = json.loads((ROOT / "variants.json").read_text())["wording_variants"]
    assert result["wording_variants"] == variants
    result["wording_variants"][0]["primary_reading"] = "changed"
    assert structure.body_structure(chart_for("風山漸"))["wording_variants"] == variants


@pytest.mark.parametrize(
    "change",
    [
        {"ruleset_id": "wrong"},
        {"source_case_gua": "乾為天"},
        {"source_case_names": []},
        {"source_case_reversed_name": "坤為地"},
        {"five_ming_symbol_readings": {}},
        {"wording_variants": []},
    ],
)
def test_bad_source_is_a_source_fault_and_cached_source_metadata_is_not_mutable(
    tmp_path, monkeypatch, change
):
    data = json.loads(structure.SOURCE_PATH.read_text())
    data.update(change)
    path = tmp_path / "source.json"
    path.write_text(json.dumps(data))
    structure._source.cache_clear()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(structure, "SOURCE_PATH", path)
            with pytest.raises(NumerologySourceError):
                structure.body_structure(chart_for("風山漸"))
    finally:
        structure._source.cache_clear()


def test_source_witnesses_and_old_references_have_not_been_rewritten():
    for w in REFERENCE["witnesses"]:
        assert (
            hashlib.sha256((ROOT / w["file"]).read_bytes()).hexdigest() == w["sha256"]
        )
    for path, digest in REFERENCE["prior_reference_hashes"].items():
        assert (
            hashlib.sha256((ROOT.parents[2] / path).read_bytes()).hexdigest() == digest
        )
    assert REFERENCE["new_structural_examples"] == 1
    assert (
        REFERENCE["new_complete_natal_examples"]
        == REFERENCE["new_independent_calendar_instants"]
        == REFERENCE["independent_second_reviews"]
        == 0
    )


@pytest.mark.parametrize("bad", [[True] * 6, [1, 1, 1], [2] * 6, "000111"])
def test_structural_inputs_cannot_be_guessed_or_coerced(bad):
    chart = chart_for("風山漸")
    chart["xian"]["lines"] = bad
    with pytest.raises(ValueError):
        structure.body_structure(chart)
