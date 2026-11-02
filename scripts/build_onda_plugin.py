"""Build a portable, closed plugin package without duplicating maintained skills.

Include the exact local backend and dependency declarations with the skills.
Resolve Markdown references so installation is independent of the source checkout.
No hooks, user configuration, virtual environments or caches are included.
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.check_docs import inspect_markdown  # noqa: E402


def backend_files(root=ROOT):
    """Keep executable source/data and dependency declarations, never runtime state."""
    files = {root / name for name in ("pyproject.toml", "uv.lock")}
    files.update(
        p
        for p in (root / "src/fatebridge").rglob("*")
        if p.is_file() and (p.suffix in {".py", ".json"} or p.name == "py.typed")
    )
    return files


def portable_markdown(path, root):
    """Ship runtime guidance without recursively shipping historical experiments.

    Audit archives contain independent checkouts and machine-local receipts.
    Preserve their repository references as explicit text in the plugin; the
    original linked evidence remains untouched in the development repository.
    Maintained runtime references still form a checked, closed local graph.
    """
    text = path.read_text(encoding="utf-8")
    projected = False

    def reference(match):
        nonlocal projected
        label, target = match.groups()
        url = urlsplit(target)
        if url.scheme or url.netloc or not url.path:
            return match.group(0)
        resolved = (path.parent / unquote(url.path)).resolve()
        if any(
            resolved.is_relative_to(root.resolve() / prefix)
            for prefix in ("docs/validation", "tests/fixtures")
        ):
            projected = True
            relative = resolved.relative_to(root.resolve()).as_posix()
            suffix = "#" + url.fragment if url.fragment else ""
            return f"{label}（仓库证据：`{relative}{suffix}`）"
        return match.group(0)

    text = re.sub(r"\[([^\]\n]+)\]\(([^)\n]+)\)", reference, text)
    if projected:
        text += (
            "\n\n本插件包含运行后端和咨询指引。上述仓库证据保留在源码仓库，"
            "历史实验及其独立源码、原始数据和本机日志不随插件分发。\n"
        )
    return text


def package_files(root=ROOT):
    selected = (
        {root / name for name in ("plugin.json", "mcp.json", "LICENSE", "NOTICE")}
        | {
            p
            for p in (root / "skills").rglob("*")
            if p.is_file()
            and not {".venv", "__pycache__", ".git"}.intersection(
                p.relative_to(root).parts
            )
            and p.suffix != ".pyc"
            and not p.name.startswith(".env")
        }
        | backend_files(root)
        | {root / "README.md"}
    )
    for path in selected:
        if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError(f"Unpackageable source: {path}")
    pending = list(selected)
    while pending:
        path = pending.pop()
        if path.suffix != ".md":
            continue
        document = inspect_markdown(portable_markdown(path, root))
        if document.errors:
            raise ValueError(f"Invalid Markdown: {path}")
        for _, reference in document.links:
            url = urlsplit(reference)
            if url.scheme or url.netloc or not url.path:
                continue
            target = (path.parent / unquote(url.path)).resolve()
            if not target.is_relative_to(root.resolve()) or not target.is_file():
                raise ValueError(f"Unpackageable reference: {path}: {reference}")
            if target.name == ".env":
                raise ValueError("Private runtime configuration must not be packaged")
            if target not in selected:
                selected.add(target)
                pending.append(target)
    return {str(path.relative_to(root)): path for path in sorted(selected)}


def build(output, root=ROOT):
    manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    servers = json.loads((root / "mcp.json").read_text(encoding="utf-8"))
    if not manifest["name"] or not servers["mcpServers"]:
        raise ValueError("Plugin identity and MCP wiring are required")
    files = package_files(root)
    requirements = subprocess.run(
        [
            "uv",
            "export",
            "--locked",
            "--no-dev",
            "--no-emit-project",
            "--format",
            "requirements-txt",
            "--no-header",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    source_bytes = {name: path.read_bytes() for name, path in files.items()}
    contents = {
        name: (
            portable_markdown(path, root).encode("utf-8")
            if path.suffix == ".md"
            else source_bytes[name]
        )
        for name, path in files.items()
    }
    if any(path.read_bytes() != source_bytes[name] for name, path in files.items()):
        raise RuntimeError(
            "Source changed while packaging; rebuild from a stable snapshot"
        )
    backend = {
        str(path.relative_to(root)): hashlib.sha256(
            contents[str(path.relative_to(root))]
        ).hexdigest()
        for path in sorted(backend_files(root))
    }
    backend["backend-requirements.txt"] = hashlib.sha256(
        requirements.encode()
    ).hexdigest()
    backend_sha256 = hashlib.sha256(
        json.dumps(backend, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Never replace a prior artifact without the caller choosing a new path.
    with ZipFile(output, "x", compression=ZIP_DEFLATED) as bundle:
        for relative, content in contents.items():
            entry = ZipInfo(relative)
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            bundle.writestr(entry, content)
        dependencies = ZipInfo("backend-requirements.txt")
        dependencies.compress_type = ZIP_DEFLATED
        dependencies.external_attr = 0o100644 << 16
        bundle.writestr(dependencies, requirements)
        provenance = ZipInfo("backend-source.json")
        provenance.compress_type = ZIP_DEFLATED
        provenance.external_attr = 0o100644 << 16
        bundle.writestr(
            provenance,
            json.dumps(
                {"sha256": backend_sha256, "files": backend},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
    return {
        "path": str(output.resolve()),
        "files": len(files) + 2,
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "plugin": manifest["name"],
        "version": manifest["version"],
        "backend_source_sha256": backend_sha256,
        "scope": "portable package; host installation is a separate acceptance step",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output.expanduser()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
