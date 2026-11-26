"""Validate supported Qimen chart options and build boards."""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.qimen import build_qimen_board
from fatebridge.core.qimen.qimen_profiles import (
    DEFAULT_GOD_PROFILE,
    DEFAULT_SEASON_PROFILE,
)


def build_qimen_with_options(
    seed: MetaphysicsSeed, options: dict[str, Any] | None
) -> dict[str, Any]:
    normalized = dict(options or {})
    unknown = set(normalized) - {
        "layout",
        "palaceShift",
        "palace_shift",
        "ju_method",
        "god_profile",
        "season_profile",
    }
    if unknown:
        raise ValueError(f"不支持的奇门选项：{sorted(unknown)}")
    layout = normalized.get("layout", "direct")
    if layout not in ("direct", "rotating"):
        raise ValueError(
            "仅支持有明确规则的转盘 layout=direct；fly/fei、镜像或反转不是已实现的奇门流派"
        )
    for key in ("palaceShift", "palace_shift"):
        shift = normalized.get(key, 0)
        if type(shift) is not int or shift != 0:
            raise ValueError("palaceShift仅允许0；移动九宫内容不能冒充飞盘排法")
    method = normalized.get("ju_method", "zhirun")
    if method not in ("zhirun", "chaibu"):
        raise ValueError("ju_method仅支持zhirun（置闰）或chaibu（拆补）")
    return build_qimen_board(
        seed,
        ju_method=method,
        god_profile=normalized.get("god_profile", DEFAULT_GOD_PROFILE),
        season_profile=normalized.get("season_profile", DEFAULT_SEASON_PROFILE),
    )
