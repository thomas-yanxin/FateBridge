"""Own Aiyar raw-table chain, with the six Rao differences retained."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import jyotish_aiyar_ashtakavarga as aiyar
from fatebridge.core import jyotish_ashtakavarga as rao
from fatebridge.core import jyotish_pinda as pinda
from fatebridge.core.output_jyotish import AiyarBavProfile

FIXTURES = Path(__file__).parents[1] / "fixtures"
PRIMARY_PATH = FIXTURES / "jyotish-aiyar-seven-bav-primary.json"
REFERENCE_PATH = FIXTURES / "jyotish-aiyar-seven-bav-full-chain-reference.json"
PRIMARY = json.loads(PRIMARY_PATH.read_text())
REFERENCE = json.loads(REFERENCE_PATH.read_text())


def test_original_transcription_and_preimplementation_full_chain_are_frozen():
    assert (
        hashlib.sha256(PRIMARY_PATH.read_bytes()).hexdigest()
        == "b18e3da44d7c6dded9e3050201a41a19d70f06f29a4d2abbde1abda7dbbdd7da"
    )
    assert (
        hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest()
        == "5ce5e5617bcec4db00282c43a8b8c3d8547710fb48eeef687540ff3da232344a"
    )
    assert REFERENCE["production_imported"] is False
    assert PRIMARY["real_event_cases"] == REFERENCE["real_event_cases"] == 0


def test_every672_literal_cell_matches_the_source_and_keeps_six_default_differences():
    actual = aiyar.calculate(dict.fromkeys(aiyar.CONTRIBUTORS, 0))
    differences = []
    for ti, target in enumerate(aiyar.TARGETS):
        for di, donor in enumerate(aiyar.CONTRIBUTORS):
            for h in range(1, 13):
                expected = int(
                    h in PRIMARY["positive_relative_houses_1_based"][target][donor]
                )
                assert actual["prastara"][target][donor][h - 1] == expected
                if int(rao.HOUSE_ROWS[ti][h - 1][di]) != expected:
                    differences.append((target, donor, h, expected))
    assert differences == [
        ("Moon", "Moon", 9, 0),
        ("Moon", "Mars", 9, 1),
        ("Moon", "Jupiter", 2, 0),
        ("Moon", "Jupiter", 12, 1),
        ("Venus", "Mars", 4, 0),
        ("Venus", "Mars", 5, 1),
    ]
    assert actual["bhinna_totals"] == dict(
        zip(aiyar.TARGETS, [48, 49, 39, 54, 56, 52, 39])
    )
    assert actual["samudaya_total"] == 337
    assert (
        "Ascendant" in actual["contributor_order"]
        and "Ascendant" not in actual["bhinna"]
    )


@pytest.mark.parametrize("case", REFERENCE["rows"], ids=lambda c: c["case_id"])
def test_all91_cases_own_raw_tables_and_637_reduced_rows(case):
    before = copy.deepcopy(case["signs"])
    actual = aiyar.calculate(case["signs"])
    assert case["signs"] == before
    assert all(actual[k] == case[k] for k in ["prastara", "bhinna", "samudaya"])
    for p in aiyar.TARGETS:
        row = actual["reduction_analysis"]["targets"][p]
        assert all(
            row[k] == case["targets"][p][k]
            for k in ["trikona", "sodhita", "reduced_sum"]
        )
        assert not {"rasi_pinda", "graha_pinda", "sodhya_pinda"}.intersection(row)
    assert (
        AiyarBavProfile.model_validate(actual).model_dump(
            mode="json", exclude_unset=True
        )
        == actual
    )


@pytest.mark.parametrize("shift", range(12))
def test_raw_tables_rotate_with_all_contributors_without_asserting_reduction_equivariance(
    shift,
):
    case = REFERENCE["rows"][0]
    signs = {p: (v + shift) % 12 for p, v in case["signs"].items()}
    actual = aiyar.calculate(signs)
    for p in aiyar.TARGETS:
        assert all(
            actual["bhinna"][p][(i + shift) % 12] == case["bhinna"][p][i]
            for i in range(12)
        )
    assert all(
        actual["samudaya"][(i + shift) % 12] == case["samudaya"][i] for i in range(12)
    )


def test_the_old_same_raw_bav_reduction_is_still_a_distinct_computation():
    case = REFERENCE["rows"][0]
    old = rao.calculate(case["signs"])
    old_comparison = pinda.analyze(
        old["bhinna"], {p: case["signs"][p] for p in aiyar.TARGETS}
    )
    own = aiyar.calculate(case["signs"])
    assert (
        old_comparison["source_profile_comparison"]["aiyar1905_commentary"]["targets"][
            "Moon"
        ]["trikona"]
        != own["reduction_analysis"]["targets"]["Moon"]["trikona"]
    )
    assert own["reduction_analysis"]["rao_default_replaced"] is False


@pytest.mark.parametrize(
    "change", ["missing", "extra", "node", "bool", "float", "negative", "twelve"]
)
def test_explicit_eight_contributor_domain_is_not_coerced(change):
    signs = dict.fromkeys(aiyar.CONTRIBUTORS, 0)
    if change == "missing":
        signs.pop("Ascendant")
    elif change in {"extra", "node"}:
        signs["Rahu"] = signs.pop("Ascendant") if change == "node" else 0
    else:
        signs["Sun"] = {"bool": True, "float": 0.0, "negative": -1, "twelve": 12}[
            change
        ]
    with pytest.raises(ValueError, match="exactly seven"):
        aiyar.calculate(signs)
