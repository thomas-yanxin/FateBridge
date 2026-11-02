"""Reject arbitrary source and code mutations across the explicit metadata edge."""

import ast
import copy
import json
import shutil

import pytest

from tests.canping_witness_knowledge_revision import REVISION
from tests.canping_witness_source_edge import (
    ENVELOPE,
    ROOT,
    _stable_ast,
    assert_r99_source_edge,
)


def test_fixed_current_edge_keeps_all17_sources_and_historical_gateway_identity():
    assert assert_r99_source_edge()


def test_ast_identity_ignores_only_empty_schema_metadata_and_keeps_semantic_fields():
    legacy = ast.parse("def rule(value):\n    return value\n")
    legacy_function = legacy.body[0]
    legacy_function._fields = tuple(
        field for field in legacy_function._fields if field != "type_params"
    )
    if hasattr(legacy_function, "type_params"):
        del legacy_function.type_params
    modern = copy.deepcopy(legacy)
    modern_function = modern.body[0]
    modern_function._fields = (*modern_function._fields, "type_params")
    modern_function.type_params = []
    assert _stable_ast(modern) == _stable_ast(legacy)
    modern_function.type_params = [ast.Name(id="T", ctx=ast.Load())]
    assert _stable_ast(modern) != _stable_ast(legacy)
    different_body = ast.parse("def rule(value):\n    return True\n")
    assert _stable_ast(different_body) != _stable_ast(legacy)


@pytest.mark.parametrize(
    "fault",
    [
        "catalogue_scope",
        "witness_text",
        "primary_uncertainty",
        "heluo_text",
        "gateway_claim",
        "missing_source",
        "rebound_witness_and_catalogue",
    ],
)
def test_current_source_edge_refuses_unreviewed_changes(fault, tmp_path):
    from tests.heluo_current_source_reference import ENVELOPE as CURRENT_ENVELOPE

    paths = [ENVELOPE["catalogue_path"], *CURRENT_ENVELOPE["code"]]
    paths += [
        "src/fatebridge/data/" + source["source_path"]
        for source in REVISION["catalogue_after"]["sources"]
    ]
    for relative in paths:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    catalogue = tmp_path / ENVELOPE["catalogue_path"]
    if fault == "gateway_claim":
        path = tmp_path / ENVELOPE["gateway_path"]
        path.write_text(path.read_text() + "\nauthority_certified = True\n")
    elif fault == "missing_source":
        (tmp_path / paths[-1]).unlink()
    elif fault == "catalogue_scope":
        data = json.loads(catalogue.read_bytes())
        data["scope"] += " unreviewed"
        catalogue.write_text(json.dumps(data, ensure_ascii=False))
    else:
        key = {
            "witness_text": "text_witnesses",
            "rebound_witness_and_catalogue": "text_witnesses",
            "primary_uncertainty": "text_collation",
            "heluo_text": "yaoci_collation",
        }[fault]
        source = next(
            s for s in REVISION["catalogue_after"]["sources"] if s["key"] == key
        )
        path = tmp_path / "src/fatebridge/data" / source["source_path"]
        data = json.loads(path.read_bytes())
        if fault == "primary_uncertainty":
            entry = next(e for e in data["entries"] if e.get("reading_uncertainties"))
            entry["reading_uncertainties"] = {}
        elif fault == "heluo_text":
            data["entries"][0]["yaoci"] += "unreviewed"
        else:
            data["entries"][0]["text"] += "unreviewed"
        path.write_text(json.dumps(data, ensure_ascii=False))
        if fault == "rebound_witness_and_catalogue":
            from tests.canping_witness_source_edge import canonical

            cat = json.loads(catalogue.read_bytes())
            target = next(s for s in cat["sources"] if s["key"] == key)
            target["canonical_content_sha256"] = canonical(data)
            catalogue.write_text(json.dumps(cat, ensure_ascii=False))
    with pytest.raises((AssertionError, FileNotFoundError)):
        assert_r99_source_edge(tmp_path)
