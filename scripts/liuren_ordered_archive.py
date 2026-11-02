"""Explicit offline annotations: never write goldens or relax live validation."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/liuren_ordered_archive_v1"
PIN = "a410a2ba55c25152691ff183b8d214e3452380c292c4825519fcb0e7267e4c74"
RULE = "liuren.ordered_transmission_patterns"


def reference() -> None:
    from scripts.audit_liuren_ordered_patterns import FREEZE_SHA256
    from scripts.audit_liuren_ordered_patterns import reference as source_reference

    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    if sha(CORPUS / "freeze.json") != PIN:
        raise ValueError("Frozen ordered archive protocol changed")
    frozen = json.loads((CORPUS / "freeze.json").read_text())
    if set(frozen["files"]) != {"protocol.json"} or {
        p.name for p in CORPUS.iterdir()
    } != {"protocol.json", "freeze.json"}:
        raise ValueError("Frozen ordered archive inventory changed")
    if sha(CORPUS / "protocol.json") != frozen["files"]["protocol.json"]:
        raise ValueError("Frozen ordered archive scope changed")
    protocol = json.loads((CORPUS / "protocol.json").read_text())
    if protocol["source_reference_manifest_sha256"] != FREEZE_SHA256:
        raise ValueError("Ordered archive source reference changed")
    source_reference()


def canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def historical_ordered_patterns(
    value: dict[str, Any], *, mode: Literal["add", "strip"] = "add"
) -> tuple[dict[str, Any], dict[str, Any]]:
    from fatebridge.core.metaphysics.liureng_ordered_patterns import (
        ordered_patterns_trace,
        ordered_transmission_patterns,
    )

    reference()
    if mode not in ("add", "strip"):
        raise ValueError("Unknown ordered archive operation")
    result = copy.deepcopy(value)
    changes: list[dict[str, Any]] = []
    for prefix in ("liureng", "subresults.liureng_gods.liureng"):
        board: Any = result
        for part in prefix.split("."):
            board = board.get(part) if isinstance(board, dict) else None
        if board is None:
            continue
        if (
            not isinstance(board, dict)
            or not isinstance(board.get("transmission_relations"), dict)
            or not isinstance(board.get("rule_trace"), list)
        ):
            raise ValueError(
                "Archive annotation requires existing relations and traces"
            )
        transmissions = board.get("three_transmissions", {})
        if not isinstance(transmissions, dict) or any(
            not isinstance(transmissions.get(p), dict)
            for p in ("initial", "middle", "final")
        ):
            raise ValueError("Archive annotation needs three recorded transmissions")
        if any(not isinstance(t, dict) for t in board["rule_trace"]):
            raise ValueError("Archive annotation needs recorded trace objects")
        branches = [
            transmissions.get(p, {}).get("branch")
            for p in ("initial", "middle", "final")
        ]
        expected = ordered_transmission_patterns(branches)
        relations = board["transmission_relations"]
        trace = ordered_patterns_trace(expected)
        traces = [t for t in board["rule_trace"] if t.get("rule_id") == RULE]
        has = "named_structures" in relations
        if has != bool(traces) or len(traces) > 1:
            raise ValueError("Archive annotation is partial or has duplicate traces")
        if has and (
            canonical(relations["named_structures"]) != canonical(expected)
            or canonical(traces[0]) != canonical(trace)
        ):
            raise ValueError("Archive annotation cannot repair supplied wrong facts")
        if mode == "add" and not has:
            old = copy.deepcopy(board["rule_trace"])
            relations["named_structures"] = expected
            board["rule_trace"].append(trace)
            changes.extend(
                [
                    dict(
                        path=prefix + ".transmission_relations.named_structures",
                        kind="added",
                        new=copy.deepcopy(expected),
                    ),
                    dict(
                        path=prefix + ".rule_trace",
                        kind="changed",
                        old=old,
                        new=copy.deepcopy(board["rule_trace"]),
                    ),
                ]
            )
        elif mode == "strip" and has:
            old = copy.deepcopy(board["rule_trace"])
            del relations["named_structures"]
            board["rule_trace"] = [
                t for t in board["rule_trace"] if t.get("rule_id") != RULE
            ]
            changes.extend(
                [
                    dict(
                        path=prefix + ".transmission_relations.named_structures",
                        kind="removed",
                        old=copy.deepcopy(expected),
                    ),
                    dict(
                        path=prefix + ".rule_trace",
                        kind="changed",
                        old=old,
                        new=copy.deepcopy(board["rule_trace"]),
                    ),
                ]
            )
    # Reversing this exact ledger must reproduce every old field and array.
    reverse = copy.deepcopy(result)
    for change in reversed(changes):
        parts = change["path"].split(".")
        parent = reverse
        for part in parts[:-1]:
            parent = parent[part]
        if change["kind"] == "added":
            del parent[parts[-1]]
        else:
            parent[parts[-1]] = copy.deepcopy(change["old"])
    if canonical(reverse) != canonical(value):
        raise ValueError("Archive annotation did not preserve original fields")
    return result, dict(
        changes=changes,
        existing_fields_unchanged=True,
        original_object_restored_exactly=True,
        supplement_computed_now=True,
        not_a_historical_or_live_receipt=True,
        golden_files_written=False,
        protocol_sha256=PIN,
    )
