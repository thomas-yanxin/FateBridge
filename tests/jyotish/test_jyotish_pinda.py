"""Frozen full BAVs, literal source arithmetic and explicit missing rules."""

import copy
import hashlib
import itertools
import json
from pathlib import Path

import pytest

from fatebridge.core.jyotish_ashtakavarga import calculate
from fatebridge.core.jyotish_pinda import PLANETS, analyze, coowned, reduce_row

FIXTURES = Path(__file__).parents[1] / "fixtures"
PRIMARY_PATH = FIXTURES / "jyotish-pinda-primary.json"
FULL_PATH = FIXTURES / "jyotish-pinda-full-bav-reference.json"
PRIMARY = json.loads(PRIMARY_PATH.read_text())
FULL = json.loads(FULL_PATH.read_text())


def test_primary_and_full_expected_tables_remain_frozen_before_kernel():
    assert hashlib.sha256(PRIMARY_PATH.read_bytes()).hexdigest() == (
        "eb665bdad180ab8b08afeb377f77ca9c6f7dc055b490b11ddd946dad39632d83"
    )
    assert hashlib.sha256(FULL_PATH.read_bytes()).hexdigest() == (
        "080f343ca816b7ea45d62807e74d5abc9c00fc49afd3334465a350148a29f1c1"
    )


@pytest.mark.parametrize("case", FULL, ids=lambda c: c["name"])
def test_all_637_full_targets_and_source_missingness(case):
    signs = {p: case["signs"][p] for p in PLANETS}
    tables = calculate(case["signs"])["bhinna"]
    assert tables == case["bav"]
    before = copy.deepcopy((tables, signs))
    actual = analyze(tables, signs)
    assert (tables, signs) == before
    assert set(actual["targets"]) == set(PLANETS)
    assert actual["occupancy_planets"] == list(PLANETS)
    for planet, expected in case["targets"].items():
        row = actual["targets"][planet]
        for field in [
            "trikona",
            "sodhita",
            "rasi_pinda",
            "graha_pinda",
            "sodhya_pinda",
        ]:
            assert row[field] == expected[field], (case["name"], planet, field)
        assert row["status"] == (
            "partial_source_rule"
            if expected["unresolved"]
            else "computed_declared_occupancy"
        )
        assert [
            (a["sign_indices"], a["affected_empty_signs"], a["reason"])
            for a in row["source_ambiguities"]
        ] == [
            (a["pair"], [a["empty_sign"]], a["reason"]) for a in expected["unresolved"]
        ]
        assert len(row["trikona_steps"]) == 4
        assert len(row["coowned_steps"]) == 5
        assert len(row["graha_terms"]) == 7
        assert row["graha_pinda"] is not None
        # Coowned reductions change only empty signs. Agreement on graha pinda
        # therefore cannot establish correctness of the coowned/rasi stage.
        assert all(
            term["count"] == row["trikona"][term["sign_index"]]
            for term in row["graha_terms"]
        )


@pytest.mark.parametrize("example", PRIMARY["coowned_example42"], ids=lambda e: e["id"])
def test_all_literal_example42_pairs(example):
    signs = dict.fromkeys(PLANETS, 4)
    for index, sign in enumerate(["Taurus", "Libra"]):
        for planet in example["occupants"][sign]:
            signs[planet] = example["pair"][index]
    row = [0] * 12
    for sign, value in zip(example["pair"], example["before"]):
        row[sign] = value
    result, _ = coowned(row, signs)
    assert [result[i] for i in example["pair"]] == example["after"]


def test_mercury_literal_examples40_41_43_preserve_multiple_occupants():
    example = PRIMARY["mercury_examples40_41_43"]
    row = reduce_row(
        example["unreduced_BAV"],
        {p: example["given_signs_from_prior_chart6_reference"][p] for p in PLANETS},
    )
    assert row["trikona"] == row["sodhita"] == example["after_trikona"]
    assert [row[p] for p in ["rasi_pinda", "graha_pinda", "sodhya_pinda"]] == [
        77,
        75,
        152,
    ]
    assert row["rasi_terms"] == [21, 10, 24, 0, 0, 0, 0, 0, 0, 0, 22, 0]
    assert [term["product"] for term in row["graha_terms"]] == [15, 0, 24, 15, 0, 21, 0]


def test_all_729_trinal_triples_preserve_pairwise_differences_and_zero_footnote():
    for values in itertools.product(range(9), repeat=3):
        original = [0] * 12
        original[0], original[4], original[8] = values
        output = reduce_row(original, dict.fromkeys(PLANETS, 3))["trikona"]
        triple = [output[0], output[4], output[8]]
        assert 0 in triple and all(v >= 0 for v in triple)
        if 0 in values:
            assert triple == list(values)
        if len(set(values)) == 1:
            assert triple == [0, 0, 0]
        for i, j in itertools.combinations(range(3), 2):
            assert triple[i] - triple[j] == values[i] - values[j]


def test_equal_single_occupied_source_gap_is_not_zero_or_a_hidden_default():
    # A transformation unit input, not a claim that this is a full natal BAV.
    row = [0] * 12
    row[0] = row[7] = 2
    signs = {**dict.fromkeys(PLANETS, 4), "Sun": 0}
    result = reduce_row(row, signs)
    assert result["sodhita"][0] == 2
    assert result["sodhita"][7] is None
    assert result["rasi_pinda"] is None
    assert result["graha_pinda"] == 10
    assert result["sodhya_pinda"] is None
    assert result["status"] == "partial_source_rule"
    assert result["source_ambiguities"][0]["affected_empty_signs"] == [7]


