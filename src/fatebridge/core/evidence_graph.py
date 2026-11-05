"""Hash-bound execution DAG, separating containment from causal declarations."""

from collections import defaultdict, deque
from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue, model_validator

from fatebridge.core.error_budget import declared_error_budget
from fatebridge.core.method_contracts import MethodContract
from fatebridge.core.verified_outputs import (
    collect_source_conflicts,
    collect_verified_outputs,
)
from fatebridge.utils.json_digest import digest


class EvidenceNode(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    node_id: str
    kind: Literal[
        "input",
        "environment",
        "method",
        "result",
        "rule_witness",
        "recorded_operand",
        "mathematical_relation",
    ]
    path: str
    value_sha256: str
    status: str
    method_ids: tuple[str, ...] = ()
    scope: Literal[
        "field", "entire_subtree", "declared_method", "conditional_math_relation"
    ]


class EvidenceEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source: str
    target: str
    relation: Literal[
        "declared_input_dependency",
        "declared_output_dependency",
        "rule_input_witness",
        "contains",
        "verified_math_operand",
    ]


class EvidenceGraph(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    method_id: Literal["execution_dependency_dag_v2"] = "execution_dependency_dag_v2"
    input_sha256: str
    business_output_sha256: str
    nodes: tuple[EvidenceNode, ...]
    edges: tuple[EvidenceEdge, ...]
    output_nodes: dict[str, str]
    runtime_method_ids: tuple[str, ...]
    supplied_input_paths: tuple[str, ...] | None = None
    generated_input_paths: tuple[str, ...] = ()
    unresolved_rule_dependencies: tuple[str, ...]
    resolved_rule_dependencies: tuple[str, ...] = ()
    dependency_resolution: Literal[
        "declared_conservative_inputs_with_observed_rule_witnesses"
    ] = "declared_conservative_inputs_with_observed_rule_witnesses"
    independent_support_count: None = None

    @model_validator(mode="after")
    def closed_acyclic_graph(self) -> "EvidenceGraph":
        ids = {n.node_id for n in self.nodes}
        if len(ids) != len(self.nodes) or not set(self.output_nodes.values()) <= ids:
            raise ValueError("证据节点重复或输出引用不存在")
        incoming = dict.fromkeys(ids, 0)
        successors: dict[str, list[str]] = defaultdict(list)
        seen = set()
        for edge in self.edges:
            key = (edge.source, edge.target, edge.relation)
            if key in seen or edge.source not in ids or edge.target not in ids:
                raise ValueError("证据边重复或悬空")
            seen.add(key)
            incoming[edge.target] += 1
            successors[edge.source].append(edge.target)
        pending = deque(n for n, count in incoming.items() if count == 0)
        visited = 0
        while pending:
            node = pending.popleft()
            visited += 1
            for target in successors[node]:
                incoming[target] -= 1
                if incoming[target] == 0:
                    pending.append(target)
        if visited != len(ids):
            raise ValueError("证据依赖存在循环")
        return self


def affected_nodes(graph: EvidenceGraph, changed: set[str]) -> set[str]:
    """Conservative invalidation; containment propagates a changed subtree too."""
    ids = {n.node_id for n in graph.nodes}
    if not changed <= ids:
        raise ValueError("更正引用了不存在的证据节点")
    successors: dict[str, list[str]] = defaultdict(list)
    for edge in graph.edges:
        successors[edge.source].append(edge.target)
    affected = set(changed)
    pending = deque(changed)
    while pending:
        for target in successors[pending.popleft()]:
            if target not in affected:
                affected.add(target)
                pending.append(target)
    return affected


def shared_input_origins(graph: EvidenceGraph, conclusions: set[str]) -> set[str]:
    """Return common original facts, never a numerical confidence increase."""
    ids = {n.node_id for n in graph.nodes}
    if not conclusions <= ids or not conclusions:
        raise ValueError("需提供存在的结论节点")
    parents: dict[str, list[str]] = defaultdict(list)
    for edge in graph.edges:
        if edge.relation != "contains":
            parents[edge.target].append(edge.source)
    inputs = {n.node_id for n in graph.nodes if n.kind == "input"}
    origins = []
    for conclusion in conclusions:
        visited, pending = set(), [conclusion]
        while pending:
            node = pending.pop()
            if node not in visited:
                visited.add(node)
                pending.extend(parents[node])
        origins.append(visited & inputs)
    return set.intersection(*origins)


def execution_evidence(
    methods: tuple[MethodContract, ...],
    inputs: dict[str, JsonValue],
    payload: dict[str, JsonValue],
    input_sha256: str,
    supplied_fields: frozenset[str] | None = None,
    generated_fields: frozenset[str] = frozenset(),
    runtime_subtree_sha256: str | None = None,
) -> dict[str, JsonValue]:
    nodes: list[EvidenceNode] = []
    edges: list[EvidenceEdge] = []
    input_ids = []
    if runtime_subtree_sha256 is not None:
        input_ids.append("environment:runtime")
        nodes.append(
            EvidenceNode(
                node_id="environment:runtime",
                kind="environment",
                path="/run_metadata/runtime",
                value_sha256=runtime_subtree_sha256,
                status="reported_environment_snapshot",
                scope="entire_subtree",
            )
        )
    for field, value in sorted(inputs.items()):
        node_id = f"input:{field}"
        input_ids.append(node_id)
        nodes.append(
            EvidenceNode(
                node_id=node_id,
                kind="input",
                path="/" + field.replace("~", "~0").replace("/", "~1"),
                value_sha256=digest(value),
                status=(
                    "generated"
                    if field in generated_fields
                    else (
                        "explicit_null"
                        if value is None
                        and supplied_fields is not None
                        and field in supplied_fields
                        else (
                            "not_provided"
                            if value is None
                            else (
                                "presence_not_supplied"
                                if supplied_fields is None
                                else (
                                    "provided"
                                    if field in supplied_fields
                                    else "defaulted"
                                )
                            )
                        )
                    )
                ),
                scope="field",
            )
        )
    for method in methods:
        node_id = f"method:{method.method_id}"
        nodes.append(
            EvidenceNode(
                node_id=node_id,
                kind="method",
                path="",
                value_sha256=digest(method.as_manifest()),
                status="declared",
                method_ids=(method.method_id,),
                scope="declared_method",
            )
        )
        # Deliberately conservative until a domain ledger supplies finer input
        # reads: no assertion that all these fields independently caused a score.
        edges.extend(
            EvidenceEdge(source=n, target=node_id, relation="declared_input_dependency")
            for n in input_ids
        )
    roots = {}
    runtime_ids: set[str] = set()
    unresolved: set[str] = set()
    identities: dict[str, list[tuple[str, str]]] = defaultdict(list)
    references: list[tuple[str, str, tuple[str, ...]]] = []
    pending: list[tuple[tuple[str, ...], JsonValue, str | None]] = [
        ((key,), value, None) for key, value in sorted(payload.items())
    ]
    while pending:
        tokens, value, parent = pending.pop()
        path = "/" + "/".join(
            token.replace("~", "~0").replace("/", "~1") for token in tokens
        )
        is_root = parent is None
        is_witness = isinstance(value, dict) and any(
            k in value
            for k in (
                "method_id",
                "rule_trace",
                "ruleset_id",
                "resolution_policy",
                "source_map",
                "assessment_status",
                "status",
                "id",
                "node_id",
                "rule_id",
            )
        )
        owner = parent
        if is_root or is_witness:
            node_id = f"result:{path}"
            identifiers = (
                tuple(
                    sorted(
                        {
                            v
                            for k, v in value.items()
                            if k in {"method_id", "ruleset_id", "resolution_policy"}
                            and isinstance(v, str)
                        }
                    )
                )
                if isinstance(value, dict)
                else ()
            )
            runtime_ids.update(identifiers)
            state = (
                next(
                    (
                        value[k]
                        for k in ("assessment_status", "status")
                        if isinstance(value.get(k), str)
                    ),
                    "emitted_unclassified",
                )
                if isinstance(value, dict)
                else "null_unclassified" if value is None else "emitted_unclassified"
            )
            assert isinstance(state, str)
            nodes.append(
                EvidenceNode(
                    node_id=node_id,
                    kind="result" if is_root else "rule_witness",
                    path=path,
                    value_sha256=digest(value),
                    status=state,
                    method_ids=identifiers,
                    scope="entire_subtree",
                )
            )
            if parent is not None:
                edges.append(
                    EvidenceEdge(source=parent, target=node_id, relation="contains")
                )
            owner = node_id
            if is_root:
                roots[tokens[0]] = node_id
                matching = [
                    m
                    for m in methods
                    if any(p.split(".")[0] == tokens[0] for p in m.output_paths)
                ]
                # Optional facts also retain the conservative execution context.
                for m in matching or methods:
                    edges.append(
                        EvidenceEdge(
                            source=f"method:{m.method_id}",
                            target=node_id,
                            relation="declared_output_dependency",
                        )
                    )
            if is_witness:
                # Existing rule_trace/source_map bytes remain the authoritative
                # witness. Containment is not silently promoted to a causal link.
                unresolved.add(path)
                assert isinstance(value, dict)
                for key in ("id", "node_id", "rule_id"):
                    identifier = value.get(key)
                    if isinstance(identifier, str):
                        identities[identifier].append((path, node_id))
                input_refs: list[str] = []
                for key in (
                    "participants",
                    "depends_on",
                    "evidence_ids",
                    "source_node_ids",
                ):
                    declared = value.get(key)
                    if isinstance(declared, list) and all(
                        isinstance(v, str) for v in declared
                    ):
                        input_refs.extend(v for v in declared if isinstance(v, str))
                if input_refs:
                    references.append((path, node_id, tuple(dict.fromkeys(input_refs))))
        if isinstance(value, dict):
            pending.extend(
                ((*tokens, k), v, owner)
                for k, v in value.items()
                if isinstance(v, (dict, list))
            )
        elif isinstance(value, list):
            pending.extend(
                ((*tokens, str(i)), v, owner)
                for i, v in enumerate(value)
                if isinstance(v, (dict, list))
            )
    resolved = []
    for path, target, refs in references:
        bindings = []
        for ref in refs:
            ranked = []
            for source_path, source in identities.get(ref, []):
                if source_path == path or source_path.startswith(path + "/"):
                    continue
                common = 0
                for a, b in zip(source_path.split("/"), path.split("/")):
                    if a != b:
                        break
                    common += 1
                ranked.append((common, source))
            best = max((rank for rank, _ in ranked), default=-1)
            matches = {source for rank, source in ranked if rank == best}
            if len(matches) != 1:
                break
            bindings.append(next(iter(matches)))
        if len(bindings) == len(refs):
            edges.extend(
                EvidenceEdge(
                    source=source, target=target, relation="rule_input_witness"
                )
                for source in dict.fromkeys(bindings)
            )
            unresolved.discard(path)
            resolved.append(path)
    mathematical = collect_verified_outputs(payload)
    source_conflicts = collect_source_conflicts(payload, mathematical)
    original_nodes = tuple(n for n in nodes if n.kind in {"result", "rule_witness"})
    operand_ids: set[str] = set()
    for witness in mathematical:
        target = "math:" + witness.method_id + ":" + witness.output_path
        nodes.append(
            EvidenceNode(
                node_id=target,
                kind="mathematical_relation",
                path=witness.output_path,
                value_sha256=digest(witness.model_dump(mode="json")),
                status="verified_given_recorded_operands",
                method_ids=(witness.method_id,),
                scope="conditional_math_relation",
            )
        )
        math_owner = max(
            (
                n
                for n in original_nodes
                if witness.output_path == n.path
                or witness.output_path.startswith(n.path + "/")
            ),
            key=lambda n: len(n.path),
        )
        edges.append(
            EvidenceEdge(source=math_owner.node_id, target=target, relation="contains")
        )
        for operand in witness.operands:
            identifier = "operand:" + operand.path
            if identifier not in operand_ids:
                operand_ids.add(identifier)
                nodes.append(
                    EvidenceNode(
                        node_id=identifier,
                        kind="recorded_operand",
                        path=operand.path,
                        value_sha256=operand.value_sha256,
                        status="upstream_value_not_proved",
                        scope="field",
                    )
                )
                operand_parent = max(
                    (
                        n
                        for n in original_nodes
                        if operand.path == n.path
                        or operand.path.startswith(n.path + "/")
                    ),
                    key=lambda n: len(n.path),
                )
                edges.append(
                    EvidenceEdge(
                        source=operand_parent.node_id,
                        target=identifier,
                        relation="contains",
                    )
                )
            edges.append(
                EvidenceEdge(
                    source=identifier, target=target, relation="verified_math_operand"
                )
            )
    graph = EvidenceGraph(
        input_sha256=input_sha256,
        business_output_sha256=digest(payload),
        nodes=tuple(nodes),
        edges=tuple(edges),
        output_nodes=roots,
        runtime_method_ids=tuple(sorted(runtime_ids)),
        supplied_input_paths=(
            tuple(sorted(supplied_fields)) if supplied_fields is not None else None
        ),
        generated_input_paths=tuple(sorted(generated_fields)),
        unresolved_rule_dependencies=tuple(sorted(unresolved)),
        resolved_rule_dependencies=tuple(sorted(resolved)),
    )
    errors = tuple(
        sorted({source for method in methods for source in method.error_sources})
    )
    # JSON values at this boundary were already checked by the execution contract.
    budget = declared_error_budget(errors, inputs, input_sha256)
    budget["conditional_output_bounds"] = [
        {
            "output_path": w.output_path,
            "unit": w.unit,
            "reference_interval_exact": (
                list(w.reference_interval_exact)
                if w.reference_interval_exact is not None
                else None
            ),
            "reference_minus_reported_interval_exact": (
                list(w.reference_minus_reported_interval_exact)
                if w.reference_minus_reported_interval_exact is not None
                else None
            ),
            "discrete_value": w.discrete_value,
            "proof_path": f"/run_metadata/calculation_evidence/verified_output_relations/{i}",
            "scope": w.proof_scope,
            "physical_accuracy_certified": False,
        }
        for i, w in enumerate(mathematical)
    ]
    return {
        "registered_methods": [method.as_manifest() for method in methods],
        "runtime_method_registry": [
            {
                "method_id": method_id,
                "registration_kind": "observed_domain_policy",
                "witness_paths": [
                    node.path
                    for node in nodes
                    if method_id in node.method_ids and node.kind != "method"
                ],
                "validation_status": "not_inferred_from_execution",
            }
            for method_id in sorted(runtime_ids)
        ],
        "graph": graph.model_dump(mode="json"),
        "error_budget": budget,
        "verified_output_relations": [w.model_dump(mode="json") for w in mathematical],
        "source_conflict_certificates": [c for c in source_conflicts],
        "semantic_proof_scope": "explicit rule-input witnesses retained; conservative method dependencies do not prove every causal read",
        "coverage": {
            "all_business_roots_hash_bound": set(roots) == set(payload),
            "registered_method_count": len(methods),
            "semantic_dependency_proof_complete": False,
            "unresolved_rule_object_count": len(unresolved),
        },
        "conditional_proof_coverage": {
            "verified_conditional_math_output_count": len(mathematical),
            "recorded_source_conflict_certificate_count": len(source_conflicts),
            "producer_instruction_read_set_attested": False,
        },
    }
