# FateBridge 算法与能力覆盖矩阵

[文档中心](README.md) · [核心概念](concepts.md) · [API 参考](api-reference.md)

本页按中央目录 `src/fatebridge/services/tool_catalog.py` 列出 FateBridge 的 12 个 family 与 90 项计算能力，说明实现状态、依赖条件与适用边界。输入字段与参数详情见 [API 参考](api-reference.md)，结果解读指引见[方法参考](interpretation/README.md)。

状态分类：

- `Implemented`：仓库内已有实现，可通过中央目录声明的接口访问；具体规则分支与限定条件以各表及领域参考为准。
- `Approximate`：可用，但算法属于内置近似或依赖回退路径。
- `Partial` / `Limited`：已实现明确子集，存在未覆盖或未裁定的规则范围。
- `Excluded`：当前仓库不提供该能力。

> 工具来自中央目录 `src/fatebridge/services/tool_catalog.py`。REST 公开 **90 个工具**，MCP 通过两个入口提供 **90 项业务能力**，分为 **12 个 family**。目录共有 90 条记录，CLI 可执行 90 条。

## 怎样核对一次结果

| 核对项 | 看什么 | 说明 |
| --- | --- | --- |
| 接口成功 | HTTP 状态、MCP `isError`、CLI 退出码与错误包络 | 接口成功不代表请求的所有分层都完整无缺项 |
| 计算与规则覆盖 | 实际 `status`、`coverage`、缺失项及 `rulesets` | `partial` 只限制对应层，未计算项不视作否定 |
| 数值与时间精度 | `chart_profile.ephemeris_model`、`time_adjustment` 与 `engine_is_approximate` | 依赖库可导入不代表已加载外部 `.se1` 星历文件 |
| 可追溯性 | 原输入、`run_metadata`、版本、来源与环境 | 重放需保留原输入、`as_of` 与环境设置 |

## 1. 总览：12 个 family / 90 个工具

| family | 工具数 | 主题 | 总体状态 |
| --- | --- | --- | --- |
| `bazi` | 12 | 八字命盘、九大专项、综合命理及原典四柱核对 | Implemented |
| `compatibility` | 2 | 双人配合（八字合婚 / 宿曜相性） | Implemented |
| `timing` | 9 | 大运 / 流年 / 流月 / 流日 / 流时 / 节气 / 农历 | Implemented |
| `divination` | 10 | 梅花、六爻、统摄法、参评数、河洛、宿占、占星骰、三式合参 | Implemented |
| `metaphysics` | 8 | 紫微斗数、六壬、奇门、太乙、金口诀 | Implemented |
| `astro` | 9 | 核心星盘、印占本命／分盘／达沙、果老、德国盘、人类图及关系盘 | Implemented（精度依赖星历） |
| `western_timing` | 12 | 西占推运总览与 11 项独立推运技法（返照/行运/主限/法达等） | Implemented（依赖 backend） |
| `western_event` | 4 | 事件占星（世俗/卜卦/择日/多重回归） | Implemented（依赖 backend） |
| `western_lifespan` | 13 | 传统阶段与周期技法（不用于寿命推断） | Implemented（依赖 backend） |
| `knowledge` | 2 | 内置知识库目录与读取 | Implemented |
| `fengshui` | 8 | 公共方位与地磁、命卦、八宅三要、金锁 24 山、四层紫白、玄空宅盘、多层合参 | Implemented（明确版本） |
| `psychometrics` | 1 | Goldberg (1992) IPIP 50 题大五人格因子标记量表 | Implemented |
| 仓库内前端 | — | 内置 Web UI | Excluded |
| 存储 / 账户 | — | 持久化数据库、历史记录、用户体系 | Excluded |

## 2. 逐 family 工具清单

### 2.1 `bazi` —— 八字与命理分析（Implemented）

