"""Validate line inputs and cast six lines from codes or coin sums."""

import random
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

SIX_YAO_GODS = ["青龙", "朱雀", "勾陈", "腾蛇", "白虎", "玄武"]


SIX_YAO_NAMES = ["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"]


def normalize_cast_lines(lines: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if lines and len(lines) != 6:
        raise ValueError("六爻 lines 必须恰为 6 条，按初爻至上爻排列")
    else:
        pass
    normalized: list[dict[str, Any]] = []
    for item in lines or []:
        if not isinstance(item, dict):
            raise ValueError("六爻 lines 每条必须是爻线对象")
        else:
            pass
        value = item.get("value")
        if type(value) is not int or value not in (0, 1):
            raise ValueError("六爻 value 必须为 0 或 1")
        else:
            pass
        if type(item.get("change", False)) is not bool:
            raise ValueError("六爻 change 必须为布尔值")
        else:
            pass
        normalized.append(
            {
                "value": value,
                "change": bool(item.get("change")),
                "god": item.get("god"),
                "name": item.get("name"),
            }
        )
    return normalized


def validate_hexagram_code(code: str | None) -> str:
    if code is None:
        return ""
    else:
        pass
    if not isinstance(code, str) or len(code) != 6 or set(code) - {"0", "1"}:
        raise ValueError("六爻卦码必须是 6 位 0/1 字符串，不接受被忽略的其他字符。")
    else:
        pass
    return code


def needs_random_coin_cast(inputs: dict[str, Any]) -> bool:
    """Share the engine's manual-input precedence with replay seed handling."""
    return (
        (inputs.get("method") or "auto").strip().lower() == "coin"
        and inputs.get("coins") is None
        and not normalize_cast_lines(inputs.get("lines"))
        and not (
            validate_hexagram_code(inputs.get("gua_code"))
            or validate_hexagram_code(inputs.get("changed_code"))
        )
    )


def cast_hexagram_code(lines: list[dict[str, Any]]) -> str:
    return "".join(str(int(line.get("value", 0))) for line in lines) or "000000"


def changed_hexagram_code(lines: list[dict[str, Any]]) -> str:
    chars: list[str] = []
    for line in lines:
        value = int(line.get("value", 0))
        if line.get("change"):
            value = 1 - value
        else:
            pass
        chars.append(str(value))
    return "".join(chars) or "000000"


def cast_lines_from_codes(
    current_code: str, changed_code: str | None = None
) -> list[dict[str, Any]]:
    current = validate_hexagram_code(current_code)
    changed = current if changed_code is None else validate_hexagram_code(changed_code)
    if len(current) != 6 or len(changed) != 6:
        raise ValueError("六爻卦码必须是 6 位 0/1 字符串。")
    else:
        pass

    normalized: list[dict[str, Any]] = []
    for index, (current_bit, changed_bit) in enumerate(zip(current, changed)):
        normalized.append(
            {
                "value": int(current_bit),
                "change": current_bit != changed_bit,
                "god": SIX_YAO_GODS[index],
                "name": SIX_YAO_NAMES[index],
            }
        )
    return normalized


class CoinToss(TypedDict):
    position: int
    name: str
    sum: int
    yao: str
    symbol: str
    moving: bool


@dataclass(kw_only=True)
class CoinCast:
    lines: list[dict[str, Any]]
    tosses: list[CoinToss]


class CoinLineMeaning(TypedDict):
    yao: str
    symbol: str
    value: Literal[0, 1]
    change: bool


COIN_LINE_MEANINGS: dict[int, CoinLineMeaning] = {
    6: {"yao": "老阴", "symbol": "× 交", "value": 0, "change": True},
    7: {"yao": "少阳", "symbol": "⚊", "value": 1, "change": False},
    8: {"yao": "少阴", "symbol": "⚋", "value": 0, "change": False},
    9: {"yao": "老阳", "symbol": "○ 重", "value": 1, "change": True},
}


def random_coin_tosses(rng: random.Random) -> list[int]:
    """系统随机摇卦：六掷，每掷三枚铜钱（字面=2 / 背面=3 等概率），返回六个和。"""
    return [sum(rng.choice((2, 3)) for _ in range(3)) for _ in range(6)]


def coin_cast(coin_sums: list[int]) -> CoinCast:
    """Convert six toss sums in bottom-up order and retain each reported sum."""
    if len(coin_sums) != 6:
        raise ValueError("摇钱起卦需要 6 掷（初爻→上爻）。")
    else:
        pass
    lines: list[dict[str, Any]] = []
    tosses: list[CoinToss] = []
    for index, coin_sum in enumerate(coin_sums):
        meaning = COIN_LINE_MEANINGS.get(coin_sum) if type(coin_sum) is int else None
        if meaning is None:
            raise ValueError(
                "摇钱起卦每掷之和必须为 6/7/8/9（三枚铜钱，字面=2、背面=3）。"
            )
        else:
            pass
        lines.append(
            {
                "value": meaning["value"],
                "change": meaning["change"],
                "god": SIX_YAO_GODS[index],
                "name": SIX_YAO_NAMES[index],
            }
        )
        tosses.append(
            {
                "position": index + 1,
                "name": SIX_YAO_NAMES[index],
                "sum": coin_sum,
                "yao": meaning["yao"],
                "symbol": meaning["symbol"],
                "moving": meaning["change"],
            }
        )
    return CoinCast(lines=lines, tosses=tosses)
