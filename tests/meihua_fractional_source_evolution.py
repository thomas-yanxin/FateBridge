"""Reviewed v65 parser binding; raw older failures remain immutable evidence."""

import hashlib
import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path

from tests.meihua_fractional_binding_reference import FOLDER as INPUT_FOLDER
from tests.meihua_fractional_binding_reference import (
    MANIFEST_SHA256 as INPUT_MANIFEST_SHA256,
)
from tests.meihua_fractional_binding_reference import load as load_inputs
from tests.meihua_fractional_source_scope import (
    PATHS,
    assert_captured_shared_changes,
    assert_only_fractional_parsing_changed,
    assert_prior_guard_body_preserved,
)
from tests.meihua_guard_originals import original_helper

FOLDER = Path(__file__).parent / "fixtures/meihua_fractional_evolution_v65"
MANIFEST_SHA256 = "32852e41be58582e9f0c83149bea2b97133bfc4be6e307d73106c14c5ba6b7dd"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load():
    raw = (FOLDER / "manifest.json").read_bytes()
    require(sha(raw) == MANIFEST_SHA256, "Fractional evolution manifest changed")
    manifest = json.loads(raw)
    for name, h in manifest["files"].items():
        require(
            sha((FOLDER / name).read_bytes()) == h,
            "Fractional evolution reference changed: " + name,
        )
    load_inputs()
    data = json.loads((FOLDER / "binding.json").read_bytes())
    require(
        data["input_manifest_sha256"] == INPUT_MANIFEST_SHA256,
        "Fractional input binding changed",
    )
    require(
        data["raw_v64_source_guard_relabelled_passed"] is False,
        "Raw v64 gate relabelled passed",
    )
    require(
        data["before_false_acceptances"] == 56
        and data["after_false_acceptances"] == 0
        and data["valid_controls_kept"] == 18,
        "Fractional fault or control queue changed",
    )
    require(
        data["before_parser_mismatches"] == 12 and data["after_parser_mismatches"] == 0,
        "Parser literal queue changed",
    )
    require(
        data["before_baseline_source_tests"] == {"passed": 167, "failed": 6},
        "Baseline source failures changed",
    )
    require(
        all(data["complete_normal_output_streams_equal"].values())
        and set(data["complete_normal_output_streams_equal"])
        == {"native23927", "public-time340", "bound-clock25"},
        "Normal output queue scope changed",
    )
    require(
        data["production_changes_this_round"] == [PATHS[0]], "Production scope widened"
    )
    require(
        sha(original_helper("meihua_fractional_source_scope.py").read_bytes())
        == data["scope_helper_sha256"],
        "Fractional scope reviewer changed",
    )
    require(
        data["full_guard_count_before"] == 123
        and data["full_guard_count_after"] == 124
        and data["named_AST_count"] == 30,
        "Fractional guard scope changed",
    )
    return data


def _reviewed_fractional_guards_v65(original_data, root, prior):
    data = load()
    root = Path(root)
    for path, record in data["reviewed_files"].items():
        require(
            sha((root / path).read_bytes()) == record["after_sha256"],
            "Fractional source file changed: " + path,
        )
    assert_only_fractional_parsing_changed(
        root, INPUT_FOLDER / "captured-before" / PATHS[0]
    )
    assert_captured_shared_changes(root, INPUT_FOLDER / "canonical-v64")
    assert_prior_guard_body_preserved(
        original_helper("meihua_source_evolution_reference.py"),
        FOLDER / "before-main-helper.py",
    )
    # Run the entire original v64 guard on a temporary reviewed preimage.
    # Every other provided file keeps its actual bytes. No live source is edited.
    with tempfile.TemporaryDirectory() as tmp:
        normalized = Path(tmp)
        for file in root.rglob("*"):
            if (
                not file.is_file()
                or "__pycache__" in file.parts
                or file.suffix == ".pyc"
            ):
                continue
            target = normalized / file.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(file, target)
        for path in PATHS:
            target = normalized / path
            target.unlink()
            target.write_bytes((INPUT_FOLDER / "canonical-v64" / path).read_bytes())
        full, named = prior(original_data, normalized)
    require(
        len(full) == 123 and sum(map(len, named.values())) == 30,
        "Prior complete source scope changed",
    )
    for path in PATHS[:2]:
        require(
            full[path] == data["reviewed_files"][path]["canonical_v64_sha256"],
            "Prior fractional full guard preimage changed",
        )
        full[path] = data["reviewed_files"][path]["after_sha256"]
    require(PATHS[2] not in full, "New shared request guard replaced old file scope")
    full[PATHS[2]] = data["reviewed_files"][PATHS[2]]["after_sha256"]
    for path, h in full.items():
        require(
            sha((root / path).read_bytes()) == h, "Listed source file changed: " + path
        )
    require(
        len(full) == 124 and sum(map(len, named.values())) == 30,
        "Expanded fractional source scope changed",
    )
    return full, deepcopy(named)


def reviewed_clock_source_scope(root, before_folder):
    """Apply the old clock AST guard after reviewing only captured Canping code.

    This is a new conditional check. The raw old guard's rejection remains in
    the receipts; none of its original code or comparison targets is edited.
    """
    from tests.meihua_clock_source_scope import assert_clock_source_scope

    load()
    root = Path(root)
    assert_captured_shared_changes(root, INPUT_FOLDER / "canonical-v64")
    with tempfile.TemporaryDirectory() as tmp:
        normalized = Path(tmp)
        for file in root.rglob("*"):
            if (
                not file.is_file()
                or "__pycache__" in file.parts
                or file.suffix == ".pyc"
            ):
                continue
            target = normalized / file.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(file, target)
        target = normalized / PATHS[2]
        target.unlink()
        target.write_bytes((INPUT_FOLDER / "canonical-v64" / PATHS[2]).read_bytes())
        assert_clock_source_scope(normalized, before_folder)


def reviewed_fractional_guards(original_data, root, prior):
    from tests.meihua_iso_clock_source_evolution import reviewed_iso_clock_guards

    return reviewed_iso_clock_guards(
        original_data, root, prior, _reviewed_fractional_guards_v65
    )
