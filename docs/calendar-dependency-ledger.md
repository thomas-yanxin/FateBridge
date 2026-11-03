# 历法与星历：依赖及未决项台账

本表供修改共享计算时确定影响范围。它记录已有证据与当前代码入口，不是一次新的天文验收，也不是穷尽所有间接调用的调用图。各审计的固定样本、失败、参考和门槛以原报告为准；不同模型、时标或参考分辨率的结果不能相互抵销。

## 共享依赖与消费者

| 依赖 | 已核对的消费路径 | 修改时重点 |
| --- | --- | --- |
| `core/almanac.py` 的节气年表和相邻节气 | `services/calendar_tools.py`、`core/timing.py`、`core/metaphysics/ren_calendar.py`、`core/liuyao_calendar_models.py`、`core/fengshui/calendar.py`、`core/fengshui/monthly_time.py` | 分别检查实际提供者、TT 交点、民用时间转换及各消费者在边界两侧的分类；参见[六壬审计](liuren-jinkou-audit.md)与[风水历法审计](fengshui.md)。 |
| 同一节气年表的河洛／参评路径 | `core/heluo_solar_context.py`、`core/heluo_seasonal.py`、`core/canping_solar.py` | 河洛绑定当前节气、前一至点及下一四立；参评还取投影立春。保留实际消费的模型与来源，不能用另一路模型的通过结果改写 Native 失败。见[太阳网格审计](validation/heluo-solar-domain-audit.md)。 |
| 农历日期与时区 | `core/ziwei_age.py`、`core/ziwei_calendar.py` | 安星时钟、岁序参考时钟与目标流曜时钟各有职责；修改其中之一应检查其他输出是否被误改。见[紫微岁序](ziwei.md#统一岁序的两个时钟端点)。 |
| Swiss 星历与时间尺度 | `services/human_design.py` 及人类图计算链 | 按实际旗标和文件核对出生及设计时刻，分别检查后端对坐标、太阳根和细分的影响；不能仅以可导入库判断使用了数据文件。见[人类图验收](human-design.md)。 |

这些路径共享某些基础组件，不意味着它们的全部历法策略、覆盖年份或后端选择相同。扩展影响范围时应沿实际调用链核实。

## 固定问题与处理状态

| 项目 | 已有记录 | 状态及下一步 |
| --- | --- | --- |
| 河洛／参评 Native 太阳交点 | 原96项中84项在1秒线内、12项超差；另一模型的15,020项有限 TT 网格结果单列。[报告与冻结证据](validation/heluo-solar-domain-audit.md) | Moshier 系数与归心近似的超差仍保留。新增显式 `swiss` 文件模式通过同96点原1秒线，缺数据明确失败；[当前复核](validation/solar-numerics-20261103-v1/report.md)分别报告两种模型，未用文件模型改判原失败。 |
| 六壬节气分钟标签 | 原3,024项分钟标签同版本重放，Swiss 21项、自动 DE440 22项超差；另有日期差异。[六壬审计](liuren-jinkou-audit.md)保留时间尺度修复、历史结果及参考限制。 | 未解决。先逐项对齐实际后端、TT 与民用转换、印刷分钟的分辨率，再定位差异；不要用 TT 网格通过替代分钟标签验收。 |
| 紫微春节混合时钟岁序 | 默认 `birth_civil_timezone` 已统一出生与目标的岁序参考区，原案例由拒算变为1岁；`legacy_mixed_clock` 仍回放旧错误。[紫微文档](ziwei.md#统一岁序的两个时钟端点)及 `tests/test_ziwei_twenty_first_iteration.py` 保留反向跨日和旧口径。 | 默认软件口径已修复；古典岁首依据仍未认证。保持实际早于出生的拒绝及各时钟的独立角色，不以本修复宣称原典或预测验收。 |
| 人类图星历细分 | 有固定的 Swiss／Moshier 跨 Base 和跨线反例；独立有限样本中 Moshier 有228项位置超原2角秒容差。[验收说明](human-design.md) | 未解决为全时域精度问题。保留模型身份、差异和未知，分别复核坐标、设计根与细分；不能把有文件或小求根残差当成物理精度保证。 |

## 星历路径解析的一致性

`core/ephemeris_paths.py` 统一处理星历目录列表，供安装提示、`doctor` 的风水／人类图检查、节气缓存、运行来源记录及梅花历法审计使用。Unix 同时支持冒号和分号，Windows 保留盘符冒号；原有目录顺序和相对路径含义保持。路径约定参照 [Swiss 官方接口文档](https://www.astro.com/swisseph/swephprg.htm)及[原生文件搜索实现](https://github.com/aloistr/swisseph/blob/master/sweph.c)。

此前在 Unix 使用 `SE_EPHE_PATH=first;second`，诊断与安装提示会将其视作单个目录，和节气缓存及来源记录的解析不一致。统一后可逐目录报告实际文件状态，并正确识别新文件目录已在搜索路径中。连续分隔符合并处理，依据[原生 `swi_cutstr` 实现](https://github.com/aloistr/swisseph/blob/master/swephlib.c)，不再将列表中间的空段当作额外当前目录写入缓存及来源记录。此项修复针对文件就绪诊断和目录清单，不改变太阳模型、交气数值或上表的固定失败。

## 修复及验收约定

先保留失败输入、参考来源、模型和容差，再对明确原因作最小修复。共享计算改动应按实际受影响路径检查 REST、MCP、CLI；本地接口一致、独立数值参考、原典规则、模型解释和现实预测分别报告。边界测试应覆盖两侧及同一瞬间的时区转换，并保留不同后端和历史失败。缺乏可裁定来源时保留未知，不为提高通过率修改固定门槛。
