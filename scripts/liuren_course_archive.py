"""Explicit offline annotations: never write goldens or relax live validation."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/liuren_course_archive_v1"
PIN = "6552390af2120eed7ab474fa136ddc7523bce9e90d118bf1d924ce08b909554e"
RULE = "liuren.course_conditions"


def reference() -> None:
    from scripts.audit_liuren_course_conditions import FREEZE_SHA256
    from scripts.audit_liuren_course_conditions import reference as source_reference

    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    if sha(CORPUS / "freeze.json") != PIN:
        raise ValueError("Frozen course archive protocol changed")
    frozen = json.loads((CORPUS / "freeze.json").read_text())
    if set(frozen["files"]) != {"protocol.json"} or {
        p.name for p in CORPUS.iterdir()
    } != {"protocol.json", "freeze.json"}:
        raise ValueError("Frozen course archive inventory changed")
    if sha(CORPUS / "protocol.json") != frozen["files"]["protocol.json"]:
        raise ValueError("Frozen course archive scope changed")
    protocol = json.loads((CORPUS / "protocol.json").read_text())
    if protocol["source_reference_manifest_sha256"] != FREEZE_SHA256:
        raise ValueError("Course archive source reference changed")
    source_reference()
    # New metadata makes additional source claims; keep the old gate and
    # independently check the new frozen primary witnesses before annotating.
    from scripts.audit_liuren_course_layout import reference as layout_reference

    layout_reference()


def canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def historical_course_conditions(
    value: dict[str, Any], *, mode: Literal["add", "strip"] = "add"
) -> tuple[dict[str, Any], dict[str, Any]]:
    from fatebridge.core.metaphysics.liureng_course_conditions import (
        course_conditions,
        course_conditions_trace,
    )
    from fatebridge.core.metaphysics.liureng_life_stages import life_stage_cycle

    reference()
    if mode not in ("add", "strip"):
        raise ValueError("Unknown course archive operation")
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
        day = board.get("calendar_policy", {}).get("effective_day_ganzhi")
        expected = course_conditions(day, transmissions)
        if board["transmission_relations"].get("day_ganzhi") != day:
            raise ValueError("Archive course day disagrees with recorded calendar")
        recorded_rows = board["transmission_relations"].get("rows")
        if not isinstance(recorded_rows, list) or len(recorded_rows) != 3:
            raise ValueError("Archive course needs three existing relation rows")
        for position, row in zip(("initial", "middle", "final"), recorded_rows):
            if not isinstance(row, dict) or row.get("position") != position:
                raise ValueError("Archive relation positions changed")
            for field in ("branch", "god", "earth_branch"):
                if row.get(field) != transmissions[position][field]:
                    raise ValueError(
                        "Archive course cannot repair recorded transmissions"
                    )
            if (
                row.get("day_stem_life_stage")
                != life_stage_cycle(day[0])[row["branch"]]
            ):
                raise ValueError("Archive course cannot repair recorded life stages")
        relations = board["transmission_relations"]
        trace = course_conditions_trace(expected)
        traces = [t for t in board["rule_trace"] if t.get("rule_id") == RULE]
        has = "course_conditions" in relations
        if has != bool(traces) or len(traces) > 1:
            raise ValueError("Archive annotation is partial or has duplicate traces")
        if has and (
            canonical(relations["course_conditions"]) != canonical(expected)
            or canonical(traces[0]) != canonical(trace)
        ):
            raise ValueError("Archive annotation cannot repair supplied wrong facts")
        if mode == "add" and not has:
            old = copy.deepcopy(board["rule_trace"])
            relations["course_conditions"] = expected
            board["rule_trace"].append(trace)
            changes.extend(
                [
                    dict(
                        path=prefix + ".transmission_relations.course_conditions",
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
            del relations["course_conditions"]
            board["rule_trace"] = [
                t for t in board["rule_trace"] if t.get("rule_id") != RULE
            ]
            changes.extend(
                [
                    dict(
                        path=prefix + ".transmission_relations.course_conditions",
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
