"""An edited day label must not erase its base witness or become a calendar."""

import hashlib
import json
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_dayan_advance import month_comparison, research_scope
from fatebridge.core.sukuyo_historical_calendar import date_reference
from fatebridge.core.sukuyo_shoku766 import (
    SOURCE,
    month_witness_comparison,
    validate_bundle,
    witness_lines,
)
from fatebridge.core.sukuyo_sources import load_source


def test_two_image_witnesses_match_before_code_facts_without_erasing_emendation():
    raw = (Path(__file__).parent / "data/sukuyo-shoku766-source-v1.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "f207ffd8d4adf29ac9f6d51c5328eb3ce8ed8087ef7388b101bbc69f9453967d"
    )
    original = json.loads(raw)
    result = month_witness_comparison(766, 2, False, host_month_start_index=22)
    assert result["witnesses"] == original["witnesses"]
    for got, expected in zip(
        result["conditional_inferences"],
        original["before_code_cyclic_reference"],
        strict=True,
    ):
        assert got["event_day_cycle_index"] == expected["event_index"]
        assert (
            got["conditional_month_start_index"]
            == expected["conditional_month_start_index"]
        )
        assert (
            got["conditional_month_start_ganzhi"]
            == expected["conditional_month_start_ganzhi"]
        )
        assert got["matches_selected_host_month_start"] == expected["matches_host22"]
    assert result["witness_day_label_conflict"]
    assert result["selected_historical_month_start"] is None
    assert result["selected_absolute_civil_date"] is None
    assert not result["genealogical_independence_established"]
    assert not result["all_cited_original_records_independently_collated"]
    assert not result["source_image_reread_at_runtime"]
    assert not any(w["february_event_has_literal_day20"] for w in result["witnesses"])


def test_condition_agreement_does_not_certify_a_history_or_rewrite_host():
    r = month_witness_comparison(766, 2, False, host_month_start_index=23)
    assert [
        v["matches_selected_host_month_start"] for v in r["conditional_inferences"]
    ] == [True, False]
    assert r["selected_historical_month_start"] is None
    assert not r["evaluation_policy"]["selected_host_rewritten"]
    r["witnesses"][0]["event_day_ganzhi_literal"] = "甲午"
    fresh = month_witness_comparison(766, 2, False, host_month_start_index=22)
    assert fresh["witnesses"][0]["event_day_ganzhi_literal"] == "丙午"


@pytest.mark.parametrize("month,leap", [(2, True), (1, False), (3, False)])
def test_not_extended_to_another_month_or_leap_key(month, leap):
    assert month_witness_comparison(766, month, leap, host_month_start_index=22) is None


@pytest.mark.parametrize(
    "year,month,leap,host",
    [
        (True, 2, False, 22),
        (766, 0, False, 22),
        (766, 2, 0, 22),
        (766, 2, False, True),
        (766, 2, False, 60),
    ],
)
def test_bad_keys_are_not_silent_wrapping_or_coercion(year, month, leap, host):
    with pytest.raises(ValueError):
        month_witness_comparison(year, month, leap, host_month_start_index=host)


@pytest.mark.parametrize(
    "mutation", ["drop", "base", "editor", "day20", "human", "calendar"]
)
def test_witness_or_acceptance_tampering_rejected(mutation):
    data = deepcopy(load_source(SOURCE).data)
    if mutation == "drop":
        data["witnesses"].pop()
    elif mutation == "base":
        data["witnesses"][1]["event_day_ganzhi_literal"] = "丙午"
    elif mutation == "editor":
        data["witnesses"][0]["editorial_note_literal"] = None
    elif mutation == "day20":
        data["witnesses"][0]["february_event_has_literal_day20"] = True
    elif mutation == "human":
        data["evaluation_policy"]["human_or_blind_collation"] = True
    else:
        data["evaluation_policy"]["selected_host_rewritten"] = True
    with pytest.raises(ValueError):
        validate_bundle(data)


def test_actual_month_days_bind_same_month_source_and_keep_all_52_conflicts():
    first = date(766, 3, 19)
    for offset in range(30):
        c = date_reference(first + timedelta(days=offset))
        table = c["dayan_advance_research_comparison"]
        assert table["selected_row"]["row_number"] == 8
        assert table["host_month_start_index"] == 22
        w = table["selected_original_witness_comparison"]
        assert w["host_month_start_index"] == 22
        assert [
            v["conditional_month_start_index"] for v in w["conditional_inferences"]
        ] == [23, 11]
        assert not table["matches_author_direction_inference"]
    assert (
        month_comparison(775, 2, False, host_month_start_index=3)[
            "selected_original_witness_comparison"
        ]
        is None
    )


def test_product_explanation_preserves_base_emendation_retrospection_and_limits():
    c = calendar_mansion(
        "0766-03-19",
        "12:00:00",
        "+09:00",
        calendar_basis="japanese_naoj_historical_utc09",
    )
    text = day_evidence(c)["reading_text"]
    for fragment in [
        "原作甲午，据一本改",
        "二十日来自同书六月回指",
        "不是两次独立历史观测",
        "两个条件干支不是两个已认证历法候选",
        "未获独立人工校勘",
        "52项研究方向分歧仍保留",
    ]:
        assert fragment in text
    r = c["calendar_reference"]["dayan_advance_research_comparison"][
        "selected_original_witness_comparison"
    ]
    assert "月首丁亥" in "".join(witness_lines(r))
    assert "乙亥" in text


def test_complete_fixed_host_scope_preserves_every_before_code_row_and_unknown():
    raw = (
        Path(__file__).parent / "data/sukuyo-dayan-advance-host-v1.json"
    ).read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "234d81f8e5909578fcbb2ab7badeb6e5f24613e93ab6c27fe0b1f635f286baa4"
    )
    expected = json.loads(raw)["rows"]
    scope = research_scope()
    assert scope["complete_selected_research_rows"] == 327
    assert (
        scope["real_samples"]
        == load_source(
            Path(__file__).resolve().parents[1]
            / "src/fatebridge/data/sukuyo_dayan_advance_2022.json"
        ).data["evaluation_policy"]["real_samples"]
        == 0
    )
    for key, value in [
        ("same_direction_rows", True),
        ("different_direction_rows", False),
        ("unknown_direction_rows", None),
    ]:
        assert scope[key] == [
            r["row_number"] for r in expected if r["matches_author_proposal"] is value
        ]
    assert [
        len(scope[k])
        for k in [
            "same_direction_rows",
            "different_direction_rows",
            "unknown_direction_rows",
        ]
    ] == [274, 52, 1]
    scope["different_direction_rows"].clear()
    assert len(research_scope()["different_direction_rows"]) == 52


@pytest.mark.parametrize("civil,row", [("0766-04-18", None), ("0861-06-15", 325)])
def test_no_selected_image_or_research_row_is_explicit_in_actual_product(civil, row):
    c = calendar_mansion(
        civil, "12:00:00", "+09:00", calendar_basis="japanese_naoj_historical_utc09"
    )
    ref = c["calendar_reference"]
    research = ref["dayan_advance_research_comparison"]
    assert (research is None) == (row is None)
    if row is not None:
        assert research["selected_row"]["row_number"] == row
        assert research["selected_original_witness_comparison"] is None
    text = day_evidence(c)["reading_text"]
    assert "274相合、52不同、1未知" in text
    assert "本组证据的真实预测样本数为0，现实预测效力未建立" in text
    assert "不沿用766年二月" in text if row is None else "不将别月甲午／丙午" in text
    assert "为空" in text
