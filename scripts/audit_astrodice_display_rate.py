"""Grade all actual complete tropical rates against the fixed named model."""

import argparse
import json
import math
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_clock_interval import I
from scripts.astrodice_display_frame import PLAN_SHA, load, pi_interval, sha
from scripts.verify_astrodice_display_reference import verify


def wire(value):
    lo, hi = value.bounds()
    return {"bounds": [str(lo), str(hi)], "lower": float(lo), "upper": float(hi)}


def audit(run, reference, proof, native_directory, seal_path, seal_sha):
    protocol = load(run)
    saved = json.loads(reference.read_text())
    split = saved["split"]
    independent = json.loads(proof.read_text())
    if independent != verify(run, reference):
        raise ValueError("Independent proof detached")
    if sha(seal_path) != seal_sha:
        raise ValueError("Candidate seal rebound")
    seal = json.loads(seal_path.read_text())
    expected = [
        f"{backend}-{i}.json"
        for i in range(len(protocol[split]))
        for backend in protocol["backends"]
    ]
    if sorted(p.name for p in native_directory.glob("*.json")) != sorted(expected):
        raise ValueError("Actual candidate population omitted or expanded")
    rows = []
    bindings = json.loads((run / "inputs-before-development.json").read_text())
    native_binary = {v for k, v in bindings.items() if k.endswith((".so", ".pyd"))}
    for backend in protocol["backends"]:
        for index, case in enumerate(protocol[split]):
            path = native_directory / f"{backend}-{index}.json"
            native = json.loads(path.read_text())
            if (
                native["protocol_sha256"] != PLAN_SHA
                or native["split"] != split
                or native["case_index"] != index
                or native["case"] != case
                or native["backend_requested"] != backend
                or native["candidate_seal_sha256"] != seal_sha
                or native["native_binary_sha256"] not in native_binary
            ):
                raise ValueError("Native input or binary identity rebound")
            if [r["body"] for r in native["rows"]] != case["bodies"]:
                raise ValueError("Actual target missing")
            for body, actual in zip(case["bodies"], native["rows"]):
                ref = next(
                    r
                    for r in saved["rows"]
                    if r["case_index"] == index and r["body"] == body
                )
                row = {
                    "case_index": index,
                    "label": case["label"],
                    "body": body,
                    "backend": backend,
                    "reference_status": ref["status"],
                    "candidate_status": actual["status"],
                    "raw_native_sha256": sha(path),
                    "qualified": False,
                }
                if ref["status"] != "ready" or actual["status"] != "ready":
                    row.update(
                        status="unavailable_retained",
                        reference_error=ref.get("error"),
                        candidate_error=actual.get("error"),
                    )
                    rows.append(row)
                    continue
                if Q(actual["native_numeric_jd"]) != Q(
                    ref["exact_binary64_numeric_jd"]
                ):
                    raise ValueError("Numeric time rebound")
                expected_model = "swieph" if backend == "swieph" else "jpl"
                bit = 2 if backend == "swieph" else 1
                physical_calls = [
                    c for c in actual["native_calls"] if c["args"][1] != -1
                ]
                if not physical_calls or any(
                    c["returned_flags"] & 7 != bit for c in physical_calls
                ):
                    raise ValueError("Returned physical backend differs")
                if actual["model"] != expected_model:
                    raise ValueError("Delivered model differs")
                trace = actual["trace"]
                if not trace["files"] or trace["has_unidentified_sources"]:
                    raise ValueError("Source trace incomplete")
                for file in trace["files"]:
                    p = (
                        Path("ephe") / file["filename"]
                        if backend == "swieph"
                        else Path(case["source"])
                        / "diagnostic-kernels"
                        / file["filename"]
                    )
                    if bindings[str(p)] != file["sha256"]:
                        raise ValueError("Actual file detached from frozen source")
                state = actual["state"]
                lon, lat = map(math.radians, (state["longitude"], state["latitude"]))
                u = [
                    math.cos(lat) * math.cos(lon),
                    math.cos(lat) * math.sin(lon),
                    math.sin(lat),
                ]
                direction = [I(*map(Q, x["value"])) for x in ref["displayed_direction"]]
                position = (
                    sum(
                        ((I(Q(a)) - b).square() for a, b in zip(u, direction)), I()
                    ).sqrt()
                    * 648000
                    / pi_interval()
                )
                reference_rate = I(*map(Q, ref["longitude_rate_arcsec_per_source_day"]))
                rate = I(Q(state["longitude_speed"]) * 3600) - reference_rate
                pos_pass = position.absolute_upper() <= Q(
                    protocol["position_line_arcsec"]
                )
                rate_pass = rate.absolute_upper() <= Q(
                    protocol["rate_line_arcsec_per_day"]
                )
                if body == "Moon":
                    policy = actual["metadata"]["lunar_light_time"][
                        "fixed_frame_source_derivative"
                    ]
                else:
                    policy = actual["metadata"]["complete_position_derivatives"][
                        body + ":tropical"
                    ]
                applied = policy["status"] == "applied"
                row.update(
                    status=(
                        "passed_declared_source_lines"
                        if pos_pass and rate_pass and applied
                        else "failed_declared_source_lines"
                    ),
                    qualified=pos_pass and rate_pass and applied,
                    position_pass=pos_pass,
                    rate_pass=rate_pass,
                    derivative_policy_applied=applied,
                    position_chord_error_arcsec=wire(position),
                    signed_complete_display_rate_error_arcsec_per_source_day=wire(rate),
                    final_displayed_longitude_speed_degrees_per_native_argument_day=state[
                        "longitude_speed"
                    ],
                )
                rows.append(row)
    return {
        "protocol_sha256": PLAN_SHA,
        "split": split,
        "candidate_phase": seal["phase"],
        "reference_sha256": sha(reference),
        "proof_sha256": sha(proof),
        "candidate_seal_sha256": seal_sha,
        "rows": rows,
        "position_line_arcsec": protocol["position_line_arcsec"],
        "rate_line_arcsec_per_day": protocol["rate_line_arcsec_per_day"],
        "scope": protocol["scope"],
        "old_gates": protocol["old_gates"],
        "physical_TT_equivalence_certified": False,
        "original_failure_records_regraded": False,
        "original_Horizons_model_equivalence_certified": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in [
        "run",
        "reference",
        "proof",
        "native-directory",
        "candidate-seal",
        "output",
    ]:
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--candidate-seal-sha", required=True)
    a = p.parse_args()
    value = audit(
        a.run,
        a.reference,
        a.proof,
        a.native_directory,
        a.candidate_seal,
        a.candidate_seal_sha,
    )
    with a.output.open("x") as out:
        json.dump(value, out, indent=2)
        out.write("\n")


if __name__ == "__main__":
    main()
