"""Projectable contracts for the limited, conditional root-budget projection."""

from fractions import Fraction
from typing import Literal, Optional

from pydantic import JsonValue, model_validator

from fatebridge.core.output_base import PartialOutput


class TimingStrengthBaseline(PartialOutput):
    method_id: Optional[str] = None
    strength_level: Optional[str] = None
    numerical_label: Optional[Literal["强", "中和", "弱"]] = None
    support_share_exact: Optional[str] = None
    energies_exact: Optional[dict[str, str]] = None
    parameters: Optional[dict[str, float]] = None
    seasonal_phases: Optional[dict[str, str]] = None
    seasonal_factors: Optional[dict[str, float]] = None
    relations: Optional[list[dict[str, JsonValue]]] = None


class ProjectedTimingHiddenRoot(PartialOutput):
    pillar: Optional[Literal["year", "month", "day", "hour"]] = None
    stem: Optional[str] = None
    element: Optional[Literal["木", "火", "土", "金", "水"]] = None
    remaining_mass_exact: Optional[str] = None


class TimingRootEffectLayer(PartialOutput):
    node_id: Optional[str] = None
    status: Optional[Literal["projected", "blocked"]] = None
    blocker_relation_ids: Optional[list[str]] = None
    effect_relation_ids: Optional[list[str]] = None
    quantity_kind: Optional[Literal["residual_natal_budget_only"]] = None
    comparison_powers_exact: Optional[dict[str, str]] = None
    retention_factors_exact: Optional[dict[str, dict[str, str]]] = None
    stem_retention_factors_exact: Optional[
        dict[Literal["year", "month", "hour"], str]
    ] = None
    hidden_roots: Optional[list[ProjectedTimingHiddenRoot]] = None
    energies_exact: Optional[dict[str, str]] = None
    support_share_exact: Optional[str] = None
    residual_natal_numerical_label: Optional[Literal["强", "中和", "弱"]] = None

    @model_validator(mode="after")
    def unresolved_cannot_publish_projection(self) -> "TimingRootEffectLayer":
        if self.status == "blocked" and (
            self.hidden_roots
            or self.energies_exact
            or self.comparison_powers_exact
            or self.retention_factors_exact
            or self.stem_retention_factors_exact
            or self.support_share_exact is not None
            or self.residual_natal_numerical_label is not None
        ):
            raise ValueError("未解会合不能发布岁运根量投影或数值档")
        if self.status == "projected" and self.blocker_relation_ids:
            raise ValueError("岁运根量存在阻塞关系时不能声明投影已完成")
        quantities = (
            [
                r.remaining_mass_exact
                for r in self.hidden_roots or []
                if r.remaining_mass_exact is not None
            ]
            + list((self.energies_exact or {}).values())
            + list((self.comparison_powers_exact or {}).values())
        )
        bounded = [
            value
            for elements in (self.retention_factors_exact or {}).values()
            for value in elements.values()
        ]
        bounded.extend((self.stem_retention_factors_exact or {}).values())
        if self.support_share_exact is not None:
            bounded.append(self.support_share_exact)
        for raw in quantities + bounded:
            try:
                value = Fraction(raw)
            except (ValueError, ZeroDivisionError) as error:
                raise ValueError("岁运根预算须为有限分数") from error
            if value < 0:
                raise ValueError("岁运根预算不可为负")
        if any(Fraction(raw) > 1 for raw in bounded):
            raise ValueError("根保留系数及扶身份额不可超过1")
        return self


class TimingStrengthProjection(PartialOutput):
    method_id: Optional[
        Literal[
            "single_layer_natal_root_retention_projection_v1",
            "single_layer_natal_budget_retention_projection_v2",
        ]
    ] = None
    baseline_method_id: Optional[str] = None
    baseline: Optional[TimingStrengthBaseline] = None
    month_command_node_id: Optional[Literal["natal.month"]] = None
    combination_resolution: Optional[Literal["not_implemented"]] = None
    full_timing_strength_status: Optional[Literal["not_adjudicated"]] = None
    layers: Optional[list[TimingRootEffectLayer]] = None
    scope: Optional[str] = None
    stem_binding_source: Optional[dict[str, str]] = None

    @model_validator(mode="after")
    def numerical_label_uses_same_baseline_thresholds(
        self,
    ) -> "TimingStrengthProjection":
        if self.baseline is None:
            return self
        if (
            self.baseline_method_id is not None
            and self.baseline.method_id is not None
            and self.baseline_method_id != self.baseline.method_id
        ):
            raise ValueError("岁运投影必须绑定同次旺衰基准版本")
        parameters = self.baseline.parameters or {}
        if "weak_share" in parameters and "strong_share" in parameters:
            for row in self.layers or []:
                if (
                    row.support_share_exact is None
                    or row.residual_natal_numerical_label is None
                ):
                    continue
                share = Fraction(row.support_share_exact)
                expected = (
                    "强"
                    if share > Fraction(str(parameters["strong_share"]))
                    else (
                        "弱"
                        if share < Fraction(str(parameters["weak_share"]))
                        else "中和"
                    )
                )
                if row.residual_natal_numerical_label != expected:
                    raise ValueError("残存原局数值档必须遵守同次原门槛")
        return self