底层由 `fatebridge.core.bazi.calendar`、`strength`、`relations` 与 `fatebridge.services.bazi` 提供；九大专项维度默认按出生资料与分析日期内部推算大运和流年，也可用 `dayun_pillar` / `liunian_pillar` 覆盖。支持通过已知 `birth_second` 与 `birth_utc_offset` 传递精确秒数并消歧重复民用钟时。

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `bazi_overview` | 综合命理分析（八字 + 喜用 + 格局） | Implemented |
| `bazi_birth_chart` | 离线八字命盘（四柱、三元、十神、五行、神煞与大运流年概略） | Implemented |
| `compare_bazi_sources` | 已明确的字面四柱与登记原典编释逐项核对，不反推生日 | Implemented |
| `bazi_marriage` | 配偶星／宫与传统婚姻象意 | Implemented，限定规则 |
| `bazi_career` | 事业类型、行业、创业倾向与贵人方位 | Implemented |
| `bazi_wealth` | 正偏财、财库、求财方式方位与风险特征 | Implemented |
| `bazi_health` | 盘内五行权重、寒暖分类与传统文化对应（不做医疗诊断） | Implemented |
| `bazi_children` | 命主视角的子女星／宫传统对应（不推数量或生育时间） | Implemented |
| `bazi_education` | 印星／食伤／官星、文昌与学业结构 | Implemented，限定规则 |
| `bazi_personality` | 日主心性、五行与十神结构特征 | Implemented |
| `bazi_relatives` | 父母、兄弟姐妹星与六亲宫位 | Implemented |
| `bazi_romance` | 桃花咸池、红鸾天喜等传统关系象意 | Implemented，限定规则 |

### 2.2 `compatibility` —— 双人配合（Implemented）

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `bazi_compatibility` | 双人八字干支接触与十神配合分析 | Implemented |
| `sukuyo_compatibility` | 宿曜双人相性（三九之秘法，二十七宿） | Implemented |

### 2.3 `timing` —— 时运与历法（Implemented）

基于本地历法算法（`fatebridge.core.almanac`）与共享太阳时归一化（`fatebridge.utils.solar_time`），年/月柱及交节采用实际民用时刻，日/时柱按规则应用真太阳时。

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `bazi_timing` | 综合时运（大运/流年/流月及根位与有限交互作用） | Implemented |
| `bazi_luck_cycles` | 大运分析 | Implemented |
| `bazi_yearly_timing` | 流年分析 | Implemented |
| `bazi_monthly_timing` | 流月分析 | Implemented |
| `bazi_daily_timing` | 流日分析 | Implemented |
| `bazi_hourly_timing` | 流时分析 | Implemented |
| `solar_term_timeline` | 节气时间轴分析 | Implemented |
| `solar_terms_for_year` | 指定年份节气时刻表（calendar helper） | Implemented |
| `lunar_calendar_time` | 公历时刻转农历与干支（calendar helper） | Implemented |

### 2.4 `divination` —— 占卜与本地技法（Implemented）

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `gua_lookup` | 八卦与六十四卦批量卦象、结构及义理查询（支持 `queries` 与 `lookup_mode`） | Implemented |
| `meihua_time_cast` | 梅花易数时间取数、体用互变、季令与经文参照 | Implemented |
| `meihua_cast` | 梅花物数、声音、尺寸、字占、端法、报数与已有卦起卦 | Implemented |
| `combine_four_gua` | 统摄四卦组合分析 | Implemented，限定组合规则 |
| `liuyao` | 六爻纳甲与版本化《增删卜易》结构证据 | Implemented |
| `canping` | 邵子参评数 / 金锁银匙（支持 `gu` / `ming` 取数与多种配运法） | Implemented |
| `heluo` | 河洛理数（元堂、卦序、节候与原文对照） | Implemented |
| `suzhan` | 二十七宿占分析 | Implemented |
| `interpret_astrology_dice` | [占星骰](astrodice.md)：十二骰面、七曜星座与喜乐宫符号解读 | Implemented |
| `sanshi_combined_chart` | 太乙、六壬与奇门三式分层证据及位置对应 | Implemented |

### 2.5 `metaphysics` —— 中国术数独立盘（Implemented）

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `ziwei_birth_chart` | [紫微斗数](ziwei.md)本命十二宫、星曜、五行局与四化 | Implemented |
| `ziwei_timing` | 紫微斗数运限（大限/小限/流年/流月/流日/流时与动态四化） | Implemented |
| `ziwei_rules` | 紫微斗数规则查询 helper | Implemented |
| `liuren_chart` | 大六壬天地盘、四课三传、天将与九宗门课名证据 | Implemented |
| `liuren_yearly_timing` | 农历虚岁行年与分析时刻六壬课 | Implemented |
| `qimen` | 奇门遁甲时家转盘（支持置闰/拆补、寄宫与格局证据） | Implemented |
| `taiyi` | 《太乙金镜式经》年/月/日/时/分计及指定历史年计 | Implemented |
| `jinkou` | 金口诀四位、阴阳用位、五动三动、得气与六十四课钤 | Implemented |

