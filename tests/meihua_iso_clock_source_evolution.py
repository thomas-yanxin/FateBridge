"""Conditional source review after immutable raw v65 and two-runtime evidence."""

import ast
import hashlib
import json
import os
import tempfile
from pathlib import Path

from tests.meihua_guard_originals import original_helper
from tests.meihua_iso_clock_reference import FOLDER as INPUT_FOLDER
from tests.meihua_iso_clock_reference import MANIFEST_SHA256 as INPUT_SHA
from tests.meihua_iso_clock_reference import fingerprints
from tests.meihua_iso_clock_source_scope import (
    APP_PATH,
    CORE_PATH,
    assert_only_clock_label_decoder_changed,
    assert_prior_fractional_helper_preserved,
)

FOLDER = Path(__file__).parent / "fixtures/meihua_iso_clock_evolution_v66"
MANIFEST_SHA256 = "ebb7a1f09ea8840128d08f9933b6e5fb5403c9fbfadd2b85721d6e69bb5f97ef"
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load():
    raw = (FOLDER / "manifest.json").read_bytes()
    require(sha(raw) == MANIFEST_SHA256, "Clock ISO evolution manifest changed")
    manifest = json.loads(raw)
    for n, h in manifest["files"].items():
        require(
            sha((FOLDER / n).read_bytes()) == h,
            "Clock ISO evolution reference changed: " + n,
        )
    fingerprints()
    data = json.loads((FOLDER / "binding.json").read_bytes())
    require(
        data["input_manifest_sha256"] == INPUT_SHA, "Clock ISO input binding changed"
    )
    require(
        data["raw_v65_source_guard_relabelled_passed"] is False,
        "Raw v65 source rejection relabelled",
    )
    require(
        data["full_guards_before"] == 124
        and data["full_guards_after"] == 125
        and data["named_AST"] == 30,
        "Clock ISO source scope changed",
    )
    require(
        all(data["normal_complete_streams_equal"].values()),
        "Clock ISO normal outputs changed",
    )
    require(
        data["after312_protocol_mismatches"] == 0
        and data["after310_protocol_mismatches"] == 0,
        "Clock ISO literal mismatch hidden",
    )
    require(
        sha(original_helper("meihua_iso_clock_source_scope.py").read_bytes())
        == data["scope_helper_sha256"],
        "Clock ISO scope reviewer changed",
    )
    return load_format_review(data)


def overlay(root, before_bytes):
    """Temporary read-only source links; detach the one restored preimage."""
    manager = tempfile.TemporaryDirectory()
    target = Path(manager.name)
    for file in Path(root).rglob("*"):
        if not file.is_file() or "__pycache__" in file.parts or file.suffix == ".pyc":
            continue
        path = target / file.relative_to(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        os.link(file, path)
    path = target / APP_PATH
    path.unlink()
    path.write_bytes(before_bytes)
    return manager, target


def _reviewed_iso_clock_guards_v66(original_data, root, prior, previous):
    data = load()
    root = Path(root)
    for path, h in data["after_full_files"].items():
        require(
            sha((root / path).read_bytes()) == h,
            "Clock ISO source file changed: " + path,
        )
    assert_only_clock_label_decoder_changed(root, INPUT_FOLDER / "before-binding.py")
    assert_prior_fractional_helper_preserved(
        original_helper("meihua_fractional_source_evolution.py"),
        FOLDER / "before-fractional-helper.py",
    )
    manager, normalized = overlay(
        root, (INPUT_FOLDER / "before-binding.py").read_bytes()
    )
    try:
        full, named = previous(original_data, normalized, prior)
    finally:
        manager.cleanup()
    require(
        len(full) == 124 and sum(map(len, named.values())) == 30,
        "Prior complete guard set changed",
    )
    require(
        full[APP_PATH] == data["before_binding_sha256"] and CORE_PATH not in full,
        "Clock ISO preimage changed",
    )
    full[APP_PATH] = data["after_full_files"][APP_PATH]
    full[CORE_PATH] = data["after_full_files"][CORE_PATH]
    for path, h in full.items():
        require(
            sha((root / path).read_bytes()) == h, "Listed source file changed: " + path
        )
    return full, named


def assert_prior_fractional_scope(root, before_path):
    """Retain old semantic mutations after the exactly reviewed call change."""
    from tests.meihua_fractional_source_scope import (
        assert_only_fractional_parsing_changed,
    )

    assert_only_clock_label_decoder_changed(root, INPUT_FOLDER / "before-binding.py")
    manager, normalized = overlay(
        Path(root), (INPUT_FOLDER / "before-binding.py").read_bytes()
    )
    try:
        assert_only_fractional_parsing_changed(normalized, before_path)
    finally:
        manager.cleanup()


FORMAT_FOLDER = Path(__file__).parent / "fixtures/meihua_iso_clock_format_v66"
FORMAT_SHA256 = "d88fe5c5c83bd0121395bf350eed8cd62d6af5027e59f6950a0f07c7e7cca30e"


def load_format_review(data):
    """One import move after the initial immutable implementation receipt."""
    raw = (FORMAT_FOLDER / "manifest.json").read_bytes()
    require(sha(raw) == FORMAT_SHA256, "Clock ISO format manifest changed")
    for name, h in json.loads(raw)["files"].items():
        require(
            sha((FORMAT_FOLDER / name).read_bytes()) == h,
            "Clock ISO format reference changed: " + name,
        )
    review = json.loads((FORMAT_FOLDER / "review.json").read_bytes())
    require(
        review["initial_evolution_manifest_sha256"] == MANIFEST_SHA256,
        "Clock ISO format source binding changed",
    )
    before = (FORMAT_FOLDER / "before-binding.py").read_bytes()
    after = (FORMAT_FOLDER / "after-binding.py").read_bytes()
    require(
        sha(before) == review["before_sha256"] == data["after_full_files"][APP_PATH],
        "Clock ISO format preimage changed",
    )
    require(sha(after) == review["after_sha256"], "Clock ISO formatted image changed")

    def without_import(raw):
        tree = ast.parse(raw)
        wanted = ast.dump(
            ast.parse(
                "from fatebridge.core.meihua_clock_iso import parse_meihua_clock_label"
            ).body[0],
            include_attributes=False,
        )
        nodes = [
            n for n in tree.body if ast.dump(n, include_attributes=False) == wanted
        ]
        require(len(nodes) == 1, "Clock ISO formatting import changed")
        tree.body.remove(nodes[0])
        return ast.dump(tree, include_attributes=False)

    require(
        without_import(before) == without_import(after),
        "Clock ISO format review changed other AST nodes",
    )
    data["after_full_files"][APP_PATH] = review["after_sha256"]
    data["format_only_followup_review_sha256"] = FORMAT_SHA256
    return data


def reviewed_iso_clock_guards(original_data, root, prior, previous):
    from tests.meihua_volume5_source_evolution import reviewed_volume5_guards

    return reviewed_volume5_guards(
        original_data, root, prior, previous, _reviewed_iso_clock_guards_v66
    )
