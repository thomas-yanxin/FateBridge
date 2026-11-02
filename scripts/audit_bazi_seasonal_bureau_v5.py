"""Same frozen hypothesis, next three complete source units, no new tuning."""

from __future__ import annotations

import argparse
import importlib.util
import json
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol, cast

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_seasonal_bureau_v5"
CHAPTERS = {"中和", "源流", "通关"}


class PreviousRunner(Protocol):
    FIXTURE: Path
    GROUPS: dict[str, str]
    NEW_GROUP: str

    def audit(self, candidate_root: Path) -> dict[str, Any]: ...


def audit(candidate_root: Path) -> dict[str, Any]:
    path = ROOT / "scripts/audit_bazi_seasonal_bureau_v2.py"
    spec = importlib.util.spec_from_file_location("_previous_seasonal_bureau", path)
    if spec is None or spec.loader is None:
        raise ValueError("Previous runner unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    previous = cast(PreviousRunner, module)
    previous.FIXTURE = FIXTURE
    previous.GROUPS = {
        **previous.GROUPS,
        "prior_bage": "tests/fixtures/bazi_seasonal_bureau_v2/reference.json",
        "prior_body_spirit_month_hour": "tests/fixtures/bazi_seasonal_bureau_v3/reference.json",
        "prior_shuaiwang": "tests/fixtures/bazi_seasonal_bureau_v4/reference.json",
        "new_dizhi": "tests/fixtures/bazi_seasonal_bureau_v5/reference.json",
    }
    previous.NEW_GROUP = "new_zhonghe_yuanliu_tongguan"
    result = previous.audit(candidate_root)
    reference = json.loads((FIXTURE / "reference.json").read_text())
    result["fresh_source_summary"]["chapter_cases"] = sum(
        c["source_unit"] in CHAPTERS for c in reference["cases"]
    )
    result["fresh_source_summary"]["previous_chapter_boundary_cases"] = sum(
        c["source_unit"] not in CHAPTERS for c in reference["cases"]
    )
    result["formation_scope"] = (
        "No source-explicit full-transformation verdict in this block. "
        "Original transcription conflicts and unknowns retain their frozen source types; "
        "Source flow and helping relations do not auto-fill body labels."
    )
    result["underlying_runner_sha256"] = result["runner_sha256"]
    result["runner_sha256"] = sha256(Path(__file__).read_bytes()).hexdigest()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Preserve the earlier comparison")
    result = audit(args.candidate_root)
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
                "fresh": result["fresh_source_summary"],
                "gates": result["adoption_gates"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["numerical_gates_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
