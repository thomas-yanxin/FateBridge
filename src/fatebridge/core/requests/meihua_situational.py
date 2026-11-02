"""Reported same-cast contexts for four selected NLC ten-response headings."""

from typing import Literal, Optional

from pydantic import Field, StrictBool, model_validator

from .base import _DeferredModel

Direction = Literal[
    "north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"
]


class MeihuaQuerentPosition(_DeferredModel):
    direction: Direction = Field(
        description="Reported compass side occupied by the person asking at this cast; not movement heading, facing, address or the casting object's direction. No compass bearing or north-reference conversion inferred"
    )
    reference_label: str = Field(
        min_length=1,
        max_length=240,
        description="Caller-reported reference/origin for this occupied side; not parsed or independently located",
    )

    @model_validator(mode="after")
    def nonblank_reference(self) -> "MeihuaQuerentPosition":
        if not self.reference_label.strip():
            raise ValueError("方应须有已报方位参照，不能用空白代替未知")
        return self


class MeihuaResponseContext(_DeferredModel):
    label: str = Field(min_length=1, max_length=240)
    same_casting_episode_confirmed: StrictBool = Field(
        json_schema_extra={"const": True},
        description="Caller explicitly confirms these are reported actual conditions at this casting episode, not desired/future outcomes. Presence/classification is not independently verified",
    )
    querent_position: Optional[MeihuaQuerentPosition] = None
    weather: Optional[
        list[Literal["clear", "rain", "snow", "rain_or_snow", "wind", "thunder"]]
    ] = Field(
        default=None,
        min_length=1,
        max_length=6,
        description="Reported present conditions corresponding to 晴明/雨/雪/雨雪未分/風/雷. 雨雪皆配坎, but坎體宜雨does not uniquely establish a preference for snow; rain_or_snow keeps that condition pending. Human-matter 天時應 only; not a future weather prediction or daily rain label. Unknown omit/null; multiple observations retained without voting",
    )
    setting: Optional[
        list[
            Literal[
                "bamboo_woodland",
                "rivers_streams_or_pools",
                "metal_place",
                "kiln_stove_or_fire",
                "earth_or_tiles",
            ]
        ]
    ] = Field(
        default=None,
        min_length=1,
        max_length=5,
        description="Reported place at the cast: 竹林/江河溪澗池沼/五金/窰竈爐火/土瓦. Keep all source trigram candidates; never infer setting from address, objects, question or unseen scene",
    )
    human: Optional[
        list[
            Literal[
                "elderly_man",
                "elderly_woman",
                "young_boy",
                "young_girl",
                "heard_laughter",
                "weeping_encountered",
            ]
        ]
    ] = Field(
        default=None,
        min_length=1,
        max_length=6,
        description="Caller-reported source classes 老人/老婦/少男/少女 or actually heard笑語/encountered哭泣. No numerical age cutoffs, automatic person classification or outcomes. Laughter/weeping do not manufacture a trigram",
    )

    @model_validator(mode="after")
    def confirmed_and_unique(self) -> "MeihuaResponseContext":
        if not self.label.strip():
            raise ValueError("十应现场资料label不能仅为空白")
        if not self.same_casting_episode_confirmed:
            raise ValueError("十应资料须明确确认是同次起卦时已报现场条件")
        for name in ("weather", "setting", "human"):
            values = getattr(self, name)
            if values is not None and len(set(values)) != len(values):
                raise ValueError("同类现场条目不得重复以增加象义票数")
        return self

    def validate_quiet_context(self, context: dict | None) -> None:
        if context is None:
            return
        known = any(
            getattr(self, name) is not None
            for name in ("querent_position", "weather", "setting", "human")
        )
        if known and all(
            context.get(name) is True
            for name in ("quiet_room", "nothing_heard", "nothing_seen")
        ):
            raise ValueError("同次静室无所闻见的完整声明不能同时附带十应现场事实")
        if (
            "heard_laughter" in (self.human or [])
            and context.get("nothing_heard") is True
        ):
            raise ValueError("同次已闻笑语与nothing_heard=true相冲突")
