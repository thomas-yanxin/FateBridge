"""Apply immutable same-edition quotation errata to generated profiles."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

FREEZE_SHA256 = "5cf1ffba164a80ac5e05abf188cf3ec304c772398b8d2cbb16abda6e173501e2"


def apply_quote_errata(
    profile: dict[str, Any], *, root: Path, original: Path, artifact: str
) -> dict[str, Any]:
    reference = root / "tests/fixtures/liuyao_quote_collation_v43"
    freeze_path = reference / "freeze.json"
    if hashlib.sha256(freeze_path.read_bytes()).hexdigest() != FREEZE_SHA256:
        raise ValueError("Frozen same-edition quotation manifest changed")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    for name, expected in freeze["files_sha256"].items():
        path = (reference / name).resolve()
        if not path.is_relative_to(reference.resolve()):
            raise ValueError("Quotation material escaped its fixture directory")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen same-edition quotation material changed: {name}")
    errata = json.loads((reference / "errata.json").read_text(encoding="utf-8"))
    transcription = json.loads(
        (reference / "transcription.json").read_text(encoding="utf-8")
    )
    records = [r for r in errata["corrections"] if r["artifact"] == artifact]
    if len(records) != 1:
        raise ValueError("Expected one identified quotation correction per profile")
    correction = records[0]
    if (
        hashlib.sha256(original.read_bytes()).hexdigest()
        != correction["original_profile_sha256"]
        or profile["source"]["sha256"] != correction["source_sha256"]
        or transcription["source_sha256"] != correction["source_sha256"]
    ):
        raise ValueError("Quotation correction detached from its original profile")
    passage = next(
        p for p in transcription["passages"] if p["id"] == correction["passage_id"]
    )
    if (
        passage["text"] != correction["new_quote"]
        or passage["pdf_page"] != correction["pdf_page"]
        or passage["image_sha256"] != correction["source_image_sha256"]
    ):
        raise ValueError("Quotation correction detached from its scanned passage")
    result = deepcopy(profile)
    clauses = [c for c in result["clauses"] if c["id"] == correction["clause_id"]]
    if len(clauses) != 1 or clauses[0]["quote"] != correction["old_quote"]:
        raise ValueError("Quotation correction does not match the original clause")
    clauses[0]["quote"] = correction["new_quote"]
    clauses[0]["quotation_revision"] = correction["revision"]
    result["ruleset_version"] = correction["new_ruleset_version"]
    result["quotation_errata"] = deepcopy(records)
    return result
