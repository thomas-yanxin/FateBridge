"""Caller-confirmed day branch, independent of inferred or current dates."""

from typing import Literal, Optional

from pydantic import Field, model_validator

from .base import _DeferredModel


class MeihuaDayQiContext(_DeferredModel):
    label: str = Field(min_length=1, max_length=240)
    day_branch: Literal[
        "子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"
    ] = Field(
        description="Caller-confirmed day branch, never the hour/year branch or lunar day number"
    )
    declared_day_boundary: Optional[Literal["local_midnight", "zi_start"]] = Field(
        default=None,
        description="Optional caller-declared convention; without a civil date it is not verified or used to infer another date/branch",
    )

    @model_validator(mode="after")
    def nonblank_label(self) -> "MeihuaDayQiContext":
        if not self.label.strip():
            raise ValueError("日气资料label不能仅为空白")
        return self
