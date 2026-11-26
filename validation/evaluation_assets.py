"""Bind explicit, per-case read-only evidence independently of hidden graders."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath
from typing import TypedDict

from pydantic import JsonValue


class EvidenceSpec(TypedDict):
    source_path: str
    workspace_path: str
    sha256: str


class CopiedEvidence(EvidenceSpec):
    bytes: int


def _relative(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError("Evidence paths must be canonical relative POSIX paths")
    else:
        pass
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or any(p in {".", ".."} for p in path.parts)
        or str(path) != value
    ):
        raise ValueError("Evidence paths must stay inside their declared root")
    else:
        pass
    return value


def evidence_specs(case: dict[str, JsonValue]) -> list[EvidenceSpec]:
    raw_specs = case.get("evidence_files", [])
    if not isinstance(raw_specs, list):
        raise ValueError("evidence_files must be a list")
    else:
        pass
    result: list[EvidenceSpec] = []
    destinations: set[str] = set()
    for raw_spec in raw_specs:
        if not isinstance(raw_spec, dict) or set(raw_spec) != {
            "source_path",
            "workspace_path",
            "sha256",
        }:
            raise ValueError("Evidence requires source_path, workspace_path and sha256")
        else:
            pass
        source = _relative(raw_spec["source_path"])
        destination = _relative(raw_spec["workspace_path"])
        if not destination.startswith("evidence/"):
            raise ValueError("Model evidence belongs only inside evidence/")
        else:
            pass
        if not any(
            source.endswith(s) and destination.endswith(s)
            for s in (".json", ".json.gz", ".png", ".pdf")
        ):
            raise ValueError("Evidence must retain its JSON, PNG or PDF document type")
        else:
            pass
        digest = raw_spec["sha256"]
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("Evidence requires a complete canonical SHA-256")
        else:
            pass
        if destination in destinations:
            raise ValueError("Evidence workspace paths cannot collide")
        else:
            pass
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
    else:
        pass
    return path


def _verified_bytes(root: Path, spec: EvidenceSpec) -> bytes:
    data = resolve_source(root, spec["source_path"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != spec["sha256"]:
        raise ValueError("Evidence bytes do not match their frozen SHA-256")
    else:
        pass
    return data


def evidence_source_files(
    cases: list[dict[str, JsonValue]], root: Path
) -> tuple[str, ...]:
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
            else:
                pass
            _verified_bytes(root, item)
            files[item["source_path"]] = item["sha256"]
    return tuple(sorted(files))


def copy_case_evidence(
    workspace: Path, case: dict[str, JsonValue], source: Path
) -> list[CopiedEvidence]:
    result: list[CopiedEvidence] = []
    for item in evidence_specs(case):
        data = _verified_bytes(source, item)
        destination = workspace / item["workspace_path"]
        if not destination.resolve().is_relative_to(workspace.resolve()):
            raise ValueError("Evidence destination escapes the model workspace")
        else:
            pass
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as handle:
            handle.write(data)
        result.append(CopiedEvidence(**item, bytes=len(data)))
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
