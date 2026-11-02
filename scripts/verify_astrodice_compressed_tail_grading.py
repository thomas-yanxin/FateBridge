"""Independent Decimal replay of every fixed-line geometric diagnostic row."""

import argparse
import hashlib
import json
from decimal import Decimal as D
from decimal import localcontext
from fractions import Fraction as Q
from pathlib import Path

from scripts.verify_astrodice_compressed_tail import PLAN_SHA, verify

PI = D(
    "3.141592653589793238462643383279502884197169399375105820974944592307816406286208998628034825342117067982148086513282306647"
)


def decimal(value):
    q = Q(value)
    return D(q.numerator) / D(q.denominator)


def evaluate(state):
    p, v = list(map(decimal, state[:3])), list(map(decimal, state[3:]))
    radius = sum(x * x for x in p).sqrt()
    u = [x / radius for x in p]
    radial = sum(x * y for x, y in zip(u, v))
    du = [(x - y * radial) / radius for x, y in zip(v, u)]
    xy = u[0] ** 2 + u[1] ** 2
    ra_numerator = u[0] * du[1] - u[1] * du[0]
    return u, du, (ra_numerator / xy, ra_numerator / xy.sqrt(), du[2] / xy.sqrt())


def metrics(state, reference):
    with localcontext() as ctx:
        ctx.prec = 120
        a, da, ra = evaluate(state)
        b, db, rb = evaluate(reference)
        factor = 648000 / PI
        return {
            "position_chord_arcsec": sum((x - y) ** 2 for x, y in zip(a, b)).sqrt()
            * factor,
            "direction_rate_error_arcsec_per_source_day": sum(
                (x - y) ** 2 for x, y in zip(da, db)
            ).sqrt()
            * factor,
            "signed_RA_rate_error": (ra[0] - rb[0]) * factor,
            "signed_RA_cos_DEC_rate_error": (ra[1] - rb[1]) * factor,
            "signed_DEC_rate_error": (ra[2] - rb[2]) * factor,
        }


