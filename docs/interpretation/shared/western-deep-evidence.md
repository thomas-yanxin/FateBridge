# 西占深层证据按问题读取

本页供用户追问古典条件、关系方向、中点／映点、历史钟制或宫制分支时按需查阅。普通生活主题先按[西占主题参考](western-topic-evidence.md)取证。

## 坐标、宫制与星历政策

- **宫头与极区分支**：`house_position_projection` 与 `house_axis_convention` 保留实际投影、极点约定与正反宫序；高纬或极区 `angle_definition.geometric_ascendant_resolved=false` 时，依赖 ASC 的宫头、福点与 13 扇区落区保留为空，仅解释独立 MC 与星体位置。`house_system=6`（或 `T`）为 Topocentric，`Gauquelin`（`G`）当前会明确报错而不静默回退其他宫制。
- **昼夜与时间尺度**：昼夜由太阳中心真实地平高度判定；普通西占保留民用钟时默认（`use_true_solar_time=false`）。`ephemeris_policy=require_data_files` 可拒绝星历降级；卜卦与择日可选 `ut1_source=iers_c04`（覆盖 1962-01-01 至 2026-09-19 UTC）或默认 `swiss_delta_t`，并在 `converted_utc` 中保留 UTC 闰秒（`23:59:60`）而不截断。
- **近太阳与视位置**：可通过 `solar_position_model` 视图查看 `apparent_position_policy`（`foreground_of_solar_disc` / `behind_solar_disc`），或查看 `longitude_motion.complete_position_derivatives`。

## 本命古典细问（`evidence_views`）

按问题复制工具公开 `evidence_views` 的 `fields`（卡名不是请求参数，三端对 `fields` 始终严格校验）：

| 追问场景 | 视图 / 字段 | 读取重点 |
| --- | --- | --- |
| 托勒密原典条件 | `ptolemy` / `classical.ptolemy` | Robbins 1940 I.7、I.13–19 与 III.10 福点算式，与混合传统 `classical.lots.fortune` 分开 |
| 福点与精神点 | `classical_detail` / `classical.lots` | 昼夜公式所得经度、星座与定位星，不补未返回相位 |
| 命主力主 | `classical.almuten_figuris` | 尊贵加权汇总、各星得分与产前朔望（`classical.syzygy`）参与情况 |
| 恒星合相 | `fixed_stars` | 视黄经容许度命中与 SIMBAD 星表模型，不将未计算当无命中 |
| 出生行星日／时 | `planetary_hours` | 当日出生地日出日落划分的不等时辰主星（极昼夜可为 `null`） |

## 历史钟制与 Lilly 卜卦 / 择日

- **历史历法与钟面**：儒略历输入传 `question_calendar=julian` / `candidate_calendar=julian`；地方平/视太阳时通过 `question_clock_basis` / `candidate_clock_basis` 声明并省略时区；正午起算小时标签传 `question_hour_origin=noon` / `candidate_hour_origin=noon`。对应字段卡为 `calendar_input`、`clock_input` 与 `hour_origin`。
- **Lilly 1647 卜卦规则**：按 `lilly_radicality` 读取判断前 12 条款与 `radicality_context`；按 `lilly_sign_rays` 读取有向左右相；按 `lilly_orbs_houses` 读取两列容许度（`orb_profile`）与居宫条件；按 `lilly_fortitudes` 与 `lilly_fortune` 读取第 115 页尊贵弱项及福点计分。子条件成立仍保留各自条款范围。

## 关系盘方向与汉堡中点

- **关系盘深读**（`relationship_detail`）：区分 `in_to_out_aspects` 与 `out_to_in_aspects` 方向、一方星体对另一方中点（`in_to_out_midpoint` / `out_to_in_midpoint`）及映点/反映点（`antiscia`/`contra_antiscia`）；Marks 盘读取 `marks_charts.inner/outer`。
- **汉堡中点与太阳弧**：支持 `meridian_houses`（Witte 1923 赤经子午宫）、`meridian_placement`、`progression_key`（365.25 日钥匙）、`daily_meridian`（Witte 1924 日推运）、`comparative_geometry`（镜点锚框）、`witte1925_table` 与太阳弧交叉组合（`mixed_pairs` / `mixed_pair_sensitivity`）。存在生时不确定范围时按实际样点变化解释。
