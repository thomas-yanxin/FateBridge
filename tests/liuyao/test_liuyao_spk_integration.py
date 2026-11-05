"""Actual file-backed solar months and unused-source isolation on public APIs."""

import asyncio
import hashlib
import json
import os
from pathlib import Path

import pytest

from fatebridge.core import almanac, spk_solar
from fatebridge.core.local_techniques.sixyao import build_sixyao_result
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.liuyao.test_liuyao_clash_transports import all_surfaces
from tests.liuyao.test_liuyao_transports import assert_same_run_receipt

MODEL = "fatebridge_jpl_spk_solar_v1"
SHA = "a4ce9bf9b3282becc9f4b2ac3cebe03a2ae7599981aabd7265fd8482fff7c4b5"
PAYLOAD = dict(
    date="1972-12-07",
    time="00:18:43.043390",
    zone="UTC",
    gua_code="111111",
    changed_code="111111",
    focus_line=4,
    timing_days=0,
)


@pytest.fixture
def selected_spk(monkeypatch, tmp_path_factory):
    pytest.importorskip("erfa", reason="optional jpl extra not installed")
    pytest.importorskip("jplephem", reason="optional jpl extra not installed")
    kernel = Path(os.environ.get("FATEBRIDGE_TEST_SPK_FILE", "ephe/solar-de440.bsp"))
    if not kernel.is_file():
        pytest.skip("External DE440 test kernel not present")
    assert hashlib.sha256(kernel.read_bytes()).hexdigest() == SHA
    empty = tmp_path_factory.mktemp("spk-empty-native")
    monkeypatch.setenv("SE_EPHE_PATH", str(empty))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "spk")
    monkeypatch.setenv("FATEBRIDGE_SOLAR_SPK_FILE", str(kernel.resolve()))
    return kernel


@pytest.mark.parametrize("mode", ["spk", "invalid-policy"])
def test_static_yi_lookup_does_not_resolve_unused_solar_source(
    mode,
    monkeypatch,
    rest,
    tmp_path,
    capsys,
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    monkeypatch.setenv("FATEBRIDGE_SOLAR_SPK_FILE", str(tmp_path / "missing.bsp"))

    def forbidden():
        pytest.fail("A static Yi lookup tried to open an unused solar SPK")

    monkeypatch.setattr(spk_solar, "_selected", forbidden)
    spec = SPECS["gua_lookup"]
    payload = dict(query="111111", lookup_mode="hexagram")
    http = rest.post(spec.rest_path, json=payload, params={"response_char_limit": 0})
    code, cli = call_cli(
        spec, payload, tmp_path, capsys, ["--response-char-limit", "0"]
    )
    mcp = asyncio.run(native(spec, payload))
    assert http.status_code == 200 and code == 0 and not mcp.is_error
    values = [http.json(), cli, mcp.structured_content]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for output in values:
        metadata = output["run_metadata"]
        policy = metadata["runtime"]["solar_term_policy"]
        assert policy["mode"] == (mode if mode == "spk" else "invalid")
        assert policy["source_resolution"] == "not_observed_in_business_output"
        assert "kernel_sha256" not in policy and "model_id" not in policy
        assert MODEL not in metadata["provenance"].get("ephemeris_model", [])


@pytest.mark.parametrize("project", [False, True])
def test_shared_sign_boundary_failure_is_corrected_by_actual_spk(
    project,
    selected_spk,
    rest,
    tmp_path,
    capsys,
):
    fields = ["liuyao_evidence.calendar_conventions.month_branch"] if project else None
    for output in all_surfaces(PAYLOAD, fields, rest, tmp_path, capsys):
        assert output["liuyao_evidence"]["calendar_conventions"]["month_branch"] == "亥"
        metadata = output["run_metadata"]
        assert MODEL in metadata["provenance"]["ephemeris_model"]
        policy = metadata["runtime"]["solar_term_policy"]
        assert policy["model_id"] == MODEL and policy["kernel_sha256"] == SHA
        assert policy["accuracy_certified"] is False
        if project:
            assert "calendar_context" not in output
        else:
            boundary = output["calendar_context"]["bazi_month_boundary"]
            assert boundary["branch"] == "亥"
            for key in ["start_term", "next_term"]:
                assert boundary[key]["ephemeris_model"] == MODEL
                assert boundary[key]["solar_model_details"]["kernel_sha256"] == SHA
            assert (
                "month_model_comparison"
                not in output["liuyao_evidence"]["calendar_conventions"]
            )


def test_spk_same_run_original_payload_hash(
    selected_spk, rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.integration.test_result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "spk-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    originals = []
    for shaped in all_surfaces(PAYLOAD, None, rest, tmp_path, capsys, budget=8192):
        original = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, original)
        assert (
            original["liuyao_evidence"]["calendar_conventions"]["month_branch"] == "亥"
        )
        assert (
            original["run_metadata"]["runtime"]["solar_term_policy"]["kernel_sha256"]
            == SHA
        )
        originals.append(business(original))
    assert originals[0] == originals[1] == originals[2]


@pytest.mark.parametrize("reason", ["missing", "invalid", "range"])
def test_consuming_sixyao_fails_loudly_on_three_protocols(
    reason,
    selected_spk,
    monkeypatch,
    rest,
    tmp_path,
    capsys,
):
    payload = dict(PAYLOAD)
    if reason == "range":
        payload["date"] = "2700-06-01"
        expected = "solar_spk_range"
    else:
        file = tmp_path / (reason + ".bsp")
        if reason == "invalid":
            file.write_bytes(b"not a SPK kernel")
        monkeypatch.setenv("FATEBRIDGE_SOLAR_SPK_FILE", str(file))
        expected = (
            "solar_spk_unavailable" if reason == "missing" else "solar_spk_invalid"
        )
    spec = SPECS["sixyao"]
    http = rest.post(spec.rest_path, json=payload)
    mcp = asyncio.run(native(spec, payload))
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    assert http.status_code == 503 and mcp.is_error and code != 0
    for output in [http.json(), cli]:
        assert output["retryable"] is False
        assert expected in str(output["issues"])
        assert "liuyao_evidence" not in output


def test_explicit_spk_cannot_relabel_native_and_default_failures(
    selected_spk, monkeypatch
):
    months = {}
    for mode in ["spk", "native", "analytic"]:
        monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
        result = build_sixyao_result(**PAYLOAD)
        months[mode] = result["liuyao_evidence"]["calendar_conventions"]["month_branch"]
    assert months == {"spk": "亥", "native": "子", "analytic": "子"}


def test_mid_batch_source_change_is_not_silently_accepted(selected_spk, monkeypatch):
    from fatebridge.utils.errors import EphemerisSourceError

    original = spk_solar.longitude_crossing_tt
    calls = 0

    def changed(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise EphemerisSourceError("solar_spk_changed")
        return original(*args, **kwargs)

    monkeypatch.setattr(spk_solar, "longitude_crossing_tt", changed)
    almanac.get_solar_terms_for_year.cache_clear()
    with pytest.raises(EphemerisSourceError) as caught:
        build_sixyao_result(**PAYLOAD)
    assert caught.value.reason == "solar_spk_changed"


MINUTE_CASES = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/liuyao_spk_v28/minute-cases.json"
    ).read_text()
)["rows"]


