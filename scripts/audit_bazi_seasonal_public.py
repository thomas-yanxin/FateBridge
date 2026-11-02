"""Replay all exposed seasonal-study source groups through the actual public entry."""

from __future__ import annotations

import argparse
import importlib.util
import json
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol, cast

ROOT = Path(__file__).resolve().parents[1]


class PublicReplay(Protocol):
    GROUPS: dict[str, str]

    def audit(self) -> dict[str, Any]: ...


def load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(
        "_season_public_" + name, ROOT / "scripts" / (name + ".py")
    )
    if spec is None or spec.loader is None:
        raise ValueError("Replay module unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit() -> dict[str, Any]:
    public = cast(PublicReplay, load("audit_bazi_clash_current"))
    study = load("audit_bazi_seasonal_bureau_v2")
    public.GROUPS = {
        **study.GROUPS,
        "prior_bage": "tests/fixtures/bazi_seasonal_bureau_v2/reference.json",
        "new_dizhi": "tests/fixtures/bazi_seasonal_bureau_v3/reference.json",
    }
    result = public.audit()
    result["runner_sha256"] = sha256(Path(__file__).read_bytes()).hexdigest()
    result["source_group_selection"] = (
        "All complete prior fixture case groups plus both new full source blocks; unknowns and repeated inputs retained, no aggregate accuracy."
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Preserve the earlier public replay")
    result = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(
        json.dumps(
            {
                "groups": {
                    g: {k: v for k, v in data.items() if k != "rows"}
                    for g, data in result["groups"].items()
                },
                "distinct_mismatches": len(result["distinct_mismatches"]),
                "source_drift": result["source_drift"],
            },
            ensure_ascii=False,
        )
    )
    return 1 if result["source_drift"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
