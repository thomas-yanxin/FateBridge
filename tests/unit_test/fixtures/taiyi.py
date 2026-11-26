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
        "timezone": "+08:00",
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
    """Check actual evidence visibility on inline MCP calculation payloads."""
    assert not result.is_error, result
    first = result.structured_content
    assert first is not None
    assert "result_delivery" not in first
    return first


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
        "timezone": "+08:00",
        "use_true_solar_time": False,
        "taiyi_options": {
            "calculation_mode": mode,
            "year_profile": HISTORICAL_YEAR_PROFILE,
        },
    }
