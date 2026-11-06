# 可选工具筛选配置

这些 YAML 从已移除的 Onda 技能接口迁出，保留现有 `onda-*` 场景 ID 及其工具、依赖和路由。场景 ID 是可选工具配置的名称，不再对应技能包，也不规定助手必须读取的参考或执行的咨询流程。

默认不指定场景时公开全部 MCP 工具。不要用某个配置的工具子集代表 FateBridge 的全部能力；当前能力以中央工具目录和实时 Schema 为准。

## 场景与接口的关系

共有14个场景：本目录的13份 YAML 各定义一个场景，`fengshui` 基础计算场景另从[住宅路由表](../../docs/scenario-routing.md#家居风水基础计算)生成。`onda-fengshui` 与 `fengshui` 是两个独立配置，不能互换名称。

| 使用位置 | 实际作用 |
| --- | --- |
| REST `/api/scenarios`、CLI `scenarios`、MCP `fatebridge://scenarios` | 查看配置、依赖、候选工具及实际可用范围 |
| REST `/api/tools?scenario=...`、CLI `discover --scenario ...` | 按场景筛选发现结果；不限制 REST／CLI 的业务调用 |
| `FATEBRIDGE_MCP_SCENARIOS` | 限制 MCP 实际注册的工具；与 `FATEBRIDGE_MCP_FAMILIES` 取交集，修改后重启连接 |
| `FATEBRIDGE_MCP_TOOL_SCOPE` | 默认 `complete` 展开条件依赖；`topic` 仅保留直接工具和知识支撑，必须同时指定场景 |

多个场景 ID 用逗号分隔并取并集。条件依赖是否公开与何时调用是两件事；完整范围公开的工具也不要求自动执行。环境配置和启动验证见[MCP 部署](../../docs/mcp-deployment.md#工具筛选与运行环境)。

## 维护与生成

维护源为本目录的 YAML 与 [场景路由](../../docs/scenario-routing.md)。变更后运行：

```bash
uv run --locked --extra dev python scripts/build_scenario_manifest.py
uv run --locked --extra dev python scripts/build_scenario_manifest.py --check
```

生成物为 `src/fatebridge/data/agent_scenarios.json`，随 Python 包分发；运行时读取该 JSON，不直接解析 YAML。生成时验证工具名称和依赖闭包，共享参考参与来源记录。`required_inputs` 是配置级指引，实际必填参数由所选工具 Schema 决定。
