"""Check the source inventory's counts, symbols, anchors and public tool list.

This is a documentation consistency check, not a proof of algorithm coverage
or numerical/source acceptance. The inventory deliberately retains those gaps.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import re
from collections import Counter
from pathlib import Path
from typing import TypedDict

from fatebridge.application.description import spec_is_cli_safe, summarize_spec
from fatebridge.core.schema_cache import model_schema
from fatebridge.services.tool_catalog import CATALOG, mcp_specs, rest_specs

REPO_ROOT = Path(__file__).resolve().parents[1]
INVENTORY = REPO_ROOT / "docs/algorithm-inventory.md"


class DefinitionReviewItem(TypedDict):
    path: str
    symbol: str
    line: int
    kind: str


class StatementReviewItem(TypedDict):
    path: str
    line: int
    kind: str


class UnreviewedInventory(TypedDict):
    definitions: list[DefinitionReviewItem]
    module_bindings: list[DefinitionReviewItem]
    module_statements: list[StatementReviewItem]


def is_field_declaration(node: ast.ClassDef) -> bool:
    """Check only a class's own declaration body, not inherited validators."""
    if node.decorator_list or node.keywords:
        return False
    else:
        pass
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
            else:
                pass
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
            else:
                pass
        elif isinstance(member, ast.Expr) and isinstance(member.value, ast.Constant):
            if not isinstance(member.value.value, str):
                return False
            else:
                pass
        elif not isinstance(member, ast.Pass):
            return False
        else:
            pass
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
            else:
                pass
    return indexed


_SOURCE_LINK = re.compile(r"\]\((\.\./(?:src|validation)/[^)#]+)(?:#L(\d+))?\)")


def _index_source_symbols(
    source: Path,
) -> tuple[dict[str, int], dict[str, int], set[str]]:
    indexed: dict[str, int] = {}
    own_declarations: set[str] = set()
    tree = ast.parse(source.read_text(encoding="utf-8"))
    top_bindings = module_bindings(tree)
    pending: list[tuple[ast.AST, str]] = [(tree, "")]
    while pending:
        node, prefix = pending.pop()
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + child.name
                indexed[name] = child.lineno
                if isinstance(child, ast.ClassDef) and is_field_declaration(child):
                    own_declarations.add(name)
                else:
                    pass
                pending.append((child, name + "."))
            else:
                pending.append((child, prefix))
    return indexed, top_bindings, own_declarations


def check_inventory(path: Path = INVENTORY) -> tuple[dict[str, int], list[str]]:
    text = path.read_text(encoding="utf-8")
    issues: list[str] = []
    definitions: dict[Path, dict[str, int]] = {}
    bindings: dict[Path, dict[str, int]] = {}
    declarations: dict[Path, set[str]] = {}
    items: list[tuple[Path, str]] = []
    groups = 0
    for number, line in enumerate(text.splitlines(), 1):
        if not line.startswith("| ") or (
            "../src/" not in line and "../validation/" not in line
        ):
            continue
        else:
            pass
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 6:
            issues.append(f"line {number}: expected six inventory columns")
            continue
        else:
            pass
        match = _SOURCE_LINK.search(cells[2])
        symbols = re.findall(r"`([^`]+)`", cells[1])
        if match is None or not symbols:
            issues.append(f"line {number}: missing source anchor or named symbol")
            continue
        else:
            pass
        source = (INVENTORY.parent / match[1]).resolve()
        if not source.is_file():
            issues.append(f"line {number}: missing source {match[1]}")
            continue
        else:
            pass
        groups += 1
        if source not in definitions:
            indexed_defs, top_bindings, own_declarations = _index_source_symbols(source)
            definitions[source] = indexed_defs
            bindings[source] = top_bindings
            declarations[source] = own_declarations
        else:
            pass
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
            else:
                pass
        first = symbols[0]
        if (
            match[2] is not None
            and first in indexed
            and int(match[2]) != indexed[first]
        ):
            issues.append(
                f"line {number}: {first} anchor L{match[2]} != L{indexed[first]}"
            )
        else:
            pass

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
        "mcp_tools": r"MCP(\d+)项业务能力",
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
        else:
            pass

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
    else:
        pass
    if documented_families != Counter(spec.family for spec in live):
        issues.append("MCP family counts do not match the live catalog")
    else:
        pass
    return counts, issues


