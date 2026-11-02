"""Portable packaging keeps shared skill references inside the installed root."""

import hashlib
import json
import shutil
from pathlib import Path
from zipfile import ZipFile

import pytest
import yaml

from scripts.build_onda_plugin import ROOT, build, package_files


def test_extracted_plugin_is_self_contained_and_declares_its_backend(tmp_path):
    package = tmp_path / "onda.zip"
    report = build(package)
    assert report["files"] > 13
    assert not any(
        name.startswith(("docs/validation/", "tests/fixtures/"))
        for name in package_files()
    )
    installed = tmp_path / "installed"
    with ZipFile(package) as bundle:
        assert all(not name.startswith(("/", "../")) for name in bundle.namelist())
        bundle.extractall(installed)
    # Re-resolve all actual links from a relocated package, not from the checkout.
    assert set(package_files(installed)) == set(package_files())
    manifest = json.loads((installed / "plugin.json").read_text())
    mcp = json.loads((installed / "mcp.json").read_text())["mcpServers"]["fatebridge"]
    assert manifest["license"] == "Apache-2.0"
    assert mcp["type"] == "stdio" and mcp["command"] == "uvx"
    assert mcp["args"][mcp["args"].index("--from") + 1] == "${PLUGIN_ROOT}"
    assert mcp["cwd"] == "${PLUGIN_ROOT}"
    assert "--isolated" in mcp["args"]
    provenance = json.loads((installed / "backend-source.json").read_text())
    assert provenance["sha256"] == report["backend_source_sha256"]
    assert "src/fatebridge/mcp_server.py" in provenance["files"]
    assert "src/fatebridge/services/jyotish.py" in provenance["files"]
    assert "uv.lock" in provenance["files"]
    assert "backend-requirements.txt" in provenance["files"]
    for name, digest in provenance["files"].items():
        assert hashlib.sha256((installed / name).read_bytes()).hexdigest() == digest
    skills = list((installed / "skills").glob("onda-*"))
    assert len(skills) == 13
    for skill in skills:
        metadata = yaml.safe_load((skill / "agents/openai.yaml").read_text())
        assert metadata["dependencies"]["tools"][0]["value"] == "fatebridge"
        assert isinstance(
            metadata.get("policy", {}).get("allow_implicit_invocation", True), bool
        )
        assert (skill.parent / "_shared/consultation-core.md").is_file()
    assert not any(
        ".venv" in name or name == ".env" for name in package_files(installed)
    )
    with pytest.raises(FileExistsError):
        build(package)


@pytest.mark.parametrize("reference", ["../../outside.md", "missing.md"])
def test_plugin_rejects_missing_or_external_references(tmp_path, reference):
    source = tmp_path / "source"
    source.mkdir()
    for name in (
        "plugin.json",
        "mcp.json",
        "LICENSE",
        "NOTICE",
        "pyproject.toml",
        "uv.lock",
    ):
        shutil.copy2(ROOT / name, source / name)
    (source / "README.md").write_text("")
    skill = source / "skills" / "one"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"[reference]({reference})")
    with pytest.raises(ValueError, match="Unpackageable reference"):
        package_files(source)


def test_packaging_keeps_skill_scripts_and_assets_without_runtime_caches(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for name in (
        "plugin.json",
        "mcp.json",
        "LICENSE",
        "NOTICE",
        "pyproject.toml",
        "uv.lock",
    ):
        shutil.copy2(ROOT / name, source / name)
    (source / "README.md").write_text("")
    skill = source / "skills/example"
    for relative in (
        "SKILL.md",
        "scripts/check.py",
        "assets/icon.png",
        "__pycache__/check.pyc",
        ".env",
    ):
        path = skill / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"example")
    files = package_files(source)
    assert "skills/example/scripts/check.py" in files
    assert "skills/example/assets/icon.png" in files
    assert "skills/example/__pycache__/check.pyc" not in files
    assert "skills/example/.env" not in files
