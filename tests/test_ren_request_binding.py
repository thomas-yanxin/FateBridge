"""Complete internally valid results must still answer the submitted request."""

import asyncio
import copy
import hashlib
import json
import shutil
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.execution_context import call_clock
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_request_binding_v3"
PIN = "c3f0fa35bb0eaa078fa3350435559484f08bb8cbec47a4754da6f24266178184"


def reference():
    from scripts.audit_ren_request_binding import reference as frozen_reference

    assert hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest() == PIN
    return frozen_reference()


REF = reference()
FAULTS = [
    p
    for p in REF["probes"]
    if p["expected"] == "reject_as_server_output_error_before_projection"
]
VALID_REQUESTS = {
    key + ":base": (key, payload) for key, payload in REF["bases"].items()
}
VALID_REQUESTS.update({p["id"]: (p["key"], p["returned_request"]) for p in FAULTS})

EDGE_REQUESTS = {}
for _key in ("liureng_gods", "liureng_runyear", "jinkou"):
    for _label, _updates in {
        "default_zone": {"analysis_timezone": None},
        "fixed_zone": {"analysis_timezone": "+08:00"},
        "day_rollover": {"analysis_hour": 23},
        "solar_other_longitude": {
            "use_true_solar_time": True,
            "analysis_longitude": -120.0,
        },
        "gender_alias": {"gender": "male"},
        "unknown_gender": {"gender": None},
        "fold_first": {
            "analysis_month": 11,
            "analysis_day": 1,
            "analysis_hour": 1,
            "analysis_timezone": "America/New_York",
            "analysis_utc_offset": "-04:00",
        },
        "fold_second": {
            "analysis_month": 11,
            "analysis_day": 1,
            "analysis_hour": 1,
            "analysis_timezone": "America/New_York",
            "analysis_utc_offset": "-05:00",
        },
    }.items():
        EDGE_REQUESTS[_key + ":" + _label] = (
            _key,
            dict(REF["bases"][_key], **_updates),
        )
for _key in ("jinkou", "liureng_gods"):
    _payload = dict(REF["bases"][_key], analysis_longitude=None)
    _payload.pop("use_true_solar_time")
    EDGE_REQUESTS[_key + ":implicit_solar_fallback"] = (_key, _payload)
for _label, _updates in {
    "no_ground": {"di_fen": None},
    "unknown_natal": {"birth_year_ganzhi": None, "year_fate_age": None},
    "branch_only": {
        "birth_year_ganzhi": None,
        "natal_branch": "卯",
        "year_fate_age": None,
    },
    "no_age": {"year_fate_age": None},
}.items():
    EDGE_REQUESTS["jinkou:" + _label] = (
        "jinkou",
        dict(REF["bases"]["jinkou"], **_updates),
    )
for _label, _updates in {
    "iso_fold_first": {
        "date": "2026-11-01",
        "time": "01:30:00-04:00",
        "zone": "America/New_York",
    },
    "iso_fold_second": {
        "date": "2026-11-01",
        "time": "01:30:00-05:00",
        "zone": "America/New_York",
    },
    "gps_precedence": {"gps_lon": 120.0},
    "default_coordinates": {"lat": None, "lon": None},
}.items():
    EDGE_REQUESTS["sanshiunited:" + _label] = (
        "sanshiunited",
        dict(REF["bases"]["sanshiunited"], **_updates),
    )


@lru_cache(maxsize=128)
def _produced(key, encoded):
    spec = SPECS[key]
    request = spec.request_model.model_validate(json.loads(encoded))
    fn, args, kwargs = spec.bind(request)
    with call_clock(AS_OF):
        value = fn(*args, **kwargs)
    assert "error" not in value, value
    execution.validate_output(spec, value)
    return value


def produce(key, payload):
    return copy.deepcopy(_produced(key, json.dumps(payload, sort_keys=True)))


