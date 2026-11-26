# 离线城市与行政区坐标 / Offline place catalog

[文档中心](README.md) · [API 参考](api-reference.md)

FateBridge 的 REST、MCP、CLI 共用 `utils/places.py`，不需要在线地理编码服务或 API Key。`birth_place` 可补全经度、纬度和 IANA 民用时区；显式提供的 `birth_longitude`、`birth_latitude`、`birth_timezone` 各自优先。

## 覆盖范围

行政区与城市覆盖按内置静态数据（数据截止 2026-10-22）提供，不自动同步后续行政区划调整：

| 范围 | 已收录数量 |
| --- | ---: |
| 大陆省级单位 | 31（含 4 个直辖市） |
| 大陆地级行政单位 | 333（含地级市、自治州、地区、盟） |
| 大陆县级行政单位 | 2,845，其中县级市 397 个 |
| 香港、澳门 | 各 1 个城市代表点 |
| 台湾 | 22 个县市、368 个乡镇市区，另有省级降级点 |
| 中国相关代表点合计 | 3,602 |
| 海外城市 | 6,333 |

海外部分包含亚洲 2,500、欧洲 1,090、非洲 1,140、美洲 1,497（北美 816、南美 681）、大洋洲 106，从 GeoNames `cities15000` 选取主要城市与行政中心；同名城市不会按人口猜测地点。中国行政区数据已去除多级联动造成的重复父子条目。

## 坐标与时区口径

- 城市和行政区坐标为来源指定的中心或行政代表点，并非具体医院或街道坐标。GeoNames 使用 WGS84；AreaCity 的 GCJ-02 中心坐标在导入时转换为近似 WGS84（标记 `coordinate_system=WGS84_approx`，保留 `source_coordinates` 原值）。需要高精度出生位置时，请直接传入实测 WGS84 经纬度。
- 大陆民用时区统一使用 `Asia/Shanghai`；香港、澳门、台湾分别使用 `Asia/Hong_Kong`、`Asia/Macau`、`Asia/Taipei`。
- 命名时区统一由标准库 `zoneinfo` 读取随 `pytz` 锁定的 TZif 数据，不依赖宿主机时区表差异，并保留重复或不存在钟时的校验。

## 地名消歧与调用示例

支持目录收录的中文、简繁体、拼音、英文及常见兼容别名（如 `peking`、`amoy`），匹配忽略大小写和组合重音。存在同名区县（如 `通州区`、`朝阳区`）或海外同名城市时，请附带省、市或国家/州名消歧：

```text
江苏省南通市海安市                 → 海安，县级
北京市通州区                     → 北京下辖通州区
江苏省南通市通州区                 → 南通下辖通州区
中國臺灣彰化縣員林市               → 员林市，Asia/Taipei
Paris, France                    → Paris，Europe/Paris
London, Canada                   → London，America/Toronto
Sydney, Nova Scotia, Canada       → Sydney，America/Glace_Bay
```

使用逗号或换行分隔多个地址成分时，所有识别成分需指向同一候选辖区；无法消除歧义的地区（如同一省内重名城市）将保留未定位状态并提示传入经纬度。调用示例：

```bash
uv run --extra dev fatebridge astrology_chart \
  --birth-year 2000 --birth-month 7 --birth-day 1 \
  --birth-hour 12 --birth-minute 10 --birth-place 'Paris, France'
```

## 数据来源与本地校验

- 中国行政区点位：[AreaCity-JsSpider-StatsGov](https://github.com/xiangyuecn/AreaCity-JsSpider-StatsGov)（MIT 许可）。
- 海外居民点与台湾行政点：[GeoNames](https://download.geonames.org/export/dump/)（CC BY 4.0）。
- 运行时只读取随包发布的 `src/fatebridge/data/places/` JSON，不联网且不依赖外部库；第三方许可详见 [NOTICE](../NOTICE)。

离线回归测试命令（核对静态目录解析、坐标与边界）：

```bash
uv run --extra dev pytest -q tests/integration/test_place_catalog.py tests/integration/test_birth_place_resolution.py
```

## English note

The offline catalog covers 397 mainland county-level cities, 333 prefecture-level units, Taiwan administrative units, and 6,333 overseas populated places. Coordinates are city or administrative representative points (WGS84 from GeoNames, approximate WGS84 converted from GCJ-02 for AreaCity). Supply explicit WGS84 coordinates and IANA time zones whenever exact birth location precision is required.
