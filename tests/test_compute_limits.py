"""Shared service execution bounds actual work and releases failed slots."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import BoundedSemaphore, Event, Lock

import pytest
from pydantic import BaseModel

from fatebridge.application import execution
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.services.tool_catalog import CATALOG


class Value(BaseModel):
    value: int


def test_heavy_shared_execution_is_bounded_across_callers(monkeypatch):
    monkeypatch.setattr(execution, "HEAVY_CALCULATIONS", BoundedSemaphore(2))
    release, occupied = Event(), Event()
    mutex = Lock()
    active = 0
    maximum = 0

    def service():
        nonlocal active, maximum
        with mutex:
            active += 1
            maximum = max(maximum, active)
            if active == 2:
                occupied.set()
        release.wait(timeout=5)
        with mutex:
            active -= 1
        return {"value": 1}

    spec = ToolSpec(
        key="review_budget",
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
            pool.submit(execution.execute_spec, spec, Value(value=1)) for _ in range(4)
        ]
        assert occupied.wait(timeout=5)
        release.set()
        assert [future.result(timeout=5) for future in futures] == [{"value": 1}] * 4
    assert maximum == 2

    def broken():
        raise RuntimeError("synthetic failure")

    failed = replace(spec, bind=lambda _: (broken, (), {}))
    with pytest.raises(RuntimeError, match="synthetic failure"):
        execution.execute_spec(failed, Value(value=1))
    assert execution.execute_spec(spec, Value(value=1)) == {"value": 1}


def test_expensive_astronomical_and_interval_tools_declare_the_budget():
    specs = {spec.key: spec for spec in CATALOG}
    for key in [
        "human_design",
        "astro_india",
        "astro_germany",
        "astro_chart",
        "western_timing_analysis",
        "pd",
        "astro_horary",
        "astro_election",
        "astro_distributions",
        "taiyi",
        "qimen",
        "ziwei_horoscope",
        "canping",
        "heluo",
        "sanshiunited",
    ]:
        assert specs[key].cpu_bound, key
    assert not specs["knowledge_read"].cpu_bound
    assert not specs["ziwei_rules"].cpu_bound
