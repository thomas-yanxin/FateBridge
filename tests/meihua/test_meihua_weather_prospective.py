"""Original byte witnesses and synthetic clocks/outcomes; no new observed weather."""

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.validation import meihua_weather_prospective as audit

FIXTURE = Path(__file__).parents[1] / "fixtures" / "meihua-prospective-v1"
AFTER = datetime.fromisoformat("2027-11-30T00:00:00+08:00")
BEFORE = datetime.fromisoformat("2026-10-25T23:14:28+08:00")


def run(at=BEFORE, directory=FIXTURE, **kwargs):
    return audit.audit_prospective_weather_study(
        directory / "study", directory / "attestation", as_of=at, **kwargs
    )


def sample():
    return {
        "observation_bytes": (FIXTURE / "synthetic-five-rows.csv").read_bytes(),
        "source_receipt": json.loads((FIXTURE / "synthetic-receipt.json").read_bytes()),
    }


def fail_if_parsed(*args, **kwargs):
    raise AssertionError("Outcome content must not be parsed or scored before analysis")


def clock_cases():
    rows = json.loads((FIXTURE / "expected-clock-states.json").read_bytes())
    amendment = json.loads((FIXTURE / "clock-reference-amendment.json").read_bytes())
    for row in rows:
        if row["as_of"] == amendment["as_of"]:
            row.update(amendment["corrected"])
    return rows


@pytest.mark.parametrize("row", clock_cases())
def test_frozen_clocks_keep_all_windows_without_outcomes(row):
    result = run(datetime.fromisoformat(row["as_of"]))
    assert result["windows"] == {
        key: row[key] for key in ("closed", "not_started", "active")
    }
    assert (
        result["analysis_gate"]["declared_as_of_reached"]
        == row["analysis_time_reached"]
    )
    assert result["ledger"]["label_counts"] == {"rain": 70, "dry": 141, "abstain": 154}
    assert result["ledger"]["cohort_days"] == 365
    assert result["ingested_outcome_rows"] == 0
    assert result["outcome_report"] is None
    stamp = result["timestamp"]
    assert stamp["signed_at_utc"] == "2026-10-21T21:03:44+00:00"
    assert stamp["query_nonce_and_signature_verified"]
    assert stamp["manifest_digest_and_signature_verified"]
    assert not stamp["scientific_registry_registration"]
    assert not stamp["new_reader_witnessed_by_original_timestamp"]
    assert stamp["revocation_status"] == "not_checked"
    assert not result["real_world_predictive_efficacy_established"]


@pytest.mark.parametrize(
    "at", [BEFORE, datetime.fromisoformat("2027-11-29T23:59:59.999999+08:00")]
)
def test_before_analysis_does_not_even_decode_content(at, monkeypatch):
    monkeypatch.setattr(audit.weather, "parse_hko_rainfall", fail_if_parsed)
    monkeypatch.setattr(audit.weather, "evaluate_weather_cohort", fail_if_parsed)
    raw = b"\xffcompletely invalid opaque outcome bytes"
    receipt = sample()["source_receipt"]
    receipt.update(
        retrieved_at=at.isoformat(), body_sha256=hashlib.sha256(raw).hexdigest()
    )
    result = run(at, observation_bytes=raw, source_receipt=receipt)
    assert result["source_content_status"] == "opaque_bytes_hashed_content_not_parsed"
    assert result["outcome_report"] is None
    assert not result["analysis_gate"]["outcome_parsing_allowed"]


def test_future_caller_clock_cannot_unlock_submitted_outcomes(monkeypatch):
    monkeypatch.setattr(audit, "_now_utc", lambda: BEFORE)
    monkeypatch.setattr(audit.weather, "parse_hko_rainfall", fail_if_parsed)
    monkeypatch.setattr(audit.weather, "evaluate_weather_cohort", fail_if_parsed)
    args = sample()
    args["source_receipt"].update(data_kind="unverified_submission")
    result = run(AFTER, **args)
    assert result["analysis_gate"]["declared_as_of_reached"]
    assert not result["analysis_gate"]["local_clock_reached"]
    assert not result["analysis_gate"]["outcome_parsing_allowed"]
    assert result["outcome_report"] is None


