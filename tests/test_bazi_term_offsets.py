"""Repeated seasonal clocks must survive typed output and all three transports."""

import asyncio
import gzip
import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.almanac import SolarTerm
from fatebridge.core.analytic_solar import MODEL_ID
from fatebridge.core.output_chinese import SolarTerm as OutputTerm
from scripts.audit_bazi_term_offset_repair import NEW_FIELDS, audit
from scripts.audit_bazi_term_offsets import ROOT, discover
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.test_bazi_year_contract import TOPICS

FIRST = ROOT / "docs/validation/bazi-term-offset-discovery-first-v1.json.gz"


def witness():
    return json.loads(gzip.decompress(FIRST.read_bytes()))["representative"]


def test_complete_original_discovery_replays_with_all_failed_and_successful_folds():
    before = json.loads(gzip.decompress(FIRST.read_bytes()))
    current = discover()
    before.pop("recorded_at_utc")
    current.pop("recorded_at_utc")
    assert before == current
    assert (
        current["scanned_pairs"],
        current["ambiguous_rows"],
        current["distinct_term_events"],
    ) == (2908584, 160, 15)
    assert current["legacy_reconstruction_failures"] == 81
    assert current["maximum_legacy_error_seconds"] == 3600
    assert {r["actual_fold"] for r in current["rows"]} == {0, 1}
    assert not current["lossless_delivery_requirement_passed"]


def test_all160_ambiguous_and4872_controls_keep_original_values_and_supplied_instant():
    result = audit()
    assert (result["ambiguous_rows"], result["utc_control_rows"]) == (160, 4872)
    assert result["original_legacy_failures_retained"] == 81
    assert result["new_roundtrip_failures"] == 0
    assert result["historical_almanac_original_hash_verified"]
    assert result["live_day_ganzhi_function_ast_unchanged"]
    # Later solver/clock delivery changes are qualified by their own gates.
    assert result["calendar_top_level_function_asts_unchanged"] is False
    assert result["all_legacy_serialized_values_preserved"]
    assert not result["original_one_second_tt_threshold_changed"]
    assert not result["original_native_moshier_failures_superseded"]
    assert not result["full_goal_complete"]
    assert result["real_world_predictive_validity"] == "not_tested"


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
    assert not NEW_FIELDS.intersection(value)
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
    bad, rest, tmp_path, capsys, monkeypatch
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
    http = rest.post(spec.rest_path, json=arguments, params=options)
    protocol = asyncio.run(native(spec, arguments, **options))
    code, cli = call_cli(
        spec,
        arguments,
        tmp_path,
        capsys,
        flags=["--fields", "analysis_type", "--strict-fields", "true"],
    )
    assert http.status_code == 500 and code == 1 and protocol.is_error
    for result in [http.json(), protocol.structured_content, cli]:
        assert result["error_code"] == "internal_error"
        assert "bazi_birth" not in result


@pytest.mark.parametrize("topic", TOPICS)
@pytest.mark.parametrize("leaf_projection", [False, True])
def test_all_ten_bazi_tools_preserve_fold_on_rest_native_mcp_cli(
    topic, leaf_projection, rest, tmp_path, capsys, monkeypatch
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    # The historical cohort was produced by this explicitly named model.
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    spec = SPECS["bazi_" + topic]
    prefix = "bazi_birth" if topic == "birth" else topic + "_analysis"
    r = witness()
    reference_path = (
        ROOT / "tests/fixtures/architecture_refactor_v1/fold-term-before.json"
    )
    raw = reference_path.read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "9cd90901a8c57f0018de92397a9868645f74d4de7736bf867fe6c60988a4b777"
    )
    accepted = json.loads(raw)
    assert accepted["original_witness"] == r
    assert accepted["model"] == "analytic"
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
    response = rest.post(spec.rest_path, json=payload, params=options)
    protocol = asyncio.run(native(spec, payload, **options))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
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
        # The explicit IEEE-point clock correction predates this repair.
        # Keep the original13us difference and compare the complete current
        # term to the independently captured pre-repair source without rounding.
        assert term["datetime_with_offset"] == accepted["term"]["datetime_with_offset"]
        assert all(value == accepted["term"][key] for key, value in term.items())
        if not leaf_projection:
            assert term == accepted["term"]
        assert (
            term["resolution_provider"] == "fatebridge_analytic"
            and term["ephemeris_model"] == MODEL_ID
        )
        assert term["solar_model_details"]["native_choice_probe_model"] == "moshier"
        assert term["solar_model_details"]["accuracy_certified"] is False
        assert value["run_metadata"]["engine_is_approximate"] is True
        assert not value.get("projection_warnings")
