"""Replay every declared root and all named targets without fitting accuracy gates."""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import os
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from fatebridge.core import almanac
from fatebridge.core.astro.time_scales import datetime_from_tt_point
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.ephemeris_runtime import configure_ephemeris_path
from fatebridge.core.metaphysics import ren_calendar

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_term_longitude_v1"
PIN = "5ac7cdfe4bb123f8aab1f4c592b819eb1cd5402fe560cb4c0f1b286e33700255"
ROOTS_SHA256 = "d5a3603dec39032eef026706c7c1119270541601f22c397fd0a9fefd3ffadee9"
NATIVE_PIN = "526029f1c5d985e6722629b6d598929a33644e1473c6d07b4d7b8c8e8b630589"


def native_reference() -> tuple[dict[str, Any], dict[str, Any]]:
    folder = ROOT / "tests/fixtures/ren_native_context_v1"
    if hashlib.sha256((folder / "freeze.json").read_bytes()).hexdigest() != NATIVE_PIN:
        raise ValueError("Frozen native context protocol changed")
    frozen = json.loads((folder / "freeze.json").read_text())
    if any(
        hashlib.sha256((folder / n).read_bytes()).hexdigest() != h
        for n, h in frozen["files"].items()
    ):
        raise ValueError("Frozen native context reference changed")
    return json.loads((folder / "protocol.json").read_text()), json.loads(
        (folder / "reference.json").read_text()
    )


def leaf_deltas(before: Any, after: Any, path: str = "") -> list[dict[str, Any]]:
    if type(before) is dict and type(after) is dict:
        result = []
        for key in sorted(before.keys() | after.keys()):
            child = path + "." + key if path else key
            if key not in before:
                result.append(dict(path=child, kind="added", after=after[key]))
            elif key not in after:
                result.append(dict(path=child, kind="removed", before=before[key]))
            else:
                result.extend(leaf_deltas(before[key], after[key], child))
        return result
    if type(before) is list and type(after) is list and len(before) == len(after):
        return [
            r
            for i, (a, b) in enumerate(zip(before, after))
            for r in leaf_deltas(a, b, path + f"[{i}]")
        ]
    return (
        []
        if canonical(before) == canonical(after)
        else [dict(path=path, kind="changed", before=before, after=after)]
    )


def causal_delta_check(
    before: dict[str, Any],
    after: dict[str, Any],
    profile: str,
    year: int,
    protocol: dict[str, Any],
    source_reference: dict[str, Any],
    source_files: dict[str, Any],
) -> tuple[list[dict[str, Any]], bool]:
    """Preserve the strict equality result; separately enforce the frozen repair scope."""
    deltas = leaf_deltas(before, after)
    case = next(
        (
            r
            for r in source_reference["rows"]
            if year == 1800 and r["term"] == before["name"]
        ),
        None,
    )
    allowed_additions = {
        r["path"]
        for r in protocol["allowed_added_paths"]
        if profile == r.get("profile") or profile in r.get("profiles", [])
    }
    allowed_changes = set()
    if case is not None:
        for rule in protocol["allowed_changed_existing_paths"]:
            if (
                profile == rule["profile"]
                and year == rule["year"]
                and before["name"] in rule["terms"]
            ):
                allowed_changes.update(rule["paths"])
        rule = protocol["allowed_derived_probe_paths"]
        if profile in rule["profiles"]:
            allowed_changes.update(rule["paths"])
    okay = True
    for delta in deltas:
        path = delta["path"]
        if delta["kind"] == "added" and path in allowed_additions:
            context = delta["after"]
            details = after["solar_model_details"]
            epoch = (
                details["selected_crossing_jd_tt"]
                if profile == "native_swiss"
                else details["native_choice_probe_jd_tt"]
            )
            windows = context.get("file_windows", [])
            okay &= (
                context.get("policy_id") == protocol["native_context_policy"]
                and context.get("selection_method")
                == "same_TT_Moshier_then_requested_Swiss"
                and all(
                    context.get(k) is False
                    for k in [
                        "physical_target_epoch_shifted",
                        "preflight_state_returned_as_target",
                        "physical_accuracy_certified",
                    ]
                )
                and [w.get("slot") for w in windows] == [0, 1]
                and all(
                    w["start_jd_tt"] <= epoch <= w["end_jd_tt"]
                    and source_files.get(w["filename"])
                    == {k: w[k] for k in ["sha256", "bytes"]}
                    for w in windows
                )
            )
        elif delta["kind"] == "changed" and any(
            path == p or path.startswith(p + "[") for p in allowed_changes
        ):
            okay &= case is not None
        else:
            okay = False
    if case is not None:
        details = after["solar_model_details"]
        if profile == "native_swiss":
            okay &= (
                details["selected_crossing_jd_tt"] == case["expected_jd_tt"]
                and details["root_bracket_tt"] == case["expected_bracket_tt"]
            )
        elif profile == "analytic":
            okay &= details["native_choice_probe_jd_tt"] == case["expected_jd_tt"]
        elif profile in ["de440", "spk"]:
            okay &= details["native_choice_probe_jd_tt"] is None
    return deltas, bool(okay)


def canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        allow_nan=False,
        separators=(",", ":"),
    )


def reference() -> tuple[dict[str, Any], dict[str, Any]]:
    if hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest() != PIN:
        raise ValueError("Frozen longitude protocol changed")
    freeze = json.loads((CORPUS / "freeze.json").read_text())
    if set(p.name for p in CORPUS.iterdir()) != {
        "freeze.json",
        "reference.json",
        "protocol.json",
    } or any(
        hashlib.sha256((CORPUS / n).read_bytes()).hexdigest() != h
        for n, h in freeze["files"].items()
    ):
        raise ValueError("Frozen longitude protocol changed")
    return json.loads((CORPUS / "protocol.json").read_text()), json.loads(
        (CORPUS / "reference.json").read_text()
    )


def validate_event_inventory(
    rows: Any, protocol: dict[str, Any], table: dict[str, Any]
) -> int:
    """Count event identities once; repeated easy years cannot replace others."""
    expected = {
        (profile, year, r["term"])
        for profile in protocol["profiles"]
        for year in protocol["years"]
        for r in table["rows"]
    }
    observed = set()
    for row in rows:
        term = row.get("term")
        name = term.get("name") if isinstance(term, dict) else row.get("term_name")
        key = (row.get("profile"), row.get("year"), name)
        if key not in expected or key in observed:
            raise ValueError("Frozen root inventory has an unknown or duplicate event")
        observed.add(key)
    if observed != expected:
        raise ValueError("Frozen root inventory has missing events")
    return len(observed)


