"""Unused orbit-data failures cannot change a text lookup into a calculation."""

import asyncio

import pytest

from fatebridge.core import de440_solar
from fatebridge.utils.errors import EphemerisSourceError
from tests.evaluation.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    inputs,
    native,
)
from tests.evaluation.test_agentic_nested_outputs import rest as _shared_rest


def unavailable():
    raise EphemerisSourceError("solar_de440_invalid")


rest = _shared_rest


@pytest.mark.parametrize("key", ["knowledge_read", "gua_lookup"])
def test_unobserved_default_source_is_not_resolved_for_text_tools(
    key,
    monkeypatch,
    rest,
    tmp_path,
    capsys,
):
    monkeypatch.delenv("FATEBRIDGE_SOLAR_TERM_MODEL", raising=False)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setattr(de440_solar, "_profile", unavailable)
    spec = SPECS[key]
    payload = inputs(spec)
    opts = dict(include_snapshot_text=False, response_char_limit=0)
    http = rest.post(spec.rest_path, json=payload, params={**opts, "as_of": AS_OF})
    mcp = asyncio.run(native(spec, payload, **opts))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=["--include-snapshot-text", "false", "--response-char-limit", "0"],
    )
    assert http.status_code == 200, http.text
    assert not mcp.is_error
    assert code == 0
    outputs = [http.json(), mcp.structured_content, cli]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        receipt = output["run_metadata"]["runtime"]["solar_term_policy"]
        assert receipt["mode"] == "auto"
        assert receipt["source_resolution"] == "not_observed_in_business_output"
        assert "model_id" not in receipt


@pytest.mark.parametrize(
    "key",
    [
        "bazi_" + topic
        for topic in [
            "birth",
            "career",
            "wealth",
            "health",
            "children",
            "education",
            "personality",
            "relatives",
            "marriage",
            "romance",
        ]
    ]
    + [
        "timing_analysis",
        "dayun_analysis",
        "liunian_analysis",
        "liuyue_analysis",
        "liuri_analysis",
        "liushi_analysis",
        "jieqi_timeline_analysis",
    ],
)
def test_consumed_default_source_remains_a_structured_failure(
    key,
    monkeypatch,
    rest,
    tmp_path,
    capsys,
):
    monkeypatch.delenv("FATEBRIDGE_SOLAR_TERM_MODEL", raising=False)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setattr(de440_solar, "_profile", unavailable)
    spec = SPECS[key]
    payload = {**inputs(spec), "use_true_solar_time": False}
    http = rest.post(spec.rest_path, json=payload)
    mcp = asyncio.run(native(spec, payload))
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    assert http.status_code == 503 and mcp.is_error and code != 0
    assert (
        http.json()["error_code"]
        == cli["error_code"]
        == "ephemeris_source_inconsistent"
    )
    assert http.json()["retryable"] is cli["retryable"] is False


def test_strict_native_jpl_does_not_resolve_the_unused_packaged_default(monkeypatch):
    from fatebridge.core.solar_model_policy import (
        solar_model_cache_key,
        solar_model_environment_receipt,
    )

    monkeypatch.delenv("FATEBRIDGE_SOLAR_TERM_MODEL", raising=False)
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "de440.eph")
    monkeypatch.setattr(de440_solar, "_profile", unavailable)
    assert solar_model_cache_key() == ("auto", "native_strict_jpl")
    assert solar_model_environment_receipt()["packaged_source_resolved"] is False
    # This is source-selection acceptance; it does not claim an actual native
    # .eph file is installed or that a strict-JPL physical call succeeded.


@pytest.mark.parametrize("mode", ["spk", "de440", "analytic"])
def test_explicit_conflict_is_rejected_before_loading_any_unused_data(
    monkeypatch, mode
):
    from fatebridge.core import almanac

    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "de440.eph")
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    monkeypatch.setattr(de440_solar, "_profile", unavailable)
    monkeypatch.setenv("FATEBRIDGE_SOLAR_SPK_FILE", "/intentionally/missing.bsp")
    with pytest.raises(ValueError, match="conflicts with strict JPL"):
        almanac.get_solar_terms_for_year(2022, "UTC")
