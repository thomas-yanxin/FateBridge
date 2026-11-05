# 可运行请求示例

[文档中心](../README.md) · [家居风水](../fengshui.md) · [玄空宅盘](../fengshui-xuankong.md)

从基础盘到工位活动与候选布局比较，这组可运行的虚构请求演示空间事实如何进入计算、产生分层结果。按下表选择任务，再运行请求、查看规则来源与覆盖状态，即可学习输入结构或核对应用集成。

示例 JSON 中的日期、方位、许可与可行性只属于虚构输入。实际使用时替换为已确认事实；未知项按模型允许的方式省略，示例结果不能直接套用为住宅方案。

## 选择请求

| 示例文件 | 调用工具 | 用来理解什么 |
| --- | --- | --- |
| [住宅基础合参](fengshui-home.json) | `fengshui_assess` | 八宅、金锁与年盘分层输出 |
| [八宅变爻与宫星关系](fengshui-bazhai-depth.json) | `fengshui_bazhai` | 累计变爻、净变爻和宫星有向生克；基本用途偏好与完整吉凶分开 |
| [八宅候选与布局证据](fengshui-bazhai-candidate-proof.json) | `fengshui_assess` | 未确认男女起法的两套结果；备选方向保留生克与变爻依据 |
| [独立室内形态](fengshui-forms.json) | `fengshui_assess` | 无生辰、无罗盘的入口视野与实体背靠 |
| [元素目标](fengshui-elements.json) | `fengshui_assess` | 对实际计算目标按作用域提出生 / 泄候选 |
| [年度作者规则](fengshui-annual-remedy.json) | `fengshui_assess` | 显式选择限定年份与作者的补充规则 |
| [住宅候选比较](fengshui-home-alternatives.json) | `fengshui_assess` | 现状、候选独立事实与分层差异 |
| [工位候选规划](fengshui-workstation-planning.json) | `fengshui_assess` | 场景选法、搬转许可与物理可行性 |
| [实测工位与完整有限搜索](fengshui-workstation-measured.json) | `fengshui_assess` | 多边形/高度几何、入口与背靠、独立BTB/WOFS规则、逐组合拒绝回执与取舍方案 |
| [自动网格与屏幕视线](fengshui-workstation-grid-screen.json) | `fengshui_assess` | 明确网格自动生成中心候选、整面透视遮挡、候选独立重算及算法覆盖状态 |
| [玄空历史宅盘](fengshui-xuankong.json) | `fengshui_xuankong_natal` | 历史事件定运、宅向与候选角区 |
| [早期宅运完整区间](fengshui-historical-period.json) | `fengshui_xuankong_natal` | 虚构1800年输入；1784–1804端点使用的实际轨道来源 |
| [原书数表差异](fengshui-source-differences.json) | `fengshui_xuankong_natal` | 原图五与计算二分别保留，读取逐候选来源比较 |
| [起星图数表差异](fengshui-replacement-source-differences.json) | `fengshui_xuankong_natal` | 五运子午替卦原图九与计算六、编者范围及未验证的兼向条件 |
| [事件有效年候选](fengshui-event-year-candidates.json) | `fengshui_xuankong_natal` | 依[受控模型运行方法](../fengshui-xuankong.md)，分开读取候选有效年和已确定宅运 |
| [候选节月有效期](fengshui-month-interval-candidates.json) | `fengshui_monthly_stars` | 依[受控模型运行方法](../fengshui.md)，读取各候选节月的完整区间与来源 |
| [宅向误差支持角区](fengshui-bearing-support.json) | `fengshui_xuankong_natal` | 同一个宅盘由哪些测量角区与选盘理由支持 |
| [WMM2025地磁参考](fengshui-geomagnetic.json) | `fengshui_directions` | NOAA数值测试例；原始方位与模型换算候选分别保留 |
| [独立沈氏城门](fengshui-city-gate.json) | `fengshui_xuankong_natal` | 显式参考运、同元龙门位、顺逆；无需编造历史宅运 |
| [玄空与年度并列](fengshui-xuankong-with-annual.json) | `fengshui_assess` | 历史宅盘与年盘的独立作用域 |
| [沈氏主客规则](fengshui-host-guest.json) | `fengshui_xuankong_natal` | 显式选择主客生克；历史宅运、评价运及来源条件分别核对 |
| [玄空有限解释](fengshui-xuankong-interpretation.json) | `fengshui_assess` | 显式启用有来源的有限解释条件 |
| [工位活动](fengshui-workstation-activity.json) | `fengshui_assess` | 书桌工作 / 学习用途与宅盘向星 |
| [入口隔挡](fengshui-entry-barrier.json) | `fengshui_assess` | 入口、桌与隔挡的明确关系和执行条件 |
| [材料施用条件](fengshui-material-application.json) | `fengshui_assess` | 材料资格、施用条件与目标绑定分别核对 |

