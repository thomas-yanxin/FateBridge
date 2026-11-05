---
name: onda-fengshui
description: 用 FateBridge 逐对象解释住宅、办公室、工位的风水依据，对照现状与候选布局，说明可保留、可调整和未覆盖之处。Use when 用户要求风水、宅向、命卦方位、九宫年星、玄空宅盘、室内形态或桌面物件的风水摆法；适用于照片审查、多人共用和不能搬动或转向的布局。不用于仅问事业命理、普通收纳或风水软件开发排错。
---


# 风水与空间布局

逐项回答本次空间和物件问题，说明已有依据、可保留之处、条件式调整及未覆盖范围。使用 FateBridge 计算；传统规则匹配不保证现实健康、财富或事业变化。

## 共用范围与安全

先读短的[咨询核心](../_shared/consultation-core.md)与[风水咨询闭环](references/consultation.md)。工程排错、普通收纳和单纯事业命理不触发本技能。主要方法为九宫飞星、金锁玉关、八宅，保留 `user_expert_policy_v1`（2026-10-15）及实际作者来源；不冒充所有门派共同结论。

## 通用触发与路由

| 用户任务 | 工具与首轮选择 |
| --- | --- |
| 布局、形态、多人或候选比较 | `fengshui_assess` 主入口，`analyze_layout=true`，按实际输入和任务取字段 |
| 仅方位和角区索引 | `fengshui_directions`，通用表不证明真实空间已定宫 |
| 独立个人命卦 | `fengshui_minggua`，支持出生日期，非立春当日无需小时 |
| 八宅人宅匹配 | `fengshui_bazhai`，使用人、位置与朝向各自确认 |
| 已确认砂水 | `fengshui_jinsuo`，物件名称不自动推分类 |
| 年度九宫紫白 | `fengshui_annual_stars`，立春换年，不当历史宅盘 |
| 月紫白与节月 | `fengshui_monthly_stars`，十二节瞬间换月，有效年以立春为界；只解释中性落宫 |
| 历史玄空宅盘 | `fengshui_xuankong_natal`，历史定运、磁北与误差独立；有限解释须显式选择 |

布局优先使用主入口，不为列出的每种方法各调一次。局部工位／合租优先飞星、次金锁，八宅命卦独立加入；缺宅运不以年盘代替。显式指定方法尊重限定，BTB 仅明确另选；旧工位分支的 WOFS 桌面仅作参考。有尺寸的实测分支可另选明确的 WOFS 作者版本，见[实测工位](references/measured-workstation.md)。

## 先解释已有依据

先回答，再解释实际规则与问题的联系，给注明条件的建议；照片写成候选观察。`partial`、候选或动作未 ready 不阻塞已有部分的解释。只追问会改变本次结论的缺项，未知后不反复索取。无规则或未实现直接说明范围。

位置、朝向、宅向和使用人分别核对。无方向可分析已确认的独立形态、关系或材质事实，不由个人命盘补宫。许可和物理可行性只约束动作落实，不能补出现场事实。来源、精度与作者分歧在相关判断处说明。

八宅解读保留累计变爻与净变爻的区别、宫星关系的方向，以及伏位文本语境；`matches_convention` 不是完整吉凶结论。细节见[基础规则](references/rule-sources.md#55-累计变爻与宫星关系)。

## 工位与家居选法

采用宅盘、年盘、金锁或个人匹配时，读[选法与覆盖](references/request-rules.md#工位与家居选法)；历史玄空另读[宅盘资料](references/xuankong.md)，兼向／替星问题另读[替星依据](references/replacement-stars.md)，反伏吟／父母三般卦读[数字结构依据](references/classical-patterns.md)，显式有限解释读[解释规则](references/xuankong-interpretation.md)。

需要逐句校核玄空释义与计算结果时，读[固定释义与同次核验](references/calculation-reading.md)；只对原始run的固定段落声明核验通过，额外模型正文和现实建议单列。

问零正神、五运前后十年或固定方位与飞星要求时，读[沈氏固定零正](references/fixed-lingzheng.md)；固定地盘、候选分段及实际山水分别说明，不以对数匹配认证现场或应验。

问城门、同元龙水口或城门运盘时，读[沈氏城门](references/city-gate.md)；独立参考运及原典版本单列，不以它重置历史宅盘。

问月飞星、节月边界或年／月盘区别时，读[月紫白](references/monthly-stars.md)。先核对含时区时刻或已确认的有效年／节月；不把公历一月当新有效年，不把农历初一或中气当换月。月盘只有中性位置与固定释义，未覆盖的用途、摆放和断事不以年星处方补足。

需核对真北／磁北换算依据时，读[地磁参考](references/geomagnetic-reference.md)；显式地点、椭球高和日期只产生待复测候选，原始宅向与测量误差保持独立。

宅向有测量误差、跨八宫或八宅与玄空候选不同时，读[共享宅向误差](references/house-bearing-uncertainty.md)；同一测量的误差须传递到各已选方法，候选宅卦不能写成已确认布局依据。

追问立春交界、历史钟时或未来日期精度时，读[时间边界](references/calendar-boundaries.md)；保留实际星历模型、历史UT1约定及未来闰秒假设，TT实现比对不冒充实际UTC秒级认证。

## 资料核对与调用

定宫、位置／朝向或对象权限问题读[输入分支](references/request-rules.md#资料核对与调用)。具体参数用当前 MCP 定义；只在定义缺失时取得所选完整合同，CLI 后备见[引擎参考](../_shared/fatebridge-engine.md#怎么调引擎)。

- 厨卫／镜／梁管／尖角双对象关系、材料器形资格：读[有来源的室内规则](references/sourced-interior-rules.md)，不由资格推摆位。
- 工作用途、入口隔挡或材料施用条件：读[工位作者规则](references/workstation-authored.md)。
- 形态或元素调节：读[形态与元素证据](references/layout-rules.md)；规则来源细问再查[基础规则](references/rule-sources.md)。
- 明确另选桌面作者法：读[桌面规则](references/surface-rules.md)，near 靠坐者、far 远离坐者，不等于罗盘方位。

## 家庭、多层和现代设计

涉及人物象征、辈分排行、复式／院落、厨卫材质或纯方法查询时，定位[对应分支](references/request-rules.md#家庭多层和现代设计)。只问象意不绑实际方向；实际多层各自核对中心和使用事实，未列某人不等于已排除使用。

## 实际候选布局

已有实测边界、尺寸和对象清单，或明确请求生成可行方案时，读[实测工位布局](references/measured-workstation.md)。它提供显式参考系的几何与有限搜索，保留全部组合回执；没有尺寸时仍使用普通观察入口，不套示例数值。

用户提出可比较方案时，读[候选输入与重核](references/request-rules.md#实际候选布局)及[场景规划](references/scene-planning.md)。搬动任一端重核相应关系、楼层及目标位置；许可不等于容纳或通行可行，旧观察不能借给新方案。

## 来源与执行闭环

保留 `rulesets`、`rule_trace`，按实际输入追加需要的结果分支，字段选择见[调用与字段](references/request-rules.md#家庭多层和现代设计)。交付作者、版本、来源及作用域；具体动作连接事实、规则、新位置和可行条件，见[闭环](references/request-rules.md#来源与执行闭环)。完整／逐物件审查与方案对照读[交付参考](references/delivery.md)，不强求建议数量。一般表达只在需要细节时定位[Onda 解读参考](../_shared/onda-counsel.md)。
