"""Caller mutation cannot change cached metadata or any numeric calculation."""

from copy import deepcopy

import pytest

from fatebridge.core.timing import _copy_timing_info


def mutable_ids(value):
    found = set()
    if isinstance(value, dict):
        found.add(id(value))
        for v in value.values():
            found.update(mutable_ids(v))
    elif isinstance(value, (list, tuple)):
        if isinstance(value, list):
            found.add(id(value))
        for v in value:
            found.update(mutable_ids(v))
    return found


@pytest.mark.parametrize(
    "nested",
    [
        {"solver": {"precision": {"verified": False}}},
        {"retflags": [1, 2, 4]},
        {"solver": [{"samples": [1.25, 2.5]}, {"versions": ["v1"]}]},
        {"tuple": ({"a": [1, {"b": 2}]},)},
    ],
)
def test_each_return_and_cache_own_every_nested_mutable_container(nested):
    source = {
        "pillar": "甲子",
        "solar_term_window": {
            "start_term": {"solar_model_details": nested},
            "next_term": {"solar_model_details": deepcopy(nested)},
            "days_since_start": 1.25,
        },
    }
    expected = deepcopy(source)
    first, second = _copy_timing_info(source), _copy_timing_info(source)
    assert first == second == expected
    assert not mutable_ids(source) & mutable_ids(first)
    assert not mutable_ids(source) & mutable_ids(second)
    assert not mutable_ids(first) & mutable_ids(second)
    first["solar_term_window"]["start_term"]["solar_model_details"].clear()
    assert source == second == expected


def test_no_window_scalar_cache_payload_is_also_a_new_caller_owned_dictionary():
    source = {"pillar": "甲子", "hour": 3}
    first, second = _copy_timing_info(source), _copy_timing_info(source)
    first.clear()
    assert source == second == {"pillar": "甲子", "hour": 3}
