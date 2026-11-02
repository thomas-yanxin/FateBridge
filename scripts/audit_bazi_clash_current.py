"""Replay exposed source labels through the actual public strength entry point."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
ORDER = ("year", "month", "day", "hour")
GROUPS = {
    "legacy": "tests/fixtures/bazi-strength-reference.json",
    "original": "tests/fixtures/bazi_classical_v1/cases.json",
    "hurt": "tests/fixtures/bazi_strength_expansion_v1/reference.json",
    "root": "tests/fixtures/bazi_root_force_experiment_v1/reference.json",
    "neutrality": "tests/fixtures/bazi_root_force_experiment_v2/reference.json",
    "passage": "tests/fixtures/bazi_root_force_experiment_v3/reference.json",
    "dizhi": "tests/fixtures/bazi_clash_season_v1/reference.json",
    "ganzhi": "tests/fixtures/bazi_clash_season_v2/reference.json",
    "shape_bureau_and_tail": "tests/fixtures/bazi_clash_power_v3/reference.json",
}


def fingerprint(
    groups: Mapping[str, str] | None = None, extra_paths: tuple[str, ...] = ()
) -> dict[str, str]:
    paths = [
        p
        for p in (ROOT / "src/fatebridge").rglob("*")
        if p.is_file() and p.suffix in {".py", ".json"}
    ]
    selected = GROUPS if groups is None else groups
    paths += [ROOT / value for value in selected.values()]
    paths += [Path(__file__), ROOT / "uv.lock"]
    paths += [ROOT / relative for relative in extra_paths]
    return {
        str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest()
        for p in sorted(paths)
    }


def audit(
    groups_to_replay: Mapping[str, str] | None = None,
    *,
    source_view_registry: Path | None = None,
) -> dict[str, Any]:
    selected = dict(GROUPS if groups_to_replay is None else groups_to_replay)
    documents = None
    extra_paths = ()
    if source_view_registry is not None:
        from fatebridge.validation.bazi_source_corpus import load_registry
        from fatebridge.validation.bazi_source_inputs import source_documents

        registry = load_registry(ROOT, source_view_registry)
        if selected != registry["groups"]:
            raise ValueError("Source view replay must retain all registered groups")
        extra_paths = (
            str(source_view_registry.relative_to(ROOT)),
            *registry["auxiliary_sha256"],
        )
        documents, _, _ = source_documents(ROOT, registry)
    before = fingerprint(selected, extra_paths)
    from fatebridge.core.elements import ElementAnalysis
    from fatebridge.core.strength import assess_strength

    groups = {}
    mismatches: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for group, relative in selected.items():
        document = (
            json.loads((ROOT / relative).read_text())
            if documents is None
            else documents[group]
        )
        cases = (
            document
            if isinstance(document, list)
            else document["cases"] + document.get("additional_cases", [])
        )
        rows = []
        for case in cases:
            raw = case["pillars"]
            values = [raw[k] for k in ORDER] if isinstance(raw, dict) else raw
            pillars = dict(zip(ORDER, map(tuple, values)))
            result = assess_strength(
                pillars, ElementAnalysis.seasonal_phases(pillars["month"][1])
            )
            expected = case.get(
                "expected_strength", case.get("adjudication", {}).get("strength")
            )
            row = {
                "id": case["id"],
                "pillars": values,
                "expected_strength": expected,
                "actual_strength": result["strength_level"],
                "method_id": result["method_id"],
                "matches": (
                    None if expected is None else result["strength_level"] == expected
                ),
                "assessment": result,
            }
            rows.append(row)
            if row["matches"] is False:
                mismatches.setdefault(tuple(values), []).append(
                    {
                        "group": group,
                        "id": case["id"],
                        "expected_strength": expected,
                        "actual_strength": result["strength_level"],
                    }
                )
        groups[group] = {
            "cases": len(rows),
            "adjudicated": sum(r["expected_strength"] is not None for r in rows),
            "unknown": sum(r["expected_strength"] is None for r in rows),
            "matched": sum(r["matches"] is True for r in rows),
            "rows": rows,
        }
    if source_view_registry is not None:
        source_documents(ROOT, load_registry(ROOT, source_view_registry))
    after = fingerprint(selected, extra_paths)
    return {
        "scope": "Selected exposed source groups only; not an automatically complete source corpus, a candidate experiment, fresh accuracy, expert review or real-world validation. Group counts overlap and cannot be summed. Use audit_bazi_source_corpus.py for the registered current corpus.",
        "selected_source_groups": selected,
        "source_fingerprints_before": before,
        "source_fingerprints_after": after,
        "source_drift": [
            p for p in before.keys() | after.keys() if before.get(p) != after.get(p)
        ],
        "public_entry_point": "fatebridge.core.strength.assess_strength",
        "groups": groups,
        "distinct_mismatches": [
            {"pillars": list(k), "source_observations": v}
            for k, v in mismatches.items()
        ],
        "classical_acceptance_passed": False,
        "real_world_efficacy": "not_tested",
        "authority_certified": False,
        "overall_score": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output exists; preserve prior replay")
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
