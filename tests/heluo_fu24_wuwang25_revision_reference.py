# Frozen R102 source reference; retain historical edges without repinning.
"""Current source successor from sealed readings; historical transforms stay fixed.

Only explicitly pinned source edges can advance old expectations. This module
never reads production output to choose an expected value or change a tolerance.
"""

import copy
import gzip
import hashlib
import json
from pathlib import Path

from tests.heluo_bo23_revision_reference import ast_identity, canonical

ROOT = Path(__file__).parents[1]
F = ROOT / "tests/fixtures/heluo_fu24_wuwang25_v1"


def _load(name, digest):
    raw = (F / name).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest, name
    return json.loads(raw)


ENVELOPE = _load(
    "source-successor/envelope.json",
    "550618bfc6325721e36cb8df33fc7e5aaad01d3f1ff74d2b1a670b9377e112e1",
)
REFERENCE = _load(
    "migration-reference-v1/reference.json",
    "565b89c4fee2f86a70281108ea41a1d9e87575a3f94c89a3c38a31493d5698be",
)
LITERAL = _load(
    "reviewed-literals-v1.json",
    "2c5d0b2e4dbb6bc32585d82167d3b3e6ac8f5f2f65b6d98a339bfc83af3c1ac1",
)
MATH_FIELDS = (
    "analysis_type",
    "input_normalized",
    "analysis_context",
    "four_pillars",
    "calendar_context",
    "chart",
    "dayun",
    "jiehou_evidence",
    "judge",
    "solar_term",
    "summary",
)
assert tuple(REFERENCE["math_fields_unchanged"]) == MATH_FIELDS


def frozen_source(name, stage="after"):
    edge = ENVELOPE["data"].get(name) or ENVELOPE["code"][name]
    raw = gzip.decompress((F / edge[stage + "_snapshot"]).read_bytes())
    assert hashlib.sha256(raw).hexdigest() == edge[stage + "_raw_sha256"], name
    return json.loads(raw) if name in ENVELOPE["data"] else raw.decode()


SOURCE_NAMES = tuple(ENVELOPE["data"])
CURRENT_HEADERS, CURRENT_COMMENTARIES, CURRENT_CATALOGUE = (
    frozen_source(name) for name in SOURCE_NAMES
)
HEADER_COUNT = len(CURRENT_HEADERS["entries"])
COMMENTARY_COUNT = len(CURRENT_COMMENTARIES["entries"])
PENDING_COUNT = 384 - HEADER_COUNT
CATALOGUE_VERSION = CURRENT_CATALOGUE["version"]
CATALOGUE_CONTENT_SHA256 = canonical(CURRENT_CATALOGUE)
COMMENTARY_RULESET_ID = CURRENT_COMMENTARIES["corpus_id"]
ALL_HEADER_PAGES = frozenset(e["pdf_page"] for e in CURRENT_HEADERS["entries"])
LITERAL_CHANGED_KEYS = frozenset(
    key
    for key, edge in REFERENCE["records"].items()
    if {k: v for k, v in edge["before"].items() if k != "text_provenance"}
    != {k: v for k, v in edge["after"].items() if k != "text_provenance"}
)
assert HEADER_COUNT == COMMENTARY_COUNT == 138 + len(LITERAL["entries"]) == 150
assert PENDING_COUNT == 234 and len(LITERAL_CHANGED_KEYS) == 12


