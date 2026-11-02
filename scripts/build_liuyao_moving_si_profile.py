"""Build the frozen same-edition moving-Si qualification profile."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tests/fixtures/liuyao_moving_si_v40"
OUTPUT = ROOT / "src/fatebridge/data/classical/liuyao-moving-si-v40.json"


def build() -> dict[str, Any]:
    freeze = json.loads((REFERENCE / "freeze.json").read_text())
    for name, digest in freeze["files_sha256"].items():
        if hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Frozen moving-Si material changed: {name}")
    adjudication = json.loads((REFERENCE / "profile-adjudication.json").read_text())
    for name, digest in json.loads(
        (REFERENCE / "profile-adjudication-freeze.json").read_text()
    ).items():
        if hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Frozen moving-Si adjudication changed: {name}")
    if (
        adjudication["original_profile_sha256"]
        != freeze["files_sha256"]["profile.json"]
    ):
        raise ValueError("Moving-Si adjudication detached from initial profile")
    permission = json.loads((REFERENCE / "permission-adjudication.json").read_text())
    for name, digest in json.loads(
        (REFERENCE / "permission-adjudication-freeze.json").read_text()
    ).items():
        if hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Frozen ordinary-permission adjudication changed: {name}")
    if (
        permission["previous_adjudication_sha256"]
        != hashlib.sha256(
            (REFERENCE / "profile-adjudication.json").read_bytes()
        ).hexdigest()
    ):
        raise ValueError("Ordinary-permission adjudication detached from prior record")
    profile: dict[str, Any] = json.loads(
        (REFERENCE / permission["adjudicated_profile"]).read_text()
    )
    source = (REFERENCE / profile["source"]["file"]).resolve()
    if not source.is_relative_to((ROOT / "tests/fixtures").resolve()):
        raise ValueError("Moving-Si source escaped fixtures")
    if hashlib.sha256(source.read_bytes()).hexdigest() != profile["source"]["sha256"]:
        raise ValueError("Original moving-Si scan changed")
    return profile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if OUTPUT.read_text() != text:
            raise SystemExit("Moving-Si profile is stale")
    else:
        OUTPUT.write_text(text)
    print("Frozen moving-Si clauses, contexts and scan hash verified")


if __name__ == "__main__":
    main()
