# FateBridge 工作方式

按请求区分工程与咨询。开发、安装、排错、审查和验收使用工程流程；排盘、命理概念和结果解释读取匹配的咨询技能。

按实际任务选择流程：对个人作命理判断的练习或假设仍走咨询入口；只审查代码、资料或评估标准时走工程流程，不因文中出现出生资料就展开个案咨询。

## 工程任务

- 包管理统一使用 uv。源码环境：`uv sync --locked --extra dev`；命令使用 `uv run --locked --extra dev`。依赖用 `uv add` / `uv remove`，同步提交 `uv.lock`；构建用 `uv build`。
- 先检查实际代码、共享契约、相关测试和 Git 状态，保留无关改动。确定性计算维护在领域服务，不由模型复写。
- 修改共享计算或契约时验证 REST、MCP、CLI 一致性。测试见[开发指南](docs/development-guide.md)；本地协议、真实模型行为和部署验收分别报告。
- 场景源在 `skills/*/agents/interface.yaml` 和 `docs/scenario-routing.md`；运行 `uv run --locked --extra dev python scripts/build_scenario_manifest.py` 后运行 `--check`。
- 按需调用合同由 `uv run --locked --extra dev python scripts/build_codex_call_contracts.py` 生成，运行 `--check` 防漂移，不手改生成文件。完整 Schema 不放回本文件。

### 代码简洁与边界

依照 [OpenAI Codex Best Practices](https://learn.chatgpt.com/guides/best-practices) 将持久工程约束放在本文件；本项目采用以下具体原则：

- 逻辑默认留在一个函数内；确有组合或复用需求时再拆分。
- 未知值只在负责它的边界校验一次，向内传递有类型的值；不重复校验 Schema、构造器或内部类型已保证的事实，不反复检查对象类型和属性是否存在。
- 不预先提取仅用一次的辅助函数；默认在调用处展开，除非它隐藏复杂边界，或有清晰独立的名称能改善调用者的可读性。
- 为推测性或极低概率的竞态、安全边缘情形增加复杂度前，先向用户说明具体失败方式、发生可能性与复杂度成本，并取得认可；不静默扩大范围。
- 尽量避免 `try/except`（其他语言的 `try/catch`）；只在需要恢复、清理或转换边界错误时捕获具体异常，不用异常处理代替正常分支。
- 避免 `Any` / `any`；未知输入用 `object` 并在所属边界收窄，内部优先使用领域类型、`TypedDict`、泛型或依赖提供的类型，不靠强制转换掩盖类型缺口。

## 咨询入口

先读取匹配的 `SKILL.md` 及短的[咨询核心](skills/_shared/consultation-core.md)。仅在本轮需要对应分支时读取技能链接的参考。软链接入口先解析真实路径，再解析相对引用。

| 用户问题 | 技能 |
| --- | --- |
| 性格、天赋、做事方式 | [onda-mingge](skills/onda-mingge/SKILL.md) |
| 事业、岗位、晋升、跳槽、创业角色 | [onda-shiye](skills/onda-shiye/SKILL.md) |
| 收入、消费、积累、回款、共同资金 | [onda-caiwu](skills/onda-caiwu/SKILL.md) |
| 恋爱、伴侣、婚姻 | [onda-yuanfen](skills/onda-yuanfen/SKILL.md) |
| 学习、考试、深造、专业 | [onda-xueye](skills/onda-xueye/SKILL.md) |
| 原生家庭、六亲、亲子 | [onda-jiating](skills/onda-jiating/SKILL.md) |
| 朋友、团队、合伙 | [onda-renji](skills/onda-renji/SKILL.md) |
| 传统身心文化解释 | [onda-jiankang](skills/onda-jiankang/SKILL.md) |
| 风水空间、布局和物件 | [onda-fengshui](skills/onda-fengshui/SKILL.md) |
| 无主题限定的整体时运、人生阶段、候选择时 | [onda-shiyun](skills/onda-shiyun/SKILL.md) |
| 索取原始盘，或核对盘式、流派与技法本身；太乙／三式占式见下一行 | [onda-xingpan](skills/onda-xingpan/SKILL.md) |
| 明确起卦、问事；太乙四计／三式合参的技法核对和已有结果解释 | [onda-zhanbu](skills/onda-zhanbu/SKILL.md) |
| 多主题全面画像 | [onda-zige](skills/onda-zige/SKILL.md) |

主题明确的时间问题仍由该主题主持；“算一下”“哪一年”本身不是起卦请求。只有明确求卦、起局或指定占式才进入占卜入口。单主题多体系不扩成人生报告。全面请求按要求覆盖，各依据负责结构、互动或实际时间层，不靠增加工具数量认证结论。

“从命盘看事业／家庭”等主题咨询不因提到命盘就改由盘式入口主持；明确限定八字、紫微等方法时仍尊重该限定。原始盘、盘式原理或技法本身的核对才由盘式入口主持；硬边界问题也先识别实际主题，再停止受限计算。

## 调用与交付

- 使用当前聊天已确认资料。独立咨询不查仓库、历史或记忆；明确要求沿用历史资料时再核对。
- 计算前检查[硬边界](skills/_shared/safety-boundaries.md)：不提供生死寿命、灾祸断言、临床诊断治疗或医疗择时。未知出生时刻不能猜，也不套默认值或示例；必要缺项简短追问，明确不知道后停止追问同项，交付已有可答部分。
- MCP 已连接且定义清楚时直接调用。只在工具或参数不清楚时按名称取得完整定义；本地无连接时可用 CLI。工具和场景发现不是每轮必经步骤。
- 离线核对常用合同见[按需合同索引](docs/contracts/README.md)，只读所选工具文件。以当前连接的实际 Schema 和公开范围为准，不因文件存在而调用隐藏工具。
- 摘要首轮按任务选择已发布 `evidence_views` 的 `fields`，设 `strict_fields=true`、`include_snapshot_text=false`；视图名不是请求参数。完整 JSON、全部时间线或完整文件首次 `fields=null`，再读取同一 run 的 `result_delivery`，不以摘要重算全文。
- 核对 `isError`、实际时区与时间粒度；按错误字段修正，仅可重试错误才重试。更正事实重建受影响输入，沿用 `trace_id` / `parent_run_id`；解释未变结果无需重算。
- 先回答问题，给实际返回依据的传统含义和现实建议。计算、传统解释、现实建议分清；分数不是成功概率，可复现不证明预测有效。`partial` 只限制对应层，不能把未读取当否定或用限制代替解读。
- 风水从技能的咨询闭环与对应分支进入；位置、朝向、现场事实和动作许可分别核对，照片保留候选，普通解释不等待动作 ready。保留 `rulesets` / `rule_trace`，最终交付作者、版本与来源。详细规则只在风水技能中维护。
