"""A weaker numerical model must not select a false unique boundary branch."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from fatebridge.core.fengshui.bazhai import minggua
from fatebridge.core.fengshui.calendar import lichun_resolution, solar_term_resolution
from fatebridge.core.fengshui.models import HousePeriod, MingguaRequest
from fatebridge.core.fengshui.xuankong import period_context
from fatebridge.core.moshier_solar import MODEL_ID as COMPLETE_MOSHIER_SOLAR_MODEL
from fatebridge.services.fengshui import calculate_annual_stars, calculate_monthly_stars

FOLDER = Path(__file__).parents[1] / "data/fengshui_monthly_v1"
REGRESSION = json.loads((FOLDER / "moshier-boundary-regression.json").read_text())
TERMS = [
    "小寒",
    "立春",
    "惊蛰",
    "清明",
    "立夏",
    "芒种",
    "小暑",
    "立秋",
    "白露",
    "寒露",
    "立冬",
    "大雪",
]


@pytest.fixture
def actual_moshier(monkeypatch, tmp_path):
    # Request the native control explicitly: auto may select another model
    # when files are absent. Never relabel that result as Moshier.
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    assert (
        solar_term_resolution(2026, "立春", "UTC")["ephemeris_model"]
        == COMPLETE_MOSHIER_SOLAR_MODEL
    )


@pytest.mark.parametrize("term", TERMS)
def test_every_jie_keeps_both_candidates_inside_the_guard_and_computes_beyond_it(
    actual_moshier, term
):
    resolution = solar_term_resolution(2026, term, "UTC")
    root = datetime.fromisoformat(resolution["moment"])
    for seconds in [-5, -1, 0, 1, 5]:
        result = calculate_monthly_stars(
            query_at=root + timedelta(seconds=seconds), timezone_name="UTC"
        )["layers"]["monthly_stars"]
        assert result["status"] == "partial" and not result["palaces"]
        time = result["time_context"]
        assert len(time["candidate_months"]) == 2
        assert time["solar_month_number"] is None
        assert all(
            r["uncertainty_reason"]
            == "complete_moshier_solar_model_guard_not_accuracy_certification"
            for r in time["uncertain_boundary_resolutions"]
        )
        assert time["precision_policy"]["numeric_acceptance_gate_seconds"] == 1.0
    for seconds in [-6, 6]:
        result = calculate_monthly_stars(
            query_at=root + timedelta(seconds=seconds), timezone_name="UTC"
        )["layers"]["monthly_stars"]
        assert result["status"] == "complete" and result["palaces"]


def test_reference_counterexample_is_preserved_without_a_false_unique_month(
    actual_moshier,
):
    result = calculate_monthly_stars(**REGRESSION["input"])["layers"]["monthly_stars"]
    expected = REGRESSION["expected_under_frozen_reference_clock_policy"]
    assert result["status"] == "partial" and not result["palaces"]
    assert any(
        all(c[k] == v for k, v in expected.items())
        for c in result["time_context"]["candidate_months"]
    )
    assert result["time_context"]["effective_solar_year"] == 2128
    assert result["time_context"]["solar_month_number"] is None


def test_year_star_minggua_and_twenty_year_changeover_share_the_same_guard(
    actual_moshier,
):
    root = datetime.fromisoformat(lichun_resolution(2024, "UTC")["moment"])
    annual = calculate_annual_stars(query_at=root, timezone_name="UTC")["layers"][
        "annual_stars"
    ]
    assert annual["status"] == "partial" and annual["palaces"] == {}
    assert annual["time_context"]["candidate_effective_years"] == [2023, 2024]
    personal = minggua(
        MingguaRequest(birth_at=root, timezone_name="UTC", gender_convention="male")
    )
    assert personal["status"] == "partial" and personal["candidates"] == []
    period = period_context(
        HousePeriod(
            basis="construction_completion",
            event_at=root,
            timezone_name="UTC",
            evidence="synthetic boundary event",
        )
    )
    assert period["number"] is None and period["candidate_period_numbers"] == [8, 9]
    assert (
        period["confirmation_reason"]
        == "complete_moshier_solar_model_precision_guard_in_period_changeover_year"
    )
    other = datetime.fromisoformat(lichun_resolution(2025, "UTC")["moment"])
    same = period_context(
        HousePeriod(
            basis="construction_completion",
            event_at=other,
            timezone_name="UTC",
            evidence="synthetic unchanged period",
        )
    )
    assert same["number"] == 9 and same["resolution_status"] == "resolved"


def test_explicit_confirmations_are_not_overruled_by_a_weaker_clock(actual_moshier):
    annual = calculate_annual_stars(effective_year=2024)["layers"]["annual_stars"]
    assert annual["status"] == "complete" and annual["effective_year"] == 2024
    personal = minggua(
        MingguaRequest(effective_birth_year=2024, gender_convention="male")
    )
    assert personal["status"] == "complete" and personal["candidates"]
    period = period_context(
        HousePeriod(
            basis="construction_completion",
            effective_event_year=2024,
            evidence="synthetic confirmed effective year",
        )
    )
    assert period["number"] == 9 and period["resolution_status"] == "resolved"


def test_date_only_birth_includes_an_adjacent_date_crossed_by_the_guard(monkeypatch):
    import fatebridge.core.fengshui.bazhai as module

    # Synthetic midnight geometry isolates the date-only logic; this is not a
    # claim that the real 2024 Lichun occurred at the fixture clock.
    monkeypatch.setattr(
        module,
        "lichun_resolution",
        lambda *a, **k: {
            "moment": "2024-02-04T00:00:02+08:00",
            "approximate": False,
            "provider": "swisseph",
            "ephemeris_model": "moshier",
        },
    )
    held = minggua(MingguaRequest(birth_date="2024-02-03", gender_convention="male"))
    assert held["status"] == "partial" and not held["candidates"]
    assert any("boundary_precision" in p for p in held["missing_inputs"])
    assert held["time_context"]["boundary_precision_policy"][
        "boundary_possible_civil_dates"
    ] == ["2024-02-03", "2024-02-04"]
    assert (
        minggua(MingguaRequest(birth_date="2024-02-02", gender_convention="male"))[
            "status"
        ]
        == "complete"
    )
    assert (
        minggua(MingguaRequest(birth_date="2024-02-05", gender_convention="male"))[
            "status"
        ]
        == "complete"
    )