def test_reference_preserves_original_setup_errors_and_all_supported_rows():
    assert len(REF["probes"]) == 70
    assert len(FAULTS) == REF["expected_fault_probe_count"] == 68
    assert (ROOT / "tests/fixtures/ren_request_binding_v1/freeze.json").is_file()
    assert (ROOT / "tests/fixtures/ren_request_binding_v2/freeze.json").is_file()


@pytest.mark.parametrize("fault", ["edit", "extra", "missing"])
def test_all_frozen_inventory_failures_still_rejected(tmp_path, fault):
    from scripts.audit_ren_request_binding import reference as frozen_reference

    target = tmp_path / "corpus"
    shutil.copytree(CORPUS, target)
    if fault == "edit":
        (target / "reference.json").write_text("{}")
    elif fault == "extra":
        (target / "unapproved.json").write_text("{}")
    else:
        (target / "protocol.json").unlink()
    with pytest.raises(ValueError, match="Frozen"):
        frozen_reference(target)


@pytest.mark.parametrize("probe", FAULTS, ids=lambda p: p["id"])
def test_complete_foreign_result_is_a_server_error(probe):
    spec = SPECS[probe["key"]]
    request = spec.request_model.model_validate(probe["request"])
    foreign = produce(spec.key, probe["returned_request"])
    execution.validate_output(spec, foreign)
    broken = replace(spec, bind=lambda _: (lambda: copy.deepcopy(foreign), (), {}))
    with pytest.raises(execution.OutputContractError):
        execution.execute_spec(broken, request)


@pytest.mark.parametrize("label", VALID_REQUESTS)
def test_correct_request_keeps_complete_business_bytes(label):
    key, payload = VALID_REQUESTS[label]
    spec = SPECS[key]
    before = produce(key, payload)
    with call_clock(AS_OF):
        after = execution.execute_spec(spec, spec.request_model.model_validate(payload))
    assert after == before


@pytest.mark.parametrize("label", EDGE_REQUESTS)
def test_normalized_clocks_and_explicitly_unknown_inputs_still_work(label):
    key, payload = EDGE_REQUESTS[label]
    spec = SPECS[key]
    before = produce(key, payload)
    with call_clock(AS_OF):
        value = execution.execute_spec(spec, spec.request_model.model_validate(payload))
    assert value == before


@pytest.mark.parametrize("key", REF["bases"])
@pytest.mark.parametrize("project", [False, True])
def test_correct_complete_and_projected_results_agree_on_three_ports(
    key, project, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = REF["bases"][key]
    params = [("as_of", AS_OF), ("response_char_limit", "0")]
    options = {}
    flags = ["--response-char-limit", "0"]
    if project:
        params += [("fields", "analysis_type"), ("strict_fields", "true")]
        options.update(fields=["analysis_type"], strict_fields=True)
        flags += ["--fields", "analysis_type", "--strict-fields", "true"]
    http = rest.post(spec.rest_path, json=payload, params=params)
    protocol = asyncio.run(native(spec, payload, **options))
    code, value = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json())
        == business(protocol.structured_content)
        == business(value)
    )


