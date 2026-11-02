"""Independent lunar reference replay; no production/native/producer imports."""

import argparse
import hashlib
import json
from fractions import Fraction as Q
from pathlib import Path

from scripts.verify_astrodice_lunar_split import (
    LunarSource,
    binary64_nearest,
    check_model,
    model,
    tdb_label,
)

PLAN_SHA = "f4398b6cf40601b333185f0e6b732a51a86ae675d94e6796886f4f685c331fe9"


def verify(run, reference_path):
    raw = (run / "plan-before-evaluation.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA:
        raise ValueError("Independent protocol binding changed")
    plan = json.loads(raw)
    saved = json.loads(reference_path.read_text())
    if saved["protocol_sha256"] != PLAN_SHA:
        raise ValueError("Reference protocol rebound")
    cases = plan[saved["split"]]
    if len(cases) != len(saved["rows"]):
        raise ValueError("Reference population omitted")
    manifest_path = run / "inputs-before-evaluation.json"
    if (
        saved["source_inputs_sha256"]
        != hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    ):
        raise ValueError("Reference source manifest rebound")
    manifest = json.loads(manifest_path.read_text())
    source_dir = Path(plan["reference_source"])
    for path in [
        source_dir / "header.bin",
        *sorted((source_dir / "record-responses").glob("*.bin")),
    ]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest[str(path)]:
            raise ValueError("Independent source bytes changed")
    rows = []
    for case, stored in zip(cases, saved["rows"]):
        exact = tdb_label(case["label"])
        number = binary64_nearest(exact)
        if (
            any(stored[k] != v for k, v in case.items())
            or stored["exact_label_jd_tdb"] != str(exact)
            or stored["exact_binary64_numeric_jd"] != str(number)
            or Q(stored["native_numeric_jd"]) != number
        ):
            raise ValueError("Independent case/input rebound")
        result = model(
            LunarSource(source_dir, case["window"]),
            number,
            "continuous_split",
            derivative=True,
        )
        check_model(result, stored["model"])
        rows.append({**case, "status": "strict_containment_passed"})
    return {
        "protocol_sha256": PLAN_SHA,
        "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
        "split": saved["split"],
        "rows": rows,
        "physical_TT_equivalence_certified": False,
        "original_failure_records_regraded": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.run, args.reference)
    with args.output.open("x") as output:
        json.dump(result, output, indent=2)
        output.write("\n")


if __name__ == "__main__":
    main()
