"""Tests for explicit unknown birth hour (birth_time_unknown=True) 3-pillar mode."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from fatebridge.application.batch import BatchRequest, execute_batch
from fatebridge.application.execution import execute_with_receipt
from fatebridge.application.response_delivery import deliver_response
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.requests.bazi import BaziBirthRequest, BaziOverviewRequest
from fatebridge.core.requests.sanshi import LiuRengRunyearRequest
from fatebridge.core.requests.timing import TimingAnalysisRequest
from fatebridge.services.tool_catalog import get_specs


def test_unknown_birth_hour_requires_explicit_opt_in_and_rejects_conflicts() -> None:
    with pytest.raises(ValidationError) as missing_err:
        BaziOverviewRequest(
            birth_year=2003,
            birth_month=2,
            birth_day=6,
            gender="male",
        )
    assert missing_err.value.errors()[0]["type"] == "missing_birth_hour"

    with pytest.raises(ValidationError) as conflict_err:
        BaziBirthRequest(
            birth_year=2003,
            birth_month=2,
            birth_day=6,
            birth_hour=10,
            birth_time_unknown=True,
            gender="male",
        )
    assert conflict_err.value.errors()[0]["type"] == "conflicting_unknown_birth_time"

    with pytest.raises(ValidationError) as minute_conflict:
        TimingAnalysisRequest(
            birth_year=2003,
            birth_month=2,
            birth_day=6,
            birth_minute=30,
            birth_time_unknown=True,
            gender="male",
        )
    assert minute_conflict.value.errors()[0]["type"] == "conflicting_unknown_birth_time"


def test_unknown_birth_hour_three_pillars_bazi_and_liuren_runyear() -> None:
    specs = {
        spec.name: spec
        for spec in get_specs(
            [
                "bazi_overview",
                "bazi_birth_chart",
                "bazi_timing",
                "liuren_yearly_timing",
            ]
        )
    }
    opts = ExecutionOptions(as_of="2026-04-06T09:30:00+08:00")
    base = {
        "name": "案例对象",
        "gender": "male",
        "birth_year": 2003,
        "birth_month": 2,
        "birth_day": 6,
        "birth_time_unknown": True,
        "birth_place": "杭州西湖区",
    }

    overview = deliver_response(
        execute_with_receipt(
            specs["bazi_overview"], BaziOverviewRequest(**base), options=opts
        ),
        spec=specs["bazi_overview"],
    )
    assert overview["four_pillars"]["hour"] is None
    assert set(overview["ten_gods"]) == {"year", "month", "day"}
    assert overview["coverage"]["mode"] == "three_pillars_hour_unknown"
    assert overview["coverage"]["known_pillars"] == ["year", "month", "day"]
    assert "hour_pillar" in overview["coverage"]["omitted_components"]
    assert len(json.dumps(overview, ensure_ascii=False)) <= 10240

    birth_chart = deliver_response(
        execute_with_receipt(
            specs["bazi_birth_chart"], BaziBirthRequest(**base), options=opts
        ),
        spec=specs["bazi_birth_chart"],
    )
    assert birth_chart["bazi_birth"]["four_pillars"]["hour"] is None
    assert set(birth_chart["bazi_birth"]["three_origins"]) == {"taiyuan"}
    assert birth_chart["coverage"]["mode"] == "three_pillars_hour_unknown"
    assert len(json.dumps(birth_chart, ensure_ascii=False)) <= 10240

    timing = deliver_response(
        execute_with_receipt(
            specs["bazi_timing"],
            TimingAnalysisRequest(
                **base, analysis_year=2026, analysis_month=4, analysis_day=6
            ),
            options=opts,
        ),
        spec=specs["bazi_timing"],
    )
    assert timing["four_pillars"]["hour"] is None
    assert timing["coverage"]["mode"] == "three_pillars_hour_unknown"
    assert len(json.dumps(timing, ensure_ascii=False)) <= 10240

    runyear = deliver_response(
        execute_with_receipt(
            specs["liuren_yearly_timing"],
            LiuRengRunyearRequest(
                **base,
                analysis_year=2026,
                analysis_month=4,
                analysis_day=6,
                analysis_hour=9,
                analysis_place="杭州西湖区",
            ),
            options=opts,
        ),
        spec=specs["liuren_yearly_timing"],
    )
    assert runyear["runyear"]["birth_lunar_year"] == 2003
    assert runyear["coverage"]["mode"] == "date_only_hour_unknown"


def test_unknown_birth_hour_lichun_solar_term_boundary_warning() -> None:
    specs = {spec.name: spec for spec in get_specs(["bazi_overview"])}
    req = BaziOverviewRequest(
        gender="male",
        birth_year=2003,
        birth_month=2,
        birth_day=4,
        birth_time_unknown=True,
        birth_place="杭州西湖区",
    )
    res = execute_with_receipt(specs["bazi_overview"], req, options=ExecutionOptions())
    warnings = res["coverage"]["boundary_warnings"]
    assert any("立春" in w for w in warnings), warnings


def test_batch_unknown_birth_hour_end_to_end() -> None:
    specs = {
        spec.name: spec
        for spec in get_specs(
            [
                "bazi_overview",
                "bazi_birth_chart",
                "bazi_timing",
                "liuren_yearly_timing",
                "qimen",
                "liuren_chart",
                "jinkou",
                "meihua_time_cast",
                "horary_chart",
            ]
        )
    }
    req = BatchRequest.model_validate(
        {
            "subjects": {
                "client": {
                    "gender": "male",
                    "birth_date": "2003-02-06",
                    "birth_time_unknown": True,
                    "birth_place": "杭州西湖区",
                }
            },
            "context": {
                "analysis_datetime": "2026-04-06T09:30:00+08:00",
                "place": "杭州西湖区",
            },
            "calls": [
                {"id": "bo", "tool": "bazi_overview", "subject": "client"},
                {"id": "bc", "tool": "bazi_birth_chart", "subject": "client"},
                {"id": "bt", "tool": "bazi_timing", "subject": "client"},
                {"id": "ly", "tool": "liuren_yearly_timing", "subject": "client"},
                {"id": "jk", "tool": "jinkou", "subject": "client"},
                {"id": "lr", "tool": "liuren_chart", "subject": "client"},
            ],
            "as_of": "2026-04-06T09:30:00+08:00",
        }
    )
    res = execute_batch(specs, req)
    assert res["status"] == "ok", res
    assert res["succeeded"] == 6
    by_id = {item["id"]: item["result"] for item in res["results"]}
    assert by_id["bo"]["four_pillars"]["hour"] is None
    assert by_id["jk"]["jinkou"]["birth_year_derivation"]["birth_year_ganzhi"] == "癸未"
    assert by_id["lr"]["liuren"]["birth_year_derivation"]["natal_branch"] == "未"
