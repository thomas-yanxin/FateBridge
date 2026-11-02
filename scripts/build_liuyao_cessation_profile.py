"""Publish frozen original-scan cessation constraints and cases."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scripts.liuyao_quote_collation import apply_quote_errata
elif __package__:
    from .liuyao_quote_collation import apply_quote_errata
else:
    from liuyao_quote_collation import apply_quote_errata

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tests/fixtures/liuyao_cessation_v17"
OUTPUT = ROOT / "src/fatebridge/data/classical/liuyao-cessation-v17.json"


def build() -> dict[str, Any]:
    frozen = json.loads((REFERENCE / "freeze.json").read_text(encoding="utf-8"))
    for name, digest in frozen["sha256"].items():
        if hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Frozen cessation reference changed: {name}")
    profile: dict[str, Any] = json.loads(
        (REFERENCE / "profile.json").read_text(encoding="utf-8")
    )
    source = (REFERENCE / profile["source"]["file"]).resolve()
    if not source.is_relative_to((ROOT / "tests/fixtures").resolve()):
        raise ValueError("Cessation source escaped fixtures")
    if hashlib.sha256(source.read_bytes()).hexdigest() != profile["source"]["sha256"]:
        raise ValueError("Original cessation scan changed")
    return apply_quote_errata(
        profile, root=ROOT, original=REFERENCE / "profile.json", artifact=OUTPUT.name
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if OUTPUT.read_text(encoding="utf-8") != text:
            raise SystemExit("Cessation profile is stale")
    else:
        OUTPUT.write_text(text, encoding="utf-8")
    print("Cessation clauses, frozen cases and original scan hash verified")


if __name__ == "__main__":
    main()
