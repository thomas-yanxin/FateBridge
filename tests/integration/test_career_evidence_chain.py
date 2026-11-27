"""Regressions for career evidence lost between raw calculation and advice."""

import pytest

from fatebridge.application.examples import (
    evidence_views,
    example_input,
    suggested_fields,
)
from fatebridge.core.almanac import localize_datetime
from fatebridge.core.bazi.timing import TimingAnalysis
from fatebridge.services.bazi import calculate_bazi_career
from fatebridge.utils.birth_input import create_person_info
from tests.support.transports import SPECS, business, rest, surface_calls

D1 = dict(
    birth_year=1992,
    birth_month=8,
    birth_day=15,
    birth_hour=14,
    birth_minute=30,
    birth_timezone="Asia/Shanghai",
    birth_longitude=116.4074,
    birth_place="北京",
    gender="男",
    name="虚构D1",
    use_true_solar_time=True,
    analysis_year=2027,
    analysis_month=6,
    analysis_day=15,
)


def person():
    return create_person_info(
        1992,
        8,
        15,
        14,
        "虚构D1",
        "男",
        "北京",
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        birth_longitude=116.4074,
    )


def test_boundary_day_keeps_midnight_and_makes_hourly_followup_discoverable() -> None:
    from datetime import datetime

    tc = calculate_bazi_career(
        person(), analysis_year=2027, analysis_month=2, analysis_day=4
    )["career_analysis"]["timing_context"]
    assert tc["analysis_datetime"] == "2027-02-04T00:00:00+08:00"
    assert tc["timezone"] == "Asia/Shanghai" and tc["anchor_policy"] == "local_midnight"
    assert tc["boundary_status"] == "year_boundary_day"
    assert tc["boundaries_on_date"][0]["name"] == "立春"
    noon = TimingAnalysis.calculate_liunian(
        2027,
        moment=localize_datetime(datetime(2027, 2, 4, 12), "Asia/Shanghai"),
        timezone_name="Asia/Shanghai",
    )
    assert tc["liunian_pillar"] == "丙午"
    assert noon["stem"] + noon["branch"] == "丁未"


def test_partial_override_reports_effective_pillar_and_marks_auto_age_reference() -> (
    None
):
    tc = calculate_bazi_career(person(), analysis_year=2027, dayun_pillar="甲子")[
        "career_analysis"
    ]["timing_context"]
    assert tc["dayun_pillar"] == "甲子" and isinstance(tc["dayun_age"], float)
    assert tc["dayun_status"] == "explicit_override"
    assert tc["dayun_selection_basis"] is None
    assert tc["overridden"] == {"dayun_pillar": True, "liunian_pillar": False}


@pytest.mark.parametrize("view", [None, "target_year", "depth"])
def test_career_projection_preserves_primary_tie_and_scope_across_transports(
    view: str | None, surface_calls
) -> None:
    spec = SPECS["bazi_career"]
    fields = suggested_fields(spec, view=view)
    params = dict(detail="audit", fields=fields)
    http, protocol, code, output = surface_calls(
        spec,
        D1,
        params=params,
        options=params,
        flags=[
            "--detail",
            "audit",
            "--fields",
            *fields,
        ],
        cli_first=False,
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json())
        == business(protocol.structured_content)
        == business(output)
    )
    career = output["career_analysis"]
    if view is None:
        assert career["topic_facts"]["natal_stars"]
    if "timing_context" in career:
        assert (
            career["timing_context"]["analysis_datetime"] == "2027-06-15T00:00:00+08:00"
        )


def test_western_career_view_keeps_phase_bounds_and_real_transit_evidence() -> None:
    spec = SPECS["western_timing"]
    fields = suggested_fields(spec, view="career")
    assert "time_lords.firdaria.current_major" in fields
    assert "time_lords.firdaria.current_sub" in fields
    assert "transits.current_transit.hits" in fields
    assert "directions.timeline" not in fields
    assert "career" in evidence_views(spec)


