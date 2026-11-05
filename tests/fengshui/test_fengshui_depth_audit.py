"""Independent source discrepancies, boundary failures and interpretation facts."""

import asyncio
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree

import pytest

from fatebridge.cli import run
from fatebridge.core import almanac
from fatebridge.core.fengshui import calendar
from fatebridge.core.fengshui.models import HousePeriod
from fatebridge.core.fengshui.xuankong import period_context
from fatebridge.services.fengshui import (
    calculate_annual_stars,
    calculate_xuankong_natal,
)
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from fatebridge.validation.fengshui import audit_classical_reference
from tests.fengshui.test_fengshui_surfaces import (
    mcp_call,
    rest_client,
    without_transport,
)

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "data/fengshui_classical_v1/reference.json"
    ).read_text()
)
FACSIMILE = json.loads(
    (
        Path(__file__).parents[1] / "data/fengshui_classical_v1/facsimile-checks.json"
    ).read_text()
)


def natal(period=7, angle=0):
    return {
        "house": {"facing_degrees": angle, "north_reference": "magnetic"},
        "period": {
            "basis": "expert_confirmed",
            "period_number": period,
            "evidence": "Source-based numeric example; no real house",
        },
    }


def test_literal_sources_keep_all_280_comparisons_and_three_disputes():
    result = audit_classical_reference(REFERENCE, FACSIMILE)
    assert result["counts"] == {
        "bazhai": {"checked": 64, "matched": 64},
        "xuankong": {"checked": 216, "matched": 213},
    }
    assert {
        (r["period"], r["sitting_mountain"], r["facing_mountain"])
        for r in result["disagreements"]
    } == {(4, "卯", "酉"), (1, "酉", "卯"), (6, "巽", "乾")}
    # A functioning audit test is not a passing classical acceptance gate.
    assert not result["numeric_clause_acceptance_passed"]
    assert not result["whole_book_conformity_established"]
    assert not result["authority_certified"]
    assert result["real_world_prediction"] == "not_tested"
    assert result["unresolved_disagreement_count"] == 0
    assert len(result["facsimile_spot_checks"]) == 3
    assert all(c["engine_matches_facsimile"] for c in result["facsimile_spot_checks"])


def test_facsimile_page_pixels_and_unresolved_source_status_remain_verifiable():
    folder = Path(__file__).parents[1] / "data/fengshui_classical_v1"
    for item in FACSIMILE["images"]:
        assert (
            hashlib.sha256((folder / item["file"]).read_bytes()).hexdigest()
            == item["sha256"]
        )
    assert audit_classical_reference(REFERENCE)["unresolved_disagreement_count"] == 3
    changed = deepcopy(FACSIMILE)
    changed["cases"][0]["mountain_flight"] = "reverse"
    assert (
        audit_classical_reference(REFERENCE, changed)["unresolved_disagreement_count"]
        == 1
    )


@pytest.mark.parametrize("part", ["shen_cases", "you_nian_verses"])
def test_discarding_source_rows_cannot_manufacture_acceptance(part):
    changed = deepcopy(REFERENCE)
    changed[part].pop()
    with pytest.raises(ValueError):
        audit_classical_reference(changed)


def test_new_source_disagreements_are_reported_without_allowlist():
    changed = deepcopy(REFERENCE)
    changed["shen_cases"][0]["mountain_seed"] = 9
    result = audit_classical_reference(changed)
    assert len(result["disagreements"]) == 4
    assert result["counts"]["xuankong"]["matched"] == 212


@pytest.mark.parametrize(
    "period,angle,label,mountain_at,facing_at",
    [
        (7, 0, "双星到向", "N", "N"),
        (7, 180, "双星到坐", "N", "N"),
        (6, 270, "上山下水", "W", "E"),
        (3, 270, "到山到向", "E", "W"),
    ],
)
def test_source_named_structures_are_historical_numeric_facts(
    period, angle, label, mountain_at, facing_at
):
    result = calculate_xuankong_natal(**natal(period, angle))
    chart = result["layers"]["xuankong_natal"]["chart"]
    structure = chart["structure"]
    assert structure["reference_period_number"] == period
    assert structure["period_scope"] == "historical_natal_period_not_current_timeliness"
    assert structure["distribution"]["traditional_label"] == label
    assert structure["distribution"]["mountain_period_star_direction"] == mountain_at
    assert structure["distribution"]["facing_period_star_direction"] == facing_at
    assert label in result["snapshot_text"]
    assert "不代表当前旺衰、外局匹配或现实吉凶" in result["snapshot_text"]


def test_source_seven_period_wu_zi_full_chart_combination_of_ten():
    chart = calculate_xuankong_natal(**natal())["layers"]["xuankong_natal"]["chart"]
    pairs = chart["structure"]["combination_of_ten"]
    assert len(pairs) == 3
    hits = [
        (p["left_role"], p["right_role"]) for p in pairs if p["all_nine_sum_to_ten"]
    ]
    assert hits == [("period", "facing")]
    assert all(len(p["palace_sums"]) == 9 for p in pairs)
    matched = next(p for p in pairs if p["all_nine_sum_to_ten"])
    assert set(matched["palace_sums"].values()) == {10}


