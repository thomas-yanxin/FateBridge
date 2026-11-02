# 离线城市与行政区坐标 / Offline place catalog

FateBridge 的 REST、MCP、CLI 共用 `utils/places.py`，不需要在线地理编码服务或 API Key。
`birth_place` 可补全经度、纬度和 IANA 民用时区；显式提供的 `birth_longitude`、`birth_latitude`、`birth_timezone` 各自优先。

## 覆盖范围

数据取得日期为 **2026-10-22**；行政区覆盖按下述来源版本核验，不能理解为未来区划变更会自动同步。

| 范围 | 已收录数量 |
| --- | ---: |
| 大陆省级单位 | 31（含 4 个直辖市） |
| 大陆地级行政单位 | 333（含地级市、自治州、地区、盟） |
| 大陆县级行政单位 | 2,845，其中县级市 397 个 |
| 香港、澳门 | 各 1 个城市代表点 |
| 台湾 | 22 个县市、368 个乡镇市区，另有省级降级点 |
| 中国相关代表点合计 | 3,602 |
| 海外城市 | 6,333 |

海外部分独立于中国行政区计数：亚洲 2,500、欧洲 1,090、非洲 1,140、美洲 1,497（北美 816、南美 681）、大洋洲 106。
从 GeoNames `cities15000` 的现存居民点选择人口至少 10 万的城市、国家首都和一级行政中心，并补充每个国家/地区人口最多的 3 个居民点及大洋洲前 50 个。排除城区分片 `PPLX`、历史/废弃居民点和南极洲。
人口仅用于选择覆盖范围，不用于在同名城市之间猜测用户地点。

中国行政区数据去除了上游为多级联动生成的重复层级，例如地级市下同名的虚拟县级条目、省直辖县级市的重复父子条目。397 个县级市按原始六位行政区代码逐一核对，清单保存在 `manifest.json`。
上游已明确缺少新设的**和康县、和安县**；这两项是县，不影响本版本的县级市覆盖验收，坐标没有用母县中心或猜测值填充。本库并非截至今天的全部县区无缺漏清单。

## 坐标代表什么

