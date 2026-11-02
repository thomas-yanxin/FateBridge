"""A complete replay comparison rejects loss, drift, duplicates and reordering."""

from copy import deepcopy

import pytest

from scripts.compare_bazi_future_clock_replays import compare_rows


@pytest.mark.parametrize(
    "change", ["drop", "duplicate", "reorder", "nested_value", "extra_field", "index"]
)
def test_replay_difference_cannot_hide_behind_summary_counts(change):
    original = [{"id": str(i), "nested": {"guard": [1, 2]}} for i in range(2)]
    merged = [dict(deepcopy(row), cohort_index=i) for i, row in enumerate(original)]
    assert compare_rows(original, merged) == 2
    if change == "drop":
        merged.pop()
    elif change == "duplicate":
        original[1] = deepcopy(original[0])
        merged[1] = dict(deepcopy(original[0]), cohort_index=1)
    elif change == "reorder":
        merged.reverse()
    elif change == "nested_value":
        merged[0]["nested"]["guard"][0] = 9
    elif change == "extra_field":
        merged[0]["ignored_failure"] = 1
    else:
        merged[0]["cohort_index"] = 1
    with pytest.raises(ValueError):
        compare_rows(original, merged)
