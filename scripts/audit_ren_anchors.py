"""Keep same-run anchors across Liu Ren, Jin Kou and embedded Three Arts."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_anchors_v1"
WATCH = (
    "src/fatebridge/core/output_ren_anchors.py",
    "src/fatebridge/core/response_models.py",
    "src/fatebridge/core/output_chinese.py",
    "src/fatebridge/core/metaphysics/common.py",
    "src/fatebridge/core/metaphysics/jinkou.py",
    "src/fatebridge/core/metaphysics/liureng.py",
    "src/fatebridge/services/metaphysics.py",
    "src/fatebridge/application/execution.py",
    "scripts/audit_ren_anchors.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    freeze = json.loads((corpus / "freeze.json").read_text())
    names = {"faults.json", "provenance.json"}
    if set(freeze["files"]) != names or {p.name for p in corpus.iterdir()} != names | {
        "freeze.json"
    }:
        raise ValueError("Frozen anchor inventory changed")
    for name in names:
        if sha(corpus / name) != freeze["files"][name]:
            raise ValueError("Frozen anchor criteria changed")
    data: dict[str, Any] = json.loads((corpus / "faults.json").read_text())
    if (
        len(data["faults"]) != 36
        or len({(f["tool"], f["id"]) for f in data["faults"]}) != 36
    ):
        raise ValueError("All 36 predeclared faults are required")
    provenance = json.loads((corpus / "provenance.json").read_text())
    for name, digest in provenance["reused_frozen_sources"].items():
        if sha(ROOT / name) != digest:
            raise ValueError("Existing independent source freeze changed")
    return data


def results(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    from fatebridge.services.tool_catalog import CATALOG

    outputs = {}
    for key, payload in data["payloads"].items():
        spec = next(s for s in CATALOG if s.key == key)
        request = spec.request_model.model_validate(payload)
        service, args, kwargs = spec.bind(request)
        outputs[key] = service(*args, **kwargs)
    spec = next(s for s in CATALOG if s.key == "jinkou")
    donor = {**data["payloads"]["jinkou"], "analysis_day": 21}
    service, args, kwargs = spec.bind(spec.request_model.model_validate(donor))
    return outputs, service(*args, **kwargs)


def corrupt(base: dict[str, Any], fault: dict[str, Any], donor: dict[str, Any]) -> Any:
    result = copy.deepcopy(base)
    operation = fault["op"]
    if operation == "other_jinkou_day":
        result["jinkou"] = copy.deepcopy(donor["jinkou"])
    elif operation == "drop_human":
        result["jinkou"]["rows"].pop(0)
    elif operation == "swap_ends":
        rows = result["jinkou"]["rows"]
        rows[0], rows[3] = rows[3], rows[0]
    elif operation == "updates":
        for path, value in fault["updates"].items():
            parts = path.split(".")
            cursor = result
            for part in parts[:-1]:
                cursor = cursor[int(part)] if isinstance(cursor, list) else cursor[part]
            key = int(parts[-1]) if isinstance(cursor, list) else parts[-1]
            cursor[key] = value
    else:
        raise ValueError("Unknown frozen fault operation")
    return result


def hashes() -> dict[str, str | None]:
    return {n: sha(ROOT / n) if (ROOT / n).exists() else None for n in WATCH}


def completeness_reference() -> list[dict[str, Any]]:
    corpus = ROOT / "tests/fixtures/ren_anchor_completeness_v1"
    freeze = json.loads((corpus / "freeze.json").read_text())
    if set(freeze["files"]) != {"faults.json"} or {
        p.name for p in corpus.iterdir()
    } != {"freeze.json", "faults.json"}:
        raise ValueError("Frozen completeness inventory changed")
    if sha(corpus / "faults.json") != freeze["files"]["faults.json"]:
        raise ValueError("Frozen completeness criteria changed")
    faults: list[dict[str, Any]] = json.loads((corpus / "faults.json").read_text())[
        "faults"
    ]
    if len(faults) != 6 or len({(f["tool"], f["path"]) for f in faults}) != 6:
        raise ValueError("All six complete-service faults are required")
    return faults


def remove_anchor(base: dict[str, Any], path: str) -> dict[str, Any]:
    result = copy.deepcopy(base)
    parts = path.split(".")
    cursor = result
    for part in parts[:-1]:
        cursor = cursor[part]
    del cursor[parts[-1]]
    return result


def audit() -> dict[str, Any]:
    data = reference()
    complete_faults = completeness_reference()
    before = hashes()
    from pydantic import ValidationError

    from fatebridge.application.execution import OutputContractError, validate_output
    from fatebridge.services.tool_catalog import CATALOG

    valid, donor = results(data)
    specs = {s.key: s for s in CATALOG}
    for key, payload in valid.items():
        model = specs[key].output_model
        assert model is not None
        model.model_validate(payload)
        validate_output(specs[key], payload)
    checks = []
    for fault in data["faults"]:
        model = specs[fault["tool"]].output_model
        assert model is not None
        try:
            model.model_validate(corrupt(valid[fault["tool"]], fault, donor))
            accepted = True
        except ValidationError:
            accepted = False
        checks.append(
            dict(
                tool=fault["tool"],
                id=fault["id"],
                expected_acceptance=False,
                accepted=accepted,
                rejected=not accepted,
            )
        )
    complete_checks = []
    for fault in complete_faults:
        try:
            validate_output(
                specs[fault["tool"]],
                remove_anchor(valid[fault["tool"]], fault["path"]),
            )
            rejected = False
        except OutputContractError:
            rejected = True
        complete_checks.append({**fault, "rejected": rejected})
    after = hashes()
    if before != after:
        raise ValueError("Anchor source changed during audit")
    return dict(
        reference_sha256=sha(CORPUS / "freeze.json"),
        implementation_sha256=after,
        valid_tool_count=len(valid),
        predeclared_fault_count=36,
        rejected_fault_count=sum(c["rejected"] for c in checks),
        checks=checks,
        fault_rejection_passed=all(c["rejected"] for c in checks),
        separately_frozen_completeness_fault_count=6,
        completeness_checks=complete_checks,
        completeness_rejection_passed=all(c["rejected"] for c in complete_checks),
        new_classical_cases=0,
        new_empirical_outcomes=0,
        model_invocations=0,
        classical_acceptance_passed=False,
        goal_complete=False,
        scope="Engineering anchor integrity under existing conventions; not independent verification of a civil date, a full original text, or free-text interpretation.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Rejected {report['rejected_fault_count']}/36 predeclared anchor faults")
    print(
        "Complete-service anchor deletion gate:",
        report["completeness_rejection_passed"],
    )
    return (
        0
        if report["fault_rejection_passed"] and report["completeness_rejection_passed"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
