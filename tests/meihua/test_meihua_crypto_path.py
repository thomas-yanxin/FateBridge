"""Original timestamp, explicit local verifier, and rejection controls; no outcomes."""

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.validation import meihua_weather_prospective as audit

FIXTURES = Path(__file__).parents[1] / "fixtures"
LEDGER = FIXTURES / "meihua-prospective-v1"
CONTRACT = json.loads(
    (FIXTURES / "meihua_crypto_path_v1/independent-verifier-contract.json").read_bytes()
)
CONTRACT_SHA = "6b4cba4b2044cdd0c5cc2d2aef90c369b593380c958c2ec8be114b018d598bc5"


def proof():
    return {
        name: (LEDGER / "attestation" / name).read_bytes()
        for name in [
            "manifest.json",
            "tsa.crt",
            "cacert.pem",
            "request.tsq",
            "response.tsr",
        ]
    }


def backend():
    value = shutil.which("openssl")
    assert (
        value is not None
    ), "Run this crypto integration suite with capable OpenSSL on PATH"
    return Path(value).resolve()


def run(**kwargs):
    return audit.audit_prospective_weather_study(
        LEDGER / "study",
        LEDGER / "attestation",
        as_of=datetime(2026, 10, 25, 15, 14, 28, tzinfo=timezone.utc),
        **kwargs,
    )


