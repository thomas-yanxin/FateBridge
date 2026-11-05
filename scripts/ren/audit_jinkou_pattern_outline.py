"""Fixed selected-definition identities remain valid without raw course anchors.

This audits a public contract, not the correctness of the selected definitions.
Original book disagreements, unknown clauses and prediction gates stay separate.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/jinkou_pattern_outline_v1"
PIN = "714dd649b9ba8884de94f55c58ea1afa62c48cc65439d34ecfa9bc6ea774d8a5"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(folder: Path = CORPUS) -> dict[str, Any]:
    if sha(folder / "freeze.json") != PIN:
        raise ValueError("Frozen pattern outline manifest identity changed")
    manifest = json.loads((folder / "freeze.json").read_text())
    if set(manifest) != {"reference.json", "protocol.json", "source-reading.json"} or {
        p.name for p in folder.iterdir()
    } != set(manifest) | {"freeze.json"}:
        raise ValueError("Frozen pattern outline inventory changed")
    if any(sha(folder / n) != h for n, h in manifest.items()):
        raise ValueError("Frozen pattern outline reference changed")
    ref: dict[str, Any] = json.loads((folder / "reference.json").read_text())
    if (
        sha(ROOT / "tests/fixtures/jinkou_patterns_v1/freeze.json")
        != ref["original_reference_freeze_sha256"]
    ):
        raise ValueError("Original64 reference changed")
    if len(ref["entries"]) != 64:
        raise ValueError("Original64 definition identities required")
    return ref


def probes() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ref = reference()
    bad, valid = [], []
    for key, value in ref["metadata"].items():
        valid.append(dict(model="patterns", value={key: value}, label=key))
        bad.append(
            dict(model="patterns", value={key: ref["metadata_faults"][key]}, label=key)
        )
    for row in ref["entries"]:
        pid = row["id"]
        keys = ("id", "name", "original_pdf_page", "condition")
        valid.append(
            dict(model="evaluation", value={k: row[k] for k in keys}, label=pid)
        )
        for key in ["name", "original_pdf_page", "condition"]:
            value = 999 if key == "original_pdf_page" else "forged-definition"
            bad.append(
                dict(
                    model="evaluation",
                    value=dict(id=pid, **{key: value}),
                    label=pid + "." + key,
                )
            )
        if pid in ref["unknown_ids"]:
            valid.append(
                dict(
                    model="unresolved",
                    value=dict(id=pid, name=row["name"], reason=row["reason"]),
                    label=pid,
                )
            )
            bad.append(
                dict(
                    model="unresolved",
                    value=dict(id=pid, reason="adjudicated"),
                    label=pid + ".reason",
                )
            )
            bad.append(
                dict(model="match", value=dict(id=pid), label=pid + ".unknown_match")
            )
            for verdict in [True, False]:
                bad.append(
                    dict(
                        model="evaluation",
                        value=dict(id=pid, matched=verdict),
                        label=pid + ".unknown." + str(verdict),
                    )
                )
        else:
            valid.append(
                dict(
                    model="match",
                    value=dict(
                        id=pid,
                        name=row["name"],
                        alias=row["alias"],
                        original_pdf_page=row["original_pdf_page"],
                        condition=row["condition"],
                    ),
                    label=pid,
                )
            )
            bad.append(
                dict(
                    model="match",
                    value=dict(id=pid, alias="forged-alias"),
                    label=pid + ".alias",
                )
            )
            bad.append(
                dict(
                    model="evaluation",
                    value=dict(id=pid, status="unresolved_definition", matched=None),
                    label=pid + ".unresolved_status",
                )
            )
    for key in ["source_url", "source_section"]:
        valid.append(
            dict(
                model="board",
                value=dict(
                    rule_trace=[
                        dict(
                            rule_id="jinkou.structural_patterns",
                            **{key: ref["metadata"][key]},
                        )
                    ]
                ),
                label="trace." + key,
            )
        )
        bad.append(
            dict(
                model="board",
                value=dict(
                    rule_trace=[
                        dict(
                            rule_id="jinkou.structural_patterns",
                            **{key: ref["metadata_faults"][key]},
                        )
                    ]
                ),
                label="trace." + key,
            )
        )
    for key in ["source_sha256", "scope"]:
        valid.append(
            dict(
                model="board",
                value=dict(
                    rule_trace=[
                        dict(
                            rule_id="jinkou.structural_patterns",
                            result={key: ref["metadata"][key]},
                        )
                    ]
                ),
                label="trace.result." + key,
            )
        )
        bad.append(
            dict(
                model="board",
                value=dict(
                    rule_trace=[
                        dict(
                            rule_id="jinkou.structural_patterns",
                            result={key: ref["metadata_faults"][key]},
                        )
                    ]
                ),
                label="trace.result." + key,
            )
        )
    valid.extend(
        [
            dict(
                model="patterns",
                value={"extension": {"unreviewed": True}},
                label="extension",
            ),
            dict(
                model="evaluation",
                value={"matched": True, "extension": 0},
                label="no-id-no-guess",
            ),
            dict(
                model="evaluation",
                value={"id": "P01", "matched": None, "status": "input_unavailable"},
                label="known-input-missing",
            ),
            dict(
                model="board",
                value={
                    "rule_trace": [
                        {"rule_id": "extension", "result": {"scope": "external"}}
                    ]
                },
                label="other-trace",
            ),
        ]
    )
    return bad, valid


def audit() -> dict[str, Any]:
    bad, valid = probes()
    from pydantic import BaseModel, ValidationError

    from fatebridge.core.output_chinese import Jinkou
    from fatebridge.core.output_ren_patterns import (
        JinkouPatternEvaluation,
        JinkouPatternMatch,
        JinkouPatterns,
        JinkouUnresolvedPattern,
    )

    models: dict[str, type[BaseModel]] = dict(
        patterns=JinkouPatterns,
        evaluation=JinkouPatternEvaluation,
        match=JinkouPatternMatch,
        unresolved=JinkouUnresolvedPattern,
        board=Jinkou,
    )
    rows = []
    for expectation, cases in [("reject", bad), ("preserve", valid)]:
        for case in cases:
            try:
                parsed = models[case["model"]].model_validate(case["value"])
                accepted = True
                preserved = parsed.model_dump(exclude_unset=True) == case["value"]
            except ValidationError:
                accepted = False
                preserved = False
            rows.append(
                dict(
                    model=case["model"],
                    label=case["label"],
                    expectation=expectation,
                    accepted=accepted,
                    preserved=preserved,
                )
            )
    counts = dict(
        invalid=len(bad),
        invalid_accepted=sum(
            r["accepted"] for r in rows if r["expectation"] == "reject"
        ),
        valid=len(valid),
        valid_rejected=sum(
            not r["accepted"] for r in rows if r["expectation"] == "preserve"
        ),
        valid_changed=sum(
            r["accepted"] and not r["preserved"]
            for r in rows
            if r["expectation"] == "preserve"
        ),
    )
    return dict(
        reference_pin=PIN,
        counts=counts,
        rows=rows,
        selected_outline_checks_passed=not any(
            counts[k] for k in ["invalid_accepted", "valid_rejected", "valid_changed"]
        ),
        new_classical_examples=0,
        new_model_processes=0,
        original_classical_gate="not regraded by this fragment audit",
        complete_classical_conformance=False,
        goal_complete=False,
        real_world_validation="deferred_by_user",
    )


def business_results() -> list[dict[str, Any]]:
    from fatebridge.services.tool_catalog import CATALOG

    payload = json.loads(
        (ROOT / "tests/fixtures/jinkou_pattern_anchors_v1/protocol.json").read_text()
    )["payload"]
    spec = next(s for s in CATALOG if s.key == "jinkou")
    result = []
    extras: list[dict[str, Any]] = [
        {},
        dict(birth_year_ganzhi="甲午", year_fate_age=20, gender="男"),
        dict(natal_branch="卯"),
    ]
    for extra in extras:
        request = {**payload, **extra}
        fn, args, kwargs = spec.bind(spec.request_model.model_validate(request))
        result.append(dict(request=request, business=fn(*args, **kwargs)))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--capture-business", type=Path)
    parser.add_argument("--compare-business", type=Path)
    args = parser.parse_args()
    result = audit()
    if args.capture_business:
        raw = json.dumps(
            business_results(), ensure_ascii=False, separators=(",", ":")
        ).encode()
        args.capture_business.write_bytes(gzip.compress(raw, mtime=0))
        result["business_baseline_sha256"] = sha(args.capture_business)
    if args.compare_business:
        before = json.loads(gzip.decompress(args.compare_business.read_bytes()))
        after = business_results()
        result["business_compared"] = len(after)
        result["business_unchanged"] = before == after
        result["selected_outline_checks_passed"] &= before == after
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False)
    )
    raise SystemExit(0 if result["selected_outline_checks_passed"] else 1)


if __name__ == "__main__":
    main()
