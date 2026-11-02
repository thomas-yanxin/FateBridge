"""Reversible offline annotations; never rewrite archives or live validation."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/liuren_day_placements_archive_v1"
PIN = "b08e7fefd3a5d6b8f7bde66f66a389994aad5f151a1a1e09404d512cacedc136"
RULE = "liuren.day_placement_patterns"
PREFIXES = ("liureng", "subresults.liureng_gods.liureng")


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def at(value: dict[str, Any], path: str) -> Any:
    result: Any = value
    for part in path.split("."):
        result = result.get(part) if isinstance(result, dict) else None
    return result


def restore(value: dict[str, Any], changes: list[dict[str, Any]]) -> dict[str, Any]:
    value = copy.deepcopy(value)
    for change in reversed(changes):
        parent, _, key = change["path"].rpartition(".")
        target = at(value, parent) if parent else value
        if change["kind"] == "added":
            del target[key]
        else:
            target[key] = copy.deepcopy(change["old"])
    return value


def reference() -> None:
    from scripts.audit_liuren_day_placements import PIN as SOURCE_PIN
    from scripts.audit_liuren_day_placements import reference as source_reference

    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if sha(CORPUS / "freeze.json") != PIN:
        raise ValueError("Day-placement archive identity changed")
    files = json.loads((CORPUS / "freeze.json").read_text())["files"]
    if set(files) != {"protocol.json"} or {p.name for p in CORPUS.iterdir()} != {
        "protocol.json",
        "freeze.json",
    }:
        raise ValueError("Day-placement archive inventory changed")
    if sha(CORPUS / "protocol.json") != files["protocol.json"]:
        raise ValueError("Day-placement archive protocol changed")
    protocol = json.loads((CORPUS / "protocol.json").read_text())
    if (
        protocol["source_reference_pin"] != SOURCE_PIN
        or tuple(protocol["prefixes"]) != PREFIXES
    ):
        raise ValueError("Day-placement archive source or scope changed")
    source_reference()


def historical_day_placements(
    value: dict[str, Any], *, mode: Literal["add", "strip"] = "add"
) -> tuple[dict[str, Any], dict[str, Any]]:
    from fatebridge.core.metaphysics.liureng_day_placements import (
        day_placement_patterns,
        day_placements_trace,
    )

    reference()
    if mode not in ("add", "strip"):
        raise ValueError("Unknown day-placement archive operation")
    result = copy.deepcopy(value)
    changes: list[dict[str, Any]] = []
    for prefix in PREFIXES:
        board = at(result, prefix)
        if board is None:
            continue
        rows = board.get("twelve_board") if isinstance(board, dict) else None
        if (
            not isinstance(rows, list)
            or len(rows) != 12
            or any(not isinstance(r, dict) for r in rows)
        ):
            raise ValueError("Archive annotation requires twelve recorded positions")
        day = board.get("calendar_policy", {}).get("effective_day_ganzhi")
        if board.get("transmission_relations", {}).get("day_ganzhi") != day:
            raise ValueError("Archive annotation cannot repair the recorded day")
        sky = {r.get("earth_branch"): r.get("sky_branch") for r in rows}
        expected = day_placement_patterns(day, sky)
        trace = day_placements_trace(expected)
        traces = board.get("rule_trace")
        if not isinstance(traces, list) or any(not isinstance(t, dict) for t in traces):
            raise ValueError("Archive annotation requires recorded traces")
        selected = [t for t in traces if t.get("rule_id") == RULE]
        has = "day_placement_patterns" in board
        if has != bool(selected) or len(selected) > 1:
            raise ValueError("Archive day placements are partial or duplicated")
        if has and (
            canonical(board["day_placement_patterns"]) != canonical(expected)
            or canonical(selected) != canonical([trace])
        ):
            raise ValueError(
                "Archive operation cannot hide supplied wrong day placements"
            )
        if mode == "add" and not has:
            old_trace = copy.deepcopy(traces)
            board["day_placement_patterns"] = expected
            traces.append(trace)
            changes.extend(
                [
                    dict(
                        path=prefix + ".day_placement_patterns",
                        kind="added",
                        new=copy.deepcopy(expected),
                    ),
                    dict(
                        path=prefix + ".rule_trace",
                        kind="changed",
                        old=old_trace,
                        new=copy.deepcopy(traces),
                    ),
                ]
            )
        elif mode == "strip" and has:
            old_trace = copy.deepcopy(traces)
            del board["day_placement_patterns"]
            board["rule_trace"] = [t for t in traces if t.get("rule_id") != RULE]
            changes.extend(
                [
                    dict(
                        path=prefix + ".day_placement_patterns",
                        kind="removed",
                        old=copy.deepcopy(expected),
                    ),
                    dict(
                        path=prefix + ".rule_trace",
                        kind="changed",
                        old=old_trace,
                        new=copy.deepcopy(board["rule_trace"]),
                    ),
                ]
            )
    if canonical(restore(result, changes)) != canonical(value):
        raise ValueError("Archive day-placement ledger is not reversible")
    return result, dict(
        changes=changes,
        existing_fields_unchanged=True,
        original_object_restored_exactly=True,
        supplement_computed_now=True,
        not_a_historical_or_live_receipt=True,
        golden_files_written=False,
        protocol_sha256=PIN,
    )


def legacy_candidate_day_placements(
    value: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Undo only the new, validated layer before the unchanged old audit gates."""
    from fatebridge.core.metaphysics.liureng_day_placements import CONVENTION

    result, annotations = historical_day_placements(value, mode="strip")
    metadata: list[dict[str, Any]] = []
    titles = []
    for prefix in PREFIXES:
        board = at(result, prefix)
        if board is None:
            continue
        rules = board["ruleset"]
        conventions = rules.get("conventions", {})
        suffix = "、干支加临课体"
        if "day_placement_patterns" not in conventions and not rules[
            "source_title"
        ].endswith(suffix):
            continue
        if (
            rules["version"] != "1.15.0"
            or not rules["source_title"].endswith(suffix)
            or conventions.get("day_placement_patterns") != CONVENTION
        ):
            raise ValueError("Live day-placement metadata is not the declared addition")
        for name, new in (
            ("version", "1.14.0"),
            ("source_title", rules["source_title"][: -len(suffix)]),
        ):
            metadata.append(
                dict(
                    path=prefix + ".ruleset." + name,
                    kind="changed",
                    old=rules[name],
                    new=new,
                )
            )
            rules[name] = new
        titles.append(rules["source_title"])
        metadata.append(
            dict(
                path=prefix + ".ruleset.conventions.day_placement_patterns",
                kind="removed",
                old=conventions.pop("day_placement_patterns"),
            )
        )
    profiles = at(result, "synthesis.source_profiles.liureng")
    if isinstance(profiles, list):
        old = copy.deepcopy(profiles)
        for profile in profiles:
            if profile.get("source_title") in [t + "、干支加临课体" for t in titles]:
                if profile.get("version") != "1.15.0":
                    raise ValueError(
                        "Propagated day-placement source version disagrees"
                    )
                profile["source_title"] = profile["source_title"][
                    : -len("、干支加临课体")
                ]
                profile["version"] = "1.14.0"
        if profiles != old:
            metadata.append(
                dict(
                    path="synthesis.source_profiles.liureng",
                    kind="changed",
                    old=old,
                    new=copy.deepcopy(profiles),
                )
            )
    changes = annotations["changes"] + metadata
    if canonical(restore(result, changes)) != canonical(value):
        raise ValueError("Offline candidate compatibility is not reversible")
    return result, dict(
        annotation_check=annotations,
        metadata_changes=metadata,
        original_candidate_restored_exactly=True,
        live_validation_bypassed=False,
        old_gates_redefined=False,
    )
