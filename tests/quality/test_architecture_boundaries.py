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
        "fatebridge.core.sukuyo.suzhan_clock_input",
        "fatebridge.core.numerology.numerology_clock_input",
        "fatebridge.core.numerology.canping_schedule_validation",
        "fatebridge.core.contracts.bazi",
        "fatebridge.core.contracts.sanshi",
        "fatebridge.core.physical_ephemeris_policy",
        "fatebridge.core.astro",
        "fatebridge.core.response_models",
    )
    for orchestrator in (
        "fatebridge.application.execution",
        "fatebridge.application.bindings",
        "fatebridge.application.batch",
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


def test_application_layer_has_zero_domain_imports(dependency_graph) -> None:
    allowed_shared_infra = (
        "fatebridge.application",
        "fatebridge.utils",
        "fatebridge.core.batch_cache",
        "fatebridge.core.execution_context",
        "fatebridge.core.public_output",
        "fatebridge.core.receipt_models",
        "fatebridge.core.reproducibility",
        "fatebridge.core.schema_cache",
        "fatebridge.services.replay_metadata",
        "fatebridge.services.run_metadata",
    )
    violations: list[str] = []
    for module, imports in dependency_graph.items():
        if matches(module, ("fatebridge.application",)):
            for dep in imports:
                if (
                    dep.startswith("fatebridge.")
                    and dep not in {"fatebridge.core", "fatebridge.services"}
                    and not matches(dep, allowed_shared_infra)
                ):
                    violations.append(f"{module} -> {dep}")
    assert not violations, "\n".join(sorted(violations))


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
        "application/batch.py",
        "application/description.py",
        "application/examples.py",
        "application/response_delivery.py",
        "services/run_metadata.py",
        "mcp_server.py",
    ):
        text = (SOURCE / rel).read_text(encoding="utf-8")
        found = [token for token in forbidden_tokens if token in text]
        assert not found, (rel, found)


def test_core_does_not_import_installers_or_obsolete_layers(dependency_graph) -> None:
    violations: list[str] = []
    for module, imports in dependency_graph.items():
        if not matches(module, ("fatebridge.core",)):
            continue
        parts = module.split(".")
        is_domain_pkg = (
            len(parts) >= 3
            and parts[2] not in {"contracts", "requests"}
            and (SOURCE / "core" / parts[2]).is_dir()
        )
        for dep in imports:
            if (
                dep.startswith("fatebridge.fetch_")
                or matches(dep, ("fatebridge.core.local_techniques",))
                or dep.startswith("fatebridge.core.contracts.output_")
                or (is_domain_pkg and matches(dep, ("fatebridge.core.requests",)))
            ):
                violations.append(f"{module} -> {dep}")
    assert not violations, "\n".join(sorted(violations))


def test_metaphysics_common_group_a_symbols_are_not_reintroduced() -> None:
    group_a_symbols = frozenset(
        {
            "SEXAGENARY_CYCLE",
            "SEXAGENARY_INDEX",
            "ELEMENT_GENERATES",
            "ELEMENT_CONTROLS",
            "XUN_HEADS",
            "KONGWANG_BY_XUN_HEAD",
            "SIX_HARMONY_BRANCHES",
            "SIX_CLASH_BRANCHES",
            "SIX_HARM_BRANCHES",
            "rotate_sequence",
            "stem_element_text",
            "branch_element_text",
            "ganzhi_text",
            "sexagenary_index_for",
            "sexagenary_text",
            "xun_head_for_ganzhi",
            "kongwang_for_ganzhi",
        }
    )
    common_path = SOURCE / "core/metaphysics/common.py"
    common_tree = ast.parse(common_path.read_text(encoding="utf-8"))
    defined_in_common: list[str] = []
    for node in common_tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in group_a_symbols:
                defined_in_common.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in group_a_symbols:
                    defined_in_common.append(target.id)
    assert not defined_in_common, defined_in_common

    imported_violations: list[str] = []
    for path in sorted(SOURCE.rglob("*.py")):
        rel = path.relative_to(SOURCE).as_posix()
        mod = (
            "fatebridge." + ".".join(path.relative_to(SOURCE).with_suffix("").parts)
        ).removesuffix(".__init__")
        package = mod if path.name == "__init__.py" else mod.rpartition(".")[0]
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                target = (
                    resolve_name("." * node.level + (node.module or ""), package)
                    if node.level
                    else node.module
                )
                if target == "fatebridge.core.metaphysics.common":
                    bad = [
                        alias.name
                        for alias in node.names
                        if alias.name in group_a_symbols
                    ]
                    if bad:
                        imported_violations.append(f"{rel}: {bad}")
    assert not imported_violations, "\n".join(imported_violations)


