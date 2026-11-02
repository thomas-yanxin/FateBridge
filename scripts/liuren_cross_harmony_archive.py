"""Reversible offline additions; original answers and live validation stay intact."""

from __future__ import annotations

import copy
from typing import Any, Literal

from scripts.liuren_day_placement_archive import PREFIXES, at, canonical, restore

RULE = "liuren.cross_harmony"
SUFFIX = "、交车六合条件"


def strip_board(board: dict[str, Any], day: str) -> dict[str, Any]:
    from fatebridge.core.metaphysics.liureng_cross_harmony import (
        CONVENTION,
        cross_harmony,
        cross_harmony_trace,
    )

    result = copy.deepcopy(board)
    rows = result.get("twelve_board")
    if not isinstance(rows, list) or len(rows) != 12:
        raise ValueError(
            "Offline cross-harmony comparison needs twelve recorded positions"
        )
    expected = cross_harmony(
        day, {r.get("earth_branch"): r.get("sky_branch") for r in rows}
    )
    traces = result.get("rule_trace")
    if not isinstance(traces, list):
        raise ValueError("Offline cross-harmony comparison needs recorded traces")
    selected = [t for t in traces if t.get("rule_id") == RULE]
    present = "cross_harmony" in result
    if present != bool(selected) or len(selected) > 1:
        raise ValueError("Offline cross-harmony fields or traces are partial")
    if present:
        if canonical(result["cross_harmony"]) != canonical(expected) or canonical(
            selected
        ) != canonical([cross_harmony_trace(expected)]):
            raise ValueError("Offline comparison cannot hide wrong cross-harmony facts")
        result.pop("cross_harmony")
        result["rule_trace"] = [t for t in traces if t.get("rule_id") != RULE]
    rules = result["ruleset"]
    conventions = rules.get("conventions", {})
    if "cross_harmony" in conventions or rules["source_title"].endswith(SUFFIX):
        if (
            not present
            or rules["version"] != "1.16.0"
            or not rules["source_title"].endswith(SUFFIX)
            or conventions.get("cross_harmony") != CONVENTION
        ):
            raise ValueError(
                "Offline cross-harmony metadata is not the declared addition"
            )
        conventions.pop("cross_harmony")
        rules["source_title"] = rules["source_title"][: -len(SUFFIX)]
        rules["version"] = "1.15.0"
    return result


def historical_cross_harmony(
    value: dict[str, Any], *, mode: Literal["add", "strip"] = "add"
) -> tuple[dict[str, Any], dict[str, Any]]:
    from fatebridge.core.metaphysics.liureng_cross_harmony import (
        cross_harmony,
        cross_harmony_trace,
    )
    from scripts.audit_liuren_cross_harmony import reference

    reference()
    if mode not in ("add", "strip"):
        raise ValueError("Unknown offline cross-harmony operation")
    result = copy.deepcopy(value)
    changes = []
    new_titles = []
    for prefix in PREFIXES:
        board = at(result, prefix)
        if board is None:
            continue
        if (
            mode == "strip"
            and "cross_harmony" not in board
            and not any(t.get("rule_id") == RULE for t in board.get("rule_trace", []))
            and "cross_harmony" not in board.get("ruleset", {}).get("conventions", {})
        ):
            continue
        day = board.get("calendar_policy", {}).get("effective_day_ganzhi")
        if board.get("transmission_relations", {}).get("day_ganzhi") != day:
            raise ValueError("Offline cross-harmony cannot repair the recorded day")
        checked = strip_board(board, day)
        if mode == "strip":
            if checked != board:
                old = copy.deepcopy(board)
                if (
                    board["ruleset"]["source_title"]
                    != checked["ruleset"]["source_title"]
                ):
                    new_titles.append(board["ruleset"]["source_title"])
                board.clear()
                board.update(checked)
                # Leaf restoration preserves shared root/nested board aliases
                # in raw service objects as well as independent JSON objects.
                changes.extend(
                    [
                        dict(
                            path=prefix + ".cross_harmony",
                            kind="removed",
                            old=old["cross_harmony"],
                        ),
                        dict(
                            path=prefix + ".rule_trace",
                            kind="changed",
                            old=old["rule_trace"],
                            new=copy.deepcopy(board["rule_trace"]),
                        ),
                    ]
                )
                for key in ("version", "source_title"):
                    if old["ruleset"][key] != board["ruleset"][key]:
                        changes.append(
                            dict(
                                path=prefix + ".ruleset." + key,
                                kind="changed",
                                old=old["ruleset"][key],
                                new=board["ruleset"][key],
                            )
                        )
                if "cross_harmony" in old["ruleset"].get("conventions", {}):
                    changes.append(
                        dict(
                            path=prefix + ".ruleset.conventions.cross_harmony",
                            kind="removed",
                            old=old["ruleset"]["conventions"]["cross_harmony"],
                        )
                    )
        elif "cross_harmony" not in board:
            sky = {r["earth_branch"]: r["sky_branch"] for r in board["twelve_board"]}
            evidence = cross_harmony(day, sky)
            old_trace = copy.deepcopy(board["rule_trace"])
            board["cross_harmony"] = evidence
            board["rule_trace"].append(cross_harmony_trace(evidence))
            changes.extend(
                [
                    dict(
                        path=prefix + ".cross_harmony",
                        kind="added",
                        new=copy.deepcopy(evidence),
                    ),
                    dict(
                        path=prefix + ".rule_trace",
                        kind="changed",
                        old=old_trace,
                        new=copy.deepcopy(board["rule_trace"]),
                    ),
                ]
            )
    profiles = at(result, "synthesis.source_profiles.liureng")
    if mode == "strip" and isinstance(profiles, list):
        old = copy.deepcopy(profiles)
        for profile in profiles:
            if profile.get("source_title") in new_titles:
                if profile.get("version") != "1.16.0":
                    raise ValueError("Propagated cross-harmony metadata disagrees")
                profile["source_title"] = profile["source_title"][: -len(SUFFIX)]
                profile["version"] = "1.15.0"
        if profiles != old:
            changes.append(
                dict(
                    path="synthesis.source_profiles.liureng",
                    kind="changed",
                    old=old,
                    new=copy.deepcopy(profiles),
                )
            )
    if canonical(restore(result, changes)) != canonical(value):
        raise ValueError("Offline cross-harmony operation is not reversible")
    return result, dict(
        operation=mode,
        changes=changes,
        original_restored_exactly=True,
        golden_files_written=False,
        live_validation_bypassed=False,
        old_gates_redefined=False,
    )
