"""Stream all registered multi-zone/direction future-clock controls on a frozen runtime."""

import argparse
import gzip
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_dayun_future_clocks_v2"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--reference", type=Path, default=FIXTURE / "reference.jsonl.gz"
    )
    parser.add_argument(
        "--reference-summary", type=Path, default=FIXTURE / "reference-summary.json"
    )
    args = parser.parse_args()
    args.output = args.output.resolve()
    records = args.output.with_suffix(".records.jsonl.gz")
    temporary_records = records.with_suffix(".partial")
    assert (
        not args.output.exists()
        and not records.exists()
        and not temporary_records.exists()
    )
    assert args.output.parent.is_dir()
    manifest = json.loads(args.source_manifest.read_text())
    source = Path(manifest["source"]).resolve()
    sys.path.insert(0, str(source / "src"))
    empty = tempfile.TemporaryDirectory(prefix="bazi-future-gap-audit-")
    os.environ["SE_EPHE_PATH"] = empty.name
    os.environ["FATEBRIDGE_SOLAR_TERM_MODEL"] = "auto"
    os.environ.pop("FATEBRIDGE_SOLAR_SPK_FILE", None)
    os.environ.pop("FATEBRIDGE_JPL_FILE", None)
    from fatebridge.core.timing import TimingAnalysis
    from fatebridge.services.timing_uncertainty import analyze_birth_time_range
    from fatebridge.utils.birth_input import PersonInfo

    reference_path = args.reference.resolve()
    assert (
        sha(reference_path) == reference_path.with_suffix(".sha256").read_text().strip()
    )
    assert (
        sha(args.reference_summary)
        == args.reference_summary.with_suffix(".sha256").read_text().strip()
    )
    reference = json.loads(args.reference_summary.read_text())
    assert sha(reference_path) == reference["reference_sha256"]

    def rows():
        with gzip.open(reference_path, "rt") as stream:
            header = json.loads(next(stream))
            assert header["record_type"] == "header"
            assert header["collector_sha256"] == reference["collector_sha256"]
            count = 0
            for line in stream:
                row = json.loads(line)
                if row["record_type"] == "footer":
                    assert row["row_count"] == count == reference["rows"]
                    assert row["counts"] == reference["counts"]
                    assert not stream.read()
                    return
                assert row["record_type"] == "control"
                count += 1
                yield row
            raise AssertionError("Missing source footer")

    counts, errors, gaps = Counter(), [], []
    with temporary_records.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as stream:
            for index, row in enumerate(rows()):
                record = {"id": row["id"], "source_status": row["status"]}
                if row["status"] != "resolved_source_control":
                    record.update(
                        adjudicated=False, unresolved_reason=row["unresolved_reason"]
                    )
                    counts["unresolved_source_controls"] += 1
                else:
                    record["adjudicated"] = True
                    counts["resolved_source_controls"] += 1
                    counts[
                        "source_minute_grid_already_has_all_declared_states"
                    ] += not row["missing_from_minute_grid"]
                    numerical, probes = [], []
                    try:
                        analysis = datetime.fromisoformat(row["analysis_at"])
                        for probe_index, probe in enumerate(
                            row["expected_grid"] + row["expected_witnesses"]
                        ):
                            birth = datetime.fromisoformat(probe["birth_utc"])
                            timeline = TimingAnalysis.calculate_dayun_timeline(
                                birth,
                                row["input"]["gender"],
                                ("甲", "子"),
                                row["input"]["birth_timezone"],
                            )
                            start = datetime.fromisoformat(
                                timeline["start_at"]
                            ).astimezone(timezone.utc)
                            expected = datetime.fromisoformat(probe["manual_start_at"])
                            state = "before_dayun" if analysis < start else "active"
                            safe = probe_index in {0, 1, 2, 3, 6}
                            term = timeline["start_details"]["reference_term"]
                            observation = {
                                "reference": probe,
                                "actual_start_at": start.isoformat(),
                                "actual_status": state,
                                "difference_seconds": (
                                    start - expected
                                ).total_seconds(),
                                "safe_distance_gate": safe,
                                "actual_consumed_reference_at": term[
                                    "datetime_with_offset"
                                ],
                                "actual_reference_provider": term[
                                    "resolution_provider"
                                ],
                                "actual_root_jd_tt": term.get(
                                    "solar_model_details", {}
                                ).get("selected_crossing_jd_tt"),
                                "actual_root_tt_parts": term.get(
                                    "solar_model_details", {}
                                ).get("selected_crossing_tt_parts"),
                                "actual_calendar_offset": timeline["calendar_offset"],
                                "actual_dst_policy": timeline["dst_policy"],
                            }
                            probes.append(observation)
                            mismatched = (
                                abs(observation["difference_seconds"]) > 0.1
                                or state != probe["expected_status"]
                            )
                            if mismatched and safe:
                                numerical.append(observation)
                            elif mismatched:
                                counts["near_inverse_boundary_probe_diagnostics"] += 1
                        person = PersonInfo(**row["input"])
                        original_input = person.model_dump()
                        result = analyze_birth_time_range(
                            person,
                            row["uncertainty_minutes"],
                            analysis_moment=analysis,
                        )
                        assert person.model_dump() == original_input
                        declared_inverse = datetime.fromisoformat(
                            row["inverse_ceil_utc"]
                        )
                        inverse_events = [
                            e
                            for e in result["dayun_event_analysis"]["events"]
                            if e["kind"] == "dayun_future_civil_gap_end"
                            and e["source"]["decade_boundary_index"] == "0"
                            and datetime.fromisoformat(e["source"]["future_gap_at_utc"])
                            == datetime.fromisoformat(row["gap"]["transition_utc"])
                        ]
                        matching_events = [
                            e
                            for e in inverse_events
                            if abs(
                                (
                                    datetime.fromisoformat(e["at_utc"])
                                    - declared_inverse
                                ).total_seconds()
                            )
                            <= 0.1
                        ]
                        record["declared_inverse_events"] = inverse_events
                        record["inverse_event_displacements_seconds"] = [
                            (
                                datetime.fromisoformat(e["at_utc"]) - declared_inverse
                            ).total_seconds()
                            for e in inverse_events
                        ]
                        if not matching_events:
                            counts["ranges_without_declared_inverse_event"] += 1
                            gaps.append(
                                {
                                    "id": row["id"],
                                    "missing_declared_inverse_event": True,
                                }
                            )
                        else:
                            counts["ranges_with_declared_inverse_event"] += 1
                        counts["ranges_with_application_unresolved_cells"] += bool(
                            result["dayun_event_analysis"]["unresolved_cells"]
                        )
                        states = sorted(
                            {p["status"] for p in result["current_dayun_candidates"]}
                        )
                        missing = sorted(set(row["expected_statuses"]) - set(states))
                        extra = sorted(set(states) - set(row["expected_statuses"]))
                        if missing:
                            counts["ranges_missing_known_current_state"] += 1
                            gaps.append({"id": row["id"], "missing_statuses": missing})
                        else:
                            counts["ranges_with_all_declared_current_states"] += 1
                        if extra:
                            numerical.append({"unexpected_current_states": extra})
                        first = [
                            p
                            for p in result["dayun_boundary_ranges"]
                            if p["period"] == 1
                        ]
                        assert len(first) == 1
                        earliest = datetime.fromisoformat(
                            first[0]["earliest_start_at"]
                        ).astimezone(timezone.utc)
                        latest = datetime.fromisoformat(
                            first[0]["latest_start_at"]
                        ).astimezone(timezone.utc)
                        outside = [
                            p
                            for p in probes
                            if p["safe_distance_gate"]
                            and not earliest
                            <= datetime.fromisoformat(p["reference"]["manual_start_at"])
                            <= latest
                        ]
                        if outside:
                            counts[
                                "probe_envelopes_not_covering_safe_source_witnesses"
                            ] += 1
                        record.update(
                            actual_range=result,
                            actual_statuses=states,
                            missing_statuses=missing,
                            unexpected_statuses=extra,
                            safe_source_witnesses_outside_probe_envelope=outside,
                        )
                    except Exception as error:
                        numerical.append(
                            {"exception": type(error).__name__, "message": str(error)}
                        )
                    record.update(
                        timeline_probes=probes, numerical_mismatches=numerical
                    )
                    if numerical:
                        errors.append({"id": row["id"], "errors": numerical})
                counts["completed_rows"] += 1
                stream.write((json.dumps(record, ensure_ascii=False) + "\n").encode())
                if index % 100 == 0:
                    print(
                        json.dumps(
                            {
                                "completed": index + 1,
                                "total": reference["rows"],
                                "counts": dict(counts),
                                "safe_numerical_mismatch_rows": len(errors),
                            }
                        ),
                        flush=True,
                    )
    modules = {
        k: str(Path(v.__file__).resolve())
        for k, v in list(sys.modules.items())
        if k.startswith("fatebridge") and getattr(v, "__file__", None)
    }
    assert all(Path(p).is_relative_to(source / "src") for p in modules.values())
    drift = [n for n, h in manifest["files"].items() if sha(source / n) != h]
    temporary_records.rename(records)
    report = {
        "source_manifest_sha256": sha(args.source_manifest),
        "source_drift": drift,
        "reference_sha256": sha(reference_path),
        "reference_summary_sha256": sha(args.reference_summary),
        "application_protocol_sha256": sha(FIXTURE / "application-protocol.json"),
        "runner_sha256": sha(__file__),
        "registered_rows": reference["rows"],
        "counts": dict(counts),
        "numerical_mismatch_rows": errors,
        "capability_gaps": gaps,
        "records": (
            str(records.relative_to(ROOT))
            if records.is_relative_to(ROOT)
            else str(records)
        ),
        "records_sha256": sha(records),
        "module_origins": modules,
        "new_model_executions": 0,
        "new_independent_observation_credit": 0,
        "scope": "Complete registered fourzone/bothdirection initial gap-end cohort; unresolvedsource rows retained. Original per-probe consumedroots/offsets and actual inverse event evidence saved. All source minutegrids already contain knownstates, so no new state-repair credit. Standard compiled clock policy only, not all historical/physical/period/extrema/originaltext/reality proof.",
        "full_goal_complete": False,
        "overall_score": None,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    args.output.with_suffix(".sha256").write_text(sha(args.output) + "\n")
    records.with_suffix(".sha256").write_text(sha(records) + "\n")
    print(
        json.dumps(
            {
                "counts": dict(counts),
                "safe_numerical_mismatch_rows": len(errors),
                "capability_gaps": len(gaps),
                "source_drift": drift,
            }
        ),
        flush=True,
    )
    return int(bool(errors or gaps or drift))


if __name__ == "__main__":
    raise SystemExit(main())
