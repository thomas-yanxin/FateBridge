"""Read the fixed 2026/27 weather ledger without rewriting its predictions.

The FreeTSA trust anchor is pinned explicitly. A valid time stamp witnesses
bytes, not scientific registration, outcome provenance or predictive skill.
No outcome content is parsed before the original single-analysis time.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from fatebridge.core.meihua_clock_iso import parse_meihua_clock_label
from fatebridge.validation import meihua_weather_study as weather

STUDY_ID = "meihua-weather-HKO-20261101-20271031-v1"
MANIFEST_SHA256 = "27a24a58e88823a8b63255bdbc1e1a277a1c6a9fc056cec6b3b4c5f3faac5bee"
ATTESTATION_PINS = {
    "tsa.crt": "8bfb0305bb64e2571ca507552ef3245cb1c2fee8728e0ff8689225081ea13467",
    "cacert.pem": "2151b61137ffa86bf664691ba67e7da0b19f98c758e3d228d5d8ebf27e044438",
    "request.tsq": "15205cdc2bcbaaad65fa6f9afd12de001c61c62da4819c2bbef971c43c86dc61",
    "response.tsr": "497ad12e417148e6bb6f75711a52d75a9b786f80f0f3bca890e0bcb7222032de",
}
STUDY_FILES = {
    "plan.json",
    "forecasts.json",
    "evidence.jsonl",
    "generate.py",
    "status.json",
}
SOURCE_URL = (
    "https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKO/ALL/daily_HKO_RF_ALL.csv"
)
ANALYSIS_AFTER = "2027-11-30T00:00:00+08:00"
_TS_OPTIONS = {
    "-reply",
    "-query",
    "-verify",
    "-in",
    "-text",
    "-queryfile",
    "-data",
    "-CAfile",
    "-untrusted",
    "-attime",
    "-check_ss_sig",
}


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _aware(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Timestamps must be ISO strings with an explicit timezone")
    try:
        result = parse_meihua_clock_label(value)
    except ValueError as exc:
        raise ValueError("Invalid ISO timestamp") from exc
    if result.utcoffset() is None:
        raise ValueError("Timestamps require an explicit timezone")
    return result.astimezone(timezone.utc)


# Repository CLI and signed-ledger/receipt fields share this exact parser.
# This is a software clock convention, not an authenticated time witness.
parse_study_timestamp = _aware


def _json(raw: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def nonfinite(value: str) -> Any:
        raise ValueError(f"Nonfinite JSON token: {value}")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def parse_source_receipt(raw: bytes) -> dict[str, Any]:
    """Decode a submitted receipt without allowing duplicate or nonfinite keys."""
    value = _json(raw)
    if not isinstance(value, dict):
        raise ValueError("Source receipt must be a JSON object")
    return value


def _read(directory: Path, name: str) -> bytes:
    # Capture once, then hash and parse these same bytes. OpenSSL receives a
    # private copy too, rather than re-opening the caller's mutable paths.
    root = directory.resolve(strict=True)
    path = (root / name).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Study files must resolve inside their supplied directory")
    return path.read_bytes()


def _run_openssl(binary: str, arguments: list[str]) -> str:
    try:
        result = subprocess.run(
            [binary, *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("OpenSSL time-stamp verification unavailable") from exc
    if result.returncode != 0:
        raise ValueError(f"OpenSSL verification failed: {result.stderr[-1200:]}")
    return str(result.stdout)


def _ts_capabilities(binary: str) -> str:
    """Diagnose required switches; actual signature verification still must run."""
    try:
        result = subprocess.run(
            [binary, "ts", "-help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("OpenSSL ts capability diagnostic unavailable") from exc
    text = result.stdout + "\n" + result.stderr
    options = set(re.findall(r"(?<![\w-])-[A-Za-z][A-Za-z0-9_]*(?![\w-])", text))
    missing = sorted(_TS_OPTIONS - options)
    if result.returncode not in (0, 1) or missing:
        raise RuntimeError(
            "OpenSSL ts lacks required verification capabilities "
            f"({', '.join(missing) or 'help command failed'}); "
            "select a capable executable with openssl_binary or CLI --openssl. "
            "No verification options were removed and no fallback was attempted."
        )
    return text


def _stamp(reply: str) -> datetime:
    matches = re.findall(r"^Time stamp:\s*(.+)$", reply, flags=re.MULTILINE)
    if len(matches) != 1:
        raise ValueError("Time-stamp response must contain exactly one signed time")
    for fmt in ("%b %d %H:%M:%S %Y GMT", "%b %d %H:%M:%S.%f %Y GMT"):
        try:
            return datetime.strptime(matches[0], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError("Unsupported signed time format")


def _nonce(text: str) -> str:
    matches = re.findall(r"^Nonce:\s*(0x[0-9a-fA-F]+)$", text, flags=re.MULTILINE)
    if len(matches) != 1:
        raise ValueError("Original request and reply require a nonempty nonce")
    return str(matches[0]).lower()


def _verify_timestamp(
    captured: dict[str, bytes], *, openssl_binary: str | Path | None = None
) -> tuple[datetime, dict[str, Any]]:
    if openssl_binary is not None and (
        not isinstance(openssl_binary, (str, Path)) or not str(openssl_binary).strip()
    ):
        raise ValueError("OpenSSL executable must be a nonempty path or command name")
    executable = shutil.which(
        "openssl" if openssl_binary is None else str(openssl_binary)
    )
    if executable is None:
        raise RuntimeError(
            "OpenSSL executable not found; select a capable executable with "
            "openssl_binary or CLI --openssl"
        )
    executable = str(Path(executable).resolve(strict=True))
    binary_hash = _hash(Path(executable).read_bytes())
    version = _run_openssl(executable, ["version"]).strip()
    capabilities = _ts_capabilities(executable)
    with tempfile.TemporaryDirectory(prefix="fatebridge-meihua-ts-") as temporary:
        directory = Path(temporary)
        for name, raw in captured.items():
            (directory / name).write_bytes(raw)
        reply = _run_openssl(
            executable,
            ["ts", "-reply", "-in", str(directory / "response.tsr"), "-text"],
        )
        signed = _stamp(reply)
        query = _run_openssl(
            executable, ["ts", "-query", "-in", str(directory / "request.tsq"), "-text"]
        )
        if _nonce(reply) != _nonce(query):
            raise ValueError("Time-stamp request and response nonce disagree")
        for option, name in (("-queryfile", "request.tsq"), ("-data", "manifest.json")):
            output = _run_openssl(
                executable,
                [
                    "ts",
                    "-verify",
                    option,
                    str(directory / name),
                    "-in",
                    str(directory / "response.tsr"),
                    "-CAfile",
                    str(directory / "cacert.pem"),
                    "-untrusted",
                    str(directory / "tsa.crt"),
                    "-check_ss_sig",
                    "-attime",
                    str(int(signed.timestamp())),
                ],
            )
            if output.strip() != "Verification: OK":
                raise ValueError("OpenSSL did not confirm time-stamp verification")
    if _hash(Path(executable).read_bytes()) != binary_hash:
        raise ValueError("OpenSSL executable changed during verification")
    return signed, {
        "executable": executable,
        "version": version,
        "binary_sha256": binary_hash,
        "executable_selection": (
            "PATH" if openssl_binary is None else "explicit_argument"
        ),
        "required_ts_options": sorted(_TS_OPTIONS),
        "ts_help_sha256": _hash(capabilities.encode()),
        "binary_unchanged_at_boundary_checks": True,
        "query_nonce_and_signature_verified": True,
        "manifest_digest_and_signature_verified": True,
        "certificate_validation_time": signed.isoformat(),
        "trust_anchor": "explicitly_pinned_FreeTSA_CA_not_OS_or_scientific_registry",
        "revocation_status": "not_checked",
    }


def _ledger(
    study_dir: Path, attestation_dir: Path, *, openssl_binary: str | Path | None = None
) -> dict[str, Any]:
    manifest_raw = _read(study_dir, "manifest.json")
    if _hash(manifest_raw) != MANIFEST_SHA256:
        raise ValueError("Original study manifest SHA256 mismatch")
    if _read(attestation_dir, "manifest.json") != manifest_raw:
        raise ValueError("Attestation and study manifests disagree")
    manifest = _json(manifest_raw)
    if not isinstance(manifest, dict) or set(manifest) != STUDY_FILES:
        raise ValueError("Original manifest file set mismatch")
    files = {
        name: _read(study_dir, name)
        for name in sorted(manifest)
        if name != "generate.py"
    }
    for name, content in files.items():
        if _hash(content) != manifest[name]:
            raise ValueError(f"Original study file SHA256 mismatch: {name}")
    proof = {"manifest.json": manifest_raw}
    for name, digest in ATTESTATION_PINS.items():
        proof[name] = _read(attestation_dir, name)
        if _hash(proof[name]) != digest:
            raise ValueError(f"Original attestation SHA256 mismatch: {name}")
    signed, verification = (
        _verify_timestamp(proof)
        if openssl_binary is None
        else _verify_timestamp(proof, openssl_binary=openssl_binary)
    )
    plan = _json(files["plan.json"])
    forecasts = _json(files["forecasts.json"])
    evidence = files["evidence.jsonl"].splitlines()
    if (
        plan["study_id"] != STUDY_ID
        or plan["target"]["source"] != SOURCE_URL
        or plan["evaluation_policy"]["after"] != ANALYSIS_AFTER
        or len(plan["cohort"]) != 365
        or len(forecasts) != 365
        or len(evidence) != 365
    ):
        raise ValueError("Original study identity, schedule or cohort mismatch")
    created = _aware(plan["created_at"])
    windows = []
    for index, (cohort, forecast, line) in enumerate(
        zip(plan["cohort"], forecasts, evidence)
    ):
        day = date(2026, 11, 1) + timedelta(days=index)
        case_id = f"HKO-{day}"
        start = _aware(cohort["window_start"])
        end = _aware(cohort["window_end"])
        expected_start = _aware(f"{day}T00:00:00+08:00")
        item = _json(line)
        label = weather.rain_without_clear_label(item["weather_rule_trace"])
        tags = sorted(
            {
                tag
                for row in item["weather_rule_trace"]
                if row["status"] == "matched"
                for tag in row["tags"]
            }
        )
        if (
            cohort["case_id"] != case_id
            or forecast["case_id"] != case_id
            or item["case_id"] != case_id
            or cohort["station"] != "Hong Kong Observatory"
            or start != expected_start
            or end != start + timedelta(days=1)
            or not created <= _aware(forecast["issued_at"]) <= signed < start
            or forecast["evidence_sha256"] != _hash(line)
            or forecast["label"] != label
            or item["study_label"] != label
            or item["study_matched_tags"] != tags
        ):
            raise ValueError(
                f"Original forecast/evidence/window binding mismatch: {case_id}"
            )
        windows.append((day, start, end))
    return {
        "plan": plan,
        "forecasts": forecasts,
        "windows": windows,
        "signed": signed,
        "verification": verification,
        "file_sha256": {"manifest.json": MANIFEST_SHA256, **manifest},
    }


def _receipt(
    raw: bytes | None, receipt: dict[str, Any] | None, as_of: datetime
) -> dict[str, Any] | None:
    if raw is None and receipt is None:
        return None
    if not isinstance(raw, bytes) or not isinstance(receipt, dict):
        raise ValueError(
            "Observation bytes and their source receipt must be supplied together"
        )
    if set(receipt) != {"source_url", "retrieved_at", "body_sha256", "data_kind"}:
        raise ValueError(
            "Source receipt requires exactly URL, retrieval time, hash and data kind"
        )
    if receipt["source_url"] != SOURCE_URL or receipt["body_sha256"] != _hash(raw):
        raise ValueError("Source receipt URL or body SHA256 mismatch")
    if receipt["data_kind"] not in ("synthetic", "unverified_submission"):
        raise ValueError("Data kind must be synthetic or unverified_submission")
    retrieved = _aware(receipt["retrieved_at"])
    if retrieved > as_of:
        raise ValueError("Source retrieval time cannot follow the declared audit time")
    return {
        **receipt,
        "origin_authenticated": False,
        "retrieval_time_authenticated": False,
        "publication_time": None,
        "body_hash_verified": True,
    }


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def audit_prospective_weather_study(
    study_dir: Path,
    attestation_dir: Path,
    *,
    as_of: datetime,
    observation_bytes: bytes | None = None,
    source_receipt: dict[str, Any] | None = None,
    openssl_binary: str | Path | None = None,
) -> dict[str, Any]:
    """Verify the original ledger; only synthetic cases may simulate future scoring.

    Caller-supplied ``as_of`` is a declared clock, never a new time witness.
    A future date alone cannot unlock real submitted outcomes before the local
    clock reaches the planned analysis. This offline reader cannot authenticate
    the system clock or enforce one global statistical look across executions.
    """
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("Audit as_of requires a timezone-aware datetime")
    as_of = as_of.astimezone(timezone.utc)
    local_clock = _now_utc()
    ledger = _ledger(
        Path(study_dir), Path(attestation_dir), openssl_binary=openssl_binary
    )
    if as_of < ledger["signed"]:
        raise ValueError("Audit time predates the original signed time")
    receipt = _receipt(observation_bytes, source_receipt, as_of)
    analysis_after = _aware(ANALYSIS_AFTER)
    declared_reached = as_of >= analysis_after
    local_reached = local_clock >= analysis_after
    synthetic = receipt is not None and receipt["data_kind"] == "synthetic"
    gate_open = declared_reached and (local_reached or synthetic)
    windows = ledger["windows"]
    states = Counter(
        "closed" if end <= as_of else "not_started" if as_of < start else "active"
        for _, start, end in windows
    )
    report = {
        "study_id": STUDY_ID,
        "execution_integrity": True,
        "as_of": as_of.isoformat(),
        "as_of_is_caller_declaration": True,
        "timestamp": {
            "signed_at_utc": ledger["signed"].isoformat(),
            **ledger["verification"],
            "attestation_sha256": dict(ATTESTATION_PINS),
            "witness_scope": "original_manifest_and_retained_issued_forecasts_policy_documents_existed_before_first_target_window",
            "scientific_registry_registration": False,
            "new_reader_witnessed_by_original_timestamp": False,
        },
        "ledger": {
            "file_sha256": ledger["file_sha256"],
            "cohort_days": len(windows),
            "label_counts": dict(
                sorted(Counter(row["label"] for row in ledger["forecasts"]).items())
            ),
            "all_forecast_evidence_bindings_verified": True,
            "policy": "original_rain_without_clear_sign_v1_not_current_weather_engine",
            "individual_plan_hash_fields_present": False,
            "plan_binding": "joint_original_manifest_not_retroactive_per_record_fields",
        },
        "windows": {key: states[key] for key in ("closed", "not_started", "active")},
        "analysis_gate": {
            "registered_after": ANALYSIS_AFTER,
            "planned_analyses": 1,
            "declared_as_of_reached": declared_reached,
            "local_clock_reached": local_reached,
            "local_clock_authenticated": False,
            "synthetic_clock_simulation": synthetic
            and declared_reached
            and not local_reached,
            "outcome_parsing_allowed": gate_open,
            "global_single_analysis_adherence": "not_authenticated_by_stateless_offline_reader",
        },
        "source_receipt": receipt,
        "source_content_status": "not_supplied",
        "status": "waiting_for_registered_analysis",
        "ingested_outcome_rows": 0,
        "outcome_report": None,
        "real_world_predictive_efficacy_established": False,
        "authority_certified": False,
    }
    if not gate_open:
        if receipt is not None:
            report["source_content_status"] = "opaque_bytes_hashed_content_not_parsed"
        return report
    if receipt is None:
        report["status"] = "analysis_time_reached_source_missing"
        return report
    if not synthetic and _aware(receipt["retrieved_at"]) > local_clock:
        raise ValueError(
            "Submitted source retrieval time follows the local audit clock"
        )
    if _aware(receipt["retrieved_at"]) < windows[-1][2]:
        raise ValueError("Final source receipt predates the end of the full cohort")
    if observation_bytes is None:
        raise ValueError("Observation bytes are required for scoring")
    # Gate must precede parsing, not just suppress performance fields afterwards.
    observations = weather.parse_hko_rainfall(
        observation_bytes, start=windows[0][0], end=windows[-1][0] + timedelta(days=1)
    )
    outcomes = weather.evaluate_weather_cohort(
        [str(day) for day, _, _ in windows],
        [
            {"date": row["case_id"][4:], "label": row["label"]}
            for row in ledger["forecasts"]
        ],
        observations,
        threshold=Decimal(str(ledger["plan"]["target"]["positive_threshold_mm"])),
    )
    report.update(
        {
            "status": (
                "synthetic_mechanical_replay"
                if synthetic
                else "descriptive_unverified_submission"
            ),
            "source_content_status": "parsed_with_original_threshold_and_complete_C_flags",
            "ingested_outcome_rows": len(observations),
            "outcome_report": outcomes,
        }
    )
    return report
