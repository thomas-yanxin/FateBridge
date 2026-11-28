"""Isomorphism, default_omit, omitted_fields, and payload budget tests for Compatibility."""

from __future__ import annotations

import json
from typing import Any

import pytest

from fatebridge.application.examples import example_input
from fatebridge.application.execution import execute_with_receipt
from fatebridge.application.response_delivery import deliver_response
from fatebridge.services.tool_catalog import CATALOG

SPEC = next(spec for spec in CATALOG if spec.name == "bazi_compatibility")


def _assert_isomorphic_subset(subset: Any, superset: Any, path: str = "$") -> None:
    if isinstance(subset, dict):
        assert isinstance(
            superset, dict
        ), f"{path}: expected dict, got {type(superset)}"
        for key, value in subset.items():
            assert key in superset, f"{path}.{key}: missing from full canonical payload"
            _assert_isomorphic_subset(value, superset[key], f"{path}.{key}")
    elif isinstance(subset, list):
        assert isinstance(
            superset, list
        ), f"{path}: expected list, got {type(superset)}"
        assert len(subset) == len(
            superset
        ), f"{path}: list length mismatch {len(subset)} != {len(superset)}"
        for index, (sub_item, super_item) in enumerate(zip(subset, superset)):
            _assert_isomorphic_subset(sub_item, super_item, f"{path}[{index}]")
    else:
        assert subset == superset, f"{path}: {subset!r} != {superset!r}"


def _business(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k != "run_metadata"}


def test_bazi_compatibility_default_omit_isomorphism_and_budget() -> None:
    req = SPEC.request_model(**(example_input(SPEC) or {}))
    canonical = execute_with_receipt(SPEC, req)

    default_payload = deliver_response(canonical, spec=SPEC)
    full_payload = deliver_response(canonical, spec=SPEC, include=["*"])

    default_bytes = len(json.dumps(default_payload, ensure_ascii=False).encode("utf-8"))
    assert (
        default_bytes <= 10240
    ), f"bazi_compatibility default too large: {default_bytes}"

    _assert_isomorphic_subset(_business(default_payload), _business(full_payload))

    assert "directional_ten_gods" not in default_payload
    assert "directional_punishments" not in default_payload["cross_chart_relations"]
    assert "calendar_context" not in default_payload["natal_contexts"]["person1"]
    assert "calendar_context" not in default_payload["natal_contexts"]["person2"]
    assert "day_master" not in default_payload["natal_contexts"]["person1"]
    assert "day_master" not in default_payload["natal_contexts"]["person2"]

    assert default_payload["run_metadata"]["omitted_fields"] == [
        "natal_contexts.*.calendar_context",
        "natal_contexts.*.day_master",
        "cross_chart_relations.directional_punishments",
        "directional_ten_gods",
    ]
    assert "omitted_fields" not in full_payload["run_metadata"]


def test_bazi_compatibility_include_dotted_paths_and_wildcard_specialization() -> None:
    req = SPEC.request_model(**(example_input(SPEC) or {}))
    canonical = execute_with_receipt(SPEC, req)

    with_ten_gods = deliver_response(
        canonical, spec=SPEC, include=["directional_ten_gods"]
    )
    assert "directional_ten_gods" in with_ten_gods
    assert with_ten_gods["run_metadata"]["omitted_fields"] == [
        "natal_contexts.*.calendar_context",
        "natal_contexts.*.day_master",
        "cross_chart_relations.directional_punishments",
    ]

    with_p1_cal = deliver_response(
        canonical, spec=SPEC, include=["natal_contexts.person1.calendar_context"]
    )
    assert "calendar_context" in with_p1_cal["natal_contexts"]["person1"]
    assert "calendar_context" not in with_p1_cal["natal_contexts"]["person2"]
    assert (
        "natal_contexts.*.calendar_context"
        in with_p1_cal["run_metadata"]["omitted_fields"]
    )

    with_p1_dm = deliver_response(
        canonical, spec=SPEC, include=["natal_contexts.person1.day_master"]
    )
    assert "day_master" in with_p1_dm["natal_contexts"]["person1"]
    assert "day_master" not in with_p1_dm["natal_contexts"]["person2"]
    assert "natal_contexts.*.day_master" in with_p1_dm["run_metadata"]["omitted_fields"]

    with_all_omitted = deliver_response(
        canonical,
        spec=SPEC,
        include=list(SPEC.default_omit),
    )
    assert "omitted_fields" not in with_all_omitted["run_metadata"]
    assert _business(with_all_omitted) == _business(
        deliver_response(canonical, spec=SPEC, include=["*"])
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "person1_name": "张三",
            "person2_name": "李四",
        },
        {
            "person1_name": "测试甲方超长姓名",
            "person1_birth_second": 15,
            "person2_name": "测试乙方超长姓名",
            "person2_birth_second": 45,
        },
    ],
)
def test_bazi_compatibility_dense_cross_chart_adversarial_budget_and_isomorphism(
    overrides: dict[str, Any],
) -> None:
    req = SPEC.request_model(
        person1_birth_year=1984,
        person1_birth_month=2,
        person1_birth_day=4,
        person1_birth_hour=23,
        person1_birth_minute=30,
        person1_birth_place="北京市朝阳区",
        person1_birth_longitude=116.4,
        person1_gender="男",
        person2_birth_year=1990,
        person2_birth_month=8,
        person2_birth_day=8,
        person2_birth_hour=11,
        person2_birth_minute=45,
        person2_birth_place="上海市浦东新区",
        person2_birth_longitude=121.5,
        person2_gender="女",
        relationship_type="marriage",
        **overrides,
    )
    canonical = execute_with_receipt(SPEC, req)

    default_payload = deliver_response(canonical, spec=SPEC)
    full_payload = deliver_response(canonical, spec=SPEC, include=["*"])
    default_bytes = len(json.dumps(default_payload, ensure_ascii=False).encode("utf-8"))

    assert (
        default_bytes <= 9500
    ), f"bazi_compatibility dense+district exceeded 9500 B: {default_bytes}"
    _assert_isomorphic_subset(_business(default_payload), _business(full_payload))
    assert default_payload["run_metadata"]["omitted_fields"] == [
        "natal_contexts.*.calendar_context",
        "natal_contexts.*.day_master",
        "cross_chart_relations.directional_punishments",
        "directional_ten_gods",
    ]
