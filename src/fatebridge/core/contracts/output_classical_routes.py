"""Projection-compatible contracts for source-scoped, position-resolved routes."""

from typing import Annotated, Literal

from fatebridge.core.contracts.output_base import (
    FULL_FACT,
    OpenJsonValue,
    PartialOutput,
)
from fatebridge.core.contracts.output_month_use import MonthUseMatch, MonthUseResolution


class RouteEdge(PartialOutput):
    from_star: str | None = None
    to_star: str | None = None
    relation: Literal["生", "克", "合"] | None = None
    position_distance: int | None = None
    both_revealed: bool | None = None
    other_matching_stem_positions: list[str] | None = None
    effect_status: (
        Literal[
            "other_matching_stems_require_position_review",
            "observed_relation_not_effect_adjudication",
        ]
        | None
    ) = None


class RouteYinGrowth(PartialOutput):
    star_ref: str | None = None
    pillar: str | None = None
    branch: str | None = None


class RouteRoots(PartialOutput):
    revealed_stars: list[str] | None = None
    with_hidden_root: list[str] | None = None
    yin_growth_references: list[RouteYinGrowth] | None = None
    effective_strength: Literal["not_adjudicated"] | None = None


class ClassicalRoute(PartialOutput):
    id: str | None = None
    label: str | None = None
    allowed_month_gods: list[str] | None = None
    status: (
        Literal[
            "not_applicable_to_selected_month",
            "month_use_not_observed",
            "requires_identity_adjudication",
            "observed_route",
            "relation_not_observed",
        ]
        | None
    ) = None
    month_use_match: Annotated[MonthUseMatch | None, FULL_FACT] = None
    star_refs: list[str] | None = None
    edges: list[RouteEdge] | None = None
    helper_root_context: RouteRoots | None = None
    unresolved: list[str] | None = None
    source_ref: str | None = None
    source_pdf_pages: list[int] | None = None
    formation_status: Literal["not_adjudicated"] | None = None


class WealthSealPosition(PartialOutput):
    wealth_star: str | None = None
    seal_star: str | None = None
    intervening_positions: list[str] | None = None
    stem_combination: bool | None = None
    effect_status: str | None = None


class SharedOutputWealthRoot(PartialOutput):
    output_star: str | None = None
    wealth_star: str | None = None
    root_pillar: str | None = None
    root_branch: str | None = None
    output_hidden_stems: list[str] | None = None
    wealth_hidden_stems: list[str] | None = None
    is_month_command: bool | None = None
    effect_status: str | None = None


class ClassicalRoutes(PartialOutput):
    method_id: Literal["ziping_position_routes_v1"] | None = None
    life_stage_profile_id: str | None = None
    source: dict[str, OpenJsonValue] | None = None
    selected_month_role: dict[str, OpenJsonValue] | None = None
    month_use_resolution: Annotated[MonthUseResolution | None, FULL_FACT] = None
    routes: list[ClassicalRoute] | None = None
    wealth_seal_positions: list[WealthSealPosition] | None = None
    output_wealth_shared_roots: list[SharedOutputWealthRoot] | None = None
    metal_water_hurt_officer_context: bool | None = None
    scope: str | None = None
