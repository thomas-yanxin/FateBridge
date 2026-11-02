"""Replay all exposed receipt links without changing force or source labels."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.output_bazi_evidence import BaziEvidenceChain

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_passage_relations_v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(path: Path) -> Any:
    raw = path.read_bytes()
    if digest(path) != Path(str(path) + ".sha256").read_text().strip():
        raise ValueError("Frozen source, counterexample or threshold changed")
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def audit() -> dict[str, Any]:
    protocol = frozen(FIXTURE / "protocol.json")
    before = frozen(FIXTURE / "before-source.json.gz")
    baseline = frozen(FIXTURE / "baseline-first.json.gz")
    for name, expected in protocol["preserved_references_sha256"].items():
        if digest(ROOT / name) != expected:
            raise ValueError(
                "Historical source, first failure or gate changed: " + name
            )
    for name in (
        "src/fatebridge/core/classical_passage.py",
        "src/fatebridge/core/output_classical_passage.py",
        "src/fatebridge/core/strength.py",
        "src/fatebridge/core/stem_effects.py",
        "src/fatebridge/services/replay_metadata.py",
        "src/fatebridge/application/result_delivery.py",
        "tests/test_bazi_passage_conditions.py",
        "tests/test_classical_passage_transports.py",
    ):
        if (ROOT / name).read_text() != before[name]:
            raise ValueError(
                "A preserved formula, passage or original gate changed: " + name
            )
    source_paths = [
        "src/fatebridge/core/passage_relations.py",
        "src/fatebridge/core/output_passage_relations.py",
        "src/fatebridge/core/bazi_evidence.py",
        "src/fatebridge/core/output_bazi_evidence.py",
        "src/fatebridge/core/output_bazi_anchors.py",
    ]
    fingerprints = {n: digest(ROOT / n) for n in source_paths}
    rows = []
    states: Counter[tuple[str, str]] = Counter()
    for row in baseline["rows"]:
        original = deepcopy(row)
        a = row["assessment"]
        pillars = dict(
            zip(("year", "month", "day", "hour"), map(tuple, row["pillars"]))
        )
        result = build_natal_evidence(
            pillars, {"assessment": a, "strength_level": a["strength_level"]}
        )
        BaziEvidenceChain.model_validate(result)
        context = result["classical_passage_relations"]
        if [e["receipt"] for e in context["events"]] != a["relations"]:
            raise ValueError(
                "A supplied original event was lost, relabelled or modified"
            )
        for e in context["events"]:
            states[(e["receipt"]["kind"], e["receipt"]["status"])] += 1
        legacy = {k: v for k, v in result.items() if k != "classical_passage_relations"}
        legacy["method_id"] = "bazi_position_prerequisites_v1"
        if legacy != row["natal_evidence"] or row != original:
            raise ValueError(
                "Existing natal, force, passage or original values changed: "
                + row["id"]
            )
        rows.append(
            {
                "group": row["group"],
                "id": row["id"],
                "pillars": row["pillars"],
                "context": context,
                "old_values_unchanged": True,
            }
        )
    corpus = frozen(
        ROOT / "docs/validation/bazi-complete-anchors-source-corpus-v1.json.gz"
    )
    explanations = []
    for case in corpus["original_nineteen"]:
        matching = [
            r for r in rows if r["id"] == case["id"] and r["pillars"] == case["pillars"]
        ]
        if not matching:
            raise ValueError("An original disagreement was omitted: " + case["id"])
        variants = []
        for row in matching:
            c = row["context"]
            claims = [
                {
                    "path": "classical_passage_relations.effective_passage",
                    "value": "not_adjudicated",
                },
                {
                    "path": "classical_passage_relations.calculation_effect",
                    "value": "none",
                },
            ]
            claims.extend(
                {
                    "path": f"classical_passage_relations.events.{i}.receipt.status",
                    "value": e["receipt"]["status"],
                }
                for i, e in enumerate(c["events"])
            )
            for claim in claims:
                actual: Any = {"classical_passage_relations": c}
                for key in claim["path"].split("."):
                    actual = (
                        actual[int(key)] if isinstance(actual, list) else actual[key]
                    )
                if actual != claim["value"]:
                    raise ValueError(
                        "Developer explanation claim conflicts with its receipt"
                    )
            variants.append(
                {
                    "group": row["group"],
                    "claims": claims,
                    "developer_explanation": "所列状态仅为同次工程模型记录；尚未裁定有效通关，不据此消除原典旺衰分歧。",
                }
            )
        explanations.append(
            {
                **case,
                "birth_instant_invented": False,
                "new_context_variants": variants,
                "review_kind": "developer_structured_claim_check_not_actual_model_or_independent_expert",
            }
        )
    if fingerprints != {n: digest(ROOT / n) for n in source_paths}:
        raise ValueError("Selected source changed during replay")
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": digest(FIXTURE / "protocol.json"),
        "runner_sha256": digest(Path(__file__)),
        "source_fingerprints": fingerprints,
        "record_count": len(rows),
        "raw_event_occurrences": sum(states.values()),
        "event_kind_status_pairs": [
            {"kind": k[0], "status": k[1], "occurrences": n}
            for k, n in sorted(states.items())
        ],
        "rows": rows,
        "original_nineteen_developer_explanation_checks": explanations,
        "all_existing_natal_and_passage_values_preserved_except_version_and_new_sibling": True,
        "legacy_classical_passage_source_and_schema_bytes_unchanged": True,
        "event_classifications_or_numeric_formulas_changed": False,
        "original_nineteen_unresolved": 19,
        "new_classical_correct_cases_credited": 0,
        "new_numeric_calculation_repairs": 0,
        "new_model_executions": 0,
        "independent_expert_acceptance": "not_completed",
        "new_actual_model_explanation_acceptance": "not_tested",
        "real_world_predictive_validity": "not_tested",
        "full_goal_complete": False,
        "overall_score": None,
        "scope": "Development replay of exposed records, including repeated inputs; retained event occurrences and node links are not independent source-error counts. No inference of missing birth dates or classical force.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Preserve first output; choose a fresh path")
    result = audit()
    raw = (
        json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()
    with args.output.open("xb") as handle:
        handle.write(gzip.compress(raw, mtime=0))
    Path(str(args.output) + ".sha256").write_text(digest(args.output) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "record_count",
                    "raw_event_occurrences",
                    "original_nineteen_unresolved",
                    "new_numeric_calculation_repairs",
                )
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
