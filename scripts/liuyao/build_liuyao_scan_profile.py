"""Validate frozen scan bytes and publish only the reviewed textual claims."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "tests/fixtures/liuyao_scan_v3"
OUTPUT = ROOT / "src/fatebridge/data/classical/liuyao-scan-v3.json"


def build():
    freeze = json.loads((REFERENCE / "freeze.json").read_text(encoding="utf-8"))
    for name, expected in freeze["sha256"].items():
        if hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen Liu Yao reference changed: {name}")
    reference = json.loads((REFERENCE / "collation.json").read_text(encoding="utf-8"))
    source = reference["source"]
    path = (REFERENCE / source["file"]).resolve()
    if not path.is_relative_to(REFERENCE.resolve()):
        raise ValueError("Scan reference escaped its bundle")
    if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
        raise ValueError("Frozen Liu Yao scan bytes changed")
    for row in reference["collations"]:
        if not row["quote"] or not all(
            1 <= p <= source["page_count"] for p in row["pdf_pages"]
        ):
            raise ValueError("Invalid collation claim or PDF page")
    return reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if OUTPUT.read_text(encoding="utf-8") != text:
            raise SystemExit("Liu Yao scan profile is stale")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(text, encoding="utf-8")
    print("Liu Yao selected scan passages and original byte hash verified")


if __name__ == "__main__":
    main()
