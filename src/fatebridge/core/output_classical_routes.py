"""Projection-compatible contracts for source-scoped, position-resolved routes."""

from typing import Any, Dict, List, Literal, Optional

from fatebridge.core.output_base import PartialOutput


class RouteEdge(PartialOutput):
    from_star: Optional[str] = None
    to_star: Optional[str] = None
    relation: Optional[Literal["生", "克", "合"]] = None
    position_distance: Optional[int] = None
    both_revealed: Optional[bool] = None
    other_matching_stem_positions: Optional[List[str]] = None
    effect_status: Optional[
        Literal[
            "other_matching_stems_require_position_review",
            "observed_relation_not_effect_adjudication",
        ]
    ] = None


class RouteYinGrowth(PartialOutput):
    star_ref: Optional[str] = None
    pillar: Optional[str] = None
    branch: Optional[str] = None


class RouteRoots(PartialOutput):
    revealed_stars: Optional[List[str]] = None
    with_hidden_root: Optional[List[str]] = None
    yin_growth_references: Optional[List[RouteYinGrowth]] = None
    effective_strength: Optional[Literal["not_adjudicated"]] = None


class ClassicalRoute(PartialOutput):
    id: Optional[str] = None
    label: Optional[str] = None
    allowed_month_gods: Optional[List[str]] = None
    status: Optional[
        Literal[
            "not_applicable_to_selected_month",
            "observed_route",
            "relation_not_observed",
        ]
    ] = None
    star_refs: Optional[List[str]] = None
    edges: Optional[List[RouteEdge]] = None
    helper_root_context: Optional[RouteRoots] = None
    unresolved: Optional[List[str]] = None
    source_ref: Optional[str] = None
    source_pdf_pages: Optional[List[int]] = None
    formation_status: Optional[Literal["not_adjudicated"]] = None


class WealthSealPosition(PartialOutput):
    wealth_star: Optional[str] = None
    seal_star: Optional[str] = None
    intervening_positions: Optional[List[str]] = None
    stem_combination: Optional[bool] = None
    effect_status: Optional[str] = None


class SharedOutputWealthRoot(PartialOutput):
    output_star: Optional[str] = None
    wealth_star: Optional[str] = None
    root_pillar: Optional[str] = None
    root_branch: Optional[str] = None
    output_hidden_stems: Optional[List[str]] = None
    wealth_hidden_stems: Optional[List[str]] = None
    is_month_command: Optional[bool] = None
    effect_status: Optional[str] = None


class ClassicalRoutes(PartialOutput):
    method_id: Optional[Literal["ziping_position_routes_v1"]] = None
    life_stage_profile_id: Optional[str] = None
    source: Optional[Dict[str, Any]] = None
    selected_month_role: Optional[Dict[str, Any]] = None
    routes: Optional[List[ClassicalRoute]] = None
    wealth_seal_positions: Optional[List[WealthSealPosition]] = None
    output_wealth_shared_roots: Optional[List[SharedOutputWealthRoot]] = None
    metal_water_hurt_officer_context: Optional[bool] = None
    scope: Optional[str] = None