def test_synthetic_future_replay_retains_missing_trace_abstain_and_baselines(
    monkeypatch,
):
    monkeypatch.setattr(audit, "_now_utc", lambda: BEFORE)
    result = run(AFTER, **sample())
    assert result["status"] == "synthetic_mechanical_replay"
    assert result["analysis_gate"]["synthetic_clock_simulation"]
    metrics = result["outcome_report"]
    assert result["ingested_outcome_rows"] == 5
    assert len(metrics["rows"]) == 365
    expected = json.loads((FIXTURE / "synthetic-expected-outcomes.json").read_bytes())
    assert [row["occurred"] for row in metrics["rows"][:5]] == list(
        expected["case_values"].values()
    )
    assert all(row["occurred"] is None for row in metrics["rows"][5:])
    assert metrics["known_observation_days"] == 3
    assert metrics["unknown_observation_days"] == 362
    assert metrics["evaluable_days"] == 2
    assert metrics["correct"] == 1
    assert metrics["accuracy_on_evaluable_days"] == 0.5
    assert metrics["full_cohort_correct_credit_fraction"] == 1 / 365
    assert metrics["declared_abstentions"] == 154
    assert metrics["missing_forecasts"] == 0
    assert metrics["confusion_matrix"] == {
        "true_positive": 0,
        "false_positive": 1,
        "true_negative": 1,
        "false_negative": 0,
    }
    assert metrics["fixed_baselines"]["same_evaluable_dates"]["always_dry_correct"] == 2
    assert metrics["fixed_baselines"]["all_observed_dates"]["always_rain_correct"] == 1
    assert metrics["fixed_baselines"]["all_observed_dates"]["always_dry_correct"] == 2
    assert metrics["rows"][2]["rainfall_mm"] is None
    assert metrics["rows"][2]["trace_upper_exclusive_mm"] == "0.05"
    assert metrics["independent_subject_count"] is None
    assert not metrics["real_world_predictive_efficacy_established"]
    assert not metrics["authority_certified"]
    assert not result["source_receipt"]["origin_authenticated"]
    assert not result["source_receipt"]["retrieval_time_authenticated"]


def test_after_gate_missing_source_is_not_an_empty_result(monkeypatch):
    monkeypatch.setattr(audit, "_now_utc", lambda: AFTER)
    result = run(AFTER)
    assert result["status"] == "analysis_time_reached_source_missing"
    assert result["outcome_report"] is None


def test_unverified_submission_remains_descriptive_even_after_local_gate(monkeypatch):
    monkeypatch.setattr(audit, "_now_utc", lambda: AFTER)
    args = sample()
    args["source_receipt"]["data_kind"] = "unverified_submission"
    result = run(AFTER, **args)
    assert result["status"] == "descriptive_unverified_submission"
    assert not result["authority_certified"]
    assert not result["source_receipt"]["origin_authenticated"]
    assert result["outcome_report"]["known_observation_days"] == 3


@pytest.mark.parametrize(
    "delta", ["2027-10-31T23:59:59+08:00", "2027-11-30T00:00:01+08:00"]
)
def test_final_source_retrieval_vintage_cannot_precede_cohort_or_follow_clock(
    delta, monkeypatch
):
    monkeypatch.setattr(audit, "_now_utc", lambda: AFTER)
    args = sample()
    args["source_receipt"]["retrieved_at"] = delta
    with pytest.raises(ValueError, match="retrieval|predates"):
        run(AFTER, **args)


def test_submitted_vintage_cannot_be_future_to_local_clock(monkeypatch):
    monkeypatch.setattr(audit, "_now_utc", lambda: AFTER)
    args = sample()
    args["source_receipt"].update(
        data_kind="unverified_submission", retrieved_at="2027-12-01T00:00:00+08:00"
    )
    with pytest.raises(ValueError, match="local audit clock"):
        run(datetime.fromisoformat("2027-12-02T00:00:00+08:00"), **args)


@pytest.mark.parametrize(
    "change",
    [
        {"source_url": "https://example.org/substituted.csv"},
        {"body_sha256": "0" * 64},
        {"data_kind": "authenticated_real"},
        {"retrieved_at": "2027-11-30T00:00:00"},
        {"retrieved_at": None},
        {"extra": True},
    ],
)
def test_bad_receipts_fail(change):
    args = sample()
    args["source_receipt"].update(change)
    with pytest.raises(ValueError):
        run(AFTER, **args)


@pytest.mark.parametrize("missing", ["observation_bytes", "source_receipt"])
def test_observation_and_receipt_are_required_together(missing):
    args = sample()
    args.pop(missing)
    with pytest.raises(ValueError, match="together"):
        run(AFTER, **args)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"data_kind":"synthetic","data_kind":"unverified_submission"}',
        b'{"x":NaN}',
        b"[]",
    ],
)
def test_source_receipt_strict_json(raw):
    with pytest.raises(ValueError):
        audit.parse_source_receipt(raw)


@pytest.mark.parametrize(
    "at",
    [
        datetime(2026, 10, 25),
        "2026-10-25",
        datetime.fromisoformat("2026-10-21T21:03:43+00:00"),
    ],
)
def test_invalid_or_predating_audit_clock_fails(at):
    with pytest.raises(ValueError, match="timezone|predates"):
        run(at)


@pytest.mark.parametrize(
    "relative",
    [
        "study/manifest.json",
        "study/plan.json",
        "study/forecasts.json",
        "study/evidence.jsonl",
        "study/status.json",
        "attestation/manifest.json",
        "attestation/tsa.crt",
        "attestation/cacert.pem",
        "attestation/request.tsq",
        "attestation/response.tsr",
    ],
)
def test_every_original_bound_file_tamper_is_rejected(relative, tmp_path):
    shutil.copytree(FIXTURE, tmp_path / "bundle")
    path = tmp_path / "bundle" / relative
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="SHA256|manifests disagree"):
        run(directory=tmp_path / "bundle")


