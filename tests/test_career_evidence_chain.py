"""Regressions for career evidence lost between raw calculation and advice."""

import asyncio

import pytest

from fatebridge.analysis.career import CareerAnalysis
from fatebridge.application.examples import (
    evidence_views,
    example_input,
    suggested_fields,
)
from fatebridge.core.almanac import localize_datetime
from fatebridge.core.timing import TimingAnalysis
from fatebridge.services.bazi import calculate_bazi_career
from fatebridge.utils.birth_input import create_person_info
from tests.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

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


def test_primary_tie_preserves_heuristic_formation_conditions():
    career = calculate_bazi_career(
        person(), analysis_year=2027, analysis_month=6, analysis_day=15
    )["career_analysis"]
    dominant = career["dominant_ten_gods"]
    assert (
        dominant["weighted_counts"]["劫财"] == dominant["weighted_counts"]["正官"] == 2
    )
    assert set(dominant["tied_primary_gods"]) == {"劫财", "正官"}
    assert dominant["primary_career_type"] == "竞争型"  # Compatibility only.
    assert dominant["counting_basis"]["excluded_pillars"] == ["day"]
    assert dominant["counting_basis"]["hidden_stem_weight"] == 0.5
    for name in ["career_structure", "entrepreneurship"]:
        assert career[name]["formation_status"] == "heuristic_candidate_only"
        assert career[name]["unverified_conditions"]
        assert career[name]["rule_signals"]
    assert career["entrepreneurship"]["score"] == 75
    signal = career["entrepreneurship"]["rule_signals"][0]
    assert signal["label"] == "食神制杀" and signal["score_delta"] == 10


def test_counting_excludes_day_branch_and_preserves_all_primary_ties():
    pillars = {
        "year": ("甲", "子"),
        "month": ("乙", "丑"),
        "day": ("丙", "寅"),
        "hour": ("丁", "卯"),
    }
    a = CareerAnalysis._analyze_dominant_ten_gods(pillars, "丙")
    b = CareerAnalysis._analyze_dominant_ten_gods(
        {**pillars, "day": ("丙", "午")}, "丙"
    )
    assert a == b
    counts = a["weighted_counts"]
    assert set(a["tied_primary_gods"]) == {
        g for g, v in counts.items() if v == max(counts.values())
    }


def test_boundary_day_keeps_midnight_and_makes_hourly_followup_discoverable():
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
    assert tc["hourly_evidence"]["tool"] == "timing_analysis"


def test_partial_override_reports_effective_pillar_and_marks_auto_age_reference():
    tc = calculate_bazi_career(person(), analysis_year=2027, dayun_pillar="甲子")[
        "career_analysis"
    ]["timing_context"]
    assert tc["dayun_pillar"] == "甲子" and isinstance(tc["dayun_age"], float)
    assert tc["dayun_age_basis"] == "auto_derived_reference_not_override_pillar_age"
    assert tc["overridden"] == {"dayun_pillar": True, "liunian_pillar": False}


