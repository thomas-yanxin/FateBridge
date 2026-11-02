"""Delivery controls frozen before v81 production edits; no new calendar oracle."""

from copy import deepcopy

import pytest

from fatebridge.core import sukuyo_compatibility_text as delivery
from fatebridge.core.sukuyo import calendar_mansion, candidate_relation_analysis
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


def test_applied_contract_describes_filtered_rows_and_preserved_matrix(hinoo):
    analysis = candidate_relation_analysis(hinoo, hinoo)
    text = delivery.joint_reconstruction_contract(analysis)
    assert "applied" in text and "unconstrained_rows" in text
    assert "rows仅列" in text and "完整联合支持" in text
    assert len(analysis["rows"]) == 2
    assert len(analysis["unconstrained_rows"]) == 4


@pytest.mark.parametrize("resolved", [False, True])
def test_not_shared_does_not_promise_a_nonexistent_matrix_key(hinoo, resolved):
    first = deepcopy(hinoo)
    second = deepcopy(hinoo)
    if resolved:
        first["natal_su27"] = second["natal_su27"] = "毕"
    second["profile_calculation"]["source_bundle_sha256"] = "different"
    analysis = candidate_relation_analysis(first, second)
    assert analysis["shared_reconstruction_analysis"]["status"] == "not_shared"
    assert "unconstrained_rows" not in analysis
    text = delivery.joint_reconstruction_contract(analysis)
    assert "not_shared" in text and "未施加共同重建约束" in text
    assert "保留在unconstrained_rows" not in text
    assert ("有向关系" in text) if resolved else ("原无约束外包络" in text)


@pytest.mark.parametrize("resolved", [False, True])
def test_incomplete_never_means_rows_were_filtered(hinoo, resolved):
    first = deepcopy(hinoo)
    second = deepcopy(hinoo)
    if resolved:
        first["calendar_day_part"] = second["calendar_day_part"] = "second_half"
        first["natal_su27"] = second["natal_su27"] = "毕"
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


def test_resolved_support_delivers_every_actual_model_date_half_tuple(hinoo):
    resolved = deepcopy(hinoo)
    resolved["calendar_day_part"] = "second_half"
    resolved["natal_su27"] = "毕"
    analysis = candidate_relation_analysis(resolved, resolved)
    text = delivery.joint_reconstruction_reading(["甲方", "乙方"], analysis)
    contract = delivery.joint_reconstruction_contract(analysis)
    assert "not_needed" in contract and "有向关系" in contract
    assert "保留在unconstrained_rows" not in contract
    supports = analysis["shared_reconstruction_analysis"]["resolved_support"]
    assert len(supports) == 2
    for support in supports:
        assert f"共同重建{support['reconstruction_id']}支持" in text
    assert text.count("甲方1341-05-24、后半、宿毕") == 2
    assert text.count("乙方1341-05-24、后半、宿毕") == 2


def test_null_half_is_not_invented_from_model_independent_support(hinoo):
    resolved = deepcopy(hinoo)
    resolved["calendar_day_part"] = "second_half"
    resolved["natal_su27"] = "毕"
    other = deepcopy(resolved)
    other["calendar_date"] = "1341-05-25"
    other["calendar_day_part"] = None
    other["profile_calculation"]["short_month_assignment"] = None
    analysis = candidate_relation_analysis(resolved, other)
    text = delivery.joint_reconstruction_reading(["甲方", "乙方"], analysis)
    assert text.count("乙方1341-05-25、未以半日区分、宿毕") == 2
    assert "乙方1341-05-25、后半" not in text


def test_ordinary_envelope_has_positive_profile_evidence_and_actual_completeness(
    ordinary,
):
    contexts = [ordinary, ordinary]
    analysis = {
        "status": "candidate_only",
        "rows": [{"person1_su27": "危", "person2_su27": "室"}],
        "candidate_set_complete_within_profile": True,
    }
    before = deepcopy((contexts, analysis))
    text = delivery.ordinary_candidate_envelope_reading(contexts, analysis)
    assert "t1299_fullmoon27" in text and "条件外包络" in text
    assert "Hinoo共同重建筛选" in text and "本次档案内完整" in text
    analysis["candidate_set_complete_within_profile"] = False
    text = delivery.ordinary_candidate_envelope_reading(contexts, analysis)
    assert "未穷尽" in text and "本次档案内完整" not in text
    analysis["candidate_set_complete_within_profile"] = True
    assert (contexts, analysis) == before


@pytest.mark.parametrize(
    "mutation",
    ["missing_profile", "missing_method", "source", "assignment", "method", "leaf"],
)
def test_missing_or_conflicting_metadata_cannot_establish_ordinary_inapplicability(
    ordinary, mutation
):
    context = deepcopy(ordinary)
    profile = context["profile_calculation"]
    if mutation == "missing_profile":
        context.pop("calendar_profile")
    elif mutation == "missing_method":
        profile.pop("mansion_method_id")
    elif mutation == "source":
        (context.get("calendar_candidates") or [context])[0]["profile_calculation"].pop(
            "hinoo_source"
        )
    elif mutation == "assignment":
        (context.get("calendar_candidates") or [context])[0]["profile_calculation"][
            "short_month_assignment"
        ] = {"unknown": True}
    elif mutation == "method":
        profile["mansion_method_id"] = "unverified"
    else:
        context["calendar_candidates"] = [deepcopy(ordinary)]
        context["calendar_candidates"][0]["calendar_profile"] = "hinoo_t1299_host27"
    analysis = {"status": "candidate_only", "rows": [{}]}
    assert (
        delivery.ordinary_candidate_envelope_reading([ordinary, context], analysis)
        == ""
    )


def test_hinoo_without_precedence_is_not_an_ordinary_profile(ordinary, hinoo):
    context = deepcopy(hinoo)
    context["profile_calculation"]["short_month_assignment"] = None
    analysis = {"status": "candidate_only", "rows": [{}]}
    assert (
        delivery.ordinary_candidate_envelope_reading([ordinary, context], analysis)
        == ""
    )


@pytest.mark.parametrize("bad_candidates", [{}, "unverified", [None]])
def test_malformed_branch_structure_cannot_establish_profile_scope(
    ordinary, bad_candidates
):
    context = deepcopy(ordinary)
    context["calendar_candidates"] = bad_candidates
    assert (
        delivery.ordinary_candidate_envelope_reading(
            [ordinary, context], {"status": "candidate_only", "rows": [{}]}
        )
        == ""
    )


def test_explicit_but_null_shared_object_is_not_silently_overridden(ordinary):
    assert (
        delivery.ordinary_candidate_envelope_reading(
            [ordinary, ordinary],
            {
                "status": "candidate_only",
                "rows": [{}],
                "shared_reconstruction_analysis": None,
            },
        )
        == ""
    )


def test_unknown_shared_status_is_not_treated_as_applied():
    text = delivery.joint_reconstruction_contract(
        {"shared_reconstruction_analysis": {"status": "new_unknown"}, "rows": []}
    )
    assert "状态未识别" in text and "rows仅列" not in text


def test_service_uses_state_specific_contract_and_resolved_support():
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
    assert "共同重建adjacent_month_short_day_assignment支持" in result["summary"]
    assert (
        result["pair"] == "命" and result["candidate_relation_analysis"]["rows"] == []
    )