### 2.6 `astro` —— 离线核心星盘与关系盘（Implemented，精度依赖星历）

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `astrology_chart` | 离线西占本命盘（可选 `apparent_model="opaque_solar"`；其他流派请直接调用独立工具） | Implemented / Approximate |
| `thirteen_sector_chart` | 上升起点 13 等分扇区盘（自定义规则） | Implemented / Approximate |
| `hellenistic_chart` | 离线希腊风格盘 | Implemented / Approximate |
| `guolao_chart` | 七政四余连续坐标、研究宿界、宫主/度主与规则轨迹 | Implemented（需 Swiss） |
| `vedic_chart` | 印占 Lahiri 本命、分盘（D1–D30）与八分法 | Implemented（需 Swiss） |
| `vimshottari_dasha` | 印占 Moon-nakshatra 出生余运与主次运（`dasha_depth=2..6`） | Implemented（需 Swiss） |
| `hamburg_midpoint_chart` | 德国汉堡 22 因素、253 中点轴与太阳弧派生盘 | Implemented（需 Swiss） |
| `human_design` | [人类图](human-design.md) 88° 双时刻、26 激活、36 通道与类型权威 | Implemented（限定机制） |
| `relationship_chart` | 关系/合盘（`compare`/`composite`/`influence`/`timespace`/`marks`） | Implemented / Approximate |

### 2.7 `western_timing` —— 西占推运（Implemented，依赖 backend）

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `western_timing` | 西占推运综合总览 bundle | Implemented（依赖 backend） |
| `solar_return` | 太阳返照 | Implemented（依赖 backend） |
| `lunar_return` | 月亮返照 | Implemented（依赖 backend） |
| `transit_chart` | 行运盘（含普通与紧密相位分档） | Implemented（依赖 backend） |
| `solar_arc` | 太阳弧 | Implemented（依赖 backend） |
| `chart_for_year` | 指定年盘 | Implemented（依赖 backend） |
| `profection` | 年小限 | Implemented（依赖 backend） |
| `primary_directions` | 主限（公开近似/坐标策略） | Implemented（依赖 backend） |
| `primary_directions_chart` | 主限法盘 | Implemented（依赖 backend） |
| `zodiacal_releasing` | 黄道释放 | Implemented（依赖 backend） |
| `firdaria` | 法达星限（支持夜盘交点顺序与年长模式选择） | Implemented（依赖 backend） |
| `decennials` | 十年星限 | Implemented（依赖 backend） |

### 2.8 `western_event` —— 事件占星（Implemented，依赖 backend）

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `mundane_ingress_chart` | 世俗入宫盘（二分二至） | Implemented（依赖 backend） |
| `planetary_returns` | 多重回归 | Implemented（依赖 backend） |
| `horary_chart` | 卜卦盘与 Lilly 条件证据（不支持生死/健康/妊娠主题） | Implemented（限定规则） |
| `evaluate_election_time` | 择日盘（不支持医疗/手术择时） | Implemented（限定规则） |

### 2.9 `western_lifespan` —— 全生命周期技法（Implemented，依赖 backend）

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `harmonic_chart` | 调波盘 | Implemented（依赖 backend） |
| `planetary_ages` | 行星年龄 | Implemented（依赖 backend） |
| `triplicity_ruler_periods` | 三分主星推运 | Implemented（依赖 backend） |
| `lunar_phase_progressions` | 实际星历八相月相推运 | Implemented（依赖 backend） |
| `bounds_directions` | 界推运（distributions） | Implemented（依赖 backend） |
| `balbillus_periods` | Balbillus 129 年系统 | Implemented（依赖 backend） |
| `numeric_aspect_periods` | 数字相位推运 | Implemented（依赖 backend） |
| `planetary_periods_129_years` | 129 年系统 | Implemented（依赖 backend） |
| `planetary_arc_directions` | 行星弧方向 | Implemented（依赖 backend） |
| `persian_directions` | 波斯向运 | Implemented（依赖 backend） |
| `age_point` | 年龄推进点（age point） | Implemented（依赖 backend） |
| `sidereal_progressions` | 恒星推运 | Implemented（依赖 backend） |
| `declination_progressions` | 赤纬推运 | Implemented（依赖 backend） |

