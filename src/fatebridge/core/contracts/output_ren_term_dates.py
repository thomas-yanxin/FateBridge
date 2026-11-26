"""Same-dependency anchors for published-day reference comparisons."""

from typing import Any, Literal

from pydantic import BaseModel, JsonValue, StrictBool, StrictInt, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_liuren_branches import compare_present_branches
from fatebridge.core.metaphysics.hko_term_dates import published_date_reference
from fatebridge.utils.civil_time import ZonedCalendar


class RenPublishedDateReference(PartialOutput):
    reference_id: Literal["hko_published_term_dates_v1"] | None = None
    term_name: str | None = None
    hko_year: StrictInt | None = None
    comparison_clock: Literal["fixed_UTC+08:00"] | None = None
    computed_hko_moment: str | None = None
    computed_hko_date: str | None = None
    published_date: str | None = None
    dates_equal: StrictBool | None = None
    status: Literal["date_match", "date_mismatch", "outside_published_range"] | None = (
        None
    )
    source_url: str | None = None
    comparison_scope: Literal["published_day_only_not_crossing_instant"] | None = None
    instant_accuracy_certified: Literal[False] | None = None

    @model_validator(mode="before")
    @classmethod
    def strict_false(cls, value: JsonValue | BaseModel) -> JsonValue | BaseModel:
        if (
            isinstance(value, dict)
            and value.get("instant_accuracy_certified") is not None
            and value["instant_accuracy_certified"] is not False
        ):
            raise ValueError("官方逐日表不认证交气瞬间精度")
        return value

    @model_validator(mode="after")
    def matches_own_context(self) -> "RenPublishedDateReference":

        if self.term_name is not None and self.computed_hko_moment is not None:
            compare_present_branches(
                self.model_dump(exclude_unset=True),
                published_date_reference(
                    self.term_name,
                    ZonedCalendar.from_isoformat(self.computed_hko_moment),
                ),
            )
        return self


def align_published_date(dependency: Any) -> None:

    get = lambda o, k: o.get(k) if isinstance(o, dict) else getattr(o, k, None)
    ref = get(dependency, "published_date_reference")
    name = get(dependency, "name")
    moment = get(dependency, "civil_moment")
    if ref is not None and name is not None and moment is not None:
        value = (
            ref.model_dump(exclude_unset=True)
            if isinstance(ref, RenPublishedDateReference)
            else ref
        )
        compare_present_branches(
            value, published_date_reference(name, ZonedCalendar.from_isoformat(moment))
        )


def require_complete_published_dates(policy: Any) -> None:

    if not isinstance(policy, dict) or policy.get("mode") != "civil_instant_checked":
        raise ValueError("完整壬课输出缺少交气日期依据")
    rows = policy.get("solar_term_dependencies")
    if rows is None:
        return
    if (
        not isinstance(rows, list)
        or not all(isinstance(r, dict) for r in rows)
        or [r.get("role") for r in rows]
        != [
            "current_term",
            "next_term",
            "month_start",
            "next_month_start",
            "year_boundary",
        ]
    ):
        raise ValueError("完整壬课输出缺少五项实际交气依赖")
    for row in rows:
        if not isinstance(row.get("name"), str) or not isinstance(
            row.get("civil_moment"), str
        ):
            raise ValueError("完整交气日期对照缺少同次节气与瞬间")
        expected = published_date_reference(
            row["name"], ZonedCalendar.from_isoformat(row["civil_moment"])
        )
        if isinstance(row.get("published_date_reference"), dict):
            RenPublishedDateReference.model_validate(row["published_date_reference"])
        if row.get("published_date_reference") != expected:
            raise ValueError("完整交气官方日期对照缺项或与本次计算不符")
