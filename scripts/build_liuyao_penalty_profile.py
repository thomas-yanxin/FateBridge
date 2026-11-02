"""Publish frozen same-edition Si/Yin/Shen clauses without outcome rules."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tests/fixtures/liuyao_penalty_v20"
OUTPUT = ROOT / "src/fatebridge/data/classical/liuyao-penalty-v20.json"


def build() -> dict[str, Any]:
    frozen = json.loads((REFERENCE / "freeze.json").read_text())
    for name, digest in frozen["sha256"].items():
        if hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Frozen penalty reference changed: {name}")
    profile: dict[str, Any] = json.loads((REFERENCE / "profile.json").read_text())
    source = (REFERENCE / profile["source"]["file"]).resolve()
    if not source.is_relative_to((ROOT / "tests/fixtures").resolve()):
        raise ValueError("Penalty source escaped fixtures")
    if hashlib.sha256(source.read_bytes()).hexdigest() != profile["source"]["sha256"]:
        raise ValueError("Original penalty scan changed")
    errata = REFERENCE / "quotation-errata.json"
    if (
        hashlib.sha256(errata.read_bytes()).hexdigest()
        != json.loads((REFERENCE / "quotation-errata-freeze.json").read_text())[
            "sha256"
        ]
    ):
        raise ValueError("Penalty quotation erratum changed")
    correction = json.loads(errata.read_text())
    assert correction["profile_sha256"] == frozen["sha256"]["profile.json"]
    clause = next(c for c in profile["clauses"] if c["id"] == correction["clause_id"])
    assert clause["quote"] == correction["old_quote"]
    clause["quote"] = correction["new_quote"]
    profile["quotation_errata"] = correction
    precedence = ROOT / "tests/fixtures/liuyao_penalty_precedence_v21"
    for name, digest in json.loads((precedence / "freeze.json").read_text())[
        "sha256"
    ].items():
        if hashlib.sha256((precedence / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Frozen precedence reference changed: {name}")
    profile["precedence"] = json.loads((precedence / "adjudication.json").read_text())
    assert profile["precedence"]["source_sha256"] == profile["source"]["sha256"]
    profile["ruleset_version"] = "2.0.0"
    profile[
        "scope"
    ] += "；第98页特定寅生巳排除先于第10章一般回头生许可，逐来源限定日月、本位变支与原动爻；原始关系、月令位置与空破门槛保留，刑的总作用仍未裁定。"
    return profile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if OUTPUT.read_text() != text:
            raise SystemExit("Penalty profile is stale")
    else:
        OUTPUT.write_text(text)
    print("Scoped penalty clauses, frozen cases and original scan verified")


if __name__ == "__main__":
    main()
