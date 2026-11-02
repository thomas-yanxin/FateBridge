"""Narrow v58 historical comparison, after validating native current output.

These are immutable engineering receipts. They are not an independent source
oracle, a production compatibility mode, or observed prediction outcomes.
"""

from __future__ import annotations

import ast
import gzip
import hashlib
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

FOLDER = Path(__file__).parent / "fixtures/meihua_candidate_history_v1"
MANIFEST_SHA256 = "e2b35f662272a84c7e7bfcdf24d368332a912ef7a0d7074495a41da0d41c5b02"
PARENT_ARCHIVE_SHA256 = (
    "530b9aedfdfb8d04faed8ba0313ee20c5d56ee2b83840da6ec13ac3acf9da311"
)


class HistoryBindingError(ValueError):
    pass


def canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def case_identity(tool, arguments):
    return digest({"tool": tool, "arguments": arguments})


def _require(condition, message):
    if not condition:
        raise HistoryBindingError(message)


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "Duplicate reference JSON key")
        result[key] = value
    return result


def _json(raw):
    def nonfinite(value):
        raise HistoryBindingError("Non-finite reference JSON value: " + value)

    return json.loads(raw, object_pairs_hook=_unique_pairs, parse_constant=nonfinite)


def _package_root():
    from tests.meihua_guard_originals import historical_package_root

    return historical_package_root()


def assert_reference_fingerprints():
    raw = (FOLDER / "manifest.json").read_bytes()
    _require(
        hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256, "Reference manifest changed"
    )
    manifest = _json(raw)
    for name, expected in manifest["files"].items():
        _require(
            hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() == expected,
            "Reference bytes changed: " + name,
        )
    return manifest


def _member_hashes(path, names):
    found = {}
    for node in ast.parse(path.read_bytes()).body:
        member = getattr(node, "name", None)
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id in names:
                    found[target.id] = hashlib.sha256(
                        ast.dump(node, include_attributes=False).encode()
                    ).hexdigest()
        elif member in names:
            found[member] = hashlib.sha256(
                ast.dump(node, include_attributes=False).encode()
            ).hexdigest()
    return found


def _assert_source_guards(data):
    root = _package_root()
    from tests.meihua_source_evolution_reference import reviewed_source_guards

    try:
        full_guards, named_guards = reviewed_source_guards(data, root)
    except (ValueError, OSError) as error:
        raise HistoryBindingError(
            "Listed source file changed or source transition invalid: " + str(error)
        ) from error
    for name, expected in full_guards.items():
        _require(
            hashlib.sha256((root / name).read_bytes()).hexdigest() == expected,
            "Listed source file changed: " + name,
        )
    for name, members in named_guards.items():
        _require(
            _member_hashes(root / name, members) == members,
            "Named shared AST changed: " + name,
        )


