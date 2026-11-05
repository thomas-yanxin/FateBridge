"""Keep the selected early witnesses fixed even after coordinated rehashing."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_reference_identity_v1"
PIN = "30afbca8ef0f318cbfe9a72333ea69d62b49118eff055d703d9157042b125e69"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protocol():
    assert sha(CORPUS / "freeze.json") == PIN
    frozen = json.loads((CORPUS / "freeze.json").read_text())
    assert {p.name for p in CORPUS.iterdir()} == set(frozen["files"]) | {"freeze.json"}
    for name, digest in frozen["files"].items():
        assert sha(CORPUS / name) == digest
    return json.loads((CORPUS / "protocol.json").read_text())


PROTOCOL = protocol()
CONFIGS = {row["id"]: row for row in PROTOCOL["corpora"]}


def audit_module(config):
    # The optional root permits an actual red run with the frozen earlier code.
    source_root = Path(os.environ.get("REN_REFERENCE_AUDIT_SOURCE", ROOT))
    path = source_root / config["script"]
    spec = importlib.util.spec_from_file_location(
        "identity_probe_" + config["id"], path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = ROOT  # Older referenced witnesses stay in this test checkout.
    return module


def copy_reference(config, target):
    def copy_file(source, destination):
        # Large, read-only scans need no duplicate; JSON mutations use real copies.
        if Path(source).suffix == ".pdf":
            Path(destination).symlink_to(Path(source).resolve())
            return destination
        return shutil.copy2(source, destination)

    shutil.copytree(ROOT / config["folder"], target, copy_function=copy_file)


def rewrite_and_rehash(target, probe):
    path = target / probe["file"]
    data = json.loads(path.read_text())
    leaf = data
    for key in probe["path"][:-1]:
        leaf = leaf[key]
    leaf[probe["path"][-1]] = probe["value"]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    manifest_path = target / "freeze.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][probe["file"]] = sha(path)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


@pytest.mark.parametrize("config", PROTOCOL["corpora"], ids=lambda c: c["id"])
def test_unchanged_selected_reference_and_copied_reference_are_accepted(
    config, tmp_path
):
    source = ROOT / config["folder"]
    assert sha(source / "freeze.json") == config["freeze_sha256"]
    module = audit_module(config)
    load = getattr(module, config["loader"])
    expected = load(source)
    copy_reference(config, tmp_path / "corpus")
    assert load(tmp_path / "corpus") == expected


@pytest.mark.parametrize("probe", PROTOCOL["probes"], ids=lambda p: p["id"])
def test_coordinated_reference_rewrite_cannot_replace_selected_witness(probe, tmp_path):
    config = CONFIGS[probe["corpus"]]
    original = ROOT / config["folder"]
    before = {p.name: sha(p) for p in original.iterdir()}
    target = tmp_path / "corpus"
    copy_reference(config, target)
    rewrite_and_rehash(target, probe)
    # The altered content really agrees with its altered local checksum.
    manifest = json.loads((target / "freeze.json").read_text())
    assert sha(target / probe["file"]) == manifest["files"][probe["file"]]
    assert sha(target / "freeze.json") != config["freeze_sha256"]
    module = audit_module(config)
    with pytest.raises(ValueError, match="[Ii]dentity"):
        getattr(module, config["loader"])(target)
    assert {p.name: sha(p) for p in original.iterdir()} == before
