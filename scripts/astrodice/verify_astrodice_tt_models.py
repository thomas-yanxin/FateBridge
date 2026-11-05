"""Separate source-clock proof plus unmodified author C model replay.

The 1e-12 second C/interval arithmetic check is not an astronomical error bar.
It is never added to the comparison with the measured source-clock interval.
"""

import argparse
import ctypes
import hashlib
import json
import math
import re
import shutil
import subprocess
import tempfile
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice.verify_astrodice_earth_clock import raw_rows, vector_proof, wire

AUTHOR_SHA = "228bd7c7c1c88dda44c29a076f289c968f64d77a2dc389138b03ab5d1d442105"
ARITHMETIC_SECONDS = Q("1e-12")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class NativeModel:
    def __init__(self, raw):
        if hashlib.sha256(raw).hexdigest() != AUTHOR_SHA:
            raise ValueError("Independent author source changed")
        self.folder = tempfile.TemporaryDirectory(prefix="astrodice-author-clock-")
        root = Path(self.folder.name)
        (root / "dtdb.c").write_bytes(raw)
        (root / "erfa.h").write_text("#include <math.h>\n")
        macros = {
            "ERFA_D2PI": "6.283185307179586476925287",
            "ERFA_DD2R": "1.745329251994329576923691e-2",
            "ERFA_DJ00": "2451545.0",
            "ERFA_DJM": "365250.0",
        }
        if set(re.findall(rb"ERFA_[A-Z0-9]+", raw)) != {x.encode() for x in macros}:
            raise ValueError("Unexpected author constant dependency")
        (root / "erfam.h").write_text(
            "".join(f"#define {k} {v}\n" for k, v in macros.items())
        )
        compilers = [(shutil.which("cc"), [])]
        llvm = Path("/opt/homebrew/opt/llvm/bin/clang")
        sdk = Path("/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk")
        if llvm.is_file() and sdk.is_dir():
            compilers.append((str(llvm), ["-isysroot", str(sdk)]))
            linker = Path("/opt/homebrew/opt/lld/bin/ld64.lld")
            if linker.is_file():
                compilers.append(
                    (str(llvm), ["-isysroot", str(sdk), "-fuse-ld=" + str(linker)])
                )
        self.compilation_attempts = []
        for compiler, flags in compilers:
            if compiler is None:
                continue
            result = subprocess.run(
                [
                    compiler,
                    *flags,
                    "-shared",
                    "-fPIC",
                    "-O0",
                    str(root / "dtdb.c"),
                    "-lm",
                    "-o",
                    str(root / "clock.so"),
                ],
                capture_output=True,
                text=True,
            )
            self.compilation_attempts.append(
                {
                    "compiler": compiler,
                    "flags": flags,
                    "exit_code": result.returncode,
                    "stderr": result.stderr,
                }
            )
            if result.returncode == 0:
                break
        else:
            raise ValueError(
                "Author C compilation unavailable: " + str(self.compilation_attempts)
            )
        self.library = ctypes.CDLL(str(root / "clock.so"))
        self.call = self.library.eraDtdb
        self.call.argtypes = [ctypes.c_double] * 6
        self.call.restype = ctypes.c_double

    def offset(self, tt, model):
        delta = 0.0
        for _ in range(8):
            days = float(tt - 2451545 + Q(delta) / 86400)
            if model == "ERFA_Fairhead_geocentric":
                delta = self.call(2451545.0, days, 0, 0, 0, 0)
            elif model == "NAIF_LSK_periodic":
                m = 6.239996 + 1.99096871e-7 * (days * 86400)
                delta = 1.657e-3 * math.sin(m + 1.671e-2 * math.sin(m))
            else:
                raise ValueError("Independent unknown clock model")
        return Q(delta)

    def close(self):
        self.folder.cleanup()


