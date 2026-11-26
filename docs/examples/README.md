# 可运行请求示例

[文档中心](../README.md) · [家居风水](../fengshui.md)

本目录提供最小的可运行虚构请求示例，用于快速核对输入结构、字段投影与结果交付。实际使用时请替换为已确认事实。

## 示例清单

| 示例文件 | 适用工具 | 用途说明 |
| --- | --- | --- |
| [demo-subject.json](../../examples/demo-subject.json) | 支持 `--subject-file` 的 CLI 工具 | 通用虚构人物出生档案模板 |
| [fengshui-home.json](fengshui-home.json) | `fengshui_assess` | 八宅、砂水、年星与玄空分层住宅合参 |
| [fengshui-xuankong.json](fengshui-xuankong.json) | `fengshui_xuankong_house_chart` | 中州派历史定运与宅向候选盘 |
| [fengshui-workstation-measured.json](fengshui-workstation-measured.json) | `fengshui_assess` | 实测工位几何、入口背靠与有限候选搜索 |
| [fengshui-workstation-activity.json](fengshui-workstation-activity.json) | `fengshui_assess` | 工位用途活动与宅盘向星关联 |
| [fengshui-entry-barrier.json](fengshui-entry-barrier.json) | `fengshui_assess` | 入口、书桌与隔挡空间条件 |
| [fengshui-material-application.json](fengshui-material-application.json) | `fengshui_assess` | 材质资格与目标绑定条件 |
| [liuyao-conditional-demo.json](liuyao-conditional-demo.json) | `sixyao` (`liuyao`) | 旬空、动静与日级条件示例输入 |

## 运行示例

按[快速入门](../getting-started.md)安装后，在仓库根目录执行 CLI：

```bash
uv run --locked --extra dev fatebridge fengshui_assess --request-file docs/examples/fengshui-home.json \
  --fields status layers coverage rulesets rule_trace --strict-fields --compact
uv run --locked --extra dev fatebridge fengshui_xuankong_house_chart --request-file docs/examples/fengshui-xuankong.json --compact
uv run --locked --extra dev fatebridge bazi_birth_chart --subject-file examples/demo-subject.json --compact
```

REST 可用 `--data-binary @docs/examples/fengshui-home.json` 发送到对应 POST 路由；MCP 直接将文件内容作为 `arguments` 参数对象传递。六爻示例 JSON 可作为 MCP 参数或 REST `/api/divination/liuyao` 请求体，CLI 请按 `fatebridge describe liuyao --detail input` 传入对应命令行参数。

先检查协议状态，再查看各层 `status`、`coverage`、`rulesets` 与 `rule_trace`；`partial` 表示对应层范围受限但已有部分事实可解释。需要完整结果时请省略字段裁剪并采用 `detail=audit`，参见[完整结果交付](../agent-guide.md#完整结果交付与同次导出)。