def test_western_career_actual_evidence_agrees_across_transports(surface_calls) -> None:
    spec = SPECS["western_timing"]
    fields = suggested_fields(spec, view="career")
    request = {
        **example_input(spec),
        "analysis_year": 2027,
        "analysis_month": 6,
        "analysis_day": 15,
        "analysis_hour": 12,
        "analysis_minute": 0,
    }
    params = dict(
        detail="audit",
        fields=fields,
        as_of="2026-10-12T02:00:00Z",
    )
    http, protocol, code, output = surface_calls(
        spec,
        request,
        params=params,
        options=params,
        flags=[
            "--detail",
            "audit",
            "--fields",
            *fields,
        ],
        cli_first=False,
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json())
        == business(protocol.structured_content)
        == business(output)
    )
    firdaria = output["time_lords"]["firdaria"]
    for name in ["current_major", "current_sub"]:
        assert firdaria[name]["start"] < firdaria[name]["end"]
    transit = output["transits"]["current_transit"]
    assert isinstance(transit["hits"], list)
    assert all("orb" in hit for hit in transit["hits"])
    assert (
        output["directions"]["given_year"]["year_start"]
        < output["directions"]["given_year"]["year_end"]
    )


def test_omitted_target_date_uses_person_timezone_at_frozen_utc_across_transports(
    surface_calls,
) -> None:
    spec = SPECS["bazi_career"]
    request = {k: v for k, v in D1.items() if not k.startswith("analysis_")}
    request.update(
        birth_timezone="America/New_York", birth_longitude=-74.0, birth_place="New York"
    )
    fields = ["career_analysis.timing_context"]
    params = dict(detail="audit", fields=fields)
    http, protocol, code, output = surface_calls(
        spec,
        request,
        params={**params, "as_of": "2026-10-12T02:00:00Z"},
        options={**params, "as_of": "2026-10-12T02:00:00Z"},
        flags=[
            "--detail",
            "audit",
            "--fields",
            *fields,
        ],
        cli_first=False,
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json())
        == business(protocol.structured_content)
        == business(output)
    )
    context = output["career_analysis"]["timing_context"]
    assert context["analysis_date"] == "2026-10-11"
    assert context["analysis_datetime"] == "2026-10-11T00:00:00-04:00"


@pytest.mark.parametrize(
    "case_input,expected_stars,expected_strength,expected_structure",
    [
        (D1, ["正官", "七杀", "正印", "食神", "伤官", "偏财"], "强", "正官格"),
        pytest.param(
            dict(
                birth_year=1965,
                birth_month=12,
                birth_day=17,
                birth_hour=16,
                name="reviewer16",
                gender="女",
                birth_timezone="Asia/Shanghai",
                use_true_solar_time=False,
                analysis_year=2027,
                analysis_month=2,
                analysis_day=4,
            ),
            ["正官", "正印", "偏印", "伤官", "正财"],
            "强",
            "偏印格",
            id="1965-winter-rootless-wood",
        ),
    ],
)
def test_career_evidence_retains_star_positions_and_formation_status(
    case_input,
    expected_stars,
    expected_strength: str,
    expected_structure: str,
    surface_calls,
) -> None:
    spec = SPECS["bazi_career"]
    fields = ["career_analysis"]
    params = dict(detail="audit", fields=fields)
    http, protocol, code, output = surface_calls(
        spec,
        case_input,
        params={**params, "as_of": "2026-10-12T02:00:00Z"},
        options={**params, "as_of": "2026-10-12T02:00:00Z"},
        flags=[
            "--detail",
            "audit",
            "--fields",
            *fields,
        ],
        cli_first=False,
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json())
        == business(protocol.structured_content)
        == business(output)
    )
    career = output["career_analysis"]
    assert {"suggestions", "career_structure", "industry_analysis"}.isdisjoint(career)
    facts = career["topic_facts"]
    stars = facts["natal_stars"]
    assert [star["ten_god"] for star in stars] == expected_stars
    assert all(star["visible_in"] or star["hidden_in"] for star in stars)
    assert facts["day_master"]["strength"] == expected_strength
    assert facts["dominant_structure"] == expected_structure


@pytest.mark.parametrize(
    "override",
    [
        {"dayun_pillar": "oops"},
        {"dayun_pillar": ""},
        {"dayun_pillar": "甲子suffix"},
        {"liunian_pillar": "甲丑"},
        {"dayun_pillar": "甲丑"},
        {"dayun_pillar": "甲子suffix", "liunian_pillar": "丙寅suffix"},
    ],
)
def test_bad_overrides_rejected_across_transports(override, surface_calls) -> None:
    spec = SPECS["bazi_career"]
    case_input = {**D1, **override}
    http, protocol, code, output = surface_calls(spec, case_input, cli_first=False)
    assert http.status_code == 422 and protocol.is_error and code == 1
    bodies = [http.json(), protocol.structured_content, output]
    for body in bodies:
        assert body["error_code"] == "validation_error" and not body["retryable"]
        assert body["issues"][0]["path"] in override
        assert "career_analysis" not in body
    assert bodies[0]["issues"] == bodies[1]["issues"] == bodies[2]["issues"]


