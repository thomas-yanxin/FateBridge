"""Shared service execution bounds actual work and releases failed slots."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import BoundedSemaphore, Event, Lock

import pytest
from pydantic import BaseModel

from fatebridge.application import execution
from fatebridge.application.compute_limits import (
    HeavyCalculationBudget,
    heavy_calculation_budget,
)
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.services.tool_catalog import CATALOG


class Value(BaseModel):
    value: int


def test_heavy_shared_execution_is_bounded_across_callers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bound concurrent callers and release the permit when a service fails."""
    assert heavy_calculation_budget() is execution.heavy_calculation_budget()
    semaphore = BoundedSemaphore(2)
    budget = HeavyCalculationBudget(max_concurrency=2, semaphore=semaphore)
    monkeypatch.setattr(execution, "heavy_calculation_budget", lambda: budget)
    release, occupied = Event(), Event()
    mutex = Lock()
    active = 0
    maximum = 0

    def service() -> dict[str, int]:
        nonlocal active, maximum
        with mutex:
            active += 1
            maximum = max(maximum, active)
            if active == 2:
                occupied.set()
            else:
                pass
        release.wait(timeout=5)
        with mutex:
            active -= 1
        return {"value": 1}

    spec = ToolSpec(
        name="review_budget",
        bind=lambda _: (service, (), {}),
        request_model=Value,
        output_model=Value,
        required_output_fields=("value",),
        summary="budget",
        operation_label_zh="budget",
        family="test",
        cpu_bound=True,
    )
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(execution.invoke_validated_service, spec, Value(value=1))
            for _ in range(4)
        ]
        assert occupied.wait(timeout=5)
        release.set()
        assert [future.result(timeout=5) for future in futures] == [{"value": 1}] * 4
    assert maximum == 2

    def broken() -> dict[str, int]:
        raise RuntimeError("synthetic failure")

    failed = replace(spec, bind=lambda _: (broken, (), {}))
    with pytest.raises(RuntimeError, match="synthetic failure"):
        execution.invoke_validated_service(failed, Value(value=1))
    assert semaphore.acquire(blocking=False)
    try:
        assert semaphore.acquire(blocking=False), "A failing service leaked its permit"
        semaphore.release()
    finally:
        semaphore.release()


def test_expensive_astronomical_and_interval_tools_declare_the_budget() -> None:
    specs = {spec.name: spec for spec in CATALOG}
    for key in [
        "human_design",
        "vedic_chart",
        "hamburg_midpoint_chart",
        "astrology_chart",
        "western_timing",
        "primary_directions",
        "horary_chart",
        "evaluate_election_time",
        "bounds_directions",
        "taiyi",
        "qimen",
        "ziwei_timing",
        "canping",
        "heluo",
        "sanshi_combined_chart",
    ]:
        assert specs[key].cpu_bound, key
    assert not specs["knowledge_read"].cpu_bound
    assert not specs["ziwei_rules"].cpu_bound