- 城市和行政区覆盖的是**来源指定的中心/行政代表点**，不代表任意地址、医院、街道或整个辖区的实测位置。不同来源或版本选取的城市代表点可能变化。
- GeoNames 使用 [WGS84](https://www.geonames.org/about.html)，部分行政点本身存在小数位较少、中心选取较粗的情况。台湾城市优先使用同一行政区内同名居民点的坐标；其他单位保留行政代表点。
- AreaCity 发布的是高德 **GCJ-02** 中心坐标。本项目在导入时使用迭代逆变换产生近似 WGS84，标记 `coordinate_system=WGS84_approx`，保留 `source_coordinates` 原值。存储六位小数表示数值格式，**不承诺米级测绘精度**；逆变换的数值收敛也不是地理误差保证。
- 大陆民用时区统一使用 `Asia/Shanghai`；新疆也遵循此输入约定。若原始记录使用当地其他计时方式，应显式说明时区。香港、澳门、台湾分别使用 `Asia/Hong_Kong`、`Asia/Macau`、`Asia/Taipei`。
- 系统或 dateutil 自带时区库缺少新 IANA 名称时，回退读取依赖 `pytz>=2025.2` 的 TZif 数据；例如 `America/Coyhaique` 也能在旧系统上解析，仍保留原有夏令时重叠/跳过检查。
- 真太阳时经度每相差 1°，经度校正约相差 4 分钟。临近时辰/日期边界、需要更准确星盘地点时，应传实际出生位置的 WGS84 经度和纬度，不能把城市代表点当作具体出生地点。

## 地名与同名处理

支持来源中的中文、简繁体、拼音和英文名称，以及既有兼容别名（如 `peking`、`amoy`、`开县`）。英文忽略大小写和拉丁重音，保留单词边界；不会从 `Comparison` 中抽出 `Paris`。

```text
江苏省南通市海安市                 → 海安，县级
北京市通州区                     → 北京下辖通州区
江苏省南通市通州区                 → 南通下辖通州区
中國臺灣彰化縣員林市               → 员林市，Asia/Taipei
Paris, France                    → Paris，Europe/Paris
London, Canada                   → London，America/Toronto
Sydney, Nova Scotia, Canada       → Sydney，America/Glace_Bay
```

上级行政区参与消歧；`通州区`、`朝阳区`、`和平区` 等缺少必要上级信息时不返回坐标，调用方应补充省、市或国家/州。`London`、`Sydney` 等少数原有常用别名保留既有默认含义，明确的国家/州信息优先。`上海安亭` 不会因跨越“上海”边界抽出“海安”。省级降级仍会通过现有 `resolution_advisory` 告知调用方。

少量海外记录在同一国家、同一一级行政区内仍同名（如巴基斯坦 Punjab 的两个 Sahiwal）。无法由这些限定词区分时继续保留歧义，应提供实际经纬度；不会按人口或数组顺序替用户选点。

三端接口参数保持不变。示例：

```bash
uv run --locked --extra dev fatebridge astro_chart \
  --birth-year 2000 --birth-month 7 --birth-day 1 \
  --birth-hour 12 --birth-minute 10 --birth-place 'Paris, France'
```

## 数据来源、许可与复现

- 中国行政区和 GCJ-02 点位：[AreaCity-JsSpider-StatsGov](https://github.com/xiangyuecn/AreaCity-JsSpider-StatsGov)，版本 `2025.251231.260403`，2026-04-03 发布。上游综合国家地名信息库 2025-12-31、腾讯地图区划 2025-11-19、高德地图行政区划和中心坐标；仓库采用 MIT 许可。
- 海外居民点、台湾行政点和 IANA 时区：[GeoNames 下载](https://download.geonames.org/export/dump/)，使用 `cities15000.zip`、`TW.zip`、`countryInfo.txt`、`admin1CodesASCII.txt`；[格式与许可](https://download.geonames.org/export/dump/readme.txt)为 CC BY 4.0，来源不保证准确性、时效性和完整性。
- 第三方署名、转换和筛选说明随发行包保留在 [NOTICE](../NOTICE)。`src/fatebridge/data/places/manifest.json` 记录来源地址、版本、原始归档/提取文件 SHA-256、产物 SHA-256、数量和县级市代码清单。运行时只读打包后的 JSON，不联网、不依赖 OpenCC。

离线检查（也由测试执行）：

```bash
uv run --locked --extra dev python scripts/build_place_catalog.py --check
uv run --locked --extra dev pytest -q \
  tests/test_place_catalog.py tests/test_place_catalog_transports.py \
  tests/test_birth_place_resolution.py tests/test_birth_time_precision.py
```

更新数据时，将以下文件准备到独立缓存目录：

1. 从 [AreaCity 固定版本 Release](https://github.com/xiangyuecn/AreaCity-JsSpider-StatsGov/releases/tag/2025.251231.260403) 下载 `ok_data_level3-4.csv.7z`、`ok_geo.csv.7z`，保留归档并解出 `ok_data_level3.csv`、`ok_geo.csv`。
2. 从 GeoNames 下载上述四个文件。GeoNames 是滚动数据；重现本版本需要使用与 manifest SHA-256 一致的快照，重新下载的内容可能不同。
3. 使用锁定开发环境中的 OpenCC 生成简繁别名。兼容别名输入在 `scripts/data/place_alias_overrides.json`，仅维护名称，不保留旧坐标。

```bash
uv run --locked --extra dev python scripts/build_place_catalog.py \
  --source-dir /absolute/path/to/place-source-cache
uv run --locked --extra dev python scripts/build_place_catalog.py --check
```

导入不会联网。`--check` 检查已发布 JSON 的摘要、坐标范围、原始坐标逆变换、时区、父子层级/循环、数量和覆盖清单；它不会重新下载上游。来源版本、取得日期和验收数量随区划变更一起审核更新。所有中国代表点还经过完整行政路径逐条解析测试；跨三端测试同时覆盖中国区县、欧洲和大洋洲，只证明软件调用一致性，不证明测绘精度或命理预测有效性。

## English precision note

The offline catalog includes 397 mainland county-level cities, all 333 prefecture-level units in the pinned source, and 6,333 overseas populated places across five inhabited continents. It also includes counties/districts and Taiwan administrative units. The two new counties He'an and Hekang are absent from the upstream release and remain documented gaps.

Coordinates are source-defined city or administrative representative points. GeoNames coordinates use WGS84; AreaCity GCJ-02 points are converted to **approximate WGS84**, with the original values retained. Decimal places do not establish survey accuracy. Supply actual WGS84 birth coordinates when precise location matters. Qualify ambiguous names with their parent city/province or country/state. REST, MCP and CLI share the same offline resolver and IANA timezone data.
