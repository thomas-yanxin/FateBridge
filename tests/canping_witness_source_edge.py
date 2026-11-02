"""Fixed R99 edge for current sources; original R96 history stays byte-bound."""

import ast
import hashlib
import json
from pathlib import Path

from tests.canping_witness_knowledge_revision import REVISION

ROOT = Path(__file__).parents[1]
F = ROOT / "tests/fixtures/canping_gold_wenming_v1"
RAW = (F / "compatibility/source-envelope-v2.json").read_bytes()
assert (
    hashlib.sha256(RAW).hexdigest()
    == "0b24e1aafd0b95d383f37f7f092e80eccb4547fb3ab3adec1a1ebd9d7180ddae"
)
ENVELOPE = json.loads(RAW)


def _stable_ast(value):
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


def ast_sha(path):
    """Bind the full tree without interpreter-specific empty schema metadata."""
    return ast_sha_text(path.read_text(encoding="utf-8"))


def ast_sha_text(source):
    tree = _stable_ast(ast.parse(source))
    raw = json.dumps(
        tree, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(raw).hexdigest()


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


def assert_r99_source_edge(root=ROOT):
    from tests.heluo_bo23_revision_reference import ENVELOPE as r101_envelope
    from tests.heluo_bo23_revision_reference import (
        assert_r101_source_edge,
        frozen_source,
    )
    from tests.heluo_current_source_reference import frozen_source as latest_source

    old, new = REVISION["catalogue_before"], REVISION["catalogue_after"]
    path = root / ENVELOPE["catalogue_path"]
    raw = path.read_bytes()
    assert new == frozen_source(ENVELOPE["catalogue_path"], "before")
    assert frozen_source(ENVELOPE["catalogue_path"]) == latest_source(
        ENVELOPE["catalogue_path"], "before"
    )
    assert json.loads(raw) == latest_source(ENVELOPE["catalogue_path"])
    assert (
        r101_envelope["data"][ENVELOPE["catalogue_path"]]["before_raw_sha256"]
        == ENVELOPE["after_catalogue_raw_sha256"]
    )
    assert assert_r101_source_edge(root)
    assert (
        canonical(old)
        == REVISION["provenance_pairs"]["source_catalogue_content_sha256"][0]
    )
    assert (
        canonical(new)
        == REVISION["provenance_pairs"]["source_catalogue_content_sha256"][1]
    )
    pairs = list(zip(old["sources"], new["sources"], strict=True))
    assert len(pairs) == 17
    assert [a["key"] for a, b in pairs if a != b] == ["text_witnesses"]
    assert sum(a == b for a, b in pairs) == 16
    for source in json.loads(raw)["sources"]:
        source_path = root / "src/fatebridge/data" / source["source_path"]
        assert (
            canonical(json.loads(source_path.read_bytes()))
            == source["canonical_content_sha256"]
        )
    gateway = ENVELOPE["gateway_path"]
    assert (
        ast_sha_text(frozen_source(gateway, "before"))
        == ENVELOPE["after_gateway_ast_sha256"]
    )
    assert (
        ast_sha(F / ENVELOPE["after_gateway_snapshot"])
        == ENVELOPE["after_gateway_ast_sha256"]
    )
    assert (
        ast_sha(F / ENVELOPE["before_gateway_snapshot"])
        == ENVELOPE["before_gateway_ast_sha256"]
    )
    r96 = ROOT / "tests/fixtures/heluo_ben22_v1/proposed" / gateway
    assert ast_sha(r96) == ENVELOPE["before_gateway_ast_sha256"]
    return True
