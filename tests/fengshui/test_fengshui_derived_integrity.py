"""Consistent raw plates cannot justify contradictory derived numeric claims."""

import asyncio
import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastmcp import Client

from fatebridge.cli import run
from fatebridge.core.fengshui import xuankong
from fatebridge.core.fengshui.models import XuankongRequest
from fatebridge.core.fengshui.structure_integrity import validate_natal_structure
from fatebridge.mcp_server import create_mcp_app
from fatebridge.utils.errors import FengshuiCalculationError
from fatebridge.validation.fengshui_reading import verify_fengshui_reading
from tests.fengshui.test_fengshui_source_comparison import request
from tests.fengshui.test_fengshui_surfaces import rest_client


def corrupt(result, fault):
    result = deepcopy(result)
    patterns = result["classical_patterns"]
    if fault == "sum":
        result["combination_of_ten"][0]["palace_sums"]["C"] = 999
    elif fault == "sum_flag":
        pair = result["combination_of_ten"][0]
        pair["all_nine_sum_to_ten"] = not pair["all_nine_sum_to_ten"]
    elif fault == "distribution":
        result["distribution"]["traditional_label"] = "保证发财"
    elif fault == "parental":
        palace = patterns["parental_triples"]["palaces"]["C"]
        palace["matched_group"] = (
            None if palace["matched_group"] is not None else [1, 4, 7]
        )
    elif fault == "ground":
        side = patterns["ground_comparison"]["roles"]["mountain"]
        side["whole_ground_repeat"] = not side["whole_ground_repeat"]
    elif fault == "named":
        named = patterns["volume_two_named_refrain"]
        named["numeric_match"] = not named["numeric_match"]
    elif fault == "opposite":
        patterns["opposite_star_comparison"]["pairs"]["N"]["sum"] = 999
    elif fault == "center":
        patterns["opposite_star_comparison"]["center_numeric_pair"][
            "spatial_opposite_exists"
        ] = True
    elif fault == "missing":
        del result["combination_of_ten"][0]["palace_sums"]["SE"]
    else:
        raise AssertionError(fault)
    return result


@pytest.mark.parametrize(
    "fault",
    [
        "sum",
        "sum_flag",
        "distribution",
        "parental",
        "ground",
        "named",
        "opposite",
        "center",
        "missing",
    ],
)
@pytest.mark.parametrize("name", ["xuankong_natal", "assess"])
def test_actual_public_transports_reject_false_derived_claims(
    monkeypatch, tmp_path, capsys, fault, name
):
    original = xuankong.natal_structure
    monkeypatch.setattr(
        xuankong, "natal_structure", lambda chart: corrupt(original(chart), fault)
    )
    inputs = request(
        interpretation={
            "current_period_number": 9,
            "period_evidence": "虚构评价运",
            "include_calculation_reading": True,
        }
    )
    if name == "assess":
        inputs = {
            "methods": ["xuankong_natal"],
            "house": inputs["house"],
            "xuankong": {k: v for k, v in inputs.items() if k != "house"},
        }

    async def call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "fengshui_" + name,
                {
                    **inputs,
                    "fields": ["summary"],
                    "strict_fields": True,
                    "response_char_limit": 0,
                },
                raise_on_error=False,
            )

    http = rest_client(monkeypatch).post(
        "/api/fengshui/" + name,
        json=inputs,
        params={"fields": "summary", "strict_fields": "true"},
    )
    protocol = asyncio.run(call())
    path = tmp_path / "derived.json"
    path.write_text(json.dumps(inputs), encoding="utf-8")
    code = run(
        [
            "fengshui_" + name,
            "--request-file",
            str(path),
            "--fields",
            "summary",
            "--strict-fields",
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 503 and protocol.is_error and code == 1
    strip = lambda obj: {
        k: v for k, v in obj.items() if k not in {"operation", "status_code"}
    }
    assert http.json() == strip(protocol.structured_content) == strip(cli)
    assert http.json()["error_code"] == "fengshui_calculation_inconsistent"
    assert http.json()["issues"][0]["code"] == "natal_structure_inconsistent"
    assert http.json()["retryable"] is False
    assert not {
        "layers",
        "calculation_reading",
        "snapshot_text",
        "run_metadata",
        "result_delivery",
    }.intersection(http.json())


def test_a_current_rehashed_receipt_cannot_certify_a_false_sum():
    from fatebridge.services.replay_metadata import digest
    from tests.fengshui.test_fengshui_fixed_reading import executed, trusted

    payload = executed(
        request(
            interpretation={
                "current_period_number": 9,
                "period_evidence": "Independent current-period test input",
            }
        )
    )
    chart = payload["layers"]["xuankong_natal"]["candidates"][0]
    chart["structure"]["combination_of_ten"][0]["palace_sums"]["C"] = 999
    payload["run_metadata"]["business_output_sha256"] = digest(
        {key: value for key, value in payload.items() if key != "run_metadata"}
    )
    report = verify_fengshui_reading(payload, **trusted(payload))
    assert report["status"] == "rejected"
    assert {row["code"] for row in report["errors"]} >= {
        "numeric_structure_inconsistent"
    }
    assert report["derived_numeric_consistency_verified"] is False


@pytest.mark.parametrize("period", range(1, 10))
def test_all_432_numeric_branches_pass_without_mutating_the_structure(period):
    for index in range(24):
        for mode in ("lower", "replacement"):
            chart = xuankong._chart(period, (index, mode, "declared-numeric-branch"))
            before = deepcopy(chart)
            validate_natal_structure(chart)
            assert chart == before


def leaves(value, path=()):
    # These fields are provenance or scope metadata, not numeric assertions.
    if isinstance(value, dict):
        for key, child in value.items():
            if key not in {
                "source_ids",
                "rule_id",
                "scope",
                "interpretation_scope",
                "replacement_scope",
            }:
                yield from leaves(child, (*path, key))
    elif isinstance(value, list) and value:
        for index, child in enumerate(value):
            yield from leaves(child, (*path, index))
    else:
        yield path, value


@pytest.mark.parametrize("angle", [60, 66])
def test_every_selected_derived_value_is_checked_from_raw_stars(angle):
    original = xuankong.xuankong_natal(
        XuankongRequest.model_validate(request(7, angle))
    )["chart"]
    assert original is not None
    selected = list(leaves(original["structure"]))
    assert {p[0] for p, _ in selected} == {
        "reference_period_number",
        "period_scope",
        "distribution",
        "combination_of_ten",
        "classical_patterns",
    }
    assert {p[1] for p, _ in selected if p[0] == "classical_patterns"} == {
        "parental_triples",
        "ground_comparison",
        "volume_two_named_refrain",
        "opposite_star_comparison",
    }
    for path, value in selected:
        chart = deepcopy(original)
        target = chart["structure"]
        for part in path[:-1]:
            target = target[part]
        replacement = (
            not value
            if type(value) is bool
            else (
                value + 1000
                if type(value) is int
                else (
                    value + "!"
                    if isinstance(value, str)
                    else [999] if isinstance(value, list) else False
                )
            )
        )
        target[path[-1]] = replacement
        with pytest.raises(FengshuiCalculationError):
            validate_natal_structure(chart)


def test_current_structure_requires_the_opposite_branch():
    chart = xuankong.xuankong_natal(XuankongRequest.model_validate(request()))["chart"]
    del chart["structure"]["classical_patterns"]["opposite_star_comparison"]
    with pytest.raises(FengshuiCalculationError):
        validate_natal_structure(chart)
