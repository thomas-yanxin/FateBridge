"""Projection-safe facts for generating intermediaries; no effective verdict."""

from functools import lru_cache
from itertools import product
from typing import List, Literal, Optional

from pydantic import Field, model_validator

from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_classical_force import ForceSource
from fatebridge.utils.data import (
    BRANCH_HIDDEN_STEMS,
    DESTRUCTION_CYCLE,
    GENERATION_CYCLE,
    STEM_ELEMENTS,
    Element,
)

Pillar = Literal["year", "month", "day", "hour"]
Plane = Literal["stem", "hidden"]
Binding = Literal[
    "not_supplied",
    "binding_recorded",
    "pending_combination_review",
    "no_binding_recorded",
]
PositionState = Literal[
    "adjacent_mediator_between",
    "between_with_gap",
    "outside_interval",
    "shared_pillar_step",
]
ORDER = ("year", "month", "day", "hour")
PhysicalOption = tuple[str, str, Optional[str], Optional[int]]


def _position_state(positions: tuple[str, ...]) -> str:
    i, j, k = (ORDER.index(p) for p in positions)
    if len(set(positions)) < 3:
        return "shared_pillar_step"
    if min(i, k) < j < max(i, k):
        return (
            "adjacent_mediator_between"
            if abs(i - j) == abs(j - k) == 1
            else "between_with_gap"
        )
    return "outside_interval"


@lru_cache(maxsize=4096)
def _physical_options(
    plane: Optional[str],
    stem: Optional[str],
    branch: Optional[str],
    rank: Optional[int],
    element: Optional[str],
) -> tuple[PhysicalOption, ...]:
    """Possible physical facts only; never insert them into a partial output."""
    options: list[PhysicalOption] = [("stem", s, None, None) for s in STEM_ELEMENTS]
    options.extend(
        ("hidden", s, b, r)
        for b, hidden in BRANCH_HIDDEN_STEMS.items()
        for r, s in enumerate(hidden)
    )
    return tuple(
        (p, s, b, r)
        for p, s, b, r in options
        if (plane is None or p == plane)
        and (stem is None or s == stem)
        and (branch is None or b == branch)
        and (rank is None or r == rank)
        and (element is None or STEM_ELEMENTS[s][0].value == element)
    )


@lru_cache(maxsize=4096)
def _possible_path(
    refs: tuple[Optional[str], ...],
    elements: Optional[tuple[str, ...]],
    positions: Optional[tuple[str, ...]],
    plane: Optional[str],
    principal: Optional[bool],
    status: Optional[str],
) -> bool:
    """Known partial facts must admit a physical generating chain.

    The bounded search checks omitted redundant facts without asserting a
    missing pillar, stem, effective root force or usable passage.
    """
    identities = [_node_identity(ref) if ref is not None else None for ref in refs]
    for a in GENERATION_CYCLE:
        middle = GENERATION_CYCLE[a]
        b = GENERATION_CYCLE[middle]
        if DESTRUCTION_CYCLE[a] != b:
            continue
        chain = (a.value, middle.value, b.value)
        if elements is not None and elements != chain:
            continue
        if any(
            n and STEM_ELEMENTS[n[2]][0].value != chain[i]
            for i, n in enumerate(identities)
        ):
            continue
        if positions is not None and any(
            n and n[0] != positions[i] for i, n in enumerate(identities)
        ):
            continue
        pillars = [
            (positions[i],) if positions is not None else (n[0],) if n else ORDER
            for i, n in enumerate(identities)
        ]
        layers = [(n[1],) if n else ("stem", "hidden") for n in identities]
        stems = [
            (
                (n[2],)
                if n
                else tuple(
                    s for s in STEM_ELEMENTS if STEM_ELEMENTS[s][0].value == chain[i]
                )
            )
            for i, n in enumerate(identities)
        ]
        for ps, ls in product(product(*pillars), product(*layers)):
            actual_plane = ls[0] if len(set(ls)) == 1 else "mixed"
            if plane is not None and plane != actual_plane:
                continue
            if status is not None and status != _position_state(ps):
                continue
            if any(
                sum(p == q and layer == "stem" for q, layer in zip(ps, ls)) > 1
                for p in ORDER
            ):
                continue
            if principal is True and actual_plane != "hidden":
                continue
            for ss in product(*stems):
                possibilities = []
                for p in ORDER:
                    local = [
                        s
                        for q, layer, s in zip(ps, ls, ss)
                        if p == q and layer == "hidden"
                    ]
                    if local:
                        possibilities.append(
                            {
                                all(hidden.index(s) == 0 for s in local)
                                for hidden in BRANCH_HIDDEN_STEMS.values()
                                if all(s in hidden for s in local)
                            }
                        )
                if any(not choices for choices in possibilities):
                    continue
                if principal is None:
                    return True
                can_be_principal = actual_plane == "hidden" and all(
                    True in choices for choices in possibilities
                )
                can_be_nonprincipal = actual_plane != "hidden" or any(
                    False in choices for choices in possibilities
                )
                if (principal and can_be_principal) or (
                    principal is False and can_be_nonprincipal
                ):
                    return True
    return False


