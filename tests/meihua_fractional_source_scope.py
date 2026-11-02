"""Review exact parser-call scope and two already captured concurrent deltas."""

import ast
from copy import deepcopy
from pathlib import Path

PATHS = (
    "application/meihua_clock_binding.py",
    "utils/civil_clock.py",
    "core/requests/divination.py",
)


def dump(node):
    return ast.dump(node, include_attributes=False)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def assert_only_fractional_parsing_changed(root, before_path):
    current = ast.parse((Path(root) / PATHS[0]).read_bytes())
    original = ast.parse(Path(before_path).read_bytes())
    imports = [
        n
        for n in current.body
        if isinstance(n, ast.ImportFrom) and n.module == "fatebridge.utils.civil_clock"
    ]
    require(len(imports) == 1, "Fractional parser import changed")
    expected = ast.parse(
        "from fatebridge.utils.civil_clock import format_utc_offset, parse_iso_datetime, resolve_civil_clock, utc_instant"
    ).body[0]
    require(dump(imports[0]) == dump(expected), "Fractional parser import changed")
    imports[0].names = [n for n in imports[0].names if n.name != "parse_iso_datetime"]
    func = next(
        n
        for n in current.body
        if isinstance(n, ast.FunctionDef) and n.name == "_clock_datetime"
    )
    expected = ast.parse("parsed = parse_iso_datetime(value)").body[0]
    found = [n for n in func.body if dump(n) == dump(expected)]
    require(len(found) == 1, "Fractional parser call changed")
    func.body[func.body.index(found[0])] = ast.parse(
        "parsed = datetime.fromisoformat(value)"
    ).body[0]
    require(
        dump(current) == dump(original),
        "Preexisting clock binding AST changed beyond fractional parser call",
    )


def assert_captured_shared_changes(root, canonical_folder):
    root, canonical_folder = Path(root), Path(canonical_folder)
    current = ast.parse((root / PATHS[1]).read_bytes())
    old = ast.parse((canonical_folder / PATHS[1]).read_bytes())
    added = [
        n
        for n in current.body
        if (isinstance(n, ast.FunctionDef) and n.name == "parse_iso_datetime")
        or (
            isinstance(n, ast.Assign)
            and len(n.targets) == 1
            and isinstance(n.targets[0], ast.Name)
            and n.targets[0].id == "_SUBSECOND_ZERO_OFFSET"
        )
    ]
    require(len(added) == 2, "Captured civil parser extension scope changed")
    for n in added:
        current.body.remove(n)
    require(
        dump(current) == dump(old),
        "Captured civil-clock AST changed outside parser extension",
    )
    current = ast.parse((root / PATHS[2]).read_bytes())
    old = ast.parse((canonical_folder / PATHS[2]).read_bytes())

    def member(tree):
        cls = next(
            n
            for n in tree.body
            if isinstance(n, ast.ClassDef) and n.name == "CanpingRequest"
        )
        return cls, next(
            n
            for n in cls.body
            if isinstance(n, ast.FunctionDef) and n.name == "aware_canping_query"
        )

    cls, actual = member(current)
    _, before = member(old)
    expected = deepcopy(before)
    count = [0, 0]

    class RestoreDeclaredChange(ast.NodeTransformer):
        def visit_ImportFrom(self, node):
            if dump(node) == dump(ast.parse("from datetime import datetime").body[0]):
                count[0] += 1
                return ast.parse(
                    "from fatebridge.utils.civil_clock import parse_iso_datetime"
                ).body[0]
            return self.generic_visit(node)

        def visit_Call(self, node):
            node = self.generic_visit(node)
            if dump(node.func) == dump(
                ast.parse("datetime.fromisoformat", mode="eval").body
            ):
                count[1] += 1
                node.func = ast.Name(id="parse_iso_datetime", ctx=ast.Load())
            return node

    expected = RestoreDeclaredChange().visit(expected)
    require(
        count == [1, 1] and dump(actual) == dump(expected),
        "Captured Canping validator scope changed",
    )
    cls.body[cls.body.index(actual)] = before
    require(
        dump(current) == dump(old),
        "Shared request AST changed outside captured Canping validator",
    )


def assert_prior_guard_body_preserved(current_path, before_path):
    current = ast.parse(Path(current_path).read_bytes())
    old = ast.parse(Path(before_path).read_bytes())
    wrappers = [
        n
        for n in current.body
        if isinstance(n, ast.FunctionDef) and n.name == "reviewed_source_guards"
    ]
    require(len(wrappers) == 1, "Fractional source wrapper missing")
    expected = ast.parse("""def reviewed_source_guards(data, root):
    from tests.meihua_fractional_source_evolution import reviewed_fractional_guards
    return reviewed_fractional_guards(data, root, _reviewed_source_guards_v64)
""").body[0]
    require(dump(wrappers[0]) == dump(expected), "Fractional source wrapper widened")
    current.body.remove(wrappers[0])
    prior = [
        n
        for n in current.body
        if isinstance(n, ast.FunctionDef) and n.name == "_reviewed_source_guards_v64"
    ]
    require(len(prior) == 1, "Prior source guard missing")
    prior[0].name = "reviewed_source_guards"
    require(dump(current) == dump(old), "Prior v64 source guard body changed")
