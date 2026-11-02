"""R96 source-only edge. Frozen preimages reject unreviewed facts and reruns."""

import ast
import copy
import hashlib
import json
from pathlib import Path

from tests.heluo_shike_bi_revision_reference import LITERAL_FIELDS, canonical

F = Path(__file__).parent / "fixtures/heluo_ben22_v1"
ROOT = Path(__file__).parents[1]
REVISION = json.loads((F / "migration-reference.json").read_bytes())
SUPPORT = json.loads((F / "support-reference.json").read_bytes())
LITERAL = json.loads((F / "reviewed-literals-v2.json").read_bytes())
SOURCE_NAMES = (
    "src/fatebridge/data/heluo/yaoci-collation-v1.json",
    "src/fatebridge/data/heluo/commentary-collation-v1.json",
    "src/fatebridge/data/knowledge/numerology-sources-v1.json",
)
CURRENT_HEADERS, CURRENT_COMMENTARIES, CURRENT_CATALOGUE = (
    json.loads((F / "proposed" / n).read_bytes()) for n in SOURCE_NAMES
)


def rebind_r96_metadata(value, parent=None, path=()):
    if isinstance(value, dict):
        pairs = (
            REVISION["text_provenance_pairs"]
            if parent == "text_provenance"
            else (
                REVISION["provenance_pairs"]
                if parent == "provenance"
                else (
                    REVISION["source_record_pairs"].get(value.get("key"), {})
                    if parent == "source_records"
                    else {}
                )
            )
        )
        result = {}
        for key, item in value.items():
            if key in pairs:
                before, after = pairs[key]
                assert type(item) is type(before) and item == before, (parent, key)
                result[key] = copy.deepcopy(after)
            elif key in LITERAL_FIELDS:
                result[key] = copy.deepcopy(item)
            else:
                result[key] = rebind_r96_metadata(item, key, path + (key,))
        return result
    if isinstance(value, list):
        return [
            rebind_r96_metadata(item, parent, path + (i,))
            for i, item in enumerate(value)
        ]
    if isinstance(value, str):
        allowed = path in {
            ("rendered_text",),
            ("snapshot_text",),
            ("snapshot_export", "export_text"),
        }
        allowed |= (
            len(path) == 4
            and path[:2] == ("snapshot_export", "sections")
            and isinstance(path[2], int)
            and path[3] == "content"
        )
        if allowed:
            pairs = dict(REVISION["exact_metadata_footer_pairs"])
            return "".join(
                pairs.get(line.rstrip("\r\n"), line.rstrip("\r\n"))
                + line[len(line.rstrip("\r\n")) :]
                for line in value.splitlines(keepends=True)
            )
    return copy.deepcopy(value)


def rebind_r96_counts(value, parent=None):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if parent == "coverage" and key in REVISION["coverage_pairs"]:
                before, after = REVISION["coverage_pairs"][key]
                assert type(item) is type(before) and item == before, key
                result[key] = after
            elif key in LITERAL_FIELDS or key == "record":
                result[key] = copy.deepcopy(item)
            else:
                result[key] = rebind_r96_counts(item, key)
        return result
    if isinstance(value, list):
        return [rebind_r96_counts(item, parent) for item in value]
    return copy.deepcopy(value)


def rebind_r96_record(value, key):
    # Metadata is composed explicitly by callers, body preimages are complete.
    result = copy.deepcopy(value)
    edge = REVISION["record_extensions"].get(key)
    expected_before = (
        edge["before_after_metadata_sha256"]
        if edge
        else canonical(rebind_r96_metadata(_before_records()[key]))
    )
    assert canonical(value) == expected_before, key
    if edge:
        result.update(copy.deepcopy(edge["fields"]))
    assert result["verdict"] == value["verdict"]
    assert canonical(result) == SUPPORT["after_records_canonical"][key], key
    return result


_BEFORE = None


def _before_records():
    global _BEFORE
    if _BEFORE is None:
        import gzip

        _BEFORE = json.loads(
            gzip.decompress((F / "before-records384.json.gz").read_bytes())
        )
        assert {k: canonical(v) for k, v in _BEFORE.items()} == SUPPORT[
            "before_records_canonical"
        ]
    return _BEFORE


def rebind_r96_render_row(row):
    key = f"{row['gua']}:{row['line']}"
    edge = SUPPORT["render_edges"].get(key)
    if edge is None:
        return copy.deepcopy(row)
    assert row == edge["before"] and canonical(row) == edge["before_sha256"], key
    result = copy.deepcopy(edge["after"])
    assert row["lines"] == result["lines"]
    assert row["poem_notes"] == result["poem_notes"]
    assert canonical(result) == edge["after_sha256"]
    return result