def verify(run, cohort):
    plan = json.loads((run / "plan-before-queries.json").read_text())
    for name, h in plan["inputs_sha256"].items():
        if digest(run / name) != h:
            raise ValueError("Independent input seal changed: " + name)
    if plan["original_lines"] != {
        "position_arcsec": "0.02",
        "daily_rate_arcsec_per_day": "0.002",
        "reference_quality_arcsec_per_day": "0.002",
    }:
        raise ValueError("Original error line changed")
    if sorted(
        p["extra_binary64_ULPs"] for p in plan["numerical_tube_profiles"].values()
    ) != [0, 64]:
        raise ValueError("Original source tube changed")
    predictions = json.loads((run / "predictions-before-queries.json").read_text())
    saved = json.loads((run / (cohort + "-first-analysis.json")).read_text())
    if (
        saved["plan_sha256"] != digest(run / "plan-before-queries.json")
        or saved["cohort"] != cohort
    ):
        raise ValueError("Analysis identity changed")
    if (
        saved["physical_time_model_certified"]
        or saved["full_goal_complete"]
        or saved["new_candidate_holdouts"]
        or saved["production_acceptance_exit_code"] != 2
        or saved["retained_overall_numeric_gate_exit_code"] != 1
    ):
        raise ValueError("Unsupported acceptance promotion")
    expected = [q for q in plan["queries"] if q["cohort"] == cohort]
    if saved["new_TT_source_conditions"] != (5 if cohort == "B" else 0):
        raise ValueError("Source-condition count changed")
    if [r["id"] for r in saved["queries"]] != [q["id"] for q in expected]:
        raise ValueError("Query population changed")
    native = NativeModel((run / "authority/dtdb.c").read_bytes())
    endpoints = boxes = 0
    details = []
    try:
        for query, group in zip(expected, saved["queries"]):
            if any(group[k] != query[k] for k in ("body", "encoding")):
                raise ValueError("Source query metadata changed")
            raw, receipt = wire(run, query)
            if receipt["status"] != 200:
                raise ValueError("Unavailable source query")
            rows = [
                r
                for r in raw_rows(raw, query, query["cases"], plan)
                if r["role"] != "auxiliary_not_primary"
            ]
            if [r["case_id"] for r in rows] != [r["case_id"] for r in group["rows"]]:
                raise ValueError("Source row population changed")
            for original, record in zip(rows, group["rows"]):
                case = next(c for c in query["cases"] if c["id"] == record["case_id"])
                e, b = vector_proof(run, query["body"], case, original, record, plan)
                endpoints += e
                boxes += b
                for model in ("ERFA_Fairhead_geocentric", "NAIF_LSK_periodic"):
                    pred = predictions[case["id"]][model]
                    tt = Q(case["nominal_JD"])
                    a, b = map(Q, pred["predicted_JD_TDB"])
                    low, high = map(Q, pred["predicted_TDB_minus_TT_seconds"])
                    if not low <= (a - tt) * 86400 <= (b - tt) * 86400 <= high:
                        raise ValueError("TT/TDB labels conflated")
                    actual = native.offset(tt, model)
                    if (
                        b < a
                        or (b - a) * 86400 > Q("1e-40")
                        or not low - ARITHMETIC_SECONDS
                        <= actual
                        <= high + ARITHMETIC_SECONDS
                    ):
                        raise ValueError("Author C arithmetic replay differs")
                    scope = (
                        (
                            "documented_1950_2050_DE405_comparison"
                            if Q("2433282.5") <= tt <= Q("2469807.5")
                            else "outside_documented_accuracy_era"
                        )
                        if model.startswith("ERFA")
                        else "approximate_30_microsecond_description_no_uniform_era_bound"
                    )
                    if (
                        pred["model_accuracy_scope"] != scope
                        or pred["physical_model_error_certified"]
                    ):
                        raise ValueError("Model error scope promoted")
                    for profile, inv in record["profiles"].items():
                        result = record["models"][model][profile]
                        if inv["status"] != "bracketed":
                            expected_result = {
                                "status": "source_clock_unknown",
                                "qualified_not_refuted": False,
                            }
                        else:
                            c, d = map(Q, inv["effective_JD"])
                            overlap = a <= d and c <= b
                            expected_result = {
                                "status": "overlap" if overlap else "disjoint",
                                "prediction_minus_source_seconds": [
                                    str((a - d) * 86400),
                                    str((b - c) * 86400),
                                ],
                                "source_all_six_compatible": inv["all_six_compatible"],
                                "label_budget_pass": original[
                                    "original_label_budget_pass"
                                ],
                                "qualified_not_refuted": overlap
                                and inv["all_six_compatible"]
                                and original["original_label_budget_pass"],
                            }
                        if result != expected_result:
                            raise ValueError(
                                "Clock discrepancy or qualification changed"
                            )
                        details.append(
                            {
                                "query": query["id"],
                                "case": case["id"],
                                "model": model,
                                "profile": profile,
                                **result,
                            }
                        )
    finally:
        native.close()
    return {
        "cohort": cohort,
        "source_endpoint_checks": endpoints,
        "source_component_boxes": boxes,
        "comparisons": details,
        "arithmetic_replay_budget_seconds": str(ARITHMETIC_SECONDS),
        "native_compilation_attempts": native.compilation_attempts,
        "physical_time_model_certified": False,
        "candidate_acceptance": "not_tested",
        "full_goal_complete": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--cohort", choices=("A", "B"), required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    value = verify(args.run, args.cohort)
    with args.output.open("x") as f:
        json.dump(value, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
