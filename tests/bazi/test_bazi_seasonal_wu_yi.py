"""Two selected seasonal passages keep documents and literal positions separate."""

import pytest

from fatebridge.core.classical import seasonal_climate_god
from fatebridge.core.contracts.output_classical_seasonal import SeasonalClimateReference


@pytest.mark.parametrize(
    "pillars, body_pages, stems, witness",
    [
        (
            ("乙丑", "乙酉", "戊辰", "丙辰"),
            [144, 145],
            ["丙", "癸"],
            (
                "癸",
                [],
                [
                    {"pillar": "year", "branch": "丑", "hidden_rank": 1},
                    {"pillar": "day", "branch": "辰", "hidden_rank": 2},
                    {"pillar": "hour", "branch": "辰", "hidden_rank": 2},
                ],
            ),
        ),
        (
            ("乙巳", "戊子", "乙巳", "甲申"),
            [66, 67, 68, 69],
            ["丙"],
            (
                "丙",
                [],
                [
                    {"pillar": "year", "branch": "巳", "hidden_rank": 0},
                    {"pillar": "day", "branch": "巳", "hidden_rank": 0},
                ],
            ),
        ),
    ],
)
def test_collation_keeps_conditions_scoped_to_the_edition_and_observation(
    pillars, body_pages, stems, witness
) -> None:
    chart = dict(zip(("year", "month", "day", "hour"), map(tuple, pillars)))
    value = seasonal_climate_god(chart["day"][0], chart["month"][1], chart)
    SeasonalClimateReference.model_validate(value)
    assert (
        value["source_review_status"] == "selected_wu_yi_passages_not_full_acceptance"
    )
    assert value["chart_adjudication_status"] == "not_performed"
    assert value["source_layers"]["chart_conditions_status"] == "not_adjudicated"
    assert value["source_layers"]["body"]["pdf_pages"] == body_pages
    assert value["source_layers"]["body"]["stem_sequence"] == stems
    assert [value["primary"], *value["secondary"]] == stems
    stem, visible, hidden = witness
    rows = {row["stem"]: row for row in value["stem_observations"]}
    assert rows[stem]["visible_positions"] == visible
    assert rows[stem]["hidden_positions"] == hidden
    if chart["day"][0] == "乙":
        assert rows["戊"]["visible_positions"] == ["month"]
        (example,) = value["source_layers"]["body"]["source_examples"]
        assert example["absolute_birth_datetime"] is None
        assert example["winter_solstice_side"] is None
    else:
        pass
