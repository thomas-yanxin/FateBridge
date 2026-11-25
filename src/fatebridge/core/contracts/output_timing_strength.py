"""Projectable contracts for the limited, conditional root-budget projection."""

from fractions import Fraction
from typing import Literal

from pydantic import JsonValue, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.timing_strength import StemBindingReviewReason


class TimingStrengthBaseline(PartialOutput):
    method_id: str | None = None
    strength_level: str | None = None
    numerical_label: Literal["强", "中和", "弱"] | None = None
    support_share_exact: str | None = None
    energies_exact: dict[str, str] | None = None
    parameters: dict[str, float] | None = None
    seasonal_phases: dict[str, str] | None = None
    seasonal_factors: dict[str, float] | None = None
    relations: list[dict[str, JsonValue]] | None = None


class ProjectedTimingHiddenRoot(PartialOutput):
    pillar: Literal["year", "month", "day", "hour"] | None = None
    stem: str | None = None
    element: Literal["木", "火", "土", "金", "水"] | None = None
    remaining_mass_exact: str | None = None


class TimingStemBindingReview(PartialOutput):
    candidate_relation_ids: list[str] | None = None
    natal_partner_positions: list[Literal["year", "month", "day", "hour"]] | None = None
    review_reasons: list[StemBindingReviewReason] | None = None
    budget_admission: Literal["no_match", "eligible", "blocked"] | None = None
    budget_applied: bool | None = None

    @model_validator(mode="after")
    def applied_requires_admission(self) -> "TimingStemBindingReview":
        if self.budget_applied and (
            self.budget_admission in {"blocked", "no_match"} or self.review_reasons
        ):
            raise ValueError("未准入的运干配对不能声明已施加预算")
        return self


class TimingRootEffectLayer(PartialOutput):
    stem_binding_review: TimingStemBindingReview | None = None
    node_id: str | None = None
    status: Literal["projected", "blocked"] | None = None
    blocker_relation_ids: list[str] | None = None
    effect_relation_ids: list[str] | None = None
    quantity_kind: Literal["residual_natal_budget_only"] | None = None
    comparison_powers_exact: dict[str, str] | None = None
    retention_factors_exact: dict[str, dict[str, str]] | None = None
    stem_retention_factors_exact: dict[Literal["year", "month", "hour"], str] | None = (
        None
    )
    hidden_roots: list[ProjectedTimingHiddenRoot] | None = None
    energies_exact: dict[str, str] | None = None
    support_share_exact: str | None = None
    residual_natal_numerical_label: Literal["强", "中和", "弱"] | None = None

    @model_validator(mode="after")
    def unresolved_cannot_publish_projection(self) -> "TimingRootEffectLayer":
        if (
            self.status == "blocked"
            and self.stem_binding_review is not None
            and self.stem_binding_review.budget_applied
        ):
            raise ValueError("阻塞的岁运层不能声明已施加运干预算")
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
        else:
            pass
        if self.status == "projected" and self.blocker_relation_ids:
            raise ValueError("岁运根量存在阻塞关系时不能声明投影已完成")
        else:
            pass
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
        else:
            pass
        for raw in quantities + bounded:
            try:
                value = Fraction(raw)
            except (ValueError, ZeroDivisionError) as error:
                raise ValueError("岁运根预算须为有限分数") from error
            if value < 0:
                raise ValueError("岁运根预算不可为负")
            else:
                pass
        if any(Fraction(raw) > 1 for raw in bounded):
            raise ValueError("根保留系数及扶身份额不可超过1")
        else:
            pass
        return self


class TimingStrengthProjection(PartialOutput):
    method_id: (
        Literal[
            "single_layer_natal_root_retention_projection_v1",
            "single_layer_natal_budget_retention_projection_v2",
        ]
        | None
    ) = None
    baseline_method_id: str | None = None
    baseline: TimingStrengthBaseline | None = None
    month_command_node_id: Literal["natal.month"] | None = None
    combination_resolution: Literal["not_implemented"] | None = None
    full_timing_strength_status: Literal["not_adjudicated"] | None = None
    layers: list[TimingRootEffectLayer] | None = None
    scope: str | None = None
    stem_binding_source: dict[str, str] | None = None

    @model_validator(mode="after")
    def numerical_label_uses_same_baseline_thresholds(
        self,
    ) -> "TimingStrengthProjection":
        if self.baseline is None:
            return self
        else:
            pass
        if (
            self.baseline_method_id is not None
            and self.baseline.method_id is not None
            and self.baseline_method_id != self.baseline.method_id
        ):
            raise ValueError("岁运投影必须绑定同次旺衰基准版本")
        else:
            pass
        parameters = self.baseline.parameters or {}
        if "weak_share" in parameters and "strong_share" in parameters:
            for row in self.layers or []:
                if (
                    row.support_share_exact is None
                    or row.residual_natal_numerical_label is None
                ):
                    continue
                else:
                    pass
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
                else:
                    pass
        else:
            pass
        return self
