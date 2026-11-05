"""Conservative error accounting: unknown bounds never become zero."""

from fractions import Fraction
from math import inf, isfinite, nextafter
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, JsonValue, model_validator

ErrorStatus = Literal["bounded", "declared", "unquantified", "not_applicable"]
ErrorUnit = Literal["seconds", "degrees", "categorical", "unresolved"]


class ErrorComponent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    component_id: str
    source: str
    unit: ErrorUnit
    status: ErrorStatus
    interval: tuple[float, float] | None = None
    correlation_group: str
    evidence_paths: tuple[str, ...] = ()
    scope: str

    @model_validator(mode="after")
    def valid_bound(self) -> "ErrorComponent":
        if self.status in {"bounded", "declared"}:
            if self.interval is None or self.unit in {"categorical", "unresolved"}:
                raise ValueError("数值界必须有量纲及区间")
            left, right = self.interval
            if not isfinite(left) or not isfinite(right) or left > right:
                raise ValueError("误差区间必须有序且有限")
        elif self.interval is not None:
            raise ValueError("未知/不适用误差不能填写数值界")
        return self


class CombinedBound(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    unit: ErrorUnit
    status: Literal[
        "bounded", "conditional_on_declared_inputs", "unquantified", "not_applicable"
    ]
    interval: tuple[float, float] | None
    unresolved_components: tuple[str, ...]
    combination: Literal["conservative_interval_sum_no_independence_assumption"] = (
        "conservative_interval_sum_no_independence_assumption"
    )

    @model_validator(mode="after")
    def consistent_combined_bound(self) -> "CombinedBound":
        known = self.status in {"bounded", "conditional_on_declared_inputs"}
        if known:
            if (
                self.interval is None
                or self.unit in {"categorical", "unresolved"}
                or self.unresolved_components
            ):
                raise ValueError("已知合成界不能缺少区间、量纲或包含未决分量")
            left, right = self.interval
            if not isfinite(left) or not isfinite(right) or left > right:
                raise ValueError("合成区间须有序且有限")
        elif self.interval is not None:
            raise ValueError("未量化或不适用不能填写数值界")
        return self


def circular_sector_candidates(
    nominal_degrees: float, bound: CombinedBound, sectors: int
) -> tuple[int, ...] | None:
    """Complete closed-interval image for an equal angular partition only."""
    if not isfinite(nominal_degrees) or sectors < 1:
        raise ValueError("名义角度须有限，等分数量须为正")
    if bound.unit != "degrees":
        raise ValueError("角度离散化不能接受时间或未知量纲")
    if bound.interval is None:
        return None
    low, high = (Fraction(nominal_degrees) + Fraction(v) for v in bound.interval)
    if high - low >= 360:
        return tuple(range(sectors))
    first, last = (value * sectors // 360 for value in (low, high))
    return tuple(sorted({index % sectors for index in range(first, last + 1)}))


def combine_bounds(
    components: tuple[ErrorComponent, ...], unit: ErrorUnit
) -> CombinedBound:
    if len({c.component_id for c in components}) != len(components):
        raise ValueError("同一误差源不可重复计入；相关项须保留共同来源")
    selected = [
        c for c in components if c.unit == unit and c.status != "not_applicable"
    ]
    unresolved = tuple(c.component_id for c in selected if c.interval is None)
    if not selected:
        return CombinedBound(
            unit=unit, status="not_applicable", interval=None, unresolved_components=()
        )
    if unresolved or unit in {"categorical", "unresolved"}:
        return CombinedBound(
            unit=unit,
            status="unquantified",
            interval=None,
            unresolved_components=unresolved or tuple(c.component_id for c in selected),
        )
    # A worst-case sum remains valid with correlated errors; RSS would not.
    intervals = [c.interval for c in selected if c.interval is not None]
    exact_left = sum((Fraction(i[0]) for i in intervals), Fraction(0))
    exact_right = sum((Fraction(i[1]) for i in intervals), Fraction(0))
    left, right = float(exact_left), float(exact_right)
    if Fraction(left) > exact_left:
        left = nextafter(left, -inf)
    if Fraction(right) < exact_right:
        right = nextafter(right, inf)
    return CombinedBound(
        unit=unit,
        status=(
            "conditional_on_declared_inputs"
            if any(c.status == "declared" for c in selected)
            else "bounded"
        ),
        interval=(left, right),
        unresolved_components=(),
    )


SOURCE_UNITS: dict[str, ErrorUnit] = {
    "civil_clock": "seconds",
    "solar_clock": "seconds",
    "calendar_model": "categorical",
    "observer_location": "degrees",
    "earth_rotation": "seconds",
    "ephemeris_model": "degrees",
    "numerical_solver": "unresolved",
    "display_quantization": "unresolved",
    "north_reference": "degrees",
    "rule_adjudication": "categorical",
}


def declared_error_budget(
    sources: tuple[str, ...], inputs: Mapping[str, object], origin: str
) -> dict[str, JsonValue]:
    components = []
    paths = tuple(
        k
        for k, v in inputs.items()
        if k.endswith("birth_time_uncertainty_minutes") and v is not None
    )
    bounds = [
        Fraction(v) * 60
        for k, v in inputs.items()
        if k in paths
        and isinstance(v, (int, float))
        and not isinstance(v, bool)
        and v > 0
    ]
    radius = float(max(bounds)) if bounds else None
    if radius is not None and Fraction(radius) < max(bounds):
        radius = nextafter(radius, inf)
    for source in sorted(set(sources)):
        unit = SOURCE_UNITS[source]
        interval = (
            (-radius, radius)
            if source == "civil_clock" and radius is not None
            else None
        )
        components.append(
            ErrorComponent(
                component_id=f"{origin}:{source}",
                source=source,
                unit=unit,
                status="declared" if interval is not None else "unquantified",
                interval=interval,
                correlation_group=f"{origin}:{source}",
                evidence_paths=paths if interval is not None else (),
                scope=(
                    "调用方声明的UTC经过时间范围，不认证出生记录、历史钟制或连续稳定"
                    if interval is not None
                    else "未取得此运行及坐标/规则域的可传递误差界；不把出版容差、求根残差或显示位数当物理精度"
                ),
            )
        )
    entries = tuple(components)
    return {
        "method_id": "component_error_budget_v1",
        "scope": "source_components; not a calibrated output confidence interval",
        "source_component_coverage": "declared_subset",
        "source_coverage_complete": False,
        "components": [c.model_dump(mode="json") for c in entries],
        "source_bounds_by_unit": [
            combine_bounds(entries, u).model_dump(mode="json")
            for u in ("seconds", "degrees", "categorical", "unresolved")
        ],
        "output_error_bounds": None,
        "output_propagation_status": "unquantified" if entries else "not_applicable",
        "propagation_requirement": "输出界须另有该输出对各分量的有界映射/Jacobian或完整区间求解；不可将秒与角度或离散规则相加",
        "probability_interpretation": False,
    }
