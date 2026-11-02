"""Apply reviewed implementation bindings without rewriting sealed knowledge."""

from __future__ import annotations

import ast
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
BINDING_FILE = PACKAGE_ROOT / "data/knowledge/bazi-structure-binding.json"


def _function_digest(text: str, name: str) -> str:
    node = next(
        n
        for n in ast.walk(ast.parse(text))
        if isinstance(n, ast.FunctionDef) and n.name == name
    )
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


def revalidate_structure_curation(
    category: str, key: str, curation: dict[str, Any]
) -> dict[str, Any]:
    """Require an approved file AND policy binding, never bless a fresh hash."""
    if category != "structures":
        return deepcopy(curation)
    review = json.loads(BINDING_FILE.read_text(encoding="utf-8"))
    if (
        review.get("schema_version") != 1
        or review.get("review_id") != "bazi_structure_implementation_revalidation_v1"
        or key not in review.get("keys", [])
    ):
        raise RuntimeError("Unreviewed BaZi structure implementation binding")
    previous = curation["implementation_refs"][0]
    if previous != review["previous_ref"]:
        raise RuntimeError("BaZi structure historical reference changed")
    for relative, expected in review["current_package_files"].items():
        path = (PACKAGE_ROOT / relative).resolve()
        if not path.is_relative_to(PACKAGE_ROOT.resolve()):
            raise RuntimeError("BaZi implementation reference escapes package")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise RuntimeError("BaZi implementation bytes need renewed review")
    text = (PACKAGE_ROOT / "core/classical.py").read_text(encoding="utf-8")
    for name, expected in review["unchanged_month_function_ast_sha256"].items():
        if _function_digest(text, name) != expected:
            raise RuntimeError("BaZi month selection policy needs renewed review")
    result = deepcopy(curation)
    result.setdefault("implementation_ref_history", []).append(
        {
            "previous_ref": deepcopy(previous),
            "review_id": review["review_id"],
            "reason": review["change_scope"],
        }
    )
    result["implementation_refs"][0] = {
        **previous,
        "source_sha256": review["current_package_files"]["core/classical.py"],
        "functions": list(review["unchanged_month_function_ast_sha256"]),
        "function_ast_sha256": review["unchanged_month_function_ast_sha256"],
        "binding_review_id": review["review_id"],
    }
    result["implementation_revalidation"] = {
        "review_id": review["review_id"],
        "binding_revision": 1,
        "record": "data/knowledge/bazi-structure-binding.json",
        "record_sha256": hashlib.sha256(BINDING_FILE.read_bytes()).hexdigest(),
        "change_scope": review["change_scope"],
        "policy_equivalence_scope": review["policy_equivalence_scope"],
        "historical_entry_revision_preserved": curation["entry_revision"],
        "classical_acceptance_changed": False,
        "new_predictive_evidence": False,
    }
    return result
