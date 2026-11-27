"""Tests for deterministic birth_date derivation in jinkou and liuren_chart."""

from __future__ import annotations

from datetime import date

import pytest

from fatebridge.core.metaphysics.ren_calendar import derive_birth_year_fate_from_date
from fatebridge.core.requests.sanshi import JinkouAnalysisRequest, LiuRengGodsRequest
from fatebridge.services.sanshi import calculate_jinkou_analysis, calculate_liureng_gods


def test_derive_birth_year_fate_agreement_and_cny_vs_lichun_disagreement() -> None:
    agreed = derive_birth_year_fate_from_date("2003-02-06", date(2026, 4, 6))
    assert agreed["birth_year_ganzhi"] == "癸未"
    assert agreed["natal_branch"] == "未"
    assert agreed["year_fate_age"] == 24
    assert agreed["boundary_disagreement"] is False
    assert "alternate_boundary" not in agreed

    # 2003-02-02 is after 2003-02-01 Chinese New Year (癸未) but before 2003-02-04 Lichun (壬午)
    disagreed_lny = derive_birth_year_fate_from_date(
        "2003-02-02", date(2026, 4, 6), boundary="lunar_new_year"
    )
    assert disagreed_lny["birth_year_ganzhi"] == "癸未"
    assert disagreed_lny["natal_branch"] == "未"
    assert disagreed_lny["year_fate_age"] == 24
    assert disagreed_lny["boundary_disagreement"] is True
    assert disagreed_lny["alternate_boundary"]["birth_year_ganzhi"] == "壬午"
    assert disagreed_lny["alternate_boundary"]["boundary"] == "lichun"

    disagreed_lc = derive_birth_year_fate_from_date(
        "2003-02-02", date(2026, 4, 6), boundary="lichun"
    )
    assert disagreed_lc["birth_year_ganzhi"] == "壬午"
    assert disagreed_lc["natal_branch"] == "午"
    assert disagreed_lc["year_fate_age"] == 25
    assert disagreed_lc["boundary_disagreement"] is True


def test_jinkou_and_liuren_chart_birth_date_integration() -> None:
    jk_req = JinkouAnalysisRequest(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=6,
        analysis_hour=9,
        analysis_place="杭州西湖区",
        gender="男",
        birth_date="2003-02-06",
    )
    jk_res = calculate_jinkou_analysis(**jk_req.service_inputs())
    assert "error" not in jk_res
    jk = jk_res["jinkou"]
    assert jk["birth_year_derivation"]["birth_year_ganzhi"] == "癸未"
    assert jk["natal_course"]["natal_branch"] == "未"
    assert jk["natal_course"]["birth_year_ganzhi"] == "癸未"
    assert jk["year_fate"]["status"] == "calculated"
    assert jk["year_fate"]["age_ordinal"] == 24

    # Explicit conflicting birth_year_ganzhi must error cleanly
    conflict_res = calculate_jinkou_analysis(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=6,
        analysis_hour=9,
        analysis_place="杭州西湖区",
        gender="男",
        birth_date="2003-02-06",
        birth_year_ganzhi="甲子",
    )
    assert "error" in conflict_res

    lr_req = LiuRengGodsRequest(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=6,
        analysis_hour=9,
        analysis_place="杭州西湖区",
        birth_date="2003-02-02",
    )
    lr_res = calculate_liureng_gods(**lr_req.service_inputs())
    assert "error" not in lr_res
    assert lr_res["liuren"]["birth_year_derivation"]["boundary_disagreement"] is True