@lru_cache(maxsize=1)
def _load():
    manifest = assert_reference_fingerprints()
    body = gzip.decompress((FOLDER / "bindings.json.gz").read_bytes())
    _require(
        hashlib.sha256(body).hexdigest() == manifest["binding_decompressed_sha256"],
        "Decompressed binding bytes changed",
    )
    data = _json(body)
    _require(
        data["id"] == "meihua_candidate_summary_history_v1"
        and data["version"] == "1.0.0",
        "Unknown history contract",
    )
    _require(
        data["parent_archive_sha256"] == PARENT_ARCHIVE_SHA256, "Foreign parent archive"
    )
    _require(
        manifest["new_test_adapter_implemented_before_freeze"] is False,
        "Incorrect freeze phase",
    )
    _require(
        manifest["frozen_after_v58_production_and_its_original_negative_gate"] is True,
        "Do not backdate this engineering reference",
    )
    _require(
        data["old_full_output_hash_gate_still_passed"] is False,
        "Original gate must stay negative",
    )
    _require(
        data["original_test_sha256"]
        == manifest["files"]["original-test_meihua_trigram_symbols.py"],
        "Original function source binding differs",
    )
    _assert_source_guards(data)
    before = _json(
        gzip.decompress((FOLDER / "v58-business-before.json.gz").read_bytes())
    )["rows"]
    after = _json(
        gzip.decompress((FOLDER / "v58-business-after-rows.json.gz").read_bytes())
    )
    packets_before = {
        row["index"]: row["before"]
        for row in (
            _json(line)
            for line in gzip.open(
                FOLDER / "v58-affected-before.jsonl.gz", "rt", encoding="utf-8"
            )
        )
    }
    packets_after = {
        row["index"]: row["after"]
        for row in (
            _json(line)
            for line in gzip.open(
                FOLDER / "v58-affected-after.jsonl.gz", "rt", encoding="utf-8"
            )
        )
    }
    _require(
        len(data["rows"]) == len(before) == len(after) == 13546,
        "Do not shrink the complete native queue",
    )
    index = {}
    deltas = 0
    paths = 0
    for number, (record, old, native) in enumerate(
        zip(data["rows"], before, after, strict=True)
    ):
        _require(
            record["index"] == old["index"] == native["index"] == number,
            "Original row order or identity changed",
        )
        _require(
            record["tool"] == old["tool"] and record["arguments"] == old["arguments"],
            "Argument binding changed",
        )
        key = case_identity(record["tool"], record["arguments"])
        _require(
            record["case_id"] == key and key not in index,
            "Duplicate or foreign input identity",
        )
        _require(
            record["before_sha256"] == old["sha256"]
            and record["current_sha256"] == native["sha256"],
            "Output receipt binding changed",
        )
        changed = record["before_sha256"] != record["current_sha256"]
        _require(
            bool(record["candidate_summaries"]) is changed,
            "Summary allowance does not match original complete-hash difference",
        )
        if changed:
            deltas += 1
            _require(
                number in packets_before and number in packets_after,
                "Missing original full affected output",
            )
            previous, current = packets_before[number], packets_after[number]
            _require(
                digest(previous) == record["before_sha256"]
                and digest(current) == record["current_sha256"],
                "Original affected packet differs",
            )
            old_rows = previous["interpretation"]["casting_readings"]
            new_rows = current["interpretation"]["casting_readings"]
            _require(
                len(record["candidate_summaries"])
                == len(old_rows)
                == len(new_rows)
                == 2,
                "Do not omit candidate rows",
            )
            for candidate, (entry, old_row, new_row) in enumerate(
                zip(record["candidate_summaries"], old_rows, new_rows, strict=True)
            ):
                _require(
                    type(entry["index"]) is int and entry["index"] == candidate,
                    "Foreign summary index",
                )
                _require(
                    entry["before_summary"] == old_row["traditional_judgement"]
                    and entry["current_summary"] == new_row["traditional_judgement"],
                    "Summary strings do not match immutable parent packets",
                )
                for field in (
                    "line_sum_basis",
                    "moving_line",
                    "base_code",
                    "body",
                    "use",
                ):
                    _require(
                        entry[field] == new_row[field],
                        "Candidate identity differs: " + field,
                    )
                for field in ("topic", "clause_id", "section", "quote", "reading"):
                    _require(
                        entry[field] == new_row["topic_clause"][field],
                        "Source clause differs: " + field,
                    )
                paths += 1
        index[key] = record
    _require(deltas == 76 and paths == 152, "Declared change scope differs")
    legacy_receipts = _json(
        gzip.decompress((FOLDER / "v58-original-9272-rows.json.gz").read_bytes())
    )
    legacy = data["original_legacy_rows"]
    _require(
        len(legacy) == len(legacy_receipts) == 9272,
        "Do not shrink the original historical queue",
    )
    failed_rows = []
    for number, (row, receipt) in enumerate(zip(legacy, legacy_receipts, strict=True)):
        bound = data["rows"][receipt["full_queue_index"]]
        _require(
            row["index"] == receipt["original_index"] == number,
            "Historical index differs",
        )
        _require(
            row["case_id"] == bound["case_id"]
            and row["business_sha256"] == receipt["original_sha256"],
            "Historical input/output binding differs",
        )
        _require(
            row["original_complete_hash_matched"]
            is receipt["original_complete_hash_matched"],
            "Original failure relabelled",
        )
        if not row["original_complete_hash_matched"]:
            failed_rows.append(number)
    _require(len(failed_rows) == 36, "Original raw failures must remain visible")
    return {"data": data, "index": index, "legacy_failed_indices": failed_rows}


def legacy_scope():
    return deepcopy(_load()["data"]["original_legacy_rows"])


def assert_current_source_signatures():
    _assert_source_guards(_load()["data"])


def assert_legacy_business_reference(raw):
    _require(
        hashlib.sha256(raw).hexdigest()
        == _load()["data"]["original_business_json_sha256"],
        "Original legacy business bytes changed",
    )


def binding_for(tool, arguments):
    key = case_identity(tool, arguments)
    index = _load()["index"]
    _require(key in index, "Unknown input; no unchecked historical projection")
    return deepcopy(index[key])


def restore_pre_v58_candidate_summary(result, *, tool, arguments):
    """Validate native output first, then replace only fixed summary values."""
    record = binding_for(tool, arguments)
    if tool == "meihua_analysis":
        from tests.meihua_clock_evolution_reference import restore_clock_before_native

        try:
            result = restore_clock_before_native(result, arguments)
        except ValueError as error:
            raise HistoryBindingError(str(error)) from error
    _require(
        digest(result) == record["current_sha256"],
        "Native current output is not the immutable post-fix result",
    )
    restored = deepcopy(result)
    for entry in record["candidate_summaries"]:
        row = restored["interpretation"]["casting_readings"][entry["index"]]
        clause = row["topic_clause"]
        _require(
            row["traditional_judgement"] == entry["current_summary"],
            "Current candidate summary differs",
        )
        for field in ("section", "quote", "reading"):
            _require(
                clause[field] in row["traditional_judgement"],
                "Candidate lost its own chapter content",
            )
        row["traditional_judgement"] = entry["before_summary"]
    _require(
        digest(restored) == record["before_sha256"],
        "Projection changed an undeclared field or restored a foreign before value",
    )
    return restored
