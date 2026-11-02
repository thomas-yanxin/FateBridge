"""Source arithmetic frozen before the distinct Aiyar kernel was implemented."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import jyotish_aiyar_reductions as aiyar
from fatebridge.core import jyotish_pinda as rao

FIXTURES = Path(__file__).parent / "fixtures"
PRIMARY_PATH = FIXTURES / "jyotish-aiyar-reductions-primary.json"
REFERENCE_PATH = FIXTURES / "jyotish-aiyar-reductions-reference.json"
PRIMARY = json.loads(PRIMARY_PATH.read_text())
REFERENCE = json.loads(REFERENCE_PATH.read_text())


def test_source_arithmetic_and_old_reference_fingerprints_are_not_refreshed():
    assert hashlib.sha256(PRIMARY_PATH.read_bytes()).hexdigest() == (
        "2b651e9ada312af07fb0e61903c6d78e692032d0bb9077597850220aece5a959"
    )
    assert hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest() == (
        "d497c18b211c73d234f3b4a5a4330285183ee14cda3e4e63b55786c323ec7f5e"
    )
    assert (
        hashlib.sha256(
            (FIXTURES / "jyotish-pinda-full-bav-reference.json").read_bytes()
        ).hexdigest()
        == "080f343ca816b7ea45d62807e74d5abc9c00fc49afd3334465a350148a29f1c1"
    )
    assert PRIMARY["source"]["scan_sha256"] == aiyar.SOURCE["scan_sha256"]
    assert PRIMARY["source"]["OCR_page_label_correction"]["actual_printed"] == "102"
    assert aiyar.SOURCE["source_kind"] == "english_translation_commentary"
    assert PRIMARY["real_event_cases"] == REFERENCE["real_event_cases"] == 0


@pytest.mark.parametrize("case", REFERENCE["trinal_cases"])
def test_all729_original_trinal_inputs(case):
    row = [0] * 12
    row[0], row[4], row[8] = case["before"]
    result, _ = aiyar.trinal(row)
    assert [result[i] for i in [0, 4, 8]] == case["after"]


@pytest.mark.parametrize("case", REFERENCE["coowned_cases"])
def test_all1620_pair_counts_and_occupancy_patterns(case):
    row = [0] * 12
    for sign, value in zip(case["pair"], case["before"]):
        row[sign] = value
    positions = [i for i, flag in zip(case["pair"], case["occupied"]) if flag]
    result, _ = aiyar.coowned(row, positions)
    assert [result[i] for i in case["pair"]] == case["after"]


@pytest.mark.parametrize("case", REFERENCE["full_rows"], ids=lambda c: c["case_id"])
def test_all637_exposed_full_input_rows_under_this_distinct_source(case):
    original = copy.deepcopy(case)
    actual = aiyar.reduce_row(case["before"], case["occupied_signs"])
    assert case == original
    assert all(actual[k] == case[k] for k in ["trikona", "sodhita", "reduced_sum"])
    assert len(actual["trikona_steps"]) == 4
    assert len(actual["coowned_steps"]) == 5


def test_the_printed_mars_example_and_single_pass_rule_are_both_retained():
    example = PRIMARY["worked_mars"]
    actual = aiyar.reduce_row(example["input_bav"], example["occupied_signs"])
    assert actual["trikona"] == actual["sodhita"] == example["trikona"]
    assert actual["reduced_sum"] == 15
    # The original Gemini/Libra/Aquarius [3,5,3] becomes [0,2,0]. The
    # newly created zeros do not trigger a second pass of the original-zero rule.
    assert [actual["trikona"][i] for i in [2, 6, 10]] == [0, 2, 0]
    assert actual["trikona_steps"][2]["source_rule"] == "IX.NB.I.1"
    assert "Pinda" not in actual and "rasi_pinda" not in actual


def test_author_profiles_keep_distinct_two_zero_and_single_occupied_equal_cases():
    row = [0] * 12
    row[0] = row[7] = 2
    signs = {**dict.fromkeys(rao.PLANETS, 4), "Sun": 0}
    # Compare the pair rule on explicitly supplied pre-reduced values first.
    old_pair, _ = rao.coowned(row, signs)
    new_pair, steps = aiyar.coowned(row, [0, 4])
    assert old_pair[0] == new_pair[0] == 2
    assert old_pair[7] is None and new_pair[7] == 0
    assert steps[0]["source_rule"] == "IX.NB.II.2.3"
    # Starting the full Aiyar chain changes the trinal result as well. Merely
    # filling the Rao null with0 would not reproduce the new complete chain.
    old = rao.reduce_row(row, signs)
    new = aiyar.reduce_row(row, [0, 4])
    assert old["trikona"][0] == 2 and old["sodhita"][7] is None
    assert new["trikona"] == new["sodhita"] == [0] * 12
    assert old["rasi_pinda"] is None


@pytest.mark.parametrize(
    "row",
    [
        [],
        [0] * 11,
        [0] * 13,
        [True] + [0] * 11,
        [-1] + [0] * 11,
        [9] + [0] * 11,
        [0.5] + [0] * 11,
    ],
)
def test_invalid_count_domains_are_rejected(row):
    with pytest.raises(ValueError, match="twelve integer"):
        aiyar.reduce_row(row, [0])


@pytest.mark.parametrize(
    "positions", [[True], [-1], [12], [0.0], [0, 0], list(range(8))]
)
def test_occupancy_indices_are_explicit_and_not_silently_coerced(positions):
    with pytest.raises(ValueError, match="distinct integer"):
        aiyar.reduce_row([0] * 12, positions)
