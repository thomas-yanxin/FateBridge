"""Freeze neighbour epochs by source geometry; reference them independently.

Candidate outputs never select epochs or reference quality. The old fixed
finite-difference qualification is retained beside exact source enclosures.
"""

import argparse
import hashlib
import json
import struct
import sys
from decimal import Decimal as N
from decimal import localcontext
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice.astrodice_apparent_source_reference import (
    Reader as DecimalReader,
)
from scripts.astrodice.astrodice_apparent_source_reference import sample
from scripts.astrodice.astrodice_clock_interval import I, Reader, apparent
from scripts.astrodice.select_astrodice_source_boundaries import geometry


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_source(fixture):
    files = json.loads((fixture / "source-files.json").read_text())["source_files"]
    for name, expected in files.items():
        if digest(fixture / name) != expected:
            raise ValueError("External source records changed: " + name)


def forbid_candidate():
    if any(
        n == "swisseph" or n == "fatebridge" or n.startswith("fatebridge.")
        for n in sys.modules
    ):
        raise ValueError("Independent selector/reference imported candidate")


def select(run, fixture, output):
    check_source(fixture)
    plan = json.loads((run / "plan-before-geometry.json").read_text())
    base = json.loads((fixture / "geometric-reference.json").read_text())["rows"]
    cohorts = {}
    roots = []
    with localcontext() as context:
        context.prec = plan["source_decimal_precision"]
        for cohort, declarations in plan["cohorts"].items():
            cases = []
            for declaration in declarations:
                window = declaration["window_index"]
                reader = DecimalReader(fixture, window)
                epoch = N.from_float(base[window]["native_numeric_argument"])
                target = N.from_float(float(declaration["impact_knot"]))
                previous = None
                brackets = []
                for seconds in range(
                    -plan["root_search_radius_seconds"],
                    plan["root_search_radius_seconds"] + 1,
                    plan["scan_step_seconds"],
                ):
                    impact, background = geometry(
                        reader, declaration["body"], epoch + N(seconds) / 86400
                    )
                    point = (N(seconds), impact - target)
                    if previous is not None and previous[1] * point[1] < 0:
                        brackets.append((previous, point))
                    previous = point
                if len(brackets) != 2:
                    raise ValueError("Planned two crossings unavailable")
                for crossing, (left, right) in enumerate(brackets):
                    lo, hi = left[0], right[0]
                    flo = left[1]
                    for _ in range(100):
                        mid = (lo + hi) / 2
                        impact, background = geometry(
                            reader, declaration["body"], epoch + mid / 86400
                        )
                        if not background:
                            raise ValueError("Crossing is not behind solar disc")
                        value = impact - target
                        if flo * value <= 0:
                            hi = mid
                        else:
                            lo, flo = mid, value
                        if hi - lo <= N(plan["root_bracket_width_seconds"]):
                            break
                    if hi - lo > N(plan["root_bracket_width_seconds"]):
                        raise ValueError("Root bracket did not converge")
                    rounded = float(epoch + (lo + hi) / 2 / 86400)
                    word = struct.unpack(">Q", struct.pack(">d", rounded))[0]
                    roots.append(
                        {
                            **declaration,
                            "cohort": cohort,
                            "crossing": crossing,
                            "base_numeric_epoch": float(epoch),
                            "offset_lower_seconds": str(lo),
                            "offset_upper_seconds": str(hi),
                            "rounded_root_hex": rounded.hex(),
                        }
                    )
                    for offset in plan["binary64_neighbours"]:
                        value = struct.unpack(">d", struct.pack(">Q", word + offset))[0]
                        cases.append(
                            {
                                "id": f"{cohort}-{window}-{crossing}-{offset:+d}",
                                "cohort": cohort,
                                "body": declaration["body"],
                                "window_index": window,
                                "impact_knot": declaration["impact_knot"],
                                "crossing": crossing,
                                "word_offset": offset,
                                "native_numeric_argument": value,
                                "native_argument_hex": value.hex(),
                                "role": "first_adjacent_source_derivative_condition",
                                "time_contract": "Canonical binary64 native argument; nominal TDB under native TT approximation, not exact physical TT acceptance.",
                            }
                        )
            cohorts[cohort] = cases
    forbid_candidate()
    result = {
        "plan_sha256": digest(run / "plan-before-geometry.json"),
        "cohorts": cohorts,
        "roots": roots,
        "candidate_or_apparent_residual_used": False,
        "full_goal_complete": False,
    }
    with output.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    return result


