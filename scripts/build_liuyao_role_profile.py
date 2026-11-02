"""Check independently frozen Chapter Ten clauses before publishing the profile."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tests/fixtures/liuyao_effects_v4"
OUTPUT = ROOT / "src/fatebridge/data/classical/liuyao-effects-v4.json"


def build():
    freeze = json.loads((REFERENCE / "freeze.json").read_text(encoding="utf-8"))
    for name, expected in freeze["sha256"].items():
        if hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen role reference changed: {name}")
    profile = json.loads((REFERENCE / "profile.json").read_text(encoding="utf-8"))
    source = (REFERENCE / profile["source"]["file"]).resolve()
    if not source.is_relative_to((ROOT / "tests/fixtures").resolve()):
        raise ValueError("Role source escaped fixture bundle")
    if hashlib.sha256(source.read_bytes()).hexdigest() != profile["source"]["sha256"]:
        raise ValueError("Role source scan changed")
    return profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if OUTPUT.read_text(encoding="utf-8") != rendered:
            raise SystemExit("Liu Yao role profile is stale")
    else:
        OUTPUT.write_text(rendered, encoding="utf-8")
    print("23 role-condition clauses, frozen cases and original scan hash checked")


if __name__ == "__main__":
    main()