def assert_current_source_edge(root=ROOT):
    for name, edge in ENVELOPE["data"].items():
        raw = (root / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == edge["after_raw_sha256"], name
        assert canonical(json.loads(raw)) == edge["after_identity"], name
        before, after = frozen_source(name, "before"), frozen_source(name)
        assert canonical(before) == edge["before_identity"]
        if "entries" in before:
            assert len(before["entries"]) == 138
            assert after["entries"][:138] == before["entries"]
            assert len(after["entries"]) == 150
    for name, edge in ENVELOPE["code"].items():
        assert ast_identity((root / name).read_text()) == edge["after_identity"], name
        assert ast_identity(frozen_source(name, "before")) == edge["before_identity"]
        assert ast_identity(frozen_source(name)) == edge["after_identity"]
    for source in CURRENT_CATALOGUE["sources"]:
        raw = (root / "src/fatebridge/data" / source["source_path"]).read_bytes()
        assert canonical(json.loads(raw)) == source["canonical_content_sha256"]
    old = frozen_source(SOURCE_NAMES[2], "before")
    pairs = list(zip(old["sources"], CURRENT_CATALOGUE["sources"], strict=True))
    assert len(pairs) == 17 and sum(a == b for a, b in pairs) == 15
    assert [a["key"] for a, b in pairs if a != b] == [
        "commentary_collation",
        "yaoci_collation",
    ]
    for literal, header, commentary in zip(
        LITERAL["entries"],
        CURRENT_HEADERS["entries"][138:],
        CURRENT_COMMENTARIES["entries"][138:],
        strict=True,
    ):
        assert header["yaoci"] == literal["yaoci"]
        assert header["reading_notes"] == literal["header_reading_notes"]
        assert commentary["sections"] == literal["sections"]
        assert commentary["reading_notes"] == literal["reading_notes"]
    return True


def advance_source_identity(name, raw_sha256, content_sha256):
    if name not in ENVELOPE["data"]:
        return raw_sha256, content_sha256
    edge = ENVELOPE["data"][name]
    assert raw_sha256 == edge["before_raw_sha256"], name
    assert content_sha256 == edge["before_identity"], name
    return edge["after_raw_sha256"], edge["after_identity"]


def advance_current_record(value, key):
    edge = REFERENCE["records"][key]
    assert canonical(value) == edge["before_sha256"] and value == edge["before"], key
    result = copy.deepcopy(edge["after"])
    assert canonical(result) == edge["after_sha256"]
    assert value["shige"] == result["shige"] and value["verdict"] == result["verdict"]
    return result


def advance_current_render_row(value):
    key = f"{value['gua']}:{value['line']}"
    edge = REFERENCE["render_rows"][key]
    assert value == edge["before"], key
    result = copy.deepcopy(edge["after"])
    assert (
        result["lines"] == value["lines"]
        and result["poem_notes"] == value["poem_notes"]
    )
    return result


def advance_current_business(value, kind, index):
    edge = REFERENCE["business_edges"][f"{kind}:{index}"]
    body = lambda v: {k: x for k, x in v.items() if k != "snapshot_text"}
    assert canonical(body(value)) == edge["before_body_sha256"]
    assert value["snapshot_text"] == edge["accepted_before_snapshot"]
    result = copy.deepcopy(value)
    for patch in edge["patches"]:
        path = patch["path"]
        assert path[0] == "numerology_evidence" or path[:2] == [
            "heluo_timing",
            "selected_texts",
        ]
        if path[0] == "numerology_evidence":
            assert path[1] in [
                "yaoci_collation",
                "commentary_collation",
                "interpretation_constraints",
                "rulesets",
                "rule_trace",
                "selected_texts",
            ]
        node = result
        for key in path[:-1]:
            node = node[key]
        key = path[-1]
        assert (
            type(node[key]) is type(patch["before"]) and node[key] == patch["before"]
        ), path
        node[key] = copy.deepcopy(patch["after"])
    assert canonical(body(result)) == edge["after_body_sha256"]
    for key in MATH_FIELDS:
        assert result[key] == value[key], key
    for key in value["heluo_timing"]:
        if key != "selected_texts":
            assert result["heluo_timing"][key] == value["heluo_timing"][key], key
    result["snapshot_text"] = edge["after_snapshot"]
    return result


def advance_current_metadata(value, parent=None, path=()):
    if isinstance(value, dict):
        pairs = (
            REFERENCE["provenance_pairs"]
            if parent == "provenance"
            else (
                REFERENCE["source_record_pairs"].get(value.get("key"), {})
                if parent == "source_records"
                else {}
            )
        )
        result = {}
        for key, item in value.items():
            if key in pairs:
                before, after = pairs[key]
                assert type(item) is type(before) and item == before, (parent, key)
                result[key] = copy.deepcopy(after)
            elif key in {
                "record",
                "lines",
                "tips",
                "text",
                "answer",
                "notes",
                "number",
                "chart",
                "four_pillars",
                "calendar_context",
                "dayun",
                "judge",
            }:
                result[key] = copy.deepcopy(item)
            else:
                result[key] = advance_current_metadata(item, key, path + (key,))
        return result
    if isinstance(value, list):
        return [
            advance_current_metadata(item, parent, path + (i,))
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
            pairs = dict(REFERENCE["exact_metadata_footer_pairs"])
            return "".join(
                pairs.get(line.rstrip("\r\n"), line.rstrip("\r\n"))
                + line[len(line.rstrip("\r\n")) :]
                for line in value.splitlines(keepends=True)
            )
    return copy.deepcopy(value)


def advance_current_registry(value, domain):
    assert value == REFERENCE["registry_before"][domain], domain
    return copy.deepcopy(REFERENCE["registry_after"][domain])