@pytest.mark.parametrize("view", [None, "direction", "target_year"])
def test_career_projection_preserves_primary_tie_and_scope_across_transports(
    view, rest, tmp_path, capsys
):
    spec = SPECS["bazi_career"]
    fields = suggested_fields(spec, view=view)
    params = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(spec.rest_path, json=D1, params=params)
    protocol = asyncio.run(native(spec, D1, **params))
    code, output = call_cli(
        spec,
        D1,
        tmp_path,
        capsys,
        [
            "--no-metadata",
            "--fields",
            *fields,
            "--strict-fields",
            "--no-include-snapshot-text",
        ],
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert business(http.json()) == business(protocol.structured_content) == output
    career = output["career_analysis"]
    assert career["interpretation_scope"]
    assert set(career["dominant_ten_gods"]["tied_primary_gods"]) == {"劫财", "正官"}
    assert career["career_structure"]["formation_status"] == "heuristic_candidate_only"
    if view != "direction":
        assert (
            career["timing_context"]["analysis_datetime"] == "2027-06-15T00:00:00+08:00"
        )


def test_western_career_view_keeps_phase_bounds_and_real_transit_evidence():
    spec = SPECS["western_timing_analysis"]
    fields = suggested_fields(spec, view="career")
    assert "time_lords.firdaria.current_major" in fields
    assert "time_lords.firdaria.current_sub" in fields
    assert "transits.current_transit.hits" in fields
    assert "directions.timeline" not in fields
    assert "career" in evidence_views(spec)


def test_western_career_actual_evidence_agrees_across_transports(
    rest, tmp_path, capsys
):
    spec = SPECS["western_timing_analysis"]
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
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
        as_of="2026-10-12T02:00:00Z",
    )
    http = rest.post(spec.rest_path, json=request, params=params)
    protocol = asyncio.run(
        native(spec, request, **{k: v for k, v in params.items() if k != "as_of"})
    )
    code, output = call_cli(
        spec,
        request,
        tmp_path,
        capsys,
        [
            "--no-metadata",
            "--fields",
            *fields,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
        ],
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert business(http.json()) == business(protocol.structured_content) == output
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
    rest, tmp_path, capsys
):
    # AS_OF is 2026-10-12T02Z: New York is still October 11, while the
    # default Shanghai clock is October 12. A timezone label alone is insufficient.
    spec = SPECS["bazi_career"]
    request = {k: v for k, v in D1.items() if not k.startswith("analysis_")}
    request.update(
        birth_timezone="America/New_York", birth_longitude=-74.0, birth_place="New York"
    )
    fields = ["career_analysis.timing_context"]
    params = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(
        spec.rest_path, json=request, params={**params, "as_of": "2026-10-12T02:00:00Z"}
    )
    protocol = asyncio.run(native(spec, request, **params))
    code, output = call_cli(
        spec,
        request,
        tmp_path,
        capsys,
        [
            "--no-metadata",
            "--fields",
            *fields,
            "--strict-fields",
            "--no-include-snapshot-text",
        ],
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert business(http.json()) == business(protocol.structured_content) == output
    context = output["career_analysis"]["timing_context"]
    assert context["analysis_date"] == "2026-10-11"
    assert context["analysis_datetime"] == "2026-10-11T00:00:00-04:00"


@pytest.mark.parametrize(
    "case_input,expected_score",
    [
        (D1, 80),
        (
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
            88,
        ),
    ],
)
def test_suggestions_do_not_reintroduce_single_primary_or_classical_formation(
    case_input, expected_score, rest, tmp_path, capsys
):
    spec = SPECS["bazi_career"]
    fields = ["career_analysis"]
    params = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(
        spec.rest_path,
        json=case_input,
        params={**params, "as_of": "2026-10-12T02:00:00Z"},
    )
    protocol = asyncio.run(native(spec, case_input, **params))
    code, output = call_cli(
        spec,
        case_input,
        tmp_path,
        capsys,
        [
            "--no-metadata",
            "--fields",
            *fields,
            "--strict-fields",
            "--no-include-snapshot-text",
        ],
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert business(http.json()) == business(protocol.structured_content) == output
    career = output["career_analysis"]
    assert career["career_structure"]["score"] == expected_score
    advice = career["suggestions"]
    assert "未验证古典成格条件" in advice[1]
    assert "列表顺序不构成优先级" in advice[-1]
    assert "兴趣、经验与岗位要求" in advice[-1]
    assert not any(
        "事业格局高" in line or "推荐行业：" in line or "自身优势" in line
        for line in advice
    )
    if len(career["dominant_ten_gods"]["tied_primary_gods"]) > 1:
        assert "并列" in advice[0] and "竞争型" in advice[0] and "管理型" in advice[0]
    else:
        assert "仅作职业类比" in advice[0]


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
def test_bad_overrides_rejected_across_transports(override, rest, tmp_path, capsys):
    spec = SPECS["bazi_career"]
    case_input = {**D1, **override}
    http = rest.post(spec.rest_path, json=case_input)
    protocol = asyncio.run(native(spec, case_input))
    code, output = call_cli(spec, case_input, tmp_path, capsys)
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
    monkeypatch, field_name, invalid
):
    import fatebridge.services.bazi as service

    def unexpected(*args, **kwargs):
        pytest.fail("invalid override must be rejected before birth computation")

    monkeypatch.setattr(service, "build_birth_computation_context", unexpected)
    result = service.calculate_bazi_career(None, **{field_name: invalid})
    assert result["status_code"] == 422 and result["error_code"] == "validation_error"
    assert result["issues"][0]["path"] == field_name


def test_all_and_only_sixty_sexagenary_pillars_are_valid():
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
    rest, tmp_path, capsys
):
    spec = SPECS["bazi_career"]
    case_input = {**D1, "dayun_pillar": "甲子", "liunian_pillar": "丙寅"}
    fields = ["career_analysis.timing_context", "career_analysis.career_timing"]
    params = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(spec.rest_path, json=case_input, params=params)
    protocol = asyncio.run(native(spec, case_input, **params))
    code, output = call_cli(
        spec,
        case_input,
        tmp_path,
        capsys,
        [
            "--no-metadata",
            "--fields",
            *fields,
            "--strict-fields",
            "--no-include-snapshot-text",
        ],
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert business(http.json()) == business(protocol.structured_content) == output
    tc = output["career_analysis"]["timing_context"]
    assert tc["dayun_pillar"] == "甲子" and tc["liunian_pillar"] == "丙寅"
    assert tc["source"] == "explicit_pillar_overrides"
