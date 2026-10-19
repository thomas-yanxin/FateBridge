# FateBridge 场景路由矩阵

机器入口为 `/api/scenarios`、CLI `scenarios` 与 MCP `fatebridge://scenarios`。维护源为本矩阵与 `skills/onda-*/agents/interface.yaml`；现有九个主题、三个服务、一个全面画像组合入口，加独立 `fengshui` 基础计算场景，共14项。机器发现包含 consultation.kind/topics、当轮范围与共享安全／时间策略。它是发现指引，不是自动执行计划。

## 如何使用本页

用户咨询先选择最贴近当前问题的[技能入口](../skills/README.md)，再看下方对应场景；维护工具覆盖时查[覆盖核对清单](#覆盖核对清单)。已有实际 Schema 且工具已公开时可直接调用，不必先遍历矩阵。

[调用纪律](#全局调用纪律) · [主旁深的含义](#交叉印证与去重) · [场景矩阵](#场景路由矩阵) · [长尾工具](#长尾与专家级工具) · [覆盖清单](#覆盖核对清单)

## 全局调用纪律

1. 先应用[咨询硬边界](../skills/_shared/safety-boundaries.md)，禁区请求不排盘、不起卦、不先算后免责声明。公共接口禁用生死／临床卜卦与手术择时，健康输出限传统分类；语义判断仍由咨询方负责。
2. 按[用户问题与范围](../skills/_shared/consultation-routing.md)识别主题、对象、任务、时间和深度。当前问什么就回答什么；首轮明确全面则覆盖，追问保留原主题与已有相关视角，只补新增范围。
3. 命盘与专项已有层复用。八字综合已含命盘、喜用与格局，不重复原始盘；专项已含时机背景，不默认补大运流年。时间问题统一读[共享时间选择](../skills/_shared/timing-selection.md)。法达、大运与紫微运限均是普通阶段问题的正常候选。
4. 多层确有价值才聚合，窄查询可单技法。后台多工具不等于正文多报告，不为凑数增工具或索取其他体系资料。
5. 普通首轮使用已验证 fields、strict_fields=true、include_snapshot_text=false；完整 JSON／全部时间线／文件首次 fields=null，保留默认预算并读同 run 交付。selected_sections 只裁剪导出文本。未知生时不填默认，不重复追问用户已说无法提供的缺项。

## 交叉印证与去重

按结构、双方互动、阶段、目标年份／时段与候选时刻分别选依据，不按主题永久设唯一主体系。专题综合主动评估相关多视角，通常两套可解释依据即可；单项、已有结果和限定方法可以一套。第三套及额外技法须补尚未回答的问题或独立层。

- 主：当前任务分支入口；同一行多个主依职责／方法选择，不默认全调用。
- 旁：有新增解释价值的相关视角，并非永久低于主体系。
- 深：当前范围确需更细节时使用，不把法达等阶段能力全藏入专家模式。

这些角色是选择指引，不是统计预测证据。相同描述合并且署明来源；冲突先查时钟、地点、太阳时和模型，再分别保留，不投票、不合成成功概率。重复同一规则不是独立支持；不同时间范围不直接互证。

## 场景路由矩阵

每行是用户任务，列为候选工具组。一个组内按具体方法／职责选择；工具清单不要求逐个执行。具体字段、精度和来源以实际工具及技能参考为准。

### 认识自己与个人发展（onda-mingge）

| 用户任务 | `analyze_destiny` `bazi_personality` | `ziwei_birth` | `astro_chart` | `timing_analysis` `ziwei_horoscope` `western_timing_analysis` `firdaria` | `bazi_birth` `ziwei_rules` `canping` `heluo` |
| --- | --- | --- | --- | --- | --- |
| 特点／天赋综合 | 主（结构与专项按需） | 旁（相关宫位） | 旁（相关配置） |  |  |
| 阶段中的自我变化 | 旁（已有结构） | 旁（已有结构） | 旁（已有结构） | 主（按时间任务选层） |  |
| 指定原始盘／数算 |  |  |  |  | 主（按用户方法选择） |

详细选择与读法见 [认识自己与个人发展](../skills/onda-mingge/SKILL.md)。
本入口可用清单（非必调）：`analyze_destiny`、`astro_chart`、`bazi_birth`、`bazi_personality`、`canping`、`firdaria`、`heluo`、`timing_analysis`、`western_timing_analysis`、`ziwei_birth`、`ziwei_horoscope`、`ziwei_rules`。

### 事业与工作（onda-shiye）

| 用户任务 | `bazi_career` `analyze_destiny` | `ziwei_birth` | `astro_chart` | `timing_analysis` `ziwei_horoscope` `western_timing_analysis` `firdaria` | `astro_election` |
| --- | --- | --- | --- | --- | --- |
| 工作方向／岗位／创业角色 | 主（专项优先，整体结构按需） | 旁（相关职业结构） | 旁（相关职业配置） |  |  |
| 今年／未来几年事业 | 主（复用已有时机） | 旁（已有结构） | 旁（已有结构） | 主（仅补所需时间层） |  |
| 给定求职／签约候选时刻 |  |  |  | 旁（独立背景） | 主（给定候选，非区间最优搜索） |

详细选择与读法见 [事业与工作](../skills/onda-shiye/SKILL.md)。
本入口可用清单（非必调）：`analyze_destiny`、`astro_chart`、`astro_election`、`bazi_career`、`firdaria`、`timing_analysis`、`western_timing_analysis`、`ziwei_birth`、`ziwei_horoscope`。

### 财务与资源（onda-caiwu）

| 用户任务 | `bazi_wealth` | `ziwei_birth` | `astro_chart` | `timing_analysis` `ziwei_horoscope` `western_timing_analysis` `firdaria` |
| --- | --- | --- | --- | --- |
| 收入／支出／积累方式 | 主 | 旁（相关宫位） | 旁（相关配置） |  |
| 今年／未来几年财务 | 主（已有时机复用） | 旁 | 旁 | 主（按阶段和目标范围选择） |

详细选择与读法见 [财务与资源](../skills/onda-caiwu/SKILL.md)。
本入口可用清单（非必调）：`astro_chart`、`bazi_wealth`、`firdaria`、`timing_analysis`、`western_timing_analysis`、`ziwei_birth`、`ziwei_horoscope`。

### 感情与伴侣关系（onda-yuanfen）

| 用户任务 | `bazi_marriage` `bazi_romance` | `two_person_compatibility` `sukuyo_compatibility` | `ziwei_birth` | `astro_chart` `astro_relative_chart` | `timing_analysis` `ziwei_horoscope` `western_timing_analysis` `firdaria` `liuyue_analysis` |
| --- | --- | --- | --- | --- | --- |
| 单人相处方式／婚恋文化 | 主（按婚姻或桃花任务） |  | 旁 | 旁（本命相关配置） |  |
| 双方互动综合 |  | 主（跨盘、双向范围） | 旁（各自结构） | 主（明确星盘互动） |  |
| 年度／阶段／月份变化 | 主（已有时机复用） |  |  |  | 主（仅补所需粒度） |

详细选择与读法见 [感情与伴侣关系](../skills/onda-yuanfen/SKILL.md)。
本入口可用清单（非必调）：`astro_chart`、`astro_relative_chart`、`bazi_marriage`、`bazi_romance`、`firdaria`、`liunian_analysis`、`liuyue_analysis`、`meihua_analysis`、`sixyao`、`sukuyo_compatibility`、`timing_analysis`、`two_person_compatibility`、`western_timing_analysis`、`ziwei_birth`、`ziwei_horoscope`。

### 学习与成长（onda-xueye）

| 用户任务 | `bazi_education` | `ziwei_birth` | `astro_chart` | `timing_analysis` `ziwei_horoscope` `western_timing_analysis` `firdaria` |
| --- | --- | --- | --- | --- |
| 学习方式／深造选项 | 主 | 旁（相关结构） | 旁（相关配置） |  |
| 考试年份／阶段比较 | 主（已有时机复用） | 旁 | 旁 | 主（同粒度，非录取承诺） |

详细选择与读法见 [学习与成长](../skills/onda-xueye/SKILL.md)。
本入口可用清单（非必调）：`astro_chart`、`bazi_education`、`firdaria`、`timing_analysis`、`western_timing_analysis`、`ziwei_birth`、`ziwei_horoscope`。

### 家庭与亲子（onda-jiating）

| 用户任务 | `bazi_relatives` `bazi_children` | `analyze_destiny` `bazi_personality` | `ziwei_birth` `astro_chart` | `two_person_compatibility` `astro_relative_chart` | `timing_analysis` `ziwei_horoscope` `western_timing_analysis` `firdaria` |
| --- | --- | --- | --- | --- | --- |
| 命主六亲／子女对应 | 主（命主资料） |  | 旁（命主结构） |  |  |
| 孩子／家人本人特点 |  | 主（该人资料） | 旁（该人资料） |  |  |
| 亲子／家人双方互动 |  |  |  | 主（双方资料与实际关系） |  |
| 家庭阶段与责任 | 旁（已有结构） |  | 旁 |  | 主（只限问题所需时段） |

详细选择与读法见 [家庭与亲子](../skills/onda-jiating/SKILL.md)。
本入口可用清单（非必调）：`analyze_destiny`、`astro_chart`、`astro_relative_chart`、`bazi_children`、`bazi_personality`、`bazi_relatives`、`firdaria`、`timing_analysis`、`two_person_compatibility`、`western_timing_analysis`、`ziwei_birth`、`ziwei_horoscope`。

### 人际与合作（onda-renji）

| 用户任务 | `analyze_destiny` `ziwei_birth` `astro_chart` | `two_person_compatibility` `astro_relative_chart` `sukuyo_compatibility` | `timing_analysis` `ziwei_horoscope` `western_timing_analysis` `firdaria` |
| --- | --- | --- | --- |
| 个人交往方式／支持资源 | 主（相关结构） |  |  |
| 朋友／合伙双方互动 | 旁（各自结构） | 主（按实际关系） |  |
| 合作阶段／年度变化 | 旁（已有结构） | 旁（已有互动） | 主（不推对方行为） |

详细选择与读法见 [人际与合作](../skills/onda-renji/SKILL.md)。
本入口可用清单（非必调）：`analyze_destiny`、`astro_chart`、`astro_relative_chart`、`firdaria`、`sukuyo_compatibility`、`timing_analysis`、`two_person_compatibility`、`western_timing_analysis`、`ziwei_birth`、`ziwei_horoscope`。

### 传统身心文化参考（onda-jiankang）

| 用户任务 | `bazi_health` | `analyze_destiny` | `timing_analysis` |
| --- | --- | --- | --- |
| 五行标签／传统对应 | 主（非体质诊断） | 旁（仅未覆盖背景） |  |
| 文化关系的阶段变化 | 主（已有时机复用） |  | 旁（未覆盖的传统时间层） |

详细选择与读法见 [传统身心文化参考](../skills/onda-jiankang/SKILL.md)。
本入口可用清单（非必调）：`analyze_destiny`、`bazi_health`、`timing_analysis`。

### 整体时运与阶段（onda-shiyun）

| 用户任务 | `timing_analysis` `dayun_analysis` | `ziwei_horoscope` | `western_timing_analysis` `firdaria` `zr` `decennials` | `liunian_analysis` `liuyue_analysis` `liuri_analysis` `liushi_analysis` | `solarreturn` `lunarreturn` `transit` `solararc` `givenyear` `profection` `pd` `pdchart` | `astro_election` |
| --- | --- | --- | --- | --- | --- | --- |
| 整体年度／未来几年 | 主（中式选择） | 主（紫微选择） | 主（西占选择） |  |  |  |
| 人生阶段／何时换阶段 | 主（大运与精度） | 主（大限） | 主（法达等实际分期） |  | 深（本轮确需） |  |
| 月份／某日／时点 | 旁（已有背景） | 主（相应运限） | 旁（已有阶段） | 主（所需粒度） | 主（西占相关单技法） |  |
| 活动候选时刻比较 |  |  |  |  |  | 主（给定非医疗候选） |

详细选择与读法见 [整体时运与阶段](../skills/onda-shiyun/SKILL.md)。其他生命周期／历法方法按共享时间参考与技法参考选择，不自动全调用。
本入口可用清单（非必调）：`astro_agepoint`、`astro_balbillus`、`astro_distributions`、`astro_election`、`astro_extrareturns`、`astro_harmonic`、`astro_jaynesprog`、`astro_keypoints`、`astro_lunation_phase`、`astro_mundane`、`astro_persiandirected`、`astro_planetary_ages`、`astro_planetaryarc`、`astro_triplicity_rulers`、`astro_vedicprog`、`astro_yearsystem129`、`dayun_analysis`、`decennials`、`firdaria`、`givenyear`、`jieqi_timeline_analysis`、`jieqi_year`、`liunian_analysis`、`liuri_analysis`、`liushi_analysis`、`liuyue_analysis`、`lunarreturn`、`nongli_time`、`pd`、`pdchart`、`profection`、`solararc`、`solarreturn`、`timing_analysis`、`transit`、`western_timing_analysis`、`ziwei_horoscope`、`zr`。

### 命盘与指定方法解读（onda-xingpan）

| 用户任务 | `bazi_birth` `analyze_destiny` | `ziwei_birth` `ziwei_horoscope` | `astro_chart` `astro_chart13` `astro_hellen_chart` `astro_guolao_chart` `astro_india_chart` `astro_germany_chart` | `astro_relative_chart` | `western_timing_analysis` `firdaria` `dayun_analysis` `liunian_analysis` |
| --- | --- | --- | --- | --- | --- |
| 指定八字／紫微命盘 | 主（原始或综合） | 主（本命或动态） |  |  |  |
| 西占本命／指定流派 |  |  | 主（择一，不重复） |  |  |
| 指定星盘关系盘 |  |  |  | 主（明确盘型） |  |
| 指定阶段方法／法达 |  |  |  |  | 主（按用户所选窄查询） |

详细选择与读法见 [命盘与指定方法解读](../skills/onda-xingpan/SKILL.md)。
本入口可用清单（非必调）：`analyze_destiny`、`astro_chart`、`astro_chart13`、`astro_germany_chart`、`astro_guolao_chart`、`astro_hellen_chart`、`astro_india_chart`、`astro_relative_chart`、`bazi_birth`、`dayun_analysis`、`firdaria`、`liunian_analysis`、`western_timing_analysis`、`ziwei_birth`、`ziwei_horoscope`。

### 具体问事与占卜（onda-zhanbu）

| 用户任务 | `meihua_analysis` `sixyao` | `qimen` `liureng_gods` `liureng_runyear` `jinkou` | `taiyi` `suzhan` `sanshiunited` `otherbu` `tongshefa` | `astro_horary` | `gua_lookup` `gua_meiyi` |
| --- | --- | --- | --- | --- | --- |
| 明确求卦／已选卜法 | 主（按所选方式） | 主（按所选方式） | 主（按所选方式与实际输入） | 主（非禁区类别） | 旁（只查义，不重起） |

详细选择与读法见 [具体问事与占卜](../skills/onda-zhanbu/SKILL.md)。
本入口可用清单（非必调）：`astro_horary`、`gua_lookup`、`gua_meiyi`、`jinkou`、`liureng_gods`、`liureng_runyear`、`meihua_analysis`、`otherbu`、`qimen`、`sanshiunited`、`sixyao`、`suzhan`、`taiyi`、`tongshefa`。

### 全面画像多主题组合（onda-zige）

| 用户任务 | `analyze_destiny` | `ziwei_birth` | `astro_chart` |
| --- | --- | --- | --- |
| 多主题全面画像 | 主（按范围） | 主（按范围） | 主（按范围） |
| 明确三体系完整画像 | 主（已有则复用） | 主（缺失保留） | 主（缺失保留） |

详细选择与读法见 [全面画像多主题组合](../skills/onda-zige/SKILL.md)。这是多主题组合入口；单主题多体系仍由对应主题主持，深入追问保留已有视角。
本入口可用清单（非必调）：`analyze_destiny`、`astro_chart`、`ziwei_birth`。

### 风水 · 空间布局（onda-fengshui）

| 用户问题 | `fengshui_assess` | `fengshui_minggua` | `fengshui_bazhai` | `fengshui_directions` | `fengshui_jinsuo` | `fengshui_annual_stars` | `fengshui_xuankong_natal` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 布局审查及行动方案 | 主（scene=workstation/home按事实选层，显式methods优先；analyze_layout=true） | | | | | | |
| 多方案布局比较与家具搬转限制 | 主（layout_constraints保存许可；layout_alternatives独立观察与可行性，逐规则比较） | | | | | | |
| 独立室内形态 | 主（form_observations，methods=[]） | | | | | | |
| 书桌工作／学习玄空用途、入口隔挡、材料施用条件 | 主（显式工位作者版本；用途按落宫取向星，物件资格不推摆位） | | | | | | |
| 桌面物件风水摆法 | 主（BTB 须明确另选；非 BTB 桌面摆放仅作者参考） | | | | | | |
| 个人命卦八方 | | 主（三选一生年路径） | | | | | |
| 单层八宅关系 | | | 主（宅与人、位置与朝向分开） | | | | |
| 参考北与固定宫数 | | | | 主（不推断进阶吉凶） | | | |
| 已确认砂水关系 | | | | | 主（分类及依据） | | |
| 某年九宫年星 | | | | | | 主（立春边界） | |
| 历史玄空宅盘 | | | | | | | 主（磁北宅向及历史定运依据） |

技能入口与资料／来源／执行闭环见 [onda-fengshui](../skills/onda-fengshui/SKILL.md)。不为形态或桌面咨询强制收集生辰；聚合已算的层不重复计算。

### 家居风水基础计算

| 用户意图 | 主调用 | 输入与输出纪律 |
| --- | --- | --- |
| 方位／固定宫数 | `fengshui_directions` | 明确参考北；24山只提供角区索引，不能推断进阶论断 |
| 命卦／个人八方 | `fengshui_minggua` | 公历生日、有效生年或出生时刻三选一；非立春当日不强制出生小时；未知起算法保留候选 |
| 布局是否要改／如何调整／元素关系 | `fengshui_assess` | scene=workstation/home按事实选层，显式methods优先；analyze_layout=true；门床桌灶统一计算，位置/朝向可分别提供；落宫关联年盘/宅盘，候选方向与具体摆件效力分开 |
| 室内形态／背门／背靠／条件式物件方案 | `fengshui_assess` | form_observations 可 methods=[] 独立算；物件目标绑定已算作用域，年度作者规则限2026；照片待确认，不造距离阈值，不合并流派 |
| 桌面物件／固定桌面下的作者方案 | `fengshui_assess` | surface_layouts显式选desktop_bagua_btb_v1，矩形/坐者近沿/事业或丰盛目标；surface_constraints单独保存许可与可行区域，远左不当东南；无规则物件不编吉侧 |
| 宅卦与各住户布局 | `fengshui_bazhai` | 宅坐山与住户分开；位置和朝向分别提供，禁止户主覆盖全家 |
| 金锁基础砂水 | `fengshui_jinsuo` | 使用已确认分类与依据；标签不自动决定砂水 |
| 某年九宫年星 | `fengshui_annual_stars` | 立春换年；固定宫数与年星数分开，不能冒充完整山向宅盘 |
| 历史玄空宅盘 | `fengshui_xuankong_natal` | 必须确认磁北宅向和历史定运依据；中州派版本，山界候选不裁成唯一盘，年星独立 |
| 三法合参 | `fengshui_assess` | 聚合调用保留三层与差异，不平均评分；缺失资料明确 partial |
| 工位/家居多方案与动作限制 | `fengshui_assess` | layout_constraints记录搬位/转向/新增许可；layout_alternatives独立重算新位置事实；ready仅指所选门槛满足，不评分、不选综合赢家 |

完整输入与 [规则范围](fengshui.md) 优先于解释。不能从户型图片猜测参考北、宅向、立极或砂水，也不能从缺失值生成确定吉凶。基础层结果只覆盖本版本规则；完整运山向宅盘须显式调用已定版本的玄空工具，不推断其他门派或金锁进阶断语。Onda 个人命理场景不自动加入住宅工具；空间咨询由独立 onda-fengshui 技能组织，原 fengshui 基础计算场景仍保留。

## 长尾与专家级工具

这些工具按其真实能力和当前问题选择，通常不在普通首轮全部调用：

| 工具 | 何时触发 |
|---|---|
| `astro_harmonic` `astro_planetary_ages` `astro_triplicity_rulers` `astro_lunation_phase` `astro_distributions` `astro_balbillus` `astro_keypoints` `astro_yearsystem129` `astro_planetaryarc` `astro_persiandirected` `astro_agepoint` `astro_vedicprog` `astro_jaynesprog` | 用户的问题确需相应生命周期／分阶段方法，或明确指定时；按新增价值选择，不默认全调用。法达等常规阶段方法已在时运主体路由。 |
| `astro_mundane` `astro_extrareturns` | 世俗盘用于明确的世运方法请求；多重回归用于相关个人周期请求，按实际输出解释。 |
| `taiyi` | 大势/国运级判断（个人问事默认用六爻/梅花/奇门）。 |
| `sanshiunited` | 仅用户明确选择三式合参时；普通重大决定不自动起三式。 |

## 支撑与元工具

这些工具不进入场景路由，只在解读或工程层面提供支撑：

| 工具 | 用途 |
|---|---|
| `gua_lookup` `gua_meiyi` | 查 64 卦义理（单卦 / 批量），为占卜类提供卦义支撑，非独立起卦。 |
| `jieqi_year` `jieqi_timeline_analysis` `nongli_time` | 节气表 / 节气时间轴 / 公历农历换算，历法支撑。 |
| `knowledge_registry` `knowledge_read` | 内置知识域目录与读取，解读查证用。 |
| `export_registry` `export_parse` | 导出协议注册表 / 快照文本解析，工程支撑。 |

## 覆盖核对清单

以下工具集合必须恰好等于 `tool_catalog.CATALOG` 全集（由 `tests/test_scenario_routing_coverage.py` 在 CI 锁定）。新增工具若未在此登记，CI 失败。格式：`- tool_key — 归属`。

- `analyze_destiny` — 命格综合主证
- `bazi_birth` — 核心命盘
- `bazi_personality` — 命格
- `bazi_education` — 学习
- `bazi_children` — 家庭亲子
- `bazi_relatives` — 家庭六亲
- `bazi_career` — 事业
- `bazi_wealth` — 财务
- `bazi_marriage` — 缘分
- `bazi_romance` — 缘分
- `bazi_health` — 健康
- `ziwei_birth` — 紫微主证
- `ziwei_horoscope` — 时运（紫微运限）
- `ziwei_rules` — 命格查表（深）
- `qimen` — 问事
- `taiyi` — 问事 / 大势国运
- `jinkou` — 问事（即时简断）
- `liureng_gods` — 问事
- `liureng_runyear` — 问事（流年）
- `astro_chart` — 星盘主证
- `astro_chart13` — 星盘（13 扇区扩展）
- `astro_hellen` — 星盘（希腊流派）
- `astro_guolao` — 星盘（果老流派）
- `astro_india` — 星盘（印度流派）
- `astro_germany` — 星盘（德国盘）
- `astro_relative` — 关系盘（REST 端）
- `astro_relative_chart` — 关系盘（MCP 端）
- `western_timing_analysis` — 时运聚合主证
- `solarreturn` — 时运单技法
- `lunarreturn` — 时运单技法
- `transit` — 时运单技法
- `solararc` — 时运单技法
- `givenyear` — 时运单技法
- `profection` — 时运单技法
- `pd` — 时运单技法
- `pdchart` — 时运单技法
- `zr` — 时运单技法
- `firdaria` — 时运单技法（法达）
- `decennials` — 时运单技法
- `astro_harmonic` — 全生命周期
- `astro_planetary_ages` — 全生命周期
- `astro_triplicity_rulers` — 全生命周期
- `astro_lunation_phase` — 全生命周期
- `astro_distributions` — 全生命周期
- `astro_balbillus` — 全生命周期
- `astro_keypoints` — 全生命周期
- `astro_yearsystem129` — 全生命周期
- `astro_planetaryarc` — 全生命周期
- `astro_persiandirected` — 全生命周期
- `astro_agepoint` — 全生命周期
- `astro_vedicprog` — 全生命周期
- `astro_jaynesprog` — 全生命周期
- `astro_horary` — 西式卜卦
- `astro_election` — 择日
- `astro_mundane` — 世运
- `astro_extrareturns` — 多重回归
- `two_person_compatibility` — 合婚/合作
- `sukuyo_compatibility` — 宿曜旁证
- `meihua_analysis` — 问事
- `sixyao` — 问事
- `tongshefa` — 问事
- `suzhan` — 问事
- `otherbu` — 西式星骰
- `sanshiunited` — 问事 / 三式合参
- `canping` — 命格数算（深）
- `heluo` — 命格数算（深）
- `gua_lookup` — 查卦义
- `gua_meiyi` — 查卦义
- `timing_analysis` — 时运聚合主证
- `dayun_analysis` — 时运单粒度
- `liunian_analysis` — 时运单粒度
- `liuyue_analysis` — 时运单粒度
- `liuri_analysis` — 时运单粒度
- `liushi_analysis` — 时运单粒度
- `jieqi_year` — 历法支撑
- `jieqi_timeline_analysis` — 历法支撑
- `nongli_time` — 历法支撑
- `knowledge_registry` — 元工具
- `knowledge_read` — 元工具
- `export_registry` — 元工具
- `export_parse` — 元工具


- `fengshui_directions` — 家居公共方位
- `fengshui_minggua` — 家居个人命卦
- `fengshui_bazhai` — 家居八宅
- `fengshui_jinsuo` — 家居基础砂水
- `fengshui_annual_stars` — 家居年度飞星
- `fengshui_xuankong_natal` — 家居玄空运山向宅盘
- `fengshui_assess` — 家居三法及可选宅盘分层合参

接口与字段见 [API 参考](api-reference.md)，返回[文档中心](README.md)查看其他任务。
