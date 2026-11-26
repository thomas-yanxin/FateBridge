"""Projection-safe consistency checks for the exact engineering decision."""

from fractions import Fraction
from typing import Annotated, Literal

from pydantic import Field, model_validator

from fatebridge.core.contracts.output_base import PartialOutput

# note (schema): The threshold scale starts at weak even when timing loads first.
ThresholdStrengthLabel = Annotated[Literal["弱", "中和", "强"], Field()]


class PhysicalRootUnitComparison(PartialOutput):
    masses_exact: dict[Literal["木", "火", "土", "金", "水"], str] | None = None
    unit_threshold_exact: str | None = None
    at_least_unit: dict[Literal["木", "火", "土", "金", "水"], bool] | None = None
    float_at_least_unit: dict[Literal["木", "火", "土", "金", "水"], bool] | None = None
    visible_non_day_elements: (
        dict[Literal["year", "month", "hour"], Literal["木", "火", "土", "金", "水"]]
        | None
    ) = None
    rooted_controller_stems: int | None = Field(default=None, ge=0, le=3)
    float_rooted_controller_stems: int | None = Field(default=None, ge=0, le=3)
    rooted_wealth_visible: bool | None = None
    float_rooted_wealth_visible: bool | None = None
    comparison_basis: Literal["exact_rational_physical_hidden_budget"] | None = None
    quantity_kind: Literal["remaining_physical_hidden_stem_budget"] | None = None
    effective_classical_root_force: Literal["not_adjudicated"] | None = None

    @model_validator(mode="after")
    def coherent_unit_boundary(self) -> "PhysicalRootUnitComparison":
        if self.unit_threshold_exact is not None:
            try:
                threshold = Fraction(self.unit_threshold_exact)
            except (ValueError, ZeroDivisionError) as error:
                raise ValueError("实际藏干根预算门槛须为有限分数") from error
            if threshold != 1:
                raise ValueError("实际藏干根预算的既定单位门槛不可改变")
        for element, raw in (self.masses_exact or {}).items():
            try:
                mass = Fraction(raw)
            except (ValueError, ZeroDivisionError) as error:
                raise ValueError("实际藏干根预算须为有限分数") from error
            if mass < 0:
                raise ValueError("实际藏干根预算不可为负")
            if (
                self.at_least_unit is not None
                and element in self.at_least_unit
                and self.at_least_unit[element] != (mass >= 1)
            ):
                raise ValueError("实际藏干根标记与精确单位门槛不符")
        return self