def test_preimplementation_independent_contract_is_unchanged():
    raw = (
        FIXTURES / "meihua_crypto_path_v1/independent-verifier-contract.json"
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == CONTRACT_SHA
    assert (
        hashlib.sha256(proof()["manifest.json"]).hexdigest()
        == CONTRACT["ledger_manifest_sha256"]
    )


def test_explicit_backend_keeps_complete_report_and_records_actual_binary():
    default = run()
    explicit = run(openssl_binary=backend())
    stamp = explicit["timestamp"]
    assert stamp["executable"] == str(backend())
    assert stamp["binary_sha256"] == hashlib.sha256(backend().read_bytes()).hexdigest()
    assert stamp["executable_selection"] == "explicit_argument"
    assert default["timestamp"]["executable_selection"] == "PATH"
    assert stamp["binary_unchanged_at_boundary_checks"] is True
    assert set(stamp["required_ts_options"]) == set(
        CONTRACT["required_ts_help_options"]
    )
    assert stamp["revocation_status"] == "not_checked"
    assert not stamp["scientific_registry_registration"]
    assert not explicit["authority_certified"]
    assert not explicit["real_world_predictive_efficacy_established"]
    assert explicit["ingested_outcome_rows"] == 0
    assert explicit["outcome_report"] is None
    explicit["timestamp"]["executable_selection"] = "PATH"
    assert explicit == default


def test_actual_verification_still_executes_both_original_commands(monkeypatch):
    commands = []
    original = audit._run_openssl

    def traced(binary, args):
        if "-verify" in args:
            commands.append(list(args))
        return original(binary, args)

    monkeypatch.setattr(audit, "_run_openssl", traced)
    result = run(openssl_binary=backend())
    assert len(commands) == 2
    for args, operation, name in zip(
        commands, CONTRACT["verification_operations"], ["request.tsq", "manifest.json"]
    ):
        directory = Path(args[3]).parent
        expected = [
            "ts",
            "-verify",
            operation,
            str(directory / name),
            "-in",
            str(directory / "response.tsr"),
            "-CAfile",
            str(directory / "cacert.pem"),
            "-untrusted",
            str(directory / "tsa.crt"),
            "-check_ss_sig",
            "-attime",
            str(CONTRACT["verification_epoch"]),
        ]
        assert args == expected
    assert result["timestamp"]["query_nonce_and_signature_verified"]
    assert result["timestamp"]["manifest_digest_and_signature_verified"]


@pytest.mark.parametrize("missing", CONTRACT["required_ts_help_options"])
@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_missing_advertised_capability_cannot_be_substring_matched(
    missing, stream, monkeypatch
):
    options = [x for x in CONTRACT["required_ts_help_options"] if x != missing]
    # An unsupported longer option must not count as the exact required option.
    text = "Usage: ts\n" + "\n".join(options + [missing + "_unsupported"])
    result = subprocess.CompletedProcess([], 0, stdout="", stderr="")
    setattr(result, stream, text)
    monkeypatch.setattr(audit.subprocess, "run", lambda *a, **k: result)
    with pytest.raises(
        RuntimeError, match="required verification capabilities"
    ) as error:
        audit._ts_capabilities("not-executed")
    assert missing in str(error.value)
    assert "--openssl" in str(error.value)


@pytest.mark.parametrize("code", [0, 1])
def test_help_exit_status_is_diagnostic_and_never_a_signature_verdict(
    code, monkeypatch
):
    result = subprocess.CompletedProcess(
        [], code, stdout="\n".join(CONTRACT["required_ts_help_options"]), stderr=""
    )
    monkeypatch.setattr(audit.subprocess, "run", lambda *a, **k: result)
    assert audit._ts_capabilities("not-executed")


@pytest.mark.parametrize("code", [-9, 2, 70])
def test_unexpected_help_exit_rejected_even_with_all_options(code, monkeypatch):
    result = subprocess.CompletedProcess(
        [], code, stdout="\n".join(CONTRACT["required_ts_help_options"]), stderr=""
    )
    monkeypatch.setattr(audit.subprocess, "run", lambda *a, **k: result)
    with pytest.raises(RuntimeError):
        audit._ts_capabilities("not-executed")


@pytest.mark.parametrize(
    "error", [OSError("unavailable"), subprocess.TimeoutExpired("probe", 15)]
)
def test_capability_probe_failure_does_not_report_verification(error, monkeypatch):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(audit.subprocess, "run", fail)
    with pytest.raises(RuntimeError, match="diagnostic unavailable"):
        audit._ts_capabilities("not-executed")


def test_missing_explicit_backend_does_not_fall_back(monkeypatch):
    names = []

    def missing(name):
        names.append(name)
        return None

    monkeypatch.setattr(audit.shutil, "which", missing)
    with pytest.raises(RuntimeError, match="not found"):
        audit._verify_timestamp(proof(), openssl_binary="explicit-missing-binary")
    assert names == ["explicit-missing-binary"]


@pytest.mark.parametrize("value", ["", "   ", 3, True])
def test_invalid_explicit_backend_is_rejected(value):
    with pytest.raises(ValueError, match="nonempty path"):
        audit._verify_timestamp(proof(), openssl_binary=value)


@pytest.mark.parametrize(
    "field", ["manifest.json", "response.tsr", "cacert.pem", "tsa.crt"]
)
def test_actual_crypto_rejects_corruption_after_capability_diagnostic(field):
    captured = proof()
    if field in {"manifest.json", "response.tsr"}:
        changed = bytearray(captured[field])
        changed[-1] ^= 1
        captured[field] = bytes(changed)
    else:
        captured[field] = b"invalid certificate"
    with pytest.raises(ValueError):
        audit._verify_timestamp(captured, openssl_binary=backend())


@pytest.mark.skipif(os.name != "posix", reason="POSIX executable wrapper control")
def test_real_wrapper_path_is_one_argument_and_changed_binary_is_rejected(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    wrapper = tmp_path / "verifier with spaces $(touch must-not-exist)"
    wrapper.write_text("#!/bin/sh\nexec " + shlex.quote(str(backend())) + ' "$@"\n')
    wrapper.chmod(0o700)
    result = run(openssl_binary=wrapper)
    assert result["timestamp"]["executable"] == str(wrapper)
    assert not (tmp_path / "must-not-exist").exists()
    original = audit._run_openssl
    count = 0

    def replace(binary, args):
        nonlocal count
        value = original(binary, args)
        if "-verify" in args:
            count += 1
            if count == 2:
                wrapper.write_text(
                    wrapper.read_text() + "# changed after verification\n"
                )
        return value

    monkeypatch.setattr(audit, "_run_openssl", replace)
    with pytest.raises(ValueError, match="executable changed"):
        run(openssl_binary=wrapper)
    assert count == 2


def test_cli_explicit_backend_works_with_missing_default_and_does_not_change_global_path(
    tmp_path,
):
    binary = backend()
    parent_path = os.environ.get("PATH")
    env = {**os.environ, "PATH": str(tmp_path / "no-programs")}
    command = [
        sys.executable,
        "-O",
        str(
            Path(__file__).parents[2]
            / "scripts/meihua/audit_meihua_weather_prospective.py"
        ),
        "--study",
        str(LEDGER / "study"),
        "--attestation",
        str(LEDGER / "attestation"),
        "--as-of",
        "2026-10-25T23:14:28+08:00",
        "--output",
        str(tmp_path / "report.json"),
    ]
    failed = subprocess.run(
        command, env=env, capture_output=True, text=True, timeout=30
    )
    assert failed.returncode == 2 and not (tmp_path / "report.json").exists()
    assert "--openssl" in failed.stderr
    success = subprocess.run(
        command + ["--openssl", str(binary)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert success.returncode == 0, success.stderr
    result = json.loads((tmp_path / "report.json").read_bytes())
    assert result == run(openssl_binary=binary)
    assert os.environ.get("PATH") == parent_path
