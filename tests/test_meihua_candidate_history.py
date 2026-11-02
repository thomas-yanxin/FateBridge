"""Exact history allowances cannot turn arbitrary new output into old passes."""

import ast
import gzip
import hashlib
import json
import os
import shutil
from copy import deepcopy

import pytest

from fatebridge.services.meihua import calculate_meihua_cast
from tests import meihua_candidate_history_reference as history
from tests.meihua_volume5_source_evolution import (
    reviewed_previous_output_shape,
    reviewed_restore_pre_v58_candidate_summary,
)

FOLDER = history.FOLDER
FROZEN = json.loads(gzip.decompress((FOLDER / "bindings.json.gz").read_bytes()))
CHANGED = [row for row in FROZEN["rows"] if row["candidate_summaries"]]
BEFORE = {
    row["index"]: row["before"]
    for row in (
        json.loads(line)
        for line in gzip.open(
            FOLDER / "v58-affected-before.jsonl.gz", "rt", encoding="utf-8"
        )
    )
}
AFTER = {
    row["index"]: row["after"]
    for row in (
        json.loads(line)
        for line in gzip.open(
            FOLDER / "v58-affected-after.jsonl.gz", "rt", encoding="utf-8"
        )
    )
}


@pytest.fixture
def reset_reference_cache(monkeypatch):
    history._load.cache_clear()
    yield
    history._load.cache_clear()


def repin_temporary_binding(monkeypatch, folder, raw):
    """Simulate a checksum-only edit; immutable parent receipts must still bind."""
    path = folder / "bindings.json.gz"
    path.write_bytes(gzip.compress(raw, mtime=0))
    manifest = json.loads((folder / "manifest.json").read_bytes())
    manifest["files"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest["binding_decompressed_sha256"] = hashlib.sha256(raw).hexdigest()
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False))
    monkeypatch.setattr(history, "FOLDER", folder)
    monkeypatch.setattr(
        history,
        "MANIFEST_SHA256",
        hashlib.sha256((folder / "manifest.json").read_bytes()).hexdigest(),
    )


def test_reference_is_explicitly_after_v58_and_original_gate_is_still_negative():
    policy = history.assert_reference_fingerprints()
    assert policy["new_test_adapter_implemented_before_freeze"] is False
    assert policy["frozen_after_v58_production_and_its_original_negative_gate"] is True
    assert policy["source_expert_or_prediction_validation"] is False
    assert len(FROZEN["rows"]) == 13546
    assert len(CHANGED) == 76
    assert sum(len(row["candidate_summaries"]) for row in CHANGED) == 152
    scope = history.legacy_scope()
    assert len(scope) == 9272
    assert sum(not row["original_complete_hash_matched"] for row in scope) == 36


@pytest.mark.parametrize("record", CHANGED, ids=lambda row: str(row["index"]))
def test_all_76_complete_parent_packets_restore_only_the_exact_declared_summaries(
    record,
):
    current = AFTER[record["index"]]
    saved = deepcopy(current)
    restored = history.restore_pre_v58_candidate_summary(
        current, tool=record["tool"], arguments=record["arguments"]
    )
    assert restored == BEFORE[record["index"]]
    assert current == saved
    assert history.digest(current) == record["current_sha256"]
    assert history.digest(restored) == record["before_sha256"]
    assert record["before_sha256"] != record["current_sha256"]


def test_unaffected_frozen_case_preserves_complete_prior_shape_after_reviewed_addition():
    arguments = {
        "casting": {"method": "existing", "hexagram_code": "000000", "moving_line": 1},
        "interpretation_topic": "general",
    }
    result = calculate_meihua_cast(**arguments)
    record = history.binding_for("meihua_cast", arguments)
    assert record["candidate_summaries"] == []
    assert record["before_sha256"] == record["current_sha256"]
    assert reviewed_restore_pre_v58_candidate_summary(
        result, tool="meihua_cast", arguments=arguments
    ) == reviewed_previous_output_shape(result)


@pytest.mark.parametrize(
    "mutation",
    [
        "old_summary",
        "missing_summary",
        "borrowed_candidate",
        "wrong_body",
        "wrong_source_quote",
        "missing_later_suffix",
        "unrelated_summary",
        "extra_field",
    ],
)
def test_current_output_must_match_the_native_post_fix_receipt_before_any_projection(
    mutation,
):
    record = CHANGED[0]
    result = deepcopy(AFTER[record["index"]])
    rows = result["interpretation"]["casting_readings"]
    if mutation == "old_summary":
        rows[0]["traditional_judgement"] = record["candidate_summaries"][0][
            "before_summary"
        ]
    elif mutation == "missing_summary":
        rows[0]["traditional_judgement"] = ""
    elif mutation == "borrowed_candidate":
        rows[0]["traditional_judgement"] = rows[1]["traditional_judgement"]
    elif mutation == "wrong_body":
        rows[0]["body"] = "坤"
    elif mutation == "wrong_source_quote":
        rows[0]["topic_clause"]["quote"] = "體用比利家宅安穩"
    elif mutation == "missing_later_suffix":
        rows[0]["traditional_judgement"] = rows[0]["traditional_judgement"][:-1]
    elif mutation == "unrelated_summary":
        result["summary"] += "未声明的变化"
    else:
        result["unlisted"] = True
    with pytest.raises(history.HistoryBindingError, match="Native current output"):
        history.restore_pre_v58_candidate_summary(
            result, tool=record["tool"], arguments=record["arguments"]
        )