def test_changed_forecast_and_rehashed_local_manifest_cannot_replace_old_commitment(
    tmp_path,
):
    shutil.copytree(FIXTURE, tmp_path / "bundle")
    study = tmp_path / "bundle" / "study"
    forecasts = json.loads((study / "forecasts.json").read_bytes())
    forecasts[2]["label"] = "dry"
    raw = json.dumps(forecasts).encode()
    (study / "forecasts.json").write_bytes(raw)
    manifest = json.loads((study / "manifest.json").read_bytes())
    manifest["forecasts.json"] = hashlib.sha256(raw).hexdigest()
    (study / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Original study manifest SHA256"):
        run(directory=tmp_path / "bundle")


def test_symlink_escape_fails_even_when_external_bytes_match(tmp_path):
    shutil.copytree(FIXTURE, tmp_path / "bundle")
    target = tmp_path / "bundle/study/plan.json"
    outside = tmp_path / "outside.json"
    outside.write_bytes(target.read_bytes())
    target.unlink()
    target.symlink_to(outside)
    with pytest.raises(ValueError, match="inside"):
        run(directory=tmp_path / "bundle")


def test_crypto_rejects_wrong_manifest_and_signature_independently_of_hash_pins():
    proof = {
        name: (FIXTURE / "attestation" / name).read_bytes()
        for name in ["manifest.json", *audit.ATTESTATION_PINS]
    }
    proof["manifest.json"] += b" "
    with pytest.raises(ValueError, match="OpenSSL verification failed"):
        audit._verify_timestamp(proof)
    proof["manifest.json"] = (FIXTURE / "attestation/manifest.json").read_bytes()
    corrupted = bytearray(proof["response.tsr"])
    corrupted[-1] ^= 1
    proof["response.tsr"] = bytes(corrupted)
    with pytest.raises(ValueError, match="OpenSSL verification failed"):
        audit._verify_timestamp(proof)


def test_missing_crypto_backend_does_not_report_verified(monkeypatch):
    monkeypatch.setattr(audit.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="OpenSSL"):
        run()


@pytest.mark.parametrize(
    "output", ["", "Verification: FAILED", "Verification: OK\nextra"]
)
def test_successful_process_without_exact_verification_output_is_rejected(
    output, monkeypatch
):
    original = audit._run_openssl

    def substituted(binary, args):
        return output if "-verify" in args else original(binary, args)

    monkeypatch.setattr(audit, "_run_openssl", substituted)
    with pytest.raises(ValueError, match="did not confirm"):
        run()


def test_captured_files_are_used_after_input_paths_change(tmp_path, monkeypatch):
    shutil.copytree(FIXTURE, tmp_path / "bundle")
    original = audit._verify_timestamp

    def change_after_capture(proof):
        (tmp_path / "bundle/study/plan.json").write_bytes(b"tampered after capture")
        (tmp_path / "bundle/attestation/response.tsr").write_bytes(
            b"tampered after capture"
        )
        return original(proof)

    monkeypatch.setattr(audit, "_verify_timestamp", change_after_capture)
    result = run(directory=tmp_path / "bundle")
    assert result["ledger"]["cohort_days"] == 365
    assert result["execution_integrity"]


def cli(output, directory=FIXTURE):
    script = (
        Path(__file__).parents[2] / "scripts/meihua/audit_meihua_weather_prospective.py"
    )
    return [
        sys.executable,
        "-O",
        str(script),
        "--study",
        str(directory / "study"),
        "--attestation",
        str(directory / "attestation"),
        "--as-of",
        BEFORE.isoformat(),
        "--output",
        str(output),
    ]


def test_cli_and_python_same_receipt_and_optimized_python_rejects_tamper(tmp_path):
    out = tmp_path / "report.json"
    result = subprocess.run(cli(out), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(out.read_bytes()) == run()
    shutil.copytree(FIXTURE, tmp_path / "bundle")
    (tmp_path / "bundle/study/forecasts.json").write_bytes(b"[]")
    out.unlink()
    result = subprocess.run(
        cli(out, tmp_path / "bundle"), capture_output=True, text=True
    )
    assert result.returncode == 2
    assert "SHA256 mismatch" in result.stderr
    assert not out.exists()


def test_nonce_substitution_is_rejected_by_actual_crypto_backend(tmp_path):
    proof = {
        name: (FIXTURE / "attestation" / name).read_bytes()
        for name in ["manifest.json", *audit.ATTESTATION_PINS]
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_bytes(proof["manifest.json"])
    query = tmp_path / "different-request.tsq"
    subprocess.run(
        [
            shutil.which("openssl"),
            "ts",
            "-query",
            "-data",
            str(manifest),
            "-sha256",
            "-cert",
            "-out",
            str(query),
        ],
        check=True,
        capture_output=True,
    )
    proof["request.tsq"] = query.read_bytes()
    with pytest.raises(ValueError, match="nonce disagree"):
        audit._verify_timestamp(proof)