def test_current_evaluation_period_never_rewrites_historical_structure():
    request = natal()
    baseline = calculate_xuankong_natal(**request)["layers"]["xuankong_natal"]["chart"]
    for period in (8, 9, 1):
        result = calculate_xuankong_natal(
            **request,
            interpretation={
                "current_period_number": period,
                "period_evidence": "Explicit current-period scenario",
            },
        )
        assert result["layers"]["xuankong_natal"]["chart"] == baseline


@pytest.mark.parametrize("days", [-30, 30, 150])
@pytest.mark.parametrize("zone", ["Asia/Shanghai", "UTC", "America/New_York"])
def test_missing_crossing_rejects_even_events_distant_from_the_boundary(
    monkeypatch, days, zone
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    almanac.get_solar_terms_for_year.cache_clear()
    boundary = calendar.lichun(2024, zone)
    monkeypatch.setattr(almanac, "_solar_term_utc_via_swe", lambda *args: None)
    almanac.get_solar_terms_for_year.cache_clear()
    try:
        with pytest.raises(EphemerisSourceError, match="no linear approximation"):
            period_context(
                HousePeriod(
                    basis="first_occupancy",
                    event_at=boundary + timedelta(days=days),
                    timezone_name=zone,
                    evidence="Known event; actual crossing is unavailable",
                )
            )
    finally:
        almanac.get_solar_terms_for_year.cache_clear()


def test_unavailable_end_boundary_rejects_the_whole_validity_interval(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    original = almanac._solar_term_utc_via_swe

    def solve(year, *args):
        return None if year == 2027 else original(year, *args)

    monkeypatch.setattr(almanac, "_solar_term_utc_via_swe", solve)
    almanac.get_solar_terms_for_year.cache_clear()
    try:
        with pytest.raises(EphemerisSourceError, match="no linear approximation"):
            calculate_annual_stars(effective_year=2026)
    finally:
        almanac.get_solar_terms_for_year.cache_clear()


@pytest.mark.parametrize(
    "zone", ["Asia/Shanghai", "UTC", "America/New_York", "Pacific/Auckland"]
)
def test_fengshui_year_period_and_birth_follow_independent_published_instants(zone):
    from fatebridge.services.fengshui import calculate_minggua

    existing = json.loads(
        (
            Path(__file__).parents[1] / "fixtures/calendar_hko_v1/reference.json"
        ).read_text()
    )
    folder = Path(__file__).parents[1] / "data/fengshui_calendar_v1"
    source = json.loads((folder / "reference.json").read_text())
    raw = (folder / source["file"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == source["sha256"]
    rows = ElementTree.fromstring(raw).findall("Data")
    assert len(rows) == 24
    lichun = rows[2]
    hko_2024 = f"2024-{lichun.findtext('M')}-{lichun.findtext('D')}T{lichun.findtext('hm')}:00+08:00"
    cases = [{"year": 2024, "at": hko_2024}] + [
        c for c in existing["cases"] if c["term"] == "立春"
    ]
    for case in cases:
        instant = datetime.fromisoformat(case["at"])
        computed = calendar.lichun(case["year"], zone)
        assert abs((computed - instant).total_seconds()) <= 60
        for offset in (-2, 2):
            at = instant + timedelta(minutes=offset)
            year = case["year"] - int(offset < 0)
            annual = calculate_annual_stars(query_at=at, timezone_name=zone)["layers"][
                "annual_stars"
            ]
            birth = calculate_minggua(
                birth_at=at, gender_convention="male", timezone_name=zone
            )["layers"]["minggua"]
            assert (
                annual["effective_year"]
                == birth["time_context"]["effective_year"]
                == year
            )
            assert (
                annual["center_star_number"]
                == {2023: 4, 2024: 3, 2025: 2, 2026: 1, 2027: 9, 2028: 8}[year]
            )
            p = period_context(
                HousePeriod(
                    basis="first_occupancy",
                    event_at=at,
                    timezone_name=zone,
                    evidence="Independent HKO published minute with two-minute separation",
                )
            )
            assert p["number"] == (8 if year == 2023 else 9)


def test_new_structure_and_timing_match_all_three_transports(
    monkeypatch, tmp_path, capsys
):
    request = natal()
    request["period"] = {
        "basis": "first_occupancy",
        "event_at": "2024-02-05T12:00:00+08:00",
        "evidence": "Confirmed historical event",
    }
    http = rest_client(monkeypatch).post("/api/fengshui/xuankong_natal", json=request)
    protocol = asyncio.run(mcp_call("xuankong_natal", request))
    request_file = tmp_path / "natal.json"
    request_file.write_text(json.dumps(request))
    assert run(["fengshui_xuankong_natal", "--request-file", str(request_file)]) == 0
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 200 and not protocol.is_error
    assert (
        without_transport(http.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    result = http.json()
    metadata = result["run_metadata"]
    path = "layers.xuankong_natal.chart.structure.distribution.traditional_label"
    claim = CalculationClaim(
        path=path,
        value=result["layers"]["xuankong_natal"]["chart"]["structure"]["distribution"][
            "traditional_label"
        ],
        run_id=metadata["run_id"],
        business_output_sha256=metadata["business_output_sha256"],
    )
    assert (
        verify_calculation_claims(result, [claim])["status"]
        == "verified_structured_facts"
    )
    wrong = claim.model_copy(update={"value": "invented guaranteed prosperity"})
    assert verify_calculation_claims(result, [wrong])["status"] == "rejected"
