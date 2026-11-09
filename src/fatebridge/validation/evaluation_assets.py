"""Bind explicit, per-case read-only evidence independently of hidden graders."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath
from typing import Any


def _relative(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError("Evidence paths must be canonical relative POSIX paths")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or any(p in {".", ".."} for p in path.parts)
        or str(path) != value
    ):
        raise ValueError("Evidence paths must stay inside their declared root")
    return value


def evidence_specs(case: dict[str, Any]) -> list[dict[str, str]]:
    raw = case.get("evidence_files", [])
    if not isinstance(raw, list):
        raise ValueError("evidence_files must be a list")
    result, destinations = [], set()
    for item in raw:
        if not isinstance(item, dict) or set(item) != {
            "source_path",
            "workspace_path",
            "sha256",
        }:
            raise ValueError("Evidence requires source_path, workspace_path and sha256")
        source = _relative(item["source_path"])
        destination = _relative(item["workspace_path"])
        if not destination.startswith("evidence/"):
            raise ValueError("Model evidence belongs only inside evidence/")
        if not any(
            source.endswith(s) and destination.endswith(s)
            for s in (".json", ".json.gz", ".png", ".pdf")
        ):
            raise ValueError("Evidence must retain its JSON, PNG or PDF document type")
        digest = item["sha256"]
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("Evidence requires a complete canonical SHA-256")
        if destination in destinations:
            raise ValueError("Evidence workspace paths cannot collide")
        destinations.add(destination)
        result.append(
            {"source_path": source, "workspace_path": destination, "sha256": digest}
        )
    return result


def resolve_source(root: Path, relative: str) -> Path:
    relative = _relative(relative)
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(
            "Evidence source must be an existing file inside its source root"
        )
    return path


def _verified_bytes(root: Path, item: dict[str, str]) -> bytes:
    data = resolve_source(root, item["source_path"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise ValueError("Evidence bytes do not match their frozen SHA-256")
    return data


def evidence_source_files(cases: list[dict[str, Any]], root: Path) -> tuple[str, ...]:
    files: dict[str, str] = {}
    for case in cases:
        for item in evidence_specs(case):
            if (
                item["source_path"] in files
                and files[item["source_path"]] != item["sha256"]
            ):
                raise ValueError(
                    "Cases cannot bind different versions of one source file"
                )
            _verified_bytes(root, item)
            files[item["source_path"]] = item["sha256"]
    return tuple(sorted(files))


def copy_case_evidence(
    workspace: Path, case: dict[str, Any], source: Path
) -> list[dict[str, Any]]:
    result = []
    for item in evidence_specs(case):
        data = _verified_bytes(source, item)
        destination = workspace / item["workspace_path"]
        if not destination.resolve().is_relative_to(workspace.resolve()):
            raise ValueError("Evidence destination escapes the model workspace")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as handle:
            handle.write(data)
        result.append({**item, "bytes": len(data)})
    return result


def prepare_evidence_workspace(workspace: Path, source: Path) -> None:
    """Expose reviewed documents; keep the complete MCP backend outside it.

    This is an instruction boundary, not a claim that the read-only CLI sandbox
    prevents every outside read. Actual model reading behavior needs review.
    """
    instructions = (source / "AGENTS.md").read_text(encoding="utf-8")
    (workspace / "AGENTS.md").write_text(
        instructions + "\n## 原页与回执验收环境\n"
        "本轮是工程资料一致性审查，只读本目录evidence文件和FateBridge实际返回的清单及结果文件。"
        "不读取本目录以外的后台源码、历史评分、预写答案或其他命例材料；不安装、不写源文件、"
        "不访问其他服务或发送消息。完整后台仍供MCP工具使用，目录隔离本身不证明你已读取原页。\n",
        encoding="utf-8",
    )
