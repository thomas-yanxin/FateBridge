# 可运行请求示例

[文档中心](../README.md) · [家居风水参考](../fengshui.md) · [接入指南](../agent-guide.md)

本目录提供最小的可运行虚构请求示例，用于快速核对输入结构、字段投影与结果交付。实际使用时请替换为已确认的用户事实。

## 示例清单

| 示例文件 | 适用工具 | 用途说明 |
| --- | --- | --- |
| [demo-subject.json](../../examples/demo-subject.json) | `astrology_chart` 等含经纬度的出生盘工具 | 通用虚构人物出生档案模板 |
| [fengshui-home.json](fengshui-home.json) | `fengshui_assess` | 八宅、金锁砂水、年星与玄空分层住宅合参 |
| [fengshui-xuankong.json](fengshui-xuankong.json) | `fengshui_xuankong_house_chart` | 中州派历史定运与宅向宅盘 |
| [liuyao-conditional-demo.json](liuyao-conditional-demo.json) | `liuyao` | 旬空、动静与日级条件示例输入 |

## 运行示例

按[快速入门](../getting-started.md)安装后，在仓库根目录执行 CLI（所有 91 个目录命令均支持 `--request-file`）：

```bash
uv run --extra dev fatebridge fengshui_assess --request-file docs/examples/fengshui-home.json \
  --fields status layers palace_overlay layout_analysis coverage
uv run --extra dev fatebridge fengshui_xuankong_house_chart --request-file docs/examples/fengshui-xuankong.json
uv run --extra dev fatebridge astrology_chart --request-file examples/demo-subject.json
uv run --extra dev fatebridge liuyao --request-file docs/examples/liuyao-conditional-demo.json
```

REST 可通过 `--data-binary @docs/examples/fengshui-home.json` 发送到对应 `POST` 路由（例如 `http://localhost:8010/api/fengshui/assess`）；MCP 直接将 JSON 文件解析为 `run_calculation` 的 `arguments` 对象参数。命令行参数详情可通过 `fatebridge discover <tool>` 查看。

核对响应时先检查协议状态与顶层错误包络，再查看各层 `status`、`coverage` 与 `run_metadata.omitted_fields`；`partial` 表示对应层范围受限但已有部分事实可解释。需要无损完整输出载荷时请省略 `--fields` 并传入 `include=["*"]`（CLI `--include "*"`），参见[输出控制与结果读取](../agent-guide.md#输出控制与结果读取)。
