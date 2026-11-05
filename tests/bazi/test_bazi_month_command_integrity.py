"""Known month-duty facts cannot become invented adjudication or false sums."""

import itertools
import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.output_bazi_evidence import BaziEvidenceChain

ROOT = Path(__file__).resolve().parents[2]
LITERAL_HIDDEN = {
    b: list(s)
    for b, s in zip(
        "子丑寅卯辰巳午未申酉戌亥",
        (
            "癸",
            "己癸辛",
            "甲丙戊",
            "乙",
            "戊乙癸",
            "丙庚戊",
            "丁己",
            "己丁乙",
            "庚壬戊",
            "辛",
            "戊辛丁",
            "壬甲",
        ),
    )
}


@pytest.mark.parametrize(
    "row",
    [
        r
        for r in json.loads(
            (
                ROOT / "src/fatebridge/data/reference/bazi-source-annotations.json"
            ).read_text()
        )["records"]
        if r["group"] == "original"
    ],
)
@pytest.mark.parametrize(
    "fault",
    [
        "invented_duty",
        "false_duration_sum",
        "false_annual_match",
        "mixed_witness_month",
        "adopted_table_order",
        "invented_source_duty",
        "wrong_hidden_identity",
        "wrong_conventional_roots",
    ],
)
def test_current_month_facts_reject_false_adjudication_and_physical_identity(
    row, fault
):
    from fatebridge.core.bazi_evidence import build_natal_evidence
    from fatebridge.core.elements import ElementAnalysis
    from tests.support.bazi_month_command_faults import perturb

    chart = dict(zip(("year", "month", "day", "hour"), map(tuple, row["pillars"])))
    natal = build_natal_evidence(
        chart, ElementAnalysis.analyze_day_master_strength(chart)
    )
    with pytest.raises(ValidationError):
        BaziEvidenceChain.model_validate(perturb(natal, fault))


def test_all408_existing_complete_outputs_roundtrip_without_rewriting_source_disagreements():
    from fatebridge.core.bazi_evidence import build_natal_evidence
    from fatebridge.core.elements import ElementAnalysis

    rows = json.loads((ROOT / "tests/data/bazi/arithmetic-inputs.json").read_text())
    for row in rows:
        chart = dict(zip(("year", "month", "day", "hour"), map(tuple, row["pillars"])))
        actual = build_natal_evidence(
            chart, ElementAnalysis.analyze_day_master_strength(chart)
        )
        assert (
            BaziEvidenceChain.model_validate(actual).model_dump(exclude_unset=True)
            == actual
        )
    assert len(rows) == 408


@pytest.mark.parametrize(
    "value,valid",
    [
        ({"month_command": {}}, True),
        ({"month_command": None}, True),
        (
            {
                "month_command": {
                    "intra_month_duty": {"status": None, "selected_stem": None}
                }
            },
            True,
        ),
        ({"month_command": {"intra_month_duty": {"selected_stem": "甲"}}}, False),
        (
            {
                "month_command": {
                    "month_branch": "卯",
                    "intra_month_duty": {"source_reference": {"month_branch": "酉"}},
                }
            },
            False,
        ),
        (
            {
                "month_command": {
                    "intra_month_duty": {"source_reference": {"month_branch": "卯"}}
                }
            },
            True,
        ),
        (
            {
                "month_command": {"month_branch": "卯"},
                "bureau_season_reference": {"month_branch": "酉"},
            },
            False,
        ),
        (
            {
                "month_command": {
                    "intra_month_duty": {"source_reference": {"month_branch": "卯"}}
                },
                "bureau_season_reference": {"month_branch": "酉"},
            },
            False,
        ),
        (
            {
                "month_command": {"month_branch": "卯"},
                "classical_passage": {
                    "nodes": [{"id": "month:hidden:辛", "branch": "酉"}]
                },
            },
            False,
        ),
        (
            {
                "month_command": {"month_branch": "卯"},
                "classical_passage": {
                    "nodes": [{"pillar": "month", "plane": "hidden", "branch": "酉"}]
                },
            },
            False,
        ),
    ],
)
def test_partial_known_months_and_non_adoption_are_preserved(value, valid):
    original = deepcopy(value)
    if valid:
        result = BaziEvidenceChain.model_validate(value)
        assert result.model_dump(exclude_unset=True) == original
    else:
        with pytest.raises(ValidationError):
            BaziEvidenceChain.model_validate(value)
    assert value == original


def test_all_literal_hidden_identity_positions_and_missing_facts():
    from fatebridge.core.output_month_command import DutyClaim

    checked = 0
    for branch, stem, rank in itertools.product(
        LITERAL_HIDDEN, "甲乙丙丁戊己庚辛壬癸", range(3)
    ):
        value = {
            "canonical_stem": stem,
            "hidden_positions": [
                {"pillar": "month", "branch": branch, "hidden_rank": rank}
            ],
        }
        expected = (
            rank < len(LITERAL_HIDDEN[branch]) and LITERAL_HIDDEN[branch][rank] == stem
        )
        try:
            model = DutyClaim.model_validate(value)
            accepted = True
            assert model.model_dump(exclude_unset=True) == value
        except ValidationError:
            accepted = False
        assert accepted == expected, value
        checked += 1
    assert checked == 360
    for value in (
        {},
        {"canonical_stem": None, "hidden_positions": None},
        {"hidden_positions": [{"branch": "子", "hidden_rank": 0}]},
    ):
        assert DutyClaim.model_validate(value).model_dump(exclude_unset=True) == value
    for value in (
        {"canonical_stem": None, "hidden_positions": []},
        {"hidden_positions": [{"branch": "子", "hidden_rank": 2}]},
    ):
        with pytest.raises(ValidationError):
            DutyClaim.model_validate(value)


def test_literal_sum_32_and_26_and_380_360_remain_valid():
    from fatebridge.core.output_month_command import (
        DutyAnnualArithmetic,
        DutyDurationLayer,
    )

    for total in (26, 30, 32):
        value = {
            "claims": [{"days": 7}, {"days": total - 7}],
            "computed_literal_duration_sum": total,
            "equals_nominal_thirty_days": total == 30,
            "chronological_order_adjudicated": False,
            "selected_duty_stem": None,
        }
        assert (
            DutyDurationLayer.model_validate(value).model_dump(exclude_unset=True)
            == value
        )
    value = {"computed_literal_sum": 380, "stated_total": 360, "matches": False}
    assert (
        DutyAnnualArithmetic.model_validate(value).model_dump(exclude_unset=True)
        == value
    )
    for partial in (
        {"computed_literal_duration_sum": 26},
        {"claims": [{"days": 7}, {}]},
        {"equals_nominal_thirty_days": False},
    ):
        assert (
            DutyDurationLayer.model_validate(partial).model_dump(exclude_unset=True)
            == partial
        )


@pytest.mark.parametrize(
    "value",
    json.loads((ROOT / "tests/data/bazi/month-command-cross-invalid.json").read_text()),
)
def test_first5_partial_cross_bindings_cannot_erase_known_month(value):
    with pytest.raises(ValidationError):
        BaziEvidenceChain.model_validate(value)
