"""
Tong She Fa (通蓍法) divination.

Pure relocation from the package facade.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..divination import BAGUA_BY_NAME, HEXAGRAM_NAMES, lookup_hexagram_by_code
from .chart import (
    _join_lines,
    _render_snapshot_text,
)


def _bagua(name: str) -> Dict[str, Any]:
    source = BAGUA_BY_NAME[name]
    return {
        "name": name,
        "cname": source["nature"],
        "nature": source["nature"],
        "elem": source["element"],
        "element": source["element"],
        "value": list(source["lines"]),
        "lines": list(source["lines"]),
        "symbol": source["symbol"],
    }


def _bagua_from_lines(lines: List[int]) -> Dict[str, Any]:
    for name, source in BAGUA_BY_NAME.items():
        if list(source["lines"]) == list(lines):
            return _bagua(name)
    return _bagua("乾")


def _hex(upper: Dict[str, Any], lower: Dict[str, Any]) -> Dict[str, Any]:
    lines = [*lower["value"], *upper["value"]]
    name = HEXAGRAM_NAMES.get(
        (upper["name"], lower["name"]), f"{upper['cname']}{lower['cname']}"
    )
    payload: Dict[str, Any] = {
        "name": name,
        "upper": upper,
        "lower": lower,
        "lines": lines,
        "value": lines,
        "binary_code": "".join(str(bit) for bit in lines),
        "symbol": f"{upper['symbol']}{lower['symbol']}",
    }
    # binary_code 由两枚合法八卦的 6 位线值拼成，恒为合法卦码，
    # lookup_hexagram_by_code 不会对它抛 ValueError。过去这里用
    # ``except ValueError: pass`` 兜底，等于把「卦码构造出错」这类内部
    # 不变量被破坏的真实 bug 静默吞掉、产出一枚缺 theme/judgement/image
    # 的残卦。改为直接调用：真出错就大声抛，而非伪装成功。
    detail = lookup_hexagram_by_code(payload["binary_code"])
    payload.update(
        {
            "theme": detail.get("theme"),
            "judgement": detail.get("judgement"),
            "image": detail.get("image"),
        }
    )
    return payload


def _mutual_hex(hexagram: Dict[str, Any]) -> Dict[str, Any]:
    lines = hexagram["lines"]
    mutual_lines = [lines[1], lines[2], lines[3], lines[2], lines[3], lines[4]]
    lower = _bagua_from_lines(mutual_lines[:3])
    upper = _bagua_from_lines(mutual_lines[3:])
    return _hex(upper, lower)


def _opposite_hex(hexagram: Dict[str, Any]) -> Dict[str, Any]:
    opposite_lines = [0 if bit == 1 else 1 for bit in hexagram["lines"]]
    lower = _bagua_from_lines(opposite_lines[:3])
    upper = _bagua_from_lines(opposite_lines[3:])
    return _hex(upper, lower)


def _tongshefa_relation_by_elem(left_elem: str, right_elem: str) -> str:
    sheng = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
    ke = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
    if left_elem == right_elem:
        return "思同实"
    if sheng[left_elem] == right_elem:
        return "思生实"
    if ke[left_elem] == right_elem:
        return "思克实"
    if sheng[right_elem] == left_elem:
        return "实生思"
    if ke[right_elem] == left_elem:
        return "实克思"
    return "思同实"


def _build_tongshefa_snapshot(model: Dict[str, Any]) -> str:
    rows = []
    for index in range(5, -1, -1):
        rows.append(
            f"第{index + 1}爻：左{'阳' if model['baseLeft']['lines'][index] == 1 else '阴'} / "
            f"右{'阳' if model['baseRight']['lines'][index] == 1 else '阴'} / "
            f"{'不变' if model['baseLeft']['lines'][index] == model['baseRight']['lines'][index] else '已变'}"
        )
    return _render_snapshot_text(
        [
            (
                "本卦",
                _join_lines(
                    [
                        f"左卦：{model['baseLeft']['name']}（上卦{model['baseLeft']['upper']['name']} / 下卦{model['baseLeft']['lower']['name']}）",
                        f"右卦：{model['baseRight']['name']}（上卦{model['baseRight']['upper']['name']} / 下卦{model['baseRight']['lower']['name']}）",
                    ]
                ),
            ),
            ("六爻", _join_lines(rows)),
            (
                "潜藏",
                _join_lines(
                    [
                        f"左潜藏：{model['mutualLeft']['name']}",
                        f"右潜藏：{model['mutualRight']['name']}",
                    ]
                ),
            ),
            (
                "亲和",
                _join_lines(
                    [
                        f"左亲和：{model['oppositeLeft']['name']}",
                        f"右亲和：{model['oppositeRight']['name']}",
                    ]
                ),
            ),
        ]
    )


def build_tongshefa_result(
    *,
    taiyin: Optional[str] = None,
    taiyang: Optional[str] = None,
    shaoyang: Optional[str] = None,
    shaoyin: Optional[str] = None,
) -> Dict[str, Any]:
    selected = {}
    for field, value, default in (
        ("taiyin", taiyin, "巽"),
        ("taiyang", taiyang, "坤"),
        ("shaoyang", shaoyang, "震"),
        ("shaoyin", shaoyin, "震"),
    ):
        if value is not None and value not in BAGUA_BY_NAME:
            raise ValueError(f"{field}必须为乾、兑、离、震、巽、坎、艮或坤")
        selected[field] = default if value is None else value
    taiyin_gua = _bagua(selected["taiyin"])
    taiyang_gua = _bagua(selected["taiyang"])
    shaoyang_gua = _bagua(selected["shaoyang"])
    shaoyin_gua = _bagua(selected["shaoyin"])

    base_left = _hex(taiyin_gua, shaoyang_gua)
    base_right = _hex(taiyang_gua, shaoyin_gua)
    mutual_left = _mutual_hex(base_left)
    mutual_right = _mutual_hex(base_right)
    opposite_left = _opposite_hex(base_left)
    opposite_right = _opposite_hex(base_right)
    left_elem = base_left["upper"]["elem"]
    right_elem = base_right["upper"]["elem"]
    main_relation = _tongshefa_relation_by_elem(left_elem, right_elem)
    model = {
        "selected": selected,
        "baseLeft": base_left,
        "baseRight": base_right,
        "mutualLeft": mutual_left,
        "mutualRight": mutual_right,
        "oppositeLeft": opposite_left,
        "oppositeRight": opposite_right,
        "left_elem": left_elem,
        "right_elem": right_elem,
        "main_relation": main_relation,
    }
    snapshot_text = _build_tongshefa_snapshot(model)
    return {
        "analysis_type": "统摄法分析",
        "input_normalized": selected,
        "tongshefa": model,
        "snapshot_text": snapshot_text,
        "summary": f"已运行本地统摄法算法。本卦：左{base_left['name']}，右{base_right['name']}。主关系：{main_relation}。",
    }
