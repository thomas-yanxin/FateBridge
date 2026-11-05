"""Shared own-back-support facts and control qualifications on three surfaces."""

import pytest

from tests.test_agentic_nested_outputs import business
from tests.test_liuyao_clash_transports import all_surfaces
from tests.test_liuyao_transports import assert_same_run_receipt


@pytest.mark.parametrize(
    "day,base,changed,source,target,back,control",
    [
        ("2002-01-29", "010011", "010010", 6, 4, True, True),
        ("2002-05-27", "100110", "100101", 5, 2, True, True),
        ("2000-02-29", "110110", "110100", 5, 2, False, None),
        ("2000-02-29", "110110", "110101", 5, 2, True, True),
    ],
)
def test_shared_back_support_and_control_across_transports(
    day, base, changed, source, target, back, control, rest, tmp_path, capsys
):
    payload = dict(
        date=day,
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code=base,
        changed_code=changed,
        focus_line=target,
    )
    # Modern synthetic input labels only, never ancient civil years.
    root = "liuyao_evidence.conditional_analysis"
    fields = [
        f"{root}.back_generation_conditions",
        f"{root}.control_conditions",
        f"{root}.generation_conditions",
        f"{root}.lines",
    ]
    for output in all_surfaces(payload, fields, rest, tmp_path, capsys):
        detail = output["liuyao_evidence"]["conditional_analysis"]
        support = detail["back_generation_conditions"]["sources"][source - 1]
        assert support.get("condition_match") is back
        pair = next(
            c
            for c in detail["control_conditions"]["controls"]
            if (c["source_position"], c["target_position"]) == (source, target)
        )
        assert pair.get("condition_match") is control
        assert pair["back_generation_source_path"] == support["source_path"]
        assert (
            detail["generation_conditions"]["sources"][source - 1][
                "back_generation_source_path"
            ]
            == support["source_path"]
        )
        if changed == "110101":
            assert detail["lines"][3]["activity_condition_match"] is True


def test_static_false_back_support_leaf_needs_no_siblings(rest, tmp_path, capsys):
    field = "liuyao_evidence.conditional_analysis.back_generation_conditions.focus.condition_match"
    payload = dict(
        date="2000-08-15",
        time="12:00:00",
        gua_code="110110",
        changed_code="110010",
        focus_line=5,
    )
    for output in all_surfaces(payload, [field], rest, tmp_path, capsys):
        assert output["liuyao_evidence"]["conditional_analysis"][
            "back_generation_conditions"
        ] == {"focus": {"condition_match": False}}


def test_same_run_back_support_control_and_snapshot_preserve_original_harm(
    rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.test_result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "rescue-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    payload = dict(
        date="2002-01-29",
        time="12:00:00",
        gua_code="010011",
        changed_code="010010",
        focus_line=4,
    )
    restored = []
    for shaped in all_surfaces(payload, None, rest, tmp_path, capsys, budget=8192):
        original = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, original)
        detail = original["liuyao_evidence"]["conditional_analysis"]
        pair = next(
            c
            for c in detail["control_conditions"]["controls"]
            if (c["source_position"], c["target_position"]) == (6, 4)
        )
        assert pair["condition_match"] is True and pair["source_rescue_used"] is True
        assert any(h["location"] == "day" for h in pair["source_calendar_oppositions"])
        assert (
            detail["classical_assessment"]["lines"][5]["strength"].get("is_supported")
            is None
        )
        support = detail["back_generation_conditions"]["sources"][5]
        assert support["changed_calendar_relations"] == {"month": "克爻", "day": "生爻"}
        assert "第6爻卯本位化子：回头生空破门槛匹配" in original["snapshot_text"]
        assert "本位回头生支持该条件，原日月反制仍保留" in original["snapshot_text"]
        assert (
            detail["back_generation_conditions"]["scope"] in original["snapshot_text"]
        )
        path = "liuyao_evidence.conditional_analysis.back_generation_conditions"
        assert (
            reconstruct(store, shaped["result_delivery"]["result_id"], path)
            == detail["back_generation_conditions"]
        )
        restored.append(business(original))
    assert restored[0] == restored[1] == restored[2]