def _node_identity(ref: str) -> tuple[str, str, str]:
    parts = ref.split(":")
    if (
        len(parts) != 3
        or parts[0] not in ("year", "month", "day", "hour")
        or parts[1] not in ("stem", "hidden")
        or parts[2] not in STEM_ELEMENTS
    ):
        raise ValueError("通关节点引用必须标明实际柱位、干藏层与天干")
    return parts[0], parts[1], parts[2]


class PassageNode(PartialOutput):
    id: Optional[str] = None
    pillar: Optional[Pillar] = None
    plane: Optional[Plane] = None
    stem: Optional[str] = None
    branch: Optional[str] = None
    hidden_rank: Optional[int] = Field(default=None, ge=0, le=2)
    element: Optional[str] = None
    remaining_root_state: Optional[
        Literal[
            "not_supplied", "positive_remaining_budget", "no_positive_remaining_budget"
        ]
    ] = None
    binding_state: Optional[Binding] = None

    @model_validator(mode="after")
    def preserve_physical_node(self) -> "PassageNode":
        parts = _node_identity(self.id) if self.id is not None else None
        if parts is not None:
            for supplied, actual in zip((self.pillar, self.plane, self.stem), parts):
                if supplied is not None and supplied != actual:
                    raise ValueError("通关节点引用不能与其实际柱位、干藏层或天干矛盾")
        stem = self.stem if self.stem is not None else parts[2] if parts else None
        plane = self.plane if self.plane is not None else parts[1] if parts else None
        if stem is not None:
            if stem not in STEM_ELEMENTS:
                raise ValueError("通关节点必须使用实际天干")
            if (
                self.element is not None
                and self.element != STEM_ELEMENTS[stem][0].value
            ):
                raise ValueError("通关节点五行必须忠于实际天干")
        if plane == "stem" and (
            self.branch is not None or self.hidden_rank is not None
        ):
            raise ValueError("透干节点不能冒充支中藏干")
        if plane == "hidden" and self.branch is not None:
            hidden = BRANCH_HIDDEN_STEMS.get(self.branch)
            if hidden is None or (stem is not None and stem not in hidden):
                raise ValueError("藏干节点必须存在于其实际地支")
            if self.hidden_rank is not None and (
                self.hidden_rank >= len(hidden)
                or (stem is not None and hidden[self.hidden_rank] != stem)
            ):
                raise ValueError("藏干序位必须忠于实际地支目录")
        if not _physical_options(
            plane, stem, self.branch, self.hidden_rank, self.element
        ):
            raise ValueError(
                "已给通关节点事实必须容许同一实际透干或藏干，缺项不消除矛盾"
            )
        return self


