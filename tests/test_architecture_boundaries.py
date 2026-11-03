"""Keep domain computation independent of adapters and import cycles."""

import ast
from importlib.util import resolve_name
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "src/fatebridge"
ADAPTERS = (
    "fatebridge.transports",
    "fatebridge.api",
    "fatebridge.cli",
    "fatebridge.mcp_server",
    "fatebridge.mcp_transport",
    "fastapi",
    "fastmcp",
    "mcp",
)


@pytest.fixture(scope="module")
def dependency_graph():
    modules = {
        path: (
            "fatebridge." + ".".join(path.relative_to(SOURCE).with_suffix("").parts)
        ).removesuffix(".__init__")
        for path in SOURCE.rglob("*.py")
    }
    known = set(modules.values())
    graph = {}
    for path, module in modules.items():
        package = module if path.name == "__init__.py" else module.rpartition(".")[0]
        imports = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                dependency = (
                    resolve_name("." * node.level + (node.module or ""), package)
                    if node.level
                    else node.module
                )
                if dependency:
                    imports.add(dependency)
                    imports.update(
                        dependency + "." + alias.name
                        for alias in node.names
                        if dependency + "." + alias.name in known
                    )
            elif isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
        graph[module] = imports
    return graph


def matches(module, prefixes):
    return any(
        module == prefix or module.startswith(prefix + ".") for prefix in prefixes
    )


def test_domain_and_shared_utilities_do_not_depend_on_outer_layers(dependency_graph):
    forbidden = (*ADAPTERS, "fatebridge.application", "fatebridge.services")
    violations = []
    for module, imports in dependency_graph.items():
        if matches(
            module, ("fatebridge.core", "fatebridge.analysis", "fatebridge.utils")
        ):
            violations.extend(
                f"{module} -> {dependency}"
                for dependency in imports
                if matches(dependency, forbidden)
            )
    assert not violations, "\n".join(sorted(violations))


def test_application_and_services_do_not_depend_on_protocol_adapters(
    dependency_graph,
):
    violations = []
    for module, imports in dependency_graph.items():
        if matches(module, ("fatebridge.application", "fatebridge.services")):
            violations.extend(
                f"{module} -> {dependency}"
                for dependency in imports
                if matches(dependency, ADAPTERS)
            )
    assert not violations, "\n".join(sorted(violations))


def test_internal_static_import_graph_has_no_cycles(dependency_graph):
    # Includes function-local imports: postponing an import does not remove
    # the architectural dependency. External libraries are not traversed.
    graph = dependency_graph
    visited = set()
    active = []

    def visit(module):
        assert module not in active, " -> ".join(active + [module])
        if module in visited:
            return
        active.append(module)
        for dependency in sorted(graph[module]):
            if dependency in graph:
                visit(dependency)
        active.pop()
        visited.add(module)

    for module in sorted(graph):
        visit(module)


def test_shared_birth_and_timing_builders_do_not_import_service_entry_points(
    dependency_graph,
):
    graph = dependency_graph
    for module in (
        "fatebridge.services.birth_context",
        "fatebridge.services.birth_payload",
        "fatebridge.services.timing_state",
        "fatebridge.services.timing_snapshots",
    ):
        assert not graph[module] & {
            "fatebridge.services.timing",
            "fatebridge.services.bazi",
            "fatebridge.services.calculation",
            "fatebridge.services.compatibility",
            "fatebridge.services.calendar_tools",
        }, module


def test_domain_catalogs_do_not_import_assembly_or_domain_services(dependency_graph):
    for module, imports in dependency_graph.items():
        if matches(module, ("fatebridge.services.catalog",)):
            assert "fatebridge.services.tool_catalog" not in imports, module
            assert not {
                dependency
                for dependency in imports
                if matches(dependency, ("fatebridge.services",))
                and not matches(dependency, ("fatebridge.services.catalog",))
            }, module
