"""Delivery controls frozen before v81 production edits; no new calendar oracle."""

from copy import deepcopy

import pytest

from fatebridge.core.sukuyo import texts as delivery
from fatebridge.core.sukuyo.calendar import calendar_mansion
from fatebridge.core.sukuyo.sanjiu import candidate_relation_analysis
from fatebridge.services.divination import calculate_sukuyo_compatibility


@pytest.fixture(scope="module")
def hinoo():
    return calendar_mansion(
        "1341-05-24",
        zone="+09:00",
        calendar_basis="japanese_naoj_historical_utc09",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )


@pytest.fixture(scope="module")
def ordinary():
    return calendar_mansion("2025-01-29", zone="+09:00")


def test_applied_contract_describes_filtered_rows_and_preserved_matrix(hinoo) -> None:
    analysis = candidate_relation_analysis(hinoo, hinoo)
    text = delivery.joint_reconstruction_contract(analysis)
    assert "applied" in text and "unconstrained_rows" in text
    assert "rows仅列" in text and "完整联合支持" in text
    assert len(analysis["rows"]) == 2
    assert len(analysis["unconstrained_rows"]) == 4


@pytest.mark.parametrize("resolved", [False, True])
def test_not_shared_does_not_promise_a_nonexistent_matrix_key(
    hinoo, resolved: bool
) -> None:
    first = deepcopy(hinoo)
    second = deepcopy(hinoo)
    if resolved:
        first["natal_su27"] = second["natal_su27"] = "毕"
    else:
        pass
    second["profile_calculation"]["ruleset_id"] = "different"
    analysis = candidate_relation_analysis(first, second)
    assert analysis["shared_reconstruction_analysis"]["status"] == "not_shared"
    assert "unconstrained_rows" not in analysis
    text = delivery.joint_reconstruction_contract(analysis)
    assert "not_shared" in text and "未施加共同重建约束" in text
    assert "保留在unconstrained_rows" not in text
    assert ("有向关系" in text) if resolved else ("原无约束外包络" in text)


@pytest.mark.parametrize("resolved", [False, True])
def test_incomplete_never_means_rows_were_filtered(hinoo, resolved: bool) -> None:
    first = deepcopy(hinoo)
    second = deepcopy(hinoo)
    if resolved:
        first["calendar_day_part"] = second["calendar_day_part"] = "second_half"
        first["natal_su27"] = second["natal_su27"] = "毕"
    else:
        pass
    second["profile_calculation"][
        "candidate_set_complete_under_declared_reconstructions"
    ] = False
    analysis = candidate_relation_analysis(first, second)
    assert analysis["shared_reconstruction_analysis"]["status"] == "incomplete"
    text = delivery.joint_reconstruction_contract(analysis)
    assert "incomplete" in text and "未筛掉" in text
    assert "rows仅列" not in text
    if resolved:
        assert "unconstrained_rows" not in analysis
        assert "有向关系" in text and "resolved_support" in text
    else:
        assert len(analysis["rows"]) == len(analysis["unconstrained_rows"]) == 4
        assert "unconstrained_rows" in text


def test_resolved_support_delivers_every_actual_model_date_half_tuple(hinoo) -> None:
    resolved = deepcopy(hinoo)
    resolved["calendar_day_part"] = "second_half"
    resolved["natal_su27"] = "毕"
    analysis = candidate_relation_analysis(resolved, resolved)
    contract = delivery.joint_reconstruction_contract(analysis)
    assert "not_needed" in contract and "有向关系" in contract
    assert "保留在unconstrained_rows" not in contract
    supports = analysis["shared_reconstruction_analysis"]["resolved_support"]
    assert len(supports) == 2
    for support in supports:
        assert support["person1"]["calendar_date"] == "1341-05-24"
        assert support["person1"]["calendar_day_part"] == "second_half"
        assert support["person1"]["natal_su27"] == "毕"
        assert support["person2"]["calendar_date"] == "1341-05-24"
        assert support["person2"]["calendar_day_part"] == "second_half"
        assert support["person2"]["natal_su27"] == "毕"


def test_null_half_is_not_invented_from_model_independent_support(hinoo) -> None:
    resolved = deepcopy(hinoo)
    resolved["calendar_day_part"] = "second_half"
    resolved["natal_su27"] = "毕"
    other = deepcopy(resolved)
    other["calendar_date"] = "1341-05-25"
    other["calendar_day_part"] = None
    other["profile_calculation"]["short_month_assignment"] = None
    analysis = candidate_relation_analysis(resolved, other)
    supports = analysis["shared_reconstruction_analysis"]["resolved_support"]
    assert len(supports) == 2
    for support in supports:
        assert support["person2"]["calendar_date"] == "1341-05-25"
        assert support["person2"]["calendar_day_part"] is None
        assert support["person2"]["natal_su27"] == "毕"


def test_unknown_shared_status_is_not_treated_as_applied() -> None:
    text = delivery.joint_reconstruction_contract(
        {"shared_reconstruction_analysis": {"status": "new_unknown"}, "rows": []}
    )
    assert "状态未识别" in text and "rows仅列" not in text


def test_service_uses_state_specific_contract_and_resolved_support() -> None:
    result = calculate_sukuyo_compatibility(
        person1_date="1341-05-24",
        person2_date="1341-05-24",
        person1_zone="+09:00",
        person2_zone="+09:00",
        calendar_basis="japanese_naoj_historical_utc09",
        calendar_profile="hinoo_t1299_host27",
        person1_calendar_day_part="second_half",
        person2_calendar_day_part="second_half",
    )
    assert "not_needed" in result["interpretation_contract"]["joint_reconstruction"]
    supports = result["candidate_relation_analysis"]["shared_reconstruction_analysis"][
        "resolved_support"
    ]
    assert len(supports) == 2
    assert any(
        item["reconstruction_id"] == "adjacent_month_short_day_assignment"
        for item in supports
    )
    assert (
        result["pair"] == "命" and result["candidate_relation_analysis"]["rows"] == []
    )
