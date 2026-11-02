"""Full SPK boundary revalidation from an immutable captured runtime."""

import argparse
import bisect
import gzip
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_boundary_decisions_v1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Refusing to overwrite accepted SPK boundary evidence")
    snapshot = json.loads(args.source_manifest.read_text())
    source = Path(snapshot["source"]).resolve()
    for name, expected in snapshot["files"].items():
        if sha(source / name) != expected:
            raise ValueError("Immutable source snapshot changed")
    sys.path.insert(0, str(source / "src"))
    sys.path.insert(1, str(ROOT))
    from fatebridge.core import almanac, ephemeris_runtime
    from fatebridge.core.astro.time_scales import ephemeris_time
    from scripts.collect_bazi_boundary_probes import JIE_BRANCHES

    assert Path(almanac.__file__).resolve() == source / "src/fatebridge/core/almanac.py"
    loader = importlib.machinery.SourceFileLoader(
        "_original_bazi_observer", str(FIXTURE / "audit-first.py.txt")
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    observer = importlib.util.module_from_spec(spec)
    loader.exec_module(observer)
    protocol = json.loads((FIXTURE / "spk-experiment-protocol.json").read_text())
    os.environ["FATEBRIDGE_SOLAR_TERM_MODEL"] = "spk"
    os.environ["FATEBRIDGE_SOLAR_SPK_FILE"] = protocol["kernel_path"]
    os.environ.pop("FATEBRIDGE_JPL_FILE", None)
    empty = source / "empty-ephe"
    empty.mkdir(exist_ok=True)
    os.environ["SE_EPHE_PATH"] = str(empty)
    ephemeris_runtime.configure_ephemeris_path(str(empty))
    reference = ROOT / protocol["reference_path"]
    assert sha(reference) == protocol["reference_sha256"]
    probes = json.loads((FIXTURE / "probes.json").read_text())
    roots = json.loads(reference.read_text())["rows"]
    jie = [r for r in roots if r["name"] in JIE_BRANCHES]
    times = [r["jd_tt"] for r in jie]
    observed, root_rows = [], []
    for year in range(1899, 2102):
        terms = {t.name: t for t in almanac.get_solar_terms_for_year(year, "UTC")}
        for r in roots[(year - 1899) * 24 : (year - 1898) * 24]:
            term = terms[r["name"]]
            epoch = ephemeris_time(term.moment)
            difference = (epoch.jd_tt - r["jd_tt"]) * 86400
            root_rows.append(
                {
                    "year": year,
                    "name": r["name"],
                    "reference_tt": r["jd_tt"],
                    "actual_tt": epoch.jd_tt,
                    "actual_term": term.as_dict(),
                    "difference_seconds": difference,
                    "within_original_one_second_gate": abs(difference) <= 1,
                }
            )
        for probe in probes["rows"][(year - 1899) * 48 : (year - 1898) * 48]:
            row = observer.compare(probe, roots)
            i = bisect.bisect_right(times, row["actual_input_jd_tt"]) - 1
            expected = {
                "liuri_last_term": jie[i]["name"] if i >= 0 else None,
                "liuri_next_term": jie[i + 1]["name"] if i + 1 < len(jie) else None,
            }
            for key, value in expected.items():
                row["reference_expected_at_actual_input_tt"][key] = value
                row["matches"][key] = (
                    row["actual"][key] == value if value is not None else None
                )
            observed.append(row)
        if (year - 1899) % 25 == 0:
            print({"year": year, "probes": len(observed)}, flush=True)
    for name, expected in snapshot["files"].items():
        if sha(source / name) != expected:
            raise ValueError("Immutable source snapshot changed during audit")
    counts = {
        k: {
            "matched": sum(r["matches"][k] is True for r in observed),
            "mismatched": sum(r["matches"][k] is False for r in observed),
            "unknown_endpoint": sum(r["matches"][k] is None for r in observed),
        }
        for k in observed[0]["matches"]
    }
    result = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime_snapshot": str(source),
        "source_manifest_sha256": sha(args.source_manifest),
        "runner_sha256": sha(Path(__file__)),
        "reference_sha256": sha(reference),
        "probes_sha256": sha(FIXTURE / "probes.json"),
        "root_count": len(root_rows),
        "root_comparisons": root_rows,
        "original_one_second_gate_failures": sum(
            not r["within_original_one_second_gate"] for r in root_rows
        ),
        "maximum_absolute_root_difference_seconds": max(
            abs(r["difference_seconds"]) for r in root_rows
        ),
        "probe_count": len(observed),
        "comparisons": observed,
        "counts": counts,
        "wrong_probe_ids": [
            r["probe_id"]
            for r in observed
            if any(v is False for v in r["matches"].values())
        ],
        "prior_attempt": "docs/validation/bazi-spk-public-first-aborted-v1.json",
        "original_default_analytic_four_month_mismatches_and_native501_failures_retained": True,
        "source_selected": "explicit_spk_only_default_unchanged",
        "full_calendar_acceptance": False,
        "overall_score": None,
        "scope": "Actual frozen-runtime BaZiCalendar/year/month/liuyue/liuri states, all original reference roots and minute probes; correct12Jie window. Shared JPL data and declared civil-clock policy are not independent absolute UTC/physical certification.",
    }
    args.output.write_bytes(
        gzip.compress(
            (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode(), mtime=0
        )
    )
    args.output.with_suffix(".sha256").write_text(sha(args.output) + "\n")
    print(
        {
            k: result[k]
            for k in [
                "root_count",
                "original_one_second_gate_failures",
                "maximum_absolute_root_difference_seconds",
                "probe_count",
                "counts",
                "wrong_probe_ids",
            ]
        }
    )


if __name__ == "__main__":
    main()
