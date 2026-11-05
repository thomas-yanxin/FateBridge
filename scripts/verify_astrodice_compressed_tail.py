"""Exact independent basis/derivative and Gregorian-JDN reference replay."""

import argparse
import hashlib
import json
import struct
from datetime import datetime
from fractions import Fraction as Q
from pathlib import Path

from scripts.verify_astrodice_lunar_split import binary64_nearest

PLAN_SHA = "6356429ab6b78a319a61393289399d8487bed68a6748e52edd2e87295e926f31"
INPUT_SHA = "b48f6d48c9d60a9ed5896ec340890f33dfd892971e07abaf39ef41a055c032e6"


def label_jd(label):
    v = datetime.fromisoformat(label)
    a = (14 - v.month) // 12
    y = v.year + 4800 - a
    m = v.month + 12 * a - 3
    jdn = v.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    return (
        Q(jdn)
        - Q(1, 2)
        + Q(v.hour * 3600 + v.minute * 60 + v.second, 86400)
        + Q(v.microsecond, 86400000000)
    )


def group(header, raw, epoch, index):
    values = struct.unpack("<1018d", raw)
    begin, end = map(Q, values[:2])
    offset, count, parts = struct.unpack_from("<3i", header, 2696 + 12 * index)
    width = (end - begin) / parts
    part = int((epoch - begin) // width)
    if not 0 <= part < parts:
        raise ValueError("Independent source part out of range")
    x = 2 * (epoch - begin - part * width) / width - 1
    basis, derivative = [Q(1), x], [Q(), Q(1)]
    for _ in range(2, count):
        derivative.append(2 * basis[-1] + 2 * x * derivative[-1] - derivative[-2])
        basis.append(2 * x * basis[-1] - basis[-2])
    au = Q(struct.unpack_from("<d", header, 2680)[0])
    position = []
    velocity = []
    for axis in range(3):
        first = offset - 1 + (part * 3 + axis) * count
        coefficients = list(map(Q, values[first : first + count]))
        position.append(sum((a * b for a, b in zip(coefficients, basis)), Q()) / au)
        velocity.append(
            sum((a * b for a, b in zip(coefficients, derivative)), Q()) * 2 / width / au
        )
    return position + velocity


def verify(run, path):
    def sha(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()

    if (
        sha(run / "plan-before-evaluation.json") != PLAN_SHA
        or sha(run / "inputs-before-development.json") != INPUT_SHA
    ):
        raise ValueError("Independent original plan/input manifest changed")
    plan = json.loads((run / "plan-before-evaluation.json").read_text())
    saved = json.loads(path.read_text())
    if (
        saved["protocol_sha256"] != PLAN_SHA
        or saved["old_gates"] != {"production": 2, "overall": 1}
        or saved["physical_TT_equivalence_certified"] is not False
        or saved["original_failure_records_regraded"] is not False
    ):
        raise ValueError("Reference binding/claim changed")
    inputs = json.loads((run / "inputs-before-development.json").read_text())
    split = saved["split"]
    if [(r["case_index"], r["body"]) for r in saved["rows"]] != [
        (i, b) for i, c in enumerate(plan[split]) for b in plan["bodies"]
    ]:
        raise ValueError("Independent planned population missing")
    rows = []
    for row in saved["rows"]:
        case = plan[split][row["case_index"]]
        label = label_jd(case["label"])
        epoch = binary64_nearest(label)
        if (
            any(row[k] != v for k, v in case.items())
            or row["exact_label_jd_tdb"] != str(label)
            or row["exact_binary64_numeric_jd"] != str(epoch)
            or Q(row["numeric_jd"]) != epoch
        ):
            raise ValueError("Independent source epoch/target rebound")
        folder = Path(case["source"])
        h = folder / "header.bin"
        p = folder / f"record-responses/case-{case['window']:02}.bin"
        for name in [h, p]:
            if sha(name) != inputs[str(name)]:
                raise ValueError("Original source bytes changed")
        raw = p.read_bytes()
        header = h.read_bytes()
        record = next(
            r
            for r in [raw[k : k + 8144] for k in range(0, len(raw), 8144)]
            if Q(struct.unpack_from("<d", r)[0])
            <= epoch
            < Q(struct.unpack_from("<d", r, 8)[0])
        )
        if hashlib.sha256(record).hexdigest() != row["source_record_sha256"]:
            raise ValueError("Source record rebound")
        moon = group(header, record, epoch, 9)
        if row["body"] == "Moon":
            state = moon
        else:
            emb = group(header, record, epoch, 2)
            ratio = Q(struct.unpack_from("<d", header, 2688)[0])
            earth = [a - b / (1 + ratio) for a, b in zip(emb, moon)]
            target = group(
                header, record, epoch, {"Mercury": 0, "Venus": 1}[row["body"]]
            )
            state = [a - b for a, b in zip(target, earth)]
        if list(map(str, state)) != row["geocentric_state_au_and_au_per_source_day"]:
            raise ValueError("Independent exact geometric components differ")
        rows.append(
            {
                "case_index": row["case_index"],
                "body": row["body"],
                "status": "exact_six_component_equality",
            }
        )
    return {
        "protocol_sha256": PLAN_SHA,
        "reference_sha256": sha(path),
        "split": split,
        "rows": rows,
        "physical_TT_equivalence_certified": False,
        "original_failure_records_regraded": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ["run", "reference", "output"]:
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    result = verify(a.run, a.reference)
    with a.output.open("x") as out:
        json.dump(result, out, indent=2)
        out.write("\n")


if __name__ == "__main__":
    main()