### 2.10 `knowledge` —— 知识库（Implemented）

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `knowledge_catalog` | 列出内置知识域与分类（`astro`、`bazi`、`liureng`、`qimen` 等） | Implemented |
| `knowledge_read` | 读取单条内置知识条目 | Implemented |

### 2.11 `fengshui` —— 家居风水（Implemented）

详情见[家居风水参考](fengshui.md)与[现场咨询指南](interpretation/fengshui/consultation.md)。

| 工具 | 范围 | 状态 |
| --- | --- | --- |
| `fengshui_directions` | 后天八卦／洛书宫数、八方与 24 山兼向/空亡细分，及 WMM2025/IGRF-14 地磁换算候选 | Implemented |
| `fengshui_minggua` | 1864 锚点命卦、原始五数寄宫与个人八方游年关系 | Implemented |
| `fengshui_bazhai` | 坐山宅盘、逐人命盘、门床桌灶位置/朝向检验及阳宅三要（门/主/灶） | Implemented |
| `fengshui_jinsuo` | 金锁玉关八宫（1234 砂 / 6789 水）与 24 山砂水偏好逐项核对 | Implemented（限定来源） |
| `fengshui_annual_stars` | 立春换年年度紫白九宫、二十年元运及太岁/岁破/三煞/五黄/二黑 | Implemented |
| `fengshui_monthly_stars` | 十二节换月中性月紫白，以及传入 `query_at` 时的日紫白与时紫白 | Implemented |
| `fengshui_xuankong_house_chart` | 中州派定运、下卦与 13 山替星、古典格局、正副城门与条件式解读 | Implemented |
| `fengshui_assess` | 八宅/金锁/玄空/年/月/日/时紫白四层叠盘（`palace_overlay`）与跨层布局分析 | Implemented（限定版本） |

### 2.12 `psychometrics` —— 心理测量量表（Implemented）

| 工具 | 范围 | 状态 |
| --- | --- | --- |
| `ipip_big_five` | Goldberg (1992) IPIP 50 题大五人格因子标记量表：条目清单与 1–5 确定性计分 | Implemented |

## 3. 精度与依赖说明

### 3.1 核心占星盘（`astro` family）

| 情形 | 状态 | 说明 |
| --- | --- | --- |
| 本地有 `swisseph` 且加载 `.se1` 数据 | Implemented | 本地星历路径，实际模型由 `chart_profile.ephemeris_model` 标志确定 |
| `swisseph` 可导入但缺 `.se1` 数据 | Implemented / Approximate | 可能使用内置 Moshier 模型，以实际标志为准 |
| 无 `swisseph` | Approximate | 回退至 FateBridge 内置近似轨道模型 |
| 显式 `house_system` 覆盖为非整宫的离线宫制（如 `1..8` / `P` 等） | Implemented（需 `swisseph`） | 缺失运行时时直接报错，不静默降级 |
| `zodiac_type="Sidereal"`（Lahiri） | Implemented | 离线恒星黄道模式 |

### 3.2 关系盘（`relationship_chart`）

支持 `compare`（比较盘）、`composite`（组合盘）、`influence`（影响盘，`synastry` 大小写归一映射至此）、`timespace`（时空中点盘）与 `marks`（派生关系盘）；未识别的 `relative_mode` 返回 `validation_error`。

### 3.3 西占推运 / 事件 / 寿命（`western_*` families）

这三个 family 依赖本地 `swisseph` 运行时，缺失时直接返回 `dependency_missing` 而不回退轨道近似。`primary_directions` / `primary_directions_chart` 会在输出中公开坐标与近似策略。`horary_chart` 与 `evaluate_election_time` 可显式选择 `ut1_source=iers_c04`（覆盖 1962-01-01 至 2026-09-19 UTC）或默认 `swiss_delta_t`。

如果你新增或修改了接口能力，请同步更新本页，确保工具列表与中央目录保持一致。
