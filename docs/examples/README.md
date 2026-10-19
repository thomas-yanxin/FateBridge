# 可运行请求示例

[文档中心](../README.md) · [家居风水](../fengshui.md) · [玄空宅盘](../fengshui-xuankong.md)

这里的 JSON 都是虚构体验输入，不是可直接套用的住宅方案。将自己的已确认事实替换进去；未知项按模型允许的方式省略，不能把示例中的日期、方位、许可或可行性当作现场事实。

## 选择请求

| 示例文件 | 调用工具 | 用来理解什么 |
| --- | --- | --- |
| [住宅基础合参](fengshui-home.json) | `fengshui_assess` | 八宅、金锁与年盘分层输出 |
| [独立室内形态](fengshui-forms.json) | `fengshui_assess` | 无生辰、无罗盘的入口视野与实体背靠 |
| [元素目标](fengshui-elements.json) | `fengshui_assess` | 对实际计算目标按作用域提出生 / 泄候选 |
| [年度作者规则](fengshui-annual-remedy.json) | `fengshui_assess` | 显式选择限定年份与作者的补充规则 |
| [住宅候选比较](fengshui-home-alternatives.json) | `fengshui_assess` | 现状、候选独立事实与分层差异 |
| [工位候选规划](fengshui-workstation-planning.json) | `fengshui_assess` | 场景选法、搬转许可与物理可行性 |
| [玄空历史宅盘](fengshui-xuankong.json) | `fengshui_xuankong_natal` | 历史事件定运、宅向与候选角区 |
| [玄空与年度并列](fengshui-xuankong-with-annual.json) | `fengshui_assess` | 历史宅盘与年盘的独立作用域 |
| [玄空有限解释](fengshui-xuankong-interpretation.json) | `fengshui_assess` | 显式启用有来源的有限解释条件 |
| [工位活动](fengshui-workstation-activity.json) | `fengshui_assess` | 书桌工作 / 学习用途与宅盘向星 |
| [入口隔挡](fengshui-entry-barrier.json) | `fengshui_assess` | 入口、桌与隔挡的明确关系和执行条件 |
| [材料施用条件](fengshui-material-application.json) | `fengshui_assess` | 材料资格、施用条件与目标绑定分别核对 |

## 运行并查看结果

从仓库根目录、已激活的安装环境执行：

```bash
fatebridge fengshui_assess --request-file docs/examples/fengshui-home.json \
  --fields status layers coverage rulesets rule_trace --strict-fields --compact
fatebridge fengshui_xuankong_natal --request-file docs/examples/fengshui-xuankong.json --compact
```

REST 将同一文件用 `--data-binary @docs/examples/fengshui-home.json` 发送到对应 POST 路由，MCP 使用文件内容作为参数对象。命令与客户端用法见[三端例子](../fengshui.md#三端例子)。CLI 请求文件未知字段仍会被拒绝，显式字段参数覆盖文件中的同名顶层字段。

先检查协议是否成功，再查看各层 `status`、`coverage`、实际 `rulesets` 与 `rule_trace`。`partial` 可包含可解释结果；`complete` 表示相应请求范围完成。布局请求还要分别看 `layout_analysis.analysis_progress` 中的计算、审查和执行状态，候选未 ready 不阻止解释已有依据。

人物示例另见 [demo-subject.json](../../examples/demo-subject.json)，用于支持 `--subject-file` 的工具；它与完整嵌套 `--request-file` 用途不同。需要完整结果时不要使用上面的字段裁剪，按[完整结果交付](../agent-guide.md#完整结果交付与同次导出)操作。
