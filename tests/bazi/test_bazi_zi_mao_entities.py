"""NLC PDF24–25 entity counts, residual pair and retained policy boundaries."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from fatebridge.core.contracts.output_source_annotations import SourceCurrentCalculation
from fatebridge.core.punishment_resolution import (
    MONTH_OFFICER_CLASH_RESOLVED,
    MONTH_OFFICER_SOURCE,
    REPEATED_PAIR_SOURCE,
    REPETITION_NO_PUNISHMENT,
)
from fatebridge.services.source_comparison import calculate_bazi_source_compare


def current(text):
    return calculate_bazi_source_compare(*text.split())["current_calculation"]


def punishment(value):
    return next(e for e in value["assessment"]["relations"] if e["kind"] == "刑")


def test_source_two_mao_do_not_punish_one_zi_or_reduce_those_roots() -> None:
    # A legal literal witness for the source's partial branch pattern; not
    # presented as the author's full natal case or a historical identity.
    value = current("乙卯 戊子 丙辰 辛卯")
    event = punishment(value)
    assert event["status"] == REPETITION_NO_PUNISHMENT
    assert (
        event["positions"]
        == event["source_positions"]
        == [
            "year",
            "month",
            "hour",
        ]
    )
    assert event["combination_removed_positions"] == []
    assert event["source_id"] == REPEATED_PAIR_SOURCE["id"]
    for root in value["assessment"]["hidden_stem_ledger"]:
        if root["pillar"] in event["source_positions"]:
            assert root["remaining_mass"] == root["initial_mass"]
        else:
            pass
    assert value["branch_combination_candidates"]["screen_status"] == "reconstructed_v8"
    SourceCurrentCalculation.model_validate(value)


def test_source_xu_combines_one_mao_and_only_the_residual_pair_punishes() -> None:
    value = current("乙卯 戊子 丙戌 辛卯")
    event = punishment(value)
    assert event["status"] == "active"
    assert event["positions"] == ["year", "month"]
    assert event["source_positions"] == ["year", "month", "hour"]
    assert event["combination_removed_positions"] == ["hour"]
    assert any(
        e["kind"] == "六合"
        and e["positions"] == ["day", "hour"]
        and e["status"] == "binding"
        for e in value["assessment"]["relations"]
    )
    SourceCurrentCalculation.model_validate(value)


@pytest.mark.parametrize(
    "text,seats,status",
    [
        ("乙亥 戊子 丙辰 辛卯", ["month", "hour"], "active"),
        ("乙丑 戊子 丙辰 辛卯", ["month", "hour"], "resolved_by_combination"),
        ("甲子 丙子 丙辰 辛卯", ["year", "month", "hour"], "active"),
        ("乙卯 戊子 丁卯 庚子", ["year", "month", "day", "hour"], "active"),
        ("乙卯 戊子 乙卯 己卯", ["year", "month", "day", "hour"], "active"),
    ],
)
def test_other_entity_counts_and_the_normal_single_pair_keep_their_policy(
    text: str, seats, status: str
) -> None:
    value = current(text)
    event = punishment(value)
    assert event["status"] == status
    assert event["positions"] == seats
    assert "source_positions" not in event
    SourceCurrentCalculation.model_validate(value)


@pytest.mark.parametrize("fault", ["false_activity", "wrong_entities", "false_cover"])
def test_complete_output_rejects_rebound_entity_receipts(fault: str) -> None:
    value = deepcopy(current("乙卯 戊子 丙辰 辛卯"))
    event = punishment(value)
    if fault == "false_activity":
        event["status"] = "active"
    elif fault == "wrong_entities":
        event["source_positions"] = ["year", "month"]
    else:
        event["combination_removed_positions"] = ["hour"]
    with pytest.raises(ValidationError, match="一子二卯|子卯重见"):
        SourceCurrentCalculation.model_validate(value)


def test_a_combined_mao_cannot_be_reintroduced_into_the_active_pair() -> None:
    value = current("乙卯 戊子 丙戌 辛卯")
    punishment(value)["positions"] = ["year", "month", "hour"]
    with pytest.raises(ValidationError, match="一子二卯"):
        SourceCurrentCalculation.model_validate(value)


@pytest.mark.parametrize(
    "text,seats",
    [
        ("乙卯 戊子 丙寅 丁酉", ["year", "month"]),
        ("乙酉 戊子 丙寅 辛卯", ["month", "hour"]),
    ],
)
def test_bing_zi_month_officer_uses_the_actual_other_seats_clash(
    text: str, seats
) -> None:
    # NLC PDF25 says 丙子月官 is not punished when 卯 actually clashes with酉.
    # These are constructed complete charts for that partial source pattern.
    value = current(text)
    event = punishment(value)
    assert event["status"] == MONTH_OFFICER_CLASH_RESOLVED
    assert event["positions"] == seats
    assert event["source_id"] == MONTH_OFFICER_SOURCE["id"]
    assert event["source_day_stem"] == "丙"
    assert event["protected_position"] == "month"
    assert event["alternative_kind"] == "六冲"
    assert event["alternative_positions"] == ["year", "hour"]
    clash = next(e for e in value["assessment"]["relations"] if e["kind"] == "六冲")
    assert clash["status"] == "active"
    assert clash["positions"] == event["alternative_positions"]
    month_roots = [
        row
        for row in value["assessment"]["hidden_stem_ledger"]
        if row["pillar"] == "month"
    ]
    assert month_roots
    assert all(row["remaining_mass"] == row["initial_mass"] for row in month_roots)
    assert value["branch_combination_candidates"]["screen_status"] == "reconstructed_v8"
    SourceCurrentCalculation.model_validate(value)


@pytest.mark.parametrize(
    "text",
    [
        "乙卯 戊子 丙辰 丁酉",  # 辰酉 already resolves the alternative clash.
        "乙卯 戊子 丁巳 己酉",  # Month子 is seven killing for丁.
        "乙卯 戊子 甲寅 癸酉",  # Month子 is seal for甲.
        "乙卯 戊子 丙子 丁酉",  # Repeated子 is not this source profile.
        "乙卯 戊子 丙午 丁酉",  # Another active子午 clash involves month官.
        "乙卯 乙酉 甲寅 甲子",  # Original卯日 glyph leaves reverse scope open.
    ],
)
def test_month_officer_rule_does_not_override_competition_or_other_roles(
    text: str,
) -> None:
    value = current(text)
    assert punishment(value)["status"] == "active"
    assert "alternative_positions" not in punishment(value)
    SourceCurrentCalculation.model_validate(value)


def test_existing_half_tendency_is_not_promoted_to_completed_combination_cover() -> (
    None
):
    value = current("乙卯 戊子 丙申 丁酉")
    assert punishment(value)["status"] == MONTH_OFFICER_CLASH_RESOLVED
    half = next(e for e in value["assessment"]["relations"] if e["kind"] == "半合")
    assert half["positions"] == ["month", "day"]
    assert half["status"] == "partial_tendency"
    assert not any(
        e["kind"] in {"三合", "三会", "六合"} for e in value["assessment"]["relations"]
    )
    SourceCurrentCalculation.model_validate(value)


@pytest.mark.parametrize("fault", ["wrong_role", "wrong_alternative", "inactive_clash"])
def test_month_officer_receipt_requires_its_co_known_role_and_actual_clash(
    fault: str,
) -> None:
    value = deepcopy(current("乙卯 戊子 丙寅 丁酉"))
    event = punishment(value)
    if fault == "wrong_role":
        event["source_day_stem"] = "丁"
    elif fault == "wrong_alternative":
        event["alternative_positions"] = ["month", "hour"]
    else:
        clash = next(e for e in value["assessment"]["relations"] if e["kind"] == "六冲")
        clash["status"] = "resolved_by_combination"
    with pytest.raises(ValidationError, match="月官别位|解刑替代"):
        SourceCurrentCalculation.model_validate(value)
