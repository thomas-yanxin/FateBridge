"""Explicit data-file admission covers complete Western requests and samples."""

import copy
import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_spec
from fatebridge.core import ephemeris_runtime as runtime
from fatebridge.core.astro import native_execution
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.source_session import source_session
from fatebridge.core.compressed_ephemeris import audit_compressed_endpoints
from fatebridge.core.physical_ephemeris_policy import (
    current_policy,
    data_file_policy,
)
from fatebridge.core.requests.western_policy import uses_western_policy
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import EphemerisSourceError
from tests.fixtures.surface_payloads import MCP_CASES, REST_POST_CASES
from tests.western.test_western_origin_preflight import directories, selected

SPECS = {s.key: s for s in CATALOG}
WESTERN_KEYS = [
    "astro_chart",
    "astro_chart13",
    "astro_hellen",
    "astro_germany",
    "astro_relative",
    "astro_relative_chart",
    "western_timing_analysis",
    "solarreturn",
    "lunarreturn",
    "transit",
    "solararc",
    "givenyear",
    "profection",
    "pd",
    "pdchart",
    "zr",
    "firdaria",
    "decennials",
    "astro_harmonic",
    "astro_planetary_ages",
    "astro_triplicity_rulers",
    "astro_lunation_phase",
    "astro_distributions",
    "astro_balbillus",
    "astro_keypoints",
    "astro_yearsystem129",
    "astro_planetaryarc",
    "astro_persiandirected",
    "astro_agepoint",
    "astro_vedicprog",
    "astro_jaynesprog",
    "astro_mundane",
    "astro_extrareturns",
    "astro_horary",
    "astro_election",
]


def payload(key, **updates):
    spec = SPECS[key]
    factory = (
        REST_POST_CASES[spec.rest_path]
        if spec.rest_path
        else MCP_CASES[spec.tool_name][1]
    )
    return {**factory(), **updates}


def request(key, **updates):
    return SPECS[key].request_model.model_validate(payload(key, **updates))


@pytest.mark.parametrize("key", WESTERN_KEYS)
def test_every_published_western_request_accepts_policy_and_removes_only_control(key):
    strict = request(key, ephemeris_policy="require_data_files")
    auto = request(key)
    assert uses_western_policy(strict) and auto.ephemeris_policy == "auto"
    assert strict.model_dump()["ephemeris_policy"] == "require_data_files"
    assert strict.model_json_schema()["properties"]["ephemeris_policy"]["enum"] == [
        "auto",
        "require_data_files",
    ]
    assert "ephemeris_policy" not in SPECS[key].bind(strict)[2]
    assert SPECS[key].bind(strict)[1:] == SPECS[key].bind(auto)[1:]
    from fatebridge.application.examples import evidence_views

    assert evidence_views(SPECS[key])["data_files"]["fields"] == [
        "ephemeris_data_policy"
    ]
    assert "ephemeris_data_policy" in SPECS[key].output_model.model_fields


@pytest.mark.parametrize("key", WESTERN_KEYS)
def test_every_published_western_strict_request_rejects_empty_data(key, selected):
    selected("empty")
    result = execute_spec(
        SPECS[key], request(key, ephemeris_policy="require_data_files")
    )
    assert result["error_code"] == "ephemeris_source_inconsistent"
    assert result["issues"][0]["code"] == "required_data_files_fallback"
    assert result["status_code"] == 503 and result["retryable"] is False
    assert "ephemeris_data_policy" not in result and "score" not in result
    assert current_policy() is None


@pytest.mark.parametrize("key", WESTERN_KEYS)
def test_every_published_western_full_strict_request_preserves_whole_result(
    key, selected
):
    selected("full")
    before = execute_spec(SPECS[key], request(key))
    selected("full")
    after = execute_spec(
        SPECS[key], request(key, ephemeris_policy="require_data_files")
    )
    assert "error" not in before and "error" not in after
    receipt = after.pop("ephemeris_data_policy")
    assert after == before
    assert receipt["physical_calls_by_model"]["swieph"] > 0
    assert {row["filename"] for row in receipt["observed_files"]} >= {
        "sepl_18.se1",
        "semo_18.se1",
    }
    assert receipt["atomic_native_read_set_proven"] is False
    assert receipt["all_native_event_internal_models_verified"] is False
    assert receipt["accuracy_certified"] is False
    assert current_policy() is None


@pytest.mark.parametrize(
    "key",
    [
        "astro_chart",
        "astro_hellen",
        "astro_chart13",
        "astro_germany",
        "astro_horary",
        "astro_election",
        "profection",
        "solararc",
    ],
)
def test_partial_data_keeps_original_mixed_dependency_failure(key, selected):
    selected("planet_only")
    value = execute_spec(
        SPECS[key], request(key, ephemeris_policy="require_data_files")
    )
    assert value["issues"][0]["code"] == "swiss_dependency_unavailable"