def validate_frozen_roots(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != ROOTS_SHA256:
        raise ValueError("Frozen before-root bytes changed")
    protocol, table = reference()
    with gzip.open(path, "rt") as source:
        count = validate_event_inventory(
            (json.loads(line) for line in source), protocol, table
        )
    return dict(sha256=digest, unique_events=count, full_registered_inventory=True)


def coherent_fault(term: almanac.SolarTerm, *, wide: bool) -> almanac.SolarTerm:
    d = copy.deepcopy(term.solar_model_details)
    assert d is not None
    shift = 0.25 if wide else 1.0
    if "selected_crossing_tt_parts" in d:
        d["selected_crossing_tt_parts"][1] += shift
        for i, point in enumerate(d["root_bracket_tt_parts"]):
            point[1] += (-1 if i == 0 else 1) if wide else shift
        d["selected_crossing_jd_tt"] = sum(d["selected_crossing_tt_parts"])
        d["root_bracket_tt"] = [sum(p) for p in d["root_bracket_tt_parts"]]
        d["root_bracket_seconds"] = (
            d["root_bracket_tt_parts"][1][1] - d["root_bracket_tt_parts"][0][1]
        ) * 86400
        point = TTInstant.from_parts(*d["selected_crossing_tt_parts"])
    else:
        d["selected_crossing_jd_tt"] += shift
        d["root_bracket_tt"] = [
            v + ((-1 if i == 0 else 1) if wide else shift)
            for i, v in enumerate(d["root_bracket_tt"])
        ]
        d["root_bracket_seconds"] = (
            d["root_bracket_tt"][1] - d["root_bracket_tt"][0]
        ) * 86400
        point = TTInstant.from_float(d["selected_crossing_jd_tt"])
    moment = datetime_from_tt_point(point)
    # The diagnostic native-probe delta stays mathematically consistent too.
    native = d.get("native_choice_probe_jd_tt")
    if type(native) in (int, float):
        d["selected_minus_native_seconds_tt"] = float(
            (point.days - TTInstant.from_float(native).days) * 86400
        )
    return replace(
        term,
        moment=moment,
        date_key=moment.date().isoformat(),
        day_ganzhi=almanac.get_day_ganzhi(moment.year, moment.month, moment.day),
        solar_model_details=d,
    )


def audit(frozen_roots: Path, output: Path, *, matrix_only: bool) -> dict[str, Any]:
    protocol, table = reference()
    repair_protocol, repair_reference = native_reference()
    input_binding = validate_frozen_roots(frozen_roots)
    names = [row["term"] for row in table["rows"]]
    if dict(zip(almanac.SOLAR_TERM_NAMES, almanac.SOLAR_TERM_LONGITUDES)) != {
        row["term"]: row["longitude_degrees"] for row in table["rows"]
    }:
        raise ValueError("Engine target table differs from frozen HKO definitions")
    expected_sha = hashlib.sha256(frozen_roots.read_bytes()).hexdigest()
    rows_path = output.with_suffix(".rows.ndjson.gz")
    assert not rows_path.exists()
    settings = [
        "FATEBRIDGE_SOLAR_TERM_MODEL",
        "SE_EPHE_PATH",
        "FATEBRIDGE_JPL_FILE",
        "FATEBRIDGE_SOLAR_SPK_FILE",
    ]
    saved = {key: os.environ.get(key) for key in settings}
    data_root = Path(
        os.environ.get("FATEBRIDGE_AUDIT_EPHE", str(ROOT / "ephe"))
    ).resolve()
    source_files = {
        p.name: dict(
            sha256=hashlib.sha256(p.read_bytes()).hexdigest(), bytes=p.stat().st_size
        )
        for p in data_root.glob("*.se1")
        if p.is_file()
    }
    empty = output.parent / "audit-empty-native"
    empty.mkdir(exist_ok=True)
    original = getattr(ren_calendar, "validate_term_longitude", None)
    observed: dict[str, Any] | None = None

    def trace(**kwargs: Any) -> Any:
        nonlocal observed
        assert original is not None
        observed = original(**kwargs)
        return observed

    if original is not None:
        ren_calendar.validate_term_longitude = trace
    counters = dict(
        frozen_rows=0,
        replayed_roots=0,
        changed_public_roots=0,
        rejected_valid_roots=0,
        missing_observations=0,
        unexpected_public_deltas=0,
    )
    failures, matrix, additional = [], [], []
    current_profile = None
    current_year = None
    actual: dict[str, almanac.SolarTerm] = {}
    try:
        with (
            gzip.open(frozen_roots, "rt") as source,
            rows_path.open("wb") as file,
            gzip.GzipFile(fileobj=file, mode="wb", mtime=0) as sink,
        ):
            for text in source:
                row = json.loads(text)
                counters["frozen_rows"] += 1
                profile, year = row["profile"], row["year"]
                if matrix_only and year != 2026:
                    continue
                if profile != current_profile:
                    current_profile = profile
                    mode = "native" if profile.startswith("native_") else profile
                    os.environ["FATEBRIDGE_SOLAR_TERM_MODEL"] = mode
                    os.environ["SE_EPHE_PATH"] = str(
                        empty if profile == "native_moshier" else data_root
                    )
                    os.environ.pop("FATEBRIDGE_JPL_FILE", None)
                    if mode == "spk":
                        os.environ["FATEBRIDGE_SOLAR_SPK_FILE"] = str(
                            data_root / "solar-de440.bsp"
                        )
                    configure_ephemeris_path()
                    current_year = None
                if current_year != year:
                    current_year = year
                    try:
                        actual = {
                            t.name: t
                            for t in almanac.get_solar_terms_for_year(year, "UTC")
                        }
                    except Exception as exc:
                        actual = {}
                        failures.append(
                            dict(
                                profile=profile,
                                year=year,
                                stage="root_generation",
                                error=type(exc).__name__,
                                message=str(exc),
                            )
                        )
                original_term = row.get("term")
                if original_term is None:
                    failures.append(
                        dict(
                            profile=profile,
                            year=year,
                            stage="frozen_calculation_error_retained",
                            row=row,
                        )
                    )
                    continue
                term = actual.get(original_term["name"])
                observed = None
                error = None
                same = term is not None and canonical(term.as_dict()) == canonical(
                    original_term
                )
                deltas, delta_allowed = (
                    causal_delta_check(
                        original_term,
                        term.as_dict(),
                        profile,
                        year,
                        repair_protocol,
                        repair_reference,
                        source_files,
                    )
                    if term is not None
                    else ([], False)
                )
                counters["replayed_roots"] += 1
                counters["changed_public_roots"] += not same
                counters["unexpected_public_deltas"] += not delta_allowed
                try:
                    if term is None:
                        raise ValueError("Named frozen root missing from actual year")
                    ren_calendar.require_ren_solar_term(term)
                    accepted = True
                except Exception as exc:
                    accepted = False
                    error = dict(
                        type=type(exc).__name__,
                        reason=getattr(exc, "reason", None),
                        message=str(exc),
                    )
                counters["rejected_valid_roots"] += not accepted
                counters["missing_observations"] += (
                    original is not None and observed is None
                )
                record = dict(
                    profile=profile,
                    year=year,
                    name=original_term["name"],
                    public_root_identical=same,
                    causal_delta_allowed=delta_allowed,
                    public_leaf_deltas=deltas,
                    accepted=accepted,
                    error=error,
                    actual_private_receipt=(
                        dict(
                            retflags=list(term.ephemeris_retflags),
                            library_version=term.ephemeris_library_version,
                        )
                        if term
                        else None
                    ),
                    observation=observed,
                )
                sink.write((canonical(record) + "\n").encode())
                if (
                    not delta_allowed
                    or not accepted
                    or (original is not None and observed is None)
                ):
                    failures.append(record)
                if term is not None and term.name == "冬至" and year % 25 == 0:
                    print(profile, year, counters, flush=True)
                if year != 2026 or term is None:
                    continue
                for claimed in names:
                    try:
                        ren_calendar.require_ren_solar_term(replace(term, name=claimed))
                        decision = True
                    except Exception:
                        decision = False
                    matrix.append(
                        dict(
                            profile=profile,
                            actual=term.name,
                            claimed=claimed,
                            accepted=decision,
                            expected=claimed == term.name,
                        )
                    )
                if term.name == "清明":
                    for fault, bad in [
                        ("unknown_name", replace(term, name="未知节气")),
                        ("coherent_one_day_shift", coherent_fault(term, wide=False)),
                        (
                            "coherent_wide_two_day_bracket",
                            coherent_fault(term, wide=True),
                        ),
                    ]:
                        try:
                            ren_calendar.require_ren_solar_term(bad)
                            rejected = False
                        except Exception:
                            rejected = True
                        additional.append(
                            dict(profile=profile, fault=fault, rejected=rejected)
                        )
                    if profile in ("analytic", "spk"):
                        field = (
                            "coefficient_sha256"
                            if profile == "analytic"
                            else "kernel_sha256"
                        )
                        assert term.solar_model_details is not None
                        bad = replace(
                            term,
                            solar_model_details={
                                **term.solar_model_details,
                                field: "0" * 64,
                            },
                        )
                        try:
                            ren_calendar.require_ren_solar_term(bad)
                            rejected = False
                        except Exception:
                            rejected = True
                        additional.append(
                            dict(
                                profile=profile,
                                fault=profile + "_wrong_" + field,
                                rejected=rejected,
                            )
                        )
    finally:
        if original is not None:
            ren_calendar.validate_term_longitude = original
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    matrix_passed = len(matrix) == 2880 and all(
        r["accepted"] == r["expected"] for r in matrix
    )
    full_passed = (
        not matrix_only
        and counters["replayed_roots"] == 48120
        and not failures
        and counters["changed_public_roots"] == 0
    )
    forward_passed = (
        not matrix_only
        and counters["replayed_roots"] == 48120
        and counters["rejected_valid_roots"] == 0
        and counters["missing_observations"] == 0
    )
    causal_passed = (
        not matrix_only
        and counters["replayed_roots"] == 48120
        and counters["unexpected_public_deltas"] == 0
        and not failures
    )
    if source_files != {
        p.name: dict(
            sha256=hashlib.sha256(p.read_bytes()).hexdigest(), bytes=p.stat().st_size
        )
        for p in data_root.glob("*.se1")
        if p.is_file()
    }:
        raise ValueError("Native reference files changed during audit")
    if hashlib.sha256(frozen_roots.read_bytes()).hexdigest() != expected_sha:
        raise ValueError("Frozen before-root bytes changed during audit")
    return dict(
        input_binding=input_binding,
        reference_pin=PIN,
        frozen_roots_sha256=expected_sha,
        frozen_root_count_expected=48120,
        mode="matrix_only" if matrix_only else "full_root_replay",
        counters=counters,
        failures=failures,
        full_supported_root_replay_passed=full_passed,
        forward_numerical_crossings_passed=forward_passed,
        separate_frozen_causal_delta_gate_passed=causal_passed,
        original_unchanged_root_gate_retained=True,
        native_repair_reference_pin=NATIVE_PIN,
        native_source_files=source_files,
        name_matrix=matrix,
        name_matrix_count=len(matrix),
        name_matrix_passed=matrix_passed,
        wrong_name_accepted_count=sum(
            r["accepted"] and not r["expected"] for r in matrix
        ),
        correct_name_accepted_count=sum(
            r["accepted"] and r["expected"] for r in matrix
        ),
        additional_faults=additional,
        additional_fault_count=len(additional),
        additional_faults_rejected=sum(r["rejected"] for r in additional),
        observations_file=rows_path.name,
        observations_sha256=hashlib.sha256(rows_path.read_bytes()).hexdigest(),
        original_private_receipt_fields_not_serialized=True,
        actual_private_fields_observed_on_replay=True,
        no_inference_of_unrecorded_private_fields=True,
        independent_astronomical_truth=False,
        physical_accuracy_certified=False,
        empirical_outcomes=0,
        new_independent_model_processes=0,
        goal_complete=False,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-roots", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--matrix-only", action="store_true")
    args = parser.parse_args()
    result = audit(args.frozen_roots, args.output, matrix_only=args.matrix_only)
    args.output.write_text(
        json.dumps(
            result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
        )
        + "\n"
    )
    print(
        {
            k: result[k]
            for k in [
                "mode",
                "counters",
                "full_supported_root_replay_passed",
                "forward_numerical_crossings_passed",
                "separate_frozen_causal_delta_gate_passed",
                "name_matrix_passed",
                "wrong_name_accepted_count",
                "additional_faults_rejected",
            ]
        }
    )
    raise SystemExit(
        0
        if result["forward_numerical_crossings_passed"]
        and result["separate_frozen_causal_delta_gate_passed"]
        and result["name_matrix_passed"]
        and result["additional_faults_rejected"] == 17
        else 1
    )