def verify_rows(protocol, report, references, captures):
    split = report["split"]
    population = [
        (i, profile, b)
        for i in range(len(protocol[split]))
        for profile in protocol["source_profiles"]
        for b in protocol["bodies"]
    ]
    if [
        (r["case_index"], r["profile"], r["body"]) for r in report["rows"]
    ] != population:
        raise ValueError("Independent grading population missing/reordered/duplicated")
    if (
        report["protocol_sha256"] != PLAN_SHA
        or report["fixed_position_line_arcsec"] != "0.02"
        or report["fixed_rate_line_arcsec_per_source_day"] != "0.002"
        or report["decoder_component_budget_au_and_au_per_source_day"] != 1e-14
        or report["old_gates"] != {"production": 2, "overall": 1}
        or any(
            report[x] is not False
            for x in (
                "physical_TT_equivalence_certified",
                "original_failure_records_regraded",
                "installed_native_replaced",
            )
        )
    ):
        raise ValueError("Independent grading original line/claim changed")
    evidence, failures, rows = {}, {}, []
    for profile in protocol["source_profiles"]:
        evidence[profile] = failures[profile] = 0
    for r in report["rows"]:
        key = r["case_index"], r["profile"]
        cap = captures[key]
        native = next(x for x in cap["rows"] if x["body"] == r["body"])
        if native["status"] != "ready":
            if r["status"] != "evidence_unavailable":
                raise ValueError("Native failed row laundered")
            evidence[r["profile"]] += 1
            continue
        if native["requested_flags"] != 137522 or native["returned_flags"] != 139122:
            raise ValueError("Independent native coordinate/backend mismatch")
        ref = next(
            x
            for x in references
            if (x["case_index"], x["body"]) == (r["case_index"], r["body"])
        )
        if Q(cap["numeric_jd"]) != Q(ref["exact_binary64_numeric_jd"]):
            raise ValueError("Independent native/source numeric epoch differs")
        measured = metrics(
            native["state"], ref["geocentric_state_au_and_au_per_source_day"]
        )
        for name, number in measured.items():
            lo, hi = map(Q, r["metrics"][name])
            if lo > Q(number) or Q(number) > hi or hi - lo > Q(1, 10**50):
                raise ValueError(
                    "Independent Decimal result outside narrow outward interval"
                )
        p = measured["position_chord_arcsec"] <= D("0.02")
        v = measured["direction_rate_error_arcsec_per_source_day"] <= D("0.002")
        decoder = (
            max(r["decoder_component_error"], r["independent_decoder_component_error"])
            <= report["decoder_component_budget_au_and_au_per_source_day"]
        )
        if r["status"] != ("evaluated" if decoder else "decoder_reproduction_failed"):
            raise ValueError("Independent decoder status differs")
        if (
            r["position_passed"],
            r["rate_passed"],
            r["rate_definitely_failed"],
            r["passed"],
        ) != (p, v, not v, p and v and decoder):
            raise ValueError("Independent fixed-line decision differs")
        if not decoder:
            evidence[r["profile"]] += 1
        elif not p or not v:
            failures[r["profile"]] += 1
        rows.append(
            {
                "case_index": r["case_index"],
                "profile": r["profile"],
                "body": r["body"],
                "metrics_decimal": {k: str(v) for k, v in measured.items()},
                "passed": p and v and decoder,
            }
        )
    for profile in protocol["source_profiles"]:
        s = report["summary"][profile]
        if (
            s["planned"],
            s["recorded"],
            s["evidence_failures"],
            s["numeric_failures"],
        ) != (
            len(protocol[split]) * len(protocol["bodies"]),
            len(protocol[split]) * len(protocol["bodies"]),
            evidence[profile],
            failures[profile],
        ):
            raise ValueError("Independent summary counts differ")
        valid = [
            r
            for r in report["rows"]
            if r["profile"] == profile and r["status"] == "evaluated"
        ]
        for output, field in (
            ("max_position_chord_arcsec_upper", "position_chord_arcsec"),
            (
                "max_direction_rate_error_arcsec_per_source_day_upper",
                "direction_rate_error_arcsec_per_source_day",
            ),
        ):
            actual = max(
                (float(Q(r["metrics"][field][1])) for r in valid), default=None
            )
            if s[output] != actual:
                raise ValueError("Independent maximum differs")
    profile = protocol["primary_candidate"]
    gate = 2 if evidence[profile] else 1 if failures[profile] else 0
    if report["primary_candidate_gate"] != gate:
        raise ValueError("Independent primary gate differs")
    return rows


def replay(run, path):
    def sha(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()

    protocol = json.loads((run / "plan-before-evaluation.json").read_text())
    if sha(run / "plan-before-evaluation.json") != PLAN_SHA:
        raise ValueError("Independent original protocol changed")
    report = json.loads(path.read_text())
    split = report["split"]
    reference_path = run / f"{split}-reference-first.json"
    reference = json.loads(reference_path.read_text())
    verify(run, reference_path)
    if report["reference_sha256"] != sha(reference_path):
        raise ValueError("Independent reference rebound")
    captures = {}
    for i in range(len(protocol[split])):
        for profile in protocol["source_profiles"]:
            cap_path = run / f"{split}-{profile}-{i}-first.json"
            if report["capture_hashes"][str(cap_path)] != sha(cap_path):
                raise ValueError("Independent capture rebound")
            captures[i, profile] = json.loads(cap_path.read_text())
    rows = verify_rows(protocol, report, reference["rows"], captures)
    return {
        "protocol_sha256": PLAN_SHA,
        "audit_sha256": sha(path),
        "split": split,
        "rows": rows,
        "primary_candidate_gate_confirmed": report["primary_candidate_gate"],
        "independent_reference_exact_replay": True,
        "old_gates": {"production": 2, "overall": 1},
        "original_failure_records_regraded": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["run", "audit", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = replay(args.run, args.audit)
    with args.output.open("x") as out:
        json.dump(result, out, indent=2)
        out.write("\n")


if __name__ == "__main__":
    main()
