"""An uncertain own-Si blocker cannot establish absence of hidden control."""

import pytest

from fatebridge.core.requests.divination import SixYaoRequest
from fatebridge.services.divination import calculate_sixyao_analysis
from tests.support.transports import SPECS, business, rest, surface_calls

CASES = [
    pytest.param("2026-03-02", "001000", "001101", 6, "卯", None, [6], id="pending"),
    pytest.param("2026-05-01", "001000", "001101", 6, "卯", True, [6], id="no-blocker"),
    pytest.param(
        "2026-03-02",
        "001101",
        "101101",
        1,
        "亥",
        "not_applicable",
        [6],
        id="definite-blocker-excluded",
    ),
]


def payload_for(date, base, changed):
    return dict(
        date=date,
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code=base,
        changed_code=changed,
    )


def check(output, position, hidden_branch, own_match, possible):
    facts = output["liuyao_evidence"]["conditional_analysis"]
    source = facts["generation_conditions"]["sources"][position - 1]
    line = facts["lines"][position - 1]
    own = facts["growth_conditions"]["lines"][position - 1].get("own_changed_si")
    hidden = next(h for h in facts["hidden_conditions"] if h["branch"] == hidden_branch)
    if own_match == "not_applicable":
        assert own is None
        assert source["condition_match"] is False
        assert source["status"] == "own_back_control_obstructs_generation"
        assert line["outgoing_obstructions"]
        assert position not in hidden["reception"]["possible_control_positions"]
    else:
        assert own["condition_match"] is own_match
        if own_match is None:
            assert own["qualified_back_control_condition"] is None
            assert source["condition_match"] is None
            assert source["status"] == "own_si_growth_or_back_control_pending"
            assert line["outgoing_obstructions"]
        else:
            assert own["qualified_back_control_condition"] is False
            assert line["outgoing_obstructions"] == []
    reception = hidden["reception"]
    assert reception["possible_control_positions"] == possible
    assert reception["condition_match"] is None
    assert (
        "moving_control_of_hidden_requires_resolution" in reception["pending_reasons"]
    )


@pytest.mark.parametrize("date,base,changed,position,hidden,own,possible", CASES)
def test_hidden_control_gate_preserves_all_three_blocker_states(
    date, base, changed, position, hidden, own, possible
):
    request = SixYaoRequest.model_validate(payload_for(date, base, changed))
    output = calculate_sixyao_analysis(**request.model_dump())
    check(output, position, hidden, own, possible)


@pytest.mark.parametrize("date,base,changed,position,hidden,own,possible", CASES)
def test_hidden_control_uncertainty_agrees_across_real_transports(
    date, base, changed, position, hidden, own, possible, surface_calls
):
    spec = SPECS["sixyao"]
    payload = payload_for(date, base, changed)
    fields = [
        "nongli.dayGanZi",
        "liuyao_evidence.conditional_analysis.lines",
        "liuyao_evidence.conditional_analysis.hidden_conditions",
        "liuyao_evidence.conditional_analysis.growth_conditions.lines",
        "liuyao_evidence.conditional_analysis.generation_conditions.sources",
    ]
    response, protocol, code, cli = surface_calls(
        spec,
        payload,
        params={"fields": fields, "strict_fields": True},
        options={"fields": fields, "strict_fields": True},
        flags=("--fields", *fields, "--strict-fields"),
    )
    assert response.status_code == 200, response.text
    assert code == 0 and not protocol.is_error
    expected = business(response.json())
    assert expected == business(cli) == business(protocol.structured_content)
    assert expected["nongli"]["dayGanZi"] == "乙亥"
    check(expected, position, hidden, own, possible)