@pytest.mark.parametrize("case", MINUTE_CASES, ids=lambda case: case["id"])
def test_original_minute_month_counterexamples_in_sixyao(case, selected_spk):
    civil = case["civil_utc"]
    result = build_sixyao_result(
        **{**PAYLOAD, "date": civil[:10], "time": civil[11:19]}
    )
    assert (
        result["liuyao_evidence"]["calendar_conventions"]["month_branch"]
        == case["reference_state_under_frozen_policy"]["month_branch"]
    )
    assert (
        result["calendar_context"]["bazi_month_boundary"]["next_term"][
            "ephemeris_model"
        ]
        == MODEL
    )


def test_changed_file_and_alias_change_actual_identity(
    selected_spk, monkeypatch, tmp_path
):
    import shutil

    from fatebridge.utils.errors import EphemerisSourceError

    copy = tmp_path / "copy.bsp"
    shutil.copy2(selected_spk, copy)
    copy.chmod(0o600)
    monkeypatch.setenv("FATEBRIDGE_SOLAR_SPK_FILE", str(copy))
    before = spk_solar.cache_key()
    alias = tmp_path / "alias.bsp"
    alias.symlink_to(copy)
    monkeypatch.setenv("FATEBRIDGE_SOLAR_SPK_FILE", str(alias))
    assert spk_solar.cache_key() == before
    loaded = spk_solar._load(Path(before[0]), before[1])
    with copy.open("r+b") as handle:
        handle.seek(1024)
        byte = handle.read(1)[0]
        handle.seek(1024)
        handle.write(bytes([byte ^ 1]))
    with pytest.raises(EphemerisSourceError) as caught:
        loaded.check_unchanged()
    assert caught.value.reason == "solar_spk_changed"
    assert spk_solar.cache_key()[2] != before[2]


def test_wrong_spk_frame_is_rejected(selected_spk, monkeypatch):
    from jplephem.spk import SPK

    from fatebridge.utils.errors import EphemerisSourceError

    original = SPK.open

    def non_j2000(*args, **kwargs):
        kernel = original(*args, **kwargs)
        for segment in kernel.segments:
            segment.frame = 17
        return kernel

    spk_solar._load.cache_clear()
    monkeypatch.setattr(SPK, "open", non_j2000)
    with pytest.raises(EphemerisSourceError) as caught:
        spk_solar.source_receipt()
    assert caught.value.reason == "solar_spk_invalid"
