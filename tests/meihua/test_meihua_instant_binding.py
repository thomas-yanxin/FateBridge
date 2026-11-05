"""A self-consistent clock receipt still has to match the actual request instant."""

import hashlib
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest

from fatebridge.application import meihua_clock_binding as binding
from fatebridge.application.execution import execute_tool
from fatebridge.services.tool_catalog import CATALOG
from tests.support.meihua_instant_binding_reference import (
    clock_of,
    load,
    mutate,
    new_result,
)

CASES, PROTOCOL = load()
BY_ID = {r["id"]: r for r in CASES}
SPEC = next(s for s in CATALOG if s.key == "meihua_analysis")


@lru_cache(maxsize=None)
def original(case_id):
    return new_result(BY_ID[case_id])


def test_fault_definitions_were_frozen_before_production_changes():
    from tests.support import meihua_instant_binding_reference as helper

    assert (
        hashlib.sha256(Path(helper.__file__).read_bytes()).hexdigest()
        == "bc5443cc518679f572d2c14f4bf8a54de4826dde47ed35e4b001ffcb664d54f6"
    )
    assert PROTOCOL["precedes_production_change"] is True
    assert not PROTOCOL["independent_expert_or_real_world_predictive_validation"]
    assert len(PROTOCOL["faults"]) == 34


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_all25_declared_clock_instants_and_fold_choices_stay_valid(case):
    request, value = original(case["id"])
    saved = deepcopy(value)
    clock = clock_of(value)
    assert clock["local_datetime"] == case["expected_local"]
    assert clock["instant_utc"] == case["expected_utc"]
    assert clock["resolved_utc_offset"] == case["expected_offset"]
    assert clock["fold"] == case["expected_fold"]
    binding.require_meihua_clock_binding(value, request)
    assert saved == value


@pytest.mark.parametrize("fault", PROTOCOL["faults"], ids=lambda c: c["id"])
def test_all34_inconsistent_complete_packets_fail_the_clock_binding(fault):
    req, value = original(fault["base_case"])
    with pytest.raises(ValueError):
        binding.require_meihua_clock_binding(mutate(value, fault["id"]), req)


@pytest.mark.parametrize("fault", PROTOCOL["faults"], ids=lambda c: c["id"])
def test_all34_packets_remain_internal_errors_in_real_shared_execution(fault):
    req, value = original(fault["base_case"])
    bad = mutate(value, fault["id"])
    spec = replace(SPEC, bind=lambda _: (lambda: deepcopy(bad), (), {}))
    out = execute_tool(spec, req)
    assert out["status_code"] == 500 and out["error_code"] == "internal_error"
    assert out["retryable"] is True


@pytest.mark.parametrize(
    "variant", PROTOCOL["positive_representation_variants"], ids=lambda c: c["id"]
)
def test_equivalent_representations_do_not_become_false_clock_errors(variant):
    req, value = original(variant["base_case"])
    binding.require_meihua_clock_binding(mutate(value, variant["id"]), req)


def test_guard_resolves_the_request_without_rerunning_the_producer(monkeypatch):
    req, value = original("known-plus8")
    calls = []
    real = binding.resolve_civil_clock

    def capture(wall, zone, offset):
        calls.append((wall.isoformat(), zone, offset))
        return real(wall, zone, offset)

    def forbidden(*a, **kw):
        raise AssertionError(
            "The public producer or astronomical solver must not be its own oracle"
        )

    import fatebridge.core.almanac as almanac
    import fatebridge.services.divination as service

    monkeypatch.setattr(binding, "resolve_civil_clock", capture)
    monkeypatch.setattr(service, "calculate_meihua_analysis", forbidden)
    monkeypatch.setattr(service.BaZiCalendar, "get_four_pillars", forbidden)
    monkeypatch.setattr(service, "build_calendar_context", forbidden)
    monkeypatch.setattr(almanac, "get_solar_terms_for_year", forbidden)
    binding.require_meihua_clock_binding(value, req)
    assert calls == [("2000-01-06T09:17:43", "+08:00", None)]
    with pytest.raises(ValueError):
        binding.require_meihua_clock_binding(mutate(value, "clock_UTC_one_day"), req)


@pytest.mark.parametrize(
    "path",
    [
        ("bazi_month_boundary", "days_since_start"),
        ("bazi_month_boundary", "days_until_next"),
        ("solar_term_delta", "days_since_current"),
        ("solar_term_delta", "days_until_next"),
    ],
)
def test_derived_day_durations_must_also_use_the_same_UTC_labels(path):
    # Supplemental engineering probes after the original34-fault freeze;
    # not new independent chronology or physical observations.
    req, value = original("known-plus8")
    broken = deepcopy(value)
    broken["calendar_context"][path[0]][path[1]] += 1
    with pytest.raises(ValueError):
        binding.require_meihua_clock_binding(broken, req)
