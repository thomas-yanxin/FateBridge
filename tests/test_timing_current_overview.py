"""Current-period overview is the same calculation, with only its full table deferred."""

import asyncio
from copy import deepcopy

import pytest

from fatebridge.application.examples import suggested_fields
from tests.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    inputs,
    native,
    rest,
)


@pytest.mark.parametrize(
    "state", ["current", "before_dayun", "missing_gender", "explicit_age"]
)
def test_first_view_keeps_every_current_fact_and_partial_status_on_three_surfaces(
    state, rest, tmp_path, capsys
):
    spec = SPECS["timing_analysis"]
    payload = {**inputs(spec), "use_true_solar_time": False}
    if state != "explicit_age":
        payload.pop("analysis_age", None)
    if state == "before_dayun":
        payload.update(
            analysis_year=payload["birth_year"],
            analysis_month=payload["birth_month"],
            analysis_day=payload["birth_day"],
            analysis_hour=12,
            analysis_minute=0,
        )
    elif state == "missing_gender":
        payload["gender"] = None
    full_response = rest.post(spec.rest_path, json=payload)
    assert full_response.status_code == 200, full_response.text
    dayun = full_response.json()["dayun_analysis"]
    expected = deepcopy(dayun)
    expected.pop("first_view")
    context = expected.get("timing_context")
    timeline = context.get("timeline") if isinstance(context, dict) else None
    if isinstance(timeline, dict):
        # No arbitrary field dropping: all metadata, conditions, model labels,
        # source references and exact boundaries survive. The original table
        # remains available in the same full service result.
        assert len(dayun["timing_context"]["timeline"]["periods"]) == 12
        timeline.pop("periods")
    assert dayun["first_view"] == expected
    if state == "before_dayun":
        assert expected["status"] == "before_dayun"
    elif state == "missing_gender":
        assert expected["status"] == "unavailable_missing_gender"
    else:
        assert expected["current_dayun"]
        assert expected["start_at"] < expected["end_at"]
        assert expected["selection_basis"] == (
            "explicit_age_reference"
            if state == "explicit_age"
            else "civil_calendar_moment"
        )
    fields = suggested_fields(spec)
    assert "dayun_analysis.first_view" in fields and "dayun_analysis" not in fields
    options = {"fields": fields, "strict_fields": True, "include_snapshot_text": False}
    http = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", p) for p in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
    )
    protocol = asyncio.run(native(spec, payload, **options))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
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
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    results = [http.json(), protocol.structured_content, cli]
    assert business(results[0]) == business(results[1]) == business(results[2])
    for result in results:
        assert result["dayun_analysis"]["first_view"] == expected
        assert result["analysis_calendar"]["analysis_date_context"][
            "bazi_month_boundary"
        ]
        assert result["liunian_analysis"]
