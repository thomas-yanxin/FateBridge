# 人类图计算参考

[文档中心](README.md) · [API 参考](api-reference.md) · [算法覆盖](algorithm-coverage.md) · [调用合同](contracts/human_design.json) · [人类图解读参考](interpretation/xingpan/human-design.md)

`human_design` 计算出生（人格）与设计（太阳黄经倒推 88°）两个时刻的激活、门/线/Color/Tone/Base、Variable、九大中心、36 通道、类型、权威、定义、桥接方案与 Profile，并返回来源分歧与可用解释。REST 为 `POST /api/human-design/chart`，MCP 与 CLI 为 `human_design`。

## 计算口径与时间尺度

- **双时刻与星历**：物理天体采用 Swiss Ephemeris 地心视位置与回归黄道，地球与南交点为派生对点，平交点使用解析节点模型。缺少 `.se1` 数据文件时回退 Moshier 并标记；设置 `require_swiss_files=true` 可禁止降级。
- **历史时间与闰秒**：1960 年起采用 IAU SOFA / IERS 历史 UTC-TAI 关系与已公布正闰秒（支持 `birth_second=60`），1960 年前采用声明的历史 UT1 约定。
- **设计太阳弧与分类**：在出生前 110 至 70 日 TT 窗口内求解 `太阳黄经(出生) - 太阳黄经(设计) = 88°`，门/线/Color/Tone/Base 采用 64×6×6×6×5 半开区间等分，地球与南交点在精确加 180° 后再分类。
- **可选参数**：`node_mode`（`true` / `mean`）、`cycle_reference_datetime`（搜索出生后 65 儒略年内的土星回归、天王星对冲与凯龙回归）、`birth_time_uncertainty_minutes`（在指定生时正负波动范围内枚举实际变体）、`transit_datetime`（叠加行运闸门与通道）与 `partner`（关系合盘通道）。

## 数据安装与调用示例

如需启用 Swiss Ephemeris 星历分段数据（需覆盖设计盘前推及可选周期窗口年份）：

```bash
uv run --extra dev python -m fatebridge.fetch_ephe --profile human_design
uv run --extra dev python -m fatebridge.fetch_ephe --profile human_design --verify-only
```

CLI 摘要调用示例（使用有效投影路径）：

```bash
uv run --extra dev fatebridge human_design \
  --birth-year 1990 --birth-month 4 --birth-day 6 \
  --birth-hour 9 --birth-minute 33 --birth-timezone Asia/Shanghai \
  --fields bodygraph.type bodygraph.authority profile bodygraph.channels summary
```

## 结构与来源边界

通道、类型与权威依赖同次联合见证，分离定义返回定义分群与最少桥接门集；384 线极性星体与有限公开线义条目保留原典名称与门分界差异。更多解读约定见[人类图解读参考](interpretation/xingpan/human-design.md)。
