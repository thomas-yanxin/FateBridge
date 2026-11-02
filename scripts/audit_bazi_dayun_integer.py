"""Keep first integer-age failures; compare exact UTC interval ceiling arithmetic."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import heapq
import json
import sys
import types
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fatebridge.core.almanac import (
    BAZI_MONTH_START_TERMS,
    get_bazi_year,
    get_solar_terms_for_year,
)
from fatebridge.core.timing import TimingAnalysis

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_dayun_integer_v1"
SOURCES = [
    "src/fatebridge/core/timing.py",
    "src/fatebridge/core/almanac.py",
    "src/fatebridge/core/calendar.py",
    "src/fatebridge/core/solar_model_policy.py",
    "src/fatebridge/core/solar_term_runtime.py",
]
AGE_US = 3 * 86400 * 1_000_000


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(path: Path) -> Any:
    raw = path.read_bytes()
    if digest(path) != Path(str(path) + ".sha256").read_text().strip():
        raise ValueError("Frozen first source, label or gate changed")
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def exact_age_ceiling(birth: datetime, boundary: datetime) -> int:
    delta = abs(boundary.astimezone(timezone.utc) - birth.astimezone(timezone.utc))
    micros = (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
    return max(1, (micros + AGE_US - 1) // AGE_US)


def selected_values(details: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in details.items() if k != "reference_term"}


def instant(term: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(term["datetime_with_offset"]).astimezone(timezone.utc)


def legacy() -> Any:
    before = frozen(FIXTURE / "before-source.json.gz")
    name = "_frozen_pre_integer_dayun"
    module = types.ModuleType(name)
    module.__package__ = "fatebridge.core"
    sys.modules[name] = module
    exec(
        compile(
            before["src/fatebridge/core/timing.py"], "pre_integer_timing.py", "exec"
        ),
        module.__dict__,
    )
    return module.TimingAnalysis


def write_summary(path: Path, value: Any) -> None:
    raw = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    with path.open("xb") as f:
        f.write(gzip.compress(raw, mtime=0) if path.suffix == ".gz" else raw)
    Path(str(path) + ".sha256").write_text(digest(path) + "\n")


def collect_first(path: Path) -> dict[str, Any]:
    protocol = frozen(FIXTURE / "protocol.json")
    before = frozen(FIXTURE / "before-source.json.gz")
    if (ROOT / "src/fatebridge/core/timing.py").read_text() != before[
        "src/fatebridge/core/timing.py"
    ]:
        raise ValueError("First source already changed")
    fingerprints = {n: digest(ROOT / n) for n in SOURCES}
    counts: Counter[str] = Counter()
    refs = {}
    unique = set()
    examples: list[dict[str, Any]] = []
    with path.open("xb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as out:
        for zone in protocol["cohort"]["zones"]:
            for year in range(1900, 2101):
                terms = [
                    t
                    for t in get_solar_terms_for_year(year, zone)
                    if t.name in BAZI_MONTH_START_TERMS
                ]
                if len(terms) != 12:
                    raise ValueError("Missing a declared jie")
                for term in terms:
                    for direction in ("forward", "reverse"):
                        for integer in protocol["cohort"]["nominal_age_integers"]:
                            for epsilon in protocol["cohort"]["delta_seconds"]:
                                dt = timedelta(days=integer * 3, seconds=epsilon)
                                birth = (
                                    (term.moment.astimezone(timezone.utc) - dt)
                                    if direction == "forward"
                                    else (term.moment.astimezone(timezone.utc) + dt)
                                ).astimezone(term.moment.tzinfo)
                                row = {
                                    "zone": zone,
                                    "target_term_year": year,
                                    "target_term_name": term.name,
                                    "direction": direction,
                                    "integer": integer,
                                    "epsilon_seconds": epsilon,
                                    "birth_at": birth.isoformat(),
                                    "birth_utc": birth.astimezone(
                                        timezone.utc
                                    ).isoformat(),
                                }
                                counts["candidate_rows"] += 1
                                if not 1900 <= birth.year <= 2100:
                                    row.update(
                                        status="outside_public_birth_year_range",
                                        expected_integer=None,
                                    )
                                    counts["outside_public_birth_year_range"] += 1
                                else:
                                    yang = get_bazi_year(birth, zone) % 2 == 0
                                    gender = (
                                        "男"
                                        if ((direction == "forward") == yang)
                                        else "女"
                                    )
                                    details = (
                                        TimingAnalysis.calculate_dayun_start_details(
                                            birth, gender, zone
                                        )
                                    )
                                    reference = details["reference_term"]
                                    ref_id = hashlib.sha256(
                                        json.dumps(
                                            reference,
                                            ensure_ascii=False,
                                            sort_keys=True,
                                            separators=(",", ":"),
                                        ).encode()
                                    ).hexdigest()
                                    refs[ref_id] = reference
                                    boundary = instant(reference)
                                    expected = exact_age_ceiling(birth, boundary)
                                    row.update(
                                        status="computed",
                                        gender=gender,
                                        reference_id=ref_id,
                                        values=selected_values(details),
                                        expected_integer=expected,
                                        target_is_selected_reference=boundary
                                        == term.moment.astimezone(timezone.utc),
                                    )
                                    counts["computed_rows"] += 1
                                    counts["old_integer_failures"] += (
                                        details["start_age_rounded"] != expected
                                    )
                                    counts["requested_target_not_adjacent"] += not row[
                                        "target_is_selected_reference"
                                    ]
                                    unique.add((row["birth_utc"], gender))
                                    if (
                                        details["start_age_rounded"] != expected
                                        and len(examples) < 12
                                    ):
                                        examples.append(row)
                                out.write(
                                    (
                                        json.dumps(
                                            row,
                                            ensure_ascii=False,
                                            separators=(",", ":"),
                                        )
                                        + "\n"
                                    ).encode()
                                )
                print(
                    json.dumps(
                        {
                            "phase": "first",
                            "zone": zone,
                            "year": year,
                            "computed": counts["computed_rows"],
                        }
                    ),
                    flush=True,
                )
    Path(str(path) + ".sha256").write_text(digest(path) + "\n")
    write_summary(FIXTURE / "reference-terms-first.json.gz", refs)
    result = {
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "runner_sha256": digest(Path(__file__)),
        "source_fingerprints_before": fingerprints,
        "source_fingerprints_after": {n: digest(ROOT / n) for n in SOURCES},
        "cohort_sha256": digest(path),
        "counts": dict(counts),
        "distinct_birth_instants_and_gender": len(unique),
        "first_failure_examples": examples,
        "scope": "Exact arithmetic against the same supplied physical boundary; not independent astronomical, classical force or real prediction validation. Repeated zones/instants retained.",
    }
    if counts["candidate_rows"] != 2 * 201 * 12 * 2 * 10 * 3:
        raise ValueError("Declared cohort omitted rows")
    write_summary(FIXTURE / "cohort-first-summary.json", result)
    return result


def verify_current(
    path: Path, first: Path, shard_index: int = 0, shard_count: int = 1
) -> dict[str, Any]:
    if not 1 <= shard_count <= 16 or not 0 <= shard_index < shard_count:
        raise ValueError("Invalid fixed row-index shard")
    protocol = frozen(FIXTURE / "protocol.json")
    frozen(FIXTURE / "cohort-first-summary.json")
    if digest(first) != Path(str(first) + ".sha256").read_text().strip():
        raise ValueError("First cohort changed")
    for n, h in protocol["preserved_references_sha256"].items():
        if digest(ROOT / n) != h:
            raise ValueError("Original source, first failure or gate changed")
    old = legacy()
    loaded_file = sys.modules[TimingAnalysis.__module__].__file__
    if loaded_file is None:
        raise ValueError("Loaded timing source is unavailable")
    counts: Counter[str] = Counter()
    fingerprints = {n: digest(ROOT / n) for n in SOURCES}
    first_drift: list[dict[str, Any]] = []
    refs: dict[str, Any] = {}
    trace_path = Path(str(path) + ".rows.jsonl.gz")
    refs_path = Path(str(path) + ".references.json.gz")
    with (
        gzip.open(first, "rt") as source,
        trace_path.open("xb") as raw,
        gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as trace,
    ):
        for row_index, line in enumerate(source):
            row = json.loads(line)
            counts["all_rows_observed"] += 1
            if row_index % shard_count != shard_index:
                continue
            counts["all_rows"] += 1
            if row["status"] != "computed":
                counts["outside_public_birth_year_range"] += 1
                trace.write(
                    (
                        json.dumps({"row_index": row_index, "status": row["status"]})
                        + "\n"
                    ).encode()
                )
                continue
            birth = datetime.fromisoformat(row["birth_at"])
            a = old.calculate_dayun_start_details(birth, row["gender"], row["zone"])
            b = TimingAnalysis.calculate_dayun_start_details(
                birth, row["gender"], row["zone"]
            )
            expected = exact_age_ceiling(birth, instant(b["reference_term"]))
            ref_id = hashlib.sha256(
                json.dumps(
                    b["reference_term"],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
            refs[ref_id] = b["reference_term"]
            evidence = {
                "row_index": row_index,
                "status": "computed",
                "old_values": selected_values(a),
                "current_values": selected_values(b),
                "reference_id": ref_id,
                "expected_integer": expected,
                "old_and_current_reference_identical": a["reference_term"]
                == b["reference_term"],
            }
            trace.write(
                (
                    json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))
                    + "\n"
                ).encode()
            )
            unchanged = {k: v for k, v in a.items() if k != "start_age_rounded"} == {
                k: v for k, v in b.items() if k != "start_age_rounded"
            }
            if b["start_age_rounded"] != expected or not unchanged:
                failure = {
                    "first_row": row,
                    "comparison": evidence,
                    "old_full": a,
                    "current_full": b,
                    "unrelated_details_identical": unchanged,
                }
                write_summary(Path(str(path) + ".first-failure.json"), failure)
                raise ValueError(
                    "Current arithmetic or unrelated-detail gate failed; exact first row retained"
                )
            counts["computed_rows"] += 1
            counts["frozen_old_failures_in_same_current_runtime"] += (
                a["start_age_rounded"] != expected
            )
            counts["corrected_integer_values"] += (
                a["start_age_rounded"] != b["start_age_rounded"]
            )
            counts["current_failures"] += b["start_age_rounded"] != expected
            if selected_values(a) != row["values"]:
                counts["initial_to_current_other_runtime_differences"] += 1
                if len(first_drift) < 12:
                    first_drift.append(
                        {
                            "birth_at": row["birth_at"],
                            "zone": row["zone"],
                            "old_initial": row["values"],
                            "frozen_old_with_current_helpers": selected_values(a),
                        }
                    )
            if counts["all_rows"] % 720 == 0:
                print(
                    json.dumps(
                        {
                            "phase": "verify",
                            "shard_index": shard_index,
                            "row_index": row_index,
                            "computed": counts["computed_rows"],
                        }
                    ),
                    flush=True,
                )
    Path(str(trace_path) + ".sha256").write_text(digest(trace_path) + "\n")
    write_summary(refs_path, refs)
    result = {
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "runner_sha256": digest(Path(__file__)),
        "first_cohort_sha256": digest(first),
        "counts": dict(counts),
        "shard_index": shard_index,
        "shard_count": shard_count,
        "trace": {"path": str(trace_path.resolve()), "sha256": digest(trace_path)},
        "references": {"path": str(refs_path.resolve()), "sha256": digest(refs_path)},
        "loaded_timing_module": {
            "path": str(Path(loaded_file).resolve()),
            "sha256": digest(Path(loaded_file)),
        },
        "source_fingerprints_before": fingerprints,
        "source_fingerprints_after": {n: digest(ROOT / n) for n in SOURCES},
        "initial_to_current_runtime_drift_examples": first_drift,
        "comparison_scope": "Frozen pre-fix timing function and current function share the same then-current calendar helpers/dependencies; not whole historical-runtime identity. Exact integer UTC intervals are the arithmetic oracle.",
        "new_numeric_component_repairs": 1,
        "new_classical_correct_cases_credited": 0,
        "original_nineteen_unresolved": 19,
        "new_model_executions": 0,
        "real_world_predictive_validity": "not_tested",
        "full_goal_complete": False,
        "overall_score": None,
    }
    write_summary(path, result)
    return result


def aggregate(path: Path, first: Path, summaries: list[Path]) -> dict[str, Any]:
    """Require the exact union of every original index; recheck stored arithmetic."""
    initial = frozen(FIXTURE / "cohort-first-summary.json")
    if digest(first) != initial["cohort_sha256"]:
        raise ValueError("Initial cohort changed")
    reports = [frozen(p) for p in summaries]
    if (
        not reports
        or {r["shard_count"] for r in reports} != {len(reports)}
        or {r["shard_index"] for r in reports} != set(range(len(reports)))
    ):
        raise ValueError("Missing or duplicate fixed shard")
    for r in reports:
        if (
            r["first_cohort_sha256"] != digest(first)
            or r["protocol_sha256"] != digest(FIXTURE / "protocol.json")
            or r["runner_sha256"] != digest(Path(__file__))
            or r["source_fingerprints_before"] != r["source_fingerprints_after"]
            or r["source_fingerprints_before"]
            != reports[0]["source_fingerprints_before"]
        ):
            raise ValueError("Incoherent source, runner or original gate")
    refs = {}
    trace_handles = []
    try:
        for r in reports:
            ref_path = Path(r["references"]["path"])
            trace_path = Path(r["trace"]["path"])
            if (
                digest(ref_path) != r["references"]["sha256"]
                or digest(trace_path) != r["trace"]["sha256"]
            ):
                raise ValueError("Shard evidence changed")
            refs.update(frozen(ref_path))
            trace_handles.append(gzip.open(trace_path, "rt"))
        merged = heapq.merge(
            *((json.loads(line) for line in handle) for handle in trace_handles),
            key=lambda row: row["row_index"],
        )
        counts: Counter[str] = Counter()
        with gzip.open(first, "rt") as source:
            for index, line in enumerate(source):
                original = json.loads(line)
                row = next(merged, None)
                if (
                    row is None
                    or row["row_index"] != index
                    or row["status"] != original["status"]
                ):
                    raise ValueError(
                        "Original index missing, duplicated or changed status"
                    )
                counts["all_rows"] += 1
                if row["status"] != "computed":
                    counts["outside_public_birth_year_range"] += 1
                    continue
                a, b = row["old_values"], row["current_values"]
                expected = exact_age_ceiling(
                    datetime.fromisoformat(original["birth_at"]),
                    instant(refs[row["reference_id"]]),
                )
                if (
                    row["expected_integer"] != expected
                    or b["start_age_rounded"] != expected
                    or not row["old_and_current_reference_identical"]
                    or {k: v for k, v in a.items() if k != "start_age_rounded"}
                    != {k: v for k, v in b.items() if k != "start_age_rounded"}
                ):
                    raise ValueError(
                        "Stored row does not pass unchanged full-detail/arithmetic gates"
                    )
                counts["computed_rows"] += 1
                counts["corrected_integer_values"] += (
                    a["start_age_rounded"] != b["start_age_rounded"]
                )
                counts["frozen_old_failures_in_same_current_runtime"] += (
                    a["start_age_rounded"] != expected
                )
                counts["current_failures"] += b["start_age_rounded"] != expected
                counts["initial_to_current_other_runtime_differences"] += (
                    a != original["values"]
                )
        if next(merged, None) is not None:
            raise ValueError("Unexpected extra row")
    finally:
        for handle in trace_handles:
            handle.close()
    if (
        counts["all_rows"] != initial["counts"]["candidate_rows"]
        or counts["computed_rows"] != initial["counts"]["computed_rows"]
        or counts["outside_public_birth_year_range"]
        != initial["counts"]["outside_public_birth_year_range"]
    ):
        raise ValueError("Original fixed cohort coverage changed")
    for name, count in counts.items():
        if count != sum(r["counts"].get(name, 0) for r in reports):
            raise ValueError("Trace and terminal summary counts differ")
    result = {
        "counts": dict(counts),
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "runner_sha256": digest(Path(__file__)),
        "first_cohort_sha256": digest(first),
        "shards": [{"path": str(p.resolve()), "sha256": digest(p)} for p in summaries],
        "source_fingerprints": reports[0]["source_fingerprints_before"],
        "scope": "All original row indices, fixed source, same-runtime old/new full start details; deduplicated full references and both complete non-reference scalar mappings retained. Not independent astronomy, source-strength or reality validation.",
        "original_nineteen_unresolved": 19,
        "new_classical_correct_cases_credited": 0,
        "new_model_executions": 0,
        "real_world_predictive_validity": "not_tested",
        "full_goal_complete": False,
        "overall_score": None,
    }
    write_summary(path, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--collect-first", action="store_true")
    parser.add_argument("--first", type=Path, default=FIXTURE / "cohort-first.jsonl.gz")
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--aggregate", type=Path, nargs="+")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Preserve first outputs; choose a new path")
    if args.collect_first:
        result = collect_first(args.output)
    elif args.aggregate:
        result = aggregate(args.output, args.first, args.aggregate)
    else:
        result = verify_current(
            args.output, args.first, args.shard_index, args.shard_count
        )
    print(json.dumps({"summary_counts": result["counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
