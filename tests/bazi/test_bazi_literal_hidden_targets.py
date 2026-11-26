"""Literal research pairs retain facts without certifying calendar origins."""

import pytest
from pydantic import ValidationError

from fatebridge.core.contracts.output_bazi import DimensionTimingContext
from fatebridge.core.contracts.output_hidden_carriers import HiddenCarrierRelations
from fatebridge.core.hidden_carriers import (
    build_natal_hidden_carriers,
    describe_hidden_targets,
)

NATAL = dict(
    zip(("year", "month", "day", "hour"), map(tuple, ["己未", "丁丑", "丙戌", "戊戌"]))
)
HIDDEN = dict(
    zip(
        "子丑寅卯辰巳午未申酉戌亥",
        [
            "癸",
            "己癸辛",
            "甲丙戊",
            "乙",
            "戊乙癸",
            "丙戊庚",
            "丁己",
            "己丁乙",
            "庚壬戊",
            "辛",
            "戊辛丁",
            "壬甲",
        ],
    )
)
ELEMENT = {
    c: e
    for chars, e in [
        ("甲乙", "木"),
        ("丙丁", "火"),
        ("戊己", "土"),
        ("庚辛", "金"),
        ("壬癸", "水"),
    ]
    for c in chars
}
MATRIX = {
    "木": [
        "same_element",
        "stem_generates_hidden",
        "stem_overcomes_hidden",
        "hidden_overcomes_stem",
        "hidden_generates_stem",
    ],
    "火": [
        "hidden_generates_stem",
        "same_element",
        "stem_generates_hidden",
        "stem_overcomes_hidden",
        "hidden_overcomes_stem",
    ],
    "土": [
        "hidden_overcomes_stem",
        "hidden_generates_stem",
        "same_element",
        "stem_generates_hidden",
        "stem_overcomes_hidden",
    ],
    "金": [
        "stem_overcomes_hidden",
        "hidden_overcomes_stem",
        "hidden_generates_stem",
        "same_element",
        "stem_generates_hidden",
    ],
    "水": [
        "stem_generates_hidden",
        "stem_overcomes_hidden",
        "hidden_overcomes_stem",
        "hidden_generates_stem",
        "same_element",
    ],
}

STEMS, BRANCHES = "甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥"
CYCLE = {STEMS[i % 10] + BRANCHES[i % 12] for i in range(60)}


@pytest.mark.parametrize("stem", STEMS)
@pytest.mark.parametrize("branch", BRANCHES)
def test_all120_literal_pairs_preserve_independent_relations_and_strict60_gate(
    stem, branch
) -> None:
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
        assert describe_hidden_targets(stem, branch)
    else:
        assert row["pair_consistency"] == "literal_nonsexagenary_pair"
        with pytest.raises(ValueError, match="六十甲子"):
            describe_hidden_targets(stem, branch)
    assert current["effective_force_status"] == "not_adjudicated"


def test_boundary_date_context_uses_the_full_existing_clock_contract() -> None:
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
