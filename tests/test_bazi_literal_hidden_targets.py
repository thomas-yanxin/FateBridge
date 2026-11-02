"""Literal research pairs retain facts without certifying calendar origins."""

import gzip
import hashlib
import json
import types
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.hidden_carriers import (
    build_natal_hidden_carriers,
    describe_hidden_targets,
)
from fatebridge.core.output_bazi import DimensionTimingContext
from fatebridge.core.output_hidden_carriers import HiddenCarrierRelations
from tests.test_hidden_carriers import ELEMENT, HIDDEN, MATRIX, NATAL

ROOT = Path(__file__).resolve().parents[1]
STEMS, BRANCHES = "甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥"
CYCLE = {STEMS[i % 10] + BRANCHES[i % 12] for i in range(60)}


@pytest.mark.parametrize("stem", STEMS)
@pytest.mark.parametrize("branch", BRANCHES)
def test_all120_literal_pairs_preserve_independent_relations_and_strict60_gate(
    stem, branch
):
    pillars = {**NATAL, "year": (stem, branch)}
    current = build_natal_hidden_carriers(pillars)
    HiddenCarrierRelations.model_validate(current)
    row = current["pillars"][0]
    assert row["pillar"] == stem + branch
    assert {t["hidden_stem"] for t in row["targets"]} == set(HIDDEN[branch])
    assert len(row["targets"]) == len(HIDDEN[branch])
    assert row["targets"][0]["hidden_stem"] == HIDDEN[branch][0]
    assert [t["hidden_rank"] for t in row["targets"]] == list(
        range(1, len(row["targets"]) + 1)
    )
    for target in row["targets"]:
        relation = MATRIX[ELEMENT[stem]][
            "木火土金水".index(ELEMENT[target["hidden_stem"]])
        ]
        assert target["relation"] == relation
        assert target["covering_candidate_if_target_desired"] == (
            relation == "stem_overcomes_hidden"
        )
    if stem + branch in CYCLE:
        assert "pair_consistency" not in row
        old_path = (
            ROOT
            / "tests/fixtures/bazi_literal_hidden_targets_v1/before/src/fatebridge/core/hidden_carriers.py"
        )
        old = types.ModuleType("_literal_hidden_before")
        exec(compile(old_path.read_bytes(), str(old_path), "exec"), old.__dict__)
        assert current == old.build_natal_hidden_carriers(pillars)
        assert describe_hidden_targets(stem, branch) == old.describe_hidden_targets(
            stem, branch
        )
    else:
        assert row["pair_consistency"] == "literal_nonsexagenary_pair"
        with pytest.raises(ValueError, match="六十甲子"):
            describe_hidden_targets(stem, branch)
    assert current["effective_force_status"] == "not_adjudicated"


def test_all349_retained_source_records_keep_literal_pair_flags_without_repairing_pillars():
    path = (
        ROOT / "docs/validation/bazi-complete-bureau-adopted-source-corpus-v1.json.gz"
    )
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == Path(str(path) + ".sha256").read_text().strip()
    )
    corpus = json.loads(gzip.decompress(path.read_bytes()))
    records = invalid_pairs = 0
    for group in corpus["groups"].values():
        for record in group["rows"]:
            original = deepcopy(record)
            pillars = dict(
                zip(("year", "month", "day", "hour"), map(tuple, record["pillars"]))
            )
            result = build_natal_hidden_carriers(pillars)
            HiddenCarrierRelations.model_validate(result)
            assert [r["pillar"] for r in result["pillars"]] == record["pillars"]
            for row in result["pillars"]:
                invalid = row["pillar"] not in CYCLE
                assert (
                    row.get("pair_consistency") == "literal_nonsexagenary_pair"
                ) == invalid
                invalid_pairs += invalid
            assert record == original
            records += 1
    expected_invalid = sum(
        pair not in CYCLE
        for group in corpus["groups"].values()
        for record in group["rows"]
        for pair in record["pillars"]
    )
    assert records == 349 and invalid_pairs == expected_invalid == 0


def test_boundary_date_context_uses_the_full_existing_clock_contract():
    # Synthetic contract facts only; no invented physical solar root.
    term = {
        "name": "立春",
        "datetime": "2027-02-04 00:00:00.000001",
        "datetime_with_offset": "2027-02-04T00:00:00.000001+08:00",
        "utc_offset_seconds": 28800.0,
        "fold": 0,
        "solar_model_details": {"synthetic_contract_probe": True},
    }
    DimensionTimingContext.model_validate({"boundaries_on_date": [term]})
    DimensionTimingContext.model_validate({"boundaries_on_date": [{"fold": 1}]})
    for fault in (
        {"fold": True},
        {"utc_offset_seconds": 3600},
        {"solar_model_details": "wrong"},
    ):
        with pytest.raises(ValidationError):
            DimensionTimingContext.model_validate(
                {"boundaries_on_date": [{**term, **fault}]}
            )
