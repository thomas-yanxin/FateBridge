# FateBridge 算法与能力覆盖矩阵

本文档列出当前工具、实际实现范围、精度依赖与未覆盖项目。工具名按 MCP 集合统计；输入参数查 [API 参考](api-reference.md)，按用户问题选工具查[场景路由](scenario-routing.md)。

状态分类：

- `Implemented`：仓库内已有实现，可通过中央目录声明的接口访问；不代表所有端均有同名入口，也不代表预测有效性已被验证
- `Approximate`：可用，但算法明确是离线近似、轻量近似或依赖回退路径
- `Placeholder`：合同或模式入口存在，但主输出层仍是占位兼容
- `Excluded`：当前仓库不提供该能力

> 工具的唯一信源是中央目录 `src/fatebridge/services/tool_catalog.py`。REST 公开 **86 个工具**，MCP 公开 **87 个工具**，分为 **13 个 family**。本页按 MCP 集合统计；目录有 88 条记录，CLI 可执行 87 条，差异见 [API 参考](api-reference.md#24-三端能力边界)。下表逐 family 列出全部工具；新增能力时请同步本页（总数、逐 family 数量与完整工具清单由 `tests/test_doc_tool_counts.py` 锁定）。

所有目录记录现有统一的输入/输出 Schema，三端由同一 `ToolSpec` 发布并校验；这属于接口合同覆盖，不提高算法的 `Implemented` / `Approximate` 等级，也不表示全部嵌套专业字段已有完整类型定义。

摘要/筛选发现与 MCP family 配置同样派生自目录，不改变算法等级。annotations 描述环境影响，不承诺数值确定性；投影警告与严格模式见 [API 参考](api-reference.md#25-字段投影与输出体积)。

## 怎样核对一次结果

| 核对项 | 看什么 | 不能据此推出什么 |
| --- | --- | --- |
| 接口成功 | HTTP 状态、MCP `isError`、CLI 退出码与错误包络 | 所有请求层都完整计算 |
| 计算与规则覆盖 | 实际 `status`、`coverage`、缺失项及所选规则 | 未请求方法也已审查，或候选已经确认 |
| 数值与时间精度 | 实际后端 / 星历模型、时间修正、分析时刻及对应限制 | 包可导入就已加载星历，或“非近似”就能预测现实 |
| 可追溯性 | 原输入、`run_metadata`、版本、来源与环境 | 仅凭 run ID 可以恢复历史输入或永久取得结果 |

工具总量和 Schema 完整性是接口证据；具体计算、传统解释及现实建议分别核对。风水还需区分动作可执行与规则审查，见[分层状态](fengshui.md#分层结果与覆盖状态)。

## 1. 总览：13 个 family / 87 个工具

| family | 工具数 | 主题 | 总体状态 |
| --- | --- | --- | --- |
| `bazi` | 11 | 八字命盘 + 九大专项维度 + 综合命理 | Implemented |
| `compatibility` | 2 | 双人配合（八字合婚 / 宿曜相性） | Implemented |
| `timing` | 9 | 大运 / 流年 / 流月 / 流日 / 流时 / 节气 / 农历 | Implemented |
| `divination` | 10 | 梅花、六爻、统摄法、参评数、河洛、宿占、三式合参等 | Implemented |
| `metaphysics` | 8 | 紫微斗数、六壬、奇门、太乙、金口诀 | Implemented |
| `astro` | 7 | 离线核心星盘家族 + 关系/合盘 | Implemented（精度依赖星历） |
| `western_timing` | 1 | 西占推运总览 bundle | Implemented（依赖 backend） |
| `western_timing_tool` | 11 | 独立西占推运技法（返照/行运/主限/法达…） | Implemented（依赖 backend） |
| `western_event` | 4 | 事件占星（世俗/卜卦/择日/多重回归） | Implemented（依赖 backend） |
| `western_lifespan` | 13 | 全生命周期 / 寿命技法（古典+西占） | Implemented（依赖 backend） |
| `knowledge` | 2 | 内置知识库目录与读取 | Implemented |
| `export` | 2 | 导出协议注册表与快照解析 | Implemented |
| `fengshui` | 7 | 公共方位、命卦、八宅、砂水、年星、玄空宅盘、分层合参 | Implemented（明确版本） |
| 仓库内前端 | — | 内置 Web UI | Excluded |
| 存储 / 账户 | — | 数据库、历史记录、用户体系 | Excluded |

## 2. 逐 family 工具清单

### 2.1 `bazi` —— 八字与命理分析（Implemented）

底层由 `fatebridge.core.calendar` / `elements` / `rules` 与 `fatebridge.services.bazi` / `calculation` 提供；九大专项维度的大运、流年缺省由命盘 + 分析日期内部推算，可用 `dayun_pillar` / `liunian_pillar` 覆盖。

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `analyze_destiny` | 综合命理分析（八字 + 喜用 + 格局） | Implemented |
| `bazi_birth` | 离线八字命盘，完整 `snapshot_text` + 可筛选 `snapshot_export` | Implemented |
| `bazi_marriage` | 婚姻：配偶星/宫、婚期信号、婚姻质量 | Implemented |
| `bazi_career` | 事业：事业类型、行业、创业倾向、贵人方位 | Implemented |
| `bazi_wealth` | 财运：正偏财、财库、求财方式/方位、破财风险 | Implemented |
| `bazi_health` | 传统健康文化：体质标签、五行脏腑对应与养护参考；不作疾病判断 | Implemented |
| `bazi_children` | 子女：子女星/宫、缘分、生育时机 | Implemented |
| `bazi_education` | 学业：印星/食伤/官星、学历倾向、文昌、考试时机 | Implemented |
| `bazi_personality` | 性格：日主心性、十神性格、刚柔内外向 | Implemented |
| `bazi_relatives` | 六亲：父母/兄弟姐妹星、六亲宫位、贵人 | Implemented |
| `bazi_romance` | 正缘桃花：桃花咸池、红鸾天喜、异性缘星、正缘时机 | Implemented |

### 2.2 `compatibility` —— 双人配合（Implemented）

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `two_person_compatibility` | 双人配合度分析（八字合婚 / 合作），复用两份个人分析做组合 | Implemented |
| `sukuyo_compatibility` | 宿曜双人相性（三九の秘法，二十七宿） | Implemented |

### 2.3 `timing` —— 时运与历法（Implemented）

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `timing_analysis` | 综合时运（大运/流年/流月等综合影响） | Implemented |
| `dayun_analysis` | 大运分析 | Implemented |
| `liunian_analysis` | 流年分析 | Implemented |
| `liuyue_analysis` | 流月分析 | Implemented |
| `liuri_analysis` | 流日分析 | Implemented |
| `liushi_analysis` | 流时分析 | Implemented |
| `jieqi_timeline_analysis` | 节气时间轴分析 | Implemented |
| `jieqi_year` | 指定年份节气时刻表（calendar helper） | Implemented |
| `nongli_time` | 公历时刻转农历与干支（calendar helper） | Implemented |

> 历法基于本地算法（`fatebridge.core.almanac`），不依赖外部服务。真太阳时修正含经度 + 均时差，统一走 `fatebridge.utils.solar_time`；出生输入构造使用 `fatebridge.utils.birth_input`。

### 2.4 `divination` —— 占卜与本地技法（Implemented）

均为本地离线技法，输出分为双层快照、仅文本和结构化数据，详见 §4。

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `gua_lookup` | 卦象查询（六十四卦义理） | Implemented |
| `gua_meiyi` | 卦义 helper（批量说明） | Implemented |
| `meihua_analysis` | 梅花易数时卦辅助 | Implemented |
| `tongshefa` | 统摄法 / 大衍筮法起卦 | Implemented |
| `sixyao` | 六爻纳甲分析 | Implemented |
| `canping` | 邵子参评数 / 金锁银匙（数算） | Implemented |
| `heluo` | 河洛理数（数算） | Implemented |
| `suzhan` | 宿占分析 | Implemented |
| `otherbu` | 占星骰子 / 其他卜法 | Implemented |
| `sanshiunited` | 三式合参（聚合太乙/六壬/奇门并统一快照导出） | Implemented |

### 2.5 `metaphysics` —— 中国术数独立盘（Implemented）

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `ziwei_birth` | 紫微斗数命盘 | Implemented |
| `ziwei_horoscope` | 紫微斗数运限（大限/小限/流年/流月/流日/流时 + 动态四化） | Implemented |
| `ziwei_rules` | 紫微斗数规则 helper | Implemented |
| `liureng_gods` | 六壬课体与天将 | Implemented |
| `liureng_runyear` | 六壬流年分析 | Implemented |
| `qimen` | 奇门遁甲排盘分析 | Implemented |
| `taiyi` | 太乙神数分析 | Implemented |
| `jinkou` | 金口诀分析 | Implemented |

> 紫微斗数以 iztro 2.5.8 为对齐基线，采用正月初一年界、虚岁自然年递增、本命晚子时算当天、闰月后半月算下月的规则。400 组本命与运限已比较字段一致；流月/流日/流时比较实际落宫索引，不能用历法地支代替。返回的 `branch` 是实际落宫，`palace_ganzhi` 是本命宫干支，`stem` 是该运限四化所用天干；后两者可能不同。童限按命、财帛、疾厄、夫妻、福德、官禄取宫，农历日期或大限超出支持范围时明确报错。

> 六壬取传按九宗门，第一课生克用日干五行、寄宫只定位；贵人顺逆按贵人实际落地盘的位置判断（巳至戌逆布）。已与独立 daliurenpython 的 8,640 种日干支/时支/月将组合对照，三传全部一致。初轮 kinliuren 参考软件的部分三传存在不稳定与异常，不能把与该软件的所有差异一律判为 FateBridge 错误。固定参考来源与 720 张独立天地盘保存在[三传基准](../tests/fixtures/liureng_transmissions_reference.json)，[全组合回归](../tests/test_third_party_correctness_fixes.py)遍历每张盘的 12 个时支位置。此对照限于三传，不包含所有神煞、课体解释、流派差异或金口诀的完整独立认证。

### 2.6 `astro` —— 离线核心星盘与关系盘（Implemented，精度依赖星历）

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `astro_chart` | 离线核心星盘（`chart_variant` 切换盘式） | Implemented / Approximate（见 §3.1） |
| `astro_chart13` | 离线 13 扇区扩展盘 | Implemented / Approximate |
| `astro_hellen_chart` | 离线希腊盘 | Implemented / Approximate |
| `astro_guolao_chart` | 离线果老星宗 / 七政四余盘 | Implemented / Approximate |
| `astro_india_chart` | 离线印度 sidereal 盘 | Implemented / Approximate |
| `astro_germany_chart` | 离线德国中点盘（派生盘） | Implemented / Approximate |
| `astro_relative_chart` | 离线关系/合盘（`compare`/`composite`/`influence`/`timespace`/`marks`） | Implemented / Approximate |

### 2.7 `western_timing` + `western_timing_tool` —— 西占推运（Implemented，依赖 backend）

走 `fatebridge.core.predictive.*`；缺 `kerykeion` / Swiss Ephemeris 时**直接报错，不降级**（见 §3.3）。

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `western_timing_analysis` | 西占推运综合总览 bundle | Implemented（依赖 backend） |
| `solarreturn` | 太阳返照 | Implemented（依赖 backend） |
| `lunarreturn` | 月亮返照 | Implemented（依赖 backend） |
| `transit` | 行运盘 | Implemented（依赖 backend） |
| `solararc` | 太阳弧 | Implemented（依赖 backend） |
| `givenyear` | 指定年盘 | Implemented（依赖 backend） |
| `profection` | 年小限 | Implemented（依赖 backend） |
| `pd` | 主限（primary directions） | Implemented（公开近似/坐标策略，见 §3.3） |
| `pdchart` | 主限法盘 | Implemented（含 coordinate / approximation 元数据） |
| `zr` | 黄道释放（zodiacal releasing） | Implemented（依赖 backend） |
| `firdaria` | 法达星限 | Implemented（依赖 backend） |
| `decennials` | 十年星限 | Implemented（依赖 backend） |

### 2.8 `western_event` —— 事件占星（Implemented，依赖 backend）

求解天文时刻后起盘的一组事件类工具，走 `fatebridge.core.astrology_events` / `astrology_horary` / `astrology_election`。

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `astro_mundane` | 世俗入宫盘 | Implemented（依赖 backend） |
| `astro_extrareturns` | 多重回归 | Implemented（依赖 backend） |
| `astro_horary` | 卜卦判断 | Implemented（依赖 backend） |
| `astro_election` | 择日 | Implemented（依赖 backend） |

### 2.9 `western_lifespan` —— 全生命周期 / 寿命技法（Implemented，依赖 backend）

读取单张本命盘的一组全生命周期技法，走 `fatebridge.core.astrology_lifespan`。

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `astro_harmonic` | 调波盘 | Implemented（依赖 backend） |
| `astro_planetary_ages` | 行星年龄 | Implemented（依赖 backend） |
| `astro_triplicity_rulers` | 三分主星推运 | Implemented（依赖 backend） |
| `astro_lunation_phase` | 月相推运 | Implemented（依赖 backend） |
| `astro_distributions` | 界推运（distributions） | Implemented（依赖 backend） |
| `astro_balbillus` | Balbillus 129 年系统 | Implemented（依赖 backend） |
| `astro_keypoints` | 数字相位推运 | Implemented（依赖 backend） |
| `astro_yearsystem129` | 129 年系统 | Implemented（依赖 backend） |
| `astro_planetaryarc` | 行星弧方向 | Implemented（依赖 backend） |
| `astro_persiandirected` | 波斯向运 | Implemented（依赖 backend） |
| `astro_agepoint` | 年龄推进点（age point） | Implemented（依赖 backend） |
| `astro_vedicprog` | 恒星推运 | Implemented（依赖 backend） |
| `astro_jaynesprog` | 赤纬推运 | Implemented（依赖 backend） |

### 2.10 `knowledge` + `export` —— 知识库与导出（Implemented）

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `knowledge_registry` | 列出内置知识域与分类 | Implemented |
| `knowledge_read` | 读取单条内置知识并支持导出裁剪 | Implemented |
| `export_registry` | 返回 FateBridge 导出协议注册表 | Implemented |
| `export_parse` | 将快照文本解析为可筛选的结构化 section | Implemented |

> 内置知识域：`astro`、`bazi`、`liureng`、`qimen`。`bazi` 域含十神（10）、神煞（12）、格局（10）、五行（5）、财运（8）、健康（8）、子女（4）、学业（6）、性格（3）、六亲（3）、正缘桃花（3）等条目。

### 2.11 `fengshui` —— 家居风水（Implemented）

| 工具 | 范围 | 状态 |
| --- | --- | --- |
| `fengshui_directions` | 后天方位／洛书宫数、八方与24山角区索引 | Implemented |
| `fengshui_minggua` | 1864锚点命卦、原始五数寄宫、个人八方关系 | Implemented |
| `fengshui_bazhai` | 坐山宅盘、逐人命盘、位置／朝向用途分开 | Implemented |
| `fengshui_jinsuo` | 八宫固定砂水偏好、已确认特征逐项判定 | Implemented（传本来源限制明确登记） |
| `fengshui_annual_stars` | 年度紫白九宫、立春区间、当前元运 | Implemented（交节时刻依赖现有节气引擎，可能近似回退） |
| `fengshui_xuankong_natal` | 中州派历史定运、24山／三元龙、五黄、下卦与兼向替星 | Implemented（xuankong_zhongzhou_v1） |
| `fengshui_assess` | 多层布局关联、匹配方位、现代作者室内形态、条件式元素/年度方案、分歧与版本 | Implemented（限已登记规则版本） |

布局入口设 `analyze_layout=true`。扩展覆盖包括场景选法与优先审查状态、家庭人物及楼层上下文、12 类明确室内关系、独立材质／器形事实、家具候选比较，以及显式启用的玄空有限解释；只按已确认事实与登记版本计算。照片候选、缺失资料、未覆盖规则和动作可行性分别保留，`complete` 不等于所有方法均已审查或可立即执行。输入与来源详见 [风水专题导航](README.md#风水专题)。

所有工具三端可调用；复杂 CLI 请求用 `--request-file`。固定宫数、年度星数、八宅星和紫白星分开；三法没有统一分数。24山方向索引不代表已经支持24山风水论断。月飞星、金锁形态距离／元运与自动户型几何均 Excluded，输出明确列入 `unavailable_layers`。

验证包括固定第三方命卦400项／关系64项、独立2026年星盘和跨端合同，不代表现实预测有效性。来源、算法和输入合同见 [家居风水](fengshui.md)。

第二阶段的运／山／向宅盘与年星分层；版本选择、7套公开完整盘例及固定外部216盘比对的24项五黄差异见 [玄空宅盘](fengshui-xuankong.md)。

## 3. 精度与依赖说明

### 3.1 核心占星盘（`astro` family）

| 情形 | 状态 | 说明 |
| --- | --- | --- |
| 本地有 `swisseph` 且加载相应星历数据 | Implemented | 本地星历路径，实际模型由返回标志确定 |
| `swisseph` 可导入，但缺相应 `.se1` 数据 | Implemented / Approximate | 可能使用内置 Moshier 模型，不能仅凭包可导入或 `engine_backend` 判断数据精度 |
| 无 `swisseph` | Approximate | 回退到 FateBridge 内置近似轨道模型 |
| 显式 `hsys` 覆盖为 `1..8` 的离线宫制 | Implemented（但依赖 `swisseph`） | 缺失时**直接报错**，不静默退化为整宫制 |
| `zodiacal=1` sidereal(Lahiri-like) | Implemented | 离线 sidereal 模式，非联网服务 |

检查 `chart_profile.engine_precision` / `engine_backend` 确认代码路径，再用 `chart_profile.ephemeris_model` 确认实际模型：`swieph` / `jpl` 为相应数据模型，`moshier` 为内置模型，`mixed` 表示混合。`run_metadata.engine_is_approximate` 会标记已识别的降级。数据获取、路径与版本复现见 [快速入门](getting-started.md#星历数据与精度)。

`pyswisseph` 与 `kerykeion` 都是 `pyproject.toml` 的常规安装依赖。“缺依赖回退”描述的是异常/裁剪环境的能力边界，不是另一种官方安装模式。

### 3.2 关系盘（`astro_relative_chart`）

| 模式 | 状态 | 说明 |
| --- | --- | --- |
| `compare` | Implemented | 方向相位层为主 |
| `composite` | Implemented | 组合盘主层 |
| `influence` | Implemented | 影响盘双向主层 |
| `timespace` | Implemented | 时空中点盘（Davison）主层 |
| `marks` | Implemented | 派生关系主层 |
| 未识别的 `relative_mode` | Excluded | 返回 `validation_error`，不把非法 mode 当作受支持能力 |

兼容性提醒：

- `relative_mode="Synastry"` / `"synastry"` 按现代语义收敛到 `influence`
- 关系盘统一使用 `relative_mode`：`compare` 为比较盘，`synastry` / `influence` 为影响盘；旧字段 `relationship_mode` 已移除
- 两条语义不同，迁移旧调用时应显式区分

### 3.3 西占推运 / 事件 / 寿命（`western_*` families）

- 这四个 family 明确依赖 `kerykeion` / Swiss Ephemeris 运行时
- `ensure_predictive_backend_available()` 会在缺依赖时抛错（`dependency_missing`）
- 与核心 chart 不同，缺 backend 时不会使用 FateBridge 内置轨道近似；但这不保证所有 backend 都加载了相同星历数据，仍需检查返回的精度/模型字段
- `pd` / `pdchart` 虽已实装，但内部会公开其近似/坐标策略（time key、direct/converse、相位列表等），不应被误读为单一路径高精度结果

## 4. 快照协议覆盖

快照双层结构不是所有工具的通用保证。当前典型成功响应按以下形态组织；工具输入是否支持 `selected_sections` 另查 [API 参考](api-reference.md#23-selected_sections)。

| 形态 | 工具范围 | 读取方式 |
| --- | --- | --- |
| `snapshot_text` + `snapshot_export` | 八字独立盘/专项/综合分析、双人配合、全部时运与历法、卦义查询、三式合参、中国术数独立盘、knowledge、核心/关系星盘（中点盘除外）、独立西占推运、七个风水工具 | 业务数据为准，快照辅助阅读；支持选择的模型才裁剪导出 |
| `snapshot_text`，无 `snapshot_export` | `tongshefa`、`sixyao`、`canping`、`heluo`、`suzhan`、`otherbu`、西占事件与生命周期工具 | 读取文本与结构化业务数据；需要 section 解析时另调用 `export_parse` |
| 结构化数据，无双层快照 | `meihua_analysis`、`astro_germany_chart`、`western_timing_analysis`、`export_registry`、`export_parse` | 读取各自的业务字段；`export_parse` 直接返回解析结果，不再嵌套 `snapshot_export` |

使用建议：

- 存在的 `snapshot_text` 适合直接阅读；日志中的出生资料需按实际用途管理。
- `snapshot_export.export_text` 是可消费的导出层，不等于所有工具都支持筛选输入。
- `section_titles_detected` / `missing_selected_sections` 用于调试标题；`export_parse` 的这些字段位于响应根。
- `selected_sections` 不删除完整快照或业务数据。整体精简使用 `fields` 与 `include_snapshot_text`。

## 5. 这页不包含什么

算法正确性按历法、规则与数值对象分别核对；第三方一致率只适用于固定版本、约定与已比较的样本，不是项目整体的“准确率”。黄金快照锁定回归输出，不能证明现实预测有效性。性能数据也须注明环境、输入、冷/热启动、星历路径及计时范围；引擎计算耗时与模型选工具、MCP 宿主准备、网络往返分开报告。对话测量方法见 [Codex 使用指南](codex-guide.md#可复现体验)。

以下内容不应从本页推断：

- 不是所有能力都保证“天文级精度”（见 §3）
- 不是所有实现都意味着“无需本地依赖”（`western_*` 需要 backend）
- 关系盘模式有明确语义，迁移时须核对 `relative_mode`（见 §3.2）

如果你准备修改接口或新增能力，请同步更新本页，确保“文档状态”仍然是从代码反推出来的结果，而不是愿景描述。