def test_core_cross_domain_imports_are_explicitly_allowlisted(
    dependency_graph,
) -> None:
    allowed_substrates = (
        "fatebridge.core.astro",
        "fatebridge.core.bazi.calendar",
        "fatebridge.core.bazi.timing",
        "fatebridge.core.metaphysics.common",
        "fatebridge.core.metaphysics.seed",
        "fatebridge.core.contracts",
    )
    allowed_legacy_edges = frozenset(
        {
            (
                "fatebridge.core.heluo.chart",
                "fatebridge.core.numerology.numerology_inputs",
            ),
            (
                "fatebridge.core.heluo.heluo",
                "fatebridge.core.numerology.numerology_inputs",
            ),
            (
                "fatebridge.core.numerology.numerology_knowledge",
                "fatebridge.core.heluo.texts",
            ),
            ("fatebridge.core.metaphysics.seed", "fatebridge.core.ziwei.calendar"),
            ("fatebridge.core.metaphysics.sanshi", "fatebridge.core.qimen"),
        }
    )
    violations: list[str] = []
    for module, imports in dependency_graph.items():
        if not module.startswith("fatebridge.core."):
            continue
        parts = module.split(".")
        if len(parts) < 3:
            continue
        pkg = parts[2]
        if pkg in {"contracts", "requests"} or not (SOURCE / "core" / pkg).is_dir():
            continue
        for dep in imports:
            if not dep.startswith("fatebridge.core."):
                continue
            other_pkg = dep.split(".")[2]
            if other_pkg == pkg or not (SOURCE / "core" / other_pkg).is_dir():
                continue
            if (
                matches(dep, allowed_substrates)
                or (module, dep) in allowed_legacy_edges
            ):
                continue
            violations.append(f"{module} -> {dep}")
    assert not violations, "\n".join(sorted(violations))


def test_in_function_imports_ratchet() -> None:
    allowed_in_function_imports = frozenset(
        {
            ("__init__.py", "fatebridge.application.batch"),
            ("__init__.py", "fatebridge.application.discovery"),
            ("__init__.py", "fatebridge.application.execution"),
            ("__init__.py", "fatebridge.services.tool_catalog"),
            ("__init__.py", "fatebridge.utils.errors"),
            ("api.py", "uvicorn"),
            ("application/batch.py", "fatebridge.utils.places"),
            ("application/bindings.py", "fatebridge.utils.birth_input"),
            ("application/discovery.py", "fatebridge.application.batch"),
            ("application/examples.py", "pydantic"),
            ("cli.py", "fatebridge.application.batch"),
            ("cli.py", "fatebridge.application.discovery"),
            ("cli.py", "fatebridge.application.examples"),
            ("cli.py", "fatebridge.application.execution"),
            ("cli.py", "fatebridge.diagnostics"),
            ("cli.py", "fatebridge.utils.errors"),
            ("cli.py", "fatebridge.utils.formatting"),
            ("cli_arguments.py", "fatebridge.application.description"),
            ("cli_arguments.py", "fatebridge.core.execution_context"),
            ("core/astro/astrology_lifespan.py", "fatebridge.core.astro"),
            (
                "core/astro/astrology_lifespan.py",
                "fatebridge.core.ephemeris_runtime",
            ),
            ("core/astro/astrology_lifespan.py", "fatebridge.core.jpl_ephemeris"),
            ("core/astro/solar_arc.py", "bisect"),
            ("core/fengshui/models.py", "dateutil.tz"),
            ("core/fengshui/models.py", "fatebridge.core.fengshui.calendar"),
            ("core/guolao/ephemeris.py", "fatebridge.core.almanac"),
            ("core/jyotish/shadbala.py", "datetime"),
            ("core/jyotish/yogas.py", "fatebridge.core.astro"),
            ("core/jyotish/yogas.py", "fatebridge.core.jyotish.panchanga"),
            ("core/knowledge_rule_tables.py", "fatebridge.core.classical_western"),
            ("core/knowledge_rule_tables.py", "fatebridge.core.qimen"),
            ("core/meihua/casting.py", "fatebridge.core.divination"),
            ("core/meihua/casting.py", "fatebridge.utils.places"),
            ("core/meihua/casting.py", "fatebridge.utils.solar_time"),
            ("core/qimen/calendar.py", "fatebridge.utils.civil_time"),
            ("core/requests/base.py", "fatebridge.utils.places"),
            ("core/requests/birth.py", "fatebridge.core.astro.birth"),
            ("core/requests/divination.py", "fatebridge.core.astrodice"),
            (
                "core/requests/divination.py",
                "fatebridge.core.numerology.numerology_clock_input",
            ),
            (
                "core/requests/divination.py",
                "fatebridge.core.numerology.numerology_inputs",
            ),
            ("core/requests/human_design.py", "fatebridge.core.human_design.cycles"),
            ("core/requests/human_design.py", "fatebridge.core.human_design.time"),
            ("core/requests/sanshi.py", "fatebridge.core.metaphysics.jinkou.year_fate"),
            ("mcp_server.py", "fatebridge.application.batch"),
            ("mcp_server.py", "fatebridge.application.discovery"),
            ("mcp_server.py", "fatebridge.application.execution"),
            ("mcp_server.py", "fatebridge.services.tool_catalog"),
            ("mcp_server.py", "fatebridge.utils.errors"),
            ("mcp_server.py", "pydantic_core"),
            (
                "services/catalog/astro_bindings.py",
                "fatebridge.core.requests.astrology",
            ),
            ("services/catalog/astrology.py", "fatebridge.core.astro.reference"),
            ("services/catalog/bazi.py", "fatebridge.core.contracts.bazi"),
            ("services/catalog/divination.py", "fatebridge.core.liuyao.casting"),
            ("services/catalog/divination.py", "fatebridge.core.requests.divination"),
            (
                "services/catalog/divination.py",
                "fatebridge.core.sukuyo.suzhan_clock_input",
            ),
            ("services/catalog/fengshui.py", "fatebridge.core.fengshui"),
            ("services/catalog/sanshi.py", "fatebridge.core.contracts.sanshi"),
            ("services/tool_catalog.py", "fatebridge.services.catalog.astrology"),
            ("services/tool_catalog.py", "fatebridge.services.catalog.bazi"),
            ("services/tool_catalog.py", "fatebridge.services.catalog.compatibility"),
            ("services/tool_catalog.py", "fatebridge.services.catalog.divination"),
            ("services/tool_catalog.py", "fatebridge.services.catalog.fengshui"),
            ("services/tool_catalog.py", "fatebridge.services.catalog.psychometrics"),
            ("services/tool_catalog.py", "fatebridge.services.catalog.reference"),
            ("services/tool_catalog.py", "fatebridge.services.catalog.sanshi"),
            ("services/tool_catalog.py", "fatebridge.services.catalog.timing"),
            ("services/tool_catalog.py", "fatebridge.services.catalog.western_events"),
            (
                "services/tool_catalog.py",
                "fatebridge.services.catalog.western_lifespan",
            ),
            ("services/tool_catalog.py", "fatebridge.services.catalog.western_timing"),
            ("services/tool_catalog.py", "fatebridge.services.catalog.ziwei"),
            ("services/western_events.py", "fatebridge.core.astro.astrology_events"),
        }
    )
    found: set[tuple[str, str]] = set()
    for path in sorted(SOURCE.rglob("*.py")):
        rel = path.relative_to(SOURCE).as_posix()
        mod = (
            "fatebridge." + ".".join(path.relative_to(SOURCE).with_suffix("").parts)
        ).removesuffix(".__init__")
        package = mod if path.name == "__init__.py" else mod.rpartition(".")[0]
        tree = ast.parse(path.read_text(encoding="utf-8"))

        def walk(node: ast.AST, in_fn: bool = False) -> None:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                in_fn = True
            elif in_fn and isinstance(node, ast.ImportFrom):
                dep = (
                    resolve_name("." * node.level + (node.module or ""), package)
                    if node.level
                    else node.module
                )
                if dep:
                    found.add((rel, dep))
            elif in_fn and isinstance(node, ast.Import):
                for alias in node.names:
                    found.add((rel, alias.name))
            for child in ast.iter_child_nodes(node):
                walk(child, in_fn)

        walk(tree)
    new_imports = sorted(found - allowed_in_function_imports)
    assert not new_imports, f"New in-function imports disallowed: {new_imports}"