@pytest.mark.parametrize("key", REF["bases"])
@pytest.mark.parametrize("project", [False, True])
def test_foreign_complete_result_fails_on_three_ports_before_projection(
    key, project, rest, monkeypatch, tmp_path, capsys
):
    spec = SPECS[key]
    probe = next(p for p in FAULTS if p["key"] == key)
    foreign = produce(key, probe["returned_request"])
    original = execution.execute_spec

    def broken(actual, request):
        if actual.key == key:
            actual = replace(
                actual, bind=lambda _: (lambda: copy.deepcopy(foreign), (), {})
            )
        return original(actual, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    options = {}
    params = dict(as_of=AS_OF, response_char_limit=0)
    flags = ["--response-char-limit", "0"]
    if project:
        params.update(fields="analysis_type", strict_fields="true")
        options.update(fields=["analysis_type"], strict_fields=True)
        flags += ["--fields", "analysis_type", "--strict-fields", "true"]
    payload = probe["request"]
    http = rest.post(spec.rest_path, json=payload, params=params)
    protocol = asyncio.run(native(spec, payload, **options))
    code, result = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    assert http.status_code == 500 and protocol.is_error and code == 1
    assert result["error_code"] == "internal_error"
    assert business(http.json())["error_code"] == "internal_error"


@pytest.mark.parametrize("key", REF["bases"])
def test_metadata_free_shared_execution_cannot_return_a_foreign_result(key):
    spec = SPECS[key]
    row = next(p for p in FAULTS if p["key"] == key)
    foreign = produce(key, row["returned_request"])
    broken = replace(spec, bind=lambda _: (lambda: copy.deepcopy(foreign), (), {}))
    value = execution.execute_tool(
        broken,
        spec.request_model.model_validate(row["request"]),
        include_metadata=False,
    )
    assert value["error_code"] == "internal_error" and value["status_code"] == 500


def test_unsupported_original_birth_second_still_rejected_before_service():
    row = next(p for p in REF["probes"] if p["id"] == "liureng_runyear:birth_second")
    with pytest.raises(ValidationError):
        SPECS[row["key"]].request_model.model_validate(row["returned_request"])


def test_original_invalid_historical_birth_offset_is_not_a_false_success():
    row = next(p for p in REF["probes"] if p["id"] == "liureng_runyear:birth_offset")
    spec = SPECS[row["key"]]
    result = execution.execute_spec(
        spec, spec.request_model.model_validate(row["returned_request"])
    )
    assert result["error_code"] == "validation_error" and result["status_code"] == 400


@pytest.mark.parametrize("key", REF["bases"])
def test_genuine_source_failure_during_binding_keeps_its_type(key, monkeypatch):
    from fatebridge.application import ren_request_binding
    from fatebridge.utils.errors import EphemerisSourceError

    spec = SPECS[key]
    value = produce(key, REF["bases"][key])
    request = spec.request_model.model_validate(REF["bases"][key])
    broken = replace(spec, bind=lambda _: (lambda: copy.deepcopy(value), (), {}))

    def unavailable(*_args):
        raise EphemerisSourceError("timezone_rules_changed")

    monkeypatch.setattr(ren_request_binding, "require_request_binding", unavailable)
    with pytest.raises(EphemerisSourceError):
        execution.execute_spec(broken, request)
    result = execution.execute_tool(broken, request)
    assert result["error_code"] == "ephemeris_source_inconsistent"
    assert result["status_code"] == 503


@pytest.mark.parametrize("key", REF["bases"])
@pytest.mark.parametrize("project", [False, True])
def test_genuine_source_failure_keeps_its_classification_on_three_ports(
    key, project, rest, monkeypatch, tmp_path, capsys
):
    from fatebridge.application import ren_request_binding
    from fatebridge.utils.errors import EphemerisSourceError

    def unavailable(*_args):
        raise EphemerisSourceError("timezone_rules_changed")

    monkeypatch.setattr(ren_request_binding, "require_request_binding", unavailable)
    spec = SPECS[key]
    payload = REF["bases"][key]
    params = dict(as_of=AS_OF, response_char_limit=0)
    options = {}
    flags = ["--response-char-limit", "0"]
    if project:
        params.update(fields="analysis_type", strict_fields="true")
        options.update(fields=["analysis_type"], strict_fields=True)
        flags += ["--fields", "analysis_type", "--strict-fields", "true"]
    http = rest.post(spec.rest_path, json=payload, params=params)
    protocol = asyncio.run(native(spec, payload, **options))
    code, result = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    assert http.status_code == 503 and protocol.is_error and code == 1
    assert (
        result["error_code"]
        == http.json()["error_code"]
        == "ephemeris_source_inconsistent"
    )
