"""Same-dependency anchors for published-day reference comparisons."""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import StrictBool, StrictInt, model_validator

from .output_base import PartialOutput
from .output_liuren_branches import compare_present_branches


class RenPublishedDateReference(PartialOutput):
    reference_id: Optional[Literal["hko_published_term_dates_v1"]] = None
    catalogue_sha256: Optional[str] = None
    term_name: Optional[str] = None
    hko_year: Optional[StrictInt] = None
    comparison_clock: Optional[Literal["fixed_UTC+08:00"]] = None
    computed_hko_moment: Optional[str] = None
    computed_hko_date: Optional[str] = None
    published_date: Optional[str] = None
    dates_equal: Optional[StrictBool] = None
    status: Optional[
        Literal["date_match", "date_mismatch", "outside_published_range"]
    ] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    comparison_scope: Optional[Literal["published_day_only_not_crossing_instant"]] = (
        None
    )
    instant_accuracy_certified: Optional[Literal[False]] = None

    @model_validator(mode="before")
    @classmethod
    def strict_false(cls, value: Any) -> Any:
        if (
            isinstance(value, dict)
            and value.get("instant_accuracy_certified") is not None
            and value["instant_accuracy_certified"] is not False
        ):
            raise ValueError("官方逐日表不认证交气瞬间精度")
        return value

    @model_validator(mode="after")
    def matches_own_context(self) -> "RenPublishedDateReference":
        from .metaphysics.hko_term_dates import published_date_reference

        if self.term_name is not None and self.computed_hko_moment is not None:
            compare_present_branches(
                self.model_dump(exclude_unset=True),
                published_date_reference(
                    self.term_name, datetime.fromisoformat(self.computed_hko_moment)
                ),
            )
        return self


def align_published_date(dependency: Any) -> None:
    from .metaphysics.hko_term_dates import published_date_reference

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
            value, published_date_reference(name, datetime.fromisoformat(moment))
        )


def require_complete_published_dates(policy: Any) -> None:
    from .metaphysics.hko_term_dates import published_date_reference

    if not isinstance(policy, dict):
        raise ValueError("完整壬课输出缺少交气日期依据")
    rows = policy.get("solar_term_dependencies")
    if (
        policy.get("mode") != "civil_instant_checked"
        or not isinstance(rows, list)
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
            row["name"], datetime.fromisoformat(row["civil_moment"])
        )
        if isinstance(row.get("published_date_reference"), dict):
            RenPublishedDateReference.model_validate(row["published_date_reference"])
        if row.get("published_date_reference") != expected:
            raise ValueError("完整交气官方日期对照缺项或与本次计算不符")
