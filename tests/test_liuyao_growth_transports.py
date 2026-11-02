"""Qualified growth, source effects and same-run explanation on all surfaces."""

import pytest

from tests.test_liuyao_clash_transports import all_surfaces
from tests.test_liuyao_transports import assert_same_run_receipt

pytest_plugins = ["tests.test_agentic_nested_outputs"]


@pytest.mark.parametrize(
    "day,base,changed,position,growth,source",
    [
        ("2004-10-05", "000000", "000001", 6, True, True),
        ("2000-04-29", "000000", "000001", 6, True, None),
        ("2000-06-28", "000000", "000001", 6, None, None),
        ("2004-10-05", "011000", "010000", 3, True, False),
    ],
)
def test_growth_qualifications_and_source_effects(
    day, base, changed, position, growth, source, rest, tmp_path, capsys
):
    root = "liuyao_evidence.conditional_analysis"
    payload = dict(
        date=day,
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code=base,
        changed_code=changed,
        focus_line=5,
    )
    for result in all_surfaces(
        payload,
        [
            root + ".growth_conditions",
            root + ".generation_conditions",
            root + ".role_effects",
        ],
        rest,
        tmp_path,
        capsys,
    ):
        detail = result["liuyao_evidence"]["conditional_analysis"]
        item = detail["growth_conditions"]["lines"][position - 1]
        assert item["position_match"] is True
        assert item.get("condition_match") is growth
        assert item["raw_day_element_relation"] == "克爻"
        assert (
            detail["generation_conditions"]["sources"][position - 1].get(
                "condition_match"
            )
            is source
        )
        role = next(
            r for r in detail["role_effects"]["lines"] if r["position"] == position
        )
        assert role["atom_values"]["day_growth_peak"] is True
        assert role["conditional_atom_values"].get("day_growth_peak") is growth


def test_replaced_calendar_control_false_leaf_is_preserved(rest, tmp_path, capsys):
    field = "liuyao_evidence.conditional_analysis.growth_conditions.focus.day_control_in_calendar_oppositions"
    for result in all_surfaces(
        dict(
            date="2004-10-05",
            time="12:00:00",
            gua_code="000000",
            changed_code="000001",
            focus_line=6,
        ),
        [field],
        rest,
        tmp_path,
        capsys,
    ):
        assert result["liuyao_evidence"]["conditional_analysis"][
            "growth_conditions"
        ] == {"focus": {"day_control_in_calendar_oppositions": False}}


@pytest.mark.parametrize(
    "code,hidden_branch,flying_branch,applied",
    [("111001", "申", "辰", True), ("001101", "亥", "申", False)],
)
def test_hidden_and_flying_use_the_same_growth_qualification(
    code, hidden_branch, flying_branch, applied, rest, tmp_path, capsys
):
    root = "liuyao_evidence.conditional_analysis.hidden_conditions"
    for result in all_surfaces(
        dict(
            date="2004-10-05",
            time="12:00:00",
            gua_code=code,
            focus_kind="hidden",
            focus_line=3,
        ),
        [root],
        rest,
        tmp_path,
        capsys,
    ):
        row = next(
            h
            for h in result["liuyao_evidence"]["conditional_analysis"][
                "hidden_conditions"
            ]
            if h["position"] == 3
        )
        assert (row["branch"], row["flying_branch"]) == (hidden_branch, flying_branch)
        assert row["reception"]["calendar_growth_rule_applied"] is applied
        if applied:
            assert row["reception"]["condition_match"] is True
            assert row["reception"]["calendar_growth_source_url"].endswith("#page=97")
        else:
            assert "calendar_strikes_flying" not in row["reception"]["support_reasons"]
            assert row["reception"]["flying_growth_source_path"].endswith(
                "growth_conditions.lines.2"
            )


@pytest.mark.parametrize(
    "day,phrase",
    [
        ("2004-10-05", "已核月令独立生扶，巳日按长生条件"),
        ("2000-06-28", "不能据位置作得生"),
    ],
)
def test_same_run_growth_text_and_source_facts(
    day, phrase, rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.test_result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "growth-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    for shaped in all_surfaces(
        dict(
            date=day,
            time="12:00:00",
            gua_code="000000",
            changed_code="000001",
            focus_line=5,
        ),
        None,
        rest,
        tmp_path,
        capsys,
        budget=8192,
    ):
        original = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, original)
        assert phrase in original["snapshot_text"]
        row = original["liuyao_evidence"]["conditional_analysis"]["growth_conditions"][
            "lines"
        ][5]
        for path in row["month_support_fact_paths"]:
            value = original
            for part in path.split("."):
                value = value[int(part)] if isinstance(value, list) else value[part]
            assert value["location"] == "month"
