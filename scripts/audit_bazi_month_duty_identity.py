"""Audit additive cross-chapter identities without recoding a force result."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import types
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fatebridge
from fatebridge.core.bazi_evidence import build_natal_evidence

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.sealed_bazi_runtime import ARCHIVE_SHA256, replay

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_month_duty_identity_v1"
DATA = ROOT / "src/fatebridge/data/bazi_month_duty_identity_v1.json"
ORDER = ("year", "month", "day", "hour")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> Any:
    value = path.read_bytes()
    return json.loads(gzip.decompress(value) if path.suffix == ".gz" else value)


def frozen(path: Path) -> Any:
    if digest(path) != Path(str(path) + ".sha256").read_text().split()[0]:
        raise ValueError("Frozen identity evidence changed: " + str(path))
    return read(path)


def legacy_builders() -> tuple[Any, Any]:
    before = frozen(FIXTURE / "before-source.json.gz")
    modules = []
    for name in ("month_duty_scan_reference", "month_duty_reference", "bazi_evidence"):
        module = types.ModuleType("_pre_identity_" + name)
        exec(
            compile(
                before["src/fatebridge/core/" + name + ".py"],
                "pre_identity_" + name + ".py",
                "exec",
            ),
            module.__dict__,
        )
        modules.append(module)
    scan, month, evidence = modules
    month.__dict__["build_month_duty_scan_reference"] = scan.__dict__[
        "build_month_duty_scan_reference"
    ]
    evidence.__dict__["build_month_duty_reference"] = month.__dict__[
        "build_month_duty_reference"
    ]
    return (
        evidence.__dict__["build_natal_evidence"],
        month.__dict__["build_month_duty_reference"],
    )


def without_identity(evidence: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(evidence)
    value["month_command"]["intra_month_duty"]["source_reference"][
        "scanned_witness"
    ].pop("cross_chapter_identities")
    return value


def audit() -> dict[str, Any]:
    program = """import json
