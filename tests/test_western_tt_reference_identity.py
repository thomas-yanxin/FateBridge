"""A caller-selected directory cannot silently replace the sealed answers."""

import hashlib
import json
import shutil

import pytest

from scripts.audit_western_tt_events import CORPUS, ROOT, validate_reference_identity


def test_canonical_corpus_is_accepted():
    validate_reference_identity(ROOT / CORPUS)


def test_alternate_reference_and_its_rewritten_manifest_cannot_replace_answers(
    tmp_path,
):
    chosen = tmp_path / "reference"
    shutil.copytree(ROOT / CORPUS, chosen)
    target = chosen / "reference.json.gz"
    target.write_bytes(b"caller-changed answers")
    manifest = json.loads((chosen / "source-files.json").read_text())
    manifest["files"]["reference.json.gz"] = hashlib.sha256(
        target.read_bytes()
    ).hexdigest()
    (chosen / "source-files.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Independent physical reference changed"):
        validate_reference_identity(chosen)
