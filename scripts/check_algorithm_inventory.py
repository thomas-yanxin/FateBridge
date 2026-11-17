"""Check the source inventory's counts, symbols, anchors and public tool list.

This is a documentation consistency check, not a proof of algorithm coverage
or numerical/source acceptance. The inventory deliberately retains those gaps.
"""

from __future__ import annotations

import ast
import json
import re
from collections import Counter
from pathlib import Path

from fatebridge.application.description import spec_is_cli_safe
from fatebridge.services.tool_catalog import CATALOG, mcp_specs, rest_specs

REPO_ROOT = Path(__file__).resolve().parents[1]
INVENTORY = REPO_ROOT / "docs/algorithm-inventory.md"


def is_field_declaration(node: ast.ClassDef) -> bool:
    """Check only a class's own declaration body, not inherited validators."""
    if node.decorator_list or node.keywords:
        return False
    literal_nodes = (
        ast.Constant,
        ast.List,
        ast.Tuple,
        ast.Set,
        ast.Dict,
        ast.UnaryOp,
        ast.USub,
        ast.UAdd,
        ast.Load,
    )
    for member in node.body:
        if isinstance(member, ast.AnnAssign) and isinstance(member.target, ast.Name):
            value = member.value
            if value is None or isinstance(value, ast.Constant) and value.value is None:
                continue
            if not (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id == "Field"
                and all(keyword.arg is not None for keyword in value.keywords)
                and all(
                    isinstance(item, literal_nodes)
                    for arg in [*value.args, *(k.value for k in value.keywords)]
                    for item in ast.walk(arg)
                )
            ):
                return False
        elif isinstance(member, ast.Expr) and isinstance(member.value, ast.Constant):
            if not isinstance(member.value.value, str):
                return False
        elif not isinstance(member, ast.Pass):
            return False
    return True


def module_bindings(tree: ast.Module) -> dict[str, int]:
    """Index simple top-level assignments and annotations, with their own role."""
    indexed: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                indexed[target.id] = node.lineno
    return indexed


def check_inventory(path: Path = INVENTORY) -> tuple[dict[str, int], list[str]]:
    text = path.read_text(encoding="utf-8")
    issues: list[str] = []
    definitions: dict[Path, dict[str, int]] = {}
    bindings: dict[Path, dict[str, int]] = {}
    declarations: dict[Path, set[str]] = {}
    items: list[tuple[Path, str]] = []
    groups = 0
    for number, line in enumerate(text.splitlines(), 1):
        if not line.startswith("| ") or "../src/" not in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 6:
            issues.append(f"line {number}: expected six inventory columns")
            continue
        match = re.search(r"\]\((\.\./src/[^)#]+)#L(\d+)\)", cells[2])
        symbols = re.findall(r"`([^`]+)`", cells[1])
        if match is None or not symbols:
            issues.append(f"line {number}: missing source anchor or named symbol")
            continue
        source = (INVENTORY.parent / match[1]).resolve()
        if not source.is_file():
            issues.append(f"line {number}: missing source {match[1]}")
            continue
        groups += 1
        if source not in definitions:
            indexed: dict[str, int] = {}
            own_declarations: set[str] = set()
            tree = ast.parse(source.read_text(encoding="utf-8"))
            bindings[source] = module_bindings(tree)
            pending: list[tuple[ast.AST, str]] = [(tree, "")]
            while pending:
                node, prefix = pending.pop()
                for child in ast.iter_child_nodes(node):
                    if isinstance(
                        child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
                    ):
                        name = prefix + child.name
                        indexed[name] = child.lineno
                        if isinstance(child, ast.ClassDef) and is_field_declaration(
                            child
                        ):
                            own_declarations.add(name)
                        pending.append((child, name + "."))
                    else:
                        pending.append((child, prefix))
            definitions[source] = indexed
            declarations[source] = own_declarations
        indexed = (
            bindings[source]
            if cells[0].startswith("模块规则与配置")
            else definitions[source]
        )
        for symbol in symbols:
            items.append((source, symbol))
            if symbol not in indexed:
                issues.append(f"line {number}: missing {match[1]}::{symbol}")
            elif (
                cells[0].startswith("输出契约字段声明")
                and symbol not in declarations[source]
            ):
                issues.append(
                    f"line {number}: {symbol} no longer has a declaration-only class body"
                )
        first = symbols[0]
        if first in indexed and int(match[2]) != indexed[first]:
            issues.append(
                f"line {number}: {first} anchor L{match[2]} != L{indexed[first]}"
            )

    live = mcp_specs()
    counts = {
        "catalog_records": len(CATALOG),
        "mcp_tools": len(live),
        "rest_tools": len(rest_specs()),
        "cli_tools": sum(spec_is_cli_safe(spec) for spec in CATALOG),
        "families": len({spec.family for spec in live}),
        "method_ids": len(
            {method.method_id for spec in CATALOG for method in spec.methods}
        ),
        "review_items": len(items),
        "source_groups": groups,
        "unique_symbols": len(set(items)),
        "source_files": len(definitions),
    }
    patterns = {
        "catalog_records": r"中央目录为\s*\*\*(\d+)条记录",
        "mcp_tools": r"MCP(\d+)个入口",
        "rest_tools": r"REST(\d+)个入口",
        "cli_tools": r"CLI(\d+)个入口",
        "families": r"(\d+)个family",
        "method_ids": r"(\d+)个唯一登记method_id",
        "review_items": r"识别了(\d+)个计算、规则及支持职责审查项",
        "source_groups": r"合并为(\d+)个源码位置组",
        "unique_symbols": r"对应(\d+)个不同的文件/符号组合",
        "source_files": r"分布于(\d+)个实现文件",
    }
    for key, pattern in patterns.items():
        documented = re.findall(pattern, text)
        if documented != [str(counts[key])]:
            issues.append(f"{key}: documented {documented}, actual {counts[key]}")

    documented_tools: Counter[tuple[str, str]] = Counter()
    documented_families: dict[str, int] = {}
    for family, count, names in re.findall(
        r"^- `([a-z_]+)`（(\d+)）：(.+)$", text, re.MULTILINE
    ):
        documented_families[family] = int(count)
        for name in re.findall(r"`([a-z][a-z0-9_]+)`", names):
            documented_tools[family, name] += 1
    expected_tools = Counter((spec.family, spec.tool_name) for spec in live)
    if documented_tools != expected_tools:
        issues.append(
            f"MCP list: missing {dict(expected_tools - documented_tools)}, "
            f"extra/repeated {dict(documented_tools - expected_tools)}"
        )
    if documented_families != Counter(spec.family for spec in live):
        issues.append("MCP family counts do not match the live catalog")
    return counts, issues


if __name__ == "__main__":
    counts, issues = check_inventory()
    print(
        json.dumps({"counts": counts, "issues": issues}, ensure_ascii=False, indent=2)
    )
    raise SystemExit(bool(issues))