class StrengthThresholdArithmetic(PartialOutput):
    method_id: Literal["exact_rational_strength_thresholds_v1"] | None = None
    basis: (
        Literal["declared_decimal_policy_conditioned_on_recorded_relations"] | None
    ) = None
    day_element: Literal["木", "火", "土", "金", "水"] | None = None
    energies_exact: dict[Literal["木", "火", "土", "金", "水"], str] | None = None
    physical_root_unit_comparison: PhysicalRootUnitComparison | None = None
    support_exact: str | None = None
    weaken_exact: str | None = None
    share_exact: str | None = None
    weak_threshold_exact: str | None = None
    strong_threshold_exact: str | None = None
    support_above_half: bool | None = None
    special_lower_threshold_exact: str | None = None
    special_upper_threshold_exact: str | None = None
    requires_special_structure_review: bool | None = None
    numerical_label: ThresholdStrengthLabel | None = None
    float_numerical_label: ThresholdStrengthLabel | None = None
    float_comparison_differs: bool | None = None
    calculation_effect: Literal["threshold_comparison_only"] | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def coherent_exact_decision(self) -> "StrengthThresholdArithmetic":
        root = self.physical_root_unit_comparison
        if (
            root is not None
            and self.day_element is not None
            and root.visible_non_day_elements is not None
            and set(root.visible_non_day_elements) == {"year", "month", "hour"}
        ):
            controls = {"木": "土", "火": "金", "土": "水", "金": "木", "水": "火"}
            controller = next(
                e for e, target in controls.items() if target == self.day_element
            )
            wealth = controls[self.day_element]
            for flags, count, has_wealth in (
                (
                    root.at_least_unit,
                    root.rooted_controller_stems,
                    root.rooted_wealth_visible,
                ),
                (
                    root.float_at_least_unit,
                    root.float_rooted_controller_stems,
                    root.float_rooted_wealth_visible,
                ),
            ):
                if flags is None or controller not in flags or wealth not in flags:
                    continue
                expected_count = sum(
                    e == controller and flags[e]
                    for e in root.visible_non_day_elements.values()
                )
                expected_wealth = any(
                    e == wealth and flags[e]
                    for e in root.visible_non_day_elements.values()
                )
                if count is not None and count != expected_count:
                    raise ValueError("官杀有根透干数与同次实际藏干根标记不符")
                if has_wealth is not None and has_wealth != expected_wealth:
                    raise ValueError("财有根标记与同次实际藏干根标记不符")
        values = {}
        for field in (
            "support_exact",
            "weaken_exact",
            "share_exact",
            "weak_threshold_exact",
            "strong_threshold_exact",
            "special_lower_threshold_exact",
            "special_upper_threshold_exact",
        ):
            raw = getattr(self, field)
            if raw is not None:
                try:
                    value = Fraction(raw)
                except (ValueError, ZeroDivisionError) as error:
                    raise ValueError("阈值回执须为有限分数") from error
                if value < 0 or (
                    field not in {"support_exact", "weaken_exact"} and value > 1
                ):
                    raise ValueError("阈值回执分数范围不符")
                values[field] = value
        energies: dict[str, Fraction] = {}
        for element, raw in (self.energies_exact or {}).items():
            try:
                value = Fraction(raw)
            except (ValueError, ZeroDivisionError) as error:
                raise ValueError("分量回执须为有限分数") from error
            if value < 0:
                raise ValueError("分量回执不可为负")
            energies[element] = value
        if len(energies) == 5 and self.day_element is not None:
            cycle = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
            seal = next(e for e, child in cycle.items() if child == self.day_element)
            support = energies[self.day_element] + energies[seal]
            weaken = sum(
                energies[e] for e in energies if e not in {self.day_element, seal}
            )
            for field, expected in (
                ("support_exact", support),
                ("weaken_exact", weaken),
            ):
                if field in values and values[field] != expected:
                    raise ValueError("身印减身总量与精确五行分量不符")
        if all(k in values for k in ("support_exact", "weaken_exact", "share_exact")):
            support, weaken = values["support_exact"], values["weaken_exact"]
            expected = (
                support / (support + weaken) if support + weaken else Fraction(1, 2)
            )
            if values["share_exact"] != expected:
                raise ValueError("精确份额与身印、减身总量不符")
        if "share_exact" in values:
            share = values["share_exact"]
            lower, upper = (
                values.get("special_lower_threshold_exact"),
                values.get("special_upper_threshold_exact"),
            )
            if lower is not None and upper is not None:
                if (lower, upper) != (Fraction(3, 20), Fraction(17, 20)):
                    raise ValueError("特殊结构复核的既定严格边界不符")
                if (
                    self.requires_special_structure_review is not None
                    and self.requires_special_structure_review
                    != (share < lower or share > upper)
                ):
                    raise ValueError("特殊结构复核标记与精确份额不符")
            if self.support_above_half is not None and self.support_above_half != (
                share > Fraction(1, 2)
            ):
                raise ValueError("二分之一比较与精确份额不符")
            if all(
                k in values for k in ("weak_threshold_exact", "strong_threshold_exact")
            ):
                weak, strong = (
                    values["weak_threshold_exact"],
                    values["strong_threshold_exact"],
                )
                if weak > strong:
                    raise ValueError("弱强阈值顺序不符")
                label = "强" if share > strong else "弱" if share < weak else "中和"
                if self.numerical_label is not None and self.numerical_label != label:
                    raise ValueError("数值档与精确阈值不符")
        if (
            self.numerical_label is not None
            and self.float_numerical_label is not None
            and self.float_comparison_differs is not None
            and self.float_comparison_differs
            != (self.numerical_label != self.float_numerical_label)
        ):
            raise ValueError("浮点判档差异标记不符")
        return self
