"""Generation conditions and target gates survive all public transports."""

import pytest

from tests.test_agentic_nested_outputs import business
from tests.test_liuyao_clash_transports import all_surfaces
from tests.test_liuyao_transports import assert_same_run_receipt


@pytest.mark.parametrize(
    "day,base,changed,source,target,can_generate,benefit",
    [
        ("2002-01-29", "010011", "010010", 6, 5, True, None),
        ("2002-05-27", "011110", "011101", 5, 4, True, False),
        ("2000-02-26", "111111", "111110", 6, 5, False, False),
    ],
)
def test_source_generation_and_target_gate_are_equal_across_transports(
    day, base, changed, source, target, can_generate, benefit, rest, tmp_path, capsys
):
    payload = dict(
        date=day,
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code=base,
        changed_code=changed,
        focus_line=target,
    )
    # Modern synthetic dates test transport. No ancient civil year inferred.
    field = "liuyao_evidence.conditional_analysis.generation_conditions"
    for output in all_surfaces(payload, [field], rest, tmp_path, capsys):
        detail = output["liuyao_evidence"]["conditional_analysis"][
            "generation_conditions"
        ]
        pair = next(
            g
            for g in detail["generations"]
            if (g["source_position"], g["target_position"]) == (source, target)
        )
        assert (
            pair.get("condition_match") is can_generate
            and pair.get("benefit_now") is benefit
        )
        assert pair["status"] and pair["target_status"]


def test_false_reception_leaf_projects_without_other_generation_fields(
    rest, tmp_path, capsys
):
    field = "liuyao_evidence.conditional_analysis.generation_conditions.focus.target_reception_condition"
    payload = dict(
        date="2002-05-27",
        time="12:00:00",
        gua_code="011110",
        changed_code="011101",
        focus_line=4,
    )
    for output in all_surfaces(payload, [field], rest, tmp_path, capsys):
        assert output["liuyao_evidence"]["conditional_analysis"][
            "generation_conditions"
        ] == {"focus": {"target_reception_condition": False}}


def test_same_run_generation_and_snapshot_keep_injury_and_target_void(
    rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.test_result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "generation-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    payload = dict(
        date="2002-01-29",
        time="12:00:00",
        gua_code="010011",
        changed_code="010010",
        focus_line=5,
    )
    restored = []
    for shaped in all_surfaces(payload, None, rest, tmp_path, capsys, budget=8192):
        original = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, original)
        detail = original["liuyao_evidence"]["conditional_analysis"]
        gen = detail["generation_conditions"]
        source = gen["sources"][5]
        assert (
            source["condition_match"] is True
            and source["strength_supported_unopposed"] is False
        )
        assert any(
            a["location"] == "day" for a in source["retained_calendar_oppositions"]
        )
        assert gen["focus"]["target_reception_condition"] is None
        assert detail["void_conditions"]["focus"]["is_xunkong"] is True
        assert gen["scope"] in original["snapshot_text"]
        assert (
            "第6爻卯生第5爻巳：生源条件匹配；受生爻空破前提待审"
            in original["snapshot_text"]
        )
        path = "liuyao_evidence.conditional_analysis.generation_conditions"
        assert reconstruct(store, shaped["result_delivery"]["result_id"], path) == gen
        restored.append(business(original))
    assert restored[0] == restored[1] == restored[2]