class PassagePath(PartialOutput):
    from_node: Optional[str] = None
    via_node: Optional[str] = None
    to_node: Optional[str] = None
    plane: Optional[Literal["stem", "hidden", "mixed"]] = None
    elements: Optional[List[str]] = Field(default=None, min_length=3, max_length=3)
    positions: Optional[List[Pillar]] = Field(default=None, min_length=3, max_length=3)
    principal_hidden_only: Optional[bool] = None
    position_status: Optional[PositionState] = None
    all_nodes_have_remaining_roots: Optional[bool] = None
    binding_states: Optional[List[Binding]] = Field(
        default=None, min_length=3, max_length=3
    )
    effective_passage: Optional[Literal["not_adjudicated"]] = None

    @model_validator(mode="after")
    def preserve_calculated_position(self) -> "PassagePath":
        if not _possible_path(
            (self.from_node, self.via_node, self.to_node),
            tuple(self.elements) if self.elements is not None else None,
            tuple(self.positions) if self.positions is not None else None,
            self.plane,
            self.principal_hidden_only,
            self.position_status,
        ):
            raise ValueError(
                "已给通关路径节点引用和事实必须容许同一实体生克链，缺项不消除矛盾"
            )
        if self.elements is not None:
            try:
                a, middle, b = (Element(e) for e in self.elements)
            except ValueError as exc:
                raise ValueError("通关路径必须使用实际五行") from exc
            if not (
                DESTRUCTION_CYCLE[a] == b
                and GENERATION_CYCLE[a] == middle
                and GENERATION_CYCLE[middle] == b
            ):
                raise ValueError("通关候选必须保留实际相克及连续相生的生克链")
        refs = (self.from_node, self.via_node, self.to_node)
        identities = [_node_identity(ref) for ref in refs if ref is not None]
        if len(identities) == 3:
            if self.elements is not None and self.elements != [
                STEM_ELEMENTS[identity[2]][0].value for identity in identities
            ]:
                raise ValueError("通关路径五行必须忠于实际节点引用")
            planes = {identity[1] for identity in identities}
            expected_plane = identities[0][1] if len(planes) == 1 else "mixed"
            if self.plane is not None and self.plane != expected_plane:
                raise ValueError("通关路径干藏层必须忠于实际节点")
            if self.principal_hidden_only is True and planes != {"hidden"}:
                raise ValueError("透干或跨层路径不能冒充本气藏干子集")
        if self.positions is not None:
            order = ("year", "month", "day", "hour")
            i, j, k = (order.index(p) for p in self.positions)
            expected = (
                "shared_pillar_step"
                if len(set(self.positions)) < 3
                else (
                    "adjacent_mediator_between"
                    if abs(i - j) == abs(j - k) == 1 and min(i, k) < j < max(i, k)
                    else (
                        "between_with_gap"
                        if min(i, k) < j < max(i, k)
                        else "outside_interval"
                    )
                )
            )
            if self.position_status is not None and self.position_status != expected:
                raise ValueError("不能把隔位或越位中介伪写为相邻通路")
            for position, ref in zip(
                self.positions, (self.from_node, self.via_node, self.to_node)
            ):
                if ref is not None and ref.split(":", 1)[0] != position:
                    raise ValueError("通关路径节点必须忠于实际柱位")
        return self


class PassageSummary(PartialOutput):
    visible_path_count: Optional[int] = Field(default=None, ge=0)
    principal_hidden_path_count: Optional[int] = Field(default=None, ge=0)
    all_hidden_path_count: Optional[int] = Field(default=None, ge=0)
    mixed_path_count: Optional[int] = Field(default=None, ge=0)
    effective_passage: Optional[Literal["not_adjudicated"]] = None
    calculation_effect: Optional[Literal["none"]] = None


