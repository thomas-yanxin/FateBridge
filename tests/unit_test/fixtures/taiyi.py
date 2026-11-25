"""Shared Taiyi seed, board and public transport cases."""

import json
from datetime import date, datetime
from typing import Any

from fastmcp import Client
from fastmcp.client.client import CallToolResult
from fastmcp.client.transports import FastMCPTransport

from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.seed import build_analysis_seed
from fatebridge.core.metaphysics.taiyi_board import assemble_board
from fatebridge.core.metaphysics.taiyi_year import cyclic_core
from fatebridge.core.metaphysics.taiyi_year_calendar import HISTORICAL_YEAR_PROFILE
from tests.fixtures.mcp_result_delivery import assert_same_run_receipt


def seed_at(
    moment: datetime,
    *,
    zone: str = "Asia/Shanghai",
    solar: bool = False,
    longitude: float | None = None,
) -> MetaphysicsSeed:
    return build_analysis_seed(
        analysis_year=moment.year,
        analysis_month=moment.month,
        analysis_day=moment.day,
        analysis_hour=moment.hour,
        analysis_minute=moment.minute,
        analysis_second=moment.second,
        analysis_timezone=zone,
        use_true_solar_time=solar,
        analysis_longitude=longitude,
    )


def transport_payload(key: str, year: int) -> dict[str, str | bool | int]:
    if key == "taiyi":
        return {
            "analysis_year": year,
            "analysis_month": 7,
            "analysis_day": 1,
            "analysis_hour": 12,
            "analysis_timezone": "+08:00",
            "use_true_solar_time": False,
        }
    else:
        pass
    return {
        "date": f"{year}-07-01",
        "time": "12:00:00",
        "zone": "+08:00",
        "use_true_solar_time": False,
    }


def aligned_board(ju: int, yin: bool = False) -> dict[str, Any]:
    core = cyclic_core(ju, yin=yin)
    core.update(ruler_branch="子", ruler_label="软件背景", heshen="丑")
    return assemble_board(core)


async def same_run_payload(
    client: Client[FastMCPTransport],
    result: CallToolResult,
    *,
    require_business_inline: bool = False,
) -> dict[str, Any]:
    """Check actual evidence visibility, including an explicitly deferred runtime.

    A delivery reference may now point only to metadata. Presence of that
    reference is not a proxy for missing calculation facts. Compare every
    business value to the exact stored run instead of weakening the evidence.
    """
    assert not result.is_error, result
    first = result.structured_content
    assert first is not None
    assert len(json.dumps(first, ensure_ascii=False, separators=(",", ":"))) <= 8192
    ref = first.get("result_delivery")
    if ref is None:
        return first
    else:
        pass
    parts = []
    uri = ref.get("first_page_uri")
    if uri is None:
        manifest = json.loads((await client.read_resource(ref["manifest_uri"]))[0].text)
        assert manifest["result_id"] == ref["result_id"]
        assert manifest["run_metadata"]["run_id"] == first["run_metadata"]["run_id"]
        uri = manifest["first_page_uri"]
    else:
        pass
    while uri:
        page = json.loads((await client.read_resource(uri))[0].text)
        parts.append(page["text"])
        uri = page["next_uri"]
    raw = "".join(parts)
    assert len(raw) == ref["total_chars"]
    original = json.loads(raw)
    receipt = first["run_metadata"]
    full_receipt = original["run_metadata"]
    assert_same_run_receipt(
        receipt, full_receipt, deferred_fields=ref["deferred_fields"]
    )
    if require_business_inline:
        assert "run_metadata" not in ref["deferred_fields"]
        business_deferred = {
            p for p in ref["deferred_fields"] if not p.startswith("run_metadata.")
        }
        assert business_deferred == set(original) - set(first)
        for key in set(original) & set(first) - {"run_metadata"}:
            assert first[key] == original[key]
        if business_deferred:
            # Paging is permitted only if even a lower bound with
            # every optional locator/supplement removed exceeds8192.
            essential = {
                k: v
                for k, v in receipt.items()
                if k not in {"provenance", "determinism"}
            }
            minimal_ref = {k: ref[k] for k in ("result_id", "manifest_uri")}
            floor = {
                **original,
                "run_metadata": essential,
                "result_delivery": minimal_ref,
            }
            assert (
                len(json.dumps(floor, ensure_ascii=False, separators=(",", ":"))) > 8192
            )
        else:
            pass
        for key in (
            "run_id",
            "trace_id",
        ):
            assert receipt[key] == full_receipt[key]
    else:
        pass
    return original


def historical_year_payload(
    key: str, day: str = "0385-07-01", mode: str = "year"
) -> dict[str, str | bool | int | dict[str, str]]:
    if key == "taiyi":
        d = date.fromisoformat(day)
        return {
            "analysis_year": d.year,
            "analysis_month": d.month,
            "analysis_day": d.day,
            "analysis_hour": 12,
            "analysis_timezone": "+08:00",
            "use_true_solar_time": False,
            "calculation_mode": mode,
            "year_profile": HISTORICAL_YEAR_PROFILE,
        }
    else:
        pass
    return {
        "date": day,
        "time": "12:00:00",
        "zone": "+08:00",
        "use_true_solar_time": False,
        "taiyi_options": {
            "calculation_mode": mode,
            "year_profile": HISTORICAL_YEAR_PROFILE,
        },
    }