## 未解析ASC与13扇区

[原生角度退化请求](chart13-unresolved-ascendant.json)是构造的虚构几何反例。未解析的实际落区返回null，后端约定值和全部生时样点分别保留；计算范围见[其他星盘流派](../other-chart-schools.md)。

## 德国盘生时区间

[太阳弧边界请求](germany-solar-arc-boundary.json)以明确的虚构出生、目标时刻及±1分钟区间，演示名义结果有效而部分推运样点未计算的返回。生时区间的读取见[其他星盘流派](../other-chart-schools.md)。全部样点须保留，未计算项不算作条件未成立或概率。

## 六爻教学输入

[旬空、动静与日级条件](liuyao-conditional-demo.json)和[需之讼装卦](liuyao-need-to-song.json)用于 `sixyao`。它们是构造的教学资料，不代表历史占例的真实日期或现实问事。JSON 可作为 MCP 参数或发送至 REST `/api/divination/sixyao`；CLI 按 `describe sixyao --detail input` 转成对应字段参数，不套用风水的 `--request-file`。

## 历法核对示例

[梅花节气日标签对照](meihua-solar-date-reference.json)是明确指定的历史日期与合成正午输入，用于核对官方日标签和实际月令锚点。它未记录现实问事或结果；运行方式及返回字段见[梅花历法说明](../meihua.md)。

## 运行并查看结果

按[快速入门](../getting-started.md)安装后，从仓库根目录执行：

```bash
uv run --locked --extra dev fatebridge fengshui_assess --request-file docs/examples/fengshui-home.json \
  --fields status layers coverage rulesets rule_trace --strict-fields --compact
uv run --locked --extra dev fatebridge fengshui_xuankong_natal --request-file docs/examples/fengshui-xuankong.json --compact
```

两个命令分别演示原始分层结果和独立数字宅盘。查看布局规则时，投影另加实际请求对应的 `layout_analysis` 分支；例如 `fengshui-forms.json` 应读取 `layout_analysis.form_analysis`，`fengshui-home-alternatives.json` 应读取 `layout_analysis.alternatives_analysis`。不要把只投影 `layers` 的输出当成布局审查结果。

REST 将同一文件用 `--data-binary @docs/examples/fengshui-home.json` 发送到对应 POST 路由，MCP 使用文件内容作为参数对象。命令与客户端用法见[三端例子](../fengshui.md#三端例子)。CLI 请求文件未知字段仍会被拒绝，显式字段参数覆盖文件中的同名顶层字段。

先检查协议是否成功，再查看各层 `status`、`coverage`、实际 `rulesets` 与 `rule_trace`。`partial` 可包含可解释结果；`complete` 表示相应请求范围完成。布局请求还要分别看 `layout_analysis.analysis_progress` 中的计算、审查和执行状态，候选未 ready 不阻止解释已有依据。

人物示例另见 [demo-subject.json](../../examples/demo-subject.json)，用于支持 `--subject-file` 的工具；它与完整嵌套 `--request-file` 用途不同。需要完整结果时不要使用上面的字段裁剪，按[完整结果交付](../agent-guide.md#完整结果交付与同次导出)操作。
