"""The derived-clock correction survives both public range consumers."""

import asyncio
import json

import pytest

from tests.bazi.test_bazi_birth_seconds import SPECS
from tests.bazi.test_bazi_unknown_second_transition import reference
from tests.support.transports import AS_OF, business, call_cli, native
from tests.support.transports import rest as _shared_rest

RANGE_SPECS = [s for s in SPECS if s.key in {"timing_analysis", "dayun_analysis"}]


def selected_reference(case):
    if case == "midnight_gap":
        return reference()
    from tests.bazi.test_bazi_unknown_second_transition import FIXTURE

    return json.loads(
        FIXTURE.with_name("unknown-second-hour-transition.json").read_text()
    )


def payload(case, second=None):
    return {
        **selected_reference(case)["birth_input"],
        "birth_second": second,
        "gender": "男",
        "birth_time_uncertainty_minutes": 1,
        "analysis_year": 2026,
        "analysis_month": 1,
        "analysis_day": 1,
        "analysis_hour": 12,
    }


rest = _shared_rest


@pytest.mark.parametrize("spec", RANGE_SPECS, ids=lambda s: s.key)
@pytest.mark.parametrize("second", [None, 0])
@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize("case", ["midnight_gap", "hour_candidate"])
def test_original_unknown_fact_and_correct_derived_candidates_on_every_surface(
    spec, second, project, case, rest, tmp_path, capsys
):
    values = payload(case, second)
    controls = {"response_char_limit": 0, "include_snapshot_text": True}
    flags = ["--response-char-limit", "0", "--include-snapshot-text", "true"]
    if project:
        fields = ["birth_time_sensitivity", "calendar_context.birth_time_input"]
        controls.update(fields=fields, strict_fields=True)
        flags += ["--fields", *fields, "--strict-fields", "true"]
    protocol = asyncio.run(native(spec, values, **controls))
    code, cli = call_cli(spec, values, tmp_path, capsys, flags=flags)
    http = rest.post(spec.rest_path, json=values, params={"as_of": AS_OF, **controls})
    assert not protocol.is_error and code == 0 and http.status_code == 200, http.text
    outputs = [protocol.structured_content, cli, http.json()]
    for result in outputs:
        assert business(result) == business(outputs[0])
        receipt = result["calendar_context"]["birth_time_input"]
        assert receipt["omitted_components"] == (["second"] if second is None else [])
        assert receipt["calculation_defaults"] == (
            {"second": 0} if second is None else {}
        )
        assert receipt["observed_precision_certified"] is False
        assert receipt["nominal_civil_datetime"] == (
            "1911-12-31T23:59:00-00:16:08"
            if case == "midnight_gap"
            else "1912-01-01T00:17:00+00:00"
        )
        sensitivity = result["birth_time_sensitivity"]
        assert sensitivity["sample_count"] == 3
        if case == "hour_candidate":
            ref = selected_reference(case)
            assert (
                len(sensitivity["pillars_candidates"])
                == ref["expected_grid_candidate_count"]
            )
            assert {
                r["pillars"]["hour"][-1] for r in sensitivity["pillars_candidates"]
            } == {ref["expected_hour_branch_on_all_grid_points"]}
        spec.output_model.model_validate(result)
        if not project:
            assert (
                "未推定记录精度" in result["snapshot_text"]
                if second is None
                else "不认证" in result["snapshot_text"]
            )


@pytest.mark.parametrize("spec", RANGE_SPECS, ids=lambda s: s.key)
@pytest.mark.parametrize("case", ["midnight_gap", "hour_candidate"])
def test_same_grid_calculation_has_distinct_input_precision_identity(spec, case, rest):
    results = []
    for second in [None, 0]:
        response = rest.post(
            spec.rest_path,
            json=payload(case, second),
            params={"as_of": AS_OF, "response_char_limit": 0},
        )
        assert response.status_code == 200, response.text
        results.append(response.json())
    assert results[0]["birth_time_sensitivity"] == results[1]["birth_time_sensitivity"]
    assert (
        results[0]["calendar_context"]["birth_time_input"]
        != results[1]["calendar_context"]["birth_time_input"]
    )
