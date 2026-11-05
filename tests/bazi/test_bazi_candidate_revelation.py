"""The selected source requires revealed wealth and seal for this one route."""

import asyncio
from copy import deepcopy

import pytest

from fatebridge.core.classical_candidate_selection import build_candidate_selection
from fatebridge.core.output_candidate_selection import CandidateSelection
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
)
from tests.evaluation.test_agentic_nested_outputs import rest as _shared_rest

ORDER = ("year", "month", "day", "hour")


rest = _shared_rest


@pytest.mark.parametrize(
    "values,wealth,seal",
    [
        # Literal source examples at PDF83–84: both non-day helpers revealed.
        (("丁酉", "己酉", "戊子", "壬子"), ["hour:stem:壬"], ["year:stem:丁"]),
        (("壬戌", "己酉", "戊午", "丁巳"), ["year:stem:壬"], ["hour:stem:丁"]),
        # Remove only the exposed helper, retaining its actual hidden stem.
        (("丁酉", "己酉", "戊子", "辛酉"), [], ["year:stem:丁"]),
        (("壬戌", "己酉", "戊午", "辛酉"), ["year:stem:壬"], []),
        # Synthetic complete-pillar control, not a dated/coherent birth chart.
        (("甲子", "己酉", "戊午", "辛酉"), [], []),
    ],
)
def test_hidden_helpers_cannot_replace_the_source_revelation_prerequisite(
    values, wealth, seal
):
    pillars = dict(zip(ORDER, map(tuple, values)))
    before = deepcopy(pillars)
    selection = build_candidate_selection(pillars)
    row = next(r for r in selection["paths"] if r["id"] == "hurt_wealth_seal")
    expected = (
        "requires_force_adjudication"
        if wealth and seal
        else "observable_prerequisite_not_met"
    )
    assert row["status"] == expected
    observations = {r["id"]: r for r in row["observed_conditions"]}
    # All controls really contain wealth and seal. Hidden occurrence survives
    # as evidence; the text's extra 干头 requirement is checked separately.
    assert observations["helper_presence:正财/偏财"]["status"] == "matched"
    assert observations["helper_presence:正印/偏印"]["status"] == "matched"
    for kind, refs in (("wealth", wealth), ("seal", seal)):
        condition = observations[f"{kind}_revealed_for_combined_wealth_seal"]
        assert condition["star_refs"] == refs
        assert condition["status"] == ("matched" if refs else "not_matched")
    assert row["formation_status"] == "not_adjudicated"
    assert all(r["status"] == "unknown" for r in row["force_conditions"])
    assert selection["chosen_path_id"] is None
    assert pillars == before
    CandidateSelection.model_validate(selection)


def test_revelation_requirement_is_not_extended_to_the_distinct_metal_water_route():
    pillars = dict(zip(ORDER, map(tuple, ("壬申", "壬子", "庚午", "丁丑"))))
    selection = build_candidate_selection(pillars)
    row = next(r for r in selection["paths"] if r["id"] == "hurt_officer")
    # PDF84's 金水伤官财印为辅 does not require every helper to reveal.
    assert row["status"] == "requires_force_adjudication"
    assert not any(
        "revealed_for_combined" in r["id"] for r in row["observed_conditions"]
    )
    helper = next(
        r for r in row["observed_conditions"] if r["id"] == "wealth_or_seal_present"
    )
    assert set(helper["star_refs"]) == {
        "year:hidden:戊",
        "day:hidden:己",
        "hour:hidden:己",
    }


@pytest.mark.parametrize(
    "base,revealed,hidden_only",
    [
        # Literal ten-god/category controls for all ten day stems. These are
        # synthetic complete pillars, not dated charts or source outcome labels.
        (("壬子", "庚午", "甲辰"), "戊辰", "乙酉"),
        (("壬子", "辛巳", "乙卯"), "戊寅", "丁卯"),
        (("甲子", "丁未", "丙申"), "辛卯", "壬子"),
        (("甲子", "丙辰", "丁酉"), "庚子", "壬子"),
        (("丁酉", "己酉", "戊子"), "壬子", "辛酉"),
        (("丁丑", "庚申", "己亥"), "癸酉", "辛酉"),
        (("戊子", "壬子", "庚寅"), "乙酉", "辛酉"),
        (("戊子", "己亥", "辛卯"), "甲午", "丁酉"),
        (("庚子", "癸卯", "壬午"), "丙午", "戊申"),
        (("庚子", "壬寅", "癸巳"), "丁巳", "戊午"),
    ],
)
def test_revelation_gate_is_a_role_rule_for_every_day_stem(base, revealed, hidden_only):
    for hour, expected in (
        (revealed, "requires_force_adjudication"),
        (hidden_only, "observable_prerequisite_not_met"),
    ):
        selection = build_candidate_selection(
            dict(zip(ORDER, map(tuple, (*base, hour))))
        )
        row = next(r for r in selection["paths"] if r["id"] == "hurt_wealth_seal")
        observations = {r["id"]: r for r in row["observed_conditions"]}
        assert row["status"] == expected
        assert observations["helper_presence:正财/偏财"]["status"] == "matched"
        assert observations["helper_presence:正印/偏印"]["status"] == "matched"
        assert observations["wealth_revealed_for_combined_wealth_seal"][
            "star_refs"
        ] == ([f"hour:stem:{revealed[0]}"] if hour == revealed else [])
        assert row["formation_status"] == "not_adjudicated"


@pytest.mark.parametrize(
    "hour,status",
    [(0, "requires_force_adjudication"), (17, "observable_prerequisite_not_met")],
)
def test_revelation_precondition_matches_across_three_public_surfaces(
    hour, status, rest, tmp_path, capsys
):
    spec = SPECS["bazi_birth"]
    # Fictional fully specified interface controls; source person identity is
    # not inferred from matching four pillars or this selected civil date.
    payload = dict(
        birth_year=1957,
        birth_month=9,
        birth_day=13,
        birth_hour=hour,
        birth_minute=0,
        birth_second=0,
        birth_timezone="Asia/Shanghai",
        use_true_solar_time=False,
        gender="男",
    )
    field = "bazi_birth.structure_profile.candidate_selection"
    options = dict(
        fields=[field],
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    response = rest.post(spec.rest_path, json=payload, params=options)
    protocol = asyncio.run(native(spec, payload, **options))
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            field,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    assert response.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(response.json())
        == business(protocol.structured_content)
        == business(local)
    )
    for value in (response.json(), protocol.structured_content, local):
        spec.output_model.model_validate(value)
        selection = value["bazi_birth"]["structure_profile"]["candidate_selection"]
        row = next(r for r in selection["paths"] if r["id"] == "hurt_wealth_seal")
        assert row["status"] == status
        assert selection["method_id"] == "month_path_conditions_v4"
        assert row["formation_status"] == "not_adjudicated"
