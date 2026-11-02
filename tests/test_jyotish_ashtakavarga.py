"""Pre-implementation primary facts and pinned external counts, never outcomes."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish import build_india, topic_evidence
from fatebridge.core.jyotish_ashtakavarga import (
    HOUSE_ROWS,
    REFERENCES,
    RULE,
    SOURCE,
    SampleGrid,
    calculate,
)
from fatebridge.core.output_jyotish import JyotishIndia
from tests.fixtures.surface_payloads import astro_payload

FIXTURES = Path(__file__).parent / "fixtures"
PRIMARY_BYTES = (FIXTURES / "jyotish-ashtakavarga-primary.json").read_bytes()
ORACLE_BYTES = (FIXTURES / "jyotish-ashtakavarga-oracle.json").read_bytes()
PRIMARY = json.loads(PRIMARY_BYTES)
ORACLE = json.loads(ORACLE_BYTES)


def resolve(body, path):
    for part in path.split("."):
        body = body[int(part)] if isinstance(body, list) else body[part]
    return body


def test_preimplementation_references_and_all_768_literal_cells_are_unchanged():
    assert (
        hashlib.sha256(PRIMARY_BYTES).hexdigest()
        == "702f1dc3798c3f56bde06bdbb6a797fe607aac04208f499761698bd56facfd13"
    )
    assert (
        hashlib.sha256(ORACLE_BYTES).hexdigest()
        == "a1cc4852befaec643ca5a12a6b0c8bd7ab3a3088660f43bba858512c35889d69"
    )
    assert SOURCE["sha256"] == PRIMARY["source"]["pdf_sha256"]
    for target, rows in zip(REFERENCES, HOUSE_ROWS):
        assert [[int(v) for v in row] for row in rows] == PRIMARY[
            "binary_house_tables"
        ][target]


@pytest.mark.parametrize("case", ORACLE["rows"], ids=lambda c: c["name"])
def test_all_preimplementation_external_outputs_match_exactly(case):
    result = calculate(case["signs"])
    assert result["prastara"] == case["PAV"]
    assert result["bhinna"] == case["BAV"]
    assert result["samudaya"] == case["SAV"]
    assert list(result["bhinna_totals"].values()) == [48, 49, 39, 54, 56, 52, 39, 49]
    assert result["samudaya_total"] == 337


def test_printed_example_and_mercury_prastara_preserve_the_authors_notation():
    chart = PRIMARY["chart6"]
    result = calculate(chart["input_sign_indices"])
    assert result["prastara"]["Mercury"] == chart["Mercury_PAV"]
    assert result["bhinna"]["Mercury"] == chart["Mercury_BAV"]
    assert result["samudaya"][0] == chart["Aries_SAV"] == 34
    example = calculate(dict.fromkeys(REFERENCES, 2))
    assert [
        i for i, v in enumerate(example["prastara"]["Jupiter"]["Venus"]) if v
    ] == sorted(PRIMARY["example37"]["benefic_sign_indices_in_source_order"])


@pytest.mark.parametrize("bad", [True, -1, 12, 1.0, "1", None, float("nan")])
def test_sign_inputs_cannot_be_boolean_missing_or_nonintegral(bad):
    signs = dict.fromkeys(REFERENCES, 0)
    signs["Moon"] = bad
    with pytest.raises(ValueError):
        calculate(signs)


def test_missing_and_extra_contributors_are_not_filled_or_counted():
    signs = dict.fromkeys(REFERENCES, 0)
    with pytest.raises(ValueError):
        calculate({k: v for k, v in signs.items() if k != "Ascendant"})
    with pytest.raises(ValueError):
        calculate({**signs, "Rahu": 0})


def test_grid_keeps_own_ascendant_column_instead_of_nominal_counts():
    grid = SampleGrid(["D1"])
    raw = {"longitudes": dict.fromkeys(REFERENCES[:7], 1.0), "ascendant": 29.9}
    grid.observe(-30.0, raw)
    grid.observe(0.0, raw)
    grid.observe(30.0, {**raw, "ascendant": 30.1})
    result = grid.result()
    assert result["sample_count"] == 3
    groups = result["charts"]["D1"]
    assert [g["sample_count"] for g in groups] == [2, 1]
    assert [g["contains_nominal"] for g in groups] == [True, False]
    for target, table in zip(REFERENCES, PRIMARY["binary_house_tables"].values()):
        old, new = groups
        for donor in REFERENCES[:7]:
            assert old["prastara"][target][donor] == new["prastara"][target][donor]
        expected = [row[7] for row in table]
        assert old["prastara"][target]["Ascendant"] == expected
        assert new["prastara"][target]["Ascendant"] == expected[-1:] + expected[:-1]
    with pytest.raises(ValueError):
        grid.observe(0.0, raw)


@pytest.fixture(scope="module")
def india():
    return build_india(
        build_astro_birth_info(**astro_payload(), preserve_instant=True),
        divisions=[2, 3, 7, 9, 10, 12, 30],
        birth_time_uncertainty_minutes=2,
    )


def test_every_returned_varga_has_typed_counts_and_resolving_nominal_claims(india):
    JyotishIndia.model_validate(india)
    av = india["ashtakavarga"]
    assert set(av["charts"]) == set(india["charts"])
    assert av["reductions_applied"] is False
    assert av["samudaya_targets"] == list(REFERENCES[:7])
    assert SOURCE["id"] in {s["id"] for s in india["rulesets"]}
    assert RULE in {r["rule_id"] for r in india["rule_trace"]}
    for name, packet in av["charts"].items():
        assert packet["chart_method"] == india["charts"][name]["method"]
        assert len(packet["input_claims"]) == 8
        for row in packet["input_claims"]:
            assert resolve({"india": india}, row["fact_path"]) == row["value"]
        assert packet["samudaya_total"] == 337
    variants = india["birth_time_sensitivity"]["ashtakavarga_variants"]
    assert (
        variants["sample_count"] == india["birth_time_sensitivity"]["sample_count"] == 9
    )
    for name, groups in variants["charts"].items():
        assert sum(g["sample_count"] for g in groups) == 9
        assert sum(g["contains_nominal"] for g in groups) == 1
        nominal = next(g for g in groups if g["contains_nominal"])
        for key in ["input_sign_indices", "prastara", "bhinna", "samudaya"]:
            assert nominal[key] == av["charts"][name][key]


def test_topic_counts_and_all_contribution_paths_resolve_in_same_result(india):
    found = []
    for topic in india["topic_evidence"].values():
        for factor in topic["factors"]:
            if factor["rule_id"] != RULE:
                continue
            found.append(factor)
            assert resolve({"india": india}, factor["fact_path"]) == factor["fact"]
            context = factor["calculation_context"]
            for row in [
                *context["scenarios"],
                *context["constraints"],
                *context["method_context"]["input_claims"],
            ]:
                assert resolve({"india": india}, row["fact_path"]) == row["value"]
            assert "名义生时" in factor["traditional_interpretation"]
    assert len(found) == 5


def test_mismatched_contributor_or_table_cannot_receive_faithful_topic_evidence(india):
    for key in ["bhinna", "prastara"]:
        bad = copy.deepcopy(india["ashtakavarga"])
        if key == "bhinna":
            bad["charts"]["D1"][key]["Sun"][0] += 1
        else:
            bad["charts"]["D1"][key]["Sun"]["Moon"][0] ^= 1
        with pytest.raises(ValueError, match="contradicts"):
            topic_evidence(india["charts"], ashtakavarga=bad)


@pytest.mark.parametrize(
    "field",
    [
        "input_claim_value",
        "input_claim_path",
        "chart_method",
        "chart_rule_ids",
        "source_id",
        "method_id",
        "reductions_applied",
        "reference_instant",
    ],
)
def test_mutated_provenance_cannot_borrow_valid_counts_for_false_source_claims(
    india, field
):
    bad = copy.deepcopy(india["ashtakavarga"])
    packet = bad["charts"]["D1"]
    if field == "input_claim_value":
        packet["input_claims"][0]["value"] = "invented-sign"
    elif field == "input_claim_path":
        packet["input_claims"][0]["fact_path"] = "invented.path"
    elif field == "chart_method":
        packet[field] = "invented-method"
    elif field == "chart_rule_ids":
        packet[field] = ["invented-rule"]
    elif field == "reductions_applied":
        bad[field] = True
    else:
        bad[field] = "invented-source-or-policy"
    with pytest.raises(ValueError, match="contradicts"):
        topic_evidence(india["charts"], ashtakavarga=bad)
