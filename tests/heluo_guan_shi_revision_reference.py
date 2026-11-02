"""Frozen R84 source edge; never rewrite arbitrary words, notes or numbers."""

import copy
import hashlib
import json
from pathlib import Path

from tests.heluo_ben22_revision_reference import CURRENT_HEADERS as R96_HEADERS
from tests.heluo_current_source_reference import CURRENT_HEADERS as LATEST_HEADERS
from tests.heluo_current_source_reference import HEADER_COUNT, PENDING_COUNT
from tests.heluo_shike_bi_revision_reference import (
    CURRENT_HEADERS,
    CURRENT_POEMS,
    assert_r92_source_addition,
)

F = Path(__file__).parent / "fixtures/heluo_guan20_shi7_v1"
REVISION = json.loads((F / "legacy-source-migration-reference.json").read_bytes())
PROPOSAL = json.loads((F / "source-proposal-reference.json").read_bytes())
NEW_HEADERS = json.loads(
    (F / "proposed/src/fatebridge/data/heluo/yaoci-collation-v1.json").read_bytes()
)
NEW_POEMS = json.loads(
    (F / "proposed/src/fatebridge/data/heluo/poem-collation-v1.json").read_bytes()
)


def canonical(value):
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def rebind_r84_metadata(value, parent=None, path=()):
    if isinstance(value, dict):
        pairs = (
            REVISION["text_provenance_pairs"]
            if parent == "text_provenance"
            else (
                REVISION["source_record_pairs"].get(value.get("key"), {})
                if parent == "source_records"
                else REVISION["provenance_pairs"] if parent == "provenance" else {}
            )
        )
        result = {}
        for key, item in value.items():
            if key in pairs:
                before, after = pairs[key]
                assert item == before, (parent, key, item)
                result[key] = copy.deepcopy(after)
            else:
                result[key] = rebind_r84_metadata(item, key, path + (key,))
        return result
    if isinstance(value, list):
        return [
            rebind_r84_metadata(item, parent, path + (index,))
            for index, item in enumerate(value)
        ]
    if isinstance(value, str):
        if path not in {
            ("rendered_text",),
            ("snapshot_text",),
            ("snapshot_export", "export_text"),
        } and not (
            len(path) == 4
            and path[:2] == ("snapshot_export", "sections")
            and isinstance(path[2], int)
            and path[3] == "content"
        ):
            return value
        pairs = dict(REVISION["exact_metadata_footer_pairs"])
        return "".join(
            pairs.get(line.rstrip("\r\n"), line.rstrip("\r\n"))
            + line[len(line.rstrip("\r\n")) :]
            for line in value.splitlines(keepends=True)
        )
    return value


def rebind_r84_counts(value, parent=None):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if parent == "coverage" and key in REVISION["coverage_field_pairs"]:
                before, after = REVISION["coverage_field_pairs"][key]
                assert item == before, (parent, key, item)
                result[key] = after
            else:
                result[key] = rebind_r84_counts(item, key)
        return result
    if isinstance(value, list):
        return [rebind_r84_counts(item, parent) for item in value]
    return value


def rebind_r84_record(record, key):
    """Advance only twelve independently declared source additions."""
    if key not in REVISION["record_extensions"]:
        return copy.deepcopy(record)
    edge = REVISION["record_extensions"][key]
    assert (
        canonical(record) == edge["before_record_after_metadata_canonical_sha256"]
    ), key
    result = copy.deepcopy(record)
    result.update(copy.deepcopy(edge["fields"]))
    assert result["verdict"] == record["verdict"]
    return result


SNAPSHOT_SOURCE = json.loads(
    (F / "snapshot-source-migration-reference.json").read_bytes()
)


def rebind_r84_snapshot_source_lines(text):
    marker = SNAPSHOT_SOURCE["block_heading"] + "\n"
    if marker not in text:
        return text
    assert text.count(marker) == 1
    prefix, tail = text.split(marker)
    block, separator, suffix = tail.partition("\n\n")
    lines = block.splitlines()
    pairs = dict(SNAPSHOT_SOURCE["line_pairs"])
    assert all(lines.count(old) == 1 for old in pairs)
    return (
        prefix
        + marker
        + "\n".join(pairs.get(line, line) for line in lines)
        + separator
        + suffix
    )


def assert_r84_commentary_control_and_all_pending():
    from fatebridge.core.heluo import _tiaowen, yao_text

    target = yao_text("風地觀", 1)
    frozen = REVISION["record_extensions"]["風地觀:1"]["fields"]
    assert target["detail"] == frozen["detail"]
    assert target["commentary_sections"] == frozen["commentary_sections"]
    assert target["commentary_branch_selection"]["selected_section_ids"] == []
    from tests.heluo_bo23_revision_reference import CURRENT_HEADERS as R101_HEADERS

    assert R101_HEADERS["entries"][:132] == R96_HEADERS["entries"]
    assert LATEST_HEADERS["entries"][:138] == R101_HEADERS["entries"]
    reviewed = {(e["hexagram"], e["line"]) for e in LATEST_HEADERS["entries"]}
    assert_r92_source_addition()
    assert len(reviewed) == HEADER_COUNT and len(_tiaowen()) == 64
    count = 0
    for gua in _tiaowen():
        for pos in range(1, 7):
            if (gua, pos) in reviewed:
                continue
            record = yao_text(gua, pos)
            assert record["text_provenance"]["commentary_status"].endswith("pending")
            assert "commentary_sections" not in record
            count += 1
    assert count == PENDING_COUNT
    return count


def assert_r84_poem_control_and_all_pending():
    from fatebridge.core.heluo import _tiaowen, yao_text

    target = yao_text("地水師", 1)
    frozen = next(
        e
        for e in CURRENT_POEMS["entries"]
        if (e["hexagram"], e["line"]) == ("地水師", 1)
    )
    assert target["poem_sections"] == [
        dict(p, applicability=None) for p in frozen["poems"]
    ]
    assert (
        target["text_provenance"]["inherited_shige"]
        == _tiaowen()["地水師"]["yao"]["1"]["shige"]
    )
    assert target["poem_selection"]["selected_poem_indices"] == []
    reviewed = {(e["hexagram"], e["line"]) for e in CURRENT_POEMS["entries"]}
    assert_r92_source_addition()
    assert len(reviewed) == 48 and len(_tiaowen()) == 64
    count = 0
    for gua in _tiaowen():
        for pos in range(1, 7):
            if (gua, pos) in reviewed:
                continue
            record = yao_text(gua, pos)
            assert (
                record["text_provenance"]["poem_status"]
                == "inherited_poem_source_unverified"
            )
            assert "poem_sections" not in record
            count += 1
    assert count == 336
    return count
