"""All327 source rows survive; unknowns and conflicts cannot become passes."""

import hashlib
import json
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from fatebridge.core import sukuyo_historical_calendar as historical
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_dayan_advance import (
    SOURCE,
    comparison_lines,
    month_comparison,
    validate_bundle,
)
from fatebridge.core.sukuyo_sources import load_source

FIXTURES = Path(__file__).parent / "data"


def test_every_before_code_source_and_host_row_preserves_52_conflicts_and_unknown():
    raw = (FIXTURES / "sukuyo-dayan-advance-source-v1.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "5f93a0caaf6ced3024aaf116dcc457bf99d139f44a5ba94c53402f546accd3a7"
    )
    source = json.loads(raw)
    host_raw = (FIXTURES / "sukuyo-dayan-advance-host-v1.json").read_bytes()
    assert hashlib.sha256(host_raw).hexdigest() == (
        "234d81f8e5909578fcbb2ab7badeb6e5f24613e93ab6c27fe0b1f635f286baa4"
    )
    host = json.loads(host_raw)
    assert [r["row_number"] for r in source["rows"]] == list(range(1, 328))
    counts = {True: 0, False: 0, None: 0}
    exceptions = []
    for original, expected in zip(source["rows"], host["rows"], strict=True):
        result = historical.date_reference(
            date.fromisoformat(expected["host_month_start"])
        )["dayan_advance_research_comparison"]
        assert result["selected_row"]["row_number"] == original["row_number"]
        for key in result["selected_row"]:
            assert result["selected_row"][key] == original[key]
        assert (
            result["author_proposed_day_shift_from_literal"]
            == original["author_proposed_day_shift"]
        )
        assert (
            result["mechanical_ge_assumed_limit"]
            == original["comparison_only_ge_threshold"]
        )
        assert (
            result["matches_author_direction_inference"]
            == expected["matches_author_proposal"]
        )
        assert result["host_month_start_ganzhi"] == expected["host_month_start_ganzhi"]
        assert (
            result["inferred_author_month_start_ganzhi"]
            == expected["author_proposed_month_start_ganzhi"]
        )
        assert result["proposed_absolute_civil_date"] is None
        assert not result["selected_host_calendar_rewritten"]
        counts[result["matches_author_direction_inference"]] += 1
        if result["author_direction_differs_from_ge_assumed_limit"]:
            exceptions.append(original["row_number"])
    assert counts == {True: 274, False: 52, None: 1}
    assert exceptions == [37, 48, 53, 56, 70, 76, 217, 281, 287, 304]


def test_unknown_proposal_keeps_threshold_separate_from_missing_author_direction():
    result = month_comparison(841, 11, False, host_month_start_index=33)
    assert result["selected_row"]["computed_new_moon_remainder"] == 23
    assert result["selected_row"]["author_proposed_decision_literal"] == "-"
    assert result["mechanical_ge_assumed_limit"] is False
    assert result["author_proposed_day_shift_from_literal"] is None
    assert result["matches_author_direction_inference"] is None
    text = "".join(comparison_lines(result))
    assert "记为未给结论，未补成不进" in text
    assert "不能据此替横杠补定作者进退" in text


def test_unknown_limit_does_not_remove_explicit_source_decision():
    result = month_comparison(764, 2, False, host_month_start_index=4)
    assert result["mechanical_ge_assumed_limit"] is None
    assert result["author_proposed_day_shift_from_literal"] == 0
    assert result["matches_author_direction_inference"]
    assert "想定进朔限未列，未套默认限值" in "".join(comparison_lines(result))


@pytest.mark.parametrize("month,leap", [(1, False), (6, True)])
def test_not_listed_is_not_false_or_a_reconstructed_complete_calendar(month, leap):
    assert month_comparison(764, month, leap, host_month_start_index=0) is None


@pytest.mark.parametrize(
    "args,kwargs",
    [
        ((True, 2, False), {"host_month_start_index": 4}),
        ((764, 0, False), {"host_month_start_index": 4}),
        ((764, 2, 0), {"host_month_start_index": 4}),
        ((764, 2, False), {"host_month_start_index": True}),
        ((764, 2, False), {"host_month_start_index": 60}),
        ((764, 2, False), {"host_month_start_index": -1}),
    ],
)
def test_wrong_keys_and_cycle_indices_cannot_silently_coerce_or_wrap(args, kwargs):
    with pytest.raises(ValueError):
        month_comparison(*args, **kwargs)


@pytest.mark.parametrize("mutation", ["drop", "dash", "star", "limit", "scope"])
def test_complete_source_binding_rejects_shrunk_or_rewritten_rows(mutation):
    data = deepcopy(load_source(SOURCE).data)
    if mutation == "drop":
        data["rows"].pop(262)
    elif mutation == "dash":
        data["rows"][262]["author_proposed_decision_literal"] = "不"
    elif mutation == "star":
        data["rows"][36]["author_proposed_decision_literal"] = "進"
    elif mutation == "limit":
        data["rows"][0]["assumed_limit_units"] = 6300
    else:
        data["evaluation_policy"]["applied_to_selected_host_calendar_or_mansion"] = True
    with pytest.raises(ValueError):
        validate_bundle(data)


def test_native_day_and_pair_scope_preserve_new_conflict_beside_old_provider_no_conflict():
    result = calendar_mansion(
        "0766-03-19",
        "12:00:00",
        "+09:00",
        calendar_basis="japanese_naoj_historical_utc09",
    )
    source = result["calendar_reference"]
    assert source["cross_source_comparison"] is None
    research = source["dayan_advance_research_comparison"]
    assert research["host_month_start_ganzhi"] == "丙戌"
    assert research["inferred_author_month_start_ganzhi"] == "丁亥"
    text = day_evidence(result)["reading_text"]
    assert "当前NAOJ月首干支为丙戌，两者不同" in text
    assert "在NAOJ／HuTime1001.1既有对照中未列跨来源分歧" in text
    assert "未改写当前历日、主宿、前月大小或闰小月先后" in text
    research["selected_row"]["lunar_year"] = 1900
    assert (
        month_comparison(766, 2, False, host_month_start_index=22)["selected_row"][
            "lunar_year"
        ]
        == 766
    )
