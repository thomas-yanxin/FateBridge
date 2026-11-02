"""The shared default preserves existing operational boundary candidates."""

import asyncio
from datetime import datetime, timedelta

from fatebridge.core import de440_solar
from fatebridge.core.fengshui.calendar import (
    boundary_model_policy,
    boundary_uncertainty_reason,
    solar_term_resolution,
)
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    inputs,
    native,
    rest,
)


def test_default_fengshui_model_keeps_the_existing_five_second_guard(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("FATEBRIDGE_SOLAR_TERM_MODEL", raising=False)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    resolution = solar_term_resolution(2026, "立春", "UTC")
    policy = boundary_model_policy(resolution)
    assert policy is not None
    assert policy["operational_guard_seconds"] == 5.0
    assert policy["scope"] == "candidate_preservation_not_numerical_accuracy_acceptance"
    instant = datetime.fromisoformat(resolution["moment"])
    assert (
        boundary_uncertainty_reason(instant + timedelta(seconds=4), resolution)
        is not None
    )
    assert (
        boundary_uncertainty_reason(instant + timedelta(seconds=6), resolution) is None
    )


def test_default_fengshui_source_is_an_orbit_record_crossing(monkeypatch):
    monkeypatch.delenv("FATEBRIDGE_SOLAR_TERM_MODEL", raising=False)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    resolution = solar_term_resolution(2026, "立春", "UTC")
    assert resolution["ephemeris_model"] == de440_solar.MODEL_ID
    assert resolution["ephemeris_model_scope"] == "named_ephemeris_solar_crossing"
    assert resolution["solar_model_details"]["reference_event_table_used"] is False


def test_default_shared_fengshui_source_matches_all_protocols(
    monkeypatch, rest, tmp_path, capsys
):
    monkeypatch.delenv("FATEBRIDGE_SOLAR_TERM_MODEL", raising=False)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    spec = SPECS["fengshui_assess"]
    payload = inputs(spec)
    options = dict(include_snapshot_text=False, response_char_limit=0)
    http = rest.post(spec.rest_path, json=payload, params={**options, "as_of": AS_OF})
    mcp = asyncio.run(native(spec, payload, **options))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=["--include-snapshot-text", "false", "--response-char-limit", "0"],
    )
    assert http.status_code == 200, http.text
    assert not mcp.is_error and code == 0
    outputs = [http.json(), mcp.structured_content, cli]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        assert (
            de440_solar.MODEL_ID
            in output["run_metadata"]["provenance"]["ephemeris_model"]
        )
