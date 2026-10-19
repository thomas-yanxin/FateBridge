"""Contract caching preserves wire schemas and never caches user executions."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import ClassVar

import pytest
from pydantic import BaseModel, create_model

from fatebridge.application.description import describe_input_spec, describe_spec
from fatebridge.application.execution import execute_tool
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.schema_cache import (
    clear_contract_caches,
    contract_fingerprint,
    model_schema,
)
from fatebridge.services.replay_metadata import digest


@pytest.fixture(autouse=True)
def clean_caches():
    clear_contract_caches()
    yield
    clear_contract_caches()


def test_contract_hash_matches_uncached_wire_schema_and_isolates_public_copies():
    class Request(BaseModel):
        value: int

    class Output(BaseModel):
        items: list[Request]

    expected = digest(
        {"input": Request.model_json_schema(), "output": Output.model_json_schema()}
    )
    assert contract_fingerprint(Request, Output) == expected
    snapshot = model_schema(Output)
    snapshot["$defs"]["Request"]["properties"]["value"]["type"] = "string"
    assert model_schema(Output) == Output.model_json_schema()
    assert contract_fingerprint(Request, Output) == expected


def test_same_name_models_and_output_overrides_have_independent_contracts():
    integer = create_model("SameName", value=(int, ...))
    string = create_model("SameName", value=(str, ...))
    assert model_schema(integer) != model_schema(string)
    assert contract_fingerprint(integer, integer) != contract_fingerprint(
        integer, string
    )
    assert contract_fingerprint(integer, None) == digest(
        {"input": integer.model_json_schema(), "output": None}
    )


def test_concurrent_cold_calls_generate_one_schema_per_model():
    class Counted(BaseModel):
        value: int
        calls: ClassVar[int] = 0

        @classmethod
        def model_json_schema(cls, **kwargs):
            cls.calls += 1
            return super().model_json_schema(**kwargs)

    barrier = Barrier(8)

    def read():
        barrier.wait(timeout=5)
        return model_schema(Counted), contract_fingerprint(Counted, Counted)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: read(), range(8)))
    assert Counted.calls == 1
    assert all(result == results[0] for result in results)
    assert results[0][0] is not results[1][0]


def test_model_rebuild_invalidates_contract_revision():
    class Mutable(BaseModel):
        value: int

    before = contract_fingerprint(Mutable, None)
    Mutable.model_fields["value"].annotation = str
    Mutable.model_rebuild(force=True)
    assert model_schema(Mutable)["properties"]["value"]["type"] == "string"
    assert contract_fingerprint(Mutable, None) != before


def test_failed_generation_is_not_cached_and_schema_hooks_can_be_invalidated():
    class Hooked(BaseModel):
        value: int
        fail: ClassVar[bool] = True
        label: ClassVar[str] = "first"

        @classmethod
        def model_json_schema(cls, **kwargs):
            if cls.fail:
                raise ValueError("schema generation failed")
            return {**super().model_json_schema(**kwargs), "title": cls.label}

    with pytest.raises(ValueError, match="schema generation failed"):
        contract_fingerprint(Hooked, None)
    Hooked.fail = False
    before = contract_fingerprint(Hooked, None)
    Hooked.label = "second"
    clear_contract_caches()
    assert model_schema(Hooked)["title"] == "second"
    assert contract_fingerprint(Hooked, None) != before


def test_user_inputs_results_and_receipts_still_execute_per_call():
    class Request(BaseModel):
        value: int

    class Output(BaseModel):
        doubled: int

    seen = []

    def service(value):
        seen.append(value)
        return {"doubled": value * 2}

    spec = ToolSpec(
        key="cache_regression",
        bind=lambda request: (service, (request.value,), {}),
        request_model=Request,
        output_model=Output,
        summary="",
        operation_label_zh="test",
        family="test",
    )
    first = execute_tool(spec, Request(value=2))
    second = execute_tool(spec, Request(value=3))
    assert seen == [2, 3]
    assert first["doubled"] == 4 and second["doubled"] == 6
    left, right = first["run_metadata"], second["run_metadata"]
    assert left["contract_sha256"] == right["contract_sha256"]
    for field in ("input_sha256", "business_output_sha256", "run_id", "trace_id"):
        assert left[field] != right[field]


def test_input_discovery_does_not_materialize_output_schema():
    class Request(BaseModel):
        value: int

    class Output(BaseModel):
        value: int
        schema_calls: ClassVar[int] = 0

        @classmethod
        def model_json_schema(cls, **kwargs):
            cls.schema_calls += 1
            return super().model_json_schema(**kwargs)

    spec = ToolSpec(
        key="review_probe",
        bind=lambda request: (lambda: {"value": request.value}, (), {}),
        request_model=Request,
        output_model=Output,
        summary="Probe",
        operation_label_zh="探针",
        family="test",
    )
    clear_contract_caches()
    try:
        compact = describe_input_spec(spec)
        assert Output.schema_calls == 0
        assert compact["output_fields"] == ["value"]
        full = describe_spec(spec)
        assert Output.schema_calls == 1
        assert {key: compact[key] for key in full if key != "output_schema"} == {
            key: value for key, value in full.items() if key != "output_schema"
        }
    finally:
        clear_contract_caches()
