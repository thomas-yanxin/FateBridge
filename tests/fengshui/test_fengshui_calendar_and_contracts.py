"""Calendar boundary precision guards, numeric input contracts, and AssessRequest UX."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from typing import Annotated

import pytest
from pydantic import TypeAdapter, ValidationError

from fatebridge.core.analytic_solar import MODEL_ID as ANALYTIC_MODEL_ID
from fatebridge.core.fengshui import models
from fatebridge.core.fengshui.calendar import (
    lichun_resolution,
    solar_month_context,
    year_context,
)
from fatebridge.core.fengshui.models import (
    AnnualRequest,
    AssessRequest,
    BazhaiRequest,
    CityGateRequest,
    EnvironmentFeature,
    GeomagneticReference,
    House,
    HousePeriod,
    JinsuoRequest,
    MingguaRequest,
    MonthlyRequest,
    Placement,
    XuankongRequest,
)
from fatebridge.services.fengshui import (
    calculate_fengshui_assessment,
    calculate_xuankong_natal,
)


@pytest.mark.parametrize(
    "model_name,field_name",
    [
        ("GeomagneticReference", "latitude"),
        ("GeomagneticReference", "longitude"),
        ("GeomagneticReference", "height_km_wgs84"),
        ("GeomagneticReference", "model_date"),
        ("GeomagneticReference", "decimal_year"),
        ("AnnualRequest", "effective_year"),
        ("AnnualRequest", "query_at"),
        ("AssessRequest", "effective_year"),
        ("AssessRequest", "query_at"),
        ("AssessRequest", "built_year"),
        ("AssessRequest", "period_number"),
        ("DirectionsRequest", "bearing_degrees"),
        ("House", "facing_degrees"),
        ("House", "bearing_uncertainty_degrees"),
        ("HousePeriod", "period_number"),
        ("HousePeriod", "event_year"),
        ("MingguaRequest", "birth_date"),
        ("MingguaRequest", "birth_year"),
        ("MingguaRequest", "birth_at"),
        ("MonthlyRequest", "query_at"),
        ("MonthlyRequest", "effective_solar_year"),
        ("MonthlyRequest", "solar_month_number"),
    ],
)
@pytest.mark.parametrize("invalid", [True, False, "2026", float("nan"), float("inf")])
def test_strict_numeric_and_calendar_guards(
    model_name: str, field_name: str, invalid
) -> None:
    cls = getattr(models, model_name)
    info = cls.model_fields[field_name]
    adapter = TypeAdapter(Annotated[(info.annotation, *info.metadata)])
    with pytest.raises(ValidationError):
        adapter.validate_python(invalid)


def test_exact_fractions_and_nonexistent_dst_handling() -> None:
    info = models.House.model_fields["facing_degrees"]
    adapter = TypeAdapter(Annotated[(info.annotation, *info.metadata)])
    assert adapter.validate_python(Decimal("22.5")) == 22.5
    assert adapter.validate_python(Fraction(45, 2)) == 22.5

    p_info = models.HousePeriod.model_fields["period_number"]
    p_adapter = TypeAdapter(Annotated[(p_info.annotation, *p_info.metadata)])
    assert p_adapter.validate_python(8.0) == 8
    with pytest.raises(ValidationError):
        p_adapter.validate_python(8.5)

    from zoneinfo import ZoneInfo

    with pytest.raises(ValidationError):
        MingguaRequest(
            birth_at=datetime(2026, 3, 8, 2, 30, tzinfo=ZoneInfo("America/New_York")),
            timezone_name="America/New_York",
        )


def test_analytic_5s_boundary_guard_for_year_and_month(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    res = lichun_resolution(2024, "UTC")
    assert res["ephemeris_model"] == ANALYTIC_MODEL_ID
    root = datetime.fromisoformat(res["moment"])

    y_ctx = year_context(None, root, "UTC")
    assert y_ctx["effective_year_status"] == "requires_confirmation"
    assert y_ctx["candidate_effective_years"] == [2023, 2024]
    assert y_ctx["boundary_resolution"]["operational_guard_seconds"] == 5.0

    m_ctx = solar_month_context(None, None, root + timedelta(seconds=1), "UTC")
    assert m_ctx["month_status"] == "requires_confirmation"
    assert [
        (c["effective_solar_year"], c["solar_month_number"])
        for c in m_ctx["candidate_months"]
    ] == [
        (2023, 12),
        (2024, 1),
    ]


def test_assess_allows_effective_year_and_query_at_together_and_4_layer_overlay() -> (
    None
):
    req = AssessRequest.model_validate(
        {
            "methods": ["xuankong_natal", "annual_stars", "monthly_stars", "bazhai"],
            "effective_year": 2026,
            "query_at": "2026-02-04T12:00:00+08:00",
            "house": {"facing_degrees": 150.0, "north_reference": "magnetic"},
            "xuankong": {
                "period": {
                    "basis": "expert_confirmed",
                    "period_number": 7,
                    "evidence": "Period 7 oracle",
                }
            },
            "occupants": [
                {
                    "subject_id": "a",
                    "birth_year": 1990,
                    "gender": "male",
                }
            ],
            "placements": [
                {"object_id": "door", "purpose": "door", "location_direction": "SE"}
            ],
            "analyze_layout": True,
        }
    )
    out = calculate_fengshui_assessment(req)
    assert out["status"] == "complete"
    assert out["layers"]["annual_stars"]["effective_year"] == 2026
    assert "daily_stars" in out["layers"]["monthly_stars"]
    assert "hourly_stars" in out["layers"]["monthly_stars"]
    overlay = out["palace_overlay"]
    assert set(overlay) == {"C", "NW", "W", "NE", "S", "N", "SW", "E", "SE"}
    assert set(overlay["C"]) >= {
        "natal_period_star",
        "natal_mountain_star",
        "natal_facing_star",
        "annual_star",
        "monthly_star",
        "daily_star",
        "hourly_star",
    }
    assert "layout_analysis" in out
    assert "annual_remedies" not in out["layout_analysis"]


def test_ergonomic_defaults_auto_ids_and_propagation() -> None:
    # Finite float accepts integer 0 and defaults height_km_wgs84=0.0, evidence=None
    geo = GeomagneticReference(latitude=0, longitude=0, decimal_year=2026)
    assert geo.height_km_wgs84 == 0.0 and geo.evidence is None

    # House defaults north_reference='magnetic' and supports facing_mountain when facing_degrees omitted
    h_deg = House(facing_degrees=180)
    assert h_deg.north_reference == "magnetic"
    assert House(facing_degrees=180, north_reference="true").north_reference == "true"
    h_mtn = House(facing_mountain="午")
    assert h_mtn.facing_mountain == "午"
    with pytest.raises(ValidationError):
        House(facing_degrees=180, facing_mountain="午")
    with pytest.raises(ValidationError):
        House(facing_mountain="午", sitting_trigram="离")

    # Placement auto-assigns object_id in BazhaiRequest and auto-populates facing_role
    p = Placement(purpose="bed", facing_direction="E")
    assert p.facing_role == "headboard"
    with pytest.raises(ValidationError):
        Placement(purpose="bed", facing_direction="E", facing_role="fire_mouth")
    with pytest.raises(ValidationError):
        Placement(purpose="bed", location_direction="N", facing_role="headboard")

    bz = BazhaiRequest.model_validate(
        {
            "house": {"facing_mountain": "午"},
            "occupants": [{"birth_year": 1990, "gender": "male"}],
            "placements": [{"purpose": "bed", "location_direction": "N", "facing_direction": "E"}],
        }
    )
    assert bz.occupants[0].subject_id == "occupant_1"
    assert bz.placements[0].object_id == "placement_1"

    # EnvironmentFeature defaults and JinsuoRequest auto-IDs
    js = JinsuoRequest.model_validate(
        {"features": [{"direction": "N", "classification": "sand"}]}
    )
    assert js.features[0].object_id == "feature_1"
    assert js.features[0].classification_basis == "user_confirmed"
    assert js.features[0].evidence is None

    # HousePeriod defaults
    hp1 = HousePeriod(period_number=8)
    assert hp1.basis == "expert_confirmed" and hp1.evidence is None
    hp2 = HousePeriod(event_year=2004)
    assert hp2.basis == "construction_completion"
    hp3 = HousePeriod(basis="confirmed_major_renovation", event_year=2024)
    assert hp3.qualifies_for_period_reset is True

    # XuankongRequest & AssessRequest propagation + auto-methods + analyze_layout
    xk = XuankongRequest.model_validate(
        {
            "house": {"facing_degrees": 180},
            "period": {"period_number": 8},
            "current_period_number": 9,
            "city_gate": {},
            "interpretation": {
                "external_forms": [{"direction": "S", "water_present": True}]
            },
        }
    )
    assert xk.city_gate is not None and xk.city_gate.reference_period_number == 9
    assert (
        xk.interpretation is not None
        and xk.interpretation.current_period_number == 9
        and xk.interpretation.external_forms[0].observation_basis == "user_confirmed"
    )
    xk_out = calculate_xuankong_natal(xk)
    assert xk_out["layers"]["xuankong_natal"]["city_gate_analysis"]["status"] == "complete"

    assess = AssessRequest.model_validate(
        {
            "house": {"facing_degrees": 255},
            "built_year": 2004,
            "query_at": "2026-04-06T12:00:00+08:00",
            "placements": [{"purpose": "desk", "location_direction": "N"}],
            "xuankong": {
                "city_gate": {},
                "interpretation": {},
            },
        }
    )
    assert assess.analyze_layout is True
    assert set(assess.selected_methods) == {
        "xuankong_natal",
        "annual_stars",
        "monthly_stars",
        "bazhai",
    }
    assert assess.xuankong is not None
    assert assess.xuankong.period is not None and assess.xuankong.period.event_year == 2004
    assert assess.xuankong.city_gate is not None
    assert assess.xuankong.city_gate.reference_period_number == 9
    assert assess.xuankong.interpretation is not None
    assert assess.xuankong.interpretation.current_period_number == 9
    assessed = calculate_fengshui_assessment(assess)
    assert assessed["status"] == "partial"
    assert "layout_analysis" in assessed
    assert "palace_overlay" in assessed