@pytest.mark.parametrize("key", ["astro_chart", "astro_chart13", "astro_germany"])
def test_solar_clock_calls_cannot_escape_strict_policy(key, selected):
    selected("empty")
    value = execute_spec(
        SPECS[key],
        request(key, use_true_solar_time=True, ephemeris_policy="require_data_files"),
    )
    assert value["error_code"] == "ephemeris_source_inconsistent"
    assert value["issues"][0]["code"] == "required_data_files_fallback"


def test_original_native_values_and_flags_stay_exact(selected, directories):
    code = """import swisseph as s,json,sys,hashlib,platform
from pathlib import Path
s.set_ephe_path(sys.argv[1]);rows=[]
for epoch in [2451545.,2455197.5]:
 for body in range(15):
  s.set_ephe_path(sys.argv[1]);v=s.calc(epoch,body,258);rows.append(dict(epoch=epoch,body=body,position=list(v[0]),returned_flags=v[1]))
print(json.dumps(dict(rows=rows,python=sys.version,platform=platform.platform(),native=s.version,binary_sha256=hashlib.sha256(Path(s.__file__).read_bytes()).hexdigest(),fatebridge_imported=any(n.startswith('fatebridge') for n in sys.modules))))"""
    raw = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code, str(directories["full"])],
        env={**os.environ, "SE_EPHE_PATH": str(directories["full"])},
        capture_output=True,
        text=True,
        check=True,
    )
    reference = json.loads(raw.stdout)
    assert not reference["fatebridge_imported"] and len(reference["rows"]) == 30
    (directories["full"].parent / "policy-native-control.json").write_text(raw.stdout)
    selected("full")
    with data_file_policy("require_data_files") as state:
        for row in reference["rows"]:
            value = runtime.ephemeris_call("calc", row["epoch"], row["body"], 258)
            assert value == (tuple(row["position"]), row["returned_flags"])
    assert state.physical_calls_by_model == {"swieph": 20}
    assert state.nonphysical_calls == 8 and state.reference_zero_calls == 2


def test_analytical_nodes_and_reference_zeros_are_not_file_read_proof(selected):
    selected("empty")
    with data_file_policy("require_data_files") as state:
        runtime.ephemeris_call("calc", 2451545.0, runtime.swe.MEAN_NODE, 258)
        earth = runtime.ephemeris_call("calc", 2451545.0, runtime.swe.EARTH, 258)
        sun = runtime.ephemeris_call(
            "calc", 2451545.0, runtime.swe.SUN, 258 | runtime.swe.FLG_HELCTR
        )
    assert set(earth[0]) == set(sun[0]) == {0}
    assert not state.files and not state.physical_calls_by_model
    assert state.reference_zero_calls == 2 and state.nonphysical_calls == 1


def test_swallowed_source_error_and_nested_auto_cannot_weaken_request(selected):
    selected("empty")
    with pytest.raises(EphemerisSourceError, match="require_data_files"):
        with data_file_policy("require_data_files"):
            with data_file_policy("auto"):
                try:
                    runtime.ephemeris_call("calc", 2451545.0, runtime.swe.SUN, 258)
                except EphemerisSourceError:
                    pass
    assert current_policy() is None
    assert runtime.ephemeris_call("calc", 2451545.0, runtime.swe.SUN, 258)[1] & 4


def test_non_native_orbital_fallback_is_rejected_even_after_optional_api_failure(
    selected, monkeypatch
):
    from fatebridge.core.astro import ephemeris

    selected("full")
    monkeypatch.setattr(ephemeris, "_swisseph_planet_state", lambda *a, **k: None)
    result = execute_spec(
        SPECS["astro_hellen"],
        request("astro_hellen", ephemeris_policy="require_data_files"),
    )
    assert result["issues"][0]["code"] == "required_data_files_fallback"


def test_optional_native_failure_cannot_return_a_successful_strict_chart(
    selected, monkeypatch
):
    selected("full")

    def broken(*args, **kwargs):
        raise RuntimeError("synthetic native failure")

    monkeypatch.setattr(runtime.swe, "calc", broken)
    value = execute_spec(
        SPECS["astro_chart"],
        request("astro_chart", ephemeris_policy="require_data_files"),
    )
    assert value["issues"][0]["code"] == "required_data_files_unavailable"


def test_unavailable_source_context_fails_instead_of_treating_flag_as_full_proof(
    selected, monkeypatch
):
    selected("full")
    monkeypatch.setattr(runtime.swe, "get_current_file_data", None)
    with pytest.raises(EphemerisSourceError) as error:
        with data_file_policy("require_data_files"):
            runtime.ephemeris_call("calc", 2451545.0, runtime.swe.SUN, 258)
    assert error.value.reason == "required_data_files_unverified"


def test_endpoint_digest_catches_changed_file(selected, directories):
    selected("full")
    path = directories["full"] / "sepl_18.se1"
    with path.open("rb") as source:
        initial = source.read(1)
    try:
        with pytest.raises(EphemerisSourceError) as error:
            with data_file_policy("require_data_files"):
                runtime.ephemeris_call("calc", 2451545.0, runtime.swe.SUN, 258)
                with path.open("r+b") as target:
                    target.write(bytes([initial[0] ^ 1]))
        assert error.value.reason == "changed_during"
    finally:
        with path.open("r+b") as target:
            target.write(initial)