@pytest.mark.parametrize("field_name", ["dayun_pillar", "liunian_pillar"])
@pytest.mark.parametrize("invalid", ["", "oops", "甲子suffix", "甲丑"])
def test_direct_service_bad_override_rejected_before_birth_work(
    monkeypatch: pytest.MonkeyPatch, field_name: str, invalid: str
) -> None:
    import fatebridge.services.bazi as service

    def unexpected(*args, **kwargs):
        pytest.fail("invalid override must be rejected before birth computation")

    monkeypatch.setattr(service, "build_birth_computation_context", unexpected)
    result = service.calculate_bazi_career(None, **{field_name: invalid})
    assert result["status_code"] == 422 and result["error_code"] == "validation_error"
    assert result["issues"][0]["path"] == field_name


def test_all_and_only_sixty_sexagenary_pillars_are_valid() -> None:
    from pydantic import ValidationError

    from fatebridge.core.metaphysics.common import SEXAGENARY_CYCLE
    from fatebridge.core.requests.bazi import BaziCareerRequest
    from fatebridge.services.bazi import _parse_pillar_str
    from fatebridge.utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS

    for stem in HEAVENLY_STEMS:
        for branch in EARTHLY_BRANCHES:
            value = stem + branch
            if value in SEXAGENARY_CYCLE:
                assert _parse_pillar_str(value) == (stem, branch)
                assert (
                    BaziCareerRequest(**{**D1, "dayun_pillar": value}).dayun_pillar
                    == value
                )
            else:
                with pytest.raises(ValueError):
                    _parse_pillar_str(value)
                with pytest.raises(ValidationError):
                    BaziCareerRequest(**{**D1, "dayun_pillar": value})


def test_exact_valid_dual_override_matches_applied_pillars_across_transports(
    surface_calls,
) -> None:
    spec = SPECS["bazi_career"]
    case_input = {**D1, "dayun_pillar": "甲子", "liunian_pillar": "丙寅"}
    fields = [
        "career_analysis.timing_context",
        "career_analysis.topic_facts.timing_layers",
    ]
    params = dict(detail="audit", fields=fields)
    http, protocol, code, output = surface_calls(
        spec,
        case_input,
        params=params,
        options=params,
        flags=[
            "--detail",
            "audit",
            "--fields",
            *fields,
        ],
        cli_first=False,
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json())
        == business(protocol.structured_content)
        == business(output)
    )
    tc = output["career_analysis"]["timing_context"]
    assert tc["dayun_pillar"] == "甲子" and tc["liunian_pillar"] == "丙寅"
    assert tc["source"] == "explicit_pillar_overrides"
    layers = output["career_analysis"]["topic_facts"]["timing_layers"]
    assert {layer["layer"]: layer["pillar"] for layer in layers} == {
        "dayun": "甲子",
        "liunian": "丙寅",
    }


def test_career_markers_and_structure_detail_returned_with_directions(
    surface_calls,
) -> None:
    spec = SPECS["bazi_career"]
    fields = suggested_fields(spec, view="markers")
    params = dict(detail="audit", fields=fields)
    http, protocol, code, output = surface_calls(
        spec,
        D1,
        params=params,
        options=params,
        flags=["--detail", "audit", "--fields", *fields],
        cli_first=False,
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json())
        == business(protocol.structured_content)
        == business(output)
    )
    markers = output["career_analysis"]["topic_facts"]["markers"]
    assert markers
    names = {m["name"] for m in markers}
    assert {"天乙贵人", "禄神", "驿马", "将星", "国印贵人", "文昌"} <= names
    tianyi = [m for m in markers if m["name"] == "天乙贵人"]
    assert tianyi and all(m.get("direction") for m in tianyi)

    full = calculate_bazi_career(
        person(), analysis_year=2027, analysis_month=6, analysis_day=15
    )["career_analysis"]["topic_facts"]
    detail = full["structure_detail"]
    assert detail["label"] == full["dominant_structure"] == "正官格"
    assert {"formation_status", "obstructions", "rescues", "reason"} <= detail.keys()
