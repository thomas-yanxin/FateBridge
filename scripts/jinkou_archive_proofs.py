"""Add a declared, reversible *new* proof annotation to an old JSON envelope.

This does not write goldens, refresh a historical calculation, invent a live
receipt, or change any old fact. Existing proofs must already be complete and
correct; this adapter is never used by live service-output validation.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/jinkou_archive_proofs_v1"
ARCHIVE_SNAPSHOTS = ROOT / "tests/fixtures/ren_archive_snapshots_v1"
PIN = "a45e9a1689cb83b0c9e78c27bea545073027692e6953c604499c9bc899f50aca"
KEYS = ("condition_facts", "condition_logic")
RULE = "jinkou.structural_patterns"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference() -> dict[str, Any]:
    if sha(CORPUS / "freeze.json") != PIN:
        raise ValueError("Frozen archive-proof supplement changed")
    freeze = json.loads((CORPUS / "freeze.json").read_text())
    if {p.name for p in CORPUS.iterdir()} != set(freeze["files"]) | {
        "freeze.json"
    } or any(sha(CORPUS / n) != h for n, h in freeze["files"].items()):
        raise ValueError("Archive-proof supplement inventory changed")
    ref: dict[str, Any] = json.loads((CORPUS / "reference.json").read_text())
    if (
        sha(ROOT / "tests/fixtures/jinkou_pattern_proofs_v1/freeze.json")
        != ref["source_proof_pin"]
        or set(ref["new_top_pattern_keys"]) != set(KEYS)
        or ref["new_evaluation_key"] != "condition_groups"
        or ref["trace_rule_id"] != RULE
    ):
        raise ValueError(
            "Archive supplement differs from selected source and declared fields"
        )
    for slug in (
        "api_cn_liureng_gods",
        "api_cn_liureng_runyear",
        "api_cn_jinkou",
        "api_divination_sanshiunited",
    ):
        name = "tests/golden/snapshots/" + slug + ".json"
        if sha(ARCHIVE_SNAPSHOTS / (slug + ".json")) != ref["old_golden_sha256"][name]:
            raise ValueError(
                "This archive supplement cannot silently replace the pinned old golden"
            )
    return ref


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def historical_pattern_proofs(
    value: dict[str, Any], *, mode: Literal["add", "strip"] = "add"
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a copy and the exact reversible new-field ledger, never mutate input."""
    from fatebridge.core.metaphysics.jinkou_patterns import patterns_from_symbols

    ref = reference()
    result = copy.deepcopy(value)
    changes: list[dict[str, Any]] = []
    courses = []
    if mode not in ("add", "strip"):
        raise ValueError("Unknown archive supplement operation")

    def visit(board: dict[str, Any], prefix: str) -> None:
        rows = board.get("rows")
        policy = board.get("calendar_policy")
        day = policy.get("effective_day_ganzhi") if isinstance(policy, dict) else None
        if (
            not isinstance(rows, list)
            or len(rows) != 4
            or any(not isinstance(row, dict) for row in rows)
            or not isinstance(day, str)
            or any(
                not isinstance(row, dict) or not isinstance(row.get("dun_stem"), str)
                for row in rows[1:3]
            )
        ):
            raise ValueError(
                "Historical supplement needs existing complete symbols, day and recorded god/general stems"
            )
        expected = patterns_from_symbols(rows, day_ganzhi=day)
        facts = {f["id"]: f for f in expected["condition_facts"]}
        stems = facts["three_wonders"]["operands"]["stems"]
        if [row["dun_stem"] for row in rows[1:3]] != stems[1:]:
            raise ValueError(
                "Archive supplement cannot replace recorded stems with newly guessed inputs"
            )
        for identity, a, z in (
            ("same:H:G", 0, 1),
            ("same:G:J", 1, 2),
            ("same:J:D", 2, 3),
        ):
            operands = facts[identity]["operands"]
            if (
                rows[a].get("element") != operands["source_element"]
                or rows[z].get("element") != operands["target_element"]
            ):
                raise ValueError("Archive symbols and recorded phases disagree")
        for index, role in enumerate("HGJD"):
            for flag in ("si_da_kong", "xun_kong"):
                identity = flag + ":" + role
                if (
                    identity in facts
                    and rows[index].get(flag) is not facts[identity]["operands"]["flag"]
                ):
                    raise ValueError("Archive day and recorded empty flags disagree")
        if (
            len(expected["condition_facts"]) != ref["expected_fact_count"]
            or len(expected["evaluations"]) != ref["expected_catalog_count"]
        ):
            raise ValueError("Selected proof inventory changed")
        legacy = copy.deepcopy(expected)
        for key in KEYS:
            legacy.pop(key)
        for row in legacy["evaluations"]:
            row.pop("condition_groups")
        patterns = board.get("patterns")
        if not isinstance(patterns, dict):
            raise ValueError("Historical pattern ledger absent")
        evaluations = patterns.get("evaluations")
        if not isinstance(evaluations, list) or any(
            not isinstance(row, dict) for row in evaluations
        ):
            raise ValueError("Malformed historical pattern evaluations")
        full = any(key in patterns for key in KEYS) or any(
            "condition_groups" in row for row in evaluations
        )
        required = expected if full else legacy
        if patterns != required:
            raise ValueError(
                "Supplement cannot replace old predicates or repair wrong supplied proofs"
            )
        raw_traces = board.get("rule_trace")
        if not isinstance(raw_traces, list) or any(
            not isinstance(t, dict) for t in raw_traces
        ):
            raise ValueError("Malformed historical pattern traces")
        traces = [(i, t) for i, t in enumerate(raw_traces) if t.get("rule_id") == RULE]
        if len(traces) != 1:
            raise ValueError(
                "Historical supplement needs a unique matching pattern trace"
            )
        index, trace = traces[0]
        if trace.get("result") != required or any(
            trace.get(k) != expected[k] for k in ["source_url", "source_section"]
        ):
            raise ValueError("Historical body, trace and source are inconsistent")
        # Preserve JSON values while detaching any in-memory service aliases.
        board["patterns"] = copy.deepcopy(patterns)
        trace["result"] = copy.deepcopy(trace["result"])
        for destination, path in [
            (board["patterns"], prefix + ".patterns"),
            (trace["result"], prefix + f".rule_trace.{index}.result"),
        ]:
            if mode == "add" and not full:
                for key in KEYS:
                    destination[key] = copy.deepcopy(expected[key])
                    changes.append(
                        dict(
                            path=path + "." + key,
                            kind="added",
                            new=copy.deepcopy(expected[key]),
                        )
                    )
                for i, row in enumerate(destination["evaluations"]):
                    row["condition_groups"] = copy.deepcopy(
                        expected["evaluations"][i]["condition_groups"]
                    )
                    changes.append(
                        dict(
                            path=path + f".evaluations.{i}.condition_groups",
                            kind="added",
                            new=copy.deepcopy(row["condition_groups"]),
                        )
                    )
            elif mode == "strip" and full:
                for key in KEYS:
                    changes.append(
                        dict(
                            path=path + "." + key,
                            kind="removed",
                            old=destination.pop(key),
                        )
                    )
                for i, row in enumerate(destination["evaluations"]):
                    changes.append(
                        dict(
                            path=path + f".evaluations.{i}.condition_groups",
                            kind="removed",
                            old=row.pop("condition_groups"),
                        )
                    )
        courses.append(prefix)
        for key in ("natal_course", "year_fate"):
            wrapper = board.get(key)
            if wrapper is not None and not isinstance(wrapper, dict):
                raise ValueError("Malformed historical derived-course wrapper")
            child = wrapper.get("course") if isinstance(wrapper, dict) else None
            if child is not None:
                if not isinstance(child, dict):
                    raise ValueError("Malformed historical derived course")
                visit(child, prefix + "." + key + ".course")

    if "jinkou" in result:
        if not isinstance(result["jinkou"], dict):
            raise ValueError("Malformed historical Jinkou result")
        visit(result["jinkou"], "jinkou")
    original_hash = canonical_sha(value)
    reverse = copy.deepcopy(result)
    for change in reversed(changes):
        parts = change["path"].split(".")
        parent = reverse
        for part in parts[:-1]:
            parent = parent[int(part)] if isinstance(parent, list) else parent[part]
        if change["kind"] == "added":
            del parent[parts[-1]]
        else:
            parent[parts[-1]] = copy.deepcopy(change["old"])
    if reverse != value or canonical_sha(reverse) != original_hash:
        raise ValueError("Archive supplement changed existing fields")
    return result, dict(
        mode=mode,
        changes=changes,
        courses=courses,
        before_object_sha256=original_hash,
        after_object_sha256=canonical_sha(result),
        original_object_restored_exactly=True,
        existing_fields_unchanged=True,
        supplement_computed_now=True,
        not_a_historical_or_live_receipt=True,
        original_engine_version_and_snapshot_preserved=True,
        source_protocol_sha256=PIN,
        new_classical_or_empirical_cases=0,
        golden_files_written=False,
    )
