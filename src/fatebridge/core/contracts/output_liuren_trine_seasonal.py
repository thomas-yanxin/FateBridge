"""Keep nominal trine seasonal facts distinct from transformed or raw branches."""

from typing import Any, Literal

from pydantic import BaseModel, JsonValue, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.metaphysics.liureng_seasonal import MONTH_PARTITION, POWERS
from fatebridge.core.metaphysics.liureng_trine_seasonal import (
    COMPONENTS,
    nominal_seasonal_evidence,
    nominal_seasonal_metadata,
)


class LiurenNominalTrineSeasonal(PartialOutput):
    method_id: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    original_pdf_pages: list[int] | None = None
    corroborating_source_url: str | None = None
    corroborating_source_sha256: str | None = None
    corroborating_pdf_pages: list[int] | None = None
    month_partition_profile: str | None = None
    month_branch: (
        Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
        | None
    ) = None
    season_partition: Literal["春", "夏", "秋", "冬", "季月"] | None = None
    nominal_element: Literal["木", "火", "金", "水"] | None = None
    nominal_power: Literal["旺", "相", "休", "囚", "死"] | None = None
    course_component: Literal["得势", "失时", "将来", "既往"] | None = None
    full_named_course_adjudicated: Literal[False] | None = None
    transformation_confirmed: None = None
    scope: str | None = None

    @model_validator(mode="before")
    @classmethod
    def no_certificate_coercion(
        cls, value: JsonValue | BaseModel
    ) -> JsonValue | BaseModel:
        if isinstance(value, dict) and "full_named_course_adjudicated" in value:
            if value["full_named_course_adjudicated"] is not False:
                raise ValueError("名义季态组件不认证完整课体")
        return value

    @model_validator(mode="after")
    def keep_selected_nominal_facts(self) -> "LiurenNominalTrineSeasonal":

        present = self.model_dump(exclude_unset=True)
        for key, expected in nominal_seasonal_metadata().items():
            if key in present and present[key] != expected:
                raise ValueError("名义局体季态的来源或适用范围不符")
        season = (
            MONTH_PARTITION[self.month_branch]
            if self.month_branch
            else self.season_partition
        )
        if self.season_partition is not None and season != self.season_partition:
            raise ValueError("名义局体季态与所选月建季节不符")
        if season is not None and self.nominal_element is not None:
            expected_power = POWERS[season][self.nominal_element]
            if self.nominal_power is not None and self.nominal_power != expected_power:
                raise ValueError("名义局体五态与该局体五行和季节不符")
            if (
                self.course_component is not None
                and self.course_component != COMPONENTS[expected_power]
            ):
                raise ValueError("名义局体课体组件与所选五态不符")
        if (
            self.nominal_power is not None
            and self.course_component is not None
            and self.course_component != COMPONENTS[self.nominal_power]
        ):
            raise ValueError("名义局体课体组件与同时返回五态不符")
        return self


def require_complete_nominal_seasonal(board: Any) -> None:

    if not isinstance(board, dict):
        raise ValueError("完整名义局体季态需要本课对象")
    seasonal = board.get("seasonal_evidence") or {}
    month = seasonal.get("month_branch")
    transmissions = board.get("three_transmissions") or {}
    branches = [
        (transmissions.get(p) or {}).get("branch")
        for p in ("initial", "middle", "final")
    ]
    trines = (board.get("transmission_relations") or {}).get("trines")
    if (
        not isinstance(month, str)
        or not all(isinstance(b, str) for b in branches)
        or not isinstance(trines, list)
        or len(trines) != 4
    ):
        raise ValueError("完整名义局体季态需要同次月建和三传及四局清单")
    for trine in trines:
        expected = (
            nominal_seasonal_evidence(month, trine["nominal_element"])
            if set(trine["branches"]) == set(branches)
            else None
        )
        if (
            "nominal_seasonal_evidence" not in trine
            or trine["nominal_seasonal_evidence"] != expected
        ):
            raise ValueError("完整三合局体须保留同次月建及三传的名义季态与可空事实")