def _business(value, edge, snapshot):
    body = lambda v: {k: x for k, x in v.items() if k != "snapshot_text"}
    assert value["snapshot_text"] == snapshot
    assert canonical(body(value)) == edge["before_body_sha256"]
    result = copy.deepcopy(value)
    for patch in edge["patches"]:
        node = result
        for key in patch["path"][:-1]:
            node = node[key]
        key = patch["path"][-1]
        assert (
            type(node[key]) is type(patch["before"]) and node[key] == patch["before"]
        ), patch["path"]
        node[key] = copy.deepcopy(patch["after"])
    assert canonical(body(result)) == edge["after_body_sha256"]
    for key in (
        "input_normalized",
        "analysis_context",
        "four_pillars",
        "calendar_context",
        "chart",
        "dayun",
        "judge",
        "solar_term",
        "jiehou_evidence",
    ):
        assert result[key] == value[key], key
    return result


def rebind_r96_business22(value, index):
    old = json.loads(
        (
            ROOT / f"tests/fixtures/heluo_reading_delivery_v1/before22/{index:02d}.json"
        ).read_bytes()
    )
    return _business(
        value, REVISION["business22_edges"][str(index)], old["snapshot_text"]
    )


def rebind_r96_ben6(value, line):
    old = json.loads((F / f"case-search/before-line-{line}.json").read_bytes())
    return _business(value, REVISION["ben6_edges"][str(line)], old["snapshot_text"])


def assert_r96_source_addition():
    from tests.canping_witness_knowledge_revision import REVISION as r99
    from tests.canping_witness_source_edge import (
        ENVELOPE,
        assert_r99_source_edge,
        ast_sha,
    )
    from tests.heluo_bo23_revision_reference import ENVELOPE as r101_envelope
    from tests.heluo_bo23_revision_reference import (
        assert_r101_source_edge,
        ast_identity,
        frozen_source,
    )
    from tests.heluo_current_source_reference import ENVELOPE as latest_envelope
    from tests.heluo_current_source_reference import HEADER_COUNT
    from tests.heluo_current_source_reference import frozen_source as latest_source

    assert assert_r99_source_edge(ROOT)
    assert assert_r101_source_edge(ROOT)
    for name, expected in zip(
        SOURCE_NAMES,
        (CURRENT_HEADERS, CURRENT_COMMENTARIES, CURRENT_CATALOGUE),
        strict=True,
    ):
        actual = json.loads((ROOT / name).read_bytes())
        current_expected = expected
        current_sha = REVISION["source_files_after_sha256"][name]
        if name == ENVELOPE["catalogue_path"]:
            assert expected == r99["catalogue_before"]
            assert current_sha == ENVELOPE["before_catalogue_raw_sha256"]
            assert (
                hashlib.sha256((F / "proposed" / name).read_bytes()).hexdigest()
                == current_sha
            )
            current_expected = r99["catalogue_after"]
            current_sha = ENVELOPE["after_catalogue_raw_sha256"]
        assert current_expected == frozen_source(name, "before")
        assert current_sha == r101_envelope["data"][name]["before_raw_sha256"]
        assert frozen_source(name) == latest_source(name, "before")
        assert actual == latest_source(name)
        assert (
            hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            == latest_envelope["data"][name]["after_raw_sha256"]
        )
        before = json.loads((F / "before-source" / name).read_bytes())
        if "entries" in expected:
            assert len(before["entries"]) == 126
            assert actual["entries"][:126] == before["entries"]
            assert len(expected["entries"]) == 132
            assert actual["entries"][:132] == expected["entries"]
            assert len(actual["entries"]) == HEADER_COUNT
    heads = CURRENT_HEADERS["entries"][-6:]
    comments = CURRENT_COMMENTARIES["entries"][-6:]
    for literal, h, c in zip(LITERAL["entries"], heads, comments, strict=True):
        assert h["hexagram"] == c["hexagram"] == LITERAL["hexagram"] == "山火賁"
        assert h["line"] == c["line"] == literal["line"]
        assert h["yaoci"] == literal["yaoci"]
        assert c["sections"] == literal["sections"]
        assert c["reading_notes"] == literal["reading_notes"]
        assert "independent_second_review_pending" in c["review_status"]
    for name in REVISION["source_files_after_sha256"]:
        if name.endswith(".py"):
            # Formatting has no source/semantic authority; compare complete AST.
            expected_path = F / "proposed" / name
            if name == ENVELOPE["gateway_path"]:
                assert ast_sha(expected_path) == ENVELOPE["before_gateway_ast_sha256"]
                expected_path = (
                    ROOT
                    / "tests/fixtures/canping_gold_wenming_v1"
                    / ENVELOPE["after_gateway_snapshot"]
                )
            assert ast_identity(expected_path.read_text()) == ast_identity(
                frozen_source(name, "before")
            )
            # This edge certifies the sealed source edition. Refactored code
            # is covered by complete current-output regressions separately.
            assert hashlib.sha256(latest_source(name).encode()).hexdigest() == (
                latest_envelope["code"][name]["after_raw_sha256"]
            )
    return True


def assert_r96_historical_file_edge(name, before_sha256):
    assert before_sha256 == REVISION["source_files_before_sha256"][name]
    assert (
        hashlib.sha256((F / "before-source" / name).read_bytes()).hexdigest()
        == before_sha256
    )
    assert_r96_source_addition()
