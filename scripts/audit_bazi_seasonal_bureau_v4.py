"""Replay the unchanged candidate against the complete, edition-specific 衰旺 unit."""

from __future__ import annotations

import argparse
import importlib.util
import json
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol, cast

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_seasonal_bureau_v4"
ORDER = ("year", "month", "day", "hour")


class PreviousRunner(Protocol):
    FIXTURE: Path
    GROUPS: dict[str, str]
    NEW_GROUP: str

    def audit(self, candidate_root: Path) -> dict[str, Any]: ...


def source_crosscheck(reference: dict[str, Any]) -> list[dict[str, Any]]:
    """Compare editions without copying legacy answers into the new annotation."""
    legacy_path = ROOT / "tests/fixtures/bazi-strength-reference.json"
    legacy = json.loads(legacy_path.read_text())
    rows = []
    for case in reference["cases"]:
        exposure = case["prior_textual_case_exposure"]
        old = next(c for c in legacy["cases"] if c["id"] == exposure["record_id"])
        old_pillars = [old["pillars"][k] for k in ORDER]
        rows.append(
            {
                "case_id": case["id"],
                "legacy_id": old["id"],
                "pillars_equal": case["pillars"] == old_pillars,
                "body_label_equal": case["expected_strength"]
                == old["expected_strength"],
                "source_state_equal": case["source_strength_state"]
                == old["source_label"],
                "legacy_pillars": old_pillars,
                "scanned_edition_pillars": case["pillars"],
                "legacy_source_label": old["source_label"],
                "scanned_edition_source_state": case["source_strength_state"],
            }
        )
    if rows != reference["legacy_source_crosscheck"]:
        raise ValueError("Edition crosscheck differs from the frozen annotation")
    return rows


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
        "new_dizhi": "tests/fixtures/bazi_seasonal_bureau_v4/reference.json",
    }
    previous.NEW_GROUP = "complete_shuaiwang_scanned_edition"
    reference = json.loads((FIXTURE / "reference.json").read_text())
    edition_check = source_crosscheck(reference)
    result = previous.audit(candidate_root)
    result["fresh_source_summary"]["chapter_cases"] = len(reference["cases"])
    result["fresh_source_summary"]["previous_chapter_boundary_cases"] = 0
    result["source_exposure"] = {
        "exact_nonoverlap_cases": [
            c["id"] for c in reference["cases"] if not c["prior_exact_pillar_overlaps"]
        ],
        "fresh_gate_eligible_cases": [
            c["id"] for c in reference["cases"] if c["fresh_gate_eligible"]
        ],
        "same_textual_cases_previously_exposed": len(edition_check),
        "policy_addendum": reference["exposure_policy_addendum"],
    }
    result["edition_crosscheck"] = edition_check
    result["formation_scope"] = (
        "The complete twenty-case unit verifies edition-specific inputs and "
        "three-bin source mappings. 太旺/旺极/太衰/衰极 remain source states, "
        "not computed substates. Same textual cases, including the changed-hour "
        "transcription, provide no independent fresh-improvement evidence."
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