def unreviewed_inventory(
    path: Path = INVENTORY,
    source_root: Path = REPO_ROOT / "src/fatebridge",
) -> UnreviewedInventory:
    """List source identities absent from the named inventory, without grading them.

    Definitions use the inventory's file/qualified-symbol mapping; every queued
    AST definition keeps its own line, including property getter/setter pairs.
    Bindings are direct top-level simple assignments/annotations. A named
    binding covers its current (last) definition, matching module_bindings().
    Module statements exclude definitions, imports and isolated constants;
    this queue overlaps the binding queue and is not an algorithm count.
    """
    named_definitions: set[tuple[Path, str]] = set()
    named_bindings: set[tuple[Path, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ") or (
            "../src/" not in line and "../validation/" not in line
        ):
            continue
        else:
            pass
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 6:
            continue
        else:
            pass
        match = _SOURCE_LINK.search(cells[2])
        if match is None:
            continue
        else:
            pass
        source = (path.parent / match[1]).resolve()
        named = (
            named_bindings
            if cells[0].startswith("模块规则与配置")
            else named_definitions
        )
        named.update((source, symbol) for symbol in re.findall(r"`([^`]+)`", cells[1]))

    report: UnreviewedInventory = {
        "definitions": [],
        "module_bindings": [],
        "module_statements": [],
    }
    source_root = source_root.resolve()
    repository_root = path.resolve().parent.parent
    for source in sorted(source_root.rglob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        source_path = source.relative_to(repository_root).as_posix()
        current_bindings = module_bindings(tree)
        reviewed_statement_lines = {
            line
            for symbol, line in current_bindings.items()
            if (source, symbol) in named_bindings
        }
        pending: list[tuple[ast.AST, str]] = [(tree, "")]
        while pending:
            node, prefix = pending.pop()
            for child in ast.iter_child_nodes(node):
                if isinstance(
                    child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
                ):
                    symbol = prefix + child.name
                    if (source, symbol) not in named_definitions:
                        report["definitions"].append(
                            {
                                "path": source_path,
                                "symbol": symbol,
                                "line": child.lineno,
                                "kind": type(child).__name__,
                            }
                        )
                    else:
                        pass
                    pending.append((child, symbol + "."))
                else:
                    pending.append((child, prefix))
        for node in tree.body:
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            else:
                targets = []
            for target in targets:
                if isinstance(target, ast.Name) and not (
                    (source, target.id) in named_bindings
                    and current_bindings[target.id] == node.lineno
                ):
                    report["module_bindings"].append(
                        {
                            "path": source_path,
                            "symbol": target.id,
                            "line": node.lineno,
                            "kind": type(node).__name__,
                        }
                    )
                else:
                    pass
            if (
                isinstance(
                    node,
                    (
                        ast.ClassDef,
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                        ast.Import,
                        ast.ImportFrom,
                    ),
                )
                or isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                or node.lineno in reviewed_statement_lines
            ):
                continue
            else:
                pass
            report["module_statements"].append(
                {
                    "path": source_path,
                    "line": node.lineno,
                    "kind": type(node).__name__,
                }
            )
    report["definitions"].sort(key=lambda item: (item["path"], item["line"]))
    report["module_bindings"].sort(key=lambda item: (item["path"], item["line"]))
    report["module_statements"].sort(key=lambda item: (item["path"], item["line"]))
    return report


def algorithm_manifest(
    path: Path = INVENTORY,
    source_root: Path = REPO_ROOT / "src/fatebridge",
) -> dict[str, object]:
    """Export current declarations and review scope without executing an audit.

    Full schemas retain nested enums, alternatives and discriminators. They do
    not enumerate continuous inputs or prove runtime-validator/call coverage.
    Priorities are exported only when semantic review explicitly assigns a row.
    The source queues remain separate from semantic review responsibilities.
    """
    responsibilities: list[dict[str, object]] = []
    unparsed_rows: list[dict[str, object]] = []
    manifest_symbols: dict[Path, tuple[dict[str, int], dict[str, int]]] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.startswith("| ") or (
            "../src/" not in line and "../validation/" not in line
        ):
            continue
        else:
            pass
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 6:
            unparsed_rows.append({"inventory_line": number, "text": line})
            continue
        else:
            pass
        match = _SOURCE_LINK.search(cells[2])
        if match is None:
            unparsed_rows.append({"inventory_line": number, "text": line})
            continue
        else:
            pass
        symbols = re.findall(r"`([^`]+)`", cells[1])
        source = (path.parent / match[1]).resolve()
        if match[2] is not None:
            first_line: int | None = int(match[2])
        else:
            if source not in manifest_symbols and source.is_file():
                defs, top_bindings, _ = _index_source_symbols(source)
                manifest_symbols[source] = (defs, top_bindings)
            else:
                pass
            defs, top_bindings = manifest_symbols.get(source, ({}, {}))
            lookup = top_bindings if cells[0].startswith("模块规则与配置") else defs
            first_line = lookup.get(symbols[0]) if symbols else None
        classification = re.match(
            r"(?:模块规则与配置：)?(P[0-3]) · "
            r"(?:(规则计算|数值计算|输入边界|产品约定|解释模板|交付支持|来源支持|类型支持|参数表)：)?",
            cells[0],
        )
        responsibilities.append(
            {
                "inventory_line": number,
                "label": cells[0],
                "priority": classification[1] if classification else None,
                "responsibility_role": classification[2] if classification else None,
                "priority_decision_basis": (
                    "explicit_semantic_review_label"
                    if classification
                    else "unclassified_requires_semantic_review"
                ),
                "responsibilities": cells[1].split("<br>"),
                "symbols": symbols,
                "implementation": {
                    "path": source.relative_to(REPO_ROOT).as_posix(),
                    "first_symbol_line": first_line,
                },
                "consumers_scope": cells[3],
                "source_refs_markdown": cells[4],
                "acceptance_scope": cells[5],
            }
        )

    # Existing catalog ownership supplies schemas, aliases and method contracts;
    # avoid a second manually maintained tool/option registry in the inventory.
    tools: list[dict[str, object]] = []
    for spec in CATALOG:
        request_sources = []
        for owner in spec.request_model.__mro__:
            if not owner.__module__.startswith("fatebridge."):
                continue
            else:
                pass
            source_file = inspect.getsourcefile(owner)
            request_sources.append(
                {
                    "module": owner.__module__,
                    "symbol": owner.__qualname__,
                    "source": (
                        {
                            "path": Path(source_file)
                            .resolve()
                            .relative_to(REPO_ROOT)
                            .as_posix(),
                            "line": inspect.getsourcelines(owner)[1],
                        }
                        if source_file is not None
                        else None
                    ),
                }
            )
        tools.append(
            {
                **summarize_spec(spec),
                "request_model": (
                    f"{spec.request_model.__module__}.{spec.request_model.__qualname__}"
                ),
                "input_schema": model_schema(spec.request_model),
                "request_class_source_refs": request_sources,
                "method_contracts": [method.as_manifest() for method in spec.methods],
            }
        )

    files: list[dict[str, object]] = []
    for source in sorted(source_root.rglob("*")):
        if (
            "__pycache__" in source.parts
            or not source.is_file()
            or not (
                source.suffix == ".py"
                or "data" in source.relative_to(source_root).parts
            )
        ):
            continue
        else:
            pass
        raw = source.read_bytes()
        files.append(
            {
                "path": source.relative_to(REPO_ROOT).as_posix(),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )

    return {
        "manifest_version": "source_review_inventory_v1",
        "scope": {
            "semantic_algorithm_count": None,
            "semantic_inventory_status": "incomplete",
            "tool_schema_scope": "current_catalog_declarations_not_runtime_execution",
            "option_scope": "schemas_and_request_class_sources_not_exhaustive_runtime_selector_domains",
            "priority_scope": "explicit_row_assignments_only_null_requires_review",
            "consumer_scope": "review_navigation_not_a_proven_call_graph",
            "reference_scope": "recorded_sources_not_revalidated_by_export",
            "numerical_acceptance": "not_granted_by_export",
            "predictive_validity": "not_established",
        },
        "priority_order": [
            {
                "priority": "P0",
                "scope": "shared_clocks_calendars_ephemerides_frames_and_sky_geometry",
            },
            {
                "priority": "P1",
                "scope": "system_specific_natal_construction_and_base_rules",
            },
            {
                "priority": "P2",
                "scope": "timing_relationship_rules_interpretation_and_combinations",
            },
            {
                "priority": "P3",
                "scope": "sources_contracts_projection_storage_and_delivery",
            },
        ],
        "generator": {
            "path": Path(__file__).resolve().relative_to(REPO_ROOT).as_posix(),
            "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "inventory": {
            "path": path.relative_to(REPO_ROOT).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        },
        "public_tools": tools,
        "responsibility_groups": responsibilities,
        "unparsed_inventory_rows": unparsed_rows,
        "unreviewed_source_positions": unreviewed_inventory(path, source_root),
        "source_and_data_files": files,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--unreviewed",
        action="store_true",
        help="include unreviewed source identities; queues overlap and are not algorithms",
    )
    modes.add_argument(
        "--manifest",
        action="store_true",
        help="export declarations, review scope and source hashes without running checks",
    )
    args = parser.parse_args()
    if args.manifest:
        print(json.dumps(algorithm_manifest(), ensure_ascii=False, indent=2))
        raise SystemExit(0)
    else:
        pass
    counts, issues = check_inventory()
    report: dict[str, object] = {"counts": counts, "issues": issues}
    if args.unreviewed:
        report["unreviewed"] = unreviewed_inventory()
    else:
        pass
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(bool(issues))
else:
    pass