def test_core_broad_except_ratchet() -> None:
    allowed_non_reraising = frozenset(
        {
            ("core/human_design/cycles.py", "_derive_body_contacts"),
            ("core/metaphysics/ren_calendar.py", "solar_longitude_at"),
        }
    )

    def is_broad(handler: ast.ExceptHandler) -> bool:
        if handler.type is None:
            return True
        if isinstance(handler.type, ast.Name):
            return handler.type.id in {"Exception", "BaseException"}
        if isinstance(handler.type, ast.Tuple):
            return any(
                isinstance(elt, ast.Name) and elt.id in {"Exception", "BaseException"}
                for elt in handler.type.elts
            )
        return False

    def terminates_with_raise(stmts: list[ast.stmt]) -> bool:
        if not stmts:
            return False
        last = stmts[-1]
        if isinstance(last, ast.Raise):
            return True
        if isinstance(last, ast.If):
            return terminates_with_raise(last.body) and terminates_with_raise(
                last.orelse
            )
        return False

    violations: set[tuple[str, str]] = set()
    for path in sorted((SOURCE / "core").rglob("*.py")):
        rel = path.relative_to(SOURCE).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))

        def walk(node: ast.AST, qual: tuple[str, ...] = ()) -> None:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = (*qual, node.name)
            elif (
                isinstance(node, ast.ExceptHandler)
                and is_broad(node)
                and not terminates_with_raise(node.body)
            ):
                violations.add((rel, ".".join(qual)))
            for child in ast.iter_child_nodes(node):
                walk(child, qual)

        walk(tree)
    unexpected = sorted(violations - allowed_non_reraising)
    assert not unexpected, f"New non-reraising broad except in core/: {unexpected}"
