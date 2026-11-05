"""Literal hidden-target arithmetic and independent source-specific distinction."""

import pytest
from pydantic import ValidationError

from fatebridge.core.hidden_carriers import (
    build_natal_hidden_carriers,
    describe_hidden_targets,
    describe_temporal_hidden_carrier,
    hidden_target_reference,
)
from fatebridge.core.metaphysics.common import SEXAGENARY_CYCLE
from fatebridge.core.output_hidden_carriers import (
    HiddenCarrierRelations,
    HiddenCarrierTarget,
)
from fatebridge.core.timing_carriers import (
    describe_timing_carrier,
    timing_carrier_snapshot_lines,
)

NATAL = dict(
    zip(("year", "month", "day", "hour"), map(tuple, ["己未", "丁丑", "丙戌", "戊戌"]))
)
# Independent literal tables, not imported from the production relation helpers.
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


def test_dingchou_can_cover_hidden_xin_without_overcoming_principal_ji():
    row = describe_timing_carrier("timing.dayun", "丁", "丑", NATAL)
    assert row["principal_relation"] == "stem_generates_branch"
    assert row["branch_covered_if_desired"] is False
    hidden = describe_temporal_hidden_carrier(row["node_id"], "丁", "丑")
    assert [r["hidden_stem"] for r in hidden["targets"]] == ["己", "癸", "辛"]
    assert [
        r["hidden_stem"]
        for r in hidden["targets"]
        if r["covering_candidate_if_target_desired"]
    ] == ["辛"]
    reference = hidden_target_reference()
    assert reference["effective_force_status"] == "not_adjudicated"
    assert {
        **reference,
        "pillar": hidden["pillar"],
        "targets": hidden["targets"],
    } == describe_hidden_targets("丁", "丑")
    natal = build_natal_hidden_carriers(NATAL)
    month = natal["pillars"][1]
    assert month["targets"][-1]["ten_god"] == "正财"
    assert month["targets"][-1]["hidden_rank"] == 3


@pytest.mark.parametrize("pair", SEXAGENARY_CYCLE)
def test_all_sixty_columns_match_an_independent_complete_relation_table(pair):
    ref = describe_hidden_targets(*pair)
    HiddenCarrierRelations.model_validate(ref)
    # These independent literal contents do not prescribe a disputed 中余氣
    # order. hidden_rank explicitly indexes the existing project table only.
    assert {r["hidden_stem"] for r in ref["targets"]} == set(HIDDEN[pair[1]])
    assert len(ref["targets"]) == len(HIDDEN[pair[1]])
    assert ref["targets"][0]["hidden_stem"] == HIDDEN[pair[1]][0]
    for rank, row in enumerate(ref["targets"], 1):
        relation = MATRIX[ELEMENT[pair[0]]][
            "木火土金水".index(ELEMENT[row["hidden_stem"]])
        ]
        assert row["hidden_rank"] == rank
        assert row["relation"] == relation
        assert row["covering_candidate_if_target_desired"] == (
            relation == "stem_overcomes_hidden"
        )


def test_contract_rejects_false_cover_and_false_effectiveness_but_keeps_projection():
    HiddenCarrierTarget.model_validate({"hidden_stem": "辛"})
    with pytest.raises(ValidationError):
        HiddenCarrierTarget.model_validate(
            {
                "relation": "stem_generates_hidden",
                "covering_candidate_if_target_desired": True,
            }
        )
    with pytest.raises(ValidationError):
        HiddenCarrierRelations.model_validate(
            {"effective_force_status": "root_destroyed"}
        )
    with pytest.raises(ValueError, match="六十甲子"):
        describe_hidden_targets("甲", "丑")


def test_unavailable_hidden_table_keeps_legacy_text_without_inventing_target_claims():
    row = describe_timing_carrier("timing.dayun", "丁", "丑", NATAL)
    before = timing_carrier_snapshot_lines({"pillar_carriers": [row]})
    unknown = timing_carrier_snapshot_lines(
        {"pillar_carriers": [row], "hidden_target_carriers": None}
    )
    assert unknown == before
    assert not any("另见干克真实藏干" in line for line in unknown)