def test_context_isolation_in_reused_parallel_workers(selected):
    selected("empty")

    def calculate(strict):
        try:
            with data_file_policy("require_data_files" if strict else "auto"):
                result = runtime.ephemeris_call("calc", 2451545.0, runtime.swe.SUN, 258)
        except EphemerisSourceError as error:
            assert strict and error.reason == "required_data_files_fallback"
        else:
            assert not strict and result[1] & 4
        assert current_policy() is None

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(calculate, [True, False] * 8))


@pytest.mark.parametrize("mode", ["empty", "full"])
def test_owned_subprocess_inherits_policy_and_returns_explicit_receipt(mode, selected):
    selected(mode)
    birth = build_astro_birth_info(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0.0,
        birth_latitude=0.0,
        use_true_solar_time=False,
    )
    if mode == "empty":
        with pytest.raises(EphemerisSourceError):
            with source_session(), data_file_policy("require_data_files"):
                native_execution.calculate(
                    "fatebridge.core.jyotish.positions", (birth,), {}
                )
    else:
        with source_session(), data_file_policy("require_data_files") as state:
            result = native_execution.calculate(
                "fatebridge.core.jyotish.positions", (birth,), {}
            )
        assert result and state.worker_reports
        assert state.worker_reports[0]["requested"] == "require_data_files"
        assert state.worker_reports[0]["physical_calls_by_model"]["swieph"] > 0


def test_india_policy_binding_is_retained_and_guolao_is_not_silently_claimed():
    indian = request("astro_india", ephemeris_policy="require_data_files")
    assert not uses_western_policy(indian)
    assert (
        SPECS["astro_india"].bind(indian)[2]["ephemeris_policy"] == "require_data_files"
    )
    with pytest.raises(ValueError):
        request(
            "astro_chart",
            chart_variant="guolao_chart",
            ephemeris_policy="require_data_files",
        )


@pytest.mark.parametrize("key", ["astro_chart13", "astro_germany"])
def test_non_civil_clock_and_all_uncertainty_samples_share_strict_request(
    key, selected
):
    extra = dict(
        birth_clock_basis="local_apparent_solar",
        birth_timezone=None,
        birth_time_uncertainty_minutes=0.1,
    )
    selected("full")
    auto = execute_spec(SPECS[key], request(key, **extra))
    selected("full")
    strict = execute_spec(
        SPECS[key], request(key, **extra, ephemeris_policy="require_data_files")
    )
    receipt = strict.pop("ephemeris_data_policy")
    assert "error" not in strict and strict == auto
    assert receipt["physical_calls_by_model"]["swieph"] > 0


def test_policy_public_schema_rejects_a_false_accuracy_claim(selected):
    from fatebridge.application.execution import OutputContractError, validate_output

    selected("full")
    spec = SPECS["astro_harmonic"]
    result = execute_spec(
        spec, request("astro_harmonic", ephemeris_policy="require_data_files")
    )
    assert "ephemeris_data_policy" in spec.output_model.model_fields
    tampered = copy.deepcopy(result)
    tampered["ephemeris_data_policy"]["accuracy_certified"] = True
    with pytest.raises(OutputContractError):
        validate_output(spec, tampered)


def test_native_version_outside_inspected_scope_cannot_certify_data_context(
    selected, monkeypatch
):
    selected("full")
    monkeypatch.setattr(runtime.swe, "version", "not-inspected")
    with pytest.raises(EphemerisSourceError) as error:
        with data_file_policy("require_data_files"):
            runtime.ephemeris_call("calc", 2451545.0, runtime.swe.SUN, 258)
    assert error.value.reason == "required_data_files_unverified"


@pytest.mark.parametrize("operation", ["calc", "calc_ut"])
@pytest.mark.parametrize("body", [0, 1, 4, 14])
@pytest.mark.parametrize("origin", [0, 8, 16384])
def test_strict_policy_preserves_owned_file_endpoints_and_origins(
    operation, body, origin, selected
):
    for epoch in [2451545.0, 2597651.3591467496, 2597651.3591467794]:
        selected("full")
        with audit_compressed_endpoints():
            original = runtime.ephemeris_call(operation, epoch, body, 258 | origin)
        selected("full")
        with data_file_policy("require_data_files"), audit_compressed_endpoints():
            actual = runtime.ephemeris_call(operation, epoch, body, 258 | origin)
        assert actual == original


@pytest.mark.parametrize("operation", ["calc", "calc_ut"])
@pytest.mark.parametrize("body", [0, 2, 4, 5, 9])
@pytest.mark.parametrize("origin", [8, 16384])
def test_strict_policy_does_not_reintroduce_unused_moon_dependency(
    operation, body, origin, selected
):
    selected("planet_only")
    with audit_compressed_endpoints():
        original = runtime.ephemeris_call(operation, 2451545.0, body, 258 | origin)
    selected("planet_only")
    with data_file_policy("require_data_files"), audit_compressed_endpoints():
        actual = runtime.ephemeris_call(operation, 2451545.0, body, 258 | origin)
    assert actual == original
