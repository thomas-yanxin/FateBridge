"""Recheck the full admitted DE440 year-grid range in Ren consumers.

Existing independent TT references and all prechange source refusals remain
visible. Same-kernel regression is not a civil clock or physical accuracy proof.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_extended_source_v1"
PIN = "f1578a034f9e64887e6a3602c3c881031a16b8aa1634511b15eea5917a6b9ff2"
BEFORE_TERMS_PIN = "dbf7250906f58182cfc06ebbeaeb1e241f3fef15fa8217f3c0c2671a50038320"
BEFORE_BUSINESS_PIN = "a81c09ebec66f8f2c96ece5d078759f9f10d9b1045e4d7da09b1f7b7c4dd6e01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(folder: Path = CORPUS) -> dict[str, Any]:
    if sha(folder / "freeze.json") != PIN:
        raise ValueError("Frozen extended-source reference identity changed")
    manifest = json.loads((folder / "freeze.json").read_text())
    names = {
        "independent-tt.json",
        "independent-protocol.json",
        "boundary-cases.json",
        "protocol.json",
    }
    if set(manifest) != names or {p.name for p in folder.iterdir()} != names | {
        "freeze.json"
    }:
        raise ValueError("Complete extended-source inventory required")
    if any(sha(folder / n) != h for n, h in manifest.items()):
        raise ValueError("Frozen extended-source bytes changed")
    full = json.loads((folder / "independent-tt.json").read_text())
    protocol = json.loads((folder / "protocol.json").read_text())
    if full["production_imported"] is not False or full["protocol_sha256"] != sha(
        folder / "independent-protocol.json"
    ):
        raise ValueError("Independent TT provenance changed")
    rows = full["rows"]
    keys = {(r["year"], r["index"]) for r in rows}
    if len(rows) != 14904 or keys != {
        (y, i) for y in range(1684, 2305) for i in range(24)
    }:
        raise ValueError("Original independent TT denominator changed")
    boundaries = json.loads((folder / "boundary-cases.json").read_text())["cases"]
    if len(boundaries) != 21:
        raise ValueError("Original21 boundary cases required")
    return dict(protocol=protocol, rows=rows, boundaries=boundaries)


def pack(term: Any) -> dict[str, Any]:
    value = asdict(term)
    value["moment"] = term.moment.isoformat()
    value["ephemeris_retflags"] = list(term.ephemeris_retflags)
    return value


def audit(before_dir: Path, observations: Path) -> dict[str, Any]:
    ref = reference()
    if (
        sha(before_dir / "before-terms.jsonl.gz") != BEFORE_TERMS_PIN
        or sha(before_dir / "before-business.json.gz") != BEFORE_BUSINESS_PIN
    ):
        raise ValueError(
            "Prechange complete range or business baseline identity changed"
        )
    with gzip.open(before_dir / "before-terms.jsonl.gz", "rt", encoding="utf-8") as f:
        before = [json.loads(line) for line in f]
    keys = {(r["year"], r["index"]) for r in before}
    expected = {(y, i) for y in range(1700, 2301) for i in range(24)}
    if len(before) != 14424 or keys != expected:
        raise ValueError("Complete14424 consumer events required")
    from fatebridge.application.execution import validate_output
    from fatebridge.core.almanac import get_solar_terms_for_year
    from fatebridge.core.metaphysics.ren_calendar import require_ren_solar_term
    from fatebridge.services.tool_catalog import CATALOG

    independent = {(r["year"], r["index"]): r for r in ref["rows"]}
    counts: Counter[str] = Counter()
    failures = []
    maximum = 0.0
    models: Counter[str] = Counter()
    with gzip.open(observations, "xt", encoding="utf-8") as stream:
        for row in before:
            key = (row["year"], row["index"])
            counts["events"] += 1
            counts["before_accepted" if row["ren_accepted"] else "before_rejected"] += 1
            try:
                term = get_solar_terms_for_year(row["year"], "UTC")[row["index"]]
                require_ren_solar_term(term)
                actual = pack(term)
                seconds = (
                    term.solar_model_details["selected_crossing_jd_tt"]
                    - independent[key]["jd_tt"]
                ) * 86400
                maximum = max(maximum, abs(seconds))
                models[term.ephemeris_model] += 1
                if actual != row["term"]:
                    failures.append(
                        dict(
                            kind="prechange_term_changed",
                            key=key,
                            before=row["term"],
                            after=actual,
                        )
                    )
                if abs(seconds) > ref["protocol"]["tt_tolerance_seconds"]:
                    failures.append(
                        dict(kind="independent_tt", key=key, seconds=seconds)
                    )
                expected_model = (
                    "fatebridge_de440_solar_v1"
                    if 1800 <= row["year"] <= 2200
                    else "fatebridge_de440_solar_extended_v1"
                )
                if term.ephemeris_model != expected_model:
                    failures.append(
                        dict(
                            kind="model",
                            key=key,
                            actual=term.ephemeris_model,
                            expected=expected_model,
                        )
                    )
                counts["after_accepted"] += 1
                stream.write(
                    json.dumps(
                        dict(
                            year=row["year"],
                            index=row["index"],
                            term=actual,
                            seconds_tt=seconds,
                            accepted=True,
                        ),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
            except Exception as error:
                counts["after_rejected"] += 1
                item = dict(
                    kind="source_error",
                    key=key,
                    error_type=type(error).__name__,
                    error=str(error),
                )
                failures.append(item)
                stream.write(json.dumps(item, ensure_ascii=False) + "\n")
            if row["index"] == 23 and row["year"] % 50 == 0:
                print(
                    json.dumps(dict(year=row["year"], counts=dict(counts))), flush=True
                )
    specs = {s.key: s for s in CATALOG}
    boundaries = []
    for row in ref["boundaries"]:
        value = row["payload"]
        wall = value["date"].split("-") + value["time"].split(":")
        y, m, d, h, minute, second = map(int, wall)
        payload = dict(
            analysis_year=y,
            analysis_month=m,
            analysis_day=d,
            analysis_hour=h,
            analysis_minute=minute,
            analysis_second=second,
            analysis_timezone=value["zone"],
            use_true_solar_time=False,
            is_diurnal=True,
        )
        for key in ref["protocol"]["boundary_tools"]:
            spec = specs[key]
            request = spec.request_model.model_validate(
                {**payload, **({"di_fen": "酉"} if key == "jinkou" else {})}
            )
            fn, args, kw = spec.bind(request)
            result = fn(*args, **kw)
            validate_output(spec, result)
            matched = (
                result["analysis_context"]["current_jieqi"]
                == row["expected_previous_term"]
                and result["four_pillars"]["month"]["branch"]
                == row["expected_month_branch"]
            )
            boundaries.append(
                dict(
                    case=row["id"],
                    tool=key,
                    matched=matched,
                    current_term=result["analysis_context"]["current_jieqi"],
                    month_branch=result["four_pillars"]["month"]["branch"],
                )
            )
    with gzip.open(before_dir / "before-business.json.gz", "rt", encoding="utf-8") as f:
        business = json.load(f)
    if [r["key"] for r in business] != ["liureng_gods", "liureng_runyear", "jinkou"]:
        raise ValueError("Complete3 original businesses required")
    preserved = []
    for row in business:
        spec = specs[row["key"]]
        fn, args, kw = spec.bind(spec.request_model.model_validate(row["input"]))
        actual = {k: v for k, v in fn(*args, **kw).items() if k != "run_metadata"}
        preserved.append(dict(tool=row["key"], unchanged=actual == row["payload"]))
    return dict(
        counts=dict(counts),
        model_counts=dict(models),
        maximum_independent_tt_seconds=maximum,
        failures=failures,
        boundaries=boundaries,
        business_preservation=preserved,
        checks_passed=not failures
        and all(r["matched"] for r in boundaries)
        and all(r["unchanged"] for r in preserved),
        observations_sha256=sha(observations),
        reference_pin=PIN,
        before_terms_pin=BEFORE_TERMS_PIN,
        original_pmo_hko_and_classical_gates="not_regraded_and_not_erased",
        physical_clock_or_full_domain_certification=False,
        new_model_processes=0,
        goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.observations.exists():
        parser.error("Refusing to overwrite retained results")
    result = audit(args.before_dir, args.observations)
    with args.output.open("x") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "counts",
                    "maximum_independent_tt_seconds",
                    "checks_passed",
                    "goal_complete",
                ]
            }
        )
    )
    return 0 if result["checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
