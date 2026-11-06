"""The corrected timing facts and their projections survive all public surfaces."""

import pytest
from jsonschema import Draft202012Validator

from tests.support.transports import SPECS, business
from tests.support.transports import rest as _shared_rest
from tests.support.transports import surface_calls

INPUT = dict(
    birth_year=1990,
    birth_month=5,
    birth_day=15,
    birth_hour=10,
    birth_minute=30,
    gender="男",
    birth_timezone="Asia/Shanghai",
    use_true_solar_time=False,
    analysis_year=2028,
    analysis_month=1,
    analysis_day=20,
    analysis_hour=12,
)


rest = _shared_rest


@pytest.mark.parametrize("key", ["dayun_analysis", "timing_analysis"])
def test_date_selected_dayun_and_shared_evidence_agree_on_three_surfaces(
    key, surface_calls
):
    spec = SPECS[key]
    response, protocol, code, local = surface_calls(
        spec,
        INPUT,
        params={"as_of": "2026-10-12T02:00:00Z"},
        flags=["--response-char-limit", "0"],
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        dayun = output["dayun_info" if key == "dayun_analysis" else "dayun_analysis"]
        assert dayun["current_dayun"] == "乙酉"
        assert dayun["selection_basis"] == "civil_calendar_moment"
        if key == "dayun_analysis":
            assert output["run_metadata"]["determinism"]["uses_current_time"] is False
        assert (
            "three_days_one_year_calendar_v1"
            in output["run_metadata"]["provenance"]["method_id"]
        )
        if key == "timing_analysis":
            assert output["liunian_analysis"]["pillar"] == "丁未"  # before 2028 立春
            assert (
                output["interaction_analysis"]["assessment_status"]
                == "structural_evidence_only"
            )


def test_timing_relation_projection_is_supported_without_recalculating(surface_calls):
    spec = SPECS["timing_analysis"]
    fields = [
        "interaction_analysis.relations",
        "interaction_analysis.rulesets",
        "dayun_analysis.start_at",
        "dayun_analysis.end_at",
    ]
    options = {"fields": fields, "strict_fields": True, "include_snapshot_text": False}
    response, protocol, code, local = surface_calls(
        spec,
        INPUT,
        params=[("fields", f) for f in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
        options=options,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    for output in [response.json(), local, protocol.structured_content]:
        assert output["interaction_analysis"]["relations"]
        assert output["interaction_analysis"]["rulesets"]
        assert "nodes" not in output["interaction_analysis"]
        assert "snapshot_text" not in output


def test_conflicting_dayun_age_and_date_are_rejected_on_every_surface(surface_calls):
    spec = SPECS["dayun_analysis"]
    payload = {**INPUT, "analysis_age": 38}
    response, protocol, code, local = surface_calls(spec, payload)
    assert response.status_code == 422 and code != 0 and protocol.is_error


def test_default_dayun_clock_is_replayable_and_explicit_age_is_clock_free(rest):
    birth = {k: v for k, v in INPUT.items() if not k.startswith("analysis_")}
    timed = rest.post(
        "/api/timing/dayun", json=birth, params={"as_of": "2028-01-20T04:00:00Z"}
    ).json()
    assert timed["dayun_info"]["current_dayun"] == "乙酉"
    assert timed["run_metadata"]["determinism"]["uses_current_time"] is True
    aged = rest.post("/api/timing/dayun", json={**birth, "analysis_age": 38}).json()
    assert aged["dayun_info"]["selection_basis"] == "explicit_age_reference"
    assert aged["run_metadata"]["determinism"]["uses_current_time"] is False


def test_before_dayun_is_a_valid_result_with_timeline_on_all_surfaces(surface_calls):
    spec = SPECS["dayun_analysis"]
    birth = {k: v for k, v in INPUT.items() if not k.startswith("analysis_")}
    payload = {**birth, "analysis_age": 0}
    response, protocol, code, local = surface_calls(
        spec, payload, flags=["--response-char-limit", "0"]
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    for output in [response.json(), local, protocol.structured_content]:
        assert "error" not in output
        assert output["dayun_info"]["status"] == "before_dayun"
        assert output["dayun_info"]["current_dayun"] is None
        assert len(output["timing_context"]["timeline"]["periods"]) == 12


def test_default_comprehensive_full_instant_uses_birth_timezone(rest):
    birth = {k: v for k, v in INPUT.items() if not k.startswith("analysis_")}
    payload = {**birth, "birth_timezone": "America/New_York"}
    # New York remains in December while Shanghai has entered January.
    response = rest.post(
        "/api/timing/comprehensive",
        json=payload,
        params={"as_of": "2027-01-01T01:00:00Z"},
    )
    assert response.status_code == 200
    output = response.json()
    assert output["personal_info"]["analysis_datetime"] == "2026-12-31 20:00"
    assert (
        output["analysis_reference"]["analysis_datetime"] == "2026-12-31T20:00:00-05:00"
    )


def test_partial_dayun_date_reads_only_the_default_year_from_clock(rest):
    birth = {k: v for k, v in INPUT.items() if not k.startswith("analysis_")}
    response = rest.post(
        "/api/timing/dayun",
        json={**birth, "analysis_month": 6},
        params={"as_of": "2028-01-20T04:00:00Z"},
    )
    assert response.status_code == 200
    determinism = response.json()["run_metadata"]["determinism"]
    assert determinism["uses_current_time"] is True
    assert determinism["current_time_fields_defaulted"] == ["analysis_year"]


@pytest.mark.parametrize("key", ["timing_analysis", "dayun_analysis"])
def test_declared_birth_range_and_fact_receipt_agree_on_three_surfaces(
    key, surface_calls
):
    from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims

    spec = SPECS[key]
    payload = {**INPUT, "birth_time_uncertainty_minutes": 1}
    response, protocol, code, local = surface_calls(
        spec, payload, flags=["--response-char-limit", "0"]
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        assert output["birth_time_sensitivity"]["sample_count"] == 3
        assert output["birth_time_sensitivity"]["boundary_ranges_vary"]
        metadata = output["run_metadata"]
        claim = CalculationClaim(
            path="birth_time_sensitivity.sample_count",
            value=3,
            run_id=metadata["run_id"],
        )
        assert (
            verify_calculation_claims(output, [claim])["status"]
            == "verified_structured_facts"
        )


def test_unknown_gender_range_preserves_partial_comprehensive_result_on_three_surfaces(
    surface_calls,
):
    spec = SPECS["timing_analysis"]
    payload = {**INPUT, "gender": None, "birth_time_uncertainty_minutes": 1}
    response, protocol, code, local = surface_calls(
        spec, payload, flags=["--response-char-limit", "0"]
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        sensitivity = output["birth_time_sensitivity"]
        assert sensitivity["status"] == "partial"
        assert sensitivity["dayun_assessment_status"] == "unavailable_missing_gender"
        assert sensitivity["current_dayun_candidates"] == []
        assert output["liunian_analysis"]["pillar"]
