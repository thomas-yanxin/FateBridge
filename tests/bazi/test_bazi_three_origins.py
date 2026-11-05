"""命宫 / 身宫 / 胎元 (三元) 数值回归。

基线为 lunar_python (de-facto 标准八字库) 的 getMingGong / getShenGong /
getTaiYuan，在 300 张随机盘上与本模块的算法逐一核对一致。这里冻结 8 张代表盘
(含晚子时、各五行局、命宫支环绕等情形) 防止 命宫天干 / 身宫 回归。

历史 bug:
- 命宫天干曾用「月柱干 + 月支→命宫支 的 mod-12 位移」推导，与天干 mod-10
  循环不匹配，命宫支环绕到月支之前时天干恒偏 +2。
- 身宫曾用寅起序数处理时支 (应子起)，干支全错。
两者均应改用「年干起五虎遁」按宫位定位 (与 lunar_python 一致)。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from fatebridge.core.calendar import BaZiCalendar
from fatebridge.services.bazi import _build_three_origins

# (year, month, day, hour, minute): {origin: 干支}  —— 真值取自 lunar_python
_CASES = {
    (2000, 12, 10, 9, 55): {"minggong": "戊子", "shengong": "壬午", "taiyuan": "己卯"},
    (1990, 6, 15, 14, 30): {"minggong": "庚辰", "shengong": "戊寅", "taiyuan": "癸酉"},
    (1985, 3, 21, 6, 0): {"minggong": "丁亥", "shengong": "癸未", "taiyuan": "庚午"},
    (1994, 8, 23, 14, 0): {"minggong": "丙寅", "shengong": "戊辰", "taiyuan": "癸亥"},
    (1977, 11, 2, 23, 30): {"minggong": "丁未", "shengong": "辛亥", "taiyuan": "辛丑"},
    (2008, 8, 8, 20, 8): {"minggong": "癸亥", "shengong": "己未", "taiyuan": "辛亥"},
    (1966, 1, 20, 3, 0): {"minggong": "戊寅", "shengong": "庚辰", "taiyuan": "庚辰"},
    # golden-master 盘 (张三 1990-05-15 10:30)：曾冻结 身宫=癸未 (误)，应为 丁亥
    (1990, 5, 15, 10, 30): {"minggong": "癸未", "shengong": "丁亥", "taiyuan": "壬申"},
}


@pytest.mark.parametrize("birth,expected", list(_CASES.items()))
def test_three_origins_match_lunar_python(birth, expected):
    pillars = BaZiCalendar.get_four_pillars(datetime(*birth), "Asia/Shanghai")
    origins = _build_three_origins(pillars)
    actual = {key: origins[key]["pillar"] for key in expected}
    assert actual == expected
