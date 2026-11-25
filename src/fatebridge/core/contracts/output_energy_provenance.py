"""Partial-safe arithmetic and same-run bindings for energy-source receipts."""

from math import isfinite
from typing import Any, Literal

from pydantic import Field, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.energy_provenance import PARTS, ROLES, ledger_parts, role_elements


def close(left: float, right: float) -> bool:
    return abs(left - right) <= 1e-12


class EnergyPart(PartialOutput):
    status: Literal["complete", "partial", "not_supplied"] | None = None
    energy_unrounded: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    refs: list[str] | None = None

    @model_validator(mode="after")
    def preserve_unknown(self) -> "EnergyPart":
        if (
            self.status in {"partial", "not_supplied"}
            and self.energy_unrounded is not None
        ):
            raise ValueError("不完整账本不能宣称已知完整分项能量")
        if self.refs is not None and len(self.refs) != len(set(self.refs)):
            raise ValueError("同一账本条目不能重复归因")
        return self


class EnergyFront(PartialOutput):
    element: Literal["木", "火", "土", "金", "水"] | None = None
    physical_hidden: EnergyPart | None = None
    synthetic_branch: EnergyPart | None = None
    non_day_visible: EnergyPart | None = None
    total_energy_unrounded: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    attributed_energy_unrounded: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    residual: float | None = Field(default=None, allow_inf_nan=False)
    status: Literal["complete", "partial", "not_closed"] | None = None

    @model_validator(mode="after")
    def preserve_sum_and_closure(self) -> "EnergyFront":
        parts = [getattr(self, k) for k in PARTS]
        if self.status == "complete" and any(
            p is not None and p.status in {"partial", "not_supplied"} for p in parts
        ):
            raise ValueError("完整归因不能含未给或不完整分项")
        values = [p.energy_unrounded if p is not None else None for p in parts]
        attributed = (
            sum(v for v in values if v is not None)
            if all(v is not None for v in values)
            else None
        )
        if (
            attributed is not None
            and self.attributed_energy_unrounded is not None
            and not close(attributed, self.attributed_energy_unrounded)
        ):
            raise ValueError("归因总量必须等于三个未舍入分项之和")
        if attributed is None:
            attributed = self.attributed_energy_unrounded
        if attributed is not None and self.total_energy_unrounded is not None:
            residual = self.total_energy_unrounded - attributed
            if self.residual is not None and not close(residual, self.residual):
                raise ValueError("归因残差不能掩盖分项与总量差额")
            if self.status == "complete" and not close(residual, 0.0):
                raise ValueError("完整能量归因须在原定精度内闭合")
        if (
            self.status == "complete"
            and self.residual is not None
            and not close(self.residual, 0.0)
        ):
            raise ValueError("非零残差不能宣称完整归因")
        return self


class EnergyFronts(PartialOutput):
    body: EnergyFront | None = None
    seal: EnergyFront | None = None
    output: EnergyFront | None = None
    wealth: EnergyFront | None = None
    officer_killer: EnergyFront | None = None


class SyntheticContribution(PartialOutput):
    pillar: Literal["year", "month", "day", "hour"] | None = None
    element: Literal["木", "火", "土", "金", "水"] | None = None
    origin: str | None = None
    mass: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    energy: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    energy_unrounded: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def preserve_display(self) -> "SyntheticContribution":
        if (
            self.energy is not None
            and self.energy_unrounded is not None
            and self.energy != round(self.energy_unrounded, 6)
        ):
            raise ValueError("合成贡献展示值须忠于同次未舍入值")
        return self


class EnergyProvenance(PartialOutput):
    method_id: Literal["same_assessment_energy_sources_v1"] | None = None
    strength_method_id: str | None = None
    day_element: Literal["木", "火", "土", "金", "水"] | None = None
    quantity_kind: Literal["uncalibrated_engineering_energy"] | None = None
    status: Literal["complete", "partial"] | None = None
    fronts: EnergyFronts | None = None
    synthetic_contributions: list[SyntheticContribution] | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def preserve_roles_and_synthetic_receipt(self) -> "EnergyProvenance":
        for role in ROLES:
            front = getattr(self.fronts, role) if self.fronts is not None else None
            if front is None:
                continue
            if (
                self.day_element is not None
                and front.element is not None
                and role_elements(self.day_element)[role] != front.element
            ):
                raise ValueError("五行归因角色须忠于日主五行")
            if self.status == "complete" and front.status in {"partial", "not_closed"}:
                raise ValueError("整体完整归因不能隐藏未闭合分量")
            bind_part(
                front,
                "synthetic_branch",
                (
                    [
                        r.model_dump(exclude_unset=True)
                        for r in self.synthetic_contributions
                    ]
                    if self.synthetic_contributions is not None
                    else None
                ),
            )
        return self


def bind_part(front: EnergyFront, kind: str, rows: Any) -> None:
    """Check only co-known facts; missing siblings remain missing under projection."""
    part = getattr(front, kind)
    if part is None or front.element is None or not isinstance(rows, list):
        return
    expected = ledger_parts(rows, kind)[front.element]
    if expected["status"] != "complete":
        return
    if part.status is not None and part.status != "complete":
        raise ValueError("归因账本状态须忠于同次完整账本")
    if part.energy_unrounded is not None and not close(
        part.energy_unrounded, expected["energy_unrounded"]
    ):
        raise ValueError("分项归因必须忠于同次未舍入账本")
    if part.refs is not None and part.refs != expected["refs"]:
        raise ValueError("分项引用不能漏记、重复或混入其他能量来源")


def bind_assessment(
    provenance: EnergyProvenance,
    assessment: dict[str, Any],
    method: str | None = None,
) -> None:
    methods = [
        m
        for m in (method, assessment.get("method_id"), provenance.strength_method_id)
        if m is not None
    ]
    if methods and any(m != methods[0] for m in methods):
        raise ValueError("能量归因不能混用不同旺衰计算方法")
    raw = assessment.get("combination_contributions")
    if isinstance(raw, list) and provenance.synthetic_contributions is not None:
        copied = [
            r.model_dump(exclude_unset=True) for r in provenance.synthetic_contributions
        ]
        if len(raw) != len(copied):
            raise ValueError("合成账本不能漏记同次条目")
        for original, copy in zip(raw, copied):
            if isinstance(original, dict) and any(
                k in original and original[k] != v for k, v in copy.items()
            ):
                raise ValueError("合成账本须忠于同次原始条目")
    stem = assessment.get("stem_energy_accounting")
    stem = stem if isinstance(stem, dict) else {}
    totals = assessment.get("effective_elements_unrounded")
    totals = totals if isinstance(totals, dict) else {}
    day = (assessment.get("threshold_arithmetic") or {}).get("day_element")
    if (
        day is not None
        and provenance.day_element is not None
        and day != provenance.day_element
    ):
        raise ValueError("能量归因日主五行不能混用另一回执")
    for role in ROLES:
        front = (
            getattr(provenance.fronts, role) if provenance.fronts is not None else None
        )
        if front is None:
            continue
        for kind, rows in zip(
            PARTS, (assessment.get("hidden_stem_ledger"), raw, stem.get("ledger"))
        ):
            bind_part(front, kind, rows)
        total = totals.get(front.element)
        if (
            (type(total) is int or type(total) is float)
            and isfinite(total)
            and front.total_energy_unrounded is not None
            and not close(total, front.total_energy_unrounded)
        ):
            raise ValueError("归因总量必须忠于同次未舍入五行总量")