from scripts.audit_bazi_month_duty_identity import _historical_audit
print(json.dumps(_historical_audit(), ensure_ascii=False, allow_nan=False))
"""
    result = replay(program, None, ROOT)
    if not isinstance(result, dict):
        raise ValueError("Historical identity audit returned no report")
    return result


def _historical_audit() -> dict[str, Any]:
    protocol = frozen(FIXTURE / "protocol.json")
    before = frozen(FIXTURE / "before-source.json.gz")
    source = frozen(FIXTURE / "witness-first.json")
    freeze = frozen(FIXTURE / "transcription-freeze.json")
    extraction = frozen(FIXTURE / "extraction-manifest.json")
    if DATA.read_bytes() != (FIXTURE / "witness-first.json").read_bytes():
        raise ValueError("Published identity layer differs from its first reading")
    if freeze["witness_sha256"] != digest(DATA):
        raise ValueError("Identity first-reading freeze changed")
    for name, expected in protocol["preserved_references_sha256"].items():
        if digest(ROOT / name) != expected:
            raise ValueError("An original counterexample, witness or gate changed")
    unchanged = [
        "src/fatebridge/data/bazi_month_duty_sources_v1.json",
        "src/fatebridge/data/bazi_month_duty_scan_v1.json",
        "src/fatebridge/core/month_duty_reference.py",
        "src/fatebridge/core/bazi_evidence.py",
        "src/fatebridge/core/strength.py",
        "src/fatebridge/core/stem_effects.py",
        "src/fatebridge/core/classical_force.py",
        "src/fatebridge/core/classical_passage.py",
        "src/fatebridge/core/classical_roots.py",
    ]
    runtime_root = Path(fatebridge.__file__).resolve().parents[2]
    for name in unchanged:
        original = (
            ROOT if name.startswith("src/fatebridge/data/") else runtime_root
        ) / name
        if original.read_text() != before[name]:
            raise ValueError("A preserved calculation/source file changed: " + name)
    if (
        digest(ROOT / extraction["source_pdf"]) != source["source"]["source_pdf_sha256"]
        or digest(FIXTURE / "chapter9-36.pdf") != extraction["excerpt_sha256"]
        or extraction["source_pdf_sha256"] != source["source"]["source_pdf_sha256"]
        or [r["original_pdf_page"] for r in extraction["pages"]] != list(range(9, 37))
        or not all(r["original_excerpt_pixels_equal"] for r in extraction["pages"])
    ):
        raise ValueError("Complete chapter/boundary binding changed")
    anchors = {r["id"]: r for r in source["anchors"]}
    if len(anchors) != len(source["anchors"]):
        raise ValueError("Source anchor id repeated")
    for anchor in anchors.values():
        if not anchor["literal_quote"] or not set(anchor["original_pdf_pages"]) <= set(
            source["source"]["chapter_original_pdf_pages"]
        ):
            raise ValueError("Anchor lacks a chapter page or literal reading")
    for claim in source["identity_claims"]:
        for name in claim["definition_anchor_ids"] + claim["context_anchor_ids"]:
            if name not in anchors:
                raise ValueError("Term references a missing source anchor")
    legacy, _ = legacy_builders()
    corpus = read(
        ROOT / "docs/validation/bazi-month-duty-scan-source-corpus-v1.json.gz"
    )
    rows = []
    for group, content in corpus["groups"].items():
        for row in content["rows"]:
            pillars = dict(zip(ORDER, map(tuple, row["pillars"]), strict=True))
            strength = dict(
                strength_level=row["actual_strength"], assessment=row["assessment"]
            )
            current = build_natal_evidence(pillars, strength)
            if without_identity(current) != legacy(pillars, strength):
                raise ValueError(
                    "An old full natal evidence value changed: " + row["id"]
                )
            identity = current["month_command"]["intra_month_duty"]["source_reference"][
                "scanned_witness"
            ]["cross_chapter_identities"]
            rows.append(
                dict(
                    group=group,
                    id=row["id"],
                    pillars=row["pillars"],
                    actual_strength=row["actual_strength"],
                    expected_strength=row["expected_strength"],
                    all_prior_evidence_values_identical=True,
                    identity_layer=identity,
                )
            )
    focus_notes = read(
        ROOT / "tests/fixtures/bazi_focus_validation_v1/source-focus-notes.json"
    )
    focus = []
    for note in focus_notes["cases"]:
        matching = [
            r for r in rows if r["id"] == note["id"] and r["pillars"] == note["pillars"]
        ]
        if not matching:
            raise ValueError("An original focus case disappeared")
        row = matching[0]
        if row["expected_strength"] != note["original_expected_strength"]:
            raise ValueError("Original focus label changed")
        layer = row["identity_layer"]
        if (
            layer["selected_duty_stem"] is not None
            or layer["effective_command_status"] != "not_adjudicated"
            or layer["calculation_effect"] != "none"
        ):
            raise ValueError("An identity became effective force or selected duty")
        focus.append(
            dict(
                id=note["id"],
                source_expected=note["original_expected_strength"],
                actual=row["actual_strength"],
                original_disagreement_remains=row["actual_strength"]
                != note["original_expected_strength"],
                exact_civil_birth_instant=note["exact_civil_birth_instant"],
                source_day_from_jie=note["day_from_jie_as_printed"],
                source_duty_stem=note["duty_stem_as_printed"],
                month_term_observations=layer["month_term_observations"],
                body_seal_and_passage_evidence_identical=True,
                effective_command_status=layer["effective_command_status"],
            )
        )
    return dict(
        recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        runner_sha256=digest(Path(__file__)),
        protocol_sha256=digest(FIXTURE / "protocol.json"),
        witness_sha256=digest(DATA),
        source_pdf_sha256=source["source"]["source_pdf_sha256"],
        chapter_pages=list(range(9, 36)),
        retained_pages=list(range(9, 37)),
        anchor_count=len(anchors),
        all_ten_stem_contexts_retained=True,
        rows=rows,
        record_count=len(rows),
        original_nineteen=focus,
        immutable_calculation_and_source_files=unchanged,
        immutable_files_scope="sealed_runtime_source_and_current_published_reference_data",
        numerical_runtime_archive_sha256=ARCHIVE_SHA256,
        first_chapter_only_identities_unchanged=True,
        new_classical_correct_cases_credited=0,
        new_force_rules_adopted=False,
        new_model_executions=0,
        independent_expert_acceptance="not_completed",
        source_review_scope="Same developer visual collation. Hashes bind the first reading and complete excerpt; they do not independently recognize the scan or prove absence elsewhere in the book.",
        real_world_predictive_validity="not_tested",
        full_goal_complete=False,
        overall_score=None,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Preserve the first result; choose a new output path")
    result = audit()
    data = (
        json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as handle:
        handle.write(
            gzip.compress(data, mtime=0) if args.output.suffix == ".gz" else data
        )
    Path(str(args.output) + ".sha256").write_text(digest(args.output) + "\n")
    print(
        json.dumps(
            dict(
                records=result["record_count"],
                anchors=result["anchor_count"],
                original_nineteen=len(result["original_nineteen"]),
                unresolved=sum(
                    r["original_disagreement_remains"]
                    for r in result["original_nineteen"]
                ),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
