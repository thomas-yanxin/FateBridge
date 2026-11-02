"""Remove exactly six new validators, their imports and one appended call."""

import ast
from copy import deepcopy
from pathlib import Path

HELPERS = {
    "_same_clock_record",
    "_clock_datetime",
    "_local_clock_matches",
    "_utc_clock_matches",
    "_elapsed_matches",
    "require_meihua_instant_binding",
}


def dump(node):
    return ast.dump(node, include_attributes=False)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def assert_only_instant_validation_added(root, before_path):
    path = Path(root) / "application/meihua_clock_binding.py"
    current = ast.parse(path.read_bytes())
    old = ast.parse(Path(before_path).read_bytes())
    expected_imports = [
        "from fatebridge.utils.civil_clock import format_utc_offset, resolve_civil_clock, utc_instant",
        "from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE",
        "from fatebridge.utils.timezones import timezone_rules_metadata",
    ]
    for source in expected_imports:
        target = dump(ast.parse(source).body[0])
        found = [n for n in current.body if dump(n) == target]
        require(len(found) == 1, "Instant validator import changed or duplicated")
        current.body.remove(found[0])
    imports = [
        n
        for n in current.body
        if isinstance(n, ast.ImportFrom) and n.module == "datetime"
    ]
    require(
        len(imports) == 1
        and dump(imports[0])
        == dump(
            ast.parse("from datetime import datetime, timedelta, timezone").body[0]
        ),
        "Unknown datetime import extension",
    )
    current.body[current.body.index(imports[0])] = ast.parse(
        "from datetime import datetime"
    ).body[0]
    found = [
        n for n in current.body if isinstance(n, ast.FunctionDef) and n.name in HELPERS
    ]
    require(
        {n.name for n in found} == HELPERS and len(found) == 6,
        "Instant validator helper scope changed",
    )
    for n in found:
        current.body.remove(n)
    original = next(
        n
        for n in current.body
        if getattr(n, "name", None) == "require_meihua_clock_binding"
    )
    expected = ast.parse("require_meihua_instant_binding(result, request)").body[0]
    require(
        dump(original.body[-1]) == dump(expected),
        "Instant binding not appended to existing validation",
    )
    original.body.pop()
    require(
        dump(current) == dump(old),
        "Preexisting clock binding AST changed outside the declared appended validator",
    )