@pytest.mark.parametrize(
    "values",
    [
        [],
        [0] * 11,
        [0] * 13,
        [True] * 12,
        [-1] + [0] * 11,
        [9] + [0] * 11,
        [0.5] + [0] * 11,
    ],
)
def test_invalid_count_domains_are_rejected(values):
    with pytest.raises(ValueError, match="twelve integer"):
        reduce_row(values, dict.fromkeys(PLANETS, 0))


@pytest.mark.parametrize(
    "change", ["missing", "extra", "bool", "float", "negative", "outside"]
)
def test_invalid_occupant_identity_and_signs_are_rejected(change):
    signs = dict.fromkeys(PLANETS, 0)
    if change == "missing":
        del signs["Sun"]
    elif change == "extra":
        signs["Rahu"] = 0
    else:
        signs["Sun"] = {"bool": True, "float": 1.0, "negative": -1, "outside": 12}[
            change
        ]
    with pytest.raises(ValueError, match="exactly seven"):
        reduce_row([0] * 12, signs)


def test_unreduced_total_and_target_contract_rejects_mutated_full_table():
    signs = FULL[0]["signs"]
    tables = calculate(signs)["bhinna"]
    tables["Sun"][0] += 1
    with pytest.raises(ValueError, match="unreduced Rao BAV totals"):
        analyze(tables, {p: signs[p] for p in PLANETS})
    tables = calculate(signs)["bhinna"]
    tables["Rahu"] = tables["Sun"]
    with pytest.raises(ValueError, match="targets"):
        analyze(tables, {p: signs[p] for p in PLANETS})


def test_typed_partial_row_keeps_null_distinct_from_zero():
    from fatebridge.core.output_jyotish import PindaRow

    values = [0] * 12
    values[0] = values[7] = 2
    row = reduce_row(values, {**dict.fromkeys(PLANETS, 4), "Sun": 0})
    typed = PindaRow.model_validate(row).model_dump(mode="json", exclude_unset=True)
    assert typed == row
    assert "sodhya_pinda" in typed and typed["sodhya_pinda"] is None
    assert typed["graha_pinda"] == 10


def test_every_returned_varga_and_own_birth_grid_has_declared_reductions():
    from fatebridge.core.astro.birth import build_astro_birth_info
    from fatebridge.core.jyotish import build_india
    from fatebridge.core.jyotish_ashtakavarga import RULE as BAV_RULE
    from fatebridge.core.jyotish_ashtakavarga import chart_inputs
    from fatebridge.core.jyotish_pinda import RULE, SOURCE
    from fatebridge.core.output_jyotish import JyotishIndia
    from tests.fixtures.surface_payloads import astro_payload

    india = build_india(
        build_astro_birth_info(**astro_payload(), preserve_instant=True),
        divisions=[2, 3, 7, 9, 10, 12, 30],
        birth_time_uncertainty_minutes=1,
    )
    assert india["profile"]["ruleset_id"] == "parashari_lahiri_core_v29"
    assert SOURCE["id"] in {s["id"] for s in india["rulesets"]}
    assert RULE in {r["rule_id"] for r in india["rule_trace"]}
    typed = JyotishIndia.model_validate(india).model_dump(
        mode="json", exclude_unset=True
    )
    groups = india["birth_time_sensitivity"]["ashtakavarga_variants"]["charts"]
    for name, chart in india["charts"].items():
        packet = india["ashtakavarga"]["charts"][name]
        analysis = packet["reduction_analysis"]
        assert analysis == typed["ashtakavarga"]["charts"][name]["reduction_analysis"]
        signs = chart_inputs(chart)
        assert analysis["input_sign_indices"] == {p: signs[p] for p in PLANETS}
        assert (
            analysis["targets"]
            == analyze(packet["bhinna"], analysis["input_sign_indices"])["targets"]
        )
        assert analysis["basis_bhinna_rule_id"] == BAV_RULE
        assert (
            analysis["bhinna_fact_path"] == f"india.ashtakavarga.charts.{name}.bhinna"
        )
        assert packet["samudaya_total"] == 337
        for sample in groups[name]:
            own = sample["reduction_analysis"]
            assert "bhinna_fact_path" not in own
            assert (
                own["targets"]
                == analyze(
                    sample["bhinna"],
                    {p: sample["input_sign_indices"][p] for p in PLANETS},
                )["targets"]
            )


def test_ascendant_grid_crossing_changes_its_own_count_basis_not_occupancy():
    from fatebridge.core.jyotish_ashtakavarga import SampleGrid

    positions = PRIMARY["mercury_examples40_41_43"][
        "given_signs_from_prior_chart6_reference"
    ]
    grid = SampleGrid(["D1"])
    for offset, ascendant in [(0, 5 * 30 + 29.9), (30, 6 * 30 + 0.1)]:
        grid.observe(
            offset,
            {
                "ascendant": ascendant,
                "longitudes": {p: positions[p] * 30 + 1 for p in PLANETS},
            },
        )
    a, b = grid.result()["charts"]["D1"]
    assert (
        a["reduction_analysis"]["input_sign_indices"]
        == b["reduction_analysis"]["input_sign_indices"]
    )
    assert a["bhinna"] != b["bhinna"]
    assert a["reduction_analysis"]["targets"] != b["reduction_analysis"]["targets"]
    assert a["contains_nominal"] and not b["contains_nominal"]
