"""Fixed R101 successor; old references and numerical requirements stay exact."""

import ast
import copy
import gzip
import hashlib
import json
from pathlib import Path

F = Path(__file__).parent / "fixtures/heluo_bo23_v1/migration-v1"
ROOT = Path(__file__).parents[1]


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


def _load(name, digest):
    raw = (F / name).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest, name
    return json.loads(raw)


REFERENCE = _load(
    "reference.json", "b5bae8f0ab81a072ab0e5f323f646620f525d603460b60accb7bdb27f79f8111"
)
KNOWLEDGE = _load(
    "knowledge.json", "e8714bfc3cd801f9de8257ad967cd47d4ecccc542bcef52df7dd4c0b092da8d0"
)
ENVELOPE = _load(
    "source-envelope.json",
    "ed91264782b9415d7f16632997a406f7206b1019b80bc15481e2a625409253f3",
)
FOOTER_ADDENDUM = _load(
    "footer-addendum-v1.json",
    "d67e306aa1163c6402406e5245c721b6a9edb15f1635d617ee6abe37b7036be4",
)


def frozen_source(name, stage="after"):
    edge = ENVELOPE["data"].get(name) or ENVELOPE["code"][name]
    raw = gzip.decompress((F / edge[stage + "_snapshot"]).read_bytes())
    assert hashlib.sha256(raw).hexdigest() == edge[stage + "_raw_sha256"], name
    return json.loads(raw) if name in ENVELOPE["data"] else raw.decode()


CURRENT_HEADERS, CURRENT_COMMENTARIES, CURRENT_CATALOGUE = (
    frozen_source(name) for name in ENVELOPE["data"]
)


def _stable_ast(value):
    if value is Ellipsis:
        return {"literal": "Ellipsis"}
    if isinstance(value, ast.AST):
        return {
            "node": type(value).__name__,
            "fields": [
                [key, _stable_ast(item)]
                for key, item in ast.iter_fields(value)
                if not (key == "type_params" and item == [])
            ],
        }
    if isinstance(value, list):
        return [_stable_ast(item) for item in value]
    return value


def ast_identity(source):
    return canonical(_stable_ast(ast.parse(source)))


def assert_r101_source_edge(root=ROOT):
    from tests.heluo_current_source_reference import assert_current_source_edge
    from tests.heluo_current_source_reference import frozen_source as latest_source

    for name, edge in ENVELOPE["data"].items():
        actual = gzip.decompress((F / edge["after_snapshot"]).read_bytes())
        assert hashlib.sha256(actual).hexdigest() == edge["after_raw_sha256"], name
        assert canonical(json.loads(actual)) == edge["after_identity"], name
        before, after = frozen_source(name, "before"), frozen_source(name)
        assert after == latest_source(name, "before"), name
        assert canonical(before) == edge["before_identity"]
        if "entries" in before:
            assert len(before["entries"]) == 132 and len(after["entries"]) == 138
            assert after["entries"][:132] == before["entries"]
    for name, edge in ENVELOPE["code"].items():
        assert (
            ast_identity(latest_source(name, "before")) == edge["after_identity"]
        ), name
        assert ast_identity(frozen_source(name, "before")) == edge["before_identity"]
        assert ast_identity(frozen_source(name)) == edge["after_identity"]
    before = frozen_source(
        "src/fatebridge/data/knowledge/numerology-sources-v1.json", "before"
    )
    pairs = list(zip(before["sources"], CURRENT_CATALOGUE["sources"], strict=True))
    assert len(pairs) == 17
    assert [a["key"] for a, b in pairs if a != b] == [
        "commentary_collation",
        "yaoci_collation",
    ]
    assert sum(a == b for a, b in pairs) == 15
    assert CURRENT_CATALOGUE == latest_source(
        "src/fatebridge/data/knowledge/numerology-sources-v1.json", "before"
    )
    assert assert_current_source_edge(root)
    return True


def rebind_r101_record(value, key):
    edge = REFERENCE["records"][key]
    assert canonical(value) == edge["before_sha256"] and value == edge["before"], key
    result = copy.deepcopy(edge["after"])
    assert canonical(result) == edge["after_sha256"]
    assert result["shige"] == value["shige"] and result["verdict"] == value["verdict"]
    return result


def rebind_r101_render_row(value):
    key = f"{value['gua']}:{value['line']}"
    edge = REFERENCE["render_rows"][key]
    assert value == edge["before"], key
    result = copy.deepcopy(edge["after"])
    assert (
        result["lines"] == value["lines"]
        and result["poem_notes"] == value["poem_notes"]
    )
    return result


def rebind_r101_business(value, kind, index):
    edge = REFERENCE["business_edges"][f"{kind}:{index}"]
    body = lambda v: {k: x for k, x in v.items() if k != "snapshot_text"}
    assert canonical(body(value)) == edge["before_body_sha256"]
    assert value["snapshot_text"] == edge["accepted_before_snapshot"]
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
    for key in REFERENCE["math_fields_unchanged"]:
        assert result[key] == value[key], key
    for key in value["heluo_timing"]:
        if key != "selected_texts":
            assert result["heluo_timing"][key] == value["heluo_timing"][key], key
    result["snapshot_text"] = edge["after_snapshot"]
    return result


def rebind_r101_metadata(value, parent=None, path=()):
    # Source words and records are advanced by their complete record edges only.
    if isinstance(value, dict):
        pairs = (
            KNOWLEDGE["provenance_pairs"]
            if parent == "provenance"
            else (
                KNOWLEDGE["source_record_pairs"].get(value.get("key"), {})
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
                result[key] = rebind_r101_metadata(item, key, path + (key,))
        return result
    if isinstance(value, list):
        return [
            rebind_r101_metadata(item, parent, path + (i,))
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
            pairs = dict(FOOTER_ADDENDUM["exact_metadata_footer_pairs"])
            return "".join(
                pairs.get(line.rstrip("\r\n"), line.rstrip("\r\n"))
                + line[len(line.rstrip("\r\n")) :]
                for line in value.splitlines(keepends=True)
            )
    return copy.deepcopy(value)


def rebind_r101_registry(value, domain):
    assert value == KNOWLEDGE["registry_before"][domain], domain
    return copy.deepcopy(KNOWLEDGE["registry_after"][domain])