@pytest.mark.parametrize("mutation", ["question", "tool"])
def test_unknown_arguments_or_tool_never_receive_unchecked_projection(mutation):
    record = CHANGED[0]
    arguments = deepcopy(record["arguments"])
    tool = record["tool"]
    if mutation == "question":
        arguments["question"] = "不在固定队列中的合成问题"
    else:
        tool = "meihua_analysis"
    with pytest.raises(history.HistoryBindingError, match="Unknown input"):
        history.restore_pre_v58_candidate_summary(
            AFTER[record["index"]], tool=tool, arguments=arguments
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "new_post_hash",
        "before_summary",
        "current_summary",
        "arguments",
        "drop_row",
        "drop_legacy_row",
        "relabel_original_failure",
        "foreign_parent",
        "original_source_hash",
        "duplicate_key",
        "nonfinite",
    ],
)
def test_repinning_derived_data_alone_cannot_replace_immutable_parent_bindings(
    mutation, tmp_path, monkeypatch, reset_reference_cache
):
    folder = tmp_path / "reference"
    shutil.copytree(FOLDER, folder)
    data = deepcopy(FROZEN)
    changed = next(row for row in data["rows"] if row["candidate_summaries"])
    if mutation == "new_post_hash":
        changed["current_sha256"] = "0" * 64
    elif mutation in {"before_summary", "current_summary"}:
        changed["candidate_summaries"][0][mutation] += "伪造"
    elif mutation == "arguments":
        changed["arguments"]["question"] = "未知输入"
    elif mutation == "drop_row":
        data["rows"].pop()
    elif mutation == "drop_legacy_row":
        data["original_legacy_rows"].pop()
    elif mutation == "relabel_original_failure":
        next(
            row
            for row in data["original_legacy_rows"]
            if not row["original_complete_hash_matched"]
        )["original_complete_hash_matched"] = True
    elif mutation == "foreign_parent":
        data["parent_archive_sha256"] = "0" * 64
    elif mutation == "original_source_hash":
        data["original_test_sha256"] = "0" * 64
    if mutation == "duplicate_key":
        raw = ('{"id":"foreign",' + json.dumps(data, ensure_ascii=False)[1:]).encode()
    elif mutation == "nonfinite":
        raw = ('{"bad":NaN,' + json.dumps(data, ensure_ascii=False)[1:]).encode()
    else:
        raw = json.dumps(data, ensure_ascii=False).encode()
    repin_temporary_binding(monkeypatch, folder, raw)
    with pytest.raises(history.HistoryBindingError):
        history.legacy_scope()


@pytest.mark.parametrize(
    "mutation",
    ["listed_file", "named_ast", "shared_comment_only", "source_drift_after_cache"],
)
def test_listed_source_and_named_shared_ast_guards_have_explicit_scope(
    mutation, tmp_path, monkeypatch, reset_reference_cache
):
    package = tmp_path / "fatebridge"
    real = history._package_root()
    from tests.meihua_source_evolution_reference import (
        additional_guarded_source_paths,
        reviewed_source_guards,
    )

    full, named = reviewed_source_guards(FROZEN, real)
    names = (
        set(full)
        | set(named)
        | set(FROZEN["source_guards"])
        | additional_guarded_source_paths()
    )
    for name in names:
        target = package / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(real / name, target)
    monkeypatch.setattr(history, "_package_root", lambda: package)
    if mutation == "source_drift_after_cache":
        assert len(history.legacy_scope()) == 9272
    if mutation in {"listed_file", "source_drift_after_cache"}:
        path = package / "core/meihua_topics.py"
        path.write_text(path.read_text() + "\n# Changed complete guarded file\n")
    else:
        path = package / "services/divination.py"
        if mutation == "shared_comment_only":
            path.write_text(
                path.read_text()
                + "\n# Unrelated shared-file comment; named AST is unchanged\n"
            )
        else:
            module = ast.parse(path.read_bytes())
            node = next(
                node
                for node in module.body
                if isinstance(node, ast.FunctionDef)
                and node.name == "calculate_meihua_analysis"
            )
            node.body.append(ast.Pass())
            path.write_text(ast.unparse(module))
    if mutation == "shared_comment_only":
        assert len(history.legacy_scope()) == 9272
    else:
        with pytest.raises(
            history.HistoryBindingError, match="source file changed|shared AST changed"
        ):
            history.assert_current_source_signatures()


def test_cached_reference_is_rechecked_by_bytes_even_if_size_and_mtime_survive(
    tmp_path, monkeypatch, reset_reference_cache
):
    folder = tmp_path / "reference"
    shutil.copytree(FOLDER, folder)
    monkeypatch.setattr(history, "FOLDER", folder)
    assert len(history.legacy_scope()) == 9272
    path = folder / "bindings.json.gz"
    stat = path.stat()
    raw = bytearray(path.read_bytes())
    raw[-1] ^= 1
    path.write_bytes(raw)
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert (
        path.stat().st_size == stat.st_size
        and path.stat().st_mtime_ns == stat.st_mtime_ns
    )
    with pytest.raises(history.HistoryBindingError, match="Reference bytes changed"):
        history.assert_reference_fingerprints()


def test_legacy_business_bytes_have_their_own_immutable_binding():
    fixture = FOLDER.parent / "meihua_trigram_symbols_v1/old-business.json.gz"
    raw = gzip.decompress(fixture.read_bytes())
    history.assert_legacy_business_reference(raw)
    with pytest.raises(
        history.HistoryBindingError, match="Original legacy business bytes"
    ):
        history.assert_legacy_business_reference(raw + b" ")
