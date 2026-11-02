"""Check frozen before/after timing clocks, with all legacy fields retained."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_analysis_instant_v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def difference_paths(old: Any, new: Any, path: str = "") -> list[str]:
    if old == new:
        return []
    if isinstance(old, dict) and isinstance(new, dict):
        return [
            item
            for key in sorted(old.keys() | new.keys())
            for item in (
                difference_paths(old[key], new[key], path + "/" + key)
                if key in old and key in new
                else [path + "/" + key]
            )
        ]
    if isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        return [
            item
            for i, (a, b) in enumerate(zip(old, new))
            for item in difference_paths(a, b, path + "/" + str(i))
        ]
    return [path]


def audit() -> dict[str, Any]:
    from fastapi.testclient import TestClient

    import fatebridge.api as api
    from fatebridge.services.tool_catalog import CATALOG
    from fatebridge.utils.timezones import parse_timezone_name

    before = FIXTURE / "before-results-controlled.json.gz"
    if digest(before) != before.with_suffix(".gz.sha256").read_text().strip():
        raise ValueError("Controlled baseline changed")
    baseline = json.loads(gzip.decompress(before.read_bytes()))
    protocol = FIXTURE / "protocol.json"
    if digest(protocol) != baseline["protocol_sha256"]:
        raise ValueError("Wrong clock protocol")
    api.API_KEY_AUTHENTICATOR = api.ApiKeyAuthenticator(
        header_name="X-API-Key", api_keys={}
    )
    specs = {s.key: s for s in CATALOG}
    rows = []
    with TestClient(api.app) as client:
        for old in baseline["cases"]:
            response = client.post(
                specs[old["tool"]].rest_path,
                json=old["input"],
                params={"as_of": old["as_of"], "response_char_limit": 0},
            )
            value = response.json()
            business = {k: v for k, v in value.items() if k != "run_metadata"}
            comparable = {
                k: v for k, v in business.items() if k != "analysis_reference"
            }
            deltas = difference_paths(old["business"], comparable)
            reference = business.get("analysis_reference", {})
            expected = datetime.fromisoformat(old["as_of"].replace("Z", "+00:00"))
            expected = expected.astimezone(
                parse_timezone_name(old["input"]["birth_timezone"])
            )
            checks = {
                "legacy_preserved": (
                    response.status_code == old["status_code"] and not deltas
                    if old["kind"] == "legacy-explicit-preservation"
                    else None
                ),
                "implicit_instant_correct": (
                    response.status_code == 200
                    and reference.get("analysis_datetime") == expected.isoformat()
                    and reference.get("utc_datetime")
                    == expected.astimezone(timezone.utc).isoformat()
                    and reference.get("basis") == "implicit_execution_clock"
                    and business["analysis_calendar"]["analysis_date_context"][
                        "bazi_month_boundary"
                    ]["comparison_datetime"]
                    == expected.isoformat()
                    if old["kind"] == "known-clock-defect"
                    else None
                ),
                "invalid_explicit_clock_rejected": (
                    response.status_code == 400
                    and any(
                        token in str(value)
                        for token in ("ambiguous local time", "nonexistent local time")
                    )
                    if old["kind"] == "ambiguous-or-nonexistent-analysis-clock"
                    else None
                ),
            }
            rows.append(
                {
                    "id": old["id"],
                    "kind": old["kind"],
                    "status_code": response.status_code,
                    "business": business,
                    "metadata": value.get("run_metadata"),
                    "old_field_difference_paths": deltas,
                    "checks": checks,
                }
            )
    gates = {
        key: all(r["checks"][key] is not False for r in rows)
        for key in (
            "legacy_preserved",
            "implicit_instant_correct",
            "invalid_explicit_clock_rejected",
        )
    }
    if digest(before) != before.with_suffix(".gz.sha256").read_text().strip():
        raise ValueError("Baseline changed during audit")
    numeric_protocol = (
        ROOT / "tests/fixtures/bazi_qualified_root_capacity_v1/protocol.json"
    )
    numeric_dependencies = json.loads(numeric_protocol.read_text())[
        "numerical_dependencies"
    ]
    numeric_preservation = {
        rel: {
            "expected_sha256": item["sha256"],
            "actual_sha256": digest(ROOT / rel),
            "unchanged": digest(ROOT / rel) == item["sha256"],
        }
        for rel, item in numeric_dependencies.items()
    }
    numeric_unchanged = all(item["unchanged"] for item in numeric_preservation.values())
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": digest(protocol),
        "controlled_baseline_sha256": digest(before),
        "runner_sha256": digest(Path(__file__)),
        "rows": rows,
        "counts": {key: sum(r["checks"][key] is True for r in rows) for key in gates},
        "gates": gates,
        "all_gates_passed": all(gates.values()),
        "new_astronomical_reference_credit": 0,
        "numeric_kernel_preservation": {
            "protocol": str(numeric_protocol.relative_to(ROOT)),
            "protocol_sha256": digest(numeric_protocol),
            "dependencies": numeric_preservation,
            "all_bytes_unchanged": numeric_unchanged,
            "scope": "Unchanged bytes preserve the numeric kernel; a changed dependency is not by itself proof of changed labels and requires a complete source-corpus replay.",
        },
        "classical_strength_labels_changed": False if numeric_unchanged else None,
        "full_goal_complete": False,
        "overall_score": None,
        "scope": "Engineering clock correction, not new solar/lunar accuracy or source-strength acceptance. All17predeclared records retained, including formerly accepted invalid clocks; all old fields of11valid explicit/partial calls compared without removing fields except the newly introduced analysis_reference.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(".gz.sha256").exists():
        parser.error("Existing outputs are reserved; do not overwrite a first result")
    report = audit()
    with args.output.open("xb") as stream:
        stream.write(
            gzip.compress(
                json.dumps(report, ensure_ascii=False, indent=2).encode(), mtime=0
            )
        )
    with args.output.with_suffix(".gz.sha256").open("x") as stream:
        stream.write(digest(args.output) + "\n")
    print(
        json.dumps(
            {"counts": report["counts"], "gates": report["gates"]}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
