# 桌面作者规则与咨询闭环

[场景技能](../SKILL.md) · [咨询闭环](consultation.md) · [工位作者规则](workstation-authored.md) · [交付方式](delivery.md)

本页说明用户明确另选现代 BTB 时的桌面分区、物件证据及动作状态。计算复用 `fengshui_assess`，REST、MCP、CLI 共用输入输出。普通桌面问题不自动启用 BTB；生日、罗盘方向或某张照片也不构成选法依据。

## 来源与方法

`desktop_bagua_btb_v1@1.0.0` 是现代 BTB 作者方法，与八宅、年度紫白及玄空宅盘独立。须显式选版本，矩形桌面均分三行三列，坐者使用的桌沿为近侧；远左不等于东南，不能触发年星或改变个人朝向判断。

- [Anjie Cho的八卦地图](https://www.anjiecho.com/holistic-spaces-blog/2014/4/28/feng-shui-101-the-bagua-map)明确桌面分区与远左丰盛区。
- [Anjie Cho的事业文章](https://www.anjiecho.com/holistic-spaces-blog/attract-abundance-in-your-career-with-feng-shui)明确远左盆栽/鲜花枝候选及使用者侧窗条件。
- [Tori McBrien的事业文章](https://www.ifsguild.org/nine-tips-to-support-your-career/)明确坐者桌沿定位、近中事业区及深色/水景象征；实现选不新增实际水装置的图案或用品。

原始页面获取时间、SHA-256 和字节数记录在 [`desktop-bagua-v1.json`](../../../src/fatebridge/data/fengshui/desktop-bagua-v1.json)。只采用分区、目标、代表物和条件，不采纳健康、财富或事业结果承诺。

[WOFS的办公室作者指引](https://www.wofs.com/7-quick-tips-career-success/)支持书桌避开已确认直走道、裸露横梁正下方和朝向使用者的家具尖角。版本记录于 [`layout-supplements-v1.json`](../../../src/fatebridge/data/fengshui/layout-supplements-v1.json) 的 F4；这三项是可选观察，未提供时不推断，不把灯带当横梁或屏幕框当实体尖角，不外推到床/灶。其有线电话接线方向、硬性左右高低、物件数量和健康/财富断语未采用。

AFSI《The Principles of Feng Shui》本次重新获取的PDF散列与原记录相同：6ab5135060df281fd6a6e376e0516e660c185dd2af2f146a5f850df64cc3b024。印刷页104/PDF页121反对机械套用左右青龙白虎决定建筑入口，不能据此推出桌面手机必须左、右屏必须低。保留分歧，不将搜索结果中的左右规则合为共识。

## 合同

`surface_layouts` 保存边界、近沿、用户目标与物件。`representation` 须有依据，支持活植物、鲜花、水景图、深色用品；手机、饮料瓶、玩偶不按名称自动归为火、水、土。属性尚不确定用 `unknown`，已确认不属于这些代表物用 `other`；照片用 `image_observed`，尚不能作为确认无规则的依据。

桌面近沿是坐者使用的一边。九格坐标以坐者为准：

| 左 | 中 | 右 |
| --- | --- | --- |
| 远左 `far_left` | 远中 `far_center` | 远右 `far_right` |
| 左中 `middle_left` | 中心 `middle_center` | 右中 `middle_right` |
| 近左 `near_left` | 近中 `near_center` | 近右 `near_right` |

表中近排靠身体，远排离身体。物件属性的 `observation_basis` 与位置的 `zone_observation_basis` 各自保存；`zone` 与位置依据成对。确认活植物不等于确认其九格位置，照片位置不能作为确定的 `retain` 依据。只确认左右时不补近远；完整 legend 也在 MCP 描述、input 资源与根目录生成合同中。

`surface_constraints` 单独保存移动／新增许可、固定物件、不可用区域与用户确认的可行区域。许可不证明现状；`feasible_zones` 表示能容纳对象、保持入口视野和必要操作空间，不表示风水效力。

### 逐件读取覆盖与动作

`layout_analysis.surface_analysis` 逐件说明覆盖；每个动作返回规则／来源、传统理由、起点／终点、条件和约束。

| 返回状态 | 如何解释 |
| --- | --- |
| `ready` | 物件、边界、许可及区域可行性已确认；执行时仍须维护条件 |
| `conditional_option` | 许可或可行性待确认，可以先说明条件依据 |
| `candidate_only` | 保留照片候选，先核对影响结论的事实 |
| `blocked` | 相应动作受限；不能改成无来源的次吉位置 |
| `no_independent_placement_rule` | 没有该物件的独立摆放规则；不能称为已算出吉位 |

未覆盖物件列入 `uncovered_item_ids` 并保留 `partial`。只有请求桌面才出现 `surface_analysis` 分支；通用 `analysis_progress` 增加审查与行动元数据，保留原计算结果和 `status` 语义。独立桌面可 `methods=[]`，无需生日、宅向或占位 `placement`；同 ID 的 `placement` 及 `form_observations` 用途必须是 `desk`，约束须正确关联，重复和未知引用拒绝。

`surface_analysis.analysis_progress` 分开记录计算、物件规则覆盖及行动状态；通用汇总在 `layout_analysis.analysis_progress` 和 `coverage.analysis_progress`，只读取coverage也能获得。`rule_coverage_counts`的计数单位由`rule_coverage_count_unit`明确：桌面为已提交物件，通用汇总还包括已呈现的布局检查，均不是传统规则总数。行动计数以候选动作计，可选候选另计`optional_action_count`。

已确认 `other` 但无规则的物件为`reviewed_unsupported`，允许`assessment_complete=true`而保留原partial；`unknown` 和照片属性保留`needs_confirmation`及事实确认理由。计算完成但未确认许可/可行区时，`calculation_status=complete`、`action_readiness=needs_confirmation`可同时存在。可选新增不会使事实审查未完成，blocked不产生该动作的执行追问；独立未知事实仍按审查范围确认。

### 确认事项与审查结束

各桌面动作增加 `action_id`、`optional`、`pending_confirmations`。确认项的`required_for`为`assessment/action/optional_action`，`path`为输入或输出确认锚点，不是新增请求参数。此元数据不扩展物理建模：ready仍是已有边界/属性、许可和区级可行性的确认，规则文本中的植物状态、操作维护条件仍需执行时复核；不同物件的尺寸/容量和非桌面搬转可行性没有新增输入。

## 咨询闭环

先回答本次桌面问题和已有依据，再按当前问题核对会改变结论的事实；具体动作的许可与可行性在落实时确认。实际房间入口与经过通道分开确认；`passage_position` 不触发入口规则。明确 `window_position` 时才判断侧窗，不当砂水或宅向。个人匹配注明所用方法；命卦不等于八字喜用，另算八字也不能自动推导物件位置。

部分资料可先算，但继续跟踪未解决项目。不可搬转时筛允许的有据动作，每项建议连接事实、rule/source、作用域、目标位置与条件；没有处方的物件可保留，不能编吉侧或把整理建议算作风水任务完成。深入逐物件请求不受首轮字数限制。

桌面请求在 `fields` 追加 `layout_analysis.surface_analysis`，所有风水解读保留 `rulesets` 与 `rule_trace`；八宅个人匹配可追加 `layers.bazhai.occupants`。读取已有结果时不重算，更正事实才替换受影响输入并沿用 trace／父 run。
