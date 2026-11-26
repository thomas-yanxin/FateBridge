"""Keep domain computation independent of adapters and import cycles."""

import ast
from importlib.util import resolve_name
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "src/fatebridge"
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
                else:
                    pass
            elif isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            else:
                pass
        graph[module] = imports
    return graph


def matches(module, prefixes):
    return any(
        module == prefix or module.startswith(prefix + ".") for prefix in prefixes
    )


def test_domain_and_shared_utilities_do_not_depend_on_outer_layers(
    dependency_graph,
) -> None:
    forbidden = (
        *ADAPTERS,
        "fatebridge.application",
        "fatebridge.services",
        "validation",
        "fatebridge.validation",
    )
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
        else:
            pass
    assert not violations, "\n".join(sorted(violations))


def test_application_and_services_do_not_depend_on_protocol_adapters(
    dependency_graph,
) -> None:
    violations = []
    for module, imports in dependency_graph.items():
        if matches(module, ("fatebridge.application", "fatebridge.services")):
            violations.extend(
                f"{module} -> {dependency}"
                for dependency in imports
                if matches(dependency, ADAPTERS)
            )
        else:
            pass
    assert not violations, "\n".join(sorted(violations))


def test_internal_static_import_graph_has_no_cycles(dependency_graph) -> None:
    # Includes function-local imports: postponing an import does not remove
    # the architectural dependency. External libraries are not traversed.
    graph = dependency_graph
    visited = set()
    active = []

    def visit(module):
        assert module not in active, " -> ".join(active + [module])
        if module in visited:
            return
        else:
            pass
        active.append(module)
        for dependency in sorted(graph[module]):
            if dependency in graph:
                visit(dependency)
            else:
                pass
        active.pop()
        visited.add(module)

    for module in sorted(graph):
        visit(module)


def test_shared_birth_and_timing_builders_do_not_import_service_entry_points(
    dependency_graph,
) -> None:
    graph = dependency_graph
    for module in (
        "fatebridge.services.birth_context",
        "fatebridge.services.birth_payload",
        "fatebridge.services.timing_state",
    ):
        assert not graph[module] & {
            "fatebridge.services.timing",
            "fatebridge.services.bazi",
            "fatebridge.services.calculation",
            "fatebridge.services.compatibility",
            "fatebridge.services.calendar_tools",
        }, module


def test_domain_catalogs_do_not_import_assembly_or_domain_services(
    dependency_graph,
) -> None:
    for module, imports in dependency_graph.items():
        if matches(module, ("fatebridge.services.catalog",)):
            assert "fatebridge.services.tool_catalog" not in imports, module
            assert not {
                dependency
                for dependency in imports
                if matches(dependency, ("fatebridge.services",))
                and not matches(dependency, ("fatebridge.services.catalog",))
            }, module
        else:
            pass


def test_runtime_does_not_import_offline_validation(dependency_graph) -> None:
    violations = [
        f"{module} -> {dep}"
        for module, imports in dependency_graph.items()
        if not matches(module, ("validation", "fatebridge.validation"))
        for dep in imports
        if matches(dep, ("validation", "fatebridge.validation"))
    ]
    assert not violations, "\n".join(sorted(violations))


def test_shared_execution_layer_has_no_domain_specific_imports(
    dependency_graph,
) -> None:
    forbidden_domain_validators = (
        "fatebridge.core.local_techniques",
        "fatebridge.core.sukuyo.suzhan_clock_input",
        "fatebridge.core.numerology.numerology_clock_input",
        "fatebridge.core.numerology.canping_schedule_validation",
        "fatebridge.core.contracts.output_bazi_anchors",
        "fatebridge.core.contracts.output_ren_anchors",
        "fatebridge.core.physical_ephemeris_policy",
        "fatebridge.core.requests.western_policy",
        "fatebridge.core.astro",
        "fatebridge.core.response_models",
        "fatebridge.application.meihua_clock_binding",
        "fatebridge.application.ren_request_binding",
        "fatebridge.application.human_design_knowledge_binding",
        "fatebridge.application.numerology_knowledge_binding",
    )
    for orchestrator in (
        "fatebridge.application.execution",
        "fatebridge.application.bindings",
        "fatebridge.application.description",
        "fatebridge.application.examples",
    ):
        execution_imports = dependency_graph[orchestrator]
        violations = [
            dep
            for dep in execution_imports
            if matches(dep, forbidden_domain_validators)
        ]
        assert not violations, (orchestrator, sorted(violations))


def test_shared_orchestrators_do_not_hardcode_domain_keys() -> None:
    forbidden_tokens = (
        '"suzhan"',
        '"meihua_analysis"',
        '"meihua_cast"',
        '"heluo"',
        '"canping"',
        '"sixyao"',
        '"jinkou"',
        '"fengshui_"',
        '"astro_chart"',
        '"astro_relative_chart"',
    )
    for rel in (
        "application/execution.py",
        "application/bindings.py",
        "application/description.py",
        "application/examples.py",
        "application/response_delivery.py",
        "services/run_metadata.py",
        "mcp_server.py",
    ):
        text = (SOURCE / rel).read_text(encoding="utf-8")
        found = [token for token in forbidden_tokens if token in text]
        assert not found, (rel, found)