def exact_reference(run, fixture, cohort, output):
    check_source(fixture)
    selection = json.loads((run / "selection-first.json").read_text())
    profile_path = (
        Path(__file__).resolve().parents[2]
        / "tests/data/astrodice/reference_sets/fixture-apparent-source-v1/source-solar-profile.json"
    )
    if (
        digest(profile_path)
        != "05523a9aa716373cd16ea400ad93182fdd672ac18e93618fb5eb6bd476adbc83"
    ):
        raise ValueError("Source solar profile changed")
    profile = json.loads(profile_path.read_text())["radius_mass_pairs"]
    old_protocol = json.loads((run / "old-reference-policy.json").read_text())
    rows = []
    with localcontext() as context:
        context.prec = 100
        for case in selection["cohorts"][cohort]:
            try:
                epoch = Q(case["native_numeric_argument"])
                value, cells = apparent(
                    Reader(fixture, case["window_index"]),
                    case["body"],
                    I(epoch),
                    profile,
                )
                precise = N(epoch.numerator) / N(epoch.denominator)
                point = sample(
                    DecimalReader(fixture, case["window_index"]),
                    case["body"],
                    precise,
                    profile,
                    precision=100,
                )
                for kind, key in [("v", "direction_icrf"), ("d", "derivative_per_day")]:
                    for box, scalar in zip(value, point[key]):
                        if not getattr(box, kind).contains(N(scalar)):
                            raise ValueError(
                                "Independent 100-digit reference outside interval"
                            )
                # The historical FD method takes calendar labels. Retain its
                # exact same steps/cell tests at this canonical numeric epoch.
                import scripts.astrodice.gen_astrodice_apparent_source_reference as old
                from scripts.astrodice.gen_astrodice_apparent_source_reference import (
                    _rate_reference,
                )

                original = old.calendar_jd_tdb
                try:
                    old.calendar_jd_tdb = lambda label: epoch
                    old_result = _rate_reference(
                        {**case, "date_tdb": "canonical-native-argument"},
                        fixture,
                        profile,
                        old_protocol,
                    )
                except Exception as error:
                    old_result = {
                        "status": "reference_quality_unresolved",
                        "error_type": type(error).__name__,
                        "message": str(error),
                    }
                finally:
                    old.calendar_jd_tdb = original
                row = {
                    **case,
                    "status": "exact_source_interval_qualified",
                    "direction_icrf_intervals": [a.v.record() for a in value],
                    "derivative_per_TDB_day_intervals": [a.d.record() for a in value],
                    "source_cells": cells,
                    "independent_point": point,
                    "old_fixed_FD_result": old_result,
                    "candidate_accuracy_pass": False,
                }
            except Exception as error:
                row = {
                    **case,
                    "status": "source_reference_unqualified",
                    "error_type": type(error).__name__,
                    "message": str(error),
                }
            rows.append(row)
            print(case["id"], row["status"], flush=True)
    forbid_candidate()
    result = {
        "method_id": "exact_dyadic_source_derivative_at_neighbouring_native_epochs_v1",
        "selection_sha256": digest(run / "selection-first.json"),
        "cohort": cohort,
        "rows": rows,
        "full_goal_complete": False,
        "original_Horizons_results_regraded": False,
        "exit_code": (
            2
            if any(r["status"] != "exact_source_interval_qualified" for r in rows)
            else 0
        ),
    }
    with output.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=["select", "reference"])
    for n in ["run", "fixture", "output"]:
        p.add_argument("--" + n, type=Path, required=True)
    p.add_argument("--cohort", choices=["A", "B"])
    a = p.parse_args()
    r = (
        select(a.run, a.fixture, a.output)
        if a.mode == "select"
        else exact_reference(a.run, a.fixture, a.cohort, a.output)
    )
    raise SystemExit(r.get("exit_code", 0))
