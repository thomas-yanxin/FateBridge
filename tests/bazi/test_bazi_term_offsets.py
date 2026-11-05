"""Repeated seasonal clocks must survive typed output and all three transports."""

import json
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.almanac import SolarTerm, get_solar_terms_for_year
from fatebridge.core.analytic_solar import MODEL_ID
from fatebridge.core.output_chinese import SolarTerm as OutputTerm
from tests.bazi.test_bazi_year_contract import TOPICS
from tests.support.transports import AS_OF, SPECS, business
from tests.support.transports import rest as _shared_rest
from tests.support.transports import surface_calls

rest = _shared_rest

ROOT = Path(__file__).resolve().parents[2]
NEW_FIELDS = ("datetime_with_offset", "datetime_utc", "utc_offset_seconds", "fold")
FIRST = ROOT / "tests/data/bazi/term-offset-input.json"


def witness():
    return json.loads(FIRST.read_text())


@pytest.mark.parametrize("seconds", [0, 1800, -1800, 19532, 19532.75])
def test_actual_offsets_are_never_rounded_to_hours_or_minutes(seconds):
    moment = datetime(
        1921, 6, 21, 23, 35, 35, 727999, tzinfo=timezone(timedelta(seconds=seconds))
    )
    value = SolarTerm("夏至", moment, "19210621", "").as_dict()
    assert value["utc_offset_seconds"] == seconds
    assert value["datetime"] == "1921-06-21 23:35:35.727999"
    assert datetime.fromisoformat(value["datetime_with_offset"]) == moment
    assert value["timezone"] == moment.tzname()
    OutputTerm.model_validate(value)


def test_naive_legacy_inputs_do_not_acquire_the_host_timezone():
    value = SolarTerm("夏至", datetime(1921, 6, 21, 23, 35), "19210621", "").as_dict()
    assert not set(NEW_FIELDS).intersection(value)
    OutputTerm.model_validate(value)
    OutputTerm.model_validate({"datetime": value["datetime"]})
    OutputTerm.model_validate(
        {"fold": 1}
    )  # Strict leaf projection may omit its siblings.
    OutputTerm.model_validate({"datetime_with_offset": "2000-01-01T00:00:00Z"})


@pytest.mark.parametrize(
    "bad",
    [
        {"datetime_with_offset": "1921-06-21T23:35:35"},
        {
            "datetime_with_offset": "1921-06-21T23:35:35+00:00",
            "utc_offset_seconds": 3600,
        },
        {
            "datetime_with_offset": "1921-06-21T23:35:35+00:00",
            "datetime": "1921-06-21 22:35:35",
        },
        {"fold": 2},
        {"fold": True},
        {"fold": False},
        {"fold": 1.0},
        {"fold": "1"},
        *[
            {"utc_offset_seconds": n}
            for n in [float("nan"), float("inf"), -86400, 86400]
        ],
    ],
)
def test_inconsistent_or_invalid_supplied_facts_are_rejected(bad):
    with pytest.raises(ValidationError):
        OutputTerm.model_validate(bad)


@pytest.mark.parametrize(
    "bad",
    [
        {"fold": True},
        {
            "datetime_with_offset": "1921-06-21T23:35:35+00:00",
            "utc_offset_seconds": 3600,
        },
    ],
)
def test_projection_cannot_hide_a_corrupt_solar_instant(
    bad, monkeypatch, surface_calls
):
    spec = SPECS["bazi_birth"]
    payload = {"bazi_birth": {"calendar_context": {"next_solar_term": bad}}}
    original = execution.execute_spec

    def corrupt(actual, request):
        if actual.key == spec.key:
            actual = replace(actual, bind=lambda _: (lambda: deepcopy(payload), (), {}))
        return original(actual, request)

    monkeypatch.setattr(execution, "execute_spec", corrupt)
    arguments = dict(
        birth_year=1921,
        birth_month=6,
        birth_day=19,
        birth_hour=12,
        birth_timezone="Africa/Algiers",
        use_true_solar_time=False,
    )
    options = dict(fields=["analysis_type"], strict_fields=True, as_of=AS_OF)
    http, protocol, code, cli = surface_calls(
        spec,
        arguments,
        params=options,
        options=options,
        flags=["--fields", "analysis_type", "--strict-fields", "true"],
        cli_first=False,
    )
    assert http.status_code == 500 and code == 1 and protocol.is_error
    for result in [http.json(), protocol.structured_content, cli]:
        assert result["error_code"] == "internal_error"
        assert "bazi_birth" not in result


@pytest.mark.parametrize("topic", TOPICS)
@pytest.mark.parametrize("leaf_projection", [False, True])
def test_all_ten_bazi_tools_preserve_fold_on_rest_native_mcp_cli(
    topic, leaf_projection, tmp_path, monkeypatch, surface_calls
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    # The historical cohort was produced by this explicitly named model.
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    spec = SPECS["bazi_" + topic]
    prefix = "bazi_birth" if topic == "birth" else topic + "_analysis"
    r = witness()
    expected_term = next(
        term
        for term in get_solar_terms_for_year(r["year"], r["zone"])
        if term.name == r["name"]
    )
    birth = datetime.fromisoformat(r["actual_local_datetime"]).replace(
        tzinfo=None, hour=12, minute=0, second=0, microsecond=0
    ) - timedelta(days=2)
    payload = dict(
        birth_year=birth.year,
        birth_month=birth.month,
        birth_day=birth.day,
        birth_hour=12,
        birth_minute=0,
        birth_timezone=r["zone"],
        gender="男",
        use_true_solar_time=False,
    )
    base = prefix + ".calendar_context"
    fields = (
        [base]
        if not leaf_projection
        else [
            base + ".next_solar_term." + k
            for k in (
                "name",
                "datetime",
                "datetime_with_offset",
                "utc_offset_seconds",
                "fold",
                "timezone",
                "resolution_provider",
                "ephemeris_model",
                "solar_model_details",
            )
        ]
    )
    options = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
        as_of=AS_OF,
    )
    response, protocol, code, cli = surface_calls(
        spec,
        payload,
        params=options,
        options=options,
        flags=[
            "--response-char-limit",
            "0",
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--fields",
            *fields,
        ],
        cli_first=False,
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    results = [response.json(), protocol.structured_content, cli]
    assert business(results[0]) == business(results[1]) == business(results[2])
    for value in results:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(value)
        term = value[prefix]["calendar_context"]["next_solar_term"]
        assert (
            term["name"],
            term["fold"],
            term["timezone"],
            term["utc_offset_seconds"],
        ) == ("夏至", 1, r["zone"], 0)
        # Exact serialization of the current core term is the transport gate.
        # Independent model accuracy is checked against the astronomical sources.
        assert term["datetime_with_offset"] == expected_term.moment.isoformat()
        assert (
            term["resolution_provider"] == "fatebridge_analytic"
            and term["ephemeris_model"] == MODEL_ID
        )
        assert term["solar_model_details"]["native_choice_probe_model"] == "moshier"
        assert term["solar_model_details"]["accuracy_certified"] is False
        assert value["run_metadata"]["engine_is_approximate"] is True
        assert not value.get("projection_warnings")