class ClassicalPassage(PartialOutput):
    method_id: Optional[
        Literal[
            "positioned_generating_intermediaries_v1",
            "positioned_generating_intermediaries_v2",
        ]
    ] = None
    source: Optional[ForceSource] = None
    nodes: Optional[List[PassageNode]] = None
    visible_paths: Optional[List[PassagePath]] = None
    principal_hidden_paths: Optional[List[PassagePath]] = None
    all_hidden_paths: Optional[List[PassagePath]] = None
    mixed_paths: Optional[List[PassagePath]] = None
    summary: Optional[PassageSummary] = None
    scope: Optional[str] = None

    @model_validator(mode="after")
    def preserve_same_calculation(self) -> "ClassicalPassage":
        """Check supplied facts together; missing projection context stays unknown."""
        nodes = {n.id: n for n in self.nodes or [] if n.id is not None}
        if len(nodes) != sum(n.id is not None for n in self.nodes or []):
            raise ValueError("同一实体通关节点不能重复计入")
        by_column: dict[str, list[tuple[PhysicalOption, ...]]] = {p: [] for p in ORDER}
        for catalog_node in self.nodes or []:
            identity = (
                _node_identity(catalog_node.id) if catalog_node.id is not None else None
            )
            pillar = catalog_node.pillar or (identity[0] if identity else None)
            options = _physical_options(
                catalog_node.plane or (identity[1] if identity else None),
                catalog_node.stem or (identity[2] if identity else None),
                catalog_node.branch,
                catalog_node.hidden_rank,
                catalog_node.element,
            )
            if pillar is not None:
                by_column[pillar].append(options)
        for column_options in by_column.values():
            visible = [o for o in column_options if all(x[0] == "stem" for x in o)]
            hidden = [o for o in column_options if all(x[0] == "hidden" for x in o)]
            if len(visible) > 1:
                raise ValueError("同一柱位只能有一个实际透干节点")
            if len(hidden) > 3 or (
                hidden
                and not any(
                    all(any(x[2] == branch for x in o) for o in hidden)
                    and any(
                        len(set(stems)) == len(stems)
                        for stems in product(
                            *[{x[1] for x in o if x[2] == branch} for o in hidden]
                        )
                    )
                    for branch in BRANCH_HIDDEN_STEMS
                )
            ):
                raise ValueError("同一柱的已给藏干必须属于同一地支且各有实际序位")
        complete_node_ids = self.nodes is not None and all(
            n.id is not None for n in self.nodes
        )
        collections = (
            ("visible_paths", "stem"),
            ("principal_hidden_paths", "hidden"),
            ("all_hidden_paths", "hidden"),
            ("mixed_paths", "mixed"),
        )
        identities_by_collection: dict[str, set[tuple[str, str, str]]] = {}
        for name, expected_plane in collections:
            paths = getattr(self, name)
            identities_by_collection[name] = set()
            for path in paths or []:
                refs = (path.from_node, path.via_node, path.to_node)
                if path.plane is not None and path.plane != expected_plane:
                    raise ValueError("通关路径必须归入实际干藏层的集合")
                if not _possible_path(
                    refs,
                    tuple(path.elements) if path.elements is not None else None,
                    tuple(path.positions) if path.positions is not None else None,
                    expected_plane,
                    (
                        True
                        if name == "principal_hidden_paths"
                        else path.principal_hidden_only
                    ),
                    path.position_status,
                ):
                    raise ValueError("已给路径事实必须容许其干藏层集合")
                if all(ref is not None for ref in refs):
                    key = (str(refs[0]), str(refs[1]), str(refs[2]))
                    if key in identities_by_collection[name]:
                        raise ValueError("同一实体通关路径不能重复计入")
                    identities_by_collection[name].add(key)
                if complete_node_ids and any(
                    ref is not None and ref not in nodes for ref in refs
                ):
                    raise ValueError("通关路径不能引用已给节点目录之外的节点")
                actual = [nodes.get(ref) if ref is not None else None for ref in refs]
                for i, node in enumerate(actual):
                    if node is None:
                        continue
                    if (
                        path.elements is not None
                        and node.element is not None
                        and path.elements[i] != node.element
                    ):
                        raise ValueError("通关路径五行必须沿用同次实际节点")
                    if (
                        path.binding_states is not None
                        and node.binding_state is not None
                        and path.binding_states[i] != node.binding_state
                    ):
                        raise ValueError("通关路径合绊状态必须沿用同次节点")
                roots = [
                    n.remaining_root_state if n is not None else None for n in actual
                ]
                if (
                    path.all_nodes_have_remaining_roots is True
                    and any(
                        r in {"not_supplied", "no_positive_remaining_budget"}
                        for r in roots
                    )
                ) or (
                    path.all_nodes_have_remaining_roots is False
                    and "not_supplied" in roots
                ):
                    raise ValueError("已给根预算状态不能被遗漏的其他节点改为有根或无根")
                if "all_nodes_have_remaining_roots" in path.model_fields_set and all(
                    r is not None for r in roots
                ):
                    expected_roots = (
                        None
                        if "not_supplied" in roots
                        else all(r == "positive_remaining_budget" for r in roots)
                    )
                    if path.all_nodes_have_remaining_roots != expected_roots:
                        raise ValueError(
                            "通关路径根预算汇总必须沿用同次节点，不把未知改为有根或无根"
                        )
                principal_options = []
                for node in actual:
                    if node is None:
                        principal_options.append({True, False})
                        continue
                    identity = _node_identity(node.id) if node.id is not None else None
                    principal_options.append(
                        {
                            p == "hidden" and rank == 0
                            for p, _, _, rank in _physical_options(
                                node.plane or (identity[1] if identity else None),
                                node.stem or (identity[2] if identity else None),
                                node.branch,
                                node.hidden_rank,
                                node.element,
                            )
                        }
                    )
                principal = (
                    True
                    if name == "principal_hidden_paths"
                    else path.principal_hidden_only
                )
                if (
                    principal is True and any(True not in o for o in principal_options)
                ) or (
                    principal is False and all(o == {True} for o in principal_options)
                ):
                    raise ValueError("本气藏干子集必须忠于同次已给节点序位")
        if (
            self.principal_hidden_paths is not None
            and self.all_hidden_paths is not None
            and all(
                p.from_node is not None
                and p.via_node is not None
                and p.to_node is not None
                for p in self.all_hidden_paths
            )
        ):
            if (
                not identities_by_collection["principal_hidden_paths"]
                <= identities_by_collection["all_hidden_paths"]
            ):
                raise ValueError("本气藏干路径不能脱离已给全部藏干路径")
        if self.summary is not None:
            for field, collection in (
                ("visible_path_count", self.visible_paths),
                ("principal_hidden_path_count", self.principal_hidden_paths),
                ("all_hidden_path_count", self.all_hidden_paths),
                ("mixed_path_count", self.mixed_paths),
            ):
                count = getattr(self.summary, field)
                if (
                    count is not None
                    and collection is not None
                    and count != len(collection)
                ):
                    raise ValueError("通关路径汇总必须等于同次已给路径数")
        return self
